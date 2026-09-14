"""Exercise real text sizing, rendering, and dismissal with a host watchdog.

The previous renderer test changed only the pointer map, leaving the opening's
short width headers in place. This test changes BOTH in its private test ROM.
No test-only redirection is saved to the release ROM.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'font_export'))
import build_korean_full_patch as b

selected = {int(x,16) for x in sys.argv[1:]}
out = Path(os.environ.get('AO_AUDIT_OUT', ROOT/'analysis_font_scan'/('freeze_focus' if selected else 'freeze_all')))
out.mkdir(exist_ok=True)
rom = b.ROM_OUT.read_bytes()
records = json.loads((ROOT/'analysis/full_dialogue_extracted.json').read_text(encoding='utf-8'))['records']
mapping, meta = b.build_glyph_maps()
font = b.ImageFont.truetype('C:/Windows/Fonts/gulim.ttc',16)
expected = {c:b.korean_tile_bytes(b.korean_glyph(c,font)) for c in meta['table1'].keys()|meta['table2'].keys()}
slots = {c:n+256*t for c,(n,t) in mapping.items()}
entries = {int.from_bytes(rom[b.TEXT_MAP_OFFSET+i*12:b.TEXT_MAP_OFFSET+i*12+2],'little'):b.TEXT_MAP_OFFSET+i*12 for i in range(len(records))}
runner = ROOT/'analysis_font_scan/run_headless.py'
sys.argv = [str(runner),str(b.ROM_OUT),str(out)]
ns={'__file__':str(runner),'__name__':'freeze_core'}
exec(compile(runner.read_text().split('for frame in range(5001):')[0],str(runner),'exec'),ns)
core=ns['core']
core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]
core.retro_unserialize.restype=C.c_bool
heartbeat=[time.monotonic(),-1,False]
def watchdog():
    while not heartbeat[2]:
        time.sleep(1)
        if time.monotonic()-heartbeat[0]>30:
            (out/'watchdog_failure.json').write_text(json.dumps({'case':heartbeat[1],'reason':'no frame returned for 30 seconds'}))
            os._exit(124)
threading.Thread(target=watchdog,daemon=True).start()
for frame in range(1491):
    ns['frame']=frame;core.retro_run();heartbeat[0]=time.monotonic()
size=core.retro_serialize_size();state=C.create_string_buffer(size)
assert core.retro_serialize(state,size)
original_font=(ROOT/'font_export/font_decompressed_2bpp.bin').read_bytes()
border_tiles=[0x2c8,0x2c9,0x2d8,0x2d9]
results=[]
cases=[r for r in records if not selected or int(r['offset'],16) in selected]
if os.environ.get('AO_AUDIT_SHARD'):
    shard, total = map(int, os.environ['AO_AUDIT_SHARD'].split('/'))
    assert 0 <= shard < total
    cases = cases[shard::total]
for case,r in enumerate(cases):
    heartbeat[1]=case
    test=bytearray(rom)
    for pointer in (0xb911,0xc674):
        header=0x40000+pointer-0x8000
        test[header]=(test[header]&0xe0)|(r['length_cells']-1)
        src=entries[int(r['original_pointer'],16)];dst=entries[pointer]
        test[dst+2:dst+12]=rom[src+2:src+12]
    core.retro_unload_game()
    data=C.create_string_buffer(bytes(test));info=ns['Info'](b'freeze-test.sfc',C.cast(data,C.c_void_p),len(test),None)
    assert core.retro_load_game(C.byref(info))
    assert core.retro_unserialize(state,size)
    ram=(C.c_ubyte*131072).from_address(core.retro_get_memory_data(2))
    guard=bytes(ram[0x1f72:0x1f92])
    for frame in range(1491,1801):
        ns['frame']=frame;core.retro_run();heartbeat[0]=time.monotonic()
    vram=C.string_at(core.retro_get_memory_data(3),65536)
    bad=[]
    for c in set(r['korean'])&expected.keys():
        start=0x8000+(slots[c]//16)*0x200+(slots[c]%16)*16
        if vram[start:start+16]+vram[start+0x100:start+0x110]!=expected[c]:bad.append(c)
    borders=[hex(t) for t in border_tiles if vram[0x8000+t*16:0x8010+t*16]!=original_font[t*16:t*16+16]]
    guard_ok=bytes(ram[0x1f72:0x1f92])==guard
    width=ram[0x57];before_cursor=ram[0x59]
    # A real A-button edge must dismiss the page and advance its script.
    @ns['INPUT']
    def advance(port,device,index,button):
        return int(port==0 and button==8 and 1810<=ns['frame']<1822)
    core.retro_set_input_state(advance)
    if selected or bad or borders or not guard_ok:
        ns['frame']=case;ns['capture']()
    for frame in range(1801,2041):
        ns['frame']=frame;core.retro_run();heartbeat[0]=time.monotonic()
    advanced=ram[0x59]!=before_cursor
    if selected:
        ns['frame']=case+10000;ns['capture']()
    core.retro_set_input_state(ns['inp'])
    result={'offset':r['offset'],'text':r['korean'],'cells':r['length_cells'],
            'width':width,'glyph_mismatches':sorted(bad),'border_mismatches':borders,
            'buffer_guard_preserved':guard_ok,'page_advanced':advanced,
            'cursor_before':before_cursor,'cursor_after':ram[0x59]}
    results.append(result)
    if case%25==0:
        print(f'checked {case+1}/{len(cases)}',flush=True)
        (out/'progress.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    for suffix in ('.state','_mem2.bin','_mem3.bin'):
        (out/f'frame{case:04d}{suffix}').unlink(missing_ok=True)
heartbeat[2]=True
core.retro_unload_game();core.retro_deinit()
failures=[r for r in results if r['glyph_mismatches'] or r['border_mismatches'] or not r['buffer_guard_preserved'] or not r['page_advanced']]
report={'rom_sha256':hashlib.sha256(rom).hexdigest(),'cases':len(results),'failures':failures,'results':results,
        'scope':'Every selected record through actual width calculation, rendering and A-button dismissal; not all story branches'}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cases':len(results),'failures':len(failures)},ensure_ascii=False),flush=True)
assert not failures
