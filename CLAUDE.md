# pwm-showcase — 자산 대시보드 체험판 (공개 리포 · GitHub Pages)

## 무엇
- vvippwm 대시보드 세 화면(자산·텐배거·예측)을 가짜 숫자로 옮긴 정적 사이트. 총액 ₩1,000만 고정, 표본 종목만.
- `build/make_demo.py` 가 원본 화면을 복사하고 라이브 API 를 틀로 받아 `data/*.json` 을 새로 만든 뒤 `build/check.py` 로 검사한다.
- main 에 올리면 GitHub Pages 로 바로 게시된다. 설명 README.md, 계획 `docs/plans/`.

## 불변 규칙
- 이 리포는 공개다. 실제 자산 숫자·실제 보유 종목명·매매 일화·계좌번호·내부 주소·포트·사용자명을 어디에도 쓰지 않는다
  (이 파일·커밋 메시지·PR 포함).
- `check.py` 는 실명을 메모리에서만 모으고 개수만 출력한다 — 실명을 파일·화면에 찍는 디버깅을 하지 않는다.
- 하나라도 걸리면(종료 코드 1) 올리지 않는다. 새로 샌 모양을 찾으면 `check.py` 의 FORBIDDEN 에 패턴을 더한다.
- 생성물 `data/` 를 손으로 고치지 않는다 — `make_demo.py` 로 다시 만든다.

## 확인 방법
- 시험: `uv run --no-project --with pytest python -m pytest -q`
- 다시 만들기·검사: `python3 build/make_demo.py` (라이브 API 가 열린 맥 안에서만) · 검사만 `python3 build/check.py`

## 먼저 물을 것
- main 푸시·머지 — 곧바로 세상에 게시된다.
