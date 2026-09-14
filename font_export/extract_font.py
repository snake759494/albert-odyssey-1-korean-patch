"""Extract Albert Odyssey's original compressed 2bpp font, without changing the ROM.

Requires Python 3 and Pillow. Run: python font_export/extract_font.py
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
ROM = ROOT / 'Albert Odyssey.sfc'
BLOCKS = [(0xC8000, 0xC8BF6, 0x1000), (0xC8BF6, 0xC97A7, 0x1000),
          (0xC97A7, 0xCA3C2, 0xF80)]
# Display colors only: retain the original four pixel indices in indexed PNGs.
PALETTE = [0, 0, 0, 18, 24, 48, 123, 134, 154, 246, 241, 221]


def decompress(rom: bytes, start: int) -> tuple[bytes, int]:
    """ROM routine $82:8C28: seed repetition with optional bit transpose."""
    pos, output = start, bytearray()
    while pos < len(rom):
        flags = rom[pos]
        pos += 1
        if flags == 1:
            return bytes(output), pos
        seed = rom[pos]
        pos += 1
        group = [seed]
        for bit in range(7, 0, -1):
            if flags & (1 << bit):
                group.append(seed)
            else:
                group.append(rom[pos])
                pos += 1
        if flags & 1:
            group = [sum(((group[x] >> (7 - y)) & 1) << (7 - x)
                         for x in range(8)) for y in range(8)]
        output.extend(group)
        if len(output) > 0x20000:
            raise ValueError('Decompression exceeded safety bound')
    raise ValueError('Missing end marker')


def indexed_image(size: tuple[int, int]) -> Image.Image:
    im = Image.new('P', size, 1)
    im.putpalette(PALETTE + [0] * (768 - len(PALETTE)))
    return im


def glyph(data: bytes, index: int) -> Image.Image:
    # Each group of 16 characters stores 16 upper tiles, then 16 lower tiles.
    tile = (index // 16) * 32 + index % 16
    im = indexed_image((8, 16))
    for y in range(16):
        off = (tile + (16 if y >= 8 else 0)) * 16 + (y % 8) * 2
        for x in range(8):
            color = ((data[off] >> (7 - x)) & 1) | (((data[off + 1] >> (7 - x)) & 1) << 1)
            im.putpixel((x, y), color)
    return im


def ids_for_kanji() -> list[int]:
    # Font table positions, not Unicode encodings. Includes duplicate glyphs.
    first = list(range(0xC5, 0x100))
    first = [x for x in first if x not in (0xCC, 0xD6, 0xF6, 0xF7)]
    second = (list(range(0x00, 0x08)) + list(range(0x10, 0x18))
              + list(range(0x1A, 0x29)) + list(range(0x2D, 0x30))
              + [0x32, 0x33, 0x34] + list(range(0x37, 0x3E))
              + list(range(0x40, 0x46)) + [0x4A, 0x4B, 0x4C, 0x4E]
              + [0x50] + list(range(0x52, 0x5A))
              + [0x60, 0x61, 0x63, 0x64, 0x66, 0x67, 0x6A])
    return first + [0x100 + x for x in second]


def make_sheet(images: list[Image.Image], ids: list[int]) -> Image.Image:
    sheet = indexed_image((128, ((len(ids) + 15) // 16) * 16))
    for i, index in enumerate(ids):
        sheet.paste(images[index], ((i % 16) * 8, (i // 16) * 16))
    return sheet


def make_preview(images: list[Image.Image], ids: list[int]) -> Image.Image:
    margin, cell_w, cell_h, top = 24, 56, 92, 92
    rows = (len(ids) + 15) // 16
    canvas = Image.new('RGB', (margin * 2 + cell_w * 16, top + cell_h * rows + 28), '#121830')
    d = ImageDraw.Draw(canvas)
    font_path = Path('C:/Windows/Fonts/consola.ttf')
    title_font = ImageFont.truetype(str(font_path), 24)
    label_font = ImageFont.truetype(str(font_path), 13)
    d.text((margin, 18), 'ALBERT ODYSSEY / JAPANESE KANJI', font=title_font, fill='#f6f1dd')
    d.text((margin, 52), f'{len(ids)} glyph slots | original 8 x 16 px | shown at 4x', font=label_font, fill='#b7c0d6')
    d.text((margin, 70), 'Labels: font table : hexadecimal character index', font=label_font, fill='#b7c0d6')
    for i, index in enumerate(ids):
        x, y = margin + (i % 16) * cell_w, top + (i // 16) * cell_h
        canvas.paste(images[index].convert('RGB').resize((32, 64), Image.Resampling.NEAREST), (x + 12, y))
        label = f'{1 + index // 256}:{index % 256:02X}'
        d.text((x + 12, y + 69), label, font=label_font, fill='#91a6d7')
    return canvas


def main() -> None:
    rom = ROM.read_bytes()
    parts, metadata = [], []
    for start, expected_end, expected_size in BLOCKS:
        part, end = decompress(rom, start)
        assert (end, len(part)) == (expected_end, expected_size)
        parts.append(part)
        metadata.append({'rom_start': f'0x{start:06X}', 'rom_end_inclusive': f'0x{end - 1:06X}',
                         'compressed_bytes': end - start, 'decompressed_bytes': len(part)})
    data = b''.join(parts)
    # Last tile row is partial: 16 upper tiles but only 8 lower tiles.
    # Only indices 0x170..0x177 can form complete 8x16 cells.
    count = 376
    images = [glyph(data, i) for i in range(count)]
    kanji_ids = ids_for_kanji()
    full_sheet = make_sheet(images, list(range(count)))
    kanji_sheet = make_sheet(images, kanji_ids)
    full_sheet.save(OUT / 'font_full_indexed.png')
    full_sheet.resize((512, 1536), Image.Resampling.NEAREST).save(OUT / 'font_full_preview.png')
    kanji_sheet.save(OUT / 'kanji_indexed.png')
    make_preview(images, kanji_ids).save(OUT / 'kanji_preview.png')
    (OUT / 'font_decompressed_2bpp.bin').write_bytes(data)

    # A row per exported kanji slot, preserving locations for future patch work.
    with (OUT / 'kanji_indices.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['sheet_slot', 'font_table', 'character_index_hex', 'upper_tile_hex',
                    'lower_tile_hex', 'upper_decompressed_offset_hex', 'lower_decompressed_offset_hex'])
        for i, index in enumerate(kanji_ids):
            tile = (index // 16) * 32 + index % 16
            w.writerow([i, 1 + index // 256, f'{index % 256:02X}', f'{tile:03X}',
                        f'{tile + 16:03X}', f'{tile * 16:04X}', f'{(tile + 16) * 16:04X}'])
    result = {'rom_name': ROM.name, 'rom_size': len(rom), 'rom_sha256': hashlib.sha256(rom).hexdigest(),
              'blocks': metadata, 'decompressed_size': len(data), 'tile_count_8x8': len(data) // 16,
              'complete_glyph_slots_8x16': count, 'selected_kanji_slots': len(kanji_ids),
              'font_format': 'SNES 2bpp planar, 8x16; lower tile = upper tile + 0x10',
              'decompressor_rom_offset': '0x010C28', 'decompressor_snes_address': '$82:8C28'}
    runtime = ROOT / 'analysis_font_scan/frame5000_mem3.bin'
    if runtime.exists():
        vram = runtime.read_bytes()
        assert data == vram[0x8000:0x8000 + len(data)]
        result['runtime_validation'] = 'Exact byte match with game VRAM bytes 0x8000-0xAF7F'
    (OUT / 'extraction_info.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert ROM.read_bytes() == rom
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
