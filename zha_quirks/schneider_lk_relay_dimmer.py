"""Schneider Electric LK FUGA Wiser wireless relay/dimmer button configuration.

Applies to:
- LK FUGA Wiser wireless double relay (545D6514, model "LK Switch")
  - relays on endpoints 1 and 2
- LK FUGA Wiser wireless dimmer (model "LK Dimmer")
  - dimmer load on endpoint 3

Exposes the per-button "switch actions" and LED indication settings
(manufacturer cluster 0xFF17) on button endpoints 21-24 as config entities.

Buttons are endpoints 21-24 on both models. Each button half
has its own endpoint, e.g. bottom-left = 23 (sends "on"), bottom-right = 24
(sends "off") in the default "Light" mode.

Decoupling a button from its relay (tested on LK Switch firmware 0x010218ff):
- "NotUsed" disables the button completely; nothing is sent.
- "Scene" decouples it from the relay and makes it send a Scenes "recall"
  command (scene_id 0, group_id 0), which ZHA fires as zha_event with
  command "recall". Both buttons send identical payloads, so tell them
  apart by endpoint_id. No hold/release events in this mode.

LK Dimmer: only the top row is linked to the load, through a normal Zigbee
binding (endpoints 21/22 -> 3). The bottom row has no binding to the load and
by default only switches it through the scene recall in "Scene" mode. Set
S3 = "Dimmer" and S4 = "DimmerOpposite" and the bottom row sends on/off,
move and stop events without touching the light (press and hold). For press
only, "Scene" mode with the up and down scene IDs set to scenes the dimmer
doesn't have (101 on S3, 102 on S4) also works.

All settings are stored on the device and survive HA/ZHA restarts.
"""

from zhaquirks.builder import QuirkBuilder
from zhaquirks.schneiderelectric import (
    SE_MANUF_NAME,
    SESwitchAction,
    SESwitchConfiguration,
    SESwitchIndication,
)

builder = QuirkBuilder(SE_MANUF_NAME, "LK Switch").applies_to(
    SE_MANUF_NAME, "LK Dimmer"
)

for ep in (21, 22, 23, 24):
    n = ep - 20
    builder = (
        builder.replaces(SESwitchConfiguration, endpoint_id=ep)
        .enum(
            attribute_name=SESwitchConfiguration.AttributeDefs.se_switch_actions.name,
            enum_class=SESwitchAction,
            cluster_id=SESwitchConfiguration.cluster_id,
            endpoint_id=ep,
            translation_key=f"switch_actions_s{n}",
            fallback_name=f"Switch actions S{n}",
        )
        .enum(
            attribute_name=SESwitchConfiguration.AttributeDefs.se_switch_indication.name,
            enum_class=SESwitchIndication,
            cluster_id=SESwitchConfiguration.cluster_id,
            endpoint_id=ep,
            translation_key=f"switch_indication_s{n}",
            fallback_name=f"Switch indication S{n}",
        )
        .number(
            attribute_name=SESwitchConfiguration.AttributeDefs.se_up_scene_id.name,
            cluster_id=SESwitchConfiguration.cluster_id,
            endpoint_id=ep,
            min_value=0,
            max_value=255,
            step=1,
            translation_key=f"up_scene_id_s{n}",
            fallback_name=f"Up scene ID S{n}",
        )
        .number(
            attribute_name=SESwitchConfiguration.AttributeDefs.se_down_scene_id.name,
            cluster_id=SESwitchConfiguration.cluster_id,
            endpoint_id=ep,
            min_value=0,
            max_value=255,
            step=1,
            translation_key=f"down_scene_id_s{n}",
            fallback_name=f"Down scene ID S{n}",
        )
    )

builder.add_to_registry()
