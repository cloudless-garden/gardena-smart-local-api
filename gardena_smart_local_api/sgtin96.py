from dataclasses import dataclass

from gardena_smart_local_api.model_loader import get_model_loader

_PARTITION_TABLE = {
    0: (40, 12, 4, 1),
    1: (37, 11, 7, 2),
    2: (34, 10, 10, 3),
    3: (30, 9, 14, 4),
    4: (27, 8, 17, 5),
    5: (24, 7, 20, 6),
    6: (20, 6, 24, 7),
}


def _gtin_checksum(digits: str) -> str:
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(digits))
    )
    remainder = total % 10
    return "0" if remainder == 0 else str(10 - remainder)


@dataclass
class SGTIN96Info:
    serial: int
    gtin13: str
    company_prefix: str
    item_reference: str
    check_digit: str

    @classmethod
    def from_hex(cls, hex_str: str) -> "SGTIN96Info":
        if len(hex_str) != 24:
            raise ValueError("SGTIN96 must be 24 hex characters")
        bits = f"{int(hex_str, 16):096b}"
        if bits[:8] != "00110000":
            raise ValueError("Not a valid SGTIN96 (invalid header)")
        partition = int(bits[11:14], 2)
        company_bits, company_digits, _, item_digits = _PARTITION_TABLE[partition]
        company = str(int(bits[14 : 14 + company_bits], 2)).zfill(company_digits)
        item_and_indicator = str(int(bits[14 + company_bits : 58], 2)).zfill(
            item_digits
        )
        item_padded = item_and_indicator[1:]
        item = item_padded.lstrip("0") or "0"
        check = _gtin_checksum(company + item_padded)
        serial = int(bits[58:96], 2)
        return cls(
            serial=serial,
            gtin13=company + item_padded + check,
            company_prefix=company,
            item_reference=item,
            check_digit=check,
        )

    async def get_model_name(self) -> str:
        loader = await get_model_loader()
        model = loader.get_model(self.item_reference)
        return model.name if model else self.item_reference
