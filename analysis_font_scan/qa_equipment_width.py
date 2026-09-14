"""Isolated width regression: equip the longest staff in a test state only."""
import ctypes as C
import os,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=Path(os.environ['AO_REVIEW_DIR'])
rom=(root/'Albert Odyssey - Korean Full.sfc').read_bytes()
original=(root/'Albert Odyssey.sfc').read_bytes()
records=json.loads((root/'analysis/all_rom_text.json').read_text(encoding='utf-8'))
index=next(r['index'] for r in records if r['offset']=='0x41309')
item=next(i for i in range(256) if int.from_bytes(original[0x2E88+i*2:0x2E8A+i*2],'little')==index)
p=root/'analysis_font_scan/run_headless.py'
sys.argv=[str(p),str(root/'Albert Odyssey - Korean Full.sfc'),str(out)]
ns={'__file__':str(p),'__name__':'qa_equipment'}
exec(p.read_text().split('for frame in range(5001):')[0],ns)
core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]
data=(out/'latest.state').read_bytes(); buf=C.create_string_buffer(data)
assert core.retro_unserialize(buf,len(data))
ram=(C.c_ubyte*131072).from_address(core.retro_get_memory_data(2))
old=ram[0x245];ram[0x245]=item
buf=C.create_string_buffer(core.retro_serialize_size());assert core.retro_serialize(buf,len(buf))
(out/'latest.state').write_bytes(buf.raw)
with (out/'equipment_assistance.jsonl').open('a') as f:
 f.write(json.dumps({'ram':'0x245','old_item':old,'new_item':item,'scope':'QA display only; shipped ROM inventory unchanged'})+'\n')
core.retro_deinit()
