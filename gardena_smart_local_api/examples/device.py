#!/usr/bin/env python3
import asyncio
import sys

from rich import print

from gardena_smart_local_api.devices import Device, build_inclusion_obj
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import Reply
from gardena_smart_local_api.sgtin96 import Sgtin96Info

extra_args = [
    {
        "name_or_flags": ["command"],
        "nargs": 1,
        "choices": ("list", "include", "exclude"),
        "help": "List included devices, include a new device, or exclude a device",
    },
]


async def prompt(question: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, question)


async def include(app: ExampleApp) -> int:
    seen: set[str] = set()

    print("Listening for includable devices...")
    while True:
        if not app.events:
            await asyncio.sleep(0.1)
            continue
        event = app.events.pop(0)
        if event.entity.path.object_name != "includable_device":
            continue

        service = event.entity.service
        instance_id = event.entity.path.object_instance_id
        if service is None or instance_id is None:
            continue
        if instance_id in seen:
            continue
        seen.add(instance_id)

        device_id = event.payload.get("identifier", {}).get("vs", instance_id)
        try:
            info = Sgtin96Info.from_hex(device_id)
            name = await info.get_model_name()
            device_desc = f"[bold]{name} {info.serial:08d}[/bold]"
        except ValueError:
            device_desc = device_id
        print(f"Found includable device: {device_desc}")
        answer = await prompt("Include? [y/N] ")
        if answer.strip().lower() != "y":
            continue

        replies = await app.send_request(build_inclusion_obj(service, instance_id))
        if replies and isinstance(replies[0], Reply) and replies[0].success:
            print(f"[green]Device {device_desc} included successfully.[/green]")
            return 0
        else:
            print(f"[red]Inclusion of {device_desc} failed.[/red]")
            return 1


async def exclude(app: ExampleApp) -> int:
    device_id = app.args.device_id
    if device_id is None:
        print("[red]No device ID provided.[/red]")
        return 1

    if device_id not in app.devices:
        print(f"[red]Device {device_id} not found.[/red]")
        return 1

    device = app.devices[device_id]
    name = device.model_definition.name
    print(f"Excluding device: [bold]{name}[/bold] ({device_id})")
    answer = await prompt("Exclude? [y/N] ")
    if answer.strip().lower() != "y":
        return 0

    replies = await app.send_request(device.build_exclusion_obj())
    if replies and isinstance(replies[0], Reply) and replies[0].success:
        print(f"[green]Device {device_id} excluded.[/green]")
        return 0
    else:
        print(f"[red]Exclusion of {device_id} failed.[/red]")
        return 1


async def main():
    async with ExampleApp((Device,), extra_args) as app:
        match app.args.command[0]:
            case "list":
                app.list_devices()
                return 0

            case "include":
                return await include(app)

            case "exclude":
                return await exclude(app)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
