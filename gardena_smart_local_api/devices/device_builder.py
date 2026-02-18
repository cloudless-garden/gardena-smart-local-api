from typing import Any

from ..messages import IngressMessageList, Reply
from .device import Device, DeviceMap
from .gen1 import WaterControl

MODEL_NUMBER_MAP: dict[str, type[Device]] = {
    "18869": WaterControl,
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
