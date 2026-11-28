"""TEMPORARY version of schneider_lk_relay_dimmer.py - only for re-binding the LK Dimmer top row.

Same as the normal quirk, but hides the bottom-row (endpoints 23/24) OnOff and
LevelControl client clusters from ZHA, so a ZHA device-to-device bind of the
dimmer to itself only links the top row (endpoints 21/22) to the load.

Use it in place of the normal quirk, restart, run zha/devices/bind, then put
the normal quirk back and restart. See zha_quirks/README.md for the full procedure.
"""

from zigpy.zcl import ClusterType
from zigpy.zcl.clusters.general import LevelControl, OnOff

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

# TEMPORARY: hide the bottom-row on/off and dim channels, so a ZHA
# device-to-device bind only links the top row (endpoints 21/22) to the load.
for ep in (23, 24):
    builder = builder.removes(
        OnOff.cluster_id, cluster_type=ClusterType.Client, endpoint_id=ep
    ).removes(LevelControl.cluster_id, cluster_type=ClusterType.Client, endpoint_id=ep)

builder.add_to_registry()
