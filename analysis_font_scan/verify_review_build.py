"""Verify the shipped ROM, text renderer and fresh-boot background tests."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
rom=(root/'Albert Odyssey - Korean Full.sfc').read_bytes()
sha=lambda data:hashlib.sha256(data).hexdigest()
full=json.loads((root/'analysis_font_scan/ai_review/report.json').read_text(encoding='utf-8'))
assert not full['failures'] and full['rom_sha256']==sha(rom)
assert len(rom)==0x200000
assert int.from_bytes(rom[0x7FDE:0x7FE0],'little')==sum(rom)&65535
assert int.from_bytes(rom[0x7FDC:0x7FDE],'little')^int.from_bytes(rom[0x7FDE:0x7FE0],'little')==65535
assert sha((root/'Albert Odyssey.sfc').read_bytes())=='abc9ee63a624dbabfd255774a254517a46be54c37aa26a89db2a299277548190'
assert rom[0x108000+0x2A10:0x108000+0x2A20]==bytes(16)
info=json.loads((root/'font_export/korean_full_patch_info.json').read_text(encoding='utf-8'))
assert '0x51' not in info['glyphs']['table2'].values()
records=json.loads((root/'analysis/full_dialogue_extracted.json').read_text(encoding='utf-8'))['records']
assert all(int(t,16)!=0x151 for r in records for t in r['dynamic_targets'].values())
scenes=[]
for mode in ('title','story'):
 report=json.loads((root/f'analysis_font_scan/background_{mode}/report.json').read_text(encoding='utf-8'))
 assert report['rom_sha256']==sha(rom) and report['fresh_boot']
 assert not report['nontransparent_clear_tile_frames']
 scenes.append({'mode':mode,'frames':report['frames'],'captures':len(report['captures'])})
result={'final_rom_sha256':sha(rom),'size':len(rom),'checksum':'pass','original_unchanged':True,
        'full_runtime_cases':full['runtime_cases'],
        'static_character_checks':full['static_character_checks'],
        'background_clear_tile':'0x2A1','background_clear_glyph':'0x151',
        'excluded_from_font_and_dynamic_targets':True,'fresh_boot_scenes':scenes,
        'failures':[], 'limitations':'Fresh title/intro/battle route and record renderer tests; not an exhaustive playthrough.'}
(root/'analysis_font_scan/background_fix_after/build_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
