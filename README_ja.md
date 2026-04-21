# garmin-ble-mcp

GarminウォッチからBluetoothLE経由でリアルタイム心拍数を取得するMCPサーバー — Garmin Connect不要、インターネット不要、クラウド不要。

## なぜこれが必要か？

`garmin-health-mcp` はGarmin Connectに同期された過去データを取得します。こちらは**今この瞬間**の心拍数を、ウォッチからBLE直接通信で取得します。

## ツール一覧

| ツール | 説明 |
|--------|------|
| `get_realtime_heart_rate` | ウォッチから現在のBPMを取得。3回計測して平均を返す。 |
| `scan_ble_devices` | 心拍サービスを持つ近くのBLEデバイスをスキャン。 |
| `get_hrv_analysis` | RR間隔を収集してHRV解析。RMSSD・SDNN・LF/HF比を返す。デフォルト120秒。 |

## 検証済み機種

| 機種 | 状態 |
|------|------|
| Garmin Vivoactive 5 | ✓ 動作確認済み |

## ウォッチの準備：心拍転送モードの有効化

接続前に、ウォッチで**心拍転送モード**を有効にする必要があります：

1. **右上のボタン**を長押し
2. **コントロール**を開く
3. **心拍転送**をタップ

ウォッチがBLEで心拍数をブロードキャストし始めます。セッションごとに1回行えばOKです。

## トラブルシューティング

| エラー | 原因 | 対処 |
|--------|------|------|
| `Garmin device not found. Make sure Bluetooth is on and the watch is nearby.` | BLE接続タイムアウト — ウォッチの電源オフ、圏外、またはBluetoothが無効 | Bluetoothをオンにしてウォッチを近づけ、再試行 |
| `Device connected but no heart rate data received. Enable heart rate broadcast mode on the watch.` | ウォッチには接続できたが心拍データが届いていない | ウォッチで心拍転送モードを有効にする（上記「ウォッチの準備」参照） |

どちらのエラーも、ツールが失敗する前にMCPログ通知（`warning`レベル）としてリアルタイムで送信されます。

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

`rr_source` は、ウォッチがRR間隔を直接送信している場合 `ble_rr`、BPMから近似した場合 `hr_derived`（精度低め）になります。

## ライセンス

MIT
