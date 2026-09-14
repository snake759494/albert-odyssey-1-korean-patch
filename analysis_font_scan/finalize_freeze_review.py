"""Publish the report only after the exhaustive renderer run has passed."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
rom = ROOT/'Albert Odyssey - Korean Full.sfc'
sha = hashlib.sha256(rom.read_bytes()).hexdigest()
audit = json.loads((ROOT/'analysis_font_scan/freeze_all/report.json').read_text(encoding='utf-8'))
assert audit['rom_sha256'] == sha and audit['cases'] == 1428 and not audit['failures']
assert (ROOT/'analysis_font_scan/freeze_route/rom_sha256.txt').read_text().strip() == sha
assert (ROOT/'analysis_font_scan/freeze_roundtrip.sfc').read_bytes() == rom.read_bytes()
text = f'''# 교회 프리징·대화창 손상 수정 빌드

2026-09-10

수정 전 ROM과 수정 후 ROM을 각각 새 게임으로 부팅하고 같은 123단계 버튼 입력을 재생했다. 수정 전에는 교회 만남의 32단계, “하지만 이제 내게서는 그 신비한 힘이 나오지 않아.”를 표시할 때 검은 화면으로 진행이 멈췄다. 수정 후에는 해당 대사, 남은 교회 이벤트, 교회 밖 이동과 필드 진행을 확인했다. 수정 전의 자동 재부팅 여부까지는 판정하지 않았다.

- 실행 ROM: [Albert Odyssey - Korean Full.sfc](./Albert%20Odyssey%20-%20Korean%20Full.sfc)
- 원본 일본어 ROM용 패치: [Albert Odyssey - Korean Full.xdelta](./Albert%20Odyssey%20-%20Korean%20Full.xdelta)
- 크기: 2,097,152바이트
- ROM SHA-256: `{sha}`

## 수정 내용

1. 28~31칸 대사가 원래 0~7까지만 있는 창 크기·꼬리 표의 8번 항목에 접근했다. 좌표 데이터를 포인터로 사용하는 경로를 차단하고, 기존 32×11타일 버퍼 안에서 그리는 넓은 창을 추가했다. 대사·줄·페이지·선택지 포인터와 번역 내용을 유지했다.
2. 말풍선 테두리가 직접 사용하는 글리프 0x168·0x169와 인접 0x16A를 폰트 할당에서 제외했다. 테두리 타일 0x2C8·0x2D8·0x2C9·0x2D9를 보존한다. 다른 미사용 한자 3칸을 회수해 표시 슬롯 264칸과 글리프 저장 용량 1,000자를 유지했다.
3. 기존 실행 검사는 포인터만 바꾸고 원본 창 폭 헤더를 그대로 사용했다. 새 검사는 실제 번역 길이로 창 폭을 계산하여 긴 대사의 경계 오류도 검사한다. 검사 전용 포인터 변경은 배포 ROM에 포함하지 않는다.

## 검증 결과와 범위

- 번역 레코드 1,428개를 각각 실제 Snes9x libretro에서 표시하고 A 버튼으로 닫았다. 글리프·테두리 불일치, 창 버퍼 경계 손상, 페이지 진행 실패: 0건. 프레임 반환 정지 감시 시간 초과: 0건.
- 같은 대사를 두 줄로 표시하는 검사 환경이다. 모든 실제 이벤트 조합과 모든 게임 분기를 실행한 결과는 아니다.
- 새 게임 자연 진행으로 음유시인 선택지, 교회 만남, 소피아 합류 후 교회 이탈, 필드 버튼 입력을 재생했다. ROM·이벤트 플래그·능력치 조작 없이 실행했다.
- 1,428개 대사의 ROM 바이트, 원본 포인터, 은행 경계, 폰트 복사 데이터를 재검사했다. 1,840개 동시 표시 그룹에서 4,448,388회 문자 소유 검사를 통과했다.
- 183개 보호 글리프, 18개 아이콘, 투명 지우기 타일, 테두리 예약과 넓은 창 훅을 확인했다.
- 체크섬과 원본 보존 검사를 통과했다. xdelta를 원본에 적용한 ROM이 배포 ROM과 바이트 단위로 일치했다.

이전 강제 저장 상태는 구형 VRAM과 폰트 배치를 포함한다. ROM을 다시 열고 새 게임 또는 게임 내 저장으로 시작한다. 기존 세이브와 원본 ROM은 변경하지 않았다.

## 검사 자료

- [전수 실행 결과](analysis_font_scan/freeze_all/report.json)
- [정적 데이터 결과](analysis/translation_review_20260910/release_validation.json)
- [교회 이전 버전 멈춤 화면](analysis_font_scan/freeze_route_before/frame0032.png)
- [같은 대사의 수정 후 화면](analysis_font_scan/freeze_route/frame0032.png)
- [교회 테두리 수정 후](analysis_font_scan/freeze_route/frame0020.png)
- [이벤트 이후 교회 밖 이동](analysis_font_scan/freeze_route/frame0044.png)
- [새 게임 입력 기록](analysis_font_scan/freeze_route/steps.jsonl)

```powershell
python font_export/build_korean_full_patch.py
python analysis_font_scan/static_build_check.py
python analysis_font_scan/verify_release_data.py
python analysis_font_scan/check_translation_review.py --built
python analysis_font_scan/freeze_audit.py
python analysis_font_scan/freeze_route_replay.py
```
'''
(ROOT/'재빌드결과.md').write_text(text,encoding='utf-8')
readme = ROOT/'font_export/README.md'
old = readme.read_text(encoding='utf-8')
marker = '## 빌드'
readme.write_text(f'''# 알버트 오디세이 1 한글 패치

**2026-09-10 교회 프리징·대화창 손상 수정 빌드:** 원본 창 크기 표를 벗어나는 긴 대사 처리를 수정하고 테두리 그래픽을 폰트 할당에서 보호했다. 1,428개 대사의 개별 표시·닫기 실행 검사를 통과했고, 새 게임에서 교회 이벤트와 이후 이동을 확인했다. 전체 게임 분기의 실행 검증을 뜻하지 않는다.

최신 ROM SHA-256: `{sha}`. 자세한 변경 사항과 재현 화면은 [재빌드결과.md](../재빌드결과.md)에 있다. 아래 과거 실행 기록은 각 보고서의 ROM 해시와 범위를 구분해서 읽는다.

''' + marker + old.split(marker,1)[1],encoding='utf-8')
# Keep the reproduction screenshots, scripts, reports and rollback archive.
# Discard duplicate test ROMs and transient memory dumps created by this audit.
scan = (ROOT/'analysis_font_scan').resolve()
discard = [scan/'freeze_roundtrip.sfc', scan/'freeze_before/baseline.sfc']
for name in ('freeze_before', 'freeze_focus', 'freeze_wide_after'):
    for pattern in ('frame*.state', 'frame*_mem2.bin', 'frame*_mem3.bin'):
        discard.extend((scan/name).glob(pattern))
for path in discard:
    assert path.resolve().is_relative_to(scan)
    path.unlink(missing_ok=True)
print(sha)
