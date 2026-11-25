"""Aqara Vibration Sensor T1 (DJT12LM) - lumi.vibration.agl01.

Custom ZHA quirk based on the zigbee2mqtt definition (zigbee-herdsman-converters
``lumi.ts``: lumiVibration, lumiSensitivityAdjustment, lumiReportInterval,
lumiBattery) and on the work in zigpy/zha-device-handlers#4137 / PR #4972.

What the device sends (from Z2M and the ZHA issue):
  * EP2, 0xFCC0 attr 0x0118 = 1   -> movement / vibration
  * EP2, MultistateInput present_value = 1 -> triple tap ("triple strike")
  * IAS Zone attr 0x002D 1/2 (shake / triple strike) - duplicates the above, ignored
  * Battery: Lumi 0x00F7 heartbeat struct (tag 1 = mV) and/or the standard
    PowerConfiguration battery_voltage (100 mV units). Percentage is not supported.

What this quirk exposes:
  * binary_sensor "Vibration" (device_class vibration) that auto-resets after a
    configurable timeout (number entity, default 70 s)
  * battery % (2850-3000 mV, same curve as Z2M) and battery voltage
  * select "Sensitivity" (high/medium/low) - write-only, queued until the device wakes
  * select "Report interval" (1 s / 5 s / 10 s) - write-only, queued until the device wakes
  * zha_event + device triggers: "vibration" and "triple_tap"

The T1 has no tilt/drop/angle data (unlike the old DJT11LM / lumi.vibration.aq1).
"""

import asyncio
from typing import Any, Final

import zigpy.types as t
from zigpy.typing import UNDEFINED, UndefinedType
from zigpy.zcl import foundation
from zigpy.zcl.clusters.general import MultistateInput, PowerConfiguration
from zigpy.zcl.clusters.security import IasZone
from zigpy.zcl.foundation import DataTypeId, ZCLAttributeDef

from zhaquirks import Bus, CustomCluster, LocalDataCluster, MotionOnEvent
from zhaquirks.builder import NumberDeviceClass, QuirkBuilder, UnitOfTime
from zhaquirks.const import (
    CLUSTER_ID,
    COMMAND,
    ENDPOINT_ID,
    MOTION_EVENT,
    ZHA_SEND_EVENT,
    ZONE_TYPE,
    BatterySize,
)
from zhaquirks.device import CustomZigpyDevice
from zhaquirks.xiaomi import (
    LUMI,
    BasicCluster,
    XiaomiAqaraE1Cluster,
    XiaomiPowerConfiguration,
)

LUMI_MANUFACTURER_CODE: Final = 0x115F

VIBRATION: Final = "vibration"
TRIPLE_TAP: Final = "triple_tap"

MOVEMENT_ATTR: Final = 0x0118  # Z2M: manuSpecificLumi "movement"
SENSITIVITY_ATTR: Final = 0x010E  # Z2M: lumiSensitivityAdjustment
REPORT_INTERVAL_ATTR: Final = 0x0110  # Z2M: lumiReportInterval
QUEUED_CONFIG_ATTRS: Final = frozenset({SENSITIVITY_ATTR, REPORT_INTERVAL_ATTR})

# Local-only attribute on the virtual IAS Zone cluster holding the reset timeout.
VIBRATION_RESET_TIMEOUT_ATTR: Final = 0xFFF0
DEFAULT_VIBRATION_RESET_TIMEOUT: Final = 70


class AqaraVibrationSensitivity(t.enum8):
    """Sensitivity (Z2M: high=1, medium=2, low=3)."""

    High = 0x01
    Medium = 0x02
    Low = 0x03


class AqaraVibrationReportInterval(t.enum8):
    """Report interval (Z2M: 1s=1, 5s=2, 10s=3)."""

    Interval_1s = 0x01
    Interval_5s = 0x02
    Interval_10s = 0x03


class VibrationPowerConfiguration(XiaomiPowerConfiguration):
    """Battery from voltage only, using the Z2M curve (2850-3000 mV).

    Handles both the Lumi heartbeat struct (via ``battery_reported``) and a plain
    ZCL battery_voltage report from the device, which the stock
    XiaomiPowerConfiguration would cache without computing a percentage.
    """

    MIN_VOLTS_MV = 2850
    MAX_VOLTS_MV = 3000

    def __init__(self, *args, **kwargs):
        """Init."""
        self._from_heartbeat = False
        super().__init__(*args, **kwargs)

    def battery_reported(self, voltage_mv: int) -> None:
        """Battery voltage from the Lumi heartbeat struct."""
        self._from_heartbeat = True
        try:
            super().battery_reported(voltage_mv)
        finally:
            self._from_heartbeat = False

    def _update_attribute(self, attrid, value):
        super()._update_attribute(attrid, value)
        if (
            attrid == PowerConfiguration.AttributeDefs.battery_voltage.id
            and not self._from_heartbeat
            and value
        ):
            # ZCL battery_voltage is in units of 100 mV
            self._update_battery_percentage(round(value * 100))


class XiaomiVibrationConfigurationCluster(XiaomiAqaraE1Cluster):
    """Lumi manufacturer cluster on EP1: configuration + heartbeat (battery).

    The T1 is a sleepy end device, so a write from the UI usually times out.
    Config writes are therefore queued: the value is cached right away (so the
    select keeps showing it) and sent the next time the device talks to us
    (vibration, triple tap, heartbeat or a button press), while it is awake.
    """

    def __init__(self, *args, **kwargs):
        """Init."""
        super().__init__(*args, **kwargs)
        self._pending: dict[int, Any] = {}
        self._flush_task: asyncio.Task | None = None

    @property
    def has_pending_writes(self) -> bool:
        """Return True if config writes are waiting for the device to wake."""
        return bool(self._pending)

    async def write_attributes(
        self,
        attributes: dict[str | int | ZCLAttributeDef, Any],
        manufacturer: int | UndefinedType | None = UNDEFINED,
        **kwargs,
    ) -> list[list[foundation.WriteAttributesStatusRecord]]:
        """Queue config writes, pass anything else straight through."""
        passthrough = {}
        for attr, value in attributes.items():
            attr_def = self.find_attribute(attr)
            if attr_def.id in QUEUED_CONFIG_ATTRS:
                value = attr_def.type(value)
                self._pending[attr_def.id] = value
                self._update_attribute(attr_def.id, value)
            else:
                passthrough[attr] = value

        result = [[foundation.WriteAttributesStatusRecord(foundation.Status.SUCCESS)]]
        if passthrough:
            result = await super().write_attributes(passthrough, manufacturer, **kwargs)
        if self._pending:
            # Try right away - works if the device happens to be awake
            self.flush_pending_writes()
        return result

    def flush_pending_writes(self) -> None:
        """Send queued config writes (no-op if none or already sending)."""
        if not self._pending or (self._flush_task and not self._flush_task.done()):
            return
        self._flush_task = asyncio.create_task(self._flush())

    async def _flush(self) -> None:
        pending = dict(self._pending)
        try:
            records = await super().write_attributes(pending)
        except Exception as exc:  # noqa: BLE001 - sleepy device, retry on next wake
            self.debug("Queued config write failed, will retry on wake: %r", exc)
            return

        failed = {
            rec.attrid
            for rec in records[0]
            if getattr(rec, "attrid", None) is not None
            and rec.status != foundation.Status.SUCCESS
        }
        for attrid, value in pending.items():
            # Only drop it if nobody queued a newer value in the meantime
            if attrid not in failed and self._pending.get(attrid) == value:
                del self._pending[attrid]
        self.debug("Queued config write sent, still pending: %s", self._pending)
        if any(attrid not in failed for attrid in self._pending):
            # A newer value was queued while we were sending - device is awake
            asyncio.get_running_loop().call_soon(self.flush_pending_writes)

    class AttributeDefs(XiaomiAqaraE1Cluster.AttributeDefs):
        """Manufacturer-specific configuration attributes."""

        sensitivity: Final = ZCLAttributeDef(
            id=SENSITIVITY_ATTR,
            type=AqaraVibrationSensitivity,
            zcl_type=DataTypeId.uint8,
            access="w",
            manufacturer_code=LUMI_MANUFACTURER_CODE,
        )
        report_interval: Final = ZCLAttributeDef(
            id=REPORT_INTERVAL_ATTR,
            type=AqaraVibrationReportInterval,
            zcl_type=DataTypeId.uint8,
            access="w",
            manufacturer_code=LUMI_MANUFACTURER_CODE,
        )


class XiaomiVibrationCluster(XiaomiAqaraE1Cluster):
    """Lumi manufacturer cluster on EP2: movement reports (attr 0x0118)."""

    class AttributeDefs(XiaomiAqaraE1Cluster.AttributeDefs):
        """Attribute definitions."""

        movement: Final = ZCLAttributeDef(
            id=MOVEMENT_ATTR,
            type=t.uint8_t,
            manufacturer_code=LUMI_MANUFACTURER_CODE,
        )

    def _update_attribute(self, attrid, value):
        super()._update_attribute(attrid, value)
        if attrid == MOVEMENT_ATTR and value == 1:
            self.endpoint.device.motion_bus.listener_event(MOTION_EVENT)
            self.listener_event(ZHA_SEND_EVENT, VIBRATION, {"value": value})


class VibrationMultistateInput(CustomCluster, MultistateInput):
    """MultistateInput on EP2: present_value 1 = triple tap."""

    def _update_attribute(self, attrid, value):
        super()._update_attribute(attrid, value)
        if attrid == MultistateInput.AttributeDefs.present_value.id and value == 1:
            # A triple tap is also a vibration
            self.endpoint.device.motion_bus.listener_event(MOTION_EVENT)
            self.listener_event(ZHA_SEND_EVENT, TRIPLE_TAP, {"value": value})


class VibrationMotionCluster(LocalDataCluster, MotionOnEvent):
    """Virtual IAS Zone: vibration binary_sensor with configurable reset."""

    class AttributeDefs(IasZone.AttributeDefs):
        """Attribute definitions."""

        vibration_reset_timeout: Final = ZCLAttributeDef(
            id=VIBRATION_RESET_TIMEOUT_ATTR,
            type=t.uint16_t,
            access="rw",
        )

    _CONSTANT_ATTRIBUTES = {ZONE_TYPE: IasZone.ZoneType.Vibration_Movement_Sensor}
    _DEFAULT_VALUES = {VIBRATION_RESET_TIMEOUT_ATTR: DEFAULT_VIBRATION_RESET_TIMEOUT}

    @property
    def reset_after(self) -> int:
        """Seconds before the vibration sensor resets to off."""
        return int(
            self.get(VIBRATION_RESET_TIMEOUT_ATTR, DEFAULT_VIBRATION_RESET_TIMEOUT)
        )


class VibrationAGL01(CustomZigpyDevice):
    """Aqara Vibration Sensor T1."""

    battery_size = BatterySize.CR2032

    def __init__(self, *args, **kwargs):
        """Init."""
        self.motion_bus = Bus()
        super().__init__(*args, **kwargs)

    def packet_received(self, packet: t.ZigbeePacket) -> None:
        """Device is awake: send any queued config writes."""
        super().packet_received(packet)
        ep1 = self.endpoints.get(1)
        cluster = ep1.in_clusters.get(XiaomiAqaraE1Cluster.cluster_id) if ep1 else None
        if isinstance(cluster, XiaomiVibrationConfigurationCluster):
            cluster.flush_pending_writes()


(
    QuirkBuilder(LUMI, "lumi.vibration.agl01")
    .friendly_name(manufacturer="Aqara", model="Vibration Sensor T1 (DJT12LM)")
    .device_class(VibrationAGL01)
    # Endpoint 1
    .replaces(BasicCluster)
    .replaces(VibrationPowerConfiguration)
    .replaces(VibrationMotionCluster)
    .adds(XiaomiVibrationConfigurationCluster)
    # Endpoint 2
    .replaces(VibrationMultistateInput, endpoint_id=2)
    .removes(IasZone.cluster_id, endpoint_id=2)
    .adds(XiaomiVibrationCluster, endpoint_id=2)
    # Config entities
    .number(
        attribute_name=VibrationMotionCluster.AttributeDefs.vibration_reset_timeout.name,
        cluster_id=IasZone.cluster_id,
        min_value=1,
        max_value=3600,
        step=1,
        unit=UnitOfTime.SECONDS,
        mode="box",
        device_class=NumberDeviceClass.DURATION,
        translation_key="vibration_reset_timeout",
        fallback_name="Vibration reset timeout",
    )
    .enum(
        attribute_name=XiaomiVibrationConfigurationCluster.AttributeDefs.sensitivity.name,
        enum_class=AqaraVibrationSensitivity,
        cluster_id=XiaomiVibrationConfigurationCluster.cluster_id,
        translation_key="sensitivity",
        fallback_name="Sensitivity",
    )
    .enum(
        attribute_name=XiaomiVibrationConfigurationCluster.AttributeDefs.report_interval.name,
        enum_class=AqaraVibrationReportInterval,
        cluster_id=XiaomiVibrationConfigurationCluster.cluster_id,
        translation_key="report_interval",
        fallback_name="Report interval",
    )
    .device_automation_triggers(
        {
            (VIBRATION, VIBRATION): {
                COMMAND: VIBRATION,
                CLUSTER_ID: XiaomiAqaraE1Cluster.cluster_id,
                ENDPOINT_ID: 2,
            },
            (TRIPLE_TAP, TRIPLE_TAP): {
                COMMAND: TRIPLE_TAP,
                CLUSTER_ID: MultistateInput.cluster_id,
                ENDPOINT_ID: 2,
            },
        }
    )
    .add_to_registry()
)
