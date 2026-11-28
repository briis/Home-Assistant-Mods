# ZHA Quirks

I have a few Devices that do not work with ZHA out of the box. My files can be found here. 

To use one of these Quirks create a directory in the `directory`, called `zha_quirks` and place the downloaded file in there.
You have to restart Home Assistant to activate the quirk.

The ones that modify an existing zha core device, I have submitted a PR for, so the might eventually show up in Core, and then you can delete the quirk in this directory.


## Quirks in this directory

| File | Device | Manufacturer / Model | What the quirk does | Upstream status |
|---|---|---|---|---|
| [`nimly_easycodetouch.py`](nimly_easycodetouch.py) | Nimly EasyCodeTouch / EasyFingerTouch door lock | Onesti Products AS / `EasyFingerTouch`, `EasyCodeTouch`, `easyCodeTouch_v1` | Fixes the battery level, which shows half the real value (a full battery reads 50%). The lock reports `battery_percentage_remaining` as 0–100 instead of the Zigbee 0–200 scale, so the quirk replaces PowerConfiguration with `DoublingPowerConfigurationCluster`. It also adds the `NimlyDoorLock` cluster that the built-in quirk's sensors rely on. Otherwise identical to the built-in `zhaquirks.nimly.lock` quirk. | PR [zigpy/zha-device-handlers#5749](https://github.com/zigpy/zha-device-handlers/pull/5749). Delete the file once the fix ships in a HA release. |
| [`schneider_lk_relay_dimmer.py`](schneider_lk_relay_dimmer.py) | Schneider LK FUGA Wiser double relay ("LK Switch") and wireless dimmer ("LK Dimmer") | Schneider Electric / `LK Switch` (545D6514), `LK Dimmer` | Exposes Schneider's manufacturer-specific switch configuration cluster (0xFF17) as config entities for each button endpoint (21–24): **Switch actions S1–S4**, **Switch indication S1–S4** (LED behaviour), and **Up/Down scene ID S1–S4**. This lets you decouple the bottom row (S3/S4, endpoints 23/24) from the load so it only sends `zha_event`, while the top row keeps controlling the relay or dimmer. See [LK Switch and LK Dimmer setup](#lk-switch-and-lk-dimmer-setup). Replaces the earlier `schneider_lk_switch.py`, delete that file. Tested with LK Switch firmware 0x010218ff and LK Dimmer firmware 0x010217ff; the settings survive restarts. | Not in zha-device-handlers. Not submitted. |
| [`vibration_agl01.py`](vibration_agl01.py) | Aqara Vibration Sensor T1 | LUMI / `lumi.vibration.agl01` (DJT12LM) | Adds support for the T1, which ZHA treats as a plain IAS device out of the box (just odd IAS zone entities and unknown battery). Based on the Zigbee2MQTT definition. Adds a vibration binary sensor with an adjustable reset timeout (default 70 s), battery percentage and voltage, and selects for sensitivity (high/medium/low) and report interval (1/5/10 s). The selects are write-only on the device, so writes are queued until it wakes. Also adds `zha_event`s and device triggers for `vibration` and `triple_tap`. No tilt/drop/angle data, because the T1 hardware doesn't send it. Tested with zha-quirks 2.4.1 / zha 2.4.3 (HA 2026.11.3). | Not merged upstream. Related: issue #4137 and PR #4972. |

## LK Switch and LK Dimmer setup

Button endpoints: top-left 21, top-right 22, bottom-left 23, bottom-right 24.

### LK Switch: press only

Set **Switch actions S3** and **S4** to `Scene`. The bottom row then sends a Scenes `recall` event (cluster 5) instead of switching the relay. `NotUsed` turns the buttons off completely, so use `Scene`.

### LK Dimmer: press and hold (dimming)

Set **Switch actions S3** to `Dimmer` and **Switch actions S4** to `DimmerOpposite` (same as the top row). The bottom row then sends `on`/`off`, `move`/`move_with_on_off` and `stop_with_on_off` events without touching the light.

This works because only the top row is linked to the dimmer's load, through a normal Zigbee binding (endpoints 21/22 to endpoint 3). The bottom row has no binding to the load; out of the box it is in `Scene` mode and switches the light by recalling the dimmer's stored scenes 1 and 2.

If you only need presses, you can also use `Scene` mode as on the LK Switch. Then set **Up scene ID S3** and **Down scene ID S3** to `101`, and **Up scene ID S4** and **Down scene ID S4** to `102`, so the dimmer doesn't recall its own scenes 1 and 2.

The [Schneider LK Dimmer & Relay Bottom Row Actions](https://github.com/briis/home-assistant-blueprints) blueprint uses these events.
