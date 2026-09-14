"""Publish only after final-ROM timing, rendering, route and delta checks pass."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'analysis/facing_latency_20260911'
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def report(name):
    return read(OUT / name / 'report.json')

rom = (ROOT / 'Albert Odyssey - Korean Full.sfc').read_bytes()
sha = hashlib.sha256(rom).hexdigest()
assert (OUT / 'roundtrip.sfc').read_bytes() == rom
results = []
for n in range(2):
    audit = report(f'release_audit{n}')
    assert audit['rom_sha256'] == sha and not audit['failures']
    results.extend(audit['results'])
assert len(results) == 1428
for name in ('release_opening',):
    assert report(name)['rom_sha256'] == sha
assert (OUT / 'release_route/rom_sha256.txt').read_text().strip() == sha
assert read(OUT/'release_validation.json')['rom_sha256'] == sha
assert read(OUT/'static.json')['rom_sha256'] == sha

measurements = {}
for version, suffix in [('original','original'), ('before','before'), ('release','release')]:
    attack = report('attack_'+suffix)
    facing = report('end_'+suffix)
    opening = report('open_'+suffix)
    field = report('field_'+suffix)
    movement = report('cursor_'+suffix)
    measurements[version] = {
        'attack_direction_menu_frame': 2 + attack[-1]['tilemap_changes'][-1],
        'facing_menu_frame': 2 + facing[-1]['tilemap_changes'][-1],
        'action_menu_initial_frame': 2 + opening[-1]['tilemap_changes'][0],
        'action_menu_finished_frame': 2 + opening[-1]['tilemap_changes'][-1],
        'field_cursor_changes': [r['cursor_changes'] for r in field],
        'movement_cursor_changes': [r['cursor_changes'] for r in movement],
    }
for key in ('field_cursor_changes','movement_cursor_changes'):
    assert measurements['release'][key] == measurements['original'][key]
assert measurements['release']['attack_direction_menu_frame'] == 20
assert measurements['before']['attack_direction_menu_frame'] == 28
assert measurements['original']['attack_direction_menu_frame'] == 19
for name in ('attack_release','end_release','open_release','field_release','cursor_release','attack_play_release'):
    assert read(OUT/name/'context.json')['rom_sha256'] == sha

summary = {
    'rom_sha256': sha,
    'measurements': measurements,
    'unit': 'emulated frames after input starts, not host FPS',
    'method': 'Shared gameplay save states. Test VRAM font restored for each ROM. Attack test moves one enemy adjacent in test RAM only; no stats, flags or release ROM edits. Natural boot/route checked separately.',
    'runtime_text_records_checked': len(results),
    'runtime_text_failures': 0,
    'xdelta_roundtrip': 'identical',
    'scope': 'Measured actions, full text renderer/dismissal and opening/church/field route; not all gameplay branches.'
}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'runtime_report.json').write_text(json.dumps({'rom_sha256':sha,'cases':1428,'failures':[],
    'results':sorted(results,key=lambda r:int(r['offset'],16))},ensure_ascii=False,indent=2),encoding='utf-8')

body = f'''# 전투 공격 메뉴·커서 지연 개선 빌드

2026-09-11

첨부된 ‘이동·공격·시전·끝내기’ 메뉴에서 공격을 선택할 때의 대기를 수정했다. 반복 갱신되는 ‘간접 공격’의 ‘접’, ‘공격력’의 ‘력’을 고정 폰트로 유지해 매번 화면 갱신을 기다리며 전송하던 처리를 없앴다. 고정 글자로 구성된 메뉴는 폰트 전송 준비도 건너뛴다. 동적 글자 전송은 고정 크기 복사로 단순화했다.

원본 지형 글자 중 한국어 지형 표로 교체되어 사용하지 않는 두 칸($106, $110)을 재활용했다. 글자 슬롯은 264→266칸, 전역 보호 글자는 183→185자로 늘었다. ROM의 1,000자 폰트 저장 공간, 원래 게임 RAM·SRAM, VBlank 안전 여유, 대화창·자막 경계 처리는 유지했다.

- [실행 ROM](./Albert%20Odyssey%20-%20Korean%20Full.sfc)
- [일본어 원본용 xdelta](./Albert%20Odyssey%20-%20Korean%20Full.xdelta)
- 크기: 2,097,152바이트
- SHA-256: `{sha}`

## 측정 결과

| 항목 | 일본어 원본 | 직전 작업본 | 수정본 |
|---|---:|---:|---:|
| 공격 선택 후 방향 메뉴 표시 | 19프레임 | 28프레임 | 20프레임 |
| 끝내기 선택 후 방향 메뉴 표시 | 18프레임 | 20프레임 | 19프레임 |
| 행동 메뉴 최초 표시 | 4프레임 | 4프레임 | 4프레임 |
| 행동 메뉴 계산·표시 완료 | 70프레임 | 70프레임 | 70프레임 |
| 필드 커서: 좌우 각 120프레임 동안 이동 횟수 | 26회 | 25회 | 26회 |

수정본은 필드 커서와 이동 범위 커서의 좌표가 바뀌는 모든 측정 프레임이 원본과 일치했다. 공격 메뉴 지연은 약 29% 줄었고, 원본과는 1프레임 차이가 남는다. 이는 재현 장면의 입력·표시 지연이며 전체 게임의 FPS 측정은 아니다.

같은 게임 진행 상태에 같은 입력을 보냈다. 버전별 폰트는 검사 VRAM에 복원했다. 공격 검사는 적 한 마리의 위치만 검사 RAM에서 인접 칸으로 옮겼다. 능력치·이벤트 플래그·배포 ROM은 이 보조 조작으로 바꾸지 않았다. 별도의 새 게임 경로는 이런 보조 조작 없이 진행했다.

## 확인한 내용

- 공격 선택, 공격 진행, 행동 메뉴 복귀를 확인했다.
- 새 게임에서 오프닝, 교회 만남 이벤트, 교회 밖 이동, 필드 행동 메뉴를 확인했다.
- 대사 1,428개를 실제 표시하고 A 버튼으로 닫았다. 글자 불일치·테두리 손상·대화창 버퍼 경계 손상·닫기 실패는 0건이다.
- 오프닝 ‘기사단의 명예를 걸고!’와 31칸 전투 자막의 글리프 및 행 경계를 확인했다.
- 원본 포인터 표, 18개 아이콘, 배경 지우기 타일, 보호 폰트, 은행 경계, 글자 동시 표시 검사를 통과했다.
- 원래 게임 코드 영역은 지형 표시 데이터와 체크섬을 제외하고 직전 작업본과 같다. 새 RAM/SRAM 캐시를 추가하지 않았다.
- xdelta를 원본에 다시 적용한 ROM이 배포 ROM과 완전히 일치한다.

모든 게임 분기를 끝까지 플레이한 검증은 아니다. 폰트 배치가 바뀌었으므로 ROM을 새로 열고 **게임 내 저장(SRAM)**으로 이어서 테스트한다. 이전 버전에서 만든 에뮬레이터 강제저장(state)은 이전 폰트와 화면 메모리를 복원하므로 사용하지 않는다.

## 검사 자료

- [측정값·방법](analysis/facing_latency_20260911/summary.json)
- [전체 대사 실행 검사](analysis/facing_latency_20260911/runtime_report.json)
- [정적 데이터 검사](analysis/facing_latency_20260911/release_validation.json)
- [변경 영역 검사](analysis/facing_latency_20260911/binary_scope.json)
- [공격 방향 메뉴](analysis/facing_latency_20260911/attack_release/frame0003.png)
- [공격 후 메뉴 복귀](analysis/facing_latency_20260911/attack_play_release/frame0004.png)
- [교회 이벤트](analysis/facing_latency_20260911/release_route/frame0032.png)
- [새 게임 행동 메뉴](analysis/facing_latency_20260911/release_route/frame0065.png)
- [오프닝 검사](analysis/facing_latency_20260911/release_opening/report.json)

직전 ROM·xdelta·빌더·보고서는 `analysis/facing_latency_20260911/before.zip`에 보관했다.
'''
(ROOT/'재빌드결과.md').write_text(body,encoding='utf-8')
readme=ROOT/'font_export/README.md'
old=readme.read_text(encoding='utf-8')
readme.write_text(f'''# 알버트 오디세이 1 한글 패치

**2026-09-11 공격 메뉴·커서 추가 개선:** ‘접’과 ‘력’을 상주시켜 반복 폰트 전송을 없앴다. 같은 장면에서 공격 방향 메뉴 28→20프레임(원본 19), 필드·이동 범위 커서의 이동 프레임은 원본과 일치했다. 1,428개 대사 출력·닫기 검사를 통과했다.

최신 SHA-256: `{sha}`. [최신 빌드 내역](../재빌드결과.md). ROM을 다시 열고 게임 내 저장으로 이어서 플레이한다. 이전 강제저장(state)은 사용하지 않는다.

## 빌드'''+old.split('## 빌드',1)[1],encoding='utf-8')
print(json.dumps({'sha256':sha,'text_cases':1428,'failures':0,'attack_frames':20}))
