"""Read release bytes back independently; never starts an emulator."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'font_export'))
import build_korean_full_patch as b

rom = b.ROM_OUT.read_bytes()
original = (ROOT / 'Albert Odyssey.sfc').read_bytes()
records = json.loads((ROOT / 'analysis/full_dialogue_extracted.json').read_text(encoding='utf-8'))['records']
mapping, meta = b.build_glyph_maps()
font = b.ImageFont.truetype('C:/Windows/Fonts/gulim.ttc', 16)
expected = {c: b.korean_tile_bytes(b.korean_glyph(c, font)) for c in meta['table1'].keys() | meta['table2'].keys()}
slots = {c: code + 256 * table for c, (code, table) in mapping.items()}
protected = set(meta['layout']['protected_glyphs'])

def physical(bank, local):
    assert bank >= 0x80 and local >= 0x8000
    return (bank - 0x80) * 0x8000 + local - 0x8000

def boot_glyph(code):
    start = b.FONT_OVERLAY_OFFSET + (code // 16) * 0x200 + code % 16 * 16
    return rom[start:start+16] + rom[start+0x100:start+0x110]

for c in protected:
    assert boot_glyph(slots[c]) == expected[c], c
by_offset = {int(r['offset'], 16): r for r in records}
for i, r in enumerate(records):
    entry = rom[b.TEXT_MAP_OFFSET+i*12:b.TEXT_MAP_OFFSET+(i+1)*12]
    pointer, local, patch = [int.from_bytes(entry[n:n+2], 'little') for n in (0, 2, 4)]
    assert pointer == int(r['original_pointer'], 16)
    start = physical(entry[8], local)
    assert b.TEXT_POOL_OFFSET <= start < b.TEXT_POOL_END
    count = r['length_cells']
    assert rom[start] == 0xe0 | count
    assert (rom[int(r['offset'], 16)] & 31) + 1 == count
    pairs = list(zip(rom[start+1:start+1+2*count:2], rom[start+2:start+2+2*count:2]))
    prefix = r['prefix_pairs']
    assert pairs[:len(prefix)] == [tuple(x) for x in prefix]
    for (code, attr), c in zip(pairs[len(prefix):], r['korean']):
        assert code + 256 * (attr & 1) == slots[c], (r['offset'], c)
    assert rom[start+1+2*count:start+3+2*count] == bytes((0x28, 0))
    assert local + 3 + 2*count <= 0x10000
    patch_start = physical(entry[10], patch)
    assert patch + entry[6]*4 <= 0x10000
    actual = {}
    for n in range(entry[6]):
        p = patch_start + n*4
        target = int.from_bytes(rom[p:p+2], 'little')
        address = int.from_bytes(rom[p+2:p+4], 'little')
        assert target in b.DYNAMIC_TARGET_CANDIDATES and target != b.BACKGROUND_CLEAR_GLYPH
        glyph_start = physical(0xa0, address)
        actual[target] = rom[glyph_start:glyph_start+32]
    for c in r['dynamic_glyphs']:
        assert actual[slots[c]] == expected[c], (r['offset'], c)

owners = {slots[c]: c for c in mapping}
checks = 0
for group in meta['coexistence_groups']:
    for sequence in (group, list(reversed(group))):
        visible = set(protected)
        for offset in sequence:
            r = by_offset[offset]
            for c, target in r['dynamic_targets'].items():
                owners[int(target, 16)] = c
            visible.update(c for c in r['korean'] if c in expected)
            for c in visible:
                assert owners[slots[c]] == c, (hex(offset), c)
                checks += 1

assert rom[0x40000:0x40c52] == original[0x40000:0x40c52]
direct=rom[b.TEXT_DIRECT_INDEX_OFFSET:b.TEXT_DIRECT_INDEX_OFFSET+0x10000]
expected_index={int(r['original_pointer'],16):i*12+1 for i,r in enumerate(records)}
for pointer in range(0x8000,0x10000):
    p=(pointer-0x8000)*2
    assert int.from_bytes(direct[p:p+2],'little')==expected_index.get(pointer,0),hex(pointer)
assert rom[b.FONT_OVERLAY_OFFSET+0x2a10:b.FONT_OVERLAY_OFFSET+0x2a20] == bytes(16)
# Each retained icon/glyph is byte-identical when adding the seven new cells.
used = {int(r['offset'], 16) for r in records}
retained = {c+256*(a&1) for r in b.ALL_ROM_RECORDS if int(r['offset'],16) not in used for c,a in r['pairs']}
icons = {c+256*(a&1) for r in records for c,a in r['prefix_pairs']}
assert not (set(b.RECLAIMED_TEXT_GLYPHS) & (retained | icons))
base_font = (ROOT / 'font_export/font_decompressed_2bpp.bin').read_bytes()
assert not (set(b.DYNAMIC_TARGET_CANDIDATES) & b.BUBBLE_GRAPHICS_GLYPHS)
for code in icons | b.BUBBLE_GRAPHICS_GLYPHS:
    p = (code//16)*0x200 + code%16*16
    assert boot_glyph(code) == base_font[p:p+16] + base_font[p+0x100:p+0x110]
assert rom[0x13927:0x1392e] == bytes.fromhex('5C 00 BA A1 EA EA EA')
assert rom[0x13b05:0x13b09] == bytes.fromhex('5C 80 BA A1')
assert rom[0x602d] == 0
assert rom[0x140cc:0x140d0] == bytes.fromhex('5C 00 BB A1')
assert bytes.fromhex('AD 3F 21 AD 37 21 AD 3D 21 C9 F8') in rom[0x10b400:0x10b800]
report = {'rom_sha256': hashlib.sha256(rom).hexdigest(), 'records_read_back': len(records),
          'glyph_copy_data': 'pass', 'pointer_table_preserved': True, 'icon_glyphs_preserved': len(icons),
          'clear_tile_transparent': True, 'protected_glyphs': len(protected),
          'bubble_graphics_reserved': sorted(b.BUBBLE_GRAPHICS_GLYPHS),
          'width_8_draw_and_tail_hooks': 'pass',
          'caption_row_bounds_and_vblank_margin': 'pass',
          'direct_rom_index_entries_checked': 32768,
          'coexistence_groups': len(meta['coexistence_groups']), 'character_checks': checks,
          'allocated_slots': meta['layout']['allocated_slots'], 'available_slots': len(b.DYNAMIC_TARGET_CANDIDATES),
          'new_slots': {hex(k):v for k,v in b.RECLAIMED_TEXT_GLYPHS.items()},
          'game_executed': False, 'scope': 'Static byte and coexistence verification, not an end-to-end playthrough'}
(ROOT/'analysis/translation_review_20260910/release_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
