import ctypes as C
import sys
from pathlib import Path
from PIL import Image
SCRIPT_DIR=Path(__file__).resolve().parent
OUT=Path(sys.argv[2]) if len(sys.argv)>2 else SCRIPT_DIR
core=C.CDLL(str(SCRIPT_DIR/'libretro/snes9x_libretro.dll'))
class Info(C.Structure): _fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class Var(C.Structure): _fields_=[('key',C.c_char_p),('value',C.c_char_p)]
ENV=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p);VIDEO=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t);AUDIO=C.CFUNCTYPE(None,C.c_int16,C.c_int16);BATCH=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t);POLL=C.CFUNCTYPE(None);INPUT=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
variables={};dirs=C.create_string_buffer(str(OUT).encode());pixfmt=0;frame=0;lastframe=None
@ENV
def env(cmd,data):
 global pixfmt
 if cmd in (9,30,31): C.cast(data,C.POINTER(C.c_char_p))[0]=C.cast(dirs,C.c_char_p);return True
 if cmd==10: pixfmt=C.cast(data,C.POINTER(C.c_int))[0];return pixfmt in (0,1,2)
 if cmd==15:
  v=C.cast(data,C.POINTER(Var)).contents;v.value=variables.get(v.key);return bool(v.value)
 if cmd==16:
  vv=C.cast(data,C.POINTER(Var));i=0
  while vv[i].key:
   variables[vv[i].key]=vv[i].value.split(b'; ')[-1].split(b'|')[0];i+=1
  return True
 if cmd==17: C.cast(data,C.POINTER(C.c_bool))[0]=False;return True
 if cmd==3: C.cast(data,C.POINTER(C.c_bool))[0]=False;return True
 if cmd in (18,37):return True
 return False
@VIDEO
def video(data,w,h,pitch):
 global lastframe
 if data and data != C.c_void_p(-1).value: lastframe=(C.string_at(data,pitch*h),w,h,pitch,pixfmt)
@AUDIO
def audio(a,b):pass
@BATCH
def batch(d,n):return n
@POLL
def poll():pass
@INPUT
def inp(port,device,index,ident):
 if port!=0:return 0
 if ident==3 and (1100<=frame<1110):return 1
 if ident==8 and (1300<=frame<1310):return 1
 if ident==8 and (1500<=frame<1510):return 1
 return 0
for name,fn,typ in [('environment',env,ENV),('video_refresh',video,VIDEO),('audio_sample',audio,AUDIO),('audio_sample_batch',batch,BATCH),('input_poll',poll,POLL),('input_state',inp,INPUT)]:
 f=getattr(core,'retro_set_'+name);f.argtypes=[typ];f(fn)
core.retro_init()
core.retro_load_game.argtypes=[C.POINTER(Info)];core.retro_load_game.restype=C.c_bool
rom_path=Path(sys.argv[1]) if len(sys.argv)>1 else SCRIPT_DIR.parent/'Albert Odyssey.sfc'
rom=rom_path.read_bytes();buf=C.create_string_buffer(rom);game=Info(str(rom_path).encode(),C.cast(buf,C.c_void_p),len(rom),None)
assert core.retro_load_game(C.byref(game))
core.retro_get_memory_size.argtypes=[C.c_uint];core.retro_get_memory_size.restype=C.c_size_t
core.retro_get_memory_data.argtypes=[C.c_uint];core.retro_get_memory_data.restype=C.c_void_p
core.retro_serialize_size.restype=C.c_size_t;core.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_serialize.restype=C.c_bool
print('Memory sizes',[(k,core.retro_get_memory_size(k)) for k in range(4)])
def capture():
 for k in [2,3]:
  size=core.retro_get_memory_size(k);ptr=core.retro_get_memory_data(k)
  if size and ptr:(OUT/f'frame{frame:04d}_mem{k}.bin').write_bytes(C.string_at(ptr,size))
 size=core.retro_serialize_size();bb=C.create_string_buffer(size)
 if core.retro_serialize(bb,size):(OUT/f'frame{frame:04d}.state').write_bytes(bb.raw)
 if lastframe:
  raw,w,h,pitch,fmt=lastframe
  im=Image.new('RGB',(w,h));pixels=im.load()
  for y in range(h):
   for x in range(w):
    n=int.from_bytes(raw[y*pitch+x*(4 if fmt==1 else 2):y*pitch+x*(4 if fmt==1 else 2)+(4 if fmt==1 else 2)],'little')
    if fmt==1:r,g,b=(n>>16)&255,(n>>8)&255,n&255
    elif fmt==2:r,g,b=((n>>11)&31)*255//31,((n>>5)&63)*255//63,(n&31)*255//31
    else:r,g,b=((n>>10)&31)*255//31,((n>>5)&31)*255//31,(n&31)*255//31
    pixels[x,y]=(r,g,b)
  im.resize((w*3,h*3),Image.Resampling.NEAREST).save(OUT/f'frame{frame:04d}.png')
for frame in range(5001):
 core.retro_run()
 if frame in [1200,1500,2000,3000,4000,5000]:capture();print('captured',frame,flush=True)
core.retro_unload_game();core.retro_deinit()
