# ZHA Quirks

I have a few Devices that do not work with ZHA out of the box. My files can be found here. 

To use one of these Quirks create a directory in the `directory`, called `zha_quirks` and place the downloaded file in there.
You have to restart Home Assistant to activate the quirk.

The ones that modify an existing zha core device, I have submitted a PR for, so the might eventually show up in Core, and then you can delete the quirk in this directory.


## Quirks in this directory

| File | Device | Manufacturer / Model | What the quirk does | Upstream status |
|---|---|---|---|---|
| [`nimly_easycodetouch.py`](nimly_easycodetouch.py) | Nimly EasyCodeTouch / EasyFingerTouch door lock | Onesti Products AS / `EasyFingerTouch`, `EasyCodeTouch`, `easyCodeTouch_v1` | Fixes the battery level, which shows half the real value (a full battery reads 50%). The lock reports `battery_percentage_remaining` as 0–100 instead of the Zigbee 0–200 scale, so the quirk replaces PowerConfiguration with `DoublingPowerConfigurationCluster`. It also adds the `NimlyDoorLock` cluster that the built-in quirk's sensors rely on. Otherwise identical to the built-in `zhaquirks.nimly.lock` quirk. | PR [zigpy/zha-device-handlers#5749](https://github.com/zigpy/zha-device-handlers/pull/5749). Delete the file once the fix ships in a HA release. |
| [`schneider_lk_switch.py`](schneider_lk_switch.py) | Schneider LK FUGA Wiser double relay ("LK Switch") | Schneider Electric / `LK Switch` (545D6514) | Exposes Schneider's manufacturer-specific switch configuration cluster (0xFF17) as config entities for each button endpoint (21–24): **Switch actions S1–S4** and **Switch indication S1–S4** (LED behaviour). This lets you decouple a rocker from the relay. Set the bottom row (S3/S4, endpoints 23/24) to `Scene` and they only send `zha_event` (`recall`, cluster 5, told apart by `endpoint_id`), while the top row keeps controlling the relay. `NotUsed` disables a button completely. Tested on firmware 0x010218ff, and the setting survives restarts. | Not in zha-device-handlers. Not submitted. |
| [`vibration_agl01.py`](vibration_agl01.py) | Aqara Vibration Sensor T1 | LUMI / `lumi.vibration.agl01` (DJT12LM) | Adds support for the T1, which ZHA treats as a plain IAS device out of the box (just odd IAS zone entities and unknown battery). Based on the Zigbee2MQTT definition. Adds a vibration binary sensor with an adjustable reset timeout (default 70 s), battery percentage and voltage, and selects for sensitivity (high/medium/low) and report interval (1/5/10 s). The selects are write-only on the device, so writes are queued until it wakes. Also adds `zha_event`s and device triggers for `vibration` and `triple_tap`. No tilt/drop/angle data, because the T1 hardware doesn't send it. Tested with zha-quirks 2.4.1 / zha 2.4.3 (HA 2026.11.3). | Not merged upstream. Related: issue #4137 and PR #4972. |
