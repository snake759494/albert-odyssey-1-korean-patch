"""Static verification for the Korean ROM build.

This deliberately does not launch an emulator or inspect a rendered frame.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "font_export"))
import build_korean_full_patch as build  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


rom_path = ROOT / "Albert Odyssey - Korean Full.sfc"
rom = rom_path.read_bytes()
info = json.loads((ROOT / "font_export" / "korean_full_patch_info.json").read_text(encoding="utf-8"))
original = (ROOT / "Albert Odyssey.sfc").read_bytes()
records = json.loads((ROOT / "analysis" / "all_rom_text.json").read_text(encoding="utf-8"))

assert len(rom) == 0x200000
assert sha(rom) == info["output_sha256"]
assert sha(original) == "abc9ee63a624dbabfd255774a254517a46be54c37aa26a89db2a299277548190"
checksum = int.from_bytes(rom[0x7FDE:0x7FE0], "little")
complement = int.from_bytes(rom[0x7FDC:0x7FDE], "little")
assert checksum == sum(rom) & 0xFFFF
assert complement ^ checksum == 0xFFFF
assert info["translated_pointer_records"] == 1428
assert info["max_cells_per_record"] <= 31
assert not info["records_over_31_cells"]
assert info["pool_size"] <= info["pool_capacity"]
assert info["font_reserved_glyph_slots"] == 1000
assert rom[build.FONT_OVERLAY_OFFSET + 0x2A10 : build.FONT_OVERLAY_OFFSET + 0x2A20] == bytes(16)
assert all(0x151 not in [int(v, 16) for v in r["dynamic_targets"].values()] for r in json.loads((ROOT / "analysis" / "full_dialogue_extracted.json").read_text(encoding="utf-8"))["records"])
assert len(records) == 1577
assert not any(int(code) == 0x06 and int(attr) & 1 for r in records for code, attr in r["pairs"])

merged = {**build.STYLE1_KO, **build.STYLE2_KO, **build.STYLE5_KO}
merged.update({int(k, 16): v for k, v in build.SUPPLEMENT.items()})
for text in merged.values():
    assert not any("\u3040" <= ch <= "\u30ff" or "\u3400" <= ch <= "\u9fff" for ch in text), repr(text)
    assert "�" not in text

result = {
    "rom_sha256": sha(rom),
    "size": len(rom),
    "checksum": "pass",
    "original_unchanged": True,
    "source_records": len(records),
    "translated_pointer_records": info["translated_pointer_records"],
    "max_cells_per_record": info["max_cells_per_record"],
    "pool": {"size": info["pool_size"], "capacity": info["pool_capacity"]},
    "font_reserved_glyph_slots": info["font_reserved_glyph_slots"],
    "background_clear_tile": "0x2A1",
    "game_execution": False,
}
print(json.dumps(result, ensure_ascii=False))
