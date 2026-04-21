#!/usr/bin/env python3
"""
Read real-time heart rate from Garmin Vivoactive 5 via BLE GATT.

The watch requires writing to handle 0x0013 (Garmin proprietary CCCD) and
handle 0x003b (HR Measurement CCCD) in quick succession before sending
HR notifications on handle 0x003a (HR Measurement characteristic, 0x2A37).
"""
import subprocess, time, threading, queue, json, sys, re, argparse
from datetime import datetime, UTC

ADDR = '64:A3:37:07:83:FD'
HR_VALUE_HANDLE = 0x003a
HR_CCCD_HANDLE  = 0x003b
GARMIN_INIT_CCCD = 0x0013

def parse_hr(value_bytes):
    """Parse BLE Heart Rate Measurement characteristic value."""
    flags = value_bytes[0]
    if flags & 0x01:  # 16-bit HR
        return int.from_bytes(value_bytes[1:3], 'little')
    else:             # 8-bit HR
        return value_bytes[1]

def run(timeout_seconds=15, samples=3):
    proc = subprocess.Popen(
        ['gatttool', '-b', ADDR, '-I'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
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
        return None, 'Garmin device not found. Make sure Bluetooth is on and the watch is nearby.'

    # Send both CCCD writes without waiting for responses
    send(f'char-write-req 0x{GARMIN_INIT_CCCD:04x} 0100')
    send(f'char-write-req 0x{HR_CCCD_HANDLE:04x} 0100')

    # Parse HR notifications
    readings = []
    device_name = 'vívoactiv'
    deadline = time.time() + timeout_seconds
    notif_re = re.compile(r'Notification handle = 0x003a value: ([0-9a-f ]+)', re.IGNORECASE)

    while time.time() < deadline and len(readings) < samples:
        try:
            line = q.get(timeout=0.5)
            m = notif_re.search(line)
            if m:
                raw = bytes.fromhex(m.group(1).replace(' ', ''))
                hr = parse_hr(raw)
                if 30 <= hr <= 220:
                    readings.append(hr)
        except queue.Empty:
            pass
        if proc.poll() is not None:
            break

    try:
        send('quit')
        proc.wait(timeout=2)
    except Exception:
        proc.kill()

    if not readings:
        return None, 'Device connected but no heart rate data received. Enable heart rate broadcast mode on the watch.'

    return {
        'device': device_name,
        'heartRate': readings[-1],
        'average': round(sum(readings) / len(readings)),
        'readings': readings,
        'timestamp': datetime.now(UTC).isoformat(),
    }, None

def run_bridge(host, timeout_seconds=15, samples=3):
    """Get heart rate from Android bridge app via WebSocket."""
    try:
        import websocket
    except ImportError:
        return None, 'websocket-client not installed. Run: pip install websocket-client'

    url = f'ws://{host}:8765'
    try:
        ws = websocket.create_connection(url, timeout=10)
    except Exception as e:
        return None, f'Cannot connect to bridge at {host}:8765. Is the app running? ({e})'

    readings = []
    deadline = time.time() + timeout_seconds
    first_data_deadline = time.time() + 10

    try:
        while time.time() < deadline and len(readings) < samples:
            ws.settimeout(0.5)
            try:
                msg = json.loads(ws.recv())
                if msg.get('type') == 'hr':
                    hr = msg['hr']
                    if 30 <= hr <= 220:
                        readings.append(hr)
            except Exception:
                pass

            if not readings and time.time() > first_data_deadline:
                return None, 'Connected to bridge but no HR data received. Enable heart rate broadcast mode on the watch.'
    finally:
        ws.close()

    if not readings:
        return None, 'Connected to bridge but no HR data received. Enable heart rate broadcast mode on the watch.'

    return {
        'device': 'vívoactiv (bridge)',
        'heartRate': readings[-1],
        'average': round(sum(readings) / len(readings)),
        'readings': readings,
        'timestamp': datetime.now(UTC).isoformat(),
    }, None


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('timeout', nargs='?', type=int, default=15)
    parser.add_argument('--bridge', type=str, help='Android bridge app IP address')
    args = parser.parse_args()

    if args.bridge:
        result, err = run_bridge(args.bridge, args.timeout)
    else:
        result, err = run(args.timeout)

    if err:
        print(json.dumps({'error': err}))
        sys.exit(1)
    print(json.dumps(result))
