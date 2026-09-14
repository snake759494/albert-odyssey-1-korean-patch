"""Explicit QA-only migration of an idle dialogue checkpoint after a ROM rebuild.

Reloads the font as the game's normal DMA would, without simulating DMA timing.
Does not replace fresh-boot validation or claim a clean full-game replay.
"""
from pathlib import Path
import ctypes as C
import hashlib
import json
import sys
import os

root = Path(__file__).resolve().parent.parent
out = Path(os.environ.get('AO_REVIEW_DIR',root/'analysis_font_scan/ending_review'))
rom_path=Path(os.environ.get('AO_ROM',root/'Albert Odyssey - Korean Full.sfc'))
checkpoint = Path(sys.argv[1]) if len(sys.argv)>1 else out/'nuras_bad_choice.state'
p = root/'analysis_font_scan/run_headless.py'
sys.argv = [str(p),str(rom_path),str(out)]
ns = {'__file__':str(p),'__name__':'migration'}
exec(p.read_text().split('for frame in range(5001):')[0],ns)
core = ns['core']
core.retro_unserialize.argtypes = [C.c_void_p,C.c_size_t]
core.retro_unserialize.restype = C.c_bool
state = checkpoint.read_bytes()
buf = C.create_string_buffer(state)
assert core.retro_unserialize(buf,len(state))
rom = rom_path.read_bytes()
if len(rom)==0x100000:
    sys.path.insert(0,str(root/'font_export'))
    from extract_font import decompress,BLOCKS
    font=b''.join(decompress(rom,a)[0] for a,_,_ in BLOCKS)
else:
    font=rom[0x108000:0x10AF80]
assert len(font)==0x2F80
C.memmove(core.retro_get_memory_data(3)+0x8000,font,len(font))
buf = C.create_string_buffer(core.retro_serialize_size())
assert core.retro_serialize(buf,len(buf))
(out/'latest.state').write_bytes(buf.raw)
h = hashlib.sha256(rom).hexdigest()
old_hash = (out/'rom_sha256.txt').read_text().strip()
(out/'rom_sha256.txt').write_text(h)
with (out/'migrations.jsonl').open('a',encoding='utf-8') as stream:
    stream.write(json.dumps({'new_rom_sha256':h,'previous_review_hash':old_hash,'checkpoint':str(checkpoint),
                             'checkpoint_sha256':hashlib.sha256(state).hexdigest(),'method':'Offline font reload; reopen dialogue before judging screenshots.'})+'\n')
core.retro_deinit()
print(h)
