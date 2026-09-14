"""Create a reversible 2 MiB ROM with a reserved 1000-glyph Korean font area.

This reserves storage and documents the page layout. It does not change the
game's text renderer; a later Korean text patch can load either 512-glyph page
into the BG3 font area and emit the corresponding tile indices.
"""
from __future__ import annotations

import hashlib
import json
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "Albert Odyssey.sfc"
OUT_DIR = Path(__file__).resolve().parent
OUT_ROM = ROOT / "Albert Odyssey - Korean Font Space.sfc"
OUT_BIN = OUT_DIR / "korean_font_space_1000.bin"
OUT_PNG = OUT_DIR / "korean_font_space_1000.png"
OUT_PREVIEW = OUT_DIR / "korean_font_space_1000_preview.png"
OUT_INFO = OUT_DIR / "korean_font_space_info.json"
OUT_CSV = OUT_DIR / "korean_font_space_indices.csv"

ORIGINAL_SIZE = 0x100000
EXPANDED_SIZE = 0x200000
ROM_SIZE_HEADER = 0x7FD7
CHECKSUM_COMPLEMENT = 0x7FDC
CHECKSUM = 0x7FDE
SLOTS = 1000
PAGE_SLOTS = 512
PAGE_COUNT = 2
GLYPH_BYTES = 32  # SNES 2bpp, 8x16: two 8x8 tiles x 16 bytes
PAGE_BYTES = PAGE_SLOTS * GLYPH_BYTES
SPACE_BYTES = PAGE_COUNT * PAGE_BYTES


def page_pack() -> bytes:
    """Return two 512-slot pages in the game's 16-glyph tile-row layout.

    A full page is 32 groups. Each group stores 16 upper 8x8 tiles followed
    by 16 lower 8x8 tiles, matching the current font loader's tile convention.
    The reserved cells are transparent (all-zero 2bpp tiles).
    """
    return bytes(SPACE_BYTES)


def indexed_template() -> Image.Image:
    # 1000 original-size 8x16 cells, 32 columns x 32 rows per page.
    im = Image.new("P", (32 * 8, PAGE_COUNT * 32 * 16), 0)
    im.putpalette([0, 0, 0, 18, 24, 48, 123, 134, 154, 246, 241, 221] + [0] * 756)
    for index in range(SLOTS):
        page = index // PAGE_SLOTS
        slot = index % PAGE_SLOTS
        x = (slot % 32) * 8
        y = (page * 32 + slot // 32) * 16
        # index 0 is a transparent placeholder; leave cell empty.
        # A thin marker in the first pixel makes page/slot boundaries visible
        # to a font editor while keeping the actual binary fully blank.
        im.putpixel((x, y), 2)
    return im


def preview(template: Image.Image) -> Image.Image:
    scale = 2
    rgb = template.convert("RGB").resize((template.width * scale, template.height * scale), Image.Resampling.NEAREST)
    # Keep the sheet useful at 2x while adding labels outside the pixel area.
    margin = 36
    canvas = Image.new("RGB", (rgb.width + margin * 2, rgb.height + 70), "#121830")
    canvas.paste(rgb, (margin, 70))
    draw = ImageDraw.Draw(canvas)
    try:
        title = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 24)
        small = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 14)
    except OSError:
        title = small = None
    draw.text((margin, 14), "KOREAN FONT SPACE / 1000 GLYPH SLOTS", fill="#f6f1dd", font=title)
    draw.text((margin, 44), "page 0: slots 000-511 | page 1: slots 512-999 | cell: 8 x 16 px", fill="#b7c0d6", font=small)
    # Page separators and labels do not belong to the indexed template.
    for page in range(PAGE_COUNT):
        y = 70 + page * 32 * 16 * scale
        draw.line((0, y, canvas.width, y), fill="#5e729d", width=1)
        draw.text((6, y + 3), f"P{page}", fill="#91a6d7", font=small)
    return canvas


def checksum_pair(data: bytearray) -> tuple[int, int]:
    """Return the complement/checksum pair accepted by Snes9x 1.63.

    This title's checksum is the byte sum of the complete image including
    the four checksum bytes.  The pair is therefore solved as a tiny fixed
    point after clearing the old values.
    """
    scratch = bytearray(data)
    scratch[CHECKSUM_COMPLEMENT:CHECKSUM + 2] = b"\0\0\0\0"
    base_sum = sum(scratch) & 0xFFFF
    checksum = base_sum
    for _ in range(8):
        complement = checksum ^ 0xFFFF
        total = (
            base_sum
            + (complement & 0xFF)
            + (complement >> 8)
            + (checksum & 0xFF)
            + (checksum >> 8)
        ) & 0xFFFF
        if total == checksum:
            break
        checksum = total
    else:
        raise ValueError("checksum fixed point did not converge")
    return checksum ^ 0xFFFF, checksum


def main() -> None:
    original = ROM_PATH.read_bytes()
    if len(original) != ORIGINAL_SIZE:
        raise ValueError(f"Expected a 1 MiB ROM, got {len(original):#x} bytes")
    original_sha256 = hashlib.sha256(original).hexdigest()
    space = page_pack()
    assert len(space) == SPACE_BYTES == 0x8000

    # Append the reserved font pages to the new bank range. The source ROM is
    # never overwritten. Update the ROM-size header from 1 MiB (0x0A) to 2 MiB
    # (0x0B), then write the standard checksum pair for the expanded image.
    expanded = bytearray(original) + bytearray(EXPANDED_SIZE - ORIGINAL_SIZE)
    expanded[ROM_SIZE_HEADER] = 0x0B
    expanded[ORIGINAL_SIZE:ORIGINAL_SIZE + len(space)] = space
    complement, checksum = checksum_pair(expanded)
    expanded[CHECKSUM_COMPLEMENT:CHECKSUM + 2] = complement.to_bytes(2, "little") + checksum.to_bytes(2, "little")
    OUT_ROM.write_bytes(expanded)
    OUT_BIN.write_bytes(space)

    sheet = indexed_template()
    sheet.save(OUT_PNG)
    preview(sheet).save(OUT_PREVIEW)
    info = {
        "source_rom": ROM_PATH.name,
        "source_sha256": original_sha256,
        "expanded_rom": OUT_ROM.name,
        "expanded_rom_size": len(expanded),
        "reserved_rom_offset": f"0x{ORIGINAL_SIZE:06X}",
        "reserved_rom_end_inclusive": f"0x{ORIGINAL_SIZE + len(space) - 1:06X}",
        "reserved_bytes": len(space),
        "glyph_slots": SLOTS,
        "glyph_bytes": GLYPH_BYTES,
        "page_count": PAGE_COUNT,
        "slots_per_page": PAGE_SLOTS,
        "page_bytes": PAGE_BYTES,
        "page_layout": "32 rows x 16-glyph groups; each group has 16 upper tiles then 16 lower tiles",
        "tile_format": "SNES 2bpp planar, 8x16 glyphs",
        "runtime_note": "Reserved storage only. The original renderer still uses its existing 376-slot font page until a page-loading/text-encoding hook is added.",
        "expanded_header_rom_size_byte": "0x0B",
        "expanded_header_checksum_complement": f"0x{complement:04X}",
        "expanded_header_checksum": f"0x{checksum:04X}",
    }
    OUT_INFO.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["global_slot", "page", "page_slot", "upper_tile_in_page_hex",
                         "lower_tile_in_page_hex", "rom_offset_hex", "rom_lower_offset_hex"])
        for index in range(SLOTS):
            page, slot = divmod(index, PAGE_SLOTS)
            group, column = divmod(slot, 16)
            upper_tile = group * 32 + column
            lower_tile = upper_tile + 16
            upper_rom = ORIGINAL_SIZE + page * PAGE_BYTES + upper_tile * 16
            lower_rom = ORIGINAL_SIZE + page * PAGE_BYTES + lower_tile * 16
            writer.writerow([index, page, slot, f"0x{upper_tile:03X}", f"0x{lower_tile:03X}",
                             f"0x{upper_rom:06X}", f"0x{lower_rom:06X}"])
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
