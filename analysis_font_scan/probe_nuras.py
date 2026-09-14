import ctypes as C
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
which=sys.argv[1];out=root/'analysis_font_scan/ending_review'/('probe_'+which);out.mkdir(exist_ok=True)
r=root/'analysis_font_scan/run_headless.py'
rom=root/('Albert Odyssey.sfc' if which=='original' else 'Albert Odyssey - Korean Full.sfc')
sys.argv=[str(r),str(rom),str(out)];ns={'__file__':str(r),'__name__':'probe'}
exec(r.read_text().split('for frame in range(5001):')[0],ns);core=ns['core']
core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
b=(root/'analysis_font_scan/ending_review/nuras_bad_choice.state').read_bytes();buf=C.create_string_buffer(b);assert core.retro_unserialize(buf,len(b))
button=-1
@ns['INPUT']
def inp(port,device,index,ident): return int(port==0 and ident==button)
core.retro_set_input_state(inp)
def run(k,n):
 global button
 button=k
 for _ in range(n): core.retro_run()
run(0,12);run(-1,200);run(8,12);run(-1,250)
for page in range(51):
 run(8,12);run(-1,400)
 if page>=30:
  ns['frame']=page;ns['capture']()
core.retro_deinit()
