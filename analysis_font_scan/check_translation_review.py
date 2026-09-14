"""Verify the source review without launching a game or overwriting a ROM."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'analysis/translation_review_20260910'
sys.path.insert(0, str(ROOT / 'font_export'))
import build_korean_full_patch as build


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


with zipfile.ZipFile(OUT / 'before_review.zip') as backup:
    before = json.loads(backup.read('analysis/full_dialogue_translations.json'))
    before_rom = backup.read('Albert Odyssey - Korean Full.sfc')

records, fixed_sources = build._source_records()
assert set(build.STYLE1_KO) == {r['offset'] for r in records if r['style'] == 1}
assert set(build.STYLE2_KO) == {r['offset'] for r in records if r['style'] == 2}
assert len({r['offset'] for r in records}) == len(records) == 1428
old = {r['offset']: r for r in before['records']}
active = {}
pool_size = 0
for r in records:
    key = f"0x{r['offset']:05X}"
    text = (build.STYLE1_KO if r['style'] == 1 else build.STYLE2_KO)[r['offset']]
    assert r['style'] == old[key]['style'], key
    prefix = 2 if key in build.REVIEW_FIXES['equipment'] else 0
    assert 0 < len(text) + prefix <= 31, (key, text)
    if prefix:
        assert len(text) + prefix <= 11, (key, text)
    assert not any('\u3040' <= c <= '\u30ff' or '\u3400' <= c <= '\u9fff' or c == '\ufffd' for c in text)
    assert all('가' <= c <= '힣' or c in build.ASCII_TABLE1 or c in build.ASCII_TABLE2 for c in text)
    size = 3 + 2 * (len(text) + prefix)
    if (pool_size & 0x7fff) + size > 0x8000:
        pool_size += 0x8000 - (pool_size & 0x7fff)
    pool_size += size
    active[key] = text

assert pool_size <= build.TEXT_POOL_END - build.TEXT_POOL_OFFSET
for key, text in build.REVIEW_FIXES['source_comparison_20260910'].items():
    assert active[key] == text, ('override did not reach its original record', key)

fixed = []
for item in before['fixed_names']:
    offset = int(item['offset'], 16)
    text = build.STYLE5_KO[offset]
    source = fixed_sources[offset]
    pair_mode = len(source) % 2 == 0 and all(source[i + 1].isdigit() for i in range(0, len(source), 2))
    capacity = len(source) // 2 if pair_mode else len(source)
    assert len(text) <= capacity
    fixed.append({'offset': item['offset'], 'before': item['korean'], 'after': text,
                  'capacity': capacity, 'changed': text != item['korean']})

rows = []
for r in build.ALL_ROM_RECORDS:
    previous = old.get(r['offset'], {}).get('korean')
    current = active.get(r['offset'])
    status = 'no_korean_entry' if current is None else ('corrected' if previous != current else 'reviewed_unchanged')
    rows.append({'index': r['index'], 'offset': r['offset'], 'japanese_decoded': r['japanese'],
                 'korean_before': previous, 'korean_after': current, 'review_status': status})
assert len(rows) == 1577
changed = [r for r in rows if r['review_status'] == 'corrected']
missing_ui = [r for r in rows if r['review_status'] == 'no_korean_entry'
              and 'X' not in r['japanese_decoded']
              and any('\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9fff' for c in r['japanese_decoded'])]
try:
    _, font_info = build.build_glyph_maps()
    font_result = {'status': 'pass', 'layout': font_info['layout']}
except ValueError as exc:
    font_result = {'status': 'blocked', 'reason': str(exc)}

rom = (ROOT / 'Albert Odyssey - Korean Full.sfc').read_bytes()
built = '--built' in sys.argv
if built:
    release = json.loads((OUT / 'release_validation.json').read_text(encoding='utf-8'))
    assert release['rom_sha256'] == hashlib.sha256(rom).hexdigest()
    assert font_result['status'] == 'pass'
else:
    assert rom == before_rom, 'Use --built after release verification for the rebuilt ROM'
result = {
    'review_scope': 'Every extracted Japanese pointer record and every existing Korean translation; static text review only',
    'source_pointer_records': len(rows), 'translated_pointer_records_reviewed': len(active),
    'changed_pointer_records': len(changed),
    'fixed_names_reviewed': len(fixed), 'fixed_names_corrected': sum(x['changed'] for x in fixed),
    'max_visible_cells': max(len(s) + (2 if o in build.REVIEW_FIXES['equipment'] else 0) for o, s in active.items()),
    'text_pool_bytes': pool_size, 'text_pool_capacity': build.TEXT_POOL_END - build.TEXT_POOL_OFFSET,
    'hangul_count': len({c for s in [*active.values(), *build.STYLE5_KO.values()] for c in s if '가' <= c <= '힣'}),
    'font_storage_capacity': build.FONT_RESERVED_SLOTS,
    'record_styles_preserved': True, 'translation_override_routing': 'pass',
    'equipment_widths_and_fixed_footprints': 'pass', 'font_allocation': font_result,
    'rom_rebuilt': built, 'game_executed': False,
    'existing_rom_sha256': hashlib.sha256(rom).hexdigest(),
    'no_korean_entry_records': len(rows) - len(active),
    'untranslated_japanese_ui_candidates': missing_ui,
}
save('validation.json', result)
save('전수대조.json', {'verification': result, 'records': rows, 'fixed_names': fixed})

def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')

lines = [
    '# 일본어 원문 대조 검수 — 2026-09-10', '',
    f"원문 포인터 {len(rows):,}개를 읽고, 기존 번역 {len(active):,}개를 대조하여 {len(changed)}개를 수정했다. "
    f"별도 고정 장비명 {len(fixed)}개도 대조해 {sum(x['changed'] for x in fixed)}개를 수정했다.", '',
    '주요 수정은 고르트 왕의 상태·슬레이를 찾는 조건·초반 침략 사건의 설명, 상점과 조작 안내, '
    '마비 상태 메시지, 귀환 아이템 및 장비 이름이다. 인물 이름 뒤에 잘못 붙던 조사도 정리했다.', '',
    '번역은 `font_export/review_fixes.json`의 `source_comparison_20260910`과 '
    '`font_export/full_korean_translation.py`의 고정 장비명에 반영했다. '
    '검수 수정문을 원래 빌더의 TextStyle로 전달하도록 로더를 수정했다. '
    '원문 ROM의 타입만 사용하면 기존 TextStyle1 대사 10개에 TextStyle2 항목이 중복 생성되는 문제가 있었다. '
    '대사 순서·포인터·원래 빌더의 TextStyle은 그대로다.', '',
    f"정적 검사: 최대 {result['max_visible_cells']}칸, 대사 풀 {pool_size:,}/{result['text_pool_capacity']:,}바이트, "
    f"한글 {result['hangul_count']}/1,000자. 장비명은 아이콘 포함 11칸, 고정 이름은 각 원래 바이트 영역 안에 들어간다.", '',
    ('**ROM 반영 및 재빌드 완료.** 사용처를 확인한 한자 7칸을 회수해 표시 슬롯을 264칸으로 늘렸다. '
     '원래의 동시 표시 제약을 유지한 채 모든 대사 데이터와 폰트 복사 목록을 재검사했다. '
     '게임 실행 검증은 하지 않았다.' if built else
    '**ROM에는 아직 반영하지 않았다.** 안전한 표시용 폰트 슬롯은 257칸인데 수정문은 264칸이 필요하다. '
    '이는 ROM의 1,000자 글꼴 저장 용량과 별개인 동시 표시 제약이다. '
    '번역의 뜻을 줄이거나 배경·아이콘 슬롯을 재사용하지 않았다. 기존 ROM은 백업과 바이트 단위로 같다. '
    '폰트 배치 문제를 해결한 후 재빌드해야 한다. 이번 검수에서는 게임을 실행하지 않았다.'), '',
    '원문 디코딩표에는 오독이 있어 원래 추출 문자열을 그대로 보존했다. '
    '`source_ambiguous_glyphs.png`의 실제 원본 글꼴로 대기 메뉴(待機する), 확대 지도, '
    '이상 없음 문구 등을 확인했다. `source_ambiguous_glyphs2.png`에는 성지와 섬 관련 원문이 있다. '
    '실제 게임 화면 캡처가 아니라 원본 글리프를 조합한 자료다.', '',
    '기존 번역이 없는 149개 레코드도 함께 살폈다. 테두리·아이콘·영문 크레딧·숫자 외에 '
    '일본어 UI 후보가 남아 있으므로 이를 전부 그래픽이라 제외하지 않았다. 아래에 별도 기록했다.', '',
    '## 수정 대조표', '', '| 주소 | 일본어 추출 원문 | 이전 번역 | 수정 번역 |', '|---|---|---|---|',
]
lines += ['| ' + ' | '.join(cell(r[k]) for k in ('offset', 'japanese_decoded', 'korean_before', 'korean_after')) + ' |' for r in changed]
lines += ['', '## 고정 장비명 수정', '', '| 주소 | 이전 | 수정 |', '|---|---|---|']
lines += ['| ' + ' | '.join(cell(r[k]) for k in ('offset', 'before', 'after')) + ' |' for r in fixed if r['changed']]
lines += ['', '## 기존 번역이 없는 일본어 UI 후보', '', '추출표에서 `中`으로 읽힌 일부 칸은 테두리 글리프다. 디버그용 문구도 포함된다.', '', '| 주소 | 추출 문자열 |', '|---|---|']
lines += [f"| {r['offset']} | {cell(r['japanese_decoded'])} |" for r in missing_ui]
lines += ['', '재검사: `python analysis_font_scan/check_translation_review.py --built`', '',
          f"보존한 ROM SHA-256: `{result['existing_rom_sha256']}`", '']
(OUT / '검수결과.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'untranslated_japanese_ui_candidates'}, ensure_ascii=False))
