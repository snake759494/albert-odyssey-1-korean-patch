"""Reduce one active enemy's HP in a QA checkpoint; never edit the ROM."""
import ctypes as C
import os
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent;out=Path(os.environ.get('AO_REVIEW_DIR',root/'analysis_font_scan/ending_review'))
x,y=map(int,sys.argv[1:3])
p=root/'analysis_font_scan/run_headless.py';sys.argv=[str(p),str(root/'Albert Odyssey - Korean Full.sfc'),str(out)];ns={'__file__':str(p),'__name__':'qa_hp'}
exec(p.read_text().split('for frame in range(5001):')[0],ns);core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
state=out.joinpath('latest.state').read_bytes();buf=C.create_string_buffer(state);assert core.retro_unserialize(buf,len(state))
out.joinpath('before_enemy_hp.state').write_bytes(state)
ram=(C.c_ubyte*131072).from_address(core.retro_get_memory_data(2));before=bytes(ram)
found=[]
for base,end,stride,hp in ((0x300,0x700,16,8),(0x197C0,0x1A7C0,8,6),(0x1A7C0,0x1A820,8,6)):
 for a in range(base,end,stride):
  if list(ram[a:a+2])==[x,y] and ram[a+2]&0x80:
   found.append({'offset':hex(a),'old_hp':int.from_bytes(bytes(ram[a+hp:a+hp+2]),'little')})
   ram[a+hp]=1;ram[a+hp+1]=0
assert found
buf=C.create_string_buffer(core.retro_serialize_size());assert core.retro_serialize(buf,len(buf));out.joinpath('latest.state').write_bytes(buf.raw)
with out.joinpath('combat_assistance.jsonl').open('a') as f:f.write(json.dumps({'target':[x,y],'new_hp':1,'matches':found,'scope':'QA only; no inventory or event flags altered'})+'\n')
core.retro_unload_game();core.retro_deinit();print(found)
