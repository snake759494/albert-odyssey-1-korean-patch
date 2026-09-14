"""QA-only field relocation. Never edits the shipped ROM or story/inventory data."""
import ctypes as C
import json,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent;out=root/'analysis_font_scan/ending_review'
x,y=map(int,sys.argv[1:3]);assert 0<=x<256 and 0<=y<128
move_party='--party' in sys.argv[3:]
p=root/'analysis_font_scan/run_headless.py';sys.argv=[str(p),str(root/'Albert Odyssey - Korean Full.sfc'),str(out)];ns={'__file__':str(p),'__name__':'qa_relocation'}
exec(p.read_text().split('for frame in range(5001):')[0],ns);core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
state=out.joinpath('latest.state').read_bytes();buf=C.create_string_buffer(state);assert core.retro_unserialize(buf,len(state))
out.joinpath('before_town_assistance.state').write_bytes(state)
ram=(C.c_ubyte*131072).from_address(core.retro_get_memory_data(2));old=list(ram[0x200:0x202]);before=bytes(ram)
for a in (0x200,0x240,0x280,0x2C0):
 ram[a]=x;ram[a+1]=y;ram[a+2]=0;ram[a+8]=0x0F;ram[a+9]=0x27
if move_party:
    for a,dx,dy in ((0x240,-2,0),(0x280,-1,0),(0x2C0,-2,1)):
        ram[a]=(x+dx)&255;ram[a+1]=(y+dy)&127
changed=[i for i in range(len(ram)) if before[i]!=ram[i]]
buf=C.create_string_buffer(core.retro_serialize_size());assert core.retro_serialize(buf,len(buf));out.joinpath('latest.state').write_bytes(buf.raw)
with out.joinpath('party_town_assistance.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'from':old,'to':[x,y],'move_party':move_party,'changed_ram_offsets':[hex(i) for i in changed],'rom_sha256':hashlib.sha256((root/'Albert Odyssey - Korean Full.sfc').read_bytes()).hexdigest(),'scope':'QA field travel only; no story flags or inventory changed'})+'\n')
core.retro_unload_game();core.retro_deinit()
