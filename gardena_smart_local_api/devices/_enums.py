# SPDX-FileCopyrightText: 2026 GARDENA GmbH
#
# SPDX-License-Identifier: LGPL-3.0-or-later

from enum import Enum


class _LowerNameEnum(Enum):
    def __str__(self):
        return self.name.lower()
