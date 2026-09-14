import ctypes as C
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent;kind=sys.argv[1]
out=root/'analysis_font_scan/ending_review'/('input_'+kind);out.mkdir(exist_ok=True)
r=bytearray((root/'Albert Odyssey - Korean Full.sfc').read_bytes());orig=(root/'Albert Odyssey.sfc').read_bytes()
if kind=='original':r[:len(orig)]=orig
elif kind in ('headers','subset'):
 for x in json.loads((root/'analysis/all_rom_text.json').read_text(encoding='utf-8')):
  o=int(x['offset'],16)
  if kind=='headers' or o in json.loads((out.parent/'header_subset.json').read_text()):r[o]=orig[o]
elif kind=='font':
 for i in range(len(orig)-3):
  if orig[i:i+4]==bytes.fromhex('22 28 8C 82'):r[i:i+4]=orig[i:i+4]
elif kind=='parsers':
 for i in range(len(orig)-3):
  if orig[i:i+4] in (bytes.fromhex('22 1D F7 84'),bytes.fromhex('22 C0 F7 84'),bytes.fromhex('22 63 F8 84')):r[i:i+4]=orig[i:i+4]
elif kind=='dynamic':r[0x10b400]=0x6b
rom=out/'probe.sfc';rom.write_bytes(r)
runner=root/'analysis_font_scan/run_headless.py';sys.argv=[str(runner),str(rom),str(out)];ns={'__file__':str(runner),'__name__':'probe'}
exec(runner.read_text().split('for frame in range(5001):')[0],ns);core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
b=(root/'analysis_font_scan/ending_review/latest.state').read_bytes();buf=C.create_string_buffer(b);assert core.retro_unserialize(buf,len(b))
f=0
@ns['INPUT']
def inp(port,device,index,ident):return int(port==0 and ident==7 and f<60)
core.retro_set_input_state(inp)
for f in range(2200):core.retro_run()
ns['frame']=0;ns['capture']();core.retro_unload_game();core.retro_deinit()
