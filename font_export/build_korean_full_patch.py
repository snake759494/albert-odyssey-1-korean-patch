"""Build the full Korean Albert Odyssey patch.

The game stores most text as pointers into bank $88 and converts TextStyle1/2
records into a tilemap buffer. This builder updates original length headers,
relocates every translated TextStyle1/2 record to banks $A5-$A8, and keeps the
original pointer table intact while a wrapper looks up translated records by
their original pointer. All translated records are emitted as TextStyle2 pairs,
which preserves the game's table/palette byte and gives every translated line
the full 31-character record limit.

Original table-2 icons and retained text stay intact. Reclaimed table-2 cells
extend the dynamic font pool. Korean glyphs share slots only when script coexistence constraints permit it. Every shared glyph is
restored before each use, from the expanded 1,000-glyph ROM store. Fixed-width
names own exclusive slots. Copies are limited to four glyphs per fresh VBlank.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent
BASE = ROOT / "Albert Odyssey - Korean Font Space.sfc"
ROM_OUT = ROOT / "Albert Odyssey - Korean Full.sfc"
ASM_SOURCE = ROOT / "analysis" / "Albert_Odyssey_translation.asm"

# The three original compressed font streams.  The concatenated decompressed
# stream is the exact 0x2F80-byte VRAM payload used by the normal loader.
BLOCKS = [
    (0xC8000, 0xC8BF6, 0x1000),
    (0xC8BF6, 0xC97A7, 0x1000),
    (0xC97A7, 0xCA3C2, 0xF80),
]

FONT_OVERLAY_OFFSET = 0x108000
# The expanded base ROM keeps two 512-glyph pages (1,024 8x16 slots) before
# the executable overlay.  The first 1,000 are the documented Korean font
# workspace; the extra 24 cells keep the page packing on a power-of-two
# boundary and are left available for future glyphs.
FONT_RESERVED_OFFSET = 0x100000
FONT_RESERVED_SIZE = 0x8000
FONT_RESERVED_SLOTS = 1000
FONT_GLYPH_BYTES = 32
# Keep the original 0x2F80-byte font DMA untouched. Table-2 codes $70-$7F are
# reserved because the source stream ends before that final partial row.
FONT_OVERLAY_SIZE = 0x2F80
FONT_OVERLAY_CODE_OFFSET = 0x10B000
TEXT_HOOK_OFFSET = 0x10B100
TEXT_HOOK_F71D_OFFSET = 0x10B200
TEXT_HOOK_F7C0_OFFSET = 0x10B300
EXT_FONT_CODE_OFFSET = 0x10B400
TABLE2_FONT_OFFSET = 0x10E000
TABLE2_FONT_SIZE = 0x1000  # complete table-2 page, loaded after title graphics
TEXT_MAP_OFFSET = 0x120000
EXT_FONT_OFFSET = 0x10F000
EXT_FONT_SIZE = 0xC00  # retained as an audit/export copy of the extended glyphs
TEXT_POOL_OFFSET = 0x128000
TEXT_POOL_END = 0x148000
DYNAMIC_GLYPH_OFFSET = FONT_RESERVED_OFFSET
DYNAMIC_PATCH_OFFSET = 0x148000
DYNAMIC_PATCH_END = 0x168000
BUBBLE_CLAMP_OFFSET = 0x10B800
TERRAIN_LABELS = ('평야', '숲', '사막', '용암', '도로', '산악', '마법진', '사당', '바다', '신전')
CACHED_UI_LABELS = ('이동 공격 공격력 간접 공격 시전 끝내기 변신 대상 종료 취소',
                    '장비 오른손 왼손 팔 다리 몸통 머리 방어',
                    '회복 소생 치유 뇌격 볼트 소생 사망 격려 기합 화염탄 순간이동')
POINTER_TABLE_OFFSET = 0x40000
POINTER_TABLE_END = 0x40C52
TEXT_MAP_ENTRY_SIZE = 12
TEXT_DIRECT_INDEX_OFFSET = 0x180000  # 32K original pointers, 16-bit map offsets

sys.path.insert(0, str(OUT_DIR))
from full_korean_translation import STYLE1_KO, STYLE2_KO, STYLE5_KO  # noqa: E402

SUPPLEMENT = json.loads((OUT_DIR / 'remaining_korean_translation.json').read_text(encoding='utf-8'))
REVIEW_FIXES = json.loads((OUT_DIR / 'review_fixes.json').read_text(encoding='utf-8'))
for section in REVIEW_FIXES.values():
    SUPPLEMENT.update(section)
ALL_ROM_RECORDS = json.loads((ROOT / 'analysis/all_rom_text.json').read_text(encoding='utf-8'))
BY_ROM_OFFSET = {r['offset']: r for r in ALL_ROM_RECORDS}
# Revisions must keep the existing builder's record style. Some original
# Japanese type-7 records are already represented as TextStyle1 in the source
# script; routing overrides by the ROM header creates a duplicate translation
# in the other dictionary and leaves the consumed text unchanged.
SOURCE_STYLES = {
    int(offset, 16): int(style)
    for style, offset in re.findall(
        r'^\s*TextStyle([12])\(\$([0-9A-Fa-f]+),',
        ASM_SOURCE.read_text(encoding='utf-8'), re.MULTILINE,
    )
}
for offset, text in SUPPLEMENT.items():
    style = SOURCE_STYLES.get(int(offset, 16), 2 if BY_ROM_OFFSET[offset]['type'] == 7 else 1)
    target = STYLE2_KO if style == 2 else STYLE1_KO
    target[int(offset, 16)] = text.replace("'", '')

def layout_source():
    source = ASM_SOURCE.read_text(encoding='utf-8')
    existing = {int(m, 16) for m in re.findall(r'TextStyle[12]\(\$([0-9A-Fa-f]+)', source)}
    extra = [o for o in sorted(SUPPLEMENT) if int(o, 16) not in existing]
    for i, offset in enumerate(extra):
        if i % 6 == 0:
            source += '\n// Additional source records; six-record coexistence window\n'
        style = 2 if BY_ROM_OFFSET[offset]['type'] == 7 else 1
        source += f'TextStyle{style}(${int(offset,16):05X}, "")\n'
    source += '\n// Reviewed Combat Names\n'
    for offset in REVIEW_FIXES['names']:
        source += f'TextStyle1(${int(offset,16):05X}, "")\n'
    source += '\n// Equipment inventory coexistence\n'
    for offset in REVIEW_FIXES['equipment']:
        source += f'TextStyle1(${int(offset,16):05X}, "")\n'
    # Equipment remains visible while item names and status labels are drawn.
    inventory = {o for o,s in {**STYLE1_KO, **STYLE2_KO}.items()
                 if '추억' in s and len(s) <= 12}
    inventory.update((0x40C7D, 0x40C5C, 0x40CBF, 0x41699, 0x416A0,
                      0x416A9, 0x416B2, 0x416BB, 0x416C4, 0x416CD,
                      0x416D6, 0x4100E, 0x4117C, 0x41182, 0x41188,
                      0x4128A, 0x41294, 0x4129D, 0x412A3, 0x412E0,
                      0x412EA, 0x4134C, 0x41764, 0x4176C, 0x4179A,
                      0x417A2, 0x41837, 0x4183D, 0x41842, 0x41853))
    for offset in sorted(inventory):
        source += f'TextStyle1(${offset:05X}, "")\n'
    return source


# Original table-1 mapping.  All original ASCII slots are retained, even if a
# particular character does not occur in the Korean data, so unpatched UI code
# still renders correctly.  The three symbols at the end are table-2 cells.
ASCII_TABLE1 = {str(i): i for i in range(10)}
ASCII_TABLE1.update({chr(ord("A") + i): 0x0A + i for i in range(26)})
ASCII_TABLE1.update(
    {
        "?": 0x24,
        "!": 0x25,
        "-": 0x26,
        "/": 0x27,
        " ": 0x28,
        "「": 0xC1,
        "」": 0xC2,
        ".": 0xC3,
        ",": 0xC4,
        ":": 0xD6,
        "$": 0xF6,
    }
)
ASCII_TABLE2 = {"+": 0x18, ">": 0x31, "%": 0x35}

# Shared slots are allocated from whole-script coexistence constraints.
# Every glyph assigned a shared slot is restored before each record is parsed.
DYNAMIC_TARGET_CANDIDATES = tuple(
    code for code in range(0x100) if code not in ASCII_TABLE1.values()
) + tuple(0x100 + code for code in (
    38,39,40,45,50,51,55,59,60,61,62,63,64,65,66,67,68,69,70,
    74,75,76,77,78,80,82,83,84,85,86,87,88,89,90,91,92,93,
    96,97,98,99,100,101,102,103,104,105,106))
# These ordinary kanji have no retained text consumer. The direct
# terrain label containing 図 is replaced by install_review_ui_fixes as well.
# Neither half of these glyphs overlaps a border, equipment icon or clear tile.
# Keep the same coexistence graph: extra capacity must not weaken constraints.
RECLAIMED_TEXT_GLYPHS = {0x103: '図', 0x11A: '戻', 0x11B: '続',
                         0x11C: '選', 0x11F: '草', 0x122: '取', 0x123: '消',
                         0x100: '定', 0x101: '拡', 0x102: '大',
                         0x106: 'terrain glyph $106', 0x110: 'terrain glyph $110'}
# The original terrain table contains tile $0206 at $000A32. Its entire
# entry is replaced by install_review_ui_fixes. No retained text or equipment
# icon uses glyph $106 (checked again in build_glyph_maps/release verification).
# The same holds for $110 at $000A46. These two cells provide room for
# permanent "접" and "력", removing repeated copies on action/cursor redraws.
# Bubble drawing uses $2C8/$2D8 and $2C9/$2D9 directly, independent of
# text pointers. These must never participate in dynamic glyph allocation.
BUBBLE_GRAPHICS_GLYPHS = {0x168, 0x169, 0x16A}
DYNAMIC_TARGET_CANDIDATES = tuple(c for c in DYNAMIC_TARGET_CANDIDATES if c not in BUBBLE_GRAPHICS_GLYPHS)
DYNAMIC_TARGET_CANDIDATES += tuple(RECLAIMED_TEXT_GLYPHS)
assert not (set(DYNAMIC_TARGET_CANDIDATES) & BUBBLE_GRAPHICS_GLYPHS)
# $89:FD67 clears the text layer with tile $02A1. It is the upper tile
# of table-2 glyph $51, regardless of whether a text pointer uses that glyph.
# Title, battle and caption scenes require this tile to remain transparent.
BACKGROUND_CLEAR_GLYPH = 0x151
BACKGROUND_CLEAR_TILE = 0x2A1
assert BACKGROUND_CLEAR_GLYPH not in DYNAMIC_TARGET_CANDIDATES


def _source_records() -> tuple[list[dict], dict[int, str]]:
    """Extract the public script's record addresses and source strings."""
    source = ASM_SOURCE.read_text(encoding="utf-8")
    records: list[dict] = []
    style5: dict[int, str] = {}
    for style in (1, 2, 5):
        pattern = re.compile(
            rf"^\s*TextStyle{style}\(\$([0-9A-Fa-f]+),\s*\"([^\"]*)\"",
            re.MULTILINE,
        )
        for match in pattern.finditer(source):
            offset = int(match.group(1), 16)
            text = match.group(2)
            if style in (1, 2):
                records.append({"style": style, "offset": offset, "source": text})
            else:
                style5[offset] = text
    # The source contains one fixed name preceded by an origin/db line, so it
    # is not matched by the macro regex.  Its footprint is still explicit.
    style5.setdefault(0x41752, "CHAIN   ")
    existing = {r['offset'] for r in records}
    for offset in SUPPLEMENT:
        if int(offset, 16) in existing:
            continue
        r = BY_ROM_OFFSET[offset]
        records.append({'style': 2 if r['type'] == 7 else 1, 'offset': int(offset,16), 'source': r['japanese']})
    records.sort(key=lambda item: (item["offset"], item["style"]))
    return records, style5


def decompress(rom: bytes, start: int) -> tuple[bytes, int]:
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
            group = [
                sum(((group[x] >> (7 - y)) & 1) << (7 - x) for x in range(8))
                for y in range(8)
            ]
        out.extend(group)


def glyph(data: bytearray, index: int, image: Image.Image) -> None:
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
    src = Image.new("L", (16, 16), 0)
    ImageDraw.Draw(src).text((0, 0), ch, font=font, fill=255)
    src = src.resize((8, 16), Image.Resampling.LANCZOS)
    return src.point(lambda p: 3 if p >= 192 else (2 if p >= 80 else 1))


def korean_tile_bytes(image: Image.Image) -> bytes:
    """Pack one rendered glyph in the same interleaved row order as glyph()."""
    if image.size != (8, 16):
        raise ValueError(image.size)
    out = bytearray()
    for start in (0, 8):
        for y in range(start, start + 8):
            p0 = p1 = 0
            for x in range(8):
                value = image.getpixel((x, y))
                p0 |= (value & 1) << (7 - x)
                p1 |= ((value >> 1) & 1) << (7 - x)
            out.extend((p0, p1))
    return bytes(out)


def build_glyph_maps() -> tuple[dict[str, tuple[int, int]], dict]:
    from font_layout import allocate_slots
    table1, shared, groups, layout = allocate_slots(
        layout_source(), {**STYLE1_KO, **STYLE2_KO},
        {**STYLE5_KO, **{o: STYLE1_KO[o] for o in (0x413B5, 0x41866, 0x4186F, 0x41878)},
         **{-(i+1):s for i,s in enumerate(TERRAIN_LABELS+CACHED_UI_LABELS)}}, DYNAMIC_TARGET_CANDIDATES,
    )
    if len(table1) > FONT_RESERVED_SLOTS:
        raise ValueError("Hangul font exceeds the expanded 1,000-glyph store")
    # These table-2 characters have no remaining original pointer consumer.
    # Icons, punctuation, and the incomplete last DMA row are excluded.
    retained = [r for r in ALL_ROM_RECORDS if int(r['offset'],16) not in STYLE1_KO and int(r['offset'],16) not in STYLE2_KO]
    reused = {code-256 for code in DYNAMIC_TARGET_CANDIDATES if code>=256}
    assert not ({c for r in retained for c,a in r['pairs'] if a&1} & reused)
    assert not ({c for r in ALL_ROM_RECORDS if r['offset'] in REVIEW_FIXES['equipment']
                 for c,a in r['pairs'][:2] if a&1} & reused)
    mapping = {ch: (code & 255, code >> 8) for ch, code in table1.items()}
    mapping.update({ch: (code, 1) for ch, code in ASCII_TABLE2.items()})
    mapping.update({ch: (code, 0) for ch, code in ASCII_TABLE1.items()})
    return mapping, {
        "hangul_count": len(table1), "table1_hangul_count": sum(v<256 for v in table1.values()),
        "table2_hangul_count": sum(code>=256 for code in table1.values()), "extended_hangul_count": 0,
        "table1": {ch: f"0x{code:02X}" for ch, code in table1.items() if code<256},
        "table2": {ch: f"0x{code&255:02X}" for ch, code in table1.items() if code>=256}, "extended": {},
        "ascii_table1": {ch: f"0x{code:02X}" for ch, code in ASCII_TABLE1.items()},
        "ascii_table2": {ch: f"0x{code:02X}" for ch, code in ASCII_TABLE2.items()},
        "shared_glyphs": shared, "coexistence_groups": groups, "layout": layout,
    }


def encode_pairs(
    text: str,
    mapping: dict[str, tuple[int, int]],
    speaker: bool = False,
    dynamic_targets: dict[str, int] | None = None,
) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for index, ch in enumerate(text):
        try:
            code, table = mapping[ch]
        except KeyError as exc:
            raise ValueError(f"no glyph mapping for {ch!r} in {text!r}") from exc
        if dynamic_targets and ch in dynamic_targets:
            code, table = dynamic_targets[ch] & 255, dynamic_targets[ch] >> 8
        attr = table
        if speaker and index < text.index("「"):
            # Color the complete speaker name, including three-syllable names.
            attr = 0x0C | table
        pairs.append((code, attr))
    return pairs


def style2_blob(
    text: str,
    mapping: dict[str, tuple[int, int]],
    speaker: bool = False,
    dynamic_targets: dict[str, int] | None = None,
    prefix_pairs: tuple = (),
) -> bytes:
    pairs = list(prefix_pairs) + encode_pairs(
        text, mapping, speaker=speaker, dynamic_targets=dynamic_targets
    )
    if len(pairs) > 31:
        raise ValueError(f"TextStyle2 line exceeds 31 cells: {len(pairs)}: {text}")
    out = bytearray([0xE0 | len(pairs)])
    for code, attr in pairs:
        out.extend((code, attr))
    # The original parser consumes one pair beyond the counted body.
    out.extend((ASCII_TABLE1[" "], 0))
    return bytes(out)


def style5_blob(source: str, text: str, mapping: dict[str, tuple[int, int]]) -> bytes:
    pair_mode = len(source) % 2 == 0 and all(
        source[i + 1].isdigit() for i in range(0, len(source), 2)
    )
    if pair_mode:
        cells = len(source) // 2
        if len(text) > cells:
            raise ValueError(f"fixed pair name is too long: {text!r} > {cells}")
        out = bytearray()
        for ch in text:
            code, table = mapping[ch]
            out.extend((code, table))
        out.extend((ASCII_TABLE1[" "], 0) * (cells - len(text)))
        return bytes(out)
    cells = len(source)
    if len(text) > cells:
        raise ValueError(f"fixed name is too long: {text!r} > {cells}")
    out = bytearray()
    for ch in text:
        code, table = mapping[ch]
        if table != 0:
            raise ValueError(f"single-byte fixed name needs table-1 glyph: {ch!r}")
        out.append(code)
    out.extend(bytes((ASCII_TABLE1[" "],)) * (cells - len(text)))
    return bytes(out)


def lo_rom_address(offset: int) -> tuple[int, int]:
    return 0x80 + offset // 0x8000, 0x8000 + offset % 0x8000


def install_review_ui_fixes(rom, mapping):
    install_wide_dialogue_window(rom)
    # The equipment pane has eleven cells after moving its value column two
    # cells left. Keep complete translated names and both original icon cells.
    assert max(len(s)+2 for s in REVIEW_FIXES['equipment'].values()) <= 11
    assert rom[0x25F95:0x25F97] == bytes.fromhex('c0 18')
    rom[0x25F95:0x25F97] = bytes.fromhex('bc 18')
    assert rom[0x4E536:0x4E538] == bytes.fromhex('ce 01')
    rom[0x4E536:0x4E538] = bytes.fromhex('ca 01')
    for address in range(0x7910,0x7A20,4):
        if rom[address]==3 and 0xBE<=int.from_bytes(rom[address+2:address+4],'little')<=0xC3:
            rom[address]=2
    # Move the six equipment cursors and the selected-label tint with labels.
    for start,end,opcodes in ((0x25E30,0x25E54,(0x8D,)),
                              (0x25E99,0x25EA7,(0x9D,)),
                              (0x25ECE,0x25F05,(0x9D,0xBD))):
        for a in range(start,end):
            if rom[a] in opcodes:
                operand=int.from_bytes(rom[a+1:a+3],'little')
                if 0x1936<=operand<=0x1BF6:
                    rom[a+1:a+3]=(operand-2).to_bytes(2,'little')
    # These ten terrain cells are direct tile words, outside the text parser.
    original_terrain = (ROOT / 'Albert Odyssey.sfc').read_bytes()[0xA24:0xA74]
    assert original_terrain[14:16] == bytes.fromhex('06 26')
    assert original_terrain[34:36] == bytes.fromhex('20 26')
    for i,text in enumerate(TERRAIN_LABELS):
        for j,ch in enumerate(text.center(4)):
            code,table=mapping[ch]
            tile=(code//16)*32+code%16+table*512
            address=0xA24+i*8+j*2
            rom[address:address+2]=(tile|0x2400).to_bytes(2,'little')
    # Scripted scenes can override the automatic horizontal placement with a
    # Japanese-width constant. Clamp after the bubble tilemap has been drawn.
    out=bytearray(); labels={}; branches=[]
    def emit(*values): out.extend(values)
    def mark(name): labels[name]=len(out)
    def branch(op,name): branches.append((len(out)+1,name)); emit(op,0)
    emit(0x08,0xC2,0x30,0x48,0xA5,0x00,0x48) # PHP REP PHA; save scratch
    emit(0xA5,0x57,0x29,0xFF,0x00,0xC9,0x08,0x00)
    branch(0x90,'width')
    emit(0xA9,0x07,0x00)
    mark('width')
    emit(0x0A,0x0A,0x0A,0x0A,0x49,0xFF,0xFF,0x1A,0x18,0x69,0x78,0x00,0x85,0x00)
    emit(0xA5,0x30,0x29,0xFF,0x00,0xC9,0x80,0x00)
    branch(0xB0,'negative')
    emit(0xC5,0x00); branch(0x90,'done')
    emit(0xA5,0x00,0x85,0x30); branch(0x80,'done')
    mark('negative')
    emit(0xA9,0x00,0x01,0x38,0xE5,0x00,0x85,0x00)
    emit(0xA5,0x30,0x29,0xFF,0x00,0xC5,0x00); branch(0xB0,'done')
    emit(0xA5,0x00,0x85,0x30)
    mark('done')
    emit(0x68,0x85,0x00,0x68,0x28,0xE2,0x20,0xA5,0xE1,0x09,0x02,0x6B)
    for pos,name in branches:
        distance=labels[name]-pos-1
        assert -128<=distance<=127
        out[pos]=distance&255
    assert rom[0x13B7F:0x13B85]==bytes.fromhex('e2 20 a5 e1 09 02')
    bank,local=lo_rom_address(BUBBLE_CLAMP_OFFSET)
    rom[0x13B7F:0x13B85]=bytes((0x22,local&255,local>>8,bank,0xEA,0xEA))
    rom[BUBBLE_CLAMP_OFFSET:BUBBLE_CLAMP_OFFSET+len(out)]=out
    # The old English source map turns the repeated Japanese PM tiles into
    # "PP". Write distinct P/M tiles; the original time-number renderer follows.
    clock_pm=bytes.fromhex(
        'c2 30 a9 29 20 99 74 17 a9 39 20 99 b4 17 '
        'a9 26 20 99 76 17 a9 36 20 99 b6 17 5c e2 c9 84')
    assert rom[0x249A2:0x249A4]==bytes.fromhex('c2 30')
    bank,local=lo_rom_address(0x10B900)
    rom[0x249A2:0x249A7]=bytes((0x5C,local&255,local>>8,bank,0xEA))
    rom[0x10B900:0x10B900+len(clock_pm)]=clock_pm


def install_wide_dialogue_window(rom):
    """Handle width class 8 without reading beyond the original 0..7 tables.

    A 28..31-cell line selects class 8 at $82:BBFA. Use a full-width panel
    inside the existing 32 x 11 tile buffer. Text starts at column zero (the
    existing $E025+8 byte is zero), with no side tiles overwriting the text.
    Keep every original line/page/control pointer and all translated words.
    """
    draw_offset = 0x10BA00
    out = bytearray.fromhex('08 C2 30 48 DA A5 55 29 FF 00 C9 08 00')
    out.extend((0xD0, 0))
    fallback_branch = len(out)-1
    out.extend(bytes.fromhex('A2 BE 02 A9 48 20'))
    loop = len(out)
    out.extend(bytes.fromhex('9D B2 1C CA CA'))
    out.extend((0x10, (loop-len(out)-2)&255))
    out.extend(bytes.fromhex('A2 3E 00'))
    loop = len(out)
    out.extend(bytes.fromhex('A9 EA A2 9D B2 1C A9 EA 22 9D 32 1F CA CA'))
    out.extend((0x10, (loop-len(out)-2)&255))
    out.extend(bytes.fromhex('64 30 A9 20 00 85 32 E2 20 A5 E1 09 02 85 E1 C2 20 FA 68 28 6B'))
    out[fallback_branch] = len(out)-fallback_branch-1
    out.extend(bytes.fromhex('FA 68 28 08 C2 30 22 67 FD 89 5C 2E B9 82'))
    assert len(out) <= 0x80  # The tail handler occupies the next code block.
    assert rom[0x13927:0x1392E] == bytes.fromhex('08 C2 30 22 67 FD 89')
    rom[0x13927:0x1392E] = bytes.fromhex('5C 00 BA A1 EA EA EA')
    rom[draw_offset:draw_offset+len(out)] = out
    # Class 8 has no speech tail. The class-8 pointer in either of the old
    # tail tables is actually glyph/coordinate data, not a valid pointer.
    tail = bytes.fromhex('C2 30 A5 57 29 FF 00 C9 08 00 D0 0B 64 30 A9 20 00 85 32 5C 7F BB 82 A4 B7 5C 09 BB 82')
    assert rom[0x13B05:0x13B09] == bytes.fromhex('C2 30 A4 B7')
    rom[0x13B05:0x13B09] = bytes.fromhex('5C 80 BA A1')
    rom[0x10BA80:0x10BA80+len(tail)] = tail
    assert rom[0x602D] == 0
    # The battle/caption renderer starts at an explicit script column. If a
    # translated line would cross the 32-tile row, move its starting column
    # left. Count $04 includes the terminating blank, so all 31 visible cells
    # fit without writing the next row. Bubble rendering uses another path.
    caption = bytearray.fromhex('C2 20 98 29 3F 00 4A 18 65 04 C9 21 00 90 00')
    caption.extend(bytes.fromhex('98 29 C0 FF 48 A9 20 00 38 E5 04 0A 03 01 A8 68'))
    caption[14] = len(caption)-15
    caption.extend(bytes.fromhex('B2 06 5C D0 C0 82'))
    assert rom[0x140CC:0x140D0] == bytes.fromhex('C2 20 B2 06')
    rom[0x140CC:0x140D0] = bytes.fromhex('5C 00 BB A1')
    rom[0x10BB00:0x10BB00+len(caption)] = caption


def _dynamic_font_code() -> bytes:
    """Return the 65816 routine that installs one line's dynamic glyphs.

    A map entry supplies the patch bank in DB, its local address in A, and the number of
    four-byte ``target table-1 code / A0 source address`` pairs in X. The routine
    copies each 8x16 2bpp glyph from the A0 store into VRAM's normal font page at
    the target table-1 tile.  All registers, DB and DP are restored before
    returning, so the three parser call sites can share the same routine.
    """
    out = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str]] = []

    def emit(*values: int) -> None:
        out.extend(values)

    def label(name: str) -> None:
        labels[name] = len(out)

    def branch(opcode: int, target: str) -> None:
        fixups.append((len(out) + 1, target))
        emit(opcode, 0)

    emit(0x08, 0xC2, 0x30, 0xDA, 0x5A, 0x8B, 0x0B)  # PHP REP PHX PHY PHB PHD
    emit(0xA8, 0xA9, 0x00, 0x00, 0x5B)  # TAY; D=0
    emit(
        0xA5, 0x1C, 0x48, 0xA5, 0x1E, 0x48,
        0xA5, 0x20, 0x48, 0xA5, 0x22, 0x48,
    )
    emit(0x98, 0x85, 0x1E, 0x8A, 0x85, 0x1C)  # incoming A/X
    # VRAM is writable only during VBlank on the real hardware.  The parser
    # can be entered at any scanline, so wait until a VBlank window is active
    # before touching $2118/$2119.  If an earlier text record in the same
    # menu redraw already entered the window, keep using that window instead
    # of discarding it and forcing every cursor step to wait an extra frame.
    label("wait_vblank")
    emit(0xE2, 0x20)  # A=8-bit for the PPU status reads below
    label("wait_set")
    emit(0xAD, 0x12, 0x42)
    branch(0x10, "wait_set")  # BPL until the next VBlank starts
    # Reusing an active VBlank is safe only with room for the complete batch.
    # Latch the beam and accept lines below 248 (at least 14 NTSC lines left).
    # Otherwise wait for the next window. This avoids both late partial writes
    # and an unconditional extra frame for every menu item.
    emit(0xAD, 0x3F, 0x21, 0xAD, 0x37, 0x21, 0xAD, 0x3D, 0x21)
    emit(0xC9, 0xF8)
    branch(0xB0, "wait_clear")
    emit(0xAD, 0x3D, 0x21, 0x29, 0x01)
    branch(0xF0, "safe_window")
    label("wait_clear")
    emit(0xAD, 0x12, 0x42)
    branch(0x30, "wait_clear")
    branch(0x80, "wait_set")
    label("safe_window")
    emit(0xA9, 0x80, 0x8D, 0x15, 0x21)  # VMAIN=$80
    emit(0xC2, 0x20)  # caller supplies patch-table DB; A/X 16-bit
    label("outer")
    emit(0xAE, 0x1E, 0x00)  # X = patch-table cursor
    emit(0xBD, 0x00, 0x00, 0x85, 0x20)  # target code (word)
    # Target VMADD = $4000 + (code//16)*$100 + (code%16)*8.
    emit(0x29, 0x0F, 0x00, 0x0A, 0x0A, 0x0A, 0x85, 0x22)
    emit(0xA5, 0x20, 0x29, 0xFF, 0x01)
    emit(0x4A, 0x4A, 0x4A, 0x4A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A)
    emit(0x18, 0x65, 0x22, 0x18, 0x69, 0x00, 0x40, 0x85, 0x22)
    # Full 16-bit source address: no 256-glyph index truncation.
    emit(0xE8, 0xE8, 0xBD, 0x00, 0x00, 0xE8, 0xE8, 0x8E, 0x1E, 0x00, 0xAA)
    emit(0xA5, 0x22, 0x8D, 0x16, 0x21)
    # Fixed-size glyphs need no per-row loop or source-index increments.
    # Keep the same VBlank boundary and four-glyph limit, with less work
    # inside each window. X remains the start of this glyph's ROM pixels.
    for offset in range(0, 16, 2):
        emit(0xBF, offset, 0x00, 0xA0, 0x8D, 0x18, 0x21)
    emit(0xA5, 0x22, 0x18, 0x69, 0x80, 0x00, 0x8D, 0x16, 0x21)
    for offset in range(16, 32, 2):
        emit(0xBF, offset, 0x00, 0xA0, 0x8D, 0x18, 0x21)
    emit(0xCE, 0x1C, 0x00)
    branch(0xF0, "copies_done")
    # Recheck the remaining VBlank time after at most four glyphs.
    emit(0xA5, 0x1C, 0x29, 0x03, 0x00)
    branch(0xF0, "recheck_window")
    displacement = labels["outer"] - (len(out) + 3)
    emit(0x82, displacement & 0xFF, (displacement >> 8) & 0xFF)
    label("recheck_window")
    displacement = labels["wait_vblank"] - (len(out) + 3)
    emit(0x82, displacement & 0xFF, (displacement >> 8) & 0xFF)
    label("copies_done")
    # The game normally leaves VMAIN in its tile-map increment mode.  Restore
    # that mode after the temporary font writes so a scene upload immediately
    # following dialogue cannot inherit the glyph-copy setting.
    emit(0xE2, 0x20, 0xA9, 0x00, 0x8D, 0x15, 0x21, 0xC2, 0x20)
    label("done")
    emit(
        0x68, 0x85, 0x22, 0x68, 0x85, 0x20,
        0x68, 0x85, 0x1E, 0x68, 0x85, 0x1C,
        0x2B, 0xAB, 0x7A, 0xFA, 0x28, 0x6B,
    )
    for position, target in fixups:
        displacement = labels[target] - (position + 1)
        if not -128 <= displacement <= 127:
            raise ValueError((target, displacement))
        out[position] = displacement & 0xFF
    return bytes(out)


def _font_stream_code() -> bytes:
    out = bytearray()
    labels, fixups = {}, []
    def emit(h): out.extend(bytes.fromhex(h))
    def label(n): labels[n] = len(out)
    def branch(op, n):
        fixups.append((len(out)+1,n));out.extend((op,0))
    emit("08 C2 30 DA 5A A5 02 29 FF 00 C9 99 00")
    branch(0xD0,"fallback")
    emit("A5 00 C9 00 80");branch(0xF0,"part0")
    emit("C9 F6 8B");branch(0xF0,"part1")
    emit("C9 A7 97");branch(0xF0,"part2")
    label("fallback")
    emit("7A FA 28 22 28 8C 82 6B")
    for i,(start,end,count) in enumerate(BLOCKS):
        label(f"part{i}")
        x=i*0x1000
        emit(f"A2 {x&255:02X} {x>>8:02X} A0 {count&255:02X} {count>>8:02X}")
        _,end_addr=lo_rom_address(end)
        emit(f"A9 {end_addr&255:02X} {end_addr>>8:02X} 85 00")
        branch(0x80,"copy")
    label("copy")
    emit("E2 20 A5 06 29 01 8D 83 21 A5 05 8D 82 21 A5 04 8D 81 21")
    label("byte")
    emit("BF 00 80 A1 8D 80 21 E8 88");branch(0xD0,"byte")
    emit("A9 01 7A FA 28 6B")
    for at,n in fixups:
        delta=labels[n]-(at+1)
        assert -128<=delta<=127
        out[at]=delta&255
    assert len(out)<0x100
    return bytes(out)


def install_font_overlay(
    rom: bytearray, font_data: bytes, table2_data: bytes, ext_data: bytes
) -> int:
    if len(font_data) != FONT_OVERLAY_SIZE:
        raise ValueError(len(font_data))
    if len(table2_data) != TABLE2_FONT_SIZE:
        raise ValueError(len(table2_data))
    if len(ext_data) != EXT_FONT_SIZE:
        raise ValueError(len(ext_data))
    data_bank, data_addr = lo_rom_address(FONT_OVERLAY_OFFSET)
    code_bank, code_addr = lo_rom_address(FONT_OVERLAY_CODE_OFFSET)
    ext_bank, ext_addr = lo_rom_address(EXT_FONT_OFFSET)
    ext_code_bank, ext_code_addr = lo_rom_address(EXT_FONT_CODE_OFFSET)
    table2_bank, table2_addr = lo_rom_address(TABLE2_FONT_OFFSET)
    if (data_bank, data_addr) != (0xA1, 0x8000):
        raise ValueError((hex(data_bank), hex(data_addr)))
    if (code_bank, code_addr) != (0xA1, 0xB000):
        raise ValueError((hex(code_bank), hex(code_addr)))
    if (ext_bank, ext_addr) != (0xA1, 0xF000):
        raise ValueError((hex(ext_bank), hex(ext_addr)))
    if (ext_code_bank, ext_code_addr) != (0xA1, 0xB400):
        raise ValueError((hex(ext_code_bank), hex(ext_code_addr)))
    if (table2_bank, table2_addr) != (0xA1, 0xE000):
        raise ValueError((hex(table2_bank), hex(table2_addr)))

    rom[FONT_OVERLAY_OFFSET : FONT_OVERLAY_OFFSET + len(font_data)] = font_data
    rom[TABLE2_FONT_OFFSET : TABLE2_FONT_OFFSET + len(table2_data)] = table2_data
    rom[EXT_FONT_OFFSET : EXT_FONT_OFFSET + len(ext_data)] = ext_data
    ext_code = _dynamic_font_code()
    rom[EXT_FONT_CODE_OFFSET : EXT_FONT_CODE_OFFSET + len(ext_code)] = ext_code
    # $828C28 is a GENERAL WRAM decompressor, also used by spell graphics.
    # Replace only the three known font streams, in their original WRAM
    # destination. Let the original game perform its later VRAM DMA. Never
    # change PPU or DMA registers for unrelated compressed resources.
    code = _font_stream_code()
    rom[FONT_OVERLAY_CODE_OFFSET : FONT_OVERLAY_CODE_OFFSET + len(code)] = code
    hook = bytes((0x22, code_addr & 0xFF, code_addr >> 8, code_bank))
    original_call = bytes.fromhex("22 28 8C 82")
    hooks = 0
    for offset in range(FONT_OVERLAY_CODE_OFFSET):
        if rom[offset : offset + 4] == original_call:
            rom[offset : offset + 4] = hook
            hooks += 1
    if hooks != 48:
        raise ValueError(f"unexpected decompressor hook count: {hooks}")
    return hooks


def _wrapper_code(entry_count: int, pointer_dp: int, parser_call: bytes) -> bytes:
    """Assemble a pointer lookup wrapper for one of the text parsers."""
    if not 0 < entry_count <= 0x3FFF:
        raise ValueError(entry_count)
    if not 0 <= pointer_dp <= 0xFF or len(parser_call) != 4:
        raise ValueError((pointer_dp, parser_call))
    ext_code_bank, ext_code_addr = lo_rom_address(EXT_FONT_CODE_OFFSET)
    out = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str]] = []

    def label(name: str) -> None:
        labels[name] = len(out)

    def branch(opcode: int, target: str) -> None:
        fixups.append((len(out) + 1, target))
        out.extend((opcode, 0))

    # Preserve the caller's registers. The parser deliberately leaves the
    # data bank at $7E when it returns because the caller immediately uses
    # the WRAM-backed dialogue buffer. Do not save/restore DB around the
    # parser call: doing so makes the dialogue window render as blank lines.
    # The lookup table retains every original pointer so resource users of
    # the same table are safe.
    # Keep two copies of the caller's X/Y.  One copy is restored immediately
    # before the original parser runs (the parser uses the caller's register
    # context on real Snes9x), and the second copy is restored after it
    # returns.  The former implementation restored them only after the call;
    # libretro happened to tolerate that, while Snes9x rendered a tiled
    # garbage screen for the opening caption and a subset of later lines.
    out.extend(
        bytes.fromhex("08 C2 30 DA 5A DA 5A A5")
        + bytes((pointer_dp,))
        + bytes.fromhex("C9 00 80")
    )
    branch(0x90, "not_found")
    out.extend(bytes.fromhex('C9 00 C0'))
    branch(0xB0, 'index_high')
    out.extend(bytes.fromhex('29 FF 3F 0A AA BF 00 80 B0'))
    branch(0x80, 'index_loaded')
    label('index_high')
    out.extend(bytes.fromhex('29 FF 3F 0A AA BF 00 80 B1'))
    label('index_loaded')
    branch(0xF0, 'not_found')
    out.extend(bytes.fromhex('3A AA'))  # stored map byte offset + 1; zero is absent
    branch(0x80, 'found')
    label('not_found')
    # No translated entry: preserve the original parser call and return.
    out.extend(bytes.fromhex("7A FA") + parser_call + bytes.fromhex("7A FA 28 6B"))
    label("found")
    out.extend(bytes.fromhex("BF 02 80 A4 85") + bytes((pointer_dp,)))
    # Fixed-slot menu labels need only a text bank and the original parser.
    # Do not set up a patch bank, push a patch pointer, and unwind it again
    # for the zero-copy case. This branch uses no additional RAM or cache.
    out.extend(bytes.fromhex("BF 06 80 A4"))
    branch(0xD0, "dynamic_entry")
    out.extend(bytes.fromhex("E2 20 BF 08 80 A4 48 AB C2 30 7A FA"))
    out.extend(parser_call)
    out.extend(bytes.fromhex("7A FA 28 6B"))
    label("dynamic_entry")
    # The original boot-time font DMA already leaves the table-2 page at
    # VRAM $A000. Shared Korean table-1 glyphs are restored by the
    # per-record patch list below, so issuing another DMA here only
    # races the title/scene VRAM work on real Snes9x and tiles the screen.
    # Keep the page untouched and continue with the dynamic table-1 copy.
    out.extend(bytes.fromhex("C2 30"))  # restore 16-bit A/X before dynamic copy
    # Save the map entry's patch-table pointer before TAX consumes X for the
    # pair count.  The previous order loaded the count first, so X no longer
    # pointed at the found entry when BF $A1D204,X ran; dynamic calls then read
    # unrelated bytes (which rendered the reserved 0x40/0x41 glyphs as 베/변).
    # Preserve the text bank across the dynamic copy, then select the bank
    # containing this record's patch list. Both pools can cross LoROM banks.
    out.extend(bytes.fromhex("BF 08 80 A4 48 E2 20 BF 0A 80 A4 48 AB C2 30"))
    out.extend(bytes.fromhex("BF 04 80 A4 48 BF 06 80 A4 AA E0 00 00"))
    branch(0xF0, "drop_patch")
    out.extend(bytes.fromhex("68"))  # restore patch address for the JSL
    out.extend(bytes.fromhex(
        f"22 {ext_code_addr & 0xFF:02X} {ext_code_addr >> 8:02X} {ext_code_bank:02X}"
    ))
    branch(0x80, "after_dynamic")
    label("drop_patch")
    out.extend(bytes.fromhex("68"))  # count was zero; discard saved pointer
    label("no_dynamic")
    label("after_dynamic")
    out.extend(bytes.fromhex("68 E2 20 48 AB"))  # saved text bank -> DB
    out.extend(bytes.fromhex("7A FA"))  # restore caller X/Y before the parser
    out.extend(parser_call)
    branch(0x80, "done")  # BRA
    label("done")
    out.extend(bytes.fromhex("7A FA 28 6B"))
    for position, target in fixups:
        displacement = labels[target] - (position + 1)
        if not -128 <= displacement <= 127:
            raise ValueError((target, displacement))
        out[position] = displacement & 0xFF
    return bytes(out)


def install_text_hook(rom: bytearray, pointer_entries: list[tuple[int, ...]]) -> int:
    # A linear scan of 1,428 entries used to run for every menu label/redraw.
    # Resolve the original bank-$88 pointer in constant time, entirely in ROM.
    # No RAM cache or invalidation state can collide with game memory or saves.
    index = bytearray(0x10000)
    for i, entry in enumerate(pointer_entries):
        pointer = entry[0]
        assert 0x8000 <= pointer <= 0xffff
        p = (pointer-0x8000)*2
        assert index[p:p+2] == bytes(2)
        index[p:p+2] = (i*TEXT_MAP_ENTRY_SIZE+1).to_bytes(2,'little')
    assert DYNAMIC_PATCH_END <= TEXT_DIRECT_INDEX_OFFSET
    assert TEXT_DIRECT_INDEX_OFFSET+len(index) <= len(rom)
    assert set(rom[TEXT_DIRECT_INDEX_OFFSET:TEXT_DIRECT_INDEX_OFFSET+len(index)]) <= {0,255}
    rom[TEXT_DIRECT_INDEX_OFFSET:TEXT_DIRECT_INDEX_OFFSET+len(index)] = index
    map_bank, map_addr = lo_rom_address(TEXT_MAP_OFFSET)
    if (map_bank, map_addr) != (0xA4, 0x8000):
        raise ValueError((hex(map_bank), hex(map_addr)))
    specs = [
        (TEXT_HOOK_OFFSET, 0x00, bytes.fromhex("22 63 F8 84"), 11),
        (TEXT_HOOK_F71D_OFFSET, 0x06, bytes.fromhex("22 1D F7 84"), 1),
        (TEXT_HOOK_F7C0_OFFSET, 0x0E, bytes.fromhex("22 C0 F7 84"), 1),
    ]
    total_hooks = 0
    for code_offset, pointer_dp, parser_call, expected in specs:
        code_bank, code_addr = lo_rom_address(code_offset)
        wrapper = _wrapper_code(len(pointer_entries), pointer_dp, parser_call)
        if code_bank != 0xA1:
            raise ValueError((hex(code_bank), hex(code_addr)))
        rom[code_offset : code_offset + len(wrapper)] = wrapper
        hook = bytes((0x22, code_addr & 0xFF, code_addr >> 8, code_bank))
        hooks = 0
        for offset in range(FONT_OVERLAY_CODE_OFFSET):
            if rom[offset : offset + 4] == parser_call:
                rom[offset : offset + 4] = hook
                hooks += 1
        if hooks != expected:
            raise ValueError((parser_call.hex(), hooks, expected))
        total_hooks += hooks
    map_bytes = b"".join(
        original.to_bytes(2, "little")
        + translated.to_bytes(2, "little")
        + patch_address.to_bytes(2, "little")
        + bytes((pair_count, 0, text_bank, 0, patch_bank, 0))
        for original, translated, patch_address, pair_count, text_bank, patch_bank in pointer_entries
    )
    assert len(map_bytes) <= 0x8000, "pointer map exceeds bank A4"
    rom[TEXT_MAP_OFFSET : TEXT_MAP_OFFSET + len(map_bytes)] = map_bytes
    return total_hooks


def update_checksum(rom: bytearray) -> None:
    rom[0x7FDC:0x7FE0] = b"\x00\x00\x00\x00"
    # Snes9x validates this title by summing the complete ROM image,
    # including the four checksum bytes themselves.  Solve that small
    # fixed-point equation instead of recording the sum with the fields
    # cleared; the latter is accepted by some cores but reported as
    # ``Invalid Checksum`` by the Windows Snes9x build.
    base_sum = sum(rom) & 0xFFFF
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
    else:  # pragma: no cover - the byte-sum equation converges immediately
        raise ValueError("checksum fixed point did not converge")
    complement = checksum ^ 0xFFFF
    rom[0x7FDC:0x7FDE] = complement.to_bytes(2, "little")
    rom[0x7FDE:0x7FE0] = checksum.to_bytes(2, "little")


def _png_bytes(image: Image.Image) -> bytes:
    import io

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def export_glyph_sheet(mapping_meta: dict, font: ImageFont.FreeTypeFont) -> None:
    items = []
    for bank_name in ("table1", "table2", "extended"):
        for ch, code in mapping_meta[bank_name].items():
            items.append((ch, bank_name, int(code, 16)))
    columns = 18
    rows = (len(items) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 54, max(1, rows) * 90), "#121830")
    draw = ImageDraw.Draw(sheet)
    for index, (ch, bank, code) in enumerate(items):
        im = korean_glyph(ch, font).convert("L").resize((32, 64), Image.Resampling.NEAREST)
        rgb = Image.new("RGB", im.size, "black")
        rgb.paste("white", mask=im.point(lambda p: 255 if p > 1 else 0))
        x = (index % columns) * 54 + 8
        y = (index // columns) * 90 + 3
        sheet.paste(rgb, (x, y))
        draw.text((x, y + 66), f"{ch} {bank[0].upper()}{code:02X}", fill="#f6f1dd")
    (OUT_DIR / "korean_full_glyphs.png").write_bytes(_png_bytes(sheet))


def main() -> None:
    base = BASE.read_bytes()
    if len(base) != 0x200000:
        raise ValueError(f"unexpected expanded ROM size: {len(base):#x}")
    rom = bytearray(base)
    source_records, style5_source = _source_records()
    if set(STYLE1_KO) != {r["offset"] for r in source_records if r["style"] == 1}:
        raise ValueError("TextStyle1 translation coverage mismatch")
    if set(STYLE2_KO) != {r["offset"] for r in source_records if r["style"] == 2}:
        raise ValueError("TextStyle2 translation coverage mismatch")
    if not set(style5_source).issubset(STYLE5_KO):
        raise ValueError("TextStyle5 translation coverage mismatch")

    mapping, mapping_meta = build_glyph_maps()
    font_path = Path("C:/Windows/Fonts/gulim.ttc")
    font = ImageFont.truetype(str(font_path), 16)
    dynamic_chars = mapping_meta["shared_glyphs"]
    dynamic_glyph_index = {ch: index for index, ch in enumerate(dynamic_chars)}
    dynamic_glyph_data = b"".join(
        korean_tile_bytes(korean_glyph(ch, font)) for ch in dynamic_chars
    )
    if len(dynamic_glyph_data) > FONT_RESERVED_SIZE:
        raise ValueError("dynamic glyph store exceeds the 1,024-slot reserved area")
    parts: list[bytes] = []
    for start, end, expected in BLOCKS:
        part, actual_end = decompress(base, start)
        if (actual_end, len(part)) != (end, expected):
            raise ValueError((hex(start), hex(actual_end), len(part)))
        parts.append(part)
    font_data = bytearray(b"".join(parts))
    if len(font_data) != FONT_OVERLAY_SIZE:
        raise ValueError(f"unexpected decompressed font size: {len(font_data):#x}")
    # Keep the original table-2 cells in the boot-time font so the title
    # screen remains untouched.  The expanded glyph store is copied per line
    # into table-1 slots immediately before the parser runs.
    table2_data = bytearray(font_data[0x2000:0x2F80])
    table2_data.extend(b"\0" * (TABLE2_FONT_SIZE - len(table2_data)))
    ext_data = bytearray(EXT_FONT_SIZE)
    for ch, code_text in mapping_meta["table1"].items():
        glyph(font_data, int(code_text, 16), korean_glyph(ch, font))
    for ch, code_text in mapping_meta["table2"].items():
        glyph(table2_data, int(code_text, 16), korean_glyph(ch, font))
        glyph(font_data, 0x100 + int(code_text, 16), korean_glyph(ch, font))
    clear_offset=BACKGROUND_CLEAR_TILE*16
    assert font_data[clear_offset:clear_offset+16] == bytes(16), 'Background clear tile must stay transparent'
    for ch, code_text in mapping_meta["extended"].items():
        glyph(ext_data, int(code_text, 16) - 0x80, korean_glyph(ch, font))

    font_hooks = install_font_overlay(
        rom, bytes(font_data), bytes(table2_data), bytes(ext_data)
    )

    # Place translated pointer records into the expanded multi-bank pool. The
    # original pointer table stays byte-for-byte intact; the parser wrapper
    # performs an address lookup only when a text record is requested.
    pointer_values: dict[int, list[int]] = {}
    for index in range((POINTER_TABLE_END - POINTER_TABLE_OFFSET) // 2):
        value = int.from_bytes(
            base[POINTER_TABLE_OFFSET + index * 2 : POINTER_TABLE_OFFSET + index * 2 + 2],
            "little",
        )
        pointer_values.setdefault(value, []).append(index)

    pool = bytearray()
    patch_data = bytearray()
    local_addresses: list[int] = []
    pointer_entries: list[tuple[int, ...]] = []
    translated_records: list[dict] = []
    for record_id, record in enumerate(source_records):
        offset = record["offset"]
        pointer = 0x8000 + (offset % 0x8000)
        indices = pointer_values.get(pointer, [])
        if len(indices) != 1:
            raise ValueError((hex(offset), hex(pointer), indices))
        if record["style"] == 1:
            text = STYLE1_KO[offset]
            speaker = False
        else:
            text = STYLE2_KO[offset]
            speaker = "「" in text
        dynamic_for_record = sorted(
            {ch for ch in text if ch in dynamic_glyph_index}
        )
        dynamic_targets = {ch: mapping[ch][0] + 256*mapping[ch][1] for ch in dynamic_for_record}
        prefix = BY_ROM_OFFSET[f'0x{offset:05X}']['pairs'][:2] if f'0x{offset:05X}' in REVIEW_FIXES['equipment'] else []
        blob = style2_blob(
            text, mapping, speaker=speaker, dynamic_targets=dynamic_targets, prefix_pairs=prefix
        )
        # Window sizing reads the original record's low five header bits
        # before the relocated parser hook runs. Keep that measurement in
        # sync with VISIBLE Korean cells. The terminator is not visible text:
        # counting it can overflow the window's five-bit width field (e.g.
        # the 27-cell farewell at $44ECE), corrupting the window copy loop.
        rom[offset] = (base[offset] & 0xE0) | max(0, len(text) + len(prefix) - 1)
        # Keep each individual record inside one LoROM bank; a following
        # record may use the next bank through its explicit map bank byte.
        if (len(pool) & 0x7FFF) + len(blob) > 0x8000:
            pool.extend(b"\xFF" * (0x8000 - (len(pool) & 0x7FFF)))
        pool_offset = len(pool)
        if TEXT_POOL_OFFSET + pool_offset + len(blob) > TEXT_POOL_END:
            raise ValueError("translated text pool exceeds its expanded-ROM pool area")
        pool.extend(blob)
        text_bank, local = lo_rom_address(TEXT_POOL_OFFSET + pool_offset)
        if local + len(blob) > 0x10000:
            raise ValueError("translated text pool crossed bank boundary")
        local_addresses.append(local)
        patch_size = len(dynamic_for_record) * 4
        if (len(patch_data) & 0x7FFF) + patch_size > 0x8000:
            patch_data.extend(b"\xFF" * (0x8000 - (len(patch_data) & 0x7FFF)))
        patch_bank, patch_address = lo_rom_address(DYNAMIC_PATCH_OFFSET + len(patch_data))
        for ch in dynamic_for_record:
            patch_data.extend(dynamic_targets[ch].to_bytes(2, "little"))
            patch_data.extend((0x8000 + dynamic_glyph_index[ch] * 32).to_bytes(2, "little"))
        if patch_address + len(dynamic_for_record) * 4 > 0x10000:
            raise ValueError("individual dynamic remap list crossed a bank window")
        if DYNAMIC_PATCH_OFFSET + len(patch_data) > DYNAMIC_PATCH_END:
            raise ValueError("dynamic remap pool capacity exceeded")
        pointer_entries.append(
            (pointer, local, patch_address, len(dynamic_for_record), text_bank, patch_bank)
        )
        translated_records.append(
            {
                "id": record_id,
                "style": record["style"],
                "offset": f"0x{offset:05X}",
                "pointer_index": indices[0],
                "original_pointer": f"0x{pointer:04X}",
                "source": record["source"],
                "korean": text,
                "speaker": speaker,
                "pool_offset": pool_offset,
                "pool_address": f"0x{local:04X}",
                "pool_bank": f"0x{text_bank:02X}",
                "patch_bank": f"0x{patch_bank:02X}",
                "length_cells": len(text) + len(prefix),
                "prefix_pairs": prefix,
                "pool_bytes": len(blob),
                "dynamic_glyphs": dynamic_for_record,
                "dynamic_targets": {
                    ch: f"0x{dynamic_targets[ch]:02X}"
                    for ch in dynamic_for_record
                },
            }
        )
    rom[TEXT_POOL_OFFSET : TEXT_POOL_OFFSET + len(pool)] = pool
    rom[DYNAMIC_GLYPH_OFFSET : DYNAMIC_GLYPH_OFFSET + len(dynamic_glyph_data)] = dynamic_glyph_data
    rom[DYNAMIC_PATCH_OFFSET : DYNAMIC_PATCH_OFFSET + len(patch_data)] = patch_data
    text_hooks = install_text_hook(rom, pointer_entries)
    # TextStyle3/4 consumers embed tile words in code/data and never call the
    # dialogue wrapper. Reapply their explicit source-map ASCII labels against
    # the preserved ASCII font slots (HP, STP, coordinates, terrain/status).
    direct_labels = 0
    direct_pattern = re.compile(
        r"TextStyle([34])\(\$([0-9A-Fa-f]+),\s*('[^']'|\$[0-9A-Fa-f]+),"
        r"\s*\$([0-9A-Fa-f]+),\s*\$([0-9A-Fa-f]+)(?:,\s*\$([0-9A-Fa-f]+))?\)"
    )
    for match in direct_pattern.finditer(ASM_SOURCE.read_text(encoding="utf-8")):
        style, address, char, attr, subtract, lower = match.groups()
        address, attr, subtract = int(address, 16), int(attr, 16), int(subtract, 16)
        value = ord(char[1]) if char.startswith("'") else int(char[1:], 16)
        value -= subtract
        tile = value + 16 * (value // 16)
        rom[address:address + 2] = bytes((tile & 0xFF, attr))
        if style == "3":
            lower_address = address + int(lower, 16)
            rom[lower_address:lower_address + 2] = bytes(((tile + 16) & 0xFF, attr))
        direct_labels += 1

    # Fixed item/equipment names have no pointer header.  Preserve each source
    # footprint and pad with spaces; all Korean item glyphs were placed in
    # table 1 so both one-byte and pair-style name readers remain compatible.
    for offset, source in style5_source.items():
        text = STYLE5_KO[offset]
        blob = style5_blob(source, text, mapping)
        rom[offset : offset + len(blob)] = blob

    rom[0x7FC0 : 0x7FC0 + 21] = b"ALBERT ODYSSEY KOR   "[:21]
    install_review_ui_fixes(rom, mapping)
    update_checksum(rom)
    ROM_OUT.write_bytes(rom)

    dialogue_export = {
        "source_rom": "Albert Odyssey.sfc",
        "source_script": ASM_SOURCE.name,
        "records": translated_records,
        "fixed_names": [
            {
                "style": 5,
                "offset": f"0x{offset:05X}",
                "source": source,
                "korean": STYLE5_KO[offset],
                "footprint_bytes": len(style5_blob(source, STYLE5_KO[offset], mapping)),
            }
            for offset, source in style5_source.items()
        ],
    }
    (ROOT / "analysis" / "full_dialogue_extracted.json").write_text(
        json.dumps(dialogue_export, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "analysis" / "full_dialogue_translations.json").write_text(
        json.dumps(dialogue_export, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lengths = [item["length_cells"] for item in translated_records]
    audit = {
        "source_sha256": hashlib.sha256((ROOT / "Albert Odyssey.sfc").read_bytes()).hexdigest(),
        "base_sha256": hashlib.sha256(base).hexdigest(),
        "output_sha256": hashlib.sha256(rom).hexdigest(),
        "output": ROM_OUT.name,
        "output_size": len(rom),
        "style1_records": sum(item["style"] == 1 for item in translated_records),
        "style2_records": sum(item["style"] == 2 for item in translated_records),
        "style5_records": len(style5_source),
        "translated_pointer_records": len(translated_records),
        "max_cells_per_record": max(lengths),
        "records_over_31_cells": [item["offset"] for item in translated_records if item["length_cells"] > 31],
        "pool_offset": f"0x{TEXT_POOL_OFFSET:06X}",
        "pool_size": len(pool),
        "pool_end": f"0x{TEXT_POOL_OFFSET + len(pool):06X}",
        "pool_capacity": TEXT_POOL_END - TEXT_POOL_OFFSET,
        "font_reserved_offset": f"0x{FONT_RESERVED_OFFSET:06X}",
        "font_reserved_size": FONT_RESERVED_SIZE,
        "font_reserved_glyph_slots": FONT_RESERVED_SLOTS,
        "font_reserved_glyph_bytes": FONT_GLYPH_BYTES,
        "font_main_offset": f"0x{FONT_OVERLAY_OFFSET:06X}",
        "font_main_size": FONT_OVERLAY_SIZE,
        "font_extended_offset": f"0x{EXT_FONT_OFFSET:06X}",
        "font_extended_size": EXT_FONT_SIZE,
        "font_table2_overlay_offset": f"0x{TABLE2_FONT_OFFSET:06X}",
        "font_table2_overlay_size": TABLE2_FONT_SIZE,
        "font_table2_vram_bytes": "0xA000-0xAFFF; reserved icons preserved, selected cells support VBlank-synchronized dynamic copies",
        "font_extended_vram_bytes": "export only; rendering uses table-1 and reclaimed table-2 slots within the original font region",
        "dynamic_glyph_store_offset": f"0x{DYNAMIC_GLYPH_OFFSET:06X}",
        "dynamic_glyph_store_size": len(dynamic_glyph_data),
        "dynamic_patch_table_offset": f"0x{DYNAMIC_PATCH_OFFSET:06X}",
        "dynamic_patch_table_size": len(patch_data),
        "dynamic_patch_pool_capacity": DYNAMIC_PATCH_END - DYNAMIC_PATCH_OFFSET,
        "font_layout": mapping_meta["layout"],
        "dynamic_patch_entry_bytes": 4,
        "text_map_entry_size": TEXT_MAP_ENTRY_SIZE,
        "text_direct_index": {"offset": hex(TEXT_DIRECT_INDEX_OFFSET), "size": 0x10000,
                              "entries": 0x8000, "ram_bytes": 0},
        "font_hooks": font_hooks,
        "text_hooks": text_hooks,
        "direct_tile_labels": direct_labels,
        "review_fixes": {"records": {k:len(v) for k,v in REVIEW_FIXES.items()},
                         "reserved_background_clear_tile": "0x2A1",
                         "reserved_background_glyph": "0x151",
                         "terrain_labels": TERRAIN_LABELS,
                         "equipment_cells_including_icon": 11,
                         "pm_time_label_hook": "0x249A2",
                         "bubble_clamp_hook": "0x13B7F",
                         "bubble_clamp_code": f"0x{BUBBLE_CLAMP_OFFSET:06X}"},
        "glyphs": mapping_meta,
        "rules": {
            "translated_line_unit": "one source TextStyle1/2 record remains one Korean line",
            "textstyle2_capacity_cells": 31,
            "terminator_pair": "space + table-1 attr 0",
            "speaker_prefix": "all cells before the Korean opening quote use the speaker color",
            "table1": "original digits/letters/punctuation retained; Hangul fills unused slots",
            "table2": "attribute bit 0 selects the original second table",
            "table2_overlay": "icons and retained original pointer consumers are excluded from reclaimed slots; dynamic targets carry a 9-bit table/code index",
            "dynamic_hangul": "Every shared-slot glyph is restored on each use from the A0 1,000-glyph ROM store; entries use 16-bit source addresses",
            "dynamic_target_pools": "Global graph coloring protects script scenes, menu/equipment/inventory coexistence and six-record windows; fixed names, terrain and cached UI have exclusive slots",
            "extended_page": "the expanded ROM keeps an export copy of the remaining Hangul; no scene/sprite VRAM page is occupied by it",
            "fixed_names": "TextStyle5 fallback footprints retained; reviewed equipment pointer records are relocated with full names and original icon pairs",
        },
    }
    (OUT_DIR / "korean_full_patch_info.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    export_glyph_sheet(mapping_meta, font)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
