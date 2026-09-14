"""QA-only town player displacement in native pixels; no story or item changes.

Town objects store X/Y as 12.4 fixed point at WRAM 0700/0702.
The current movement-history entry at 0980 + byte[0053] is authoritative
(original ROM routine 82:B0C4 and movement reads around 82:AF03).
Use only on a free town screen, never in a conversation or event cutscene.
"""
import ctypes as C
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
out = root / 'analysis_font_scan/ending_review'
assert len(sys.argv) == 3
dx, dy = map(int, sys.argv[1:])
assert abs(dx) <= 256 and abs(dy) <= 256
rom = root / 'Albert Odyssey - Korean Full.sfc'
digest = hashlib.sha256(rom.read_bytes()).hexdigest()
assert out.joinpath('rom_sha256.txt').read_text().strip() == digest
p = root / 'analysis_font_scan/run_headless.py'
sys.argv = [str(p), str(rom), str(out)]
ns = {'__file__': str(p), '__name__': 'town_displacement'}
exec(p.read_text().split('for frame in range(5001):')[0], ns)
core = ns['core']
core.retro_unserialize.argtypes = [C.c_void_p, C.c_size_t]
core.retro_unserialize.restype = C.c_bool
state = out.joinpath('latest.state').read_bytes()
buf = C.create_string_buffer(state)
assert core.retro_unserialize(buf, len(state))
ram = (C.c_ubyte * 131072).from_address(core.retro_get_memory_data(2))
before = bytes(ram)
leader = ram[0x7f]
assert leader in (0, 0x10, 0x20, 0x30)
history = 0x980 + ram[0x53]
assert ram[0x53] % 4 == 0
old = [int.from_bytes(before[a:a+2], 'little') for a in (history, history+2)]
new = [v + delta * 16 for v, delta in zip(old, (dx, dy))]
assert all(0 <= v < 0x8000 for v in new)
out.joinpath('before_town_shift.state').write_bytes(state)
allowed = set()
for base in (0x700 + leader, history):
    for a, v in zip((base, base+2), new):
        ram[a], ram[a+1] = v & 255, v >> 8
        allowed.update((a, a+1))
changed = [i for i in range(len(ram)) if before[i] != ram[i]]
assert set(changed) <= allowed
buf = C.create_string_buffer(core.retro_serialize_size())
assert core.retro_serialize(buf, len(buf))
out.joinpath('latest.state').write_bytes(buf.raw)
with out.joinpath('town_shifts.jsonl').open('a', encoding='utf-8') as f:
    f.write(json.dumps({'from_fixed': old, 'to_fixed': new,
        'delta_pixels': [dx, dy], 'changed_ram_offsets': [hex(i) for i in changed],
        'rom_sha256': digest, 'scope': 'QA town player position only; no story flags, NPCs, inventory or ROM changed'}) + '\n')
core.retro_unload_game()
core.retro_deinit()
