from typing import Any

from ..messages import IngressMessageList, Reply
from .device import Device, DeviceMap
from .irrigation import (
    Gen1IrrigationControl,
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
)
from .mowers import Gen1Mower1, Gen1Mower2
from .power import PowerAdapter
from .sensors import Sensor1, Sensor2

MODEL_NUMBER_MAP: dict[str, type[Device]] = {
    "469": Gen2IrrigationControl,
    "2812": Gen2WaterControl,
    "2814": Gen2WaterControl,
    "2826": Gen2WaterControl,
    "6146": Gen1Mower1,
    "18845": Sensor1,
    "18869": Gen1WaterControl,
    "19040": Sensor2,
    "29694": Gen1Mower1,
    "31653": Gen1IrrigationControl,
    "35279": PowerAdapter,
    "53988": Gen1Mower2,
}


async def _create_device_from_data(device_data: dict[str, Any]) -> Device | None:
    model_number = list(device_data.values())[0]["device"]["0"]["model_number"]["vs"]
    if model_number is None:
        return None

    return await MODEL_NUMBER_MAP.get(model_number, Device)._from_raw(device_data)


async def create_devices_from_messages(messages: IngressMessageList) -> DeviceMap:
    devices: dict[str, Device] = {}
    for msg in messages:
        if not isinstance(msg, Reply):
            continue
        for device_id, device_data in msg.payload.items():
            device = await _create_device_from_data({device_id: device_data})
            if device is not None:
                devices[device_id] = device
    return DeviceMap(devices)


async def create_devices_from_json(json_obj: str) -> DeviceMap:
    msgs = IngressMessageList.model_validate_json(json_obj)
    return await create_devices_from_messages(msgs)
