"""Merge completed runtime shards and publish a hash-bound release report."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'analysis/opening_review_20260911'
rom=ROOT/'Albert Odyssey - Korean Full.sfc'
sha=hashlib.sha256(rom.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
records=read(ROOT/'analysis/full_dialogue_extracted.json')['records']
results=[]
for part in (0,1):
    report=read(out/f'audit{part}/report.json')
    assert report['rom_sha256']==sha and not report['failures']
    assert not (out/f'audit{part}/watchdog_failure.json').exists()
    results.extend(report['results'])
assert len(results)==len(records)==1428
assert {r['offset'] for r in results}=={r['offset'] for r in records}
assert all(r['width']==r['cells']//4+1 for r in results)
assert (out/'route/rom_sha256.txt').read_text().strip()==sha
opening=read(out/'opening/report.json')
assert opening['rom_sha256']==sha
assert len(opening['natural_scene_checks'])==2
assert all(not c['glyph_mismatches'] for c in opening['natural_scene_checks'])
assert opening['natural_scene_checks'][1]['caption_stays_in_row']
assert read(out/'static.json')['rom_sha256']==sha
assert (out/'roundtrip.sfc').read_bytes()==rom.read_bytes()
report={'rom_sha256':sha,'cases':len(results),'failures':[],
        'scope':'Each translated record rendered twice through actual width calculation and dismissed with A; not all event branches',
        'results':sorted(results,key=lambda r:int(r['offset'],16))}
(out/'runtime_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
review=read(out/'review.json')
assert len(review)==41 and sum(r['changed'] for r in review)==11
active={r['offset']:r['korean'] for r in records}
assert all(active[r['offset']]==r['after'] for r in review)
table=['# 오프닝 과거 이야기 원문 재검수','',
       '2026-09-11. 일본어 ROM에서 추출한 원문과 오프닝 41개 레코드를 대조하여 11곳을 수정했다.', '',
       '「騎士団の名にかけて」는 기사단의 이름·명예를 건다는 뜻이다. 기존 빌드는 “기사단의 이름을 걸고!”였으며, 개인 기사의 이름으로 읽히지 않도록 “기사단의 명예를 걸고!”로 다듬었다.', '',
       '슬레이가 부하에게 하는 「戻ろう」의 말투와 「ふたりで」의 의미, 「むすめさんのためにも」의 “따님을 위해서라도”를 복원했다. 「決戦」은 “결전”으로, 「団長」은 “단장님”으로 맞췄다.', '',
       '| 주소 | 일본어 원문 | 이전 번역 | 최종 번역 | 수정 |',
       '|---|---|---|---|---|']
for r in review:
    table.append('| '+' | '.join([r['offset'],r['japanese'],r['before'],r['after'],'수정' if r['changed'] else '유지'])+' |')
(out/'검수결과.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
body=f'''# 오프닝 과거 이야기 재검수 빌드

2026-09-11

과거 이야기 41개 레코드를 일본어 원문과 대조하고 11곳을 수정했다. “기사단의 이름을 걸고!”를 “기사단의 명예를 걸고!”로 다듬고, 슬레이의 부하에 대한 말투와 누락된 의미를 복원했다. 번역을 억지로 줄이지 않았으며, 원래 레코드·페이지·이벤트 포인터를 유지했다.

실제 오프닝 검수 중 발견한 두 가지 표시 문제도 수정했다. VBlank 끝자락에서 폰트를 복사해 “명” 대신 이전 글자 “폭”이 남는 문제는 남은 전송 시간을 확인하도록 고쳤다. 충분한 시간이 있으면 현재 VBlank를 그대로 사용하므로 메뉴 항목마다 무조건 한 프레임을 더 기다리지 않는다. 전투 자막은 원래 시작 열에 긴 번역을 더하면 다음 줄로 넘어갈 수 있어, 32칸 안에 전체 문장이 들어오도록 시작 열을 조정한다.

- [실행 ROM](./Albert%20Odyssey%20-%20Korean%20Full.sfc)
- [원본 일본어 ROM용 xdelta](./Albert%20Odyssey%20-%20Korean%20Full.xdelta)
- 크기: 2,097,152바이트
- SHA-256: `{sha}`

## 이번 ROM에서 다시 확인한 내용

- 전체 번역 1,428개를 실제 Snes9x libretro에서 각각 두 줄로 표시하고 A 버튼으로 닫았다. 글리프·테두리 불일치, 대화창 버퍼 경계 손상, 페이지 진행 실패, 프레임 반환 시간 초과: 0건.
- 창 폭이 실제 글자 수와 맞는지 1,428건 모두 확인했다. 최대 31칸의 긴 대사와 기존 넓은 창 처리를 유지한다.
- 새 게임 42,001프레임의 오프닝 캡처 및 기존 123단계 입력 경로를 재생했다. 교회 만남부터 교회 밖 이동과 필드 진행까지 확인했다.
- “기사단의 명예를 걸고!”와 31칸 전투 자막을 실제 해당 장면에서 VRAM 글리프와 비교했다. 긴 자막의 위·아래 타일이 한 행 안에 들어오는 것도 확인했다.
- 전체 대사 ROM 바이트·원본 포인터·은행 경계·폰트 복사 데이터를 검사했다. 테두리 예약 글리프, 투명 지우기 타일과 넓은 창 훅도 통과했다.
- 폰트 저장 용량 1,000자와 동시 표시 충돌 제약을 유지한다. 체크섬 및 xdelta 재적용 결과가 정상이며, 재적용 ROM은 배포 ROM과 바이트 단위로 일치한다.

이는 모든 게임 분기를 끝까지 플레이한 검증은 아니다. 개별 대사 전수 검사와 실제 실행한 오프닝·초반 이동 경로를 구분한다. 이전 버전의 강제 저장 대신 새 게임 또는 게임 내 저장으로 시작한다. 원본 ROM과 기존 세이브는 수정하지 않았다.

## 검사 자료

- [41개 원문 대조표](analysis/opening_review_20260911/검수결과.md)
- [1,428개 실행 검사 결과](analysis/opening_review_20260911/runtime_report.json)
- [정적 검사 결과](analysis/opening_review_20260911/static.json)
- [오프닝 캡처 기록](analysis/opening_review_20260911/opening/report.json)
- [명예 문구 실제 화면](analysis/opening_review_20260911/opening/frame6500.png)
- [31칸 전투 자막 실제 화면](analysis/opening_review_20260911/opening/frame17000.png)
- [교회 이벤트 캡처](analysis/opening_review_20260911/route/frame0032.png)
- [새 게임 입력 기록](analysis/opening_review_20260911/route/steps.jsonl)

직전 정상 ROM과 패치는 `analysis/opening_review_20260911/before_review.zip`에 보관했다.
'''
(ROOT/'재빌드결과.md').write_text(body,encoding='utf-8')
readme=ROOT/'font_export/README.md'
old=readme.read_text(encoding='utf-8')
readme.write_text(f'''# 알버트 오디세이 1 한글 패치

**2026-09-11 오프닝 과거 이야기 재검수 빌드:** 41개 레코드를 대조해 11곳을 수정했다. “기사단의 명예를 걸고!”로 표현을 다듬고, 전체 1,428개 대사의 표시·닫기와 메모리 경계를 다시 검사했다. 새 게임 오프닝·교회·필드 진행을 재생했다. 모든 게임 분기의 완료 검증은 아니다.

최신 SHA-256: `{sha}`. [최신 빌드 내역](../재빌드결과.md). 아래 과거 실행 기록은 각 보고서의 해시와 범위를 구분한다.

## 빌드''' + old.split('## 빌드',1)[1],encoding='utf-8')
assert (out/'roundtrip.sfc').resolve().is_relative_to(out.resolve())
(out/'roundtrip.sfc').unlink()
for path in (out/'opening').glob('caption_*'):
    assert path.resolve().is_relative_to(out.resolve()) and path.is_file()
    path.unlink()
for path in (out/'diagnose').glob('*'):
    if path.is_file():
        assert path.resolve().is_relative_to(out.resolve())
        path.unlink()
if (out/'diagnose').exists():
    (out/'diagnose').rmdir()
diagnostic_script=ROOT/'analysis_font_scan/diagnose_opening.py'
diagnostic_script.unlink(missing_ok=True)
print(json.dumps({'reviewed':41,'changed':11,'runtime_cases':1428,'failures':0,'sha256':sha}))
