#!/usr/bin/env python3
"""WebSocket event listener for Smart System Local gateway."""

import argparse
import asyncio
import base64
import json
import signal
import ssl
import sys
from datetime import datetime
from pathlib import Path

import aiohttp

from smart_system_local.devices import Response


def create_ssl_context() -> ssl.SSLContext:
    """Create an insecure SSL context for self-signed certificates."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class EventLogger:
    """Handles logging events to console and optionally to file."""

    def __init__(self, log_file: Path | None = None):
        self.log_file = log_file
        self.event_count = 0
        self.file_handle = None

        if self.log_file:
            self.file_handle = open(self.log_file, 'a', encoding='utf-8')
            self._log_to_file(f"\n{'='*80}\n")
            self._log_to_file(f"Session started at {datetime.now().isoformat()}\n")
            self._log_to_file(f"{'='*80}\n\n")

    def _log_to_file(self, message: str) -> None:
        """Write a message to the log file."""
        if self.file_handle:
            self.file_handle.write(message)
            self.file_handle.flush()

    def log_event(self, event_data: dict | list) -> None:
        """Log an event to console and optionally to file."""
        self.event_count += 1
        timestamp = datetime.now().isoformat()

        print(f"\n{'='*80}")
        print(f"📨 Event #{self.event_count} at {timestamp}")
        print(f"{'='*80}")

        try:
            if isinstance(event_data, list):
                for item in event_data:
                    self._display_parsed_event(item)
            elif isinstance(event_data, dict):
                self._display_parsed_event(event_data)
            else:
                print(json.dumps(event_data, indent=2))
        except Exception as e:
            print(f"⚠️  Failed to parse event: {e}")
            print(json.dumps(event_data, indent=2))

        if self.file_handle:
            self._log_to_file(f"\n{'='*80}\n")
            self._log_to_file(f"Event #{self.event_count} at {timestamp}\n")
            self._log_to_file(f"{'='*80}\n")
            self._log_to_file(json.dumps(event_data, indent=2))
            self._log_to_file("\n")

    def _display_parsed_event(self, event: dict) -> None:
        """Display a parsed event using CommandResponse."""
        try:
            cmd_resp = Response(**event)

            if 'op' in event:
                print(f"  🔧 Operation: {event['op']}")

            status_icon = "✅" if cmd_resp.success else "❌"
            if cmd_resp.success is not None:
                print(f"  {status_icon} Success: {cmd_resp.success}")

            if cmd_resp.device_id:
                print(f"  📍 Device: {cmd_resp.device_id}")

            if cmd_resp.command_path:
                print(f"  📂 Path: {cmd_resp.command_path}")

            if cmd_resp.sequence is not None:
                print(f"  🔢 Sequence: {cmd_resp.sequence}")

            if cmd_resp.source:
                print(f"  🔗 Source: {cmd_resp.source}")

            if cmd_resp.error_source:
                print(f"  ⚠️  Error Source: {cmd_resp.error_source}")

            if cmd_resp.payload:
                print("  📦 Payload:")
                payload_str = json.dumps(cmd_resp.payload, indent=4)
                for line in payload_str.split('\n'):
                    print(f"    {line}")
        except Exception as e:
            print(f"⚠️  Parse error: {e}")
            print(json.dumps(event, indent=2))

    def close(self) -> None:
        """Close the log file if open."""
        if self.file_handle:
            self._log_to_file(f"\n{'='*80}\n")
            self._log_to_file(f"Session ended at {datetime.now().isoformat()}\n")
            self._log_to_file(f"Total events received: {self.event_count}\n")
            self._log_to_file(f"{'='*80}\n")
            self.file_handle.close()


async def listen_to_events(uri: str, headers: dict, logger: EventLogger, ssl_context: ssl.SSLContext) -> None:
    """Connect to WebSocket and listen for events."""
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.ws_connect(uri, headers=headers) as ws:
                print("✅ Connected to gateway!")
                print("👂 Listening for events... (Press Ctrl+C to stop)\n")

                if logger.log_file:
                    print(f"📝 Logging to: {logger.log_file}\n")

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            event_data = json.loads(msg.data)
                            logger.log_event(event_data)
                        except json.JSONDecodeError as e:
                            print(f"\n⚠️  Failed to parse JSON: {e}")
                            print(f"Raw message: {msg.data}")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"\n❌ WebSocket error: {ws.exception()}")
                        break
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                        print("\n❌ Connection closed by server")
                        break

    except aiohttp.ClientError as e:
        print(f"❌ Connection error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Listen to Gardena Smart System Gateway WebSocket events"
    )
    parser.add_argument(
        "--user", "-u", default="_", help="Username (default: _)"
    )
    parser.add_argument(
        "--password", "-p", required=True, help="Gateway password"
    )
    parser.add_argument(
        "--ip", "-i", required=True, help="Gateway IP address"
    )
    parser.add_argument(
        "--port", "-P", type=int, default=8443, help="Gateway port (default: 8443)"
    )
    parser.add_argument(
        "--log-file", "-l", type=Path,
        help="Optional file to log all events (appends to existing file)"
    )

    args = parser.parse_args()

    uri = f"wss://{args.ip}:{args.port}/"

    auth_string = f"{args.user}:{args.password}"
    auth_bytes = auth_string.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
    headers = {"Authorization": f"Basic {auth_b64}"}

    print(f"\n🔌 Connecting to {args.ip}:{args.port}...")

    logger = EventLogger(args.log_file)
    ssl_context = create_ssl_context()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(sig, frame):
        print("\n\n👋 Stopping listener...")
        print(f"📊 Total events received: {logger.event_count}")
        logger.close()
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        loop.run_until_complete(listen_to_events(uri, headers, logger, ssl_context))
    except KeyboardInterrupt:
        pass
    finally:
        logger.close()
        loop.close()


if __name__ == "__main__":
    main()
