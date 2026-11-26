#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Show and change the settings of a gateway.

The settings are part of the configuration API of the gateway, not of the WebSocket API
the other examples use, so this one does not connect to the devices. Every
setting is a subcommand.
"""

import argparse
import asyncio
import sys

from gardena_smart_local_api.client import (
    AuthenticationError,
    ConfigApiError,
    GatewayConfigApi,
)


async def cloud(config_api: GatewayConfigApi, args: argparse.Namespace) -> None:
    if args.command == "status":
        connected = await config_api.get_cloud_connection()
    else:
        connected = args.command == "enable"
        if connected:
            print("Connecting to the cloud can take half a minute...")
        await config_api.set_cloud_connection(connected)
    print(f"Cloud connection: {'on' if connected else 'off'}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-g",
        "--gateway",
        required=True,
        help="e.g. GARDENA-123456 or IP address",
    )
    parser.add_argument(
        "-p",
        "--password",
        required=True,
        help="First 8 characters of ID found on the back of the gateway",
    )
    parser.add_argument(
        "-f",
        "--fingerprint",
        required=False,
        help="SHA-256 fingerprint of the gateway certificate, to only talk to "
        "that gateway",
    )
    settings = parser.add_subparsers(dest="setting", required=True, metavar="setting")

    # To add a setting, add a subcommand with a handler like this one.
    cloud_parser = settings.add_parser(
        "cloud", help="Connection of the gateway to the GARDENA cloud"
    )
    cloud_parser.add_argument(
        "command",
        choices=("status", "enable", "disable"),
        help="Show the cloud connection, or turn it on or off",
    )
    cloud_parser.set_defaults(handler=cloud)

    return parser.parse_args()


async def main() -> int:
    args = _parse_args()

    try:
        config_api = GatewayConfigApi(
            args.gateway, args.password, fingerprint=args.fingerprint
        )
    except ValueError as err:
        print(f"Invalid --gateway or --fingerprint: {err}", file=sys.stderr)
        return 1

    try:
        await args.handler(config_api, args)
    except AuthenticationError:
        print("The gateway rejected the password. Check the password.", file=sys.stderr)
        return 1
    except ConfigApiError as err:
        print(err, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
