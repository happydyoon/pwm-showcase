"""체험판 사이트 검사 — 표준 라이브러리 + pytest.

    python3 -m pytest -q tests/        (pytest 가 없으면: uv run --with pytest pytest -q tests/)

라이브 API 가 필요한 검사(check.py)는 API 에 닿지 않으면 건너뛴다.
"""
import json
import os
import re
import sys
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'build'))
import make_demo as M  # noqa: E402
import check as C  # noqa: E402

PAGES = ('index.html', 'tenbagger.html', 'forecast.html')


def read(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as fh:
        return fh.read()


def js_slug(url, pattern):
    """demo.js 의 slug() 를 그대로 옮긴 것 — 파일에서 읽은 정규식 문자열로 계산한다."""
    i = url.find('/api/')
    rest = url[i + 5:] if i >= 0 else url
    return re.sub(r'^_+|_+$', '', re.sub(pattern, '_', rest))


# ── slug 규칙: 파이썬 ↔ JS ──
def test_slug_pattern_same_in_python_and_js():
    js = read('demo.js')
    m = re.search(r"var SLUG_PATTERN = '([^']+)';", js)
    assert m, 'demo.js 에 SLUG_PATTERN 이 없다'
    assert m.group(1) == M.SLUG_PATTERN
    assert ".replace(/^_+|_+$/g, '')" in js           # 앞뒤 밑줄 떼기도 같다
    for url, want in [('/api/series?range=3M', 'series_range_3M'),
                      ('/api/stock?code=005930', 'stock_code_005930'),
                      ('/api/quant?panel=perf&scope=kr', 'quant_panel_perf_scope_kr'),
                      ('/api/ranking', 'ranking'),
                      ('/api/grade_history?scope=us&range=3Y', 'grade_history_scope_us_range_3Y'),
                      ('/api/benchmark?range=ALL&scope=krw', 'benchmark_range_ALL_scope_krw')]:
        assert M.slug(url) == want
        assert js_slug(url, m.group(1)) == want


# ── 패치 ──
def test_patches_all_hit_on_source():
    if not os.path.isdir(M.DEFAULT_SRC):
        pytest.skip('원본 대시보드 폴더 없음')
    src = M.read_src(M.DEFAULT_SRC)
    for f, rx, _b, n in M.patches():
        assert len(rx.findall(src[f])) == n, (f, rx.pattern)
    M.apply_patches(src)     # 하나라도 어긋나면 SystemExit


def test_pages_are_patched():
    for p in PAGES:
        t = read(p)
        assert '<script src="./demo.js"></script>' in t
        assert '<title>[체험판] ' in t
        assert not re.search(r'(?:href|src)="/(?!/)', t), p + ' 에 절대 경로가 남음'
    assert 'if (!window.DEMO) setInterval(load, 30000);' in read('index.html')
    assert 'href="./quant.css"' in read('index.html') and 'src="./quant.js"' in read('index.html')


# ── 데이터 ──
def test_latest_totals():
    L = json.loads(read('data/latest.json'))
    assert abs(L['krw']['total'] - 10_000_000) <= 100_000
    assert abs(L['coin']['total'] - 1_000_000) <= 10_000
    assert abs(L['usd']['total'] - 8_000) <= 80
    assert abs(L['stock']['total'] + L['coin']['total'] - L['krw']['total']) < 1
    assert abs(L['krw']['eval'] - 9_400_000) <= 94_000 and abs(L['krw']['cash'] - 600_000) <= 6_000


def test_samples_are_fixed_not_excluded():
    """표본은 실명과 겹쳐도 빠지지 않는다 — 보유 표의 이름은 늘 표본 12(한국)·8(미국)·3(코인) 그대로."""
    import samples as S
    for slug, want in (('ranking', {n for n, _, _ in S.SAMPLE_KR}), ('ranking_scope_us', {s for s, _, _, _ in S.SAMPLE_US}),
                       ('ranking_scope_coin', {s for s, _, _ in S.SAMPLE_COIN})):
        got = {it['name'] for it in json.loads(read('data/%s.json' % slug))['items']}
        assert got == want, slug


def test_sample_order_is_shuffled():
    """1:1 배정은 seed 로 섞은 표본 순서 — 비중 1위가 목록 첫 줄 표본이 되지 않는다(결정적)."""
    import samples as S
    first = M.shuffled([(n, c, p, n, n) for n, c, p in S.SAMPLE_KR])
    assert first == M.shuffled([(n, c, p, n, n) for n, c, p in S.SAMPLE_KR])     # 같은 seed → 같은 순서
    assert [r[0] for r in first] != [n for n, _, _ in S.SAMPLE_KR]
    top = max(json.loads(read('data/ranking.json'))['items'], key=lambda x: x['weight_pct'])
    assert top['name'] == first[0][0]


def test_collection_status_always_ok():
    """정적 사이트는 시간이 갈수록 오래된 자료 — 수집 상태 판정은 항상 정상(빨간 줄·경고 띠 없음)."""
    assert json.loads(read('data/latest.json'))['stale_buckets'] == []
    for mk in ('kr', 'us', 'coin'):
        t = json.loads(read('data/trust_scope_%s.json' % mk))
        assert t['level'] == 'ok' and t['summary'] == '문제 0 · 주의 0'
        assert all(s['level'] == 'ok' for s in t['sources'])


def test_series_ends_at_total():
    s = json.loads(read('data/series_range_3M.json'))
    pts = s['points']
    assert abs(pts[-1]['krw']['total'] - 10_000_000) <= 100_000
    ret = pts[-1]['krw']['total'] / pts[0]['krw']['total'] - 1
    assert 0.06 <= ret <= 0.10                         # 3개월 +8% 안팎


def test_every_called_api_has_data():
    if not os.path.isdir(M.DEFAULT_SRC):
        pytest.skip('원본 대시보드 폴더 없음')
    paths, _ = M.api_paths(M.read_src(M.DEFAULT_SRC))
    have = {f[:-5] for f in os.listdir(os.path.join(ROOT, 'data')) if f.endswith('.json')}
    missing = [M.slug('/api/' + p) for p in paths if M.slug('/api/' + p) not in have]
    assert not missing, missing


def test_no_internal_address_in_files():
    for f in C.scan_files(ROOT):
        t = read(os.path.relpath(f, ROOT))
        assert '100.67.98.100' not in t, f
        assert not re.search(r'(?<!\d)8787(?!\d)', t), f


def test_long_strings_come_from_pool():
    for f in os.listdir(os.path.join(ROOT, 'data')):
        if f.endswith('.json'):
            out = []
            C.long_strings(json.loads(read('data/' + f)), out)
            assert not out, f


# ── 띠 ──
def test_banner_text():
    js = read('demo.js')
    assert "'체험판 · 가상 데이터 — 실제 계좌가 아닙니다 · 총액 ₩1,000만 고정'" in js
    assert 'position:sticky;top:0' in js
    assert 'white-space:nowrap' in js
    assert "console.warn('DEMO missing', s)" in js


# ── 실명 검사(라이브) ──
def api_up():
    try:
        urllib.request.urlopen(M.DEFAULT_API + '/api/latest', timeout=5).read(64)
        return True
    except Exception:  # noqa: BLE001
        return False


def test_check_passes_against_live_names():
    if not api_up():
        pytest.skip('라이브 API 에 닿지 않음(Tailscale 밖)')
    assert C.run(ROOT, verbose=False)
