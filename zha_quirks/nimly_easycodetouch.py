"""Custom ZHA quirk for Onesti/Nimly EasyCodeTouch / EasyFingerTouch locks.

Same as the built-in zhaquirks.nimly.lock "EasyFingerTouch" quirk, but also
replaces the PowerConfiguration cluster with DoublingPowerConfigurationCluster.
These locks report battery_percentage_remaining (0x0021) as 0-100 instead of
the Zigbee-spec 0-200 (half-percent steps), so ZHA shows half the real value.
"""

from zhaquirks import DoublingPowerConfigurationCluster
from zhaquirks.builder import QuirkBuilder, SensorDeviceClass
from zhaquirks.nimly import NIMLY
from zhaquirks.nimly.lock import (
    NIMLY_LOCK_NODE_DESCRIPTOR,
    NimlyDoorLock,
    last_action_converter,
    last_action_source_converter,
    last_action_user_converter,
)

(
    QuirkBuilder(NIMLY, "EasyFingerTouch")
    .applies_to(NIMLY, "EasyCodeTouch")
    .applies_to(NIMLY, "easyCodeTouch_v1")
    .node_descriptor(NIMLY_LOCK_NODE_DESCRIPTOR)
    .replaces(DoublingPowerConfigurationCluster, endpoint_id=11)
    .replaces(NimlyDoorLock, endpoint_id=11)
    .sensor(
        endpoint_id=11,
        cluster_id=NimlyDoorLock.cluster_id,
        attribute_name=NimlyDoorLock.AttributeDefs.nimly_last_lock_unlock_source.name,
        unique_id_suffix="last_action_source",
        attribute_converter=last_action_source_converter,
        device_class=SensorDeviceClass.ENUM,
        translation_key="last_action_source",
        fallback_name="Last action source",
    )
    .sensor(
        endpoint_id=11,
        cluster_id=NimlyDoorLock.cluster_id,
        attribute_name=NimlyDoorLock.AttributeDefs.nimly_last_lock_unlock_source.name,
        unique_id_suffix="last_action",
        attribute_converter=last_action_converter,
        device_class=SensorDeviceClass.ENUM,
        translation_key="last_action",
        fallback_name="Last action",
    )
    .sensor(
        endpoint_id=11,
        cluster_id=NimlyDoorLock.cluster_id,
        attribute_name=NimlyDoorLock.AttributeDefs.nimly_last_lock_unlock_source.name,
        unique_id_suffix="last_action_user",
        attribute_converter=last_action_user_converter,
        translation_key="last_action_user",
        fallback_name="Last action user",
    )
    .sensor(
        endpoint_id=11,
        cluster_id=NimlyDoorLock.cluster_id,
        attribute_name=NimlyDoorLock.AttributeDefs.nimly_last_pin_code.name,
        unique_id_suffix="last_pin_code",
        attribute_converter=lambda value: value.hex(),
        initially_disabled=True,
        translation_key="last_pin_code",
        fallback_name="Last PIN code",
    )
    .switch(
        endpoint_id=11,
        cluster_id=NimlyDoorLock.cluster_id,
        attribute_name=NimlyDoorLock.AttributeDefs.auto_relock_time.name,
        translation_key="auto_relock",
        fallback_name="Autorelock",
    )
    .number(
        endpoint_id=11,
        cluster_id=NimlyDoorLock.cluster_id,
        attribute_name=NimlyDoorLock.AttributeDefs.sound_volume.name,
        min_value=0,
        max_value=2,
        step=1,
        translation_key="sound_volume",
        fallback_name="Sound volume",
    )
    .add_to_registry()
)
