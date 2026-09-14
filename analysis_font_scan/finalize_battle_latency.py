"""Publish only the release whose benchmarks and regression checks passed."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
out=ROOT/'analysis/battle_latency_20260911'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
rom=ROOT/'Albert Odyssey - Korean Full.sfc'
sha=hashlib.sha256(rom.read_bytes()).hexdigest()
baseline=hashlib.sha256((out/'before.sfc').read_bytes()).hexdigest()
records=read(ROOT/'analysis/full_dialogue_extracted.json')['records']
results=[]
for n in (0,1):
    report=read(out/f'audit{n}/report.json')
    assert report['rom_sha256']==sha and not report['failures']
    assert not (out/f'audit{n}/watchdog_failure.json').exists()
    results.extend(report['results'])
assert len(results)==1428 and {r['offset'] for r in results}=={r['offset'] for r in records}
assert all(r['width']==r['cells']//4+1 for r in results)
static=read(out/'static.json');assert static['rom_sha256']==sha
assert static['direct_rom_index_entries_checked']==32768
natural=read(out/'opening/report.json')
assert natural['rom_sha256']==sha and len(natural['checks'])==2
assert all(not r['glyph_mismatches'] and r['row_bounded'] and r['lower_tiles_match'] for r in natural['checks'])
assert (out/'after_route/rom_sha256.txt').read_text().strip()==sha
assert (out/'roundtrip.sfc').read_bytes()==rom.read_bytes()
measurements={}
seeds=set()
for version in ('original','before','after'):
    menu=read(out/f'menu_{version}/report.json');reaction=read(out/f'reaction_{version}/report.json')
    seeds.add(menu['seed_sha256']);seeds.add(reaction['seed_sha256'])
    assert menu['rom_sha256']==reaction['rom_sha256']
    if version=='after':assert menu['rom_sha256']==sha
    if version=='before':assert menu['rom_sha256']==baseline
    if version=='original':assert menu['original_font_restored_in_test_vram']
    measurements[version]={'info_window_complete_frame':menu['results'][0]['tilemap_change_frames'][-1],
                           'cursor_info_complete_frame':menu['results'][1]['tilemap_change_frames'][-1],
                           'next_input_cursor_frames':reaction['results'][0]['cursor_change_frames']}
assert len(seeds)==1
assert measurements['after']['info_window_complete_frame']<measurements['before']['info_window_complete_frame']
assert measurements['after']['cursor_info_complete_frame']<measurements['before']['cursor_info_complete_frame']
assert measurements['after']['next_input_cursor_frames']==measurements['original']['next_input_cursor_frames']
summary={'rom_sha256':sha,'baseline_sha256':baseline,'measurements':measurements,
         'method':'Same gameplay state; test-only cursor placement; original font restored in Japanese test VRAM. 2-frame inputs, 132-frame observation. Rendering completion is the last BG3 tilemap change for the settled information screen. Reaction sends A on frames 1-2 and Down on frames 13-14.',
         'all_dialogue_cases':1428,'all_dialogue_failures':0,
         'limitations':'Measured scenarios, not a universal speed or all-game-branches guarantee.'}
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'runtime_report.json').write_text(json.dumps({'rom_sha256':sha,'cases':1428,'failures':[],
    'scope':'Each record in the real balloon renderer with actual width, two copies and A dismissal; not all gameplay branches',
    'results':sorted(results,key=lambda r:int(r['offset'],16))},ensure_ascii=False,indent=2),encoding='utf-8')
table='| 측정 항목 | 일본어 원본 | 이전 패치 | 수정 패치 |\n|---|---:|---:|---:|\n'
for name,key in [('전투 유닛 정보창 표시 완료','info_window_complete_frame'),('커서 이동 후 정보 갱신 완료','cursor_info_complete_frame')]:
    table+='| '+name+' | '+' | '.join(str(measurements[v][key])+'프레임' for v in ('original','before','after'))+' |\n'
body=f'''# 전투 메뉴 반응 지연 개선 빌드

2026-09-11

메뉴와 전투 UI를 다시 그릴 때 번역 주소 1,428개를 매번 순서대로 검색하던 처리를 ROM 직접 조회표로 교체했다. 기존 2 MiB ROM의 빈 영역 64 KiB를 사용하며, 게임 RAM·세이브용 캐시를 추가하지 않는다. 번역, 폰트 배치, VBlank 여유 시간 검사, 대화창·전투 자막 경계 처리는 이전 빌드와 바이트 단위로 같다.

- [실행 ROM](./Albert%20Odyssey%20-%20Korean%20Full.sfc)
- [원본 일본어 ROM용 xdelta](./Albert%20Odyssey%20-%20Korean%20Full.xdelta)
- 크기: 2,097,152바이트
- SHA-256: `{sha}`

## 반응 속도 비교

{table}
메뉴를 연 뒤 13~14프레임에 아래 방향을 누르는 검사에서 이전 패치는 입력을 놓쳤다. 수정본과 원본은 모두 14프레임에 커서가 반응했다. 이는 특정 재현 장면의 입력·표시 지연 측정이며, 게임 전체 FPS를 측정한 수치가 아니다.

비교에는 같은 게임 진행 상태를 사용했다. 검사 전용 상태에서 커서만 알버트에게 맞췄고, 일본어 비교본의 VRAM에는 원본 폰트를 복원했다. 유닛 위치·능력치·이벤트 플래그와 배포 ROM은 조작하지 않았다. 커서 보조가 없는 새 게임 진행 재생은 별도로 수행했다.

## 안전성 확인

- 새 직접 주소표의 가능한 32,768개 항목을 모두 검사했다. 미번역 항목은 원래 파서로 돌아간다.
- 1,428개 대사를 실제 출력·닫기 검사했다. 글리프 불일치, 테두리 손상, 대화창 버퍼 경계 손상, 진행 실패: 0건.
- 오프닝의 “기사단의 명예를 걸고!” 및 31칸 전투 자막을 실제 표시되는 시점에 찾아 글리프와 위·아래 타일의 행 경계를 확인했다.
- 새 게임에서 교회 이벤트와 교회 밖 이동을 지나 필드까지 진행했다.
- 바뀐 ROM 바이트는 조회 래퍼·직접 주소표·체크섬 영역에 한정된다. 글자 전송 안전 조건과 번역 데이터는 그대로다.
- 정적 포인터·은행 경계·동시 표시 검사와 체크섬 검사를 통과했다. xdelta 재적용 결과가 배포 ROM과 완전히 같다.

모든 게임 분기를 끝까지 플레이한 검증은 아니다. 원본 ROM과 사용자 세이브는 변경하지 않았다. 새 ROM을 다시 열고 게임 내 저장으로 이어서 테스트한다.

## 검사 자료

- [측정 수치와 방법](analysis/battle_latency_20260911/summary.json)
- [전체 대사 실행 결과](analysis/battle_latency_20260911/runtime_report.json)
- [정적 검사](analysis/battle_latency_20260911/static.json)
- [변경 영역 검사](analysis/battle_latency_20260911/binary_scope.json)
- [오프닝 실제 장면 검사](analysis/battle_latency_20260911/opening/report.json)
- [교회 이벤트](analysis/battle_latency_20260911/after_route/frame0032.png)
- [교회 밖 이동](analysis/battle_latency_20260911/after_route/frame0044.png)
- [새 게임 입력 기록](analysis/battle_latency_20260911/after_route/steps.jsonl)

직전 ROM과 패치, 빌더는 `analysis/battle_latency_20260911/before.zip`에 보관했다.
'''
(ROOT/'재빌드결과.md').write_text(body,encoding='utf-8')
readme=ROOT/'font_export/README.md';old=readme.read_text(encoding='utf-8')
readme.write_text(f'''# 알버트 오디세이 1 한글 패치

**2026-09-11 전투 메뉴 반응 개선 빌드:** 번역 주소의 순차 검색을 ROM 직접 조회로 바꿨다. 같은 장면에서 정보창 표시 36→4프레임, 커서 이동 후 정보 갱신 46→15프레임을 확인했다. 게임 RAM과 폰트 전송 안전 조건을 유지하고 1,428개 대사의 표시·닫기 검사를 다시 통과했다.

최신 SHA-256: `{sha}`. [최신 빌드 내역](../재빌드결과.md). 아래 과거 기록은 각 보고서의 해시와 범위를 구분한다.

## 빌드'''+old.split('## 빌드',1)[1],encoding='utf-8')
for name in ('before.sfc','roundtrip.sfc'):
    path=out/name;assert path.resolve().is_relative_to(out.resolve());path.unlink()
for name in ('before','after'):
    folder=out/name
    for path in folder.glob('*'):
        assert path.resolve().is_relative_to(out.resolve()) and path.is_file()
        path.unlink()
    if folder.exists():folder.rmdir()
for version in ('original','before','after'):
    for kind in ('menu','reaction'):
        folder=out/f'{kind}_{version}'
        count=len(read(folder/'report.json')['results'])
        for path in folder.glob('frame*.png'):
            if int(path.stem[5:])>=count:
                assert path.resolve().is_relative_to(out.resolve());path.unlink()
print(json.dumps(summary,ensure_ascii=False))
