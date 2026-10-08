# 보여주기용 복제 대시보드(pwm-showcase) — 계획 (2026-10-10)

출발점: 석호님 10-09 "지금 내가 갖고 있는 페이지를 그대로 하나 복제해서, 갖고 있는 금액만 1천만 원 고정으로 하나의 거짓 그래프와 함께 남들에게 내가 구축한 대시보드 형태를 보여주기에 좋은 웹사이트를 별도로".
원본 대시보드: `~/dev/vvippwm/dashboard/static/{index.html, tenbagger.html, forecast.html, quant.js, quant.css}` (10-10 신호등 3층 적용본). 라이브 API: `http://100.67.98.100:8787/api/…`(Tailscale 안에서만, **읽기만**).

## 한 줄 결론

**정적 사이트 하나**(서버 없음). 원본 HTML 세 장을 그대로 복사하고, 페이지 맨 위에서 `window.fetch` 를 가로채 `/api/…` 를 `./data/<slug>.json` 으로 바꾼다.
`data/` 는 **생성기 한 개**(`build/make_demo.py`, 파이썬 3.9 표준 라이브러리만)가 라이브 API 응답을 **모양 틀**로 받아 이름·돈·문장을 전부 갈아 끼운 것이다.
총액 ₩10,000,000 고정, 3개월 그래프는 매끈한 가짜 곡선(+8%), 종목은 실제 보유가 아니라 누구나 아는 표본(한국 12·미국 8·코인 3). 배포는 GitHub Pages(무료, 사람 손 없이 `gh` 로 켠다).

## 결정 사항 (석호님 답이 없어 권장안대로)

- 종목 이름은 **표본**(실제 보유 공개 안 함). 한국 12: 삼성전자 005930 · SK하이닉스 000660 · 현대차 005380 · 기아 000270 · NAVER 035420 · 카카오 035720 · LG에너지솔루션 373220 · 셀트리온 068270 · KB금융 105560 · POSCO홀딩스 005490 · KODEX 200 069500 · TIGER 미국S&P500 360750.
  미국 8: AAPL · MSFT · NVDA · GOOGL · AMZN · TSLA · SPY · QQQ. 코인 3: BTC · ETH · SOL.
  보유 밖 종목(후보 표·시나리오 종목 등)용 **2차 풀** 약 40개(한화에어로스페이스 · 두산에너빌리티 · LG전자 · 삼성SDI · 한미반도체 · 알테오젠 · 에코프로 · 크래프톤 · 삼성바이오로직스 · 현대모비스 · LG화학 · SK이노베이션 · 삼성물산 · 신한지주 · 하나금융지주 · 메리츠금융지주 · 한국전력 · KT&G · 아모레퍼시픽 · 엔씨소프트 · 펄어비스 · 카카오뱅크 · 카카오페이 · HMM · 대한항공 · 롯데케미칼 · S-Oil · 고려아연 · 포스코퓨처엠 · LG디스플레이 · 삼성전기 · LG이노텍 · DB하이텍 · 리노공업 · 이오테크닉스 · 주성엔지니어링 · 원익IPS · 솔브레인 · 동진쎄미켐 · 테스 / 미국 AMD · AVGO · META · NFLX · CRM · ORCL · ADBE · INTC · MU · ASML · TSM · ARM · PLTR · COIN · SMCI · VRT · ANET · LRCX · AMAT · KLAC).
  **풀에서 실제 보유 종목과 겹치는 이름은 실행 때 자동으로 뺀다**(아래 '새지 않게').
- 금액: 한국 총액 **₩10,000,000**(종목 ₩9,400,000 + 현금 ₩600,000) · 미국 **$8,000** · 코인 **₩1,000,000**. 3개월 곡선 +8%(출발 ₩9,260,000 → 끝 ₩10,000,000), 코스피 비교선 +5%, 미국 +6%, 코인 +12%. 1년·전체 구간도 같은 식(1년 +18%, 전체 +35%).
- 배포: **GitHub Pages**(공개 리포 `happydyoon/pwm-showcase`, 주소 `https://happydyoon.github.io/pwm-showcase/`). Cloudflare Pages + `demo.seokhoyoon.com` 은 맥에 Cloudflare 토큰·node 가 없어 사람 손(대시보드 클릭)이 필요 → 나중에 석호님이 원하면 리포만 연결하면 된다(리포 구조는 그대로 쓸 수 있다).
- 공개 리포에 올라가는 것: HTML 세 장 + quant.js/css + `data/*.json`(가짜) + 생성기. **실제 보유 목록·실제 API 응답·실명 사전은 절대 커밋하지 않는다**(생성기가 실행 때 라이브에서 읽고 메모리에서만 쓴다).

## 리포 구조

```
pwm-showcase/
├── index.html  tenbagger.html  forecast.html  quant.js  quant.css   ← 생성기가 원본에서 복사+패치(손으로 고치지 않는다)
├── demo.js            ← fetch 가로채기 + 체험판 띠 + 30초 갱신 끄기 (세 페이지가 맨 위에서 불러온다)
├── data/*.json        ← 생성기 산출물(가짜)
├── build/make_demo.py ← 생성기(3.9 표준 라이브러리만). 실행: python3 build/make_demo.py [--src ~/dev/vvippwm/dashboard/static] [--api http://100.67.98.100:8787]
├── build/check.py     ← 새는지 검사(실행 때 라이브에서 실명을 받아 data/·html 을 훑는다. 결과만 출력, 실명은 저장 안 함)
├── tests/test_showcase.py  ← pytest(표준 라이브러리 + pytest): 슬러그 함수 · 패치 전부 적중 · data 총액 · 띠 문자열
├── .nojekyll  README.md  docs/plans/  docs/history/
```

## 생성기 `build/make_demo.py` — 완료 기준

1. **복사+패치**: 원본 다섯 파일을 복사하고 문자열 치환으로 패치한다. 패치마다 "정확히 1회(또는 N회) 적중" 을 확인하고 아니면 **실패로 멈춘다**(원본이 바뀌면 바로 안다).
   - `<head>` 첫머리에 `<script src="./demo.js"></script>` 삽입(세 페이지). `href="/quant.css"`→`./quant.css`, `src="/quant.js"`→`./quant.js`, `href="/forecast"`→`./forecast.html`, `href="/tenbagger`→`./tenbagger.html`, `href="/"`(← 자산 대시보드)→`./index.html`.
   - `setInterval(load, 30000);` → 제거(또는 `if (!window.DEMO)` 로 감싼다). `<title>` 앞에 `[체험판] ` 붙임.
   - 데이터 안의 `url` 문자열(`/tenbagger#rule_card`, `http://100.67.98.100:8787/tenbagger#board` 등)은 생성기가 `./tenbagger.html#rule_card` 로 바꾼다(`http://100.67.98.100:8787` 는 어디에도 남지 않아야 한다).
2. **`demo.js`**: `window.DEMO = true`; `window.fetch` 를 감싸 인자가 `/api/` 로 시작하면 `./data/` + `slug(url)` + `.json` 을 대신 받는다. `slug` = `api/` 뒤 경로+쿼리를 `[^A-Za-z0-9]+` → `_` 로 바꾼 것(예 `series?range=3m` → `series_range_3m`, `stock?code=005930` → `stock_code_005930`, `quant?panel=perf&scope=kr` → `quant_panel_perf_scope_kr`). 파일이 없으면(404) `console.warn('DEMO missing', slug)` 후 `{}` 를 돌려준다. 페이지 맨 위에 고정 띠(`position:sticky; top:0`) `체험판 · 가상 데이터 — 실제 계좌가 아닙니다 · 총액 ₩1,000만 고정`(어두운 바탕에 노란 글씨, 폰에서도 한 줄). 생성기의 파이썬 `slug()` 와 **같은 규칙** — 테스트가 둘을 같은 입력으로 대조한다.
3. **받을 주소 목록**(라이브에서 하나씩 GET, 타임아웃 30초, 실패하면 그 슬러그는 건너뛰고 보고): `latest` · `ranking` · `series?range={1m,3m,6m,1y,all 중 index.html 의 range 버튼이 쓰는 값 전부}` · `board` · `changes?scope={kr,us,coin}` · `grade?scope={kr,us}` · `grade_history?scope={kr,us}&range={index.html 이 쓰는 값}` · `sectors` · `sectors?scope=us` · `us_book` · `risk` · `scorecard` · `action_scorecard` · `entry` · `growth` · `cashflows` · `cashflows?scope=us` · `trust?scope={kr,us}` · `benchmark?range=…&scope=…`(index.html 조합 전부) · `attribution?range=…&scope=…`(전부) · `quant?panel={quant.js 의 패널 id 전부}&scope={kr,us}` · `stock?code=<실제 상위 12 코드>`(→ 표본 코드 이름으로 저장) · `us_stock?sym=<실제 상위 8>`(→ 표본 심볼로 저장) · `whatif?scope=kr&fund=<라이브 응답 첫 항목>` 한두 개 · `tenbagger` · `forecast`. index.html·quant.js 를 읽어 실제로 부르는 조합을 뽑는다(추측 금지).
4. **변환 규칙**(JSON 을 재귀로 걸으며 적용, 순서대로):
   - **이름 사전**: `ranking.items` 비중 상위 12 → 한국 표본 12(비중 순으로 1:1), `us_book` 상위 8 → 미국 표본, 코인 3 → 코인 표본. 그 밖에 등장하는 실제 종목(`tenbagger.candidates`·`forecast.scenarios[].tickers`·`holdings`·`entry_board` 등에서 `code`/`name` 쌍으로 보이는 것 전부)은 2차 풀에서 순서대로 배정. 사전은 **코드→표본코드, 이름→표본이름** 둘 다. 이름은 긴 것부터 치환(부분 일치 꼬임 방지). 영문 심볼은 단어 경계로.
   - **행 줄이기**: 보유 목록류(ranking.items · us_book 항목 · 승자 표 rows · rule_card items · holdings 표 · 종이 계좌 holdings)는 사전에 있는 행만 남긴다(한국 12·미국 8). 후보 표·시나리오·가설·출처·주장·질문·채점 같은 긴 목록은 **앞 10개**(열린 질문은 유형별 4개씩). `counts`·`n` 류 숫자는 남긴 행 수로 다시 센다(최소한 화면 제목에 쓰이는 것: `counts.candidates/registered`, `counts.open/claims`, `open`, `trades_n` 등 — 못 맞춘 것은 보고에 적는다).
   - **비중 다시 나누기**: 남은 행의 `weight`/`weight_pct`/`share` 류가 합 1(또는 100)이 되게 비례로 다시 나눈다(한국은 종목 합 0.94, 현금 0.06).
   - **돈 배율**: 키 이름이 `total|eval|cash|cost|amount|nav|principal|deposit|withdraw|capital|value|krw|usd|size_amount|pnl_amount|price|avg_price|target` 에 걸리는 숫자는 **배율**로 줄인다. 배율 = 목표 총액 / 라이브 총액(한국 `latest.krw.total`→₩10,000,000, 미국 `latest.usd.total`→$8,000, 코인→₩1,000,000). 문맥(krw/usd/coin)은 상위 키·`scope`·`market` 로 판단하고, 못 정하면 한국 배율. `price`/`avg_price` 는 표본 종목의 **그럴듯한 가격대**(표본 표에 기준가를 적어 둔다: 삼성전자 85,000 · SK하이닉스 420,000 … NVDA 180 …)로 바꾸고 `pnl_pct` 와 맞게 `avg_price = price/(1+pnl)` 로 계산.
   - **퍼센트 흔들기**: `pnl|ret|return|change|pct|drawdown|excess|share|score` 류 숫자는 결정적 난수(seed 20261010)로 ×0.6~1.4 흔든다(등급·국면 글자는 그대로). 비중은 위 규칙이 우선.
   - **문장 교체**: 값이 문자열이고 **40자 넘으면 무조건** 풀 문장으로 바꾼다(키 이름이 `sentence|text|note|why|reason|reasons|thesis|claim|evidence|comment|summary|intro|meaning|history|detail|label` 이면 40자 이하라도 바꾼다 — 단 `label` 은 20자 넘을 때만). 풀은 키 이름별 5~8개 한국어 문장(`sentence`→"사이클: 살아 있음(엔진 초록 4/4) · 빠른 경고 0개 — 꺾이면 내 돈의 한국 62%가 맞는다 · 먼저 줄일 것: 레버리지 1종목 3%", `reasons`→"펀더멘털: 양호 · ROE 15%" 등 **원본과 같은 어투지만 표본 종목·가짜 숫자**). 날짜·코드·URL·색 이름(`green/red`)·국면 글자(`살아 있음`·`2차 후 하락`·등급 `A/B/경고/주의/양호`)·`kind/status/stance` 같은 짧은 분기값은 건드리지 않는다(화면 분기가 깨진다).
   - **시계열**: `series?range=*`(`points[].krw/stock/usd/coin.total/eval/cash/cost`)는 포인트 수·`t` 를 유지하고 값은 **목표 곡선**(선형 + sin 두 개 + 작은 결정적 노이즈)으로 통째로 다시 쓴다. `benchmark`·`grade_history`·`growth`·`cashflows`·`quant perf` 의 시계열도 같은 식(구간 수익률 위 숫자대로). `latest.ts/as_of_kst` 는 생성 시각.
   - **깊은 링크**: 문자열 값이 `/tenbagger`·`/forecast`·`/` 로 시작하는 `url`/`anchor` 류는 `./tenbagger.html…` 로.
5. **새지 않게**(`build/check.py`, 생성기 끝에서도 호출): 라이브 `ranking.items`·`us_book`·코인·`tenbagger.candidates`·`holdings`·`forecast.scenarios[].tickers`·`rule_card items` 의 **실제 이름·코드 전부**를 메모리에 모아, `data/*.json`·`*.html`·`demo.js` 에 하나라도 남아 있으면 실패(0건이어야 통과). 표본 풀에 실제 이름이 있으면 그 이름을 풀에서 뺀 뒤 매핑한다. `100.67.98.100`·`8787`·`seokho`·`키움 계좌번호 패턴`(`\d{8}-\d{2}` 등)도 0건. 40자 넘는 문자열 중 풀에 없는 것 0건. `latest.krw.total` 이 ₩10,000,000 ±1%.
   **실명 목록은 어떤 파일에도 쓰지 않는다**(출력에도 개수만).
6. **빠진 데이터 0**: Playwright 로 세 페이지를 열고 탭(한국·미국·코인)·구간 버튼·정렬 버튼·종목 행 클릭(상세)·퀀트 패널 펼치기·3층 묶음 전부 열기를 돌려 `DEMO missing` 경고가 **0** 이어야 한다. 콘솔 오류 0. "아직 계산 전"·"없음"·"—" 가 첫 화면·텐배거 1~2층·예측 1~2층에 없어야 한다(3층 안은 2곳까지 허용 — 보고에 적는다).
7. **GitHub Pages**: `.nojekyll` 추가 → `gh repo create happydyoon/pwm-showcase --public --source . --push` → `gh api -X POST repos/happydyoon/pwm-showcase/pages -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/'` → 1~3분 뒤 `curl -sI https://happydyoon.github.io/pwm-showcase/` 가 200. (리포 만들기·푸시·Pages 켜기는 **맡긴 쪽이 한다** — 빌더는 로컬 `python3 -m http.server` 로 확인까지.)

## 테스트·검사

- `python3 -m pytest -q tests/`(맥 시스템 파이썬 3.9, pytest 없으면 `uv run --with pytest pytest -q`): slug 규칙 파이썬↔JS 동일(JS 는 정규식 문자열을 파일에서 읽어 비교) · 패치 전부 적중 · `data/latest.json` 총액 · `demo.js` 띠 문자열 · `check.py` 통과.
- Playwright(일 1 과 같은 스크래치 venv 재사용 가능 — `/private/tmp/claude-501/-Users-seokho-dev/00fb27c5-6260-4f84-8cf5-666ef89f3451/scratchpad/.venv`): `python3 -m http.server 8791` 로 띄우고 노트북·폰 스크린샷 세 페이지 → `docs/history/img/2026-10-10-showcase-*.png`.
- 커밋·푸시·Pages 는 하지 않는다(검수 뒤 맡긴 쪽이 한다).

## 보고에 적을 것

만든 파일 · 받은 슬러그 수/건너뛴 것 · `check.py` 결과(실명 0건·총액) · `DEMO missing` 0 여부 · 자리표시(계산 전/없음) 남은 곳 · 스크린샷 경로 · 계획과 달라진 점 · 못 한 것.

## 버린 안과 이유

- 라이브 서버에 `?demo=1` 모드: 실제 서버를 밖에 내놓게 되고 Tailscale 밖에서 못 본다.
- 스크린샷 이미지만: 움직이는 대시보드를 보여 주는 목적에 안 맞는다.
- JSON 을 손으로 쓰기: 주소 30여 개·응답 합계 2MB 라 손으로는 못 맞춘다 → 라이브 응답을 틀로 쓰는 생성기.
- 실제 보유 이름 그대로 + 금액만 축소: 포트폴리오 구성이 공개된다(석호님 답 없음 → 표본).
- 실제 AI 문장을 이름만 바꿔 싣기: 종목 근거가 드러난다(장부 3등급이어도) → 40자 넘는 문자열은 전부 풀 문장.
- Cloudflare Pages 를 지금: 맥에 토큰·node 없음 → 사람 손 필요. GitHub Pages 는 `gh` 로 끝난다.
