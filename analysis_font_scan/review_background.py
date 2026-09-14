"""Fresh-boot title/intro/battle regression for the transparent BG3 tile."""
import ctypes as C
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
mode=sys.argv[1] if len(sys.argv)>1 else 'story'
out=root/'analysis_font_scan'/f'background_{mode}'
out.mkdir(exist_ok=True)
p=root/'analysis_font_scan/run_headless.py'
rom_path=root/'Albert Odyssey - Korean Full.sfc'
sys.argv=[str(p),str(rom_path),str(out)]
ns={'__file__':str(p),'__name__':'background_review'}
exec(p.read_text().split('for frame in range(5001):')[0],ns)
core=ns['core']
@ns['INPUT']
def inp(port,device,index,ident):
 if port: return 0
 f=ns['frame']
 if mode=='title': return int(ident==3 and 1100<=f<1112)
 return int((ident==3 and 2000<=f<2012) or
            (ident==8 and 2300<=f<2312) or
            (ident==8 and f>=3000 and (f-3000)%700<12))
core.retro_set_input_state(inp)
failures=[]; captures=[]
end=10000 if mode=='title' else 42000
for frame in range(end+1):
 ns['frame']=frame
 core.retro_run()
 if frame>=1000 and frame%500==0:
  tile=C.string_at(core.retro_get_memory_data(3)+0xAA10,16)
  if any(tile): failures.append(frame)
  ns['capture'](); captures.append(frame)
  # Keep screenshots, final memory and a few reproducible checkpoints only.
  if frame!=end and frame not in (1000,1500,2500,8000,15000,25000):
   for suffix in ('.state','_mem2.bin','_mem3.bin'):
    (out/f'frame{frame:04d}{suffix}').unlink(missing_ok=True)
print({'mode':mode,'frames':end,'captures':len(captures),'nontransparent_clear_tile_frames':failures},flush=True)
(out/'report.json').write_text(json.dumps({'rom_sha256':hashlib.sha256(rom_path.read_bytes()).hexdigest(),
 'mode':mode,'fresh_boot':True,'frames':end,'captures':captures,'clear_tile':'0x2A1',
 'nontransparent_clear_tile_frames':failures},indent=2)+'\n',encoding='utf-8')
core.retro_unload_game();core.retro_deinit()
assert not failures
