"""Decode every original bank-$88 pointer, independently of the partial EN script."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def chartable(number):
    result = {}
    for line in (ROOT / f'analysis/AOCharTable{number}.txt').read_text(encoding='utf-8-sig').splitlines():
        m = re.match(r'([0-9A-F])\|(.*)', line)
        if m:
            for col, ch in enumerate(m[2].split('\t')):
                result[int(m[1], 16) * 16 + col] = ch.strip() or ' '
    if number == 2:
        # Read from the original glyph sheet; the old transcription contains
        # several look-alike kanji errors and uses X for unlabelled glyphs.
        result.update({0x01:'抜',0x18:'…',0x32:'持',0x3C:'待',0x3D:'思',
                       0x3E:'考',0x3F:'親',0x46:'心',0x49:'中',0x4E:'測',
                       0x51:'日',0x56:'接',0x66:'異'})
    return result

def extract():
    rom = (ROOT / 'Albert Odyssey.sfc').read_bytes()
    tables = (chartable(1), chartable(2))
    known = {int(m, 16) for m in re.findall(r'TextStyle[12]\(\$([0-9A-Fa-f]+)', (ROOT/'analysis/Albert_Odyssey_translation.asm').read_text(encoding='utf-8'))}
    supplement = ROOT/'font_export/remaining_korean_translation.json'
    if supplement.exists():
        known.update(int(k,16) for k in json.loads(supplement.read_text(encoding='utf-8')))
    records = []
    for index in range(0xC52 // 2):
        pointer = int.from_bytes(rom[0x40000+index*2:0x40002+index*2], 'little')
        offset = 0x40000 + pointer - 0x8000
        if not 0x40C52 <= offset < 0x48000:
            continue
        header = rom[offset]
        count, kind = (header & 31) + 1, header >> 5
        if kind == 7:
            pairs = [(rom[offset+1+i*2], rom[offset+2+i*2]) for i in range(count)]
            size = 1+count*2
        else:
            positions = set(rom[offset+1:offset+1+kind])
            pairs = [(rom[offset+1+kind+i], int(i in positions)) for i in range(count)]
            size = 1+kind+count
        text = ''.join(tables[attr&1].get(code, f'<{attr&1}:{code:02X}>') for code,attr in pairs)
        records.append({'index':index,'offset':f'0x{offset:05X}','type':kind,'cells':count,'size':size,'japanese':text,'pairs':pairs,'translated':offset in known})
    return records

if __name__ == '__main__':
    records = extract()
    (ROOT/'analysis/all_rom_text.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'analysis/missing_translation.txt').write_text('\n'.join(f"{r['index']:04d} {r['offset']} {r['japanese']}" for r in records if not r['translated']),encoding='utf-8')
    missing_prose = [r for r in records if not r['translated'] and int(r['offset'],16)>=0x41B59 and 'X' not in r['japanese']]
    coverage = {'total_pointer_records':len(records),'translated_pointer_records':sum(r['translated'] for r in records),
                'untranslated_prose_candidates':len(missing_prose),'untranslated_prose_offsets':[r['offset'] for r in missing_prose],
                'complete':False,'note':'All pointer records include graphics and UI. Prose candidates require individual classification. Renderer tests are not a completeness check.'}
    (ROOT/'analysis/translation_coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print({'total':len(records),'known':sum(r['translated'] for r in records),'missing':sum(not r['translated'] for r in records)})
