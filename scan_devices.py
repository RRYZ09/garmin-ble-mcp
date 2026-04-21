#!/usr/bin/env python3
import asyncio
import json
import sys
from bleak import BleakScanner

HR_SERVICE = "0000180d-0000-1000-8000-00805f9b34fb"
GARMIN_COMPANY_ID = 135

async def main(timeout: int):
    found = {}

    def on_detect(device, adv):
        uuids = [u.lower() for u in (adv.service_uuids or [])]
        has_hr = HR_SERVICE in uuids or GARMIN_COMPANY_ID in adv.manufacturer_data
        found[device.address] = {
            "name": device.name or "(unknown)",
            "address": device.address,
            "rssi": adv.rssi,
            "hasHrService": has_hr,
        }

    scanner = BleakScanner(detection_callback=on_detect)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    devices = list(found.values())
    print(json.dumps({"devices": devices, "count": len(devices)}))

if __name__ == "__main__":
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(main(timeout))
