"""Compare identical state and joypad inputs, using emulated frames, not host time."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
label=sys.argv[1]
rom=Path(sys.argv[2])
state_path=Path(sys.argv[3])
mode=sys.argv[4] if len(sys.argv)>4 else 'field'
out=ROOT/'analysis/facing_latency_20260911'/label
out.mkdir(exist_ok=True)
runner=ROOT/'analysis_font_scan/run_headless.py'
sys.argv=[str(runner),str(rom),str(out)]
ns={'__file__':str(runner),'__name__':'battle_benchmark'}
exec(compile(runner.read_text().split('for frame in range(5001):')[0],str(runner),'exec'),ns)
core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
data=state_path.read_bytes();buf=C.create_string_buffer(data);assert core.retro_unserialize(buf,len(data))
pressed=set()
@ns['INPUT']
def inp(port,device,index,ident):return int(port==0 and ident in pressed)
core.retro_set_input_state(inp)
ram=(C.c_ubyte*131072).from_address(core.retro_get_memory_data(2))
if len(rom.read_bytes())==0x100000:
    # A controlled shared gameplay state may contain Korean font pixels.
    # Restore the original font solely in test VRAM before measuring Japanese.
    font=(ROOT/'font_export/font_decompressed_2bpp.bin').read_bytes()
    C.memmove(core.retro_get_memory_data(3)+0x8000,font,len(font))
def signature():
    v=C.string_at(core.retro_get_memory_data(3),65536)
    return (bytes(ram[0xa3:0xa5]).hex(),hashlib.sha256(v[0xb800:0xc000]).hexdigest())
buttons={'b':0,'up':4,'down':5,'left':6,'right':7,'a':8,'x':9,'start':3}
if mode in ('menu','reaction'):
    # Test-state cursor placement only. Unit stats, positions and story flags
    # remain untouched. Settle each version before measuring the same action.
    for f in range(132):
        pressed={0} if f<2 else set();core.retro_run()
    ram[0x202]=0xc0
    ram[0x8d]=15
    for p in (0xa3,0xa6):ram[p]=ram[0x200];ram[p+1]=ram[0x201]
    for button in (7,6):
        for f in range(132):
            pressed={button} if f<2 else set();core.retro_run()

ns['frame']=0;ns['capture']()
(out/'frame0000.state').replace(out/'latest.state')
(out/'rom_sha256.txt').write_text(hashlib.sha256(rom.read_bytes()).hexdigest())
core.retro_unload_game();core.retro_deinit()
