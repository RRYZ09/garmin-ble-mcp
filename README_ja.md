# garmin-ble-mcp

GarminウォッチからBluetoothLE経由でリアルタイム心拍数を取得するMCPサーバー — Garmin Connect不要、インターネット不要、クラウド不要。

## なぜこれが必要か？

`garmin-health-mcp` はGarmin Connectに同期された過去データを取得します。こちらは**今この瞬間**の心拍数を、ウォッチからBLE直接通信で取得します。

## ツール一覧

| ツール | 説明 |
|--------|------|
| `get_realtime_heart_rate` | ウォッチから現在のBPMを取得。3回計測して平均を返す。 |
| `scan_ble_devices` | 心拍サービスを持つ近くのBLEデバイスをスキャン。 |

## 仕組み

- `get_realtime_heart_rate` — `gatttool` で接続し、Garmin独自のCCCD（ハンドル `0x0013`）と標準の心拍数Measurement CCCD（ハンドル `0x003b`）の両方に書き込んだ後、ハンドル `0x003a`（characteristic `0x2A37`）のHR通知を読み取ります。
- `scan_ble_devices` — `bleak` を使って標準のHRサービスUUIDまたはGarminメーカーIDを持つBLEデバイスをスキャンします。

Vivoactive 5はHR UUIDをアドバタイズしないため、`get_realtime_heart_rate` はスキャンせずMACアドレス直指定で接続します。

## 必要なもの

- Linux（HRは `gatttool`、スキャンは `bleak` を使用）
- Python 3 + `bleak`: `pip install bleak`
- `bluez` ツール: `sudo apt install bluez`
- BLE権限: `sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)` またはroot実行
- Node.js 18以上

## セットアップ

```bash
git clone https://github.com/lifemate-ai/garmin-ble-mcp.git
cd garmin-ble-mcp
npm install
pip install bleak
```

`hr_reader.py` の `ADDR` をあなたのウォッチのBluetoothMACアドレスに変更：

```python
ADDR = '64:A3:37:07:83:FD'  # ← 自分のウォッチのMACアドレスに変える
```

MACアドレスの調べ方：

```bash
bluetoothctl scan on
# ウォッチの名前が表示されたらCtrl+Cで停止
```

## Claude Codeに追加

`~/.claude.json` に追記：

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

## 出力例

```json
{
  "device": "vívoactiv",
  "heartRate": 99,
  "average": 99,
  "readings": [98, 99, 99],
  "timestamp": "2026-04-21T05:38:48.432788+00:00"
}
```

## ライセンス

MIT
