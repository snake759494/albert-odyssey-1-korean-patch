# 알버트 오딧세이 1 한글패치

슈퍼패미컴 일본판 알버트 오딧세이 1용 비공식 한국어 패치입니다. 전투와 이야기를 진행하는 RPG의 대사와 화면 정보를 한국어로 표시합니다. 현재 배포 버전은 **v1.0.0**입니다.

[최신 패치 다운로드](https://github.com/snake759494/albert-odyssey-1-korean-patch/releases/latest) · [제작 소스 안내](docs/BUILD.md) · [수정·검수 기록](재빌드결과.md)

대사·메뉴 한글화와 전투 메뉴·커서 지연 개선판입니다. 공격 선택 후 방향 메뉴가 표시되기까지 재현 장면에서 28→20프레임으로 개선했고 일본판은 19프레임이었습니다. 대사 1,428개 표시·닫기 검사와 새 게임 오프닝·교회 이벤트·필드 진입을 확인했습니다.

## 배포 구성

스타오션 1 프로젝트와 같은 구성으로 제작 소스·번역·검수 자료를 공개합니다. 릴리즈 직접 첨부 파일은 **`Albert.Odyssey.-.Korean.Full.xdelta` 하나**입니다. 원본·완성 ROM, 추출 바이너리·게임 글꼴 덤프·에뮬레이터·세이브 스테이트는 포함하지 않습니다. 자동 Source code ZIP/TAR는 공개 저장소 압축본입니다.

## 대상 원본과 확인값

수정되지 않은 일본판 `Albert Odyssey.sfc`에 적용하세요. 파일명보다 크기와 해시가 중요합니다. 복사기 헤더를 추가한 파일이나 이전 한글판에 덧씌우면 안 됩니다. 원본은 별도로 준비해야 합니다.

| 항목 | 값 |
| --- | --- |
| 원본 크기 | `1048576` |
| 원본 MD5 | `8822eb60ec69ede557c3294bae005b32` |
| 원본 SHA-256 | `abc9ee63a624dbabfd255774a254517a46be54c37aa26a89db2a299277548190` |
| xdelta 크기 | `62723` |
| xdelta MD5 | `9d4c4b9876b3aaf3a0590489e9c88de5` |
| xdelta SHA-256 | `57daeca98a2ca096429337e1d0e4b87dfc163ef02a8b2595d059ee2c38e3f719` |
| 결과 ROM 크기 | `2097152` |
| 결과 ROM MD5 | `a7d26211f76d8fe61ce4ee2a4c314ecd` |
| 결과 ROM SHA-256 | `5509b4d8afda2bc497c2245bd2824629a703eac907d65660347041ffba2f183b` |


## 적용 방법

1. 위 원본의 MD5와 SHA-256을 확인합니다. PowerShell: `Get-FileHash -Algorithm SHA256 -LiteralPath './Albert Odyssey.sfc'` (MD5는 알고리즘을 MD5로 변경).
2. xdelta3 지원 도구의 Apply Patch에서 Patch는 다운로드한 xdelta, Source는 원본 ROM으로 지정합니다.
3. Output은 원본과 다른 새 파일명으로 지정합니다.
4. 결과 SHA-256을 위 표와 비교합니다.
5. 게임을 완전히 종료하고 새 ROM을 여세요. 이전 버전의 에뮬레이터 강제 저장은 옛 코드·글꼴을 복원할 수 있으므로 게임 내 일반 저장으로 이어 하세요.

```powershell
.\xdelta3.exe -d -s './Albert Odyssey.sfc' './Albert.Odyssey.-.Korean.Full.xdelta' './Albert Odyssey - Korean Full.sfc'
python tools/apply_release.py --xdelta './xdelta3.exe' --source './Albert Odyssey.sfc' --patch './Albert.Odyssey.-.Korean.Full.xdelta' --output './new-korean.sfc'
```

두 명령은 대안입니다. 자체 적용 도구는 원본·패치·결과 해시를 검사하고 기존 출력 파일을 덮어쓰지 않습니다. xdelta 도구는 별도 준비하며 이 배포에 실행 파일은 포함하지 않습니다.

## 검증 범위와 제보

원본에 배포 xdelta를 적용한 결과가 완성 ROM과 바이트 단위로 일치함을 재확인했습니다. 상세한 검사 조건은 위 검수 기록을 참고하세요. **모든 분기·엔딩까지 완주한 검증이나 실제 슈퍼패미컴 기기 검증은 아닙니다.** 보고된 검사 수치는 모든 진행 상황에서 무오류라는 뜻이 아닙니다.

제보에는 버전, 결과 ROM SHA-256, 에뮬레이터 버전, 장소와 재현 순서, 강제 저장 사용 여부를 적어 주세요. ROM과 추출 바이너리는 이슈에 올리지 마세요.

## 권리

원작 게임의 권리는 원 권리자에게 있습니다. 공식 한국어판이 아닙니다. [권리·외부 자료 안내](RIGHTS.md)를 확인하세요.
