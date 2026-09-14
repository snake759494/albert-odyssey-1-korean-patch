from pathlib import Path
import capstone,sys
b=Path('Albert Odyssey.sfc').read_bytes()
start=int(sys.argv[1],16) if len(sys.argv)>1 else 0
end=int(sys.argv[2],16) if len(sys.argv)>2 else start+0x100
m=x=0
p=start
while p<end:
    mode=(32 if m else 0)|(64 if x or not m else 0)
    md=capstone.Cs(capstone.CS_ARCH_MOS65XX,mode)
    ins=next(md.disasm(b[p:p+4],((p>>15)|0x80)<<16|(p&0x7fff)|0x8000,count=1),None)
    if ins is None: p+=1;continue
    print(f'{p:06X} {ins.bytes.hex(" "):11s} {ins.mnemonic:5s} {ins.op_str}')
    if b[p]==0xc2:
        m=m or bool(b[p+1]&0x20);x=x or bool(b[p+1]&0x10)
    elif b[p]==0xe2:
        m=m and not bool(b[p+1]&0x20);x=x and not bool(b[p+1]&0x10)
    p+=2 if not x and b[p] in (0xa0,0xa2,0xc0,0xe0) else ins.size

