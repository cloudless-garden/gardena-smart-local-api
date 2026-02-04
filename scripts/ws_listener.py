#!/usr/bin/env python3
"""WebSocket event listener for Smart System Local gateway."""

import argparse
import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

from smart_system_local.devices import Event, Response
from smart_system_local.websocket_helper import WebSocketHelper


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

    def log_event(self, event_data: list[Event | Response]) -> None:
        """Log an event to console and optionally to file."""
        self.event_count += 1
        timestamp = datetime.now().isoformat()

        print(f"\n{'='*80}")
        print(f"📨 Event #{self.event_count} at {timestamp}")
        print(f"{'='*80}")

        try:
            for item in event_data:
                self._display_parsed_event(item)
        except Exception as e:
            print(f"⚠️  Failed to parse event: {e}")
            import traceback
            traceback.print_exc()

        if self.file_handle:
            self._log_to_file(f"\n{'='*80}\n")
            self._log_to_file(f"Event #{self.event_count} at {timestamp}\n")
            self._log_to_file(f"{'='*80}\n")
            # Convert Pydantic objects to dicts for JSON serialization
            data_as_dicts = [item.model_dump() for item in event_data]
            self._log_to_file(json.dumps(data_as_dicts, indent=2))
            self._log_to_file("\n")

    def _display_parsed_event(self, event: Event | Response) -> None:
        """Display a parsed event."""
        try:
            # Get the event data as dict for checking fields
            event_dict = event.model_dump()

            if isinstance(event, Response):
                if 'op' in event_dict:
                    print(f"  🔧 Operation: {event_dict['op']}")

                status_icon = "✅" if event.success else "❌"
                if event.success is not None:
                    print(f"  {status_icon} Success: {event.success}")

                if event.device_id:
                    print(f"  📍 Device: {event.device_id}")

                if event.command_path:
                    print(f"  📂 Path: {event.command_path}")

                if event.sequence is not None:
                    print(f"  🔢 Sequence: {event.sequence}")

                if event.source:
                    print(f"  🔗 Source: {event.source}")

                if event.error_source:
                    print(f"  ⚠️  Error Source: {event.error_source}")
            else:
                # Handle Event type
                print(f"  🔧 Operation: {event_dict.get('op', 'N/A')}")
                if event.entity:
                    if event.entity.device:
                        print(f"  📍 Device: {event.entity.device}")
                    if event.entity.path:
                        print(f"  📂 Path: {event.entity.path}")
                if event.metadata:
                    if event.metadata.sequence is not None:
                        print(f"  🔢 Sequence: {event.metadata.sequence}")
                    if event.metadata.source:
                        print(f"  🔗 Source: {event.metadata.source}")

            if event.payload:
                print("  📦 Payload:")
                payload_str = json.dumps(event.payload, indent=4)
                for line in payload_str.split('\n'):
                    print(f"    {line}")
        except Exception as e:
            print(f"⚠️  Parse error: {e}")
            print(json.dumps(event.model_dump(), indent=2))

    def close(self) -> None:
        """Close the log file if open."""
        if self.file_handle:
            self._log_to_file(f"\n{'='*80}\n")
            self._log_to_file(f"Session ended at {datetime.now().isoformat()}\n")
            self._log_to_file(f"Total events received: {self.event_count}\n")
            self._log_to_file(f"{'='*80}\n")
            self.file_handle.close()


async def listen_to_events(helper: WebSocketHelper, logger: EventLogger) -> None:
    """Listen for events using WebSocketHelper."""
    try:
        await helper.connect()
        print("✅ Connected to gateway!")
        print("👂 Listening for events... (Press Ctrl+C to stop)\n")

        if logger.log_file:
            print(f"📝 Logging to: {logger.log_file}\n")

        while helper.is_connected:
            msg = await helper.receive()
            logger.log_event(msg.data)

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

    print(f"\n🔌 Connecting to {args.ip}:{args.port}...")

    logger = EventLogger(args.log_file)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    helper = None

    def signal_handler(sig, frame):
        print("\n\n👋 Stopping listener...")
        print(f"📊 Total events received: {logger.event_count}")
        logger.close()
        if helper:
            loop.run_until_complete(helper.close())
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    async def run():
        nonlocal helper
        helper = await WebSocketHelper.from_config(
            host=args.ip,
            port=args.port,
            path="/",
            use_ssl=True,
            verify_ssl=False,
            username=args.user,
            password=args.password,
        )
        await listen_to_events(helper, logger)

    try:
        loop.run_until_complete(run())
    except KeyboardInterrupt:
        pass
    finally:
        logger.close()
        if helper:
            loop.run_until_complete(helper.close())
        loop.close()


if __name__ == "__main__":
    main()
