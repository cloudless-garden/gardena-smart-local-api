# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

import pytest

from gardena_smart_local_api.messages import IngressMessageList


def _pkg_version_update(device_id: str, pkg_version: str):
    return IngressMessageList.model_validate_json(f"""
        [
          {{
            "entity": {{ "device": "{device_id}", "path": "firmware_update/0" }},
            "metadata": {{ "sequence": 1, "source": "lemonbeatd" }},
            "op": "update",
            "payload": {{
              "pkg_version": {{ "ts": 1774970419, "vs": "{pkg_version}" }},
              "_urn": "urn:oma:lwm2m:x:5"
            }}
          }}
        ]
        """).root[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("pkg_version", "expected"),
    [
        # Gen2
        ("1.3.2+0", "1.3.2"),
        ("1.3.2", "1.3.2"),
        # Gen1
        ("4.0.0-1.5.3-3.0.3", "3.0.3"),
        ("5487193-07A_P14.2E-SwPkg_105.8", "105.8"),
    ],
)
async def test_available_software_version(water_control, pkg_version, expected):
    water_control.update_data(_pkg_version_update(water_control.id, pkg_version))

    assert water_control.available_firmware_version == pkg_version
    assert water_control.available_software_version == expected


@pytest.mark.asyncio
async def test_available_software_version_without_update(water_control):
    assert water_control.available_firmware_version is None
    assert water_control.available_software_version is None
