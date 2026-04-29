from enum import Enum


class _LowerNameEnum(Enum):
    def __str__(self):
        return self.name.lower()
