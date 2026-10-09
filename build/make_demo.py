#!/usr/bin/env python3
"""보여주기용 복제 대시보드 생성기 (파이썬 3.9 표준 라이브러리만).

    python3 build/make_demo.py [--src ~/dev/vvippwm/dashboard/static] [--api http://100.67.98.100:8787]

하는 일
  1) 원본 다섯 파일(index·tenbagger·forecast.html, quant.js, quant.css)을 리포 루트로 복사하고 문자열 패치(패치마다 적중 횟수 확인).
  2) 원본 HTML·JS 가 실제로 부르는 /api 주소 조합을 읽어 라이브 API 에서 하나씩 GET(읽기만, 타임아웃 30초).
  3) 응답을 모양 틀로만 쓰고 이름·돈·문장을 갈아 끼워 data/<slug>.json 으로 쓴다.
  4) 끝에 build/check.py 로 실명·주소·총액을 검사한다.

실제 보유 이름·코드·라이브 응답·실명 사전은 **메모리에서만** 쓰고 어떤 파일에도 쓰지 않는다.
"""
import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import samples as S  # noqa: E402

DEFAULT_SRC = os.path.expanduser('~/dev/vvippwm/dashboard/static')
DEFAULT_API = 'http://100.67.98.100:8787'
TIMEOUT = 30
SEED = 20261010

# 목표 금액 — 한국 총액(주식+코인) ₩1,000만 · 미국 $8,000 · 코인 ₩100만
KRW_TOTAL, COIN_TOTAL, USD_TOTAL = 10_000_000, 1_000_000, 8_000
STOCK_TOTAL = KRW_TOTAL - COIN_TOTAL
CASH_FRAC = {'stock': 0.06, 'coin': 0.06, 'usd': 0.056}      # 한국 현금 합계 ₩60만(종목 ₩940만)
UNREAL = {'stock': 0.226, 'coin': -0.10, 'usd': 0.18}        # 평가액/원가 − 1
CAPITAL = {'stock': 7_000_000, 'coin': 1_100_000}
BUCKET_SHARE = {'GENERAL': 0.35, 'ISA': 0.50, 'PENSION': 0.15}
# 미국 장부 '큰 베팅' 묶음 이름 — 실제 일화 이름 대신(순서대로 배정)
BET_NAMES = ['폭락장 역발상 매수 A', '폭락장 역발상 매수 B', '폭락장 역발상 매수 C', '폭락장 역발상 매수 D']
BUCKET_CAPITAL = {'GENERAL': 2_400_000, 'ISA': 3_500_000, 'PENSION': 1_100_000, 'KORBIT': 1_100_000}
# 구간 수익률(계획서: 3개월 +8% · 1년 +18% · 전체 +35%, 코스피 +5% · 미국 +6% · 코인 +12%)
RET = {
    'krw':  {'1D': 0.004, '1W': 0.011, '1M': 0.030, '3M': 0.08, '1Y': 0.18, 'ALL': 0.35},
    'coin': {'1D': 0.012, '1W': -0.02, '1M': 0.050, '3M': 0.12, '1Y': 0.30, 'ALL': 0.55},
    'usd':  {'1D': -0.003, '1W': 0.008, '1M': 0.022, '3M': 0.06, '1Y': 0.14, 'ALL': 0.28},
}
BENCH_RET = [  # 비교선 — 첫째·둘째 지수
    {'1D': 0.002, '1W': 0.006, '1M': 0.018, '3M': 0.05, '1Y': 0.12, 'ALL': 0.22},
    {'1D': 0.001, '1W': 0.004, '1M': 0.012, '3M': 0.03, '1Y': 0.08, 'ALL': 0.15},
]
AGE = {'1D': 1.0, '1W': 7.0, '1M': 30.4, '3M': 91.3, '1Y': 365.0}

SLUG_PATTERN = '[^A-Za-z0-9]+'          # demo.js 의 SLUG_PATTERN 과 같아야 한다(테스트가 대조)
MAX_STR = 40
ALWAYS_KEYS = {'sentence', 'text', 'note', 'why', 'reason', 'reasons', 'thesis', 'claim', 'evidence', 'comment',
               'summary', 'intro', 'meaning', 'history', 'detail', 'label'}
TRUNC_KEYS = {'candidates', 'claims', 'sources', 'trial_sources', 'resolved', 'bottlenecks', 'hypotheses',
              'hypotheses_auto', 'tracked', 'qualified', 'buy', 'skip', 'layers', 'layers_recent', 'new_signals',
              'evidence', 'theses', 'recall', 'news', 'filings', 'events', 'proposals', 'trades', 'gaps',
              'top_unheld', 'watch_only', 'scenarios', 'external', 'proxy_filled'}
PRICE_KEYS = {'price', 'avg_price', 'reg_price', 'entry_price', 'target', 'median_target', 'weighted_target',
              'wait_price', 'high_52w', 'low_52w', 'conservative', 'targetMeanPrice'}
BAND_PRICE_KEYS = {'low', 'high', 'median'}
WEIGHT_KEYS = {'weight_pct', 'weight', 'w'}
MONEY_TOKENS = {'total', 'eval', 'cash', 'cost', 'amount', 'nav', 'principal', 'deposit', 'deposited', 'withdraw',
                'withdrawn', 'capital', 'value', 'krw', 'usd', 'gain', 'profit', 'net', 'flow', 'diff', 'invested',
                'returned', 'returns', 'buys', 'cum', 'income', 'fee', 'fees', 'dividends', 'loss', 'pnl', 'taken',
                'change', 'invest'}
PCT_TOKENS = {'pct', 'ret', 'return', 'change', 'drawdown', 'excess', 'share', 'score', 'gap', 'pnl', 'gain',
              'yoy', 'cagr', 'irr', 'xirr', 'mdd'}
LARGE_EXEMPT = {'amt', 'cap', 'needed', 'usd', 'marketcap', 'volume', 'shares', 'income', 'revenue', 'f', 'i', 'v',
                'net', 'foreign', 'inst', 'd', 'bars'}
NO_TOUCH_KEYS = {'t', 'ts', 'checked_at', 'computed_at', 'updated', 'start', 'end', 'stock_updated', 'idx', 'year',
                 'semi_usd', 'positions', 'n', 'days', 'obs', 'rank', 'months'}


# ───────────────────────────── 공용 ─────────────────────────────
def slug(url):
    """'/api/series?range=3M' → 'series_range_3M'. demo.js 의 slug() 와 같은 규칙."""
    i = url.find('/api/')
    rest = url[i + 5:] if i >= 0 else url
    return re.sub(SLUG_PATTERN, '_', rest).strip('_')


def h01(*parts):
    """결정적 난수 0~1 (seed 20261010)."""
    m = hashlib.md5(('%d|' % SEED + '|'.join(str(p) for p in parts)).encode('utf-8')).hexdigest()
    return int(m[:12], 16) / float(16 ** 12)


def pick(lst, *parts):
    return lst[int(h01(*parts) * len(lst)) % len(lst)]


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def ndigits(v):
    if isinstance(v, int):
        return 0
    s = repr(v)
    if 'e' in s or '.' not in s:
        return 2
    return min(4, max(1, len(s.split('.')[1])))


def like(orig, new):
    """원래 값의 정수/소수 자릿수를 따른다."""
    if isinstance(orig, int):
        return int(round(new))
    return round(new, ndigits(orig))


# ───────────────────────────── 주소 목록(원본 소스에서 뽑는다) ─────────────────────────────
def read_src(src):
    out = {}
    for f in ('index.html', 'tenbagger.html', 'forecast.html', 'quant.js', 'quant.css'):
        with open(os.path.join(src, f), encoding='utf-8') as fh:
            out[f] = fh.read()
    return out


def api_paths(src_text):
    """원본 HTML·JS 를 읽어 실제로 부르는 /api 조합을 만든다(추측 금지 — 소스에서 못 찾으면 실패)."""
    ix, qj = src_text['index.html'], src_text['quant.js']
    allsrc = '\n'.join(src_text.values())

    def need(pattern, text, what):
        found = re.findall(pattern, text)
        if not found:
            raise SystemExit('소스에서 %s 을(를) 찾지 못함 — 원본이 바뀌었는지 확인' % what)
        out = []
        for x in found:
            if x not in out:
                out.append(x)
        return out

    markets = need(r'data-market="(\w+)"', ix, '시장 탭')
    ranges = need(r'data-(?:r|usr|coinr)="(\w+)"', ix, '구간 버튼')
    m = re.search(r'const rngBtn = \[(.*?)\]\s*\n?\s*\.map', ix, re.S)
    gh_ranges = need(r"\['(\w+)',", m.group(1) if m else '', '등급 추이 구간')
    gh_default = re.search(r"const gh = \{data:null, rng:'(\w+)'", ix)
    if gh_default and gh_default.group(1) not in gh_ranges:
        gh_ranges.append(gh_default.group(1))
    bench_scopes = need(r"ensureBench\('(\w+)'", ix, '시장 대비 범위')
    attr_scopes = need(r"ensureAttr\('(\w+)'", ix, '손익 분해 범위')
    panels = []   # (panel, books)
    for blk in re.findall(r'Q\.register\(\{(.*?)\n\s*(?:render|\}\))', qj, re.S):
        pid = re.search(r"id: '(\w+)'", blk)
        books = re.search(r"books: \[([^\]]*)\]", blk)
        if not pid or not books:
            continue
        bl = re.findall(r"'(\w+)'", books.group(1))
        panel = 'perf' if 'fetch: perfFetch' in blk else pid.group(1)
        panels.append((panel, bl))
    if not panels:
        raise SystemExit('quant.js 에서 패널을 찾지 못함')
    for frag in ("'/api/latest'", "'/api/board'", "'/api/sectors'", "'/api/sectors?scope=us'", "'/api/us_book'",
                 "'/api/scorecard'", "'/api/action_scorecard'", "'/api/entry'", "'/api/growth'", "'/api/cashflows'",
                 "'/api/cashflows?scope=us'", "'/api/tenbagger'", "'/api/forecast'", "'/api/ranking'", "'/api/risk'",
                 "'/api/changes?scope='", "'/api/grade?scope='", "'/api/trust?scope='"):
        if frag not in allsrc:
            raise SystemExit('소스에서 %s 를 찾지 못함' % frag)
    paths = ['latest', 'board', 'sectors', 'sectors?scope=us', 'us_book', 'scorecard', 'action_scorecard', 'entry',
             'growth', 'cashflows', 'cashflows?scope=us', 'tenbagger', 'forecast']
    for mk in markets:
        q = '' if mk == 'kr' else '?scope=' + mk            # loadHoldings: mk === 'kr' ? '' : `?scope=${mk}`
        paths += ['ranking' + q, 'risk' + q, 'changes?scope=' + mk, 'grade?scope=' + mk, 'trust?scope=' + mk]
        paths += ['grade_history?scope=%s&range=%s' % (mk, r) for r in gh_ranges]
    paths += ['series?range=' + r for r in ranges]
    paths += ['benchmark?range=%s&scope=%s' % (r, s) for s in bench_scopes for r in ranges]
    paths += ['attribution?range=%s&scope=%s' % (r, s) for s in attr_scopes for r in ranges]
    for panel, books in panels:
        for b in books:
            p = 'quant?panel=%s&scope=%s' % (panel, b)
            if p not in paths:
                paths.append(p)
    return paths, markets


# ───────────────────────────── 라이브 받기(읽기만) ─────────────────────────────
def fetch(api, path):
    url = api.rstrip('/') + '/api/' + path
    req = urllib.request.Request(url, headers={'User-Agent': 'pwm-showcase-builder'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode('utf-8'))


# ───────────────────────────── 실명 모으기(메모리에서만) ─────────────────────────────
INDEX_LIKE = re.compile(r'^(\^.*|KS11|KQ11|US500|IXIC|DJI|SOX|VIX|KOSPI|KOSDAQ|.*/KRW|.*=X)$')
PAIR_SKIP_SLUGS = ('series', 'benchmark', 'grade_history', 'attribution', 'latest', 'cashflows', 'growth', 'trust')


def is_hangul(s):
    return bool(re.search('[가-힣]', s or ''))


def entity_code(o):
    """종목을 가리키는 dict 의 코드 — {code, name} 쌍이거나 {symbol}(미국 장부·손익 사건). 거시 일정·지수 줄은 아니다."""
    c, s = o.get('code'), o.get('symbol')
    if isinstance(c, str) and c and isinstance(o.get('name'), str) and o.get('name'):
        return c
    if isinstance(s, str) and s and not INDEX_LIKE.match(s):
        return s
    return None


def collect_real(raw):
    """라이브 응답 전체에서 (코드, 이름) 쌍과 실명 토큰을 모은다. 반환값은 메모리에만 둔다."""
    pairs = {}          # code → set(names)
    order = []          # 코드가 처음 보인 순서
    hints = {}          # code → 시장(응답의 market 칸)

    def add(code, name=None):
        if not isinstance(code, str) or not code.strip() or INDEX_LIKE.match(code):
            return
        if code not in pairs:
            pairs[code] = set()
            order.append(code)
        if isinstance(name, str) and name.strip() and name != code:
            pairs[code].add(name)

    def walk(o, key=None):
        if isinstance(o, dict):
            n = o.get('name')
            c = entity_code(o)
            if c:
                add(c, n)
                m = o.get('market')
                if isinstance(m, str) and m.upper() in ('KR', 'US', 'ADR') and c not in hints:
                    hints[c] = 'kr' if m.upper() == 'KR' else 'us'
            if key in ('moved', 'flags'):
                for k, v in o.items():
                    add(k, v.get('name') if isinstance(v, dict) else None)
            for k, v in o.items():
                if k == 'symbols' and isinstance(v, list):
                    for x in v:
                        add(x)
                walk(v, k)
        elif isinstance(o, list):
            for v in o:
                walk(v, key)

    prio = ['ranking', 'ranking?scope=us', 'ranking?scope=coin', 'entry', 'tenbagger', 'forecast']
    for p in prio + sorted(k for k in raw if k not in prio):
        if p in raw and not slug('/api/' + p).startswith(PAIR_SKIP_SLUGS):
            walk(raw[p])
    coin_codes = set()
    for p in ('ranking?scope=coin', 'risk?scope=coin', 'quant?panel=whatif&scope=coin'):
        o = raw.get(p) or {}
        for it in (o.get('items') or o.get('sizing_flags') or o.get('held') or []):
            if isinstance(it, dict) and isinstance(it.get('code'), str):
                coin_codes.add(it['code'])
    ch = raw.get('changes?scope=coin') or {}
    coin_codes.update((ch.get('moved') or {}).keys())
    tokens = set()
    for c, ns in pairs.items():
        tokens.add(c)
        tokens.update(ns)
    for p, mk in (('ranking', 'kr'), ('ranking?scope=us', 'us'), ('entry', 'kr')):
        o = raw.get(p) or {}
        for it in (o.get('items') or o.get('candidates') or []):
            if isinstance(it, dict) and isinstance(it.get('code'), str):
                hints[it['code']] = mk
    return {'pairs': pairs, 'order': order, 'coin': coin_codes, 'tokens': tokens, 'hints': hints}


def token_regex(tokens):
    """실명 토큰 하나라도 걸리는 정규식. 영숫자 토큰은 단어 경계, 한글 이름은 그대로."""
    parts = []
    for t in sorted(tokens, key=len, reverse=True):
        if not t or len(t) < 2 and not is_hangul(t):
            continue
        e = re.escape(t)
        if re.fullmatch(r'[A-Za-z0-9.\-/&+ ]+', t):
            parts.append(r'(?<![A-Za-z0-9_])' + e + r'(?![A-Za-z0-9_])')
        else:
            parts.append(e)
    return re.compile('|'.join(parts)) if parts else re.compile(r'(?!x)x')


def market_of(code, coin_codes, hints=None):
    if code in coin_codes:
        return 'coin'
    if hints and code in hints:
        return hints[code]
    if code[:1].isdigit() or re.fullmatch(r'Q\d{6}', code):      # 한국 주식·ETF(영숫자 코드)·ETN(Q…)
        return 'kr'
    return 'us'


# ───────────────────────────── 이름 사전(실명 → 표본) ─────────────────────────────
def sample_rows():
    """시장별 (1차 표본 줄, 2차 풀 줄). 줄 = (짧은 이름, 코드, 기준가, 영문 이름, 한글 이름)."""
    return {
        'kr': ([(n, c, p, n, n) for n, c, p in S.SAMPLE_KR], [(n, c, p, n, n) for n, c, p in S.POOL_KR]),
        'us': ([(s, s, p, en, ko) for s, en, ko, p in S.SAMPLE_US], [(s, s, p, en, ko) for s, en, ko, p in S.POOL_US]),
        'coin': ([(s, s, p, ko, ko) for s, ko, p in S.SAMPLE_COIN], [(s, s, p, ko, ko) for s, ko, p in S.POOL_COIN]),
    }


def shuffled(rows):
    out = list(rows)
    random.Random(SEED).shuffle(out)
    return out


def sample_tokens():
    """표본 사전(samples.py)의 이름·코드·심볼 — 실명과 겹쳐도 검사에서 예외로 둔다."""
    out = set()
    for first, rest in sample_rows().values():
        for short, code, _p, en, ko in first + rest:
            out.update((short, code, en, ko))
    return out


class NameMap:
    def __init__(self, real, raw):
        self.real = real
        self.rx = token_regex(real['tokens'])
        self.code = {}       # 실코드 → 표본코드
        self.name = {}       # 실이름 → 표본이름
        self.info = {}       # 표본코드 → (기준가, 시장)
        self.en = {}         # 표본코드 → 영문 이름
        self.used = set()
        self.primary = {'kr': [], 'us': [], 'coin': []}    # 실코드(비중 순)
        self.hold_w = {'kr': {}, 'us': {}, 'coin': {}}     # 실코드 → 비중
        self.fallback_n = {'kr': 0, 'us': 0, 'coin': 0}
        # 표본은 실명과 겹쳐도 고정(빼면 '빠진 유명 종목 = 실제 보유'로 새는 길이 된다).
        # 1차 표본 순서는 seed 로 섞는다 — 비중 1위가 늘 표본 첫 줄(예: 목록 맨 앞 종목)이 되지 않게.
        self.pools = {k: shuffled(v) + rows for k, (v, rows) in sample_rows().items()}
        self._syn = {'kr': 0, 'us': 0, 'coin': 0}
        self._build(raw)

    def clashes(self, *names):
        for n in names:
            if not n:
                continue
            if n in self.real['tokens'] or self.rx.search(n):
                return True
        return False

    def _next(self, mk):
        pool = self.pools[mk]
        while pool:
            short, code, price, en, ko = pool.pop(0)
            if code in self.used:
                continue
            return short, code, price, en, ko
        # 풀까지 다 쓰면 가상 이름
        while True:
            i = self._syn[mk]
            self._syn[mk] += 1
            self.fallback_n[mk] += 1
            if mk == 'kr':
                nm = S.SYN_KR_PRE[i % len(S.SYN_KR_PRE)] + S.SYN_KR_SUF[(i // len(S.SYN_KR_PRE)) % len(S.SYN_KR_SUF)]
                code, price, en, ko = '99%04d' % (i + 1), 10000 + int(h01('p', nm) * 90000) // 100 * 100, nm, nm
                short = nm
            elif mk == 'us':
                a, b = divmod(i, 26)
                code = 'ZX' + chr(65 + a % 26) + chr(65 + b)
                short, price, en, ko = code, 20 + int(h01('p', code) * 300), 'Sample Holdings ' + code[2:], '샘플 ' + code[2:]
            else:
                code = 'CN' + chr(65 + i % 26)
                short, price, en, ko = code, 1000 + int(h01('p', code) * 20000), '샘플코인 ' + code[2:], '샘플코인 ' + code[2:]
            if code not in self.used and not self.clashes(short, code, en, ko):
                return short, code, price, en, ko

    def assign(self, real_code):
        if real_code in self.code:
            return self.code[real_code]
        mk = market_of(real_code, self.real['coin'], self.real.get('hints'))
        short, code, price, en, ko = self._next(mk)
        self.used.add(code)
        self.code[real_code] = code
        self.info[code] = (price, mk)
        self.en[code] = en
        for nm in self.real['pairs'].get(real_code, ()):
            if nm in self.name:
                continue
            if mk == 'kr':
                self.name[nm] = short
            elif is_hangul(nm):
                self.name[nm] = ko
            elif re.fullmatch(r'[A-Z0-9.\-/]+', nm):
                self.name[nm] = short
            else:
                self.name[nm] = en
        return code

    def _build(self, raw):
        def top(path, n):
            items = [x for x in ((raw.get(path) or {}).get('items') or []) if isinstance(x, dict) and x.get('code')]
            ws ={x['code']: (x.get('weight_pct') or 0) for x in items}
            return [c for c, _ in sorted(ws.items(), key=lambda kv: -kv[1])][:n], ws
        for mk, path, n in (('kr', 'ranking', 12), ('us', 'ranking?scope=us', 8), ('coin', 'ranking?scope=coin', 3)):
            codes, ws = top(path, n)
            self.hold_w[mk] = ws
            self.primary[mk] = codes
            for c in codes:
                self.assign(c)
        # 비중 다시 나누기 배율 — 남긴 행의 비중 합이 100% 가 되게
        self.wfac = {}
        for mk in ('kr', 'us', 'coin'):
            s = sum(self.hold_w[mk].get(c, 0) for c in self.primary[mk])
            self.wfac[mk] = (100.0 / s) if s else 1.0
        self.primary_all = set(self.primary['kr']) | set(self.primary['us']) | set(self.primary['coin'])
        self.hold_all = set(self.hold_w['kr']) | set(self.hold_w['us']) | set(self.hold_w['coin'])
        self.both = {}

    def finish(self, visible):
        """화면에 남는 종목부터 표본 풀을 배정하고(가상 이름은 뒤로), 나머지 실명도 전부 사전에 넣는다."""
        for c in list(visible) + list(self.real['order']):
            if c in self.real['pairs']:
                self.assign(c)
        both = dict(self.code)                       # 코드가 이름보다 먼저(같은 글자가 다른 종목 이름일 때)
        for rn, sn in self.name.items():
            both.setdefault(rn, sn)
        self.both = both

    def subst(self, s):
        if s in self.both:
            return self.both[s]
        if not self.rx.search(s):
            return s
        return self.rx.sub(lambda m: self.both.get(m.group(0), m.group(0)), s)


# ───────────────────────────── 문자열 ─────────────────────────────
POOL_SET = set(S.SHORT_POOL)
for _v in S.POOLS.values():
    POOL_SET.update(_v)


def pool_line(key, parent, orig):
    for k in ('%s.%s' % (parent, key), key):
        if k in S.POOLS:
            return pick(S.POOLS[k], k, orig)
    return pick(S.POOLS['default'], 'default', orig)


def wordy(s):
    return len(re.findall('[가-힣A-Za-z]', s)) >= 6


MONEY_RX = re.compile(
    r'(?P<won>₩\s?)(?P<a>\d[\d,]*(?:\.\d+)?)'
    r'|\$(?P<usd>\d[\d,]*(?:\.\d+)?)(?P<usdk>[KMB])?'
    r'|(?P<e>\d[\d,]*(?:\.\d+)?)억(?:\s?(?P<em>\d[\d,]*)만)?(?P<ew>\s?원)?'
    r'|(?P<m>\d[\d,]*(?:\.\d+)?)만(?P<mw>\s?원)?(?![가-힣])'
    r'|(?P<w>\d{1,3}(?:,\d{3})+|\d{4,})(?P<ww>\s?원)')


def fmt_won_compact(v):
    if abs(v) >= 1e8:
        return '%.2f억' % (v / 1e8)
    if abs(v) >= 1e4:
        return '{:,}만'.format(int(round(v / 1e4)))
    return '{:,}'.format(int(round(v)))


def scale_money_text(s, k_krw, k_usd):
    def num(x):
        return float(x.replace(',', ''))

    def rep(m):
        if m.group('won'):
            return '₩{:,}'.format(int(round(num(m.group('a')) * k_krw)))
        if m.group('usd'):
            mult = {'K': 1e3, 'M': 1e6, 'B': 1e9}.get(m.group('usdk') or '', 1)
            v = num(m.group('usd')) * mult * k_usd
            if mult > 1:
                return '$%.1f%s' % (v / mult, m.group('usdk'))
            return '${:,}'.format(int(round(v)))
        if m.group('e'):
            v = num(m.group('e')) * 1e8 + (num(m.group('em')) * 1e4 if m.group('em') else 0)
            return fmt_won_compact(v * k_krw) + (m.group('ew') or '')
        if m.group('m'):
            return fmt_won_compact(num(m.group('m')) * 1e4 * k_krw) + (m.group('mw') or '')
        if m.group('w'):
            return '{:,}'.format(int(round(num(m.group('w')) * k_krw))) + m.group('ww')
        return m.group(0)
    return MONEY_RX.sub(rep, s)


def rel_url(s):
    """라이브 주소·내부 경로 → 정적 사이트 상대 경로. 외부 주소는 비운다."""
    if re.match(r'https?://', s):
        m = re.match(r'https?://100\.67\.98\.100(?::\d+)?(/.*)?$', s)
        if not m:
            return ''
        s = m.group(1) or '/'
    if s.startswith('/tenbagger'):
        return './tenbagger.html' + s[len('/tenbagger'):]
    if s.startswith('/forecast'):
        return './forecast.html' + s[len('/forecast'):]
    if s == '/' or s.startswith('/#') or s.startswith('/?'):
        return './index.html' + s[1:]
    return s


# ───────────────────────────── 변환기 ─────────────────────────────
class Ctx:
    __slots__ = ('cur', 'base', 'ref', 'code')

    def __init__(self, cur='krw', base=None, ref=None, code=None):
        self.cur, self.base, self.ref, self.code = cur, base, ref, code


def first_price(o, depth=0):
    if depth > 3 or not isinstance(o, dict):
        return None
    if is_num(o.get('price')) and o['price'] > 0:
        return o['price']
    for v in o.values():
        if isinstance(v, dict):
            p = first_price(v, depth + 1)
            if p:
                return p
    return None


class Transformer:
    def __init__(self, nm, k):
        self.nm = nm
        self.k = k        # {'krw':…, 'usd':…, 'coin':…}

    # 통화 문맥
    def cur_of(self, obj, cur):
        for key in ('scope', 'market', 'book', 'currency'):
            v = obj.get(key)
            if not isinstance(v, str):
                continue
            v2 = v.lower()
            if v2 in ('us', 'usd', 'robinhood', 'us_all', 'us_top') or v2.startswith('us_'):
                return 'usd'
            if v2 in ('coin', 'korbit') or v2.startswith('coin'):
                return 'coin'
            if v2 in ('kr', 'krw', 'kiwoom') or v2.startswith('kr'):
                return 'krw'
        return cur

    def walk(self, o, key=None, parent=None, ctx=None, path=''):
        ctx = ctx or Ctx()
        if isinstance(o, dict):
            return self.walk_dict(o, key, ctx, path)
        if isinstance(o, list):
            lst = self.reduce_list(key, o)
            return [self.walk(v, key, parent, ctx, path + '[]') for v in lst]
        if isinstance(o, str):
            return self.string(o, key, parent, ctx)
        if is_num(o):
            return self.number(o, key, parent, ctx, path)
        return o

    def walk_dict(self, o, key, ctx, path):
        cur = self.cur_of(o, ctx.cur)
        if key in ('usd', 'US', 'us') or (isinstance(key, str) and key.startswith('us_')):
            cur = 'usd'
        elif key in ('coin', 'coin_capital'):
            cur = 'coin'
        c = entity_code(o)
        nctx = Ctx(cur, ctx.base, ctx.ref, ctx.code)
        primary_mk = None
        if isinstance(c, str) and c in self.nm.code:
            sc = self.nm.code[c]
            price, mk = self.nm.info[sc]
            nctx = Ctx('usd' if mk == 'us' else cur, price, first_price(o), c)
            if c in self.nm.primary_all:
                primary_mk = mk
        elif ctx.base is not None and ctx.ref is None and is_num(o.get('price')) and o['price'] > 0:
            nctx.ref = o['price']
        out = {}
        for k, v in o.items():
            nk = self.nm.subst(k) if isinstance(k, str) else k
            if primary_mk and k in WEIGHT_KEYS and is_num(v):
                out[nk] = like(v, v * self.nm.wfac[primary_mk])
                continue
            if k == 'numbers' and key == 'evidence' and isinstance(v, dict):   # 기사·공시에서 뽑은 회사 숫자(매출·판매량 등) — 회사가 드러나 비운다
                out[nk] = {}
                continue
            out[nk] = self.walk(v, k, key, nctx, path + '.' + k)
        # 평단은 현재가와 수익률에서 다시 계산(표본 가격대와 맞게)
        if is_num(out.get('price')) and is_num(out.get('avg_price')) and is_num(out.get('pnl_pct')) and out['pnl_pct'] > -99:
            out['avg_price'] = like(o['avg_price'], out['price'] / (1 + out['pnl_pct'] / 100.0))
        return out

    def reduce_list(self, key, lst):
        if not lst:
            return lst
        if key == 'open_questions':          # 유형별 4개씩
            seen, out = {}, []
            for q in lst:
                t = q.get('template') if isinstance(q, dict) else None
                if seen.get(t, 0) < 4:
                    out.append(q)
                    seen[t] = seen.get(t, 0) + 1
            return out
        coded = [x for x in lst if isinstance(x, dict) and entity_code(x)]
        if coded and len(coded) == len(lst):
            codes = [entity_code(x) for x in coded]
            held = sum(1 for c in codes if c in self.nm.hold_all)
            if held * 2 >= len(codes):           # 보유 목록류 — 표본에 있는 행만
                return [x for x in coded if entity_code(x) in self.nm.primary_all]
            return lst[:10] if len(lst) > 10 else lst
        if key in TRUNC_KEYS and len(lst) > 10:
            return lst[:10]
        if all(isinstance(x, str) for x in lst) and key in ('holdings', 'symbols', 'up', 'down'):
            return lst[:10]
        return lst

    def string(self, s, key, parent, ctx):
        if not s:
            return s
        if re.match(r'https?://', s) or (s.startswith('/') and key in ('url', 'anchor', 'href', 'link')):
            return rel_url(s)
        if key in ('news', 'filings') or (parent in ('news', 'filings') and key == 'title'):
            return pool_line('title', None, s)
        if len(s) > MAX_STR or '%s.%s' % (parent, key) in S.POOLS or (key == 'text' and wordy(s)):
            return pool_line(key, parent, s)
        if key in ALWAYS_KEYS and (key != 'label' or len(s) > 20) and wordy(s):
            return pick(S.SHORT_POOL, 'short', key, s)
        s2 = self.nm.subst(s)
        if ctx.cur in ('krw', 'usd') and '종목 수' in s2:      # 실제 보유 종목 수 → 남긴 표본 수
            n = len(self.nm.primary['us' if ctx.cur == 'usd' else 'kr'])
            s2 = re.sub(r'종목 수 \d+', '종목 수 %d' % n, s2)
        s2 = scale_money_text(s2, self.k['coin'] if ctx.cur == 'coin' else self.k['krw'], self.k['usd'])
        if len(s2) > MAX_STR:
            return pool_line(key, parent, s)
        return s2

    def number(self, v, key, parent, ctx, path):
        if key == 'n_positions':
            return len(self.nm.primary[{'usd': 'us', 'coin': 'coin'}.get(ctx.cur, 'kr')]) or v
        if not isinstance(key, str) or key in NO_TOUCH_KEYS:
            return v
        toks = set(key.lower().split('_'))
        if key in PRICE_KEYS or (key in BAND_PRICE_KEYS and parent in ('band', 'points', 'trend')):
            if ctx.base is not None:
                if ctx.ref:
                    return like(v, ctx.base * v / ctx.ref)
                return like(v, ctx.base * (0.9 + 0.3 * h01(path, v)))
            if key in ('price', 'avg_price') and v >= 1000:
                return like(v, v * self.k['krw'])
            return v
        if key in WEIGHT_KEYS:
            return v
        thresh = 100 if ctx.cur == 'usd' else 1000
        if toks & MONEY_TOKENS and abs(v) >= thresh:
            return like(v, v * self.k[ctx.cur])
        # 이름표가 낯선 큰 금액(예: hold_vs_ledger)도 계좌 돈이면 줄인다 — 시가총액·수급 거래대금 같은 시장 숫자는 그대로
        if abs(v) >= 1e6 and not (toks & LARGE_EXEMPT) and not toks & PCT_TOKENS:
            return like(v, v * self.k[ctx.cur])
        if toks & PCT_TOKENS:
            if isinstance(v, int) and abs(v) <= 5:
                return v
            f = 0.6 + 0.8 * h01(path, v)
            nv = v * f
            if 'score' in toks and 0 <= v <= 100:
                nv = min(100, max(0, nv))
            if 0 <= v <= 1 and toks & {'share', 'prob', 'score'}:
                nv = min(1, max(0, nv))
            if -100 <= v < 0:                       # 손실률이 −100% 를 넘지 않게
                nv = max(v if v < -95 else -95.0, nv)
            return like(v, nv)
        return v


# ───────────────────────────── 가짜 곡선 ─────────────────────────────
class Curve:
    """끝값 고정 · 구간 수익률 고정(기준점 나이) · 기준점 사이에서만 출렁이는 매끈한 곡선."""

    def __init__(self, end, rets, now, all_days, phase, amp=0.012):
        anchors = [(0.0, 0.0)] + [(AGE[r], rets[r]) for r in ('1D', '1W', '1M', '3M', '1Y')]
        anchors.append((max(all_days, 400.0), rets['ALL']))
        self.anch = sorted(anchors)
        self.end, self.now, self.ph, self.amp = end, now, phase, amp

    def _seg(self, age):
        a = self.anch
        for i in range(len(a) - 1):
            if a[i][0] <= age <= a[i + 1][0]:
                return a[i], a[i + 1]
        return a[-2], a[-1]

    def __call__(self, t):
        age = max(0.0, (self.now - t) / 86400.0)
        (a0, r0), (a1, r1) = self._seg(age)
        x = 0.0 if a1 == a0 else min(1.0, (age - a0) / (a1 - a0))
        r = r0 + (r1 - r0) * x
        env = math.sin(math.pi * x)                     # 기준점에서는 0 → 구간 수익률이 정확
        span = a1 - a0
        w = self.amp * min(8.0, math.sqrt(span / 30.0)) * env * (0.6 * math.sin(2 * math.pi * age / max(2.0, span / 2.3) + self.ph)
                                                      + 0.4 * math.sin(2 * math.pi * age / max(1.0, span / 5.1) + 2 * self.ph))
        w += 0.002 * env * math.sin(2 * math.pi * age * 24 / 3.5 + 3 * self.ph)
        w += 0.0012 * env * (h01('n', self.ph, int(t // 300)) - 0.5)
        return self.end / (1 + r) * (1 + w)


def grp(total, kind):
    cash = total * CASH_FRAC[kind]
    ev = total - cash
    return {'total': round(total, 2), 'eval': round(ev, 2), 'cash': round(cash, 2),
            'cost': round(ev / (1 + UNREAL[kind]), 2)}


def merge_grp(a, b):
    return {k: round(a[k] + b[k], 2) for k in a}


# ───────────────────────────── 생성기 본체 ─────────────────────────────
class Builder:
    def __init__(self, src, api, out):
        self.src, self.api, self.out = src, api, out
        self.raw, self.skipped, self.data = {}, [], {}

    def log(self, *a):
        print(*a, flush=True)

    def get(self, path, label=None):
        """label: 건너뛸 때 보고에 쓸 이름(종목 상세는 실제 코드 대신 표본 코드로 — 출력에 실명을 남기지 않는다)."""
        try:
            self.raw[path] = fetch(self.api, path)
            return self.raw[path]
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.skipped.append((label or slug('/api/' + path), type(e).__name__))
            return None

    def run(self):
        t0 = time.time()
        self.src_text = read_src(self.src)
        paths, self.markets = api_paths(self.src_text)
        for p in paths:
            self.get(p)
        if 'latest' not in self.raw or 'ranking' not in self.raw:
            raise SystemExit('라이브 API 에서 latest/ranking 을 받지 못함 — Tailscale·서버 확인')
        self.real = collect_real(self.raw)
        self.nm = NameMap(self.real, self.raw)
        L = self.raw['latest']
        self.k = {'krw': KRW_TOTAL / L['krw']['total'], 'usd': USD_TOTAL / L['usd']['total'],
                  'coin': COIN_TOTAL / L['coin']['total']}
        self.tf = Transformer(self.nm, self.k)
        # 종목 상세 — 한국 표본 12 + 진입 후보 앞 10, 미국 표본 8
        kr_codes = list(self.nm.primary['kr'])
        for c in (self.raw.get('entry') or {}).get('candidates', [])[:10]:
            if c.get('code') and c['code'] not in kr_codes:
                kr_codes.append(c['code'])
        self.detail, self.detail_fail = [], []
        for kind, codes in (('stock?code=', kr_codes), ('us_stock?sym=', self.nm.primary['us'])):
            for c in codes:
                label = slug('/api/' + kind + self.nm.assign(c))
                ok = self.get(kind + urllib.parse.quote(c), label) is not None
                (self.detail if ok else self.detail_fail).append((kind, c))
        # What-if — 맨 위 보유 하나를 절반 판다고 가정(계산만 하는 주소)
        self.whatif = {}
        for book in ('kr', 'us'):
            top = self.nm.primary[book][:1]
            if top:
                p = 'whatif?scope=%s&fund=cash&legs=%s' % (book, urllib.parse.quote('%s:sell:50' % top[0]))
                if self.get(p, 'whatif_scope_' + book) is not None:
                    self.whatif[book] = p
        # 상세·What-if 응답까지 넣어 실명 사전을 다시 모으고, 화면에 남는 종목부터 표본을 배정한다
        self.real = collect_real(self.raw)
        self.nm.real = self.real
        self.nm.rx = token_regex(self.real['tokens'])
        self.nm.finish(self.visible_codes())
        self.now = L['ts']
        allp = (self.raw.get('series?range=ALL') or {}).get('points') or []
        self.all_days = (self.now - allp[0]['t']) / 86400.0 if allp else 2400.0
        self.curves = {
            'krw': Curve(KRW_TOTAL, RET['krw'], self.now, self.all_days, 0.7),
            'coin': Curve(COIN_TOTAL, RET['coin'], self.now, self.all_days, 2.1, amp=0.03),
            'usd': Curve(USD_TOTAL, RET['usd'], self.now, self.all_days, 4.3, amp=0.015),
        }
        self.build_all()
        self.write()
        self.log('생성 %.1f초 · 받은 주소 %d · 건너뜀 %d · 데이터 파일 %d' % (time.time() - t0, len(self.raw),
                                                                   len(self.skipped), len(self.data)))
        for s, why in self.skipped:
            self.log('  건너뜀:', s, why)
        self.log('표본 배정: 고정 표본(섞기 seed %d) · 가상 이름 사용 KR %d · US %d · 코인 %d' % (
            SEED, self.nm.fallback_n['kr'], self.nm.fallback_n['us'], self.nm.fallback_n['coin']))
        import check
        return check.run(self.out, real=self.real, verbose=True)

    def visible_codes(self):
        """행 줄이기를 적용한 뒤 화면에 남는 종목 코드(보이는 순서)."""
        seen, order = set(), []

        def walk(o, key=None):
            if isinstance(o, dict):
                c = entity_code(o)
                if c and c not in seen:
                    seen.add(c)
                    order.append(c)
                for k, v in o.items():
                    walk(v, k)
            elif isinstance(o, list):
                for v in self.tf.reduce_list(key, o):
                    walk(v, key)
        first = ['ranking', 'ranking?scope=us', 'ranking?scope=coin', 'entry', 'tenbagger', 'forecast']
        for p in first + sorted(k for k in self.raw if k not in first):
            if p in self.raw and not slug('/api/' + p).startswith(PAIR_SKIP_SLUGS):
                walk(self.raw[p])
        return order

    # ── 엔드포인트별 ──
    def build_all(self):
        tf = self.tf
        for path, o in self.raw.items():
            if path.startswith(('stock?code=', 'us_stock?sym=', 'whatif?')):
                continue
            sl = slug('/api/' + path)
            fn = getattr(self, 'b_' + re.sub(r'\W.*', '', path), None)
            if fn is not None:
                res = fn(path, o)
            else:
                res = tf.walk(o, ctx=Ctx(self.ctx_of(path)))
            if res is not None:
                self.data[sl] = res
        for kind, real_code in self.detail:
            o = self.raw[kind + urllib.parse.quote(real_code)]
            cur = 'usd' if kind.startswith('us_') else 'krw'
            res = tf.walk(o, ctx=Ctx(cur))
            pf = (res.get('extras') or {}).get('profile') if isinstance(res, dict) else None
            if isinstance(pf, dict):                    # 회사 정식 이름·시가총액은 실제 회사를 드러낸다 → 표본 것으로
                sc = self.nm.code[real_code]
                if 'longName' in pf:
                    pf['longName'] = self.nm.en.get(sc, sc)
                if is_num(pf.get('marketCap')):
                    pf['marketCap'] = int(self.nm.info[sc][0] * 4e9 * (0.5 + h01('cap', sc)))
            self.data[slug('/api/' + kind + self.nm.code[real_code])] = res
        for kind, real_code in self.detail_fail:       # 원본 서버도 상세가 없는 종목 — 원본처럼 '찾지 못함'
            self.data[slug('/api/' + kind + self.nm.code[real_code])] = {'error': 'not_found'}
        for book, p in self.whatif.items():
            self.data['whatif_scope_' + book] = tf.walk(self.raw[p], ctx=Ctx('usd' if book == 'us' else 'krw'))
        for book in self.markets:          # What-if 종목 검색 — 입력할 때만 부른다 → 표본 목록 하나로
            mk = book if book in ('kr', 'us', 'coin') else 'kr'
            items = []
            for rc in self.nm.primary[mk]:
                sc = self.nm.code[rc]
                nm = next((self.nm.name[n] for n in self.real['pairs'].get(rc, ()) if n in self.nm.name), sc)
                items.append({'code': sc, 'name': nm})
            self.data['whatif_search_scope_' + book] = {'items': items}
        self.fix_counts()
        self.fix_texts()
        self.fix_private()

    def fix_private(self):
        """짧아서 문장 교체를 피한 실제 매매 일화(미국 장부 묶음 이름·키, 종목별 '자료 없음' 사유)를 일반 표현으로."""
        ub = self.data.get('us_book')
        if isinstance(ub, dict):
            keys = {}
            for i, b in enumerate(ub.get('bets') or []):
                if isinstance(b, dict):
                    keys[b.get('key')] = 'bet_%d' % (i + 1)
                    b['key'] = keys[b.get('key')]
                    b['name'] = BET_NAMES[i % len(BET_NAMES)]
            for i, g in enumerate(ub.get('groups') or []):
                if not isinstance(g, dict):
                    continue
                k = g.get('key') or ''
                if k.startswith('bet:') and k[4:] in keys:
                    j = int(keys[k[4:]].split('_')[1]) - 1
                    g['key'], g['name'] = 'bet:' + keys[k[4:]], BET_NAMES[j % len(BET_NAMES)]

        def na(o):
            if isinstance(o, dict):
                return {k: ({c: '분기 재무 자료 없음' for c in v} if k == 'na_codes' and isinstance(v, dict) else na(v))
                        for k, v in o.items()}
            if isinstance(o, list):
                return [na(v) for v in o]
            return o
        for sl in list(self.data):
            self.data[sl] = na(self.data[sl])

    def ctx_of(self, path):
        if 'scope=us' in path or path.startswith('us_'):
            return 'usd'
        if 'scope=coin' in path:
            return 'coin'
        return 'krw'

    def b_latest(self, path, L):
        now = int(time.time())
        out = json.loads(json.dumps(L))
        out['ts'] = now
        out['stale_buckets'] = []           # 체험판은 수집 상태를 항상 정상으로(‘수집 중단’ 빨간 줄이 뜨지 않게)
        out['as_of_kst'] =time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(now + 9 * 3600))
        st, co, us = grp(STOCK_TOTAL, 'stock'), grp(COIN_TOTAL, 'coin'), grp(USD_TOTAL, 'usd')
        out['stock'], out['coin'], out['usd'], out['krw'] = st, co, us, merge_grp(st, co)
        cap = out.get('capital') or {}
        cap.update(self.cap_block(cap, CAPITAL['stock'], self.k['krw']))
        ucap = out.get('us_capital') or {}
        ucap.update(self.cap_block(ucap, (ucap.get('net_capital') or 0) * self.k['usd'], self.k['usd']))
        ccap = out.get('coin_capital') or {}
        ccap.update(self.cap_block(ccap, CAPITAL['coin'], self.k['coin']))
        bb = out.get('by_bucket') or {}
        for b, v in bb.items():
            if b in BUCKET_SHARE:
                g = grp(STOCK_TOTAL * BUCKET_SHARE[b], 'stock')
            elif b == 'KORBIT':
                g = dict(co)
            elif b == 'ROBINHOOD':
                g = dict(us)
            else:
                continue
            g.update({'positions': {'GENERAL': 4, 'ISA': 6, 'PENSION': 2, 'KORBIT': 3, 'ROBINHOOD': 8}.get(b, v.get('positions')),
                      'currency': v.get('currency'), 'ts': now})
            bb[b] = g
        do = out.get('day_open') or {}
        for k2, base, r in (('krw', out['krw'], 0.004), ('usd', us, -0.003), ('coin', co, 0.012)):
            if k2 in do:
                do[k2] = {kk: round(vv / (1 + r), 2) for kk, vv in base.items()}
        return out

    def cap_block(self, cap, net, k):
        out = {'net_capital': round(net, 2)}
        for key in ('peak_capital', 'total_deposit', 'total_withdraw'):
            if is_num(cap.get(key)):
                out[key] = round(cap[key] * k, 2)
        if is_num(out.get('peak_capital')) and abs(out['peak_capital']) < abs(net):
            out['peak_capital'] = round(net, 2)
        return out

    def b_series(self, path, s):
        cv = self.curves
        us_cap = ((self.raw['latest'].get('us_capital') or {}).get('net_capital') or 0) * self.k['usd']
        pts = []
        for p in s.get('points') or []:
            t = p['t']
            k, c, u = cv['krw'](t), cv['coin'](t), cv['usd'](t)
            st = k - c
            q = dict(p)
            for name, g in (('krw', merge_grp(grp(st, 'stock'), grp(c, 'coin'))), ('stock', grp(st, 'stock')),
                            ('coin', grp(c, 'coin')), ('usd', grp(u, 'usd'))):
                if name in q:
                    q[name] = g
            if isinstance(q.get('by_bucket'), dict):
                bb = {}
                wig = {b: 1 + 0.04 * math.sin(t / 86400.0 / (17 + 9 * i) + i) for i, b in enumerate(BUCKET_SHARE)}
                norm = sum(BUCKET_SHARE[b] * wig[b] for b in BUCKET_SHARE)
                for b, v in q['by_bucket'].items():
                    if v is None:
                        bb[b] = None
                    elif b in BUCKET_SHARE:
                        bb[b] = round(st * BUCKET_SHARE[b] * wig[b] / norm, 2)
                    elif b == 'KORBIT':
                        bb[b] = round(c, 2)
                    elif b == 'ROBINHOOD':
                        bb[b] = round(u, 2)
                q['by_bucket'] = bb
            if isinstance(q.get('by_bucket_capital'), dict):
                q['by_bucket_capital'] = {b: (None if v is None else BUCKET_CAPITAL.get(b, v))
                                          for b, v in q['by_bucket_capital'].items()}
            if isinstance(q.get('by_bucket_pnl'), dict):
                q['by_bucket_pnl'] = {b: (None if v is None else round(UNREAL['coin'] * 100, 2))
                                      for b, v in q['by_bucket_pnl'].items()}
            if q.get('capital') is not None:
                q['capital'] = CAPITAL['stock']
            if q.get('coin_capital') is not None:
                q['coin_capital'] = CAPITAL['coin']
            if q.get('us_capital') is not None:
                q['us_capital'] = round(us_cap, 2)
            pts.append(q)
        out = dict(s)
        out['points'] = pts
        return out

    def b_benchmark(self, path, b):
        if not isinstance(b, dict) or b.get('empty') or not b.get('mine'):
            return self.tf.walk(b)
        scope = re.search(r'scope=(\w+)', path).group(1)
        cv = self.curves['usd' if scope == 'us' else 'coin' if scope == 'coin' else 'krw']
        rng = re.search(r'range=(\w+)', path).group(1)
        t0 = b['mine'][0][0]
        out = self.tf.walk({k: v for k, v in b.items() if k not in ('mine', 'benchmarks', 'summary')})
        out['mine'] = [[t, round(100 * cv(t) / cv(t0), 4)] for t, _ in b['mine']]
        mine_pct = (out['mine'][-1][1] / 100 - 1) * 100
        summ = {'mine_pct': round(mine_pct, 2)}
        benches = []
        for i, bm in enumerate(b.get('benchmarks') or []):
            bc = Curve(100.0, BENCH_RET[i % 2], self.now, self.all_days, 5.0 + i, amp=0.02)
            pts = bm.get('points') or []
            tb0 = pts[0][0] if pts else t0
            nb = dict(bm)
            nb['symbol'] = self.nm.subst(bm['symbol']) if isinstance(bm.get('symbol'), str) else bm.get('symbol')
            nb['name'] = self.nm.subst(bm['name']) if isinstance(bm.get('name'), str) else bm.get('name')
            nb['points'] = [[t, round(100 * bc(t) / bc(tb0), 4)] for t, _ in pts]
            benches.append(nb)
            if pts:
                bp = (nb['points'][-1][1] / 100 - 1) * 100
                summ[nb['symbol']] = round(bp, 2)
                summ['vs_' + nb['symbol']] = round(mine_pct - bp, 2)
        out['benchmarks'] = benches
        out['summary'] = summ
        out['range'] = rng
        return out

    def b_attribution(self, path, a):
        if not isinstance(a, dict) or a.get('empty') or not is_num(a.get('start')):
            return self.tf.walk(a)
        scope = re.search(r'scope=(\w+)', path).group(1)
        cv = self.curves['usd' if scope == 'us' else 'krw']
        out = self.tf.walk(a, ctx=Ctx('usd' if scope == 'us' else 'krw'))
        st, en = cv(a['start']), cv(a['end'])
        out.update({'start_total': round(st, 2), 'end_total': round(en, 2), 'change': round(en - st, 2),
                    'net_flow': 0.0, 'gain': round(en - st, 2), 'gain_pct': round((en / st - 1) * 100, 2),
                    'flow_share': 0.0})
        return out

    def b_ranking(self, path, r):
        mk = 'us' if 'scope=us' in path else 'coin' if 'scope=coin' in path else 'kr'
        out = self.tf.walk(r, ctx=Ctx({'kr': 'krw', 'us': 'usd', 'coin': 'coin'}[mk]))
        ev = {'kr': grp(STOCK_TOTAL, 'stock')['eval'], 'us': grp(USD_TOTAL, 'usd')['eval'],
              'coin': grp(COIN_TOTAL, 'coin')['eval']}[mk]
        items = out.get('items') or []
        for it in items:
            if is_num(it.get('weight_pct')):
                it['eval_amount'] = like(1, ev * it['weight_pct'] / 100.0)
        out['total_eval'] = int(round(ev))
        if 'halted_value' in out:
            out['halted_value'] = 0
        return out

    def b_trust(self, path, t):
        """데이터 신뢰도 배지 — 정적 사이트는 시간이 갈수록 '수집 오래됨'이 되므로 체험판에서는 항상 정상으로 고정."""
        if not isinstance(t, dict) or t.get('error'):
            return self.tf.walk(t)
        out = {k: v for k, v in t.items() if k not in ('sources',)}
        out['level'] = 'ok'
        out['summary'] = '문제 0 · 주의 0'
        srcs = []
        for s in t.get('sources') or []:
            srcs.append({'name': self.nm.subst(s.get('name') or ''), 'level': 'ok', 'status': '정상',
                         'last': s.get('last'), 'detail': '정상', 'coverage': s.get('coverage'),
                         'affects': [self.nm.subst(a) for a in (s.get('affects') or []) if isinstance(a, str)]})
        out['sources'] = srcs
        return out

    def b_changes(self, path, c):
        """오늘 달라진 것 — 하루 손익 줄을 헤더(총자산·오늘)와 같은 가짜 하루 변화로."""
        mk = re.search(r'scope=(\w+)', path).group(1)
        cur = {'kr': 'krw', 'us': 'usd', 'coin': 'coin'}.get(mk, 'krw')
        out = self.tf.walk(c, ctx=Ctx(cur))
        if not isinstance(out.get('day'), dict):
            return out
        base, r, head = {'kr': (STOCK_TOTAL, 0.004, '오늘 주식'), 'us': (USD_TOTAL, -0.003, '간밤'),
                         'coin': (COIN_TOTAL, 0.012, '하루 손익')}.get(mk, (STOCK_TOTAL, 0.004, '오늘'))
        gain = base - base / (1 + r)
        out['day'] = {'gain': round(gain, 2), 'pct': round(r * 100, 2)}
        if is_num(out.get('total')):
            out['total'] = round(base, 2)
        sign = '+' if gain >= 0 else '−'
        money = ('$%s' % '{:,}'.format(int(round(abs(gain))))) if mk == 'us' else '{:,}원'.format(int(round(abs(gain))))
        # 기준(전일 종가 대비 등)은 위 줄(chgbasis)에 이미 나오므로 생략 — 40자 안
        out['day_text'] = '%s %s %s%s (%s%.2f%%)' % ('🔺' if gain >= 0 else '🔻', head, sign, money, sign, abs(r) * 100)
        return out

    def b_sectors(self, path, s):
        mk = 'us' if 'scope=us' in path else 'kr'
        ev = grp(STOCK_TOTAL, 'stock')['eval'] if mk == 'kr' else grp(USD_TOTAL, 'usd')['eval']
        wmap = {}
        rk = self.data.get('ranking' if mk == 'kr' else 'ranking_scope_us')
        if rk is None:
            rk = self.b_ranking('ranking' if mk == 'kr' else 'ranking?scope=us',
                                self.raw['ranking' if mk == 'kr' else 'ranking?scope=us'])
        for it in rk.get('items') or []:
            wmap[it['code']] = it.get('weight_pct') or 0
        out = self.tf.walk(s, ctx=Ctx('usd' if mk == 'us' else 'krw'))
        slices = []
        for sl in out.get('slices') or []:
            items = [i for i in (sl.get('items') or []) if i.get('symbol') in wmap]
            if not items:
                continue
            for i in items:
                i['eval'] = round(ev * wmap[i['symbol']] / 100.0, 2)
            sl['items'] = items
            sl['eval'] = round(sum(i['eval'] for i in items), 2)
            sl['positions'] = len(items)
            slices.append(sl)
        tot = sum(x['eval'] for x in slices) or 1
        for sl in slices:
            sl['pct'] = round(sl['eval'] / tot * 100, 2)
            for i in sl['items']:
                i['pct'] = round(i['eval'] / tot * 100, 2)
        slices.sort(key=lambda x: -x['eval'])
        out['slices'] = slices
        out['total'] = round(tot, 2)
        return out

    def b_quant(self, path, q):
        mk = re.search(r'scope=(\w+)', path).group(1)
        out = self.tf.walk(q, ctx=Ctx({'kr': 'krw', 'us': 'usd', 'coin': 'coin'}.get(mk, 'krw')))
        if 'panel=track' in path:
            cv = self.curves['usd' if mk == 'us' else 'coin' if mk == 'coin' else 'krw']
            for sh in out.get('shadow') or []:
                c = sh.get('compare') or {}
                acc = c.get('account') or []
                if len(acc) >= 2:
                    def ts(d):
                        return time.mktime(time.strptime(d, '%Y-%m-%d'))
                    t0 = ts(acc[0][0])
                    c['account'] = [[d, round(100 * cv(ts(d)) / cv(t0), 2)] for d, _ in acc]
                    c['account_pct'] = round(c['account'][-1][1] - 100, 2)
                    if is_num(c.get('shadow_pct')):
                        c['shadow_vs_account'] = round(c['shadow_pct'] - c['account_pct'], 2)
        if 'panel=perf' in path and not out.get('empty'):
            self.perf_rewrite(out, self.curves['usd' if mk == 'us' else 'coin' if mk == 'coin' else 'krw'], mk)
        if 'panel=factor' in path and isinstance(out.get('etfs'), dict):
            # 팩터 근사용 지수 ETF 가 실명 사전과 겹쳐 코드가 표본으로 바뀌었으면 이름은 일반 표현으로
            for k in (q.get('etfs') or {}):
                if k in self.nm.code:
                    out['etfs'][self.nm.code[k]] = '지수 추종 ETF'
        if 'panel=whatif' in path and isinstance(out.get('held'), list):
            ev = {'kr': grp(STOCK_TOTAL, 'stock')['eval'], 'us': grp(USD_TOTAL, 'usd')['eval'],
                  'coin': grp(COIN_TOTAL, 'coin')['eval']}.get(mk, 0)
            for h in out['held']:
                if is_num(h.get('weight_pct')):
                    h['eval'] = round(ev * h['weight_pct'] / 100.0, 2)
        return out

    def daily_path(self, cv, start, end, tag):
        """영업일 하루하루의 가짜 계좌 지수 — 곡선에 하루 잡음(±0.6%)을 얹는다(끝값은 그대로)."""
        d0 = time.mktime(time.strptime(start, '%Y-%m-%d'))
        d1 = time.mktime(time.strptime(end, '%Y-%m-%d'))
        dates, vals = [], []
        t = d0
        while t <= d1 + 1:
            tm = time.localtime(t)
            if tm.tm_wday < 5:
                ds = time.strftime('%Y-%m-%d', tm)
                z = (h01('d', tag, ds) + h01('e', tag, ds) + h01('f', tag, ds) - 1.5) * 2.0 * 0.006
                dates.append(ds)
                vals.append(cv(t + 6 * 3600) * (1 + (z if ds != end else 0)))
            t += 86400
        return dates, vals

    @staticmethod
    def ratios(vals, rf):
        if len(vals) < 3:
            return None
        rets = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]
        n = len(rets)
        mean = sum(rets) / n
        sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / max(1, n - 1))
        dn = math.sqrt(sum(min(0.0, r) ** 2 for r in rets) / n)
        ann_ret = ((vals[-1] / vals[0]) ** (252.0 / n) - 1) * 100
        ann_vol = sd * math.sqrt(252) * 100
        peak, mdd = vals[0], 0.0
        for v in vals:
            peak = max(peak, v)
            mdd = min(mdd, v / peak - 1)
        return {'sharpe': round((ann_ret - rf) / ann_vol, 2) if ann_vol else None,
                'sortino': round((ann_ret - rf) / (dn * math.sqrt(252) * 100), 2) if dn else None,
                'calmar': round(ann_ret / abs(mdd * 100), 2) if mdd else None,
                'ann_ret': round(ann_ret, 1), 'ann_vol': round(ann_vol, 1)}

    def perf_rewrite(self, out, cv, mk):
        """퀀트 성과(샤프·언더워터)의 '내 계좌' 쪽을 가짜 곡선으로 다시 계산한다(지수 쪽은 그대로)."""
        start, end = out.get('start'), out.get('end')
        if not (isinstance(start, str) and isinstance(end, str)):
            return
        dates, vals = self.daily_path(cv, start, end, mk)
        if len(vals) < 30:
            return
        idx = {d: i for i, d in enumerate(dates)}

        def at(d):
            if d in idx:
                return idx[d]
            lo = [i for i, x in enumerate(dates) if x <= d]
            return lo[-1] if lo else 0
        rf = out.get('rf_pct') or 0
        peak, dd = vals[0], []
        for v in vals:
            peak = max(peak, v)
            dd.append((v / peak - 1) * 100)
        out['underwater'] = [[d, round(dd[at(d)], 2)] for d, _ in (out.get('underwater') or [])]
        out['current_dd'] = round(dd[-1], 2)
        eps, i, n = [], 0, len(vals)
        while i < n:
            if dd[i] < 0:
                j = i
                while j < n and dd[j] < 0:
                    j += 1
                seg = range(i, j)
                tr = min(seg, key=lambda k: dd[k])
                if dd[tr] <= -3:
                    pk = i - 1 if i > 0 else 0
                    ongoing = j >= n
                    eps.append({'peak': dates[pk], 'trough': dates[tr], 'recovered': None if ongoing else dates[j],
                                'depth_pct': round(dd[tr], 1), 'to_trough_days': tr - pk,
                                'recover_days': None if ongoing else j - tr, 'total_days': (n - 1 if ongoing else j) - pk,
                                'ongoing': ongoing})
                i = j
            else:
                i += 1
        eps.sort(key=lambda e: e['depth_pct'])
        out['episodes'] = eps[:5]
        full = self.ratios(vals, rf)
        if full:
            out['full'] = full
        for w, win in (out.get('windows') or {}).items():
            try:
                N = int(w)
            except ValueError:
                continue
            if not isinstance(win, dict) or not win.get('available'):
                continue
            mine = []
            for p in win.get('mine') or []:
                k = at(p.get('d'))
                r = self.ratios(vals[max(0, k - N):k + 1], rf)
                if r:
                    mine.append({'d': p['d'], 'sharpe': r['sharpe'], 'sortino': r['sortino'], 'calmar': r['calmar']})
            win['mine'] = mine
            now = self.ratios(vals[-N - 1:], rf)
            if now:
                win['now'] = now

    def b_growth(self, path, g):
        """돈 불리기 성적표 — 월말 자산·번 돈을 가짜 곡선(한국 총액)으로. 입출금은 0(곡선에 입금이 없다)."""
        out = self.tf.walk(g)
        months = out.get('months') or []
        if not months:
            return out
        cv = self.curves['krw']

        def month_end(m):
            y, mo = int(m[:4]), int(m[5:7])
            y2, mo2 = (y + 1, 1) if mo == 12 else (y, mo + 1)
            return min(self.now, time.mktime((y2, mo2, 1, 0, 0, 0, 0, 0, -1)) - 3600)
        prev = None
        for m in months:
            end = cv(month_end(m['month']))
            start = prev if prev is not None else cv(month_end(m['month']) - 30 * 86400)
            m.update({'start_value': int(round(start)), 'flow': 0, 'gain': int(round(end - start)),
                      'end_value': int(round(end)), 'return_pct': round((end / start - 1) * 100, 1)})
            prev = end
        for i, m in enumerate(months):
            if 'gain_12m' in m:
                m['gain_12m'] = sum(x['gain'] for x in months[max(0, i - 11):i + 1])
        years = {}
        for m in months:
            years.setdefault(int(m['month'][:4]), []).append(m)
        for y in out.get('years') or []:
            ms = years.get(y.get('year')) or []
            if ms:
                s, e = ms[0]['start_value'], ms[-1]['end_value']
                y.update({'start_value': s, 'flow': 0, 'gain': e - s, 'end_value': e, 'return_pct': round((e / s - 1) * 100, 1)})
        last = months[-12:]
        out['last12'] = {'gain': sum(m['gain'] for m in last), 'months': len(last), 'positive': sum(1 for m in last if m['gain'] > 0)}
        out['all_months'] = {'months': len(months), 'positive': sum(1 for m in months if m['gain'] > 0)}
        out['value'] = int(round(cv(self.now)))
        out['net_capital'] = CAPITAL['stock'] + CAPITAL['coin']
        out['profit'] = out['value'] - out['net_capital']
        return out

    def fix_counts(self):
        """화면 제목에 쓰이는 개수를 남긴 행 수로 다시 센다."""
        for key in ('tenbagger', 'forecast'):
            d = self.data.get(key)
            if not d:
                continue
            for tb in ([d, d.get('tenbagger')] if key == 'forecast' else [d]):
                if not isinstance(tb, dict):
                    continue
                cands = tb.get('candidates')
                cnt = tb.get('counts')
                if isinstance(cands, list) and isinstance(cnt, dict) and 'candidates' in cnt:
                    cnt['candidates'] = len(cands)
                    cnt['registered'] = sum(1 for c in cands if c.get('registered'))
                    cnt['flagged'] = sum(1 for c in cands if c.get('red_flag'))
                    cnt['traps'] = sum(1 for c in cands if ((c.get('scan') or {}).get('traps')))
                    cnt['signals_on'] = sum(1 for c in cands if ((c.get('scan') or {}).get('on')))
                    cnt['with_ai'] = sum(1 for c in cands if c.get('ai'))
                    cnt['with_card'] = sum(1 for c in cands if c.get('ai_card'))
                bd = tb.get('board') or {}
                for m in (bd.get('winners') or {}).values():
                    rows = m.get('rows') or []
                    m['n'] = len(rows)
                    m['weight'] = round(sum((r.get('weight') or 0) for r in rows), 4)
                    if isinstance(m.get('counts'), dict):
                        for col in list(m['counts']):
                            m['counts'][col] = sum(1 for r in rows if r.get('color') == col)
                rc = tb.get('rule_card') or {}
                for mk, m in (rc.get('markets') or {}).items():
                    items = m.get('items') or []
                    held_n = len(self.nm.primary.get(mk.lower(), []))
                    if isinstance(m.get('n'), int):
                        m['n'] = held_n
                    for r in m.get('rules') or []:
                        if r.get('id') == 'stop':
                            r['n'] = len(items)
                            r['weight'] = round(sum((x.get('weight') or 0) for x in items), 4)
                            if r.get('breach') is not None:
                                r['breach'] = bool(items)
                        if r.get('id') == 'count' and is_num(r.get('limit')):
                            r['value'] = held_n
                            r['over'] = max(0, held_n - int(r['limit']))
                            r['breach'] = r['over'] > 0
                    if isinstance(m.get('decided'), dict):
                        m['decided'] = {'none': sum(1 for x in items if not x.get('decision')),
                                        'hold': sum(1 for x in items if (x.get('decision') or {}).get('action') == 'hold'),
                                        'sell': sum(1 for x in items if (x.get('decision') or {}).get('action') == 'sell')}
                if isinstance(rc.get('n_breach'), int):
                    rc['n_breach'] = sum(1 for m in (rc.get('markets') or {}).values()
                                         for r in (m.get('rules') or []) if r.get('breach'))
                eb = tb.get('entry_board') or {}
                if isinstance(eb.get('counts'), dict):
                    buys = [x for m in (eb.get('markets') or {}).values() for x in (m.get('buy') or [])]
                    eb['counts']['buy'] = len(buys)
                    eb['counts']['new'] = sum(1 for x in buys if not x.get('held'))
                    eb['counts']['add'] = sum(1 for x in buys if x.get('held'))
                for m in ((tb.get('holdings') or {}).get('markets') or {}).values():
                    if isinstance(m, dict) and isinstance(m.get('holdings'), list):
                        m['n'] = len(m['holdings'])
                    for part in ('stop', 'review'):
                        sp = ((m or {}).get('summary') or {}).get(part)
                        if isinstance(sp, dict) and isinstance(sp.get('items'), list):
                            sp['n'] = len(sp['items'])
                            sp['weight'] = round(sum((x.get('weight') or 0) for x in sp['items']), 4)
                pp = tb.get('paper') or {}
                if isinstance(pp.get('trades'), list):
                    pp['trades_n'] = len(pp['trades'])
            if key == 'tenbagger':
                self.fix_board_numbers(d.get('rule_card') or {})
            if key == 'forecast':
                oq = d.get('open_questions') or []
                cnt = d.get('counts') or {}
                if cnt:
                    cnt['open'] = len(oq)
                    cnt['resolved'] = len(d.get('resolved') or [])
                    cnt['claims_30d'] = len(d.get('claims') or [])
                for s in d.get('scenarios') or []:
                    s['open'] = sum(1 for q in oq if q.get('scenario') == s.get('id'))

    def fix_texts(self):
        """실제 개수가 박힌 짧은 문장('손절선 아래 13종목')을 남긴 행 기준으로, 종이 계좌 과거 시험 금액을 계좌 크기에 맞게."""
        rc = (self.data.get('tenbagger') or {}).get('rule_card') or {}
        n_stop = {mk: len((m or {}).get('items') or []) for mk, m in (rc.get('markets') or {}).items()}

        def fix(o, mk):
            if isinstance(o, dict):
                return {k: fix(v, mk) for k, v in o.items()}
            if isinstance(o, list):
                return [fix(v, mk) for v in o]
            if isinstance(o, str) and '손절선 아래' in o and o not in POOL_SET:
                return re.sub(r'(손절선 아래 )\d+(종목)', lambda m: '%s%d%s' % (m.group(1), n_stop.get(mk, 0), m.group(2)), o)
            return o
        for sl in list(self.data):
            mk = 'US' if 'scope_us' in sl else 'KR'
            self.data[sl] = fix(self.data[sl], mk)
        # 종이 계좌 과거 시험 — 누적 매수 원장 전체라 계좌보다 몇 배 크다 → 매수 합계가 주식 총액(₩900만)이 되게 같은 비율로
        for d in (self.data.get('tenbagger'), (self.data.get('forecast') or {}).get('tenbagger')):
            bt = ((d or {}).get('paper') or {}).get('backtest')
            if isinstance(bt, dict) and is_num(bt.get('buy_total')) and bt['buy_total']:
                f = STOCK_TOTAL / float(bt['buy_total'])

                def sc(o):
                    if isinstance(o, dict):
                        money = lambda k: 'pct' not in k and any(t in k for t in ('profit', 'total', 'diff', 'hold', 'amount', 'value'))
                        return {k: (like(v, v * f) if is_num(v) and money(k) else sc(v)) for k, v in o.items()}
                    if isinstance(o, list):
                        return [sc(v) for v in o]
                    return o
                d['paper']['backtest'] = sc(bt)

    def fix_board_numbers(self, rc):
        """첫 화면 숫자 칸(종목 수·물린 돈)을 남긴 표본 행에 맞춘다."""
        bd = self.data.get('board') or {}
        for mk, nums in (bd.get('numbers') or {}).items():
            m = (rc.get('markets') or {}).get(mk) or {}
            for n in nums:
                if n.get('id') == 'count':
                    cnt = len(self.nm.primary.get(mk.lower(), []))
                    lim = re.search(r'\d+', n.get('limit_text') or '')
                    n['value_text'] = '%d종목' % cnt
                    n['color'] = 'red' if lim and cnt > int(lim.group(0)) else 'green'
                elif n.get('id') == 'stop':
                    items = m.get('items') or []
                    w = sum((x.get('weight') or 0) for x in items)
                    n['value_text'] = '%d종목 %.1f%%' % (len(items), w * 100) if items else '없음'
                    n['color'] = 'red' if items else 'green'

    # ── 쓰기 ──
    def write(self):
        ddir = os.path.join(self.out, 'data')
        os.makedirs(ddir, exist_ok=True)
        for f in os.listdir(ddir):                     # 생성기 산출물만 있는 폴더 — 지난 실행 파일 정리
            if f.endswith('.json'):
                os.remove(os.path.join(ddir, f))
        for sl, obj in sorted(self.data.items()):
            with open(os.path.join(ddir, sl + '.json'), 'w', encoding='utf-8') as fh:
                json.dump(no_port_lookalike(obj), fh, ensure_ascii=False, separators=(',', ':'))
        write_pages(self.src_text, self.out, self.nm.code)


PORT_RX = re.compile(r'(?<!\d)8787(?!\d)')


def no_port_lookalike(o):
    """가짜 숫자가 우연히 내부 포트(8787)처럼 보이면 끝자리를 살짝 바꾼다(검사가 걸러내는 글자라)."""
    if isinstance(o, dict):
        return {k: no_port_lookalike(v) for k, v in o.items()}
    if isinstance(o, list):
        return [no_port_lookalike(v) for v in o]
    if is_num(o) and PORT_RX.search(json.dumps(o)):
        if isinstance(o, int):
            return o + 1
        s = repr(o)
        step = 10 ** -(len(s.split('.')[1])) if '.' in s and 'e' not in s else 1e-6
        for cand in (round(o + step, 10), o + 1.0):
            if not PORT_RX.search(json.dumps(cand)):
                return cand
        return o + 2.0
    if isinstance(o, str) and PORT_RX.search(o):
        return PORT_RX.sub('8788', o)
    return o


# ───────────────────────────── HTML 복사 + 패치 ─────────────────────────────
def patches(code_map=None):
    """(파일, 정규식, 바꿀 것, 기대 적중 횟수). 적중 횟수가 다르면 실패로 멈춘다.

    원본 문구 속 종목 이름(코어·코인 설명)은 패턴에 이름을 적지 않고 모양으로만 잡는다 — 이 파일도 공개 리포에 올라간다.
    """
    cm = code_map or {}

    def lit(f, a, b, n):
        return (f, re.compile(re.escape(a)), b.replace('\\', '\\\\'), n)

    def mapped(fmt):
        return lambda m: fmt % cm.get(m.group(1), m.group(1))
    P = []
    for f in ('index.html', 'tenbagger.html', 'forecast.html'):
        P.append(lit(f, '<meta charset="utf-8">', '<meta charset="utf-8">\n<script src="./demo.js"></script>', 1))
        P.append(lit(f, '<title>', '<title>[체험판] ', 1))
    P += [
        lit('index.html', 'href="/quant.css"', 'href="./quant.css"', 1),
        lit('index.html', 'src="/quant.js"', 'src="./quant.js"', 1),
        lit('index.html', 'href="/forecast"', 'href="./forecast.html"', 1),
        lit('index.html', 'href="/tenbagger', 'href="./tenbagger.html', 3),
        lit('index.html', 'setInterval(load, 30000);', 'if (!window.DEMO) setInterval(load, 30000);', 1),
        lit('tenbagger.html', 'href="/forecast"', 'href="./forecast.html"', 1),
        lit('tenbagger.html', 'href="/"', 'href="./index.html"', 1),
        lit('forecast.html', 'href="/tenbagger"', 'href="./tenbagger.html"', 1),
        lit('forecast.html', 'href="/"', 'href="./index.html"', 1),
        # 원본 설명 문구 속 종목 이름 — 일반 표현으로(이름은 패턴에 적지 않는다)
        ('index.html', re.compile(r'국면은 [A-Z]{2,5} 기준, 코어\([^)]*\)는 손절 판정 없음'),
         '국면은 대장 코인 기준, 코어(대형 코인 3종)는 손절 판정 없음', 1),
        ('index.html', re.compile(r"'[A-Z]{2,5} 국면 위험"), "'대장 코인 국면 위험", 1),
        ('index.html', re.compile(r'`[A-Z]{2,5}( 20일 \$\{sg\(r\.btc_20d\))'), r'`대장 코인\1', 1),
        ('index.html', re.compile(r'`[A-Z]{2,5}( 200일선 \$\{sg\(r\.btc_vs_200ma\))'), r'`대장 코인\1', 1),
        ('index.html', re.compile(r'원화 시세\([^)]*\)'), '원화 시세(대장 코인 2종)', 2),
        # 원본 주석 속 실제 매매 일화 예시 — 통째로 뺀다(일화 이름은 패턴에 적지 않는다)
        ('index.html', re.compile(r' \(예: [^)]*강제청산\)'), '', 1),
        # 원본 주석 속 실제 계좌 금액·건수·수익률 — 공개 페이지 소스에 남지 않게 일반 표현으로
        ('index.html', re.compile(r'순수익이 [\d,]+만원'), '순수익이 수천만 원', 1),
        ('index.html', re.compile(r'축이 0~[\d,]+만이 되어 하루 [\d,]+만원 변동이 \d+% 짜리'), '축이 0부터 잡혀 하루 변동이 아주 얇은', 1),
        ('index.html', re.compile(r'\(ISA [\d,]+만 vs 연금 [\d,]+만\)'), '(계좌마다 몇 배씩 차이)', 1),
        ('index.html', re.compile(r'축이 [\d,]+만~[\d,]+만으로'), '축이 크게', 1),
        ('index.html', re.compile(r'\(미국 \d+건, 한국 \d+건\)'), '(수십 건)', 1),
        ('index.html', re.compile(r'일반계좌가 \+\d+%→\+\d+%로'), '일반계좌가 크게 떨어진 것', 1),
        ('tenbagger.html', re.compile(r'코어\([^)]*\)와 거래정지 종목은'), '코어 종목과 거래정지 종목은', 1),
        ('tenbagger.html', re.compile(r'분류표에 없는 ETF·[A-Z]{3}'), '분류표에 없는 ETF·상장지수증권', 2),
        ('quant.js', re.compile(r"sl\('qs-m', '[A-Z]{2,5}',"), "sl('qs-m', '대장 코인',", 1),
        ('quant.js', re.compile(r'\([A-Z]{2,5} 는 β 1 고정\)'), '(대장 코인은 β 1 고정)', 1),
        # 코드 비교·팩터 ETF 표 — 데이터 쪽 코드가 표본으로 바뀌었으면 같은 표본 코드로
        ('quant.js', re.compile(r"it\.code === '([A-Z]{2,5})'"), mapped("it.code === '%s'"), 1),
        ('quant.js', re.compile(r"d\.etfs\['([0-9A-Z]{6})'\]"), mapped("d.etfs['%s']"), 5),
    ]
    return P


def apply_patches(src_text, code_map=None):
    out = dict(src_text)
    for f, rx, b, n in patches(code_map):
        new, got = rx.subn(b, out[f])
        if got != n:
            raise SystemExit('패치 적중 횟수 다름: %s /%s/ — 기대 %d, 실제 %d (원본이 바뀌었는지 확인)' % (f, rx.pattern, n, got))
        out[f] = new
    return out


def write_pages(src_text, out_dir, code_map):
    pages = apply_patches(src_text, code_map)
    for f, txt in pages.items():
        with open(os.path.join(out_dir, f), 'w', encoding='utf-8') as fh:
            fh.write(txt)


def main(argv=None):
    ap = argparse.ArgumentParser(description='보여주기용 복제 대시보드 생성기')
    ap.add_argument('--src', default=DEFAULT_SRC)
    ap.add_argument('--api', default=DEFAULT_API)
    ap.add_argument('--out', default=ROOT)
    a = ap.parse_args(argv)
    ok = Builder(os.path.expanduser(a.src), a.api, a.out).run()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
