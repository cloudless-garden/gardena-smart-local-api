#!/usr/bin/env python3
import asyncio
import sys

from rich import print

from gardena_smart_local_api.devices import build_inclusion_obj
from gardena_smart_local_api.examples import ExampleApp
from gardena_smart_local_api.messages import Reply
from gardena_smart_local_api.sgtin96 import parse_sgtin96


async def prompt(question: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, question)


async def main():
    async with ExampleApp(()) as app:
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
                info = parse_sgtin96(device_id)
                name = await info.get_model_name()
                device_desc = f"[bold]{name} {info.serial:08d}[/bold]"
            except ValueError:
                device_desc = device_id
            print(f"Found includable device: {device_desc}")
            answer = await prompt("Include? [y/N] ")
            if answer.strip().lower() != "y":
                continue

            replies = await app.send_request(
                build_inclusion_obj(service, instance_id)
            )
            if replies and isinstance(replies[0], Reply) and replies[0].success:
                print(f"[green]Device {device_desc} included successfully.[/green]")
                return 0
            else:
                print(f"[red]Inclusion of {device_desc} failed.[/red]")
                return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
