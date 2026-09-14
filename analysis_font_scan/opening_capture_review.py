"""Capture the natural opening with the same inputs as the route regression."""
import hashlib
import json
from pathlib import Path
import sys
import ctypes as C

ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'analysis/opening_review_20260911/opening'
out.mkdir(exist_ok=True)
runner=ROOT/'analysis_font_scan/run_story_probe.py'
rom=ROOT/'Albert Odyssey - Korean Full.sfc'
sys.path.insert(0,str(ROOT/'font_export'))
import build_korean_full_patch as b
mapping,meta=b.build_glyph_maps()
font=b.ImageFont.truetype('C:/Windows/Fonts/gulim.ttc',16)
records={r['offset']:r for r in json.loads((ROOT/'analysis/full_dialogue_extracted.json').read_text(encoding='utf-8'))['records']}
checkpoints={6500:'0x43D73',17000:'0x43C4F'}
expected={c:b.korean_tile_bytes(b.korean_glyph(c,font)) for key in checkpoints.values() for c in records[key]['korean'] if '가'<=c<='힣'}
slots={c:n+256*t for c,(n,t) in mapping.items()}
sys.argv=[str(runner),str(rom),str(out),'42000']
ns={'__file__':str(runner),'__name__':'opening_capture'}
exec(compile(runner.read_text().split('for frame in range(END_FRAME+1):')[0],str(runner),'exec'),ns)
seen=set();frames=[]
checks=[]
for frame in range(42001):
    ns['frame']=frame;ns['core'].retro_run()
    if frame in checkpoints:
        key=checkpoints[frame];text=records[key]['korean']
        vram=C.string_at(ns['core'].retro_get_memory_data(3),65536)
        mismatches=[]
        for c in set(text)&expected.keys():
            code=slots[c];p=0x8000+(code//16)*0x200+(code%16)*16
            if vram[p:p+16]+vram[p+0x100:p+0x110]!=expected[c]:mismatches.append(c)
        check={'frame':frame,'offset':key,'glyph_mismatches':mismatches}
        if frame==17000:
            ram=C.string_at(ns['core'].retro_get_memory_data(2),131072)
            upper=[(slots[c]//16)*32+slots[c]%16 for c in text]
            tile=lambda p:int.from_bytes(ram[p:p+2],'little')&0x3ff
            starts=[p for p in range(0x1772,0x1f32,2) if [tile(p+2*i) for i in range(len(upper))]==upper]
            if len(starts)!=1:
                (out/'caption_ram.bin').write_bytes(ram)
                (out/'caption_vram.bin').write_bytes(vram)
                (out/'caption_expected.json').write_text(json.dumps(upper))
            assert len(starts)==1,starts
            start=starts[0]
            check['caption_start']=hex(start)
            check['caption_stays_in_row']=(start-0x1772)%64+len(upper)*2<=64
            check['caption_lower_tiles_match']=[tile(start+64+2*i) for i in range(len(upper))]==[t+16 for t in upper]
            assert check['caption_stays_in_row'] and check['caption_lower_tiles_match']
        checks.append(check)
        assert not mismatches,check
    if frame>=1000 and frame%500==0:
        digest=hashlib.sha256(ns['lastframe'][0]).hexdigest()
        if digest not in seen:
            ns['capture']();frames.append(frame);seen.add(digest)
            for suffix in ('.state','_mem2.bin','_mem3.bin'):
                (out/f'frame{frame:04d}{suffix}').unlink(missing_ok=True)
    if frame%10000==0:print(frame,flush=True)
ns['core'].retro_unload_game();ns['core'].retro_deinit()
(out/'report.json').write_text(json.dumps({'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'frames_run':42001,'screenshots':frames,'natural_scene_checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
