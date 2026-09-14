"""Natural scene checks keyed to rendered text, independent of ROM speed."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import os

ROOT=Path(__file__).resolve().parent.parent
out=Path(os.environ.get('AO_OPENING_OUT', ROOT/'analysis/battle_latency_20260911/opening'))
out.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'font_export'))
import build_korean_full_patch as b
mapping,meta=b.build_glyph_maps()
slots={c:n+256*t for c,(n,t) in mapping.items()}
font=b.ImageFont.truetype('C:/Windows/Fonts/gulim.ttc',16)
texts={k:b.STYLE1_KO.get(k,b.STYLE2_KO.get(k)) for k in (0x43d73,0x43c4f)}
expected={c:b.korean_tile_bytes(b.korean_glyph(c,font)) for text in texts.values() for c in text if '가'<=c<='힣'}
runner=ROOT/'analysis_font_scan/run_story_probe.py'
sys.argv=[str(runner),str(b.ROM_OUT),str(out),'42000']
ns={'__file__':str(runner),'__name__':'natural_battle_regression'}
exec(compile(runner.read_text().split('for frame in range(END_FRAME+1):')[0],str(runner),'exec'),ns)
core=ns['core'];checks=[];pending=dict(texts)
for frame in range(42001):
    ns['frame']=frame;core.retro_run()
    if pending:
        ram=C.string_at(core.retro_get_memory_data(2),131072)
        for key,text in list(pending.items()):
            codes=[slots[c] for c in text]
            if [int.from_bytes(ram[0x2b00+2*i:0x2b02+2*i],'little')&0x1ff for i in range(len(codes))]!=codes:continue
            upper=[(code//16)*32+code%16 for code in codes]
            tile=lambda p:int.from_bytes(ram[p:p+2],'little')&0x3ff
            starts=[p for p in range(0x1772,0x1f32,2) if tile(p)==upper[0] and [tile(p+2*i) for i in range(len(upper))]==upper]
            if not starts:continue
            vram=C.string_at(core.retro_get_memory_data(3),65536)
            mismatches=[]
            for c in set(text)&expected.keys():
                code=slots[c];p=0x8000+(code//16)*0x200+(code%16)*16
                if vram[p:p+16]+vram[p+256:p+272]!=expected[c]:mismatches.append(c)
            assert not mismatches,(hex(key),mismatches)
            bounded=all((p-0x1772)%64+len(upper)*2<=64 for p in starts)
            lower=all([tile(p+64+2*i) for i in range(len(upper))]==[t+16 for t in upper] for p in starts)
            assert bounded and lower
            checks.append({'record':hex(key),'frame':frame,'glyph_mismatches':[],'row_bounded':bounded,'lower_tiles_match':lower})
            ns['capture']()
            for suffix in ('.state','_mem2.bin','_mem3.bin'):(out/f'frame{frame:04d}{suffix}').unlink(missing_ok=True)
            del pending[key]
    if frame%10000==0:print(frame,flush=True)
core.retro_unload_game();core.retro_deinit()
assert not pending,list(pending)
(out/'report.json').write_text(json.dumps({'rom_sha256':hashlib.sha256(b.ROM_OUT.read_bytes()).hexdigest(),'frames_run':42001,'checks':checks},indent=2))
