from pathlib import Path
from PIL import Image
b=Path('Albert Odyssey.sfc').read_bytes()
def decode(pos):
 start=pos; out=bytearray()
 while len(out)<0x20000:
  h=b[pos];pos+=1
  if h==1:return bytes(out),pos
  seed=b[pos];pos+=1; t=[seed]
  for bit in range(7,0,-1):
   if h>>bit&1: t.append(seed)
   else: t.append(b[pos]);pos+=1
  if h&1:
   t=[sum(((t[x]>>(7-y))&1)<<(7-x) for x in range(8)) for y in range(8)]
  out.extend(t)
 raise ValueError('too long')
def render(buf,path,bpp=2):
 nt=len(buf)//(8*bpp);im=Image.new('RGB',(16*8,((nt+15)//16)*8))
 pal=[(0,0,0),(255,255,255),(100,100,100),(200,200,200)]
 for i in range(nt):
  for y in range(8):
   for x in range(8):
    v=sum(((buf[i*8*bpp+y*bpp+k]>>(7-x))&1)<<k for k in range(bpp))
    im.putpixel((i%16*8+x,i//16*8+y),pal[v])
 im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST).save(path)
if __name__=='__main__':
 for p in [0xc8000,0xc8bf6,0xc97a7,0xca3c2,0xca4a2]:
  buf,end=decode(p);print(hex(p),hex(end),hex(len(buf)))
  Path(f'analysis_compression/{p:06x}.bin').write_bytes(buf)
  render(buf,f'analysis_compression/{p:06x}.png')

