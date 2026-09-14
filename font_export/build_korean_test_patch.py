"""Build a Korean dialogue test patch for the supplied early-game captures.

The original ROM is kept untouched.  The patch uses the previously expanded
2-Mbit image, installs the Hangul glyphs in table-1 slots, and overlays the
complete custom 2bpp font into VRAM after the game's normal font load.  The
overlay is needed because the original compressed font blocks have no spare
capacity for the full early-game Hangul set.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
BASE = ROOT / "Albert Odyssey - Korean Font Space.sfc"
ROM_OUT = ROOT / "Albert Odyssey - Korean Test.sfc"

BLOCKS = [
    (0xC8000, 0xC8BF6, 0x1000),
    (0xC8BF6, 0xC97A7, 0x1000),
    (0xC97A7, 0xCA3C2, 0xF80),
]

# Stable table-1 slots used by the first prompt.  Additional slots needed by
# the rest of the supplied screenshots are assigned below from unused table-1
# positions, while the original ASCII/punctuation slots remain untouched.
GLYPH_SLOTS = {
    "엄": 0xCD,
    "마": 0xF4,
    "년": 0xF3,
    "전": 0x6A,
    "이": 0x6F,
    "야": 0xED,
    "기": 0x4D,
    "를": 0x6D,
    "듣": 0x46,
    "고": 0x62,
    "싶": 0x66,
    "니": 0x5C,
    "알": 0xD9,
    "버": 0xE9,
    "트": 0xF2,
    "예": 0x6B,
    "아": 0x3F,
    "요": 0x5F,
    "글": 0xEC,
    "는": 0xE0,
    "다": 0xC8,
    "대": 0xC7,
    "되": 0x6C,
    "드": 0x68,
    "략": 0x67,
    "로": 0x60,
    "법": 0xFF,
    "사": 0xFA,
    "스": 0xE6,
    "시": 0xE5,
    "오": 0xE4,
    "왈": 0xDF,
    "위": 0xDC,
    "을": 0x61,
    "의": 0x5A,
    "작": 0x58,
    "찾": 0x57,
    "침": 0x54,
    "해": 0x4A,
    "했": 0x49,
    "힘": 0x3D,
}

# Text-style 1 table-1 values used by the original game.
ASCII = {str(i): i for i in range(10)}
ASCII.update({chr(ord("A") + i): 0x0A + i for i in range(26)})
ASCII.update({"?": 0x24, "!": 0x25, "-": 0x26, "/": 0x27,
              " ": 0x28, "「": 0xC1, "」": 0xC2, ".": 0xC3,
              ",": 0xC4, ":": 0xD6, "$": 0xF6})

# Dialogues visible in Albert Odyssey000.png ... Albert Odyssey034.png.
# Entries are kept short enough for the original message boxes while retaining
# the meaning of the Japanese lines.
STYLE1_PATCHES = {
    0x43911: "글로버스의 힘을 찾아",
    0x4398C: "모두 전멸했다!",
    0x439AA: "설마... 이렇게 되다니?!",
    0x43A03: "소피아를 부탁해!",
    0x43A65: "아빠!",
    0x438FC: "---10년 후---",
    0x44650: "내일이면 너는",
    0x4465F: "16살이네. 푹 쉬렴",
    # This is a style-1 line in the opening narration.  Its original byte
    # footprint is larger than the translated text, but the length byte keeps
    # the unused Japanese bytes out of the rendered line.
    0x44674: "대마법사 오스왈드는 침략을 시작했다",
    0x43EA9: "---다음 날---",
    0x41CA4: "용사의 피를 잇는구나",
    0x43E99: "이제 홀로 서야 해",
    0x43E84: "훌륭한 영웅이 되렴",
}

STYLE2_PATCHES = {
    0x44619: ("엄마「10년 전 이야기를 듣고 싶니? 알버트」", True),
    0x43929: ("기사1「슬레이 대장!」", True),
    0x43946: ("슬레이「너 혼자냐?!」", True),
    0x43965: ("기사1「모두 전멸했습니다!」", True),
    0x43F8A: ("슬레이「총독!」", True),
    0x4399D: ("총독「젠장", True),
    0x43D4E: ("기사2「총독! 갑시다!」", True),
    0x43D73: ("기사3「총독의 이름을 걸고!」", True),
    0x439BC: ("총독「좋아! 가자!」", True),
    0x439DF: ("소피아「아빠!」", True),
    0x439F2: ("엄마「여보」", True),
    0x43AA5: ("총독「걱정 마!」", True),
    0x43A15: ("소피아「안 돼! 가지 마!」", True),
    0x43AD1: ("슬레이「제가 갑니다!!」", True),
    0x43AF4: ("슬레이「전투에서 지고 있습니다!」", True),
    0x43B33: ("슬레이「총독! 더는 못 갑니다!」", True),
    0x43B6A: ("총독「괜찮나?!」", True),
    0x43B8D: ("슬레이「이제 후퇴해야 합니다!」", True),
    0x43BC2: ("슬레이「총독!」", True),
    0x43BDF: ("총독「마을을 대피시켜라!」", True),
    0x43C1C: ("슬레이「소피아를 위해 돌아오세요!」", True),
    0x43C4F: ("슬레이「이길 수 없어, 돌아갑시다!」", True),
    0x43C86: ("기사「주민들을 대피시켜야 합니다!」", True),
    0x43A3E: ("소피아「아빠는 어디 있어?」", True),
    0x43A90: ("슬레이「...」", True),
    0x43CC5: ("소피아「엄마 어디 있어?」", True),
    0x43D9A: ("오스왈드「수정?」", True),
    0x43DB9: ("오스왈드「마법을 지녔군...」", True),
    0x43CE8: ("소피아「엄마! 엄마!」", True),
    0x43E46: ("소피아「엄마를 돌려줘!」", True),
    0x43E1F: ("사제「무슨 일이냐! 정신 차려!」", True),
    0x43E65: ("엄마「일어나렴...」", True),
    0x41C7B: ("엄마「이제 16살이구나」", True),
    0x43DF0: ("엄마「선물이야. $1000도 줄게」", True),
}

FONT_OVERLAY_OFFSET = 0x108000
FONT_OVERLAY_CODE_OFFSET = 0x10B000
FONT_OVERLAY_SIZE = 0x2F80


def extend_glyph_slots() -> None:
    """Assign every new Hangul syllable to an unused table-1 slot."""
    chars = sorted({ch for text in list(STYLE1_PATCHES.values())
                    + [text for text, _ in STYLE2_PATCHES.values()]
                    for ch in text if "가" <= ch <= "힣"})
    used = set(GLYPH_SLOTS.values()) | set(ASCII.values())
    candidates = [slot for slot in range(0x100) if slot not in used]
    missing = [ch for ch in chars if ch not in GLYPH_SLOTS]
    if len(missing) > len(candidates):
        raise ValueError(f"not enough table-1 slots: {len(missing)} > {len(candidates)}")
    for ch, slot in zip(missing, candidates):
        GLYPH_SLOTS[ch] = slot


def decompress(rom: bytes, start: int) -> tuple[bytes, int]:
    """Decode the game's 8-byte seed/repeat font stream."""
    pos = start
    out = bytearray()
    while True:
        flags = rom[pos]
        pos += 1
        if flags == 1:
            return bytes(out), pos
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
        out.extend(group)


def compress(data: bytes) -> bytes:
    """Encode a stream accepted by the original game decompressor."""
    if len(data) % 8:
        raise ValueError("font block must be a multiple of 8 bytes")
    out = bytearray()
    for off in range(0, len(data), 8):
        output_group = list(data[off:off + 8])

        # The original compressor chooses the shorter of the direct form and
        # the bit-transposed form.  Reproducing that choice keeps untouched
        # blocks byte-for-byte the same size as the shipped ROM.
        transposed = [sum(((output_group[x] >> (7 - y)) & 1) << (7 - x)
                          for x in range(8)) for y in range(8)]
        candidates: list[bytes] = []
        for transpose_flag, group in ((0, output_group), (1, transposed)):
            seed = group[0]
            flags = transpose_flag
            raw = bytearray()
            for i, value in enumerate(group[1:], start=1):
                if value == seed:
                    flags |= 1 << (8 - i)
                else:
                    raw.append(value)
            candidates.append(bytes([flags, seed]) + raw)
        out.extend(min(candidates, key=len))
    out.append(1)
    return bytes(out)


def glyph(data: bytearray, index: int, image: Image.Image) -> None:
    """Write one 8x16 2bpp glyph into the decompressed font stream."""
    if image.size != (8, 16):
        raise ValueError(image.size)
    tile = (index // 16) * 32 + index % 16
    for y in range(16):
        off = (tile + (16 if y >= 8 else 0)) * 16 + (y % 8) * 2
        p0 = p1 = 0
        for x in range(8):
            value = image.getpixel((x, y))
            p0 |= (value & 1) << (7 - x)
            p1 |= ((value >> 1) & 1) << (7 - x)
        data[off] = p0
        data[off + 1] = p1


def korean_glyph(ch: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    """Rasterize a Hangul syllable into the game's 8x16 2bpp cell."""
    src = Image.new("L", (16, 16), 0)
    ImageDraw.Draw(src).text((0, 0), ch, font=font, fill=255)
    src = src.resize((8, 16), Image.Resampling.LANCZOS)
    # The game's text font uses color index 1 as the opaque bubble/background
    # color; zero would be transparent and would reveal the map behind the
    # dialogue window.  Keep the same convention and reserve indices 2/3 for
    # the antialiased foreground strokes.
    return src.point(lambda p: 3 if p >= 192 else (2 if p >= 80 else 1))


def table1(text: str) -> list[int]:
    encoded: list[int] = []
    for ch in text:
        if ch in GLYPH_SLOTS:
            encoded.append(GLYPH_SLOTS[ch])
        elif ch in ASCII:
            encoded.append(ASCII[ch])
        else:
            raise ValueError(f"no table-1 mapping for {ch!r}")
    return encoded


def write_style1(rom: bytearray, offset: int, text: str) -> None:
    body = bytes(table1(text))
    if len(body) > 0xFF:
        raise ValueError("style-1 text too long")
    # The text routine reads one terminator byte after the length-counted
    # body.  Replace that byte with a space so a shortened Korean line cannot
    # expose the original Japanese glyph at the right edge.
    rom[offset:offset + 2 + len(body)] = bytes([len(body)]) + body + bytes((ASCII[" "],))


def write_style2(rom: bytearray, offset: int, text: str, speaker: bool = True,
                 length: int | None = None, pad_after: bool = False) -> None:
    chars = table1(text)
    target_length = len(chars) if length is None else length
    if target_length > 31:
        raise ValueError("style-2 text exceeds 5-bit length")
    if len(chars) > target_length:
        raise ValueError(f"style-2 text too long at {offset:#x}: {len(chars)} > {target_length}")
    pairs = bytearray()
    for i, code in enumerate(chars):
        # The original prompt colors the speaker name red.  All dialogue
        # glyphs use the normal table-1/palette attribute.
        attr = 0x0C if speaker and i < 2 else 0x00
        pairs.extend((code, attr))
    for _ in range(target_length - len(chars)):
        pairs.extend((ASCII[" "], 0x00))
    blob = bytes([0xE0 | target_length]) + pairs
    # This event record is consumed once more by the original text routine
    # after the length-counted pairs.  A blank pair prevents the old Japanese
    # byte immediately following a shortened test string from being drawn.
    if pad_after:
        blob += bytes((ASCII[" "], 0x00))
    rom[offset:offset + len(blob)] = blob


def write_style2_original(rom: bytearray, base: bytes, offset: int,
                          text: str, speaker: bool = True) -> None:
    """Replace a two-byte record without changing its original footprint."""
    # The renderer consumes the closing pair immediately after the
    # length-counted body.  Clear that pair too, otherwise one Japanese
    # glyph from the original record remains visible at the right edge.
    write_style2(rom, offset, text, speaker=speaker,
                 length=base[offset] & 0x1F, pad_after=True)


def lo_rom_address(offset: int) -> tuple[int, int]:
    """Return the SNES LoROM bank/address for a file offset."""
    return 0x80 + offset // 0x8000, 0x8000 + offset % 0x8000


def install_font_overlay(rom: bytearray, font_data: bytes) -> None:
    """Hook every decompression call and DMA the custom font into VRAM.

    The game's two high-level font-loader call sites are not reached during
    the opening sequence.  The low-level decompressor is called whenever a
    graphics/font block is loaded, so wrapping those calls makes the overlay
    deterministic for the title, intro, and early-game scenes.
    """
    if len(font_data) != FONT_OVERLAY_SIZE:
        raise ValueError(len(font_data))
    data_bank, data_addr = lo_rom_address(FONT_OVERLAY_OFFSET)
    code_bank, code_addr = lo_rom_address(FONT_OVERLAY_CODE_OFFSET)
    if (data_bank, data_addr) != (0xA1, 0x8000) or (code_bank, code_addr) != (0xA1, 0xB000):
        raise ValueError((hex(data_bank), hex(data_addr), hex(code_bank), hex(code_addr)))

    # The wrapper calls the original decompressor first.  The DMA below then
    # replaces the complete 12,160-byte font region from the expanded ROM.
    # VRAM byte offset 0x8000 is word address $4000 on the SNES PPU.
    code = bytes.fromhex(
        "08 8B 22 28 8C 82 E2 20 A9 80 8D 15 21 9C 16 21 "
        "A9 40 8D 17 21 A9 01 8D 00 43 A9 18 8D 01 43 "
        "A9 00 8D 02 43 A9 80 8D 03 43 A9 A1 8D 04 43 "
        "A9 80 8D 05 43 A9 2F 8D 06 43 A9 01 8D 0B 42 "
        "AB 28 6B"
    )
    rom[FONT_OVERLAY_OFFSET:FONT_OVERLAY_OFFSET + len(font_data)] = font_data
    rom[FONT_OVERLAY_CODE_OFFSET:FONT_OVERLAY_CODE_OFFSET + len(code)] = code
    hook = bytes((0x22, code_addr & 0xFF, code_addr >> 8, code_bank))
    original_call = bytes.fromhex("22 28 8C 82")
    hooks = 0
    # Limit the scan to the original ROM area so the JSL inside the new hook
    # routine is left pointing at the real decompressor.
    for offset in range(FONT_OVERLAY_CODE_OFFSET):
        if rom[offset:offset + 4] == original_call:
            rom[offset:offset + 4] = hook
            hooks += 1
    if hooks != 48:
        raise ValueError(f"unexpected decompressor hook count: {hooks}")


def update_checksum(rom: bytearray) -> None:
    """Update the LoROM header checksum after expanding/patching the image."""
    # Header checksum fields are at $7FDC/$7FDE for this LoROM.
    total = sum(rom) & 0xFFFF
    # The conventional SNES checksum is the sum of all bytes with the
    # checksum/complement bytes zeroed, then complemented for $7FDC.
    rom[0x7FDC:0x7FE0] = b"\x00\x00\x00\x00"
    total = sum(rom) & 0xFFFF
    checksum = total
    complement = checksum ^ 0xFFFF
    rom[0x7FDC:0x7FDE] = complement.to_bytes(2, "little")
    rom[0x7FDE:0x7FE0] = checksum.to_bytes(2, "little")


def main() -> None:
    base = BASE.read_bytes()
    if len(base) != 0x200000:
        raise ValueError(f"unexpected expanded ROM size: {len(base):#x}")
    rom = bytearray(base)
    extend_glyph_slots()

    parts: list[bytes] = []
    for start, end, expected in BLOCKS:
        part, actual_end = decompress(base, start)
        if (actual_end, len(part)) != (end, expected):
            raise ValueError((hex(start), hex(actual_end), len(part)))
        parts.append(part)
    font_data = bytearray(b"".join(parts))

    font_path = Path("C:/Windows/Fonts/gulim.ttc")
    font = ImageFont.truetype(str(font_path), 16)
    for ch, slot in GLYPH_SLOTS.items():
        glyph(font_data, slot, korean_glyph(ch, font))

    # The original compressed blocks are left intact.  The expanded ROM has
    # enough room for the complete custom font, and the hook above loads this
    # uncompressed overlay after the game's normal font loader runs.
    install_font_overlay(rom, bytes(font_data))

    # Choice shown by frame 000.
    write_style2_original(rom, base, 0x44619,
                          "엄마「10년 전 이야기를 듣고 싶니? 알버트」")
    # The menu renderer reserves a leading alignment cell for both options,
    # matching the original ` OK` / ` NO` records.
    write_style1(rom, 0x4379B, " 예")
    write_style1(rom, 0x4379F, " 아니요")
    for offset, text in STYLE1_PATCHES.items():
        write_style1(rom, offset, text)
    for offset, (text, speaker) in STYLE2_PATCHES.items():
        write_style2_original(rom, base, offset, text, speaker=speaker)

    # Mark the test build in the standard title field while preserving the
    # original ROM as a separate input artifact.
    title = b"ALBERT ODYSSEY KOR   "
    rom[0x7FC0:0x7FC0 + 21] = title[:21]
    update_checksum(rom)
    ROM_OUT.write_bytes(rom)

    # Export a readable glyph proof sheet for the patch review.
    columns = 18
    rows = max(2, (len(GLYPH_SLOTS) + columns - 1) // columns)
    sheet = Image.new("RGB", (columns * 48, rows * 88), "#121830")
    d = ImageDraw.Draw(sheet)
    for i, (ch, slot) in enumerate(GLYPH_SLOTS.items()):
        im = korean_glyph(ch, font).convert("L").resize((32, 64), Image.Resampling.NEAREST)
        rgb = Image.new("RGB", im.size, "black")
        rgb.paste("white", mask=im.point(lambda p: 255 if p > 1 else 0))
        x = (i % 18) * 48 + 8
        y = (i // 18) * 88 + 4
        sheet.paste(rgb, (x, y))
        d.text((x, y + 66), f"{ch} {slot:02X}", fill="#f6f1dd")
    (OUT / "korean_test_glyphs.png").write_bytes(_png_bytes(sheet))

    info = {
        "base": BASE.name,
        "output": ROM_OUT.name,
        "output_size": len(rom),
        "output_sha256": hashlib.sha256(rom).hexdigest(),
        "patched_text": {
            "0x4379B": "예",
            "0x4379F": "아니요",
            **{f"0x{offset:X}": text for offset, text in STYLE1_PATCHES.items()},
            **{f"0x{offset:X}": text for offset, (text, _) in STYLE2_PATCHES.items()},
        },
        "font_overlay_offset": f"0x{FONT_OVERLAY_OFFSET:06X}",
        "font_overlay_size": FONT_OVERLAY_SIZE,
        "font_overlay_code_offset": f"0x{FONT_OVERLAY_CODE_OFFSET:06X}",
        "glyph_count": len(GLYPH_SLOTS),
        "glyph_slots": {ch: f"0x{slot:02X}" for ch, slot in GLYPH_SLOTS.items()},
        "original_compressed_sizes": [end - start for start, end, _ in BLOCKS],
    }
    (OUT / "korean_test_patch_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))


def _png_bytes(im: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


if __name__ == "__main__":
    main()
