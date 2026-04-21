#!/usr/bin/env python3
"""
Collect RR intervals from Garmin Vivoactive 5 and compute HRV metrics.

Uses the same BLE GATT connection as hr_reader.py. If the device sends
RR interval data (flag bit 4), those are used directly; otherwise HR
readings are converted to approximate RR intervals.

HRV metrics:
  Time domain : RMSSD, SDNN, mean HR
  Frequency   : LF power (0.04–0.15 Hz), HF power (0.15–0.4 Hz), LF/HF ratio
"""
import subprocess, time, threading, queue, json, sys, re
import numpy as np
from datetime import datetime, UTC

ADDR = '64:A3:37:07:83:FD'
HR_CCCD_HANDLE   = 0x003b
GARMIN_INIT_CCCD = 0x0013

NOTIF_RE = re.compile(r'Notification handle = 0x003a value: ([0-9a-f ]+)', re.IGNORECASE)

MIN_RR_COUNT = 30  # minimum samples for meaningful LF/HF


def parse_hr_measurement(value_bytes):
    """Return (hr_bpm, [rr_ms, ...]) from a BLE HR Measurement value."""
    flags = value_bytes[0]
    offset = 1

    if flags & 0x01:
        hr = int.from_bytes(value_bytes[offset:offset + 2], 'little')
        offset += 2
    else:
        hr = value_bytes[offset]
        offset += 1

    if flags & 0x08:  # energy expended present
        offset += 2

    rr_list = []
    if flags & 0x10:  # RR interval present (1/1024 sec units)
        while offset + 1 < len(value_bytes):
            raw = int.from_bytes(value_bytes[offset:offset + 2], 'little')
            rr_ms = raw * 1000.0 / 1024.0
            if 300 <= rr_ms <= 2000:
                rr_list.append(rr_ms)
            offset += 2

    return hr, rr_list


def compute_hrv(rr_ms):
    rr = np.array(rr_ms, dtype=float)

    # --- time domain ---
    mean_hr = round(60000.0 / np.mean(rr), 1)
    sdnn    = round(float(np.std(rr, ddof=1)), 1)
    rmssd   = round(float(np.sqrt(np.mean(np.diff(rr) ** 2))), 1)

    # --- frequency domain ---
    # Interpolate to uniform 4 Hz grid
    t = np.cumsum(rr) / 1000.0  # seconds
    t -= t[0]
    fs = 4.0
    t_uni = np.arange(0, t[-1], 1.0 / fs)
    rr_uni = np.interp(t_uni, t, rr)

    # Remove mean, apply Hanning window
    rr_d = rr_uni - np.mean(rr_uni)
    n = len(rr_d)
    win = np.hanning(n)
    psd = np.abs(np.fft.rfft(rr_d * win)) ** 2 / (np.sum(win ** 2) * fs)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    df = freqs[1] - freqs[0]

    lf_mask = (freqs >= 0.04) & (freqs < 0.15)
    hf_mask = (freqs >= 0.15) & (freqs < 0.40)
    lf_power = float(np.sum(psd[lf_mask]) * df)
    hf_power = float(np.sum(psd[hf_mask]) * df)
    lf_hf    = round(lf_power / hf_power, 3) if hf_power > 0 else None

    # simple interpretation
    if lf_hf is None:
        interp = 'unknown'
    elif lf_hf < 1.0:
        interp = 'relaxed (parasympathetic dominant)'
    elif lf_hf <= 2.0:
        interp = 'balanced'
    else:
        interp = 'stressed (sympathetic dominant)'

    return {
        'time_domain': {
            'mean_hr_bpm': mean_hr,
            'sdnn_ms': sdnn,
            'rmssd_ms': rmssd,
        },
        'frequency_domain': {
            'lf_power_ms2': round(lf_power, 4),
            'hf_power_ms2': round(hf_power, 4),
            'lf_hf_ratio': lf_hf,
        },
        'interpretation': interp,
    }


def run(duration_seconds=120):
    proc = subprocess.Popen(
        ['gatttool', '-b', ADDR, '-I'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    q = queue.Queue()
    def reader():
        for line in proc.stdout:
            q.put(line.strip())
    threading.Thread(target=reader, daemon=True).start()

    def send(cmd):
        try:
            proc.stdin.write(cmd + '\n')
            proc.stdin.flush()
        except BrokenPipeError:
            pass

    def wait_for(keyword, timeout=12):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if keyword.lower() in q.get(timeout=0.2).lower():
                    return True
            except queue.Empty:
                pass
        return False

    send('connect')
    if not wait_for('Connection successful', timeout=12):
        proc.kill()
        return None, 'Connection timed out'

    send(f'char-write-req 0x{GARMIN_INIT_CCCD:04x} 0100')
    send(f'char-write-req 0x{HR_CCCD_HANDLE:04x} 0100')

    rr_intervals = []   # from RR fields in characteristic
    hr_readings  = []   # fallback: (timestamp, hr_bpm)
    has_rr_data  = False
    deadline = time.time() + duration_seconds

    while time.time() < deadline:
        try:
            line = q.get(timeout=0.5)
            m = NOTIF_RE.search(line)
            if m:
                raw = bytes.fromhex(m.group(1).replace(' ', ''))
                hr, rr_list = parse_hr_measurement(raw)
                if 30 <= hr <= 220:
                    hr_readings.append((time.time(), hr))
                if rr_list:
                    has_rr_data = True
                    rr_intervals.extend(rr_list)
        except queue.Empty:
            pass
        if proc.poll() is not None:
            break

    try:
        send('quit')
        proc.wait(timeout=2)
    except Exception:
        proc.kill()

    if not hr_readings:
        return None, 'No heart rate data received'

    # If no RR data from characteristic, derive from HR readings
    if not has_rr_data:
        rr_intervals = [60000.0 / hr for (_, hr) in hr_readings]
        rr_source = 'hr_derived'
    else:
        rr_source = 'ble_rr'

    if len(rr_intervals) < MIN_RR_COUNT:
        return None, (
            f'Not enough data ({len(rr_intervals)} RR intervals). '
            f'Need at least {MIN_RR_COUNT}. Try a longer duration.'
        )

    hrv = compute_hrv(rr_intervals)

    return {
        'device': 'vívoactiv',
        'duration_seconds': duration_seconds,
        'rr_count': len(rr_intervals),
        'rr_source': rr_source,
        **hrv,
        'timestamp': datetime.now(UTC).isoformat(),
    }, None


if __name__ == '__main__':
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    result, err = run(duration)
    if err:
        print(json.dumps({'error': err}))
        sys.exit(1)
    print(json.dumps(result))
