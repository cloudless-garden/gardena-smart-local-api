#!/usr/bin/env python3
"""Interactive CLI for testing Smart System Local WebSocket gateway."""

import argparse
import asyncio
import json
import uuid

from smart_system_local.devices import Response
from smart_system_local.devices.dynamic import DynamicDevice
from smart_system_local.devices.messages import Entity, Request
from smart_system_local.websocket_helper import WebSocketHelper


def display_response(response: Response) -> None:
    """Display a formatted Response."""
    status_icon = "✅" if response.success else "❌"
    print(f"  {status_icon} Success: {response.success}")

    if response.device_id:
        print(f"  📍 Device: {response.device_id}")

    if response.command_path:
        print(f"  📂 Path: {response.command_path}")

    if response.sequence is not None:
        print(f"  🔢 Sequence: {response.sequence}")

    if response.source:
        print(f"  🔗 Source: {response.source}")

    if response.error_source:
        print(f"  ⚠️  Error Source: {response.error_source}")

    if response.payload:
        print(f"  📦 Payload: {response.payload}")


async def handle_commands(helper: WebSocketHelper, selected_device):
    """Handle command execution for a device."""
    if not hasattr(selected_device, "Command") or selected_device.Command is None:
        print("\n⚠️  No commands available for this device")
        return

    command_enums = list(selected_device.Command)

    print("\n🎮 Available Commands:")
    for idx, cmd in enumerate(command_enums):
        print(f"  [{idx}] {cmd.name} (value: {cmd.value})")

    while True:
        cmd_input = input("\n⚡ Select command number (or 'b' for back): ").strip()

        if cmd_input.lower() == "b":
            break

        try:
            cmd_idx = int(cmd_input)
            if cmd_idx < 0 or cmd_idx >= len(command_enums):
                print(f"❌ Invalid command number. Choose 0-{len(command_enums) - 1}")
                continue
        except ValueError:
            print("❌ Please enter a valid number or 'b'")
            continue

        try:
            cmd_enum = command_enums[cmd_idx]
            print(f"\n📤 Executing: {cmd_enum.name} (Command ID: {cmd_enum.value})")

            command_json = selected_device.build_command(cmd_enum)

            # Convert to Request model
            request = Request(**command_json)

            print(f"📝 Command JSON: {json.dumps(command_json, indent=2)}")

            response = await helper.send(request, wait_for_reply=True, timeout=5.0)
            print("✅ Command sent!")

            print("\n📥 Response:")
            if response and response.payload:
                cmd_resp = Response(**response.payload)
                display_response(cmd_resp)
            else:
                print("No response data")

        except asyncio.TimeoutError:
            print("⚠️  Response timeout!")
        except Exception as e:
            print(f"❌ Error: {e}")


async def handle_read_value(helper: WebSocketHelper, selected_device):
    """Handle reading a value from a device."""
    object_names = selected_device.objects

    if not object_names:
        print("\n⚠️  No readable values available for this device")
        return

    readable_resources = []
    for obj_name in object_names:
        instances = selected_device.list_instances(obj_name)
        for instance_id in instances:
            obj = selected_device.get_object(obj_name, instance_id)
            if obj:
                for resource_name, resource in obj.resources.items():
                    if resource.is_readable:
                        readable_resources.append(
                            {
                                "object": obj_name,
                                "instance": instance_id,
                                "resource": resource_name,
                                "value": resource.get_value(selected_device.raw),
                            }
                        )

    if not readable_resources:
        print("\n⚠️  No readable values available for this device")
        return

    print("\n📖 Available Values:")
    for idx, res in enumerate(readable_resources):
        value = res["value"]
        print(f"  [{idx}] {res['object']}.{res['instance']}.{res['resource']}: {value}")

    value_input = input("\n📖 Select value number (or 'b' for back): ").strip()

    if value_input.lower() == "b":
        return

    try:
        value_idx = int(value_input)
        if value_idx < 0 or value_idx >= len(readable_resources):
            print(f"❌ Invalid value number. Choose 0-{len(readable_resources) - 1}")
            return
    except ValueError:
        print("❌ Please enter a valid number or 'b'")
        return

    selected_res = readable_resources[value_idx]

    try:
        print(
            f"\n📖 Reading: {selected_res['object']}.{selected_res['instance']}.{selected_res['resource']}"
        )

        obj_key = None
        for key in selected_device.raw.keys():
            if (
                key.endswith(":" + selected_res["object"])
                or key == selected_res["object"]
            ):
                obj_key = key
                break

        if not obj_key:
            obj_key = selected_res["object"]

        path = f"{obj_key}/{selected_res['instance']}/{selected_res['resource']}"

        # FIXME: implement in Device class
        request = Request(
            request_id=str(uuid.uuid4()),
            op="read",
            entity=Entity(device=selected_device.id, path=path, service="lemonbeatd"),
            payload={},
        )
        print(
            f"📝 Read JSON: {json.dumps(request.model_dump(exclude_none=True), indent=2)}"
        )

        response = await helper.send(request, wait_for_reply=True, timeout=5.0)
        print("✅ Read request sent!")

        print("\n📥 Response:")
        if response:
            display_response(response)
        else:
            print("No response data")

    except asyncio.TimeoutError:
        print("⚠️  Response timeout!")
    except Exception as e:
        print(f"❌ Error: {e}")


async def handle_update_value(helper: WebSocketHelper, selected_device):
    """Handle updating a value on a device."""
    object_names = selected_device.objects

    if not object_names:
        print("\n⚠️  No writable values available for this device")
        return

    writable_resources = []
    for obj_name in object_names:
        instances = selected_device.list_instances(obj_name)
        for instance_id in instances:
            obj = selected_device.get_object(obj_name, instance_id)
            if obj:
                for resource_name, resource in obj.resources.items():
                    if resource.is_writable:
                        writable_resources.append(
                            {
                                "object": obj_name,
                                "instance": instance_id,
                                "resource": resource_name,
                                "value": resource.get_value(selected_device.raw),
                            }
                        )

    if not writable_resources:
        print("\n⚠️  No writable values available for this device")
        return

    print("\n✏️  Writable Values:")
    for idx, res in enumerate(writable_resources):
        value = res["value"]
        print(f"  [{idx}] {res['object']}.{res['instance']}.{res['resource']}: {value}")

    value_input = input(
        "\n✏️  Select value number to update (or 'b' for back): "
    ).strip()

    if value_input.lower() == "b":
        return

    try:
        value_idx = int(value_input)
        if value_idx < 0 or value_idx >= len(writable_resources):
            print(f"❌ Invalid value number. Choose 0-{len(writable_resources) - 1}")
            return
    except ValueError:
        print("❌ Please enter a valid number or 'b'")
        return

    selected_res = writable_resources[value_idx]

    print(f"\nCurrent value: {selected_res['value']}")
    new_value_input = input("Enter new value: ").strip()

    try:
        if new_value_input.lower() in ("true", "false"):
            new_value = new_value_input.lower() == "true"
        elif new_value_input.isdigit() or (
            new_value_input.startswith("-") and new_value_input[1:].isdigit()
        ):
            new_value = int(new_value_input)
        elif "." in new_value_input:
            new_value = float(new_value_input)
        else:
            new_value = new_value_input
    except ValueError:
        new_value = new_value_input

    try:
        print(
            f"\n✏️  Updating {selected_res['object']}.{selected_res['resource']} to: {new_value} (type: {type(new_value).__name__})"
        )

        update_json = selected_device.set_resource(
            selected_res["object"],
            selected_res["instance"],
            selected_res["resource"],
            new_value,
        )

        # Convert to Request model
        request = Request(**update_json)
        print(f"📝 Update JSON: {json.dumps(update_json, indent=2)}")

        response = await helper.send(request, wait_for_reply=True, timeout=5.0)
        print("✅ Update request sent!")

        print("\n📥 Response:")
        if response and response.payload:
            cmd_resp = Response(**response.payload)
            display_response(cmd_resp)
        else:
            print("No response data")

    except asyncio.TimeoutError:
        print("⚠️  Response timeout!")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Interactive Lemonbeat Gateway WebSocket CLI"
    )
    parser.add_argument("--user", "-u", default="_", help="Username (default: _)")
    parser.add_argument("--password", "-p", required=True, help="Gateway password")
    parser.add_argument("--ip", "-i", required=True, help="Gateway IP address")
    parser.add_argument(
        "--port", "-P", type=int, default=8443, help="Gateway port (default: 8443)"
    )

    args = parser.parse_args()

    print(f"\n🔌 Connecting to {args.ip}:{args.port}...")

    try:
        helper = await WebSocketHelper.from_config(
            host=args.ip,
            port=args.port,
            path="/",
            use_ssl=True,
            verify_ssl=False,
            username=args.user,
            password=args.password,
        )
        await helper.connect()
        print("✅ Connected!\n")

        discover_cmd = DynamicDevice.discover()
        print("📡 Sending discover command...")

        response = await helper.send(discover_cmd, wait_for_reply=True)

        devices = []
        if response and (payload := response.payload) and len(payload) > 0:
            print(f"🔍 Found {len(payload)} device entries in payload\n")

            for device_id, device_data in payload.items():
                device = await DynamicDevice.from_raw({device_id: device_data})
                devices.append(device)

        if not devices:
            print("❌ No devices found!")
            return

        print(f"📋 Found {len(devices)} device(s):\n")
        for idx, device in enumerate(devices, start=1):
            online_status = "🟢 ONLINE" if device.is_online else "🔴 OFFLINE"
            device_type = device.device_type_name
            device_name = device.device_name
            print(
                f"  [{idx}] {online_status} - {device_name} ({device_type}) (ID: {device.id})"
            )

        while True:
            print("\n" + "=" * 60)
            device_input = input("\n🎯 Select device number (or 'q' to quit): ").strip()

            if device_input.lower() == "q":
                print("👋 Goodbye!")
                break

            try:
                device_idx = int(device_input)
                if device_idx < 1 or device_idx > len(devices):
                    print(f"❌ Invalid device number. Choose 1-{len(devices)}")
                    continue
            except ValueError:
                print("❌ Please enter a valid number or 'q'")
                continue

            selected_device = devices[device_idx - 1]

            print("\n📊 Device Data:")
            print(f"  ID: {selected_device.id}")
            print(f"  Online: {selected_device.is_online}")
            print(f"  Model: {selected_device.device_name}")
            print(f"  Type: {selected_device.device_type_name}")

            object_names = selected_device.objects
            if object_names:
                print("\n📊 Device Objects:")
                for obj_name in object_names:
                    instances = selected_device.list_instances(obj_name)
                    for instance_id in instances:
                        obj = selected_device.get_object(obj_name, instance_id)
                        if obj:
                            print(f"\n  {obj_name} [{instance_id}]:")
                            for resource_name, resource in obj.resources.items():
                                value = resource.get_value(selected_device.raw)
                                access = []
                                if resource.is_readable:
                                    access.append("R")
                                if resource.is_writable:
                                    access.append("W")
                                access_str = "/".join(access) if access else "?"
                                print(f"    {resource_name} ({access_str}): {value}")

            while True:
                print("\n" + "=" * 60)
                print("📋 Actions:")
                print("  [1] Send Command")
                print("  [2] Read Value")
                print("  [3] Update Value")
                print("  [b] Back to device selection")

                action = input("\n➤ Select action: ").strip()

                if action.lower() == "b":
                    break

                if action == "1":
                    await handle_commands(helper, selected_device)
                elif action == "2":
                    await handle_read_value(helper, selected_device)
                elif action == "3":
                    await handle_update_value(helper, selected_device)
                else:
                    print("❌ Invalid action")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if "helper" in locals():
            await helper.close()


if __name__ == "__main__":
    asyncio.run(main())
