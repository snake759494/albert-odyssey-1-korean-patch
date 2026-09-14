"""QA-only field cursor positioning; never moves units or changes story/inventory."""
import ctypes as C
import os
import json,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent;out=Path(os.environ.get('AO_REVIEW_DIR',root/'analysis_font_scan/ending_review'))
x,y=map(int,sys.argv[1:3]);assert 0<=x<256 and 0<=y<128
assert len(sys.argv) == 3, 'usage: qa_cursor.py X Y'
p=root/'analysis_font_scan/run_headless.py';sys.argv=[str(p),str(root/'Albert Odyssey - Korean Full.sfc'),str(out)];ns={'__file__':str(p),'__name__':'qa_relocation'}
exec(p.read_text().split('for frame in range(5001):')[0],ns);core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
state=out.joinpath('latest.state').read_bytes();buf=C.create_string_buffer(state);assert core.retro_unserialize(buf,len(state))
out.joinpath('before_cursor.state').write_bytes(state)
ram=(C.c_ubyte*131072).from_address(core.retro_get_memory_data(2));old=list(ram[0xA3:0xA5]);before=bytes(ram)
for a in (0xA3,0xA6):ram[a]=x;ram[a+1]=y
changed=[i for i in range(len(ram)) if before[i]!=ram[i]]
buf=C.create_string_buffer(core.retro_serialize_size());assert core.retro_serialize(buf,len(buf));out.joinpath('latest.state').write_bytes(buf.raw)
with out.joinpath('cursor_assistance.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'from':old,'to':[x,y],'changed_ram_offsets':[hex(i) for i in changed],'rom_sha256':hashlib.sha256((root/'Albert Odyssey - Korean Full.sfc').read_bytes()).hexdigest(),'scope':'QA cursor only; no unit positions, story flags or inventory changed'})+'\n')
core.retro_unload_game();core.retro_deinit()
