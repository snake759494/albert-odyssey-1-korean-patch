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
if len(rom.read_bytes())==0x200000:
    font=rom.read_bytes()[0x108000:0x10af80]
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

import os
if os.environ.get('AO_ADJACENT_ENEMY')=='1':
    ram[0x340]=ram[0x240]+1;ram[0x341]=ram[0x241]
commands=mode.split(',')
rows=[];frame_no=0
size=core.retro_serialize_size();statebuf=C.create_string_buffer(size)
for i,cmd in enumerate(commands):
    key,duration=cmd.split(':');previous=signature();changes=[];cursor=[];pcs={};samples=[]
    for f in range(1,int(duration)+1):
        pressed={buttons[key]} if key!='wait' else set()
        core.retro_run();current=signature()
        if current[1]!=previous[1]:changes.append(f)
        if current[0]!=previous[0]:cursor.append([f,current[0]])
        previous=current
        assert core.retro_serialize(statebuf,size)
        raw=statebuf.raw;at=raw.index(b'REG:000016:')+11;r=raw[at:at+16]
        pc=f'{r[0]:02x}:{int.from_bytes(r[14:16],"big"):04x}'
        pcs[pc]=pcs.get(pc,0)+1
        if pc.startswith('a1:'):samples.append([f,pc,bytes(ram[0x1c:0x24]).hex(),bytes(ram[:16]).hex()])
    rows.append({'command':cmd,'tilemap_changes':changes,'cursor_changes':cursor,'pcs':pcs,'patch_samples':samples})
    ns['frame']=i;ns['capture']()
core.retro_unload_game();core.retro_deinit()
(out/'report.json').write_text(json.dumps(rows,indent=2))
(out/'context.json').write_text(json.dumps({'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'seed_sha256':hashlib.sha256(data).hexdigest(),'font_restored_in_test_vram':True,'enemy_position_assistance':os.environ.get('AO_ADJACENT_ENEMY')=='1','commands':commands},indent=2))
print(json.dumps(rows))
