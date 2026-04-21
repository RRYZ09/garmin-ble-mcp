# garmin-ble-mcp

[日本語版 README はこちら](README_ja.md)

MCP server for real-time heart rate directly from a Garmin watch via Bluetooth LE — no Garmin Connect, no internet, no cloud.

## Why?

`garmin-health-mcp` gives you historical data synced to Garmin Connect. This gives you **right now** — current BPM, straight from the watch over BLE.

## Tools

| Tool | Description |
|------|-------------|
| `get_realtime_heart_rate` | Current BPM from the watch. Averages 3 readings. |
| `scan_ble_devices` | Scan for nearby BLE devices that expose a heart rate service. |
| `get_hrv_analysis` | Collect RR intervals and compute HRV: RMSSD, SDNN, LF/HF ratio. Default 120s. |

## Tested Devices

| Device | Status |
|--------|--------|
| Garmin Vivoactive 5 | ✓ Verified |

## Watch Setup: Heart Rate Broadcast Mode

Before connecting, enable **Heart Rate Broadcast** on the watch:

1. Long-press the **top-right button**
2. Open **Controls**
3. Tap **Heart Rate Broadcast**

The watch will start broadcasting heart rate over BLE. You only need to do this once per session.

## How it works

- `get_realtime_heart_rate` — connects via `gatttool`, writes to both Garmin's proprietary CCCD (handle `0x0013`) and the standard HR Measurement CCCD (handle `0x003b`), then reads HR notifications on handle `0x003a` (characteristic `0x2A37`).
- `scan_ble_devices` — uses `bleak` to scan for BLE devices with the standard HR service UUID or Garmin manufacturer ID.

The Vivoactive 5 doesn't advertise the HR UUID, so `get_realtime_heart_rate` connects directly by MAC address rather than scanning.

## Requirements

- Linux (uses `gatttool` for HR, `bleak` for scanning)
- Python 3 with `bleak`: `pip install bleak`
- `bluez` tools: `sudo apt install bluez`
- BLE permissions: `sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)` or run as root
- Node.js 18+

## Setup

```bash
git clone https://github.com/lifemate-ai/garmin-ble-mcp.git
cd garmin-ble-mcp
npm install
pip install bleak
```

Update the `ADDR` in `hr_reader.py` to your watch's Bluetooth MAC address:

```python
ADDR = '64:A3:37:07:83:FD'  # change this to your watch
```

To find your watch's MAC address:

```bash
bluetoothctl scan on
# look for your watch name in the output
```

## Add to Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "garmin-ble": {
      "command": "node",
      "args": ["/path/to/garmin-ble-mcp/index.js"]
    }
  }
}
```

## Example Output

`get_realtime_heart_rate`:
```json
{
  "device": "vívoactiv",
  "heartRate": 99,
  "average": 99,
  "readings": [98, 99, 99],
  "timestamp": "2026-04-21T05:38:48.432788+00:00"
}
```

`get_hrv_analysis`:
```json
{
  "device": "vívoactiv",
  "duration_seconds": 120,
  "rr_count": 142,
  "rr_source": "ble_rr",
  "time_domain": {
    "mean_hr_bpm": 68.2,
    "sdnn_ms": 45.3,
    "rmssd_ms": 38.1
  },
  "frequency_domain": {
    "lf_power_ms2": 0.0234,
    "hf_power_ms2": 0.0189,
    "lf_hf_ratio": 1.24
  },
  "interpretation": "balanced",
  "timestamp": "2026-04-21T05:38:48.432788+00:00"
}
```

`rr_source` is `ble_rr` when the watch sends raw RR intervals, or `hr_derived` (less accurate) when approximated from BPM readings.

## License

MIT
