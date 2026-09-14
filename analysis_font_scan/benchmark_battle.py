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
out=ROOT/'analysis/battle_latency_20260911'/label
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
    for p in (0xa3,0xa6):ram[p]=ram[0x200];ram[p+1]=ram[0x201]
    for button in (7,6):
        for f in range(132):
            pressed={button} if f<2 else set();core.retro_run()
rows=[]
keys=['a_then_down'] if mode=='reaction' else (['a','down','up'] if mode=='menu' else ['b','right','left','a','down','up','b']*3)
for i,key in enumerate(keys):
    previous=signature();changes=[];cursor=[]
    for f in range(1,133):
        if mode=='reaction':
            pressed={8} if f<=2 else ({5} if 13<=f<=14 else set())
        else:
            pressed={buttons[key]} if f<=2 else set()
        core.retro_run();current=signature()
        if current[1]!=previous[1]:changes.append(f)
        if current[0]!=previous[0]:cursor.append(f)
        previous=current
    rows.append({'step':i,'button':key,'tilemap_change_frames':changes,'cursor_change_frames':cursor,'cursor_end':previous[0]})
    ns['frame']=i;ns['capture']()
    for suffix in ('.state','_mem2.bin','_mem3.bin'):(out/f'frame{i:04d}{suffix}').unlink(missing_ok=True)
core.retro_unload_game();core.retro_deinit()
(out/'report.json').write_text(json.dumps({'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'seed_sha256':hashlib.sha256(data).hexdigest(),'mode':mode,'cursor_placement_assistance':mode in ('menu','reaction'),'original_font_restored_in_test_vram':len(rom.read_bytes())==0x100000,'results':rows},indent=2))
print(json.dumps(rows))
