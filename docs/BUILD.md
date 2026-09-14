# 제작 소스 안내

Python 3.13, Pillow, Windows의 `C:/Windows/Fonts/gulim.ttc`를 사용한 작업 소스입니다. 원본 ROM은 README에 지정된 이름으로 저장소 루트에 별도 준비합니다.

1. `python font_export/expand_font_space.py`
2. `python font_export/build_korean_full_patch.py`

`analysis/Albert_Odyssey_translation.asm`은 기존 Peter Lemon(krom)의 영문 번역 분석 자료를 참조하는 입력입니다. 원래 작성자 표기를 보존했습니다. 한국어 최종 덮어쓰기는 `font_export/review_fixes.json`과 빌더를 확인하세요.

런타임 검사에는 별도 Snes9x libretro DLL을 `analysis_font_scan/libretro/snes9x_libretro.dll`에 준비해야 합니다. 일부 검사 도구는 기존 로컬 시험 산출물·경로를 전제로 하므로 환경에 맞게 설정해야 합니다. 바이너리·세이브·추출 자원은 배포하지 않으며 필요한 자료는 원본에서 추출 도구로 생성하세요. 공개 시점에는 패치 적용 왕복 검증을 수행했으며, 공개 폴더에서 소스 전체를 재빌드한 검증은 하지 않았습니다.
