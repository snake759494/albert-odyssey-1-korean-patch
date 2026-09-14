import ctypes as C
import sys,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
checkpoint=Path(sys.argv[1])
p=root/'analysis_font_scan/run_headless.py'
sys.argv=[str(p),str(root/'Albert Odyssey - Korean Full.sfc'),str(root/'analysis_font_scan/review_fixes')]
ns={'__file__':str(p),'__name__':'inspect'}
exec(p.read_text().split('for frame in range(5001):')[0],ns)
core=ns['core'];core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t]
data=checkpoint.read_bytes(); buf=C.create_string_buffer(data)
assert core.retro_unserialize(buf,len(data))
ram=bytes((C.c_ubyte*131072).from_address(core.retro_get_memory_data(2)))
w=lambda a:int.from_bytes(ram[a:a+2],'little')
rom=(root/'Albert Odyssey - Korean Full.sfc').read_bytes()
rw=lambda a:int.from_bytes(rom[a:a+2],'little')
actor=w(0xb7); typ=ram[0x704+actor]
script=rw(0x38000+typ*2)-0x8000+0x38000
lines=rw(script+ram[0xc4]*2)-0x8000+0x38000
print({'actor':hex(actor),'type':typ,'c4':ram[0xc4],'59':ram[0x59],'57':ram[0x57], '30':w(0x30),'bb':w(0xbb),'actorx':w(0x700+actor),'script':hex(script),'lines':hex(lines)})
records={r['index']:r for r in json.loads((root/'analysis/all_rom_text.json').read_text(encoding='utf8'))}
for pos in range(max(0,ram[0x59]-3),ram[0x59]+6):
 i=rw(lines+pos*2)
 print(pos,hex(i),records.get(i,{}).get('offset'),records.get(i,{}).get('japanese'))
sys.path.insert(0,str(root/'font_export'))
import build_korean_full_patch as b
m,meta=b.build_glyph_maps()
v=bytes((C.c_ubyte*65536).from_address(core.retro_get_memory_data(3)))
font=b.ImageFont.truetype('C:/Windows/Fonts/gulim.ttc',16)
for ch in '예여':
 c,t=m[ch]; index=c+t*256; start=0x8000+(index//16)*0x200+index%16*16
 actual=v[start:start+16]+v[start+256:start+272]
 owners=[x for x in m if '가'<=x<='힣' and b.korean_tile_bytes(b.korean_glyph(x,font))==actual]
 print(ch,m[ch],owners)
core.retro_deinit()
