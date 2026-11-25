"""Schneider Electric LK FUGA Wiser wireless double relay (545D6514, model "LK Switch").

Exposes the per-button "switch actions" and LED indication settings
(manufacturer cluster 0xFF17) on button endpoints 21-24 as config entities.

Endpoints: 1 and 2 are the relays, 21-24 are the buttons. Each button half
has its own endpoint, e.g. bottom-left = 23 (sends "on"), bottom-right = 24
(sends "off") in the default "Light" mode.

Decoupling a button from its relay (tested on firmware 0x010218ff):
- "NotUsed" disables the button completely; nothing is sent.
- "Scene" decouples it from the relay and makes it send a Scenes "recall"
  command (scene_id 0, group_id 0), which ZHA fires as zha_event with
  command "recall". Both buttons send identical payloads, so tell them
  apart by endpoint_id. No hold/release events in this mode.

The setting is stored on the device and survives HA/ZHA restarts.
"""

from zhaquirks.builder import QuirkBuilder
from zhaquirks.schneiderelectric import (
    SE_MANUF_NAME,
    SESwitchAction,
    SESwitchConfiguration,
    SESwitchIndication,
)

builder = QuirkBuilder(SE_MANUF_NAME, "LK Switch")

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
    )

builder.add_to_registry()
