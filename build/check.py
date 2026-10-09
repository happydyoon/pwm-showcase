#!/usr/bin/env python3
"""새는지 검사 — 실명·내부 주소·계좌번호 모양·원문 문장·총액.

    python3 build/check.py [--api http://100.67.98.100:8787]

라이브 API 에서 실제 이름·코드를 받아 **메모리에서만** 모은 뒤 data/*.json · *.html · demo.js · quant.js 를 훑는다.
출력은 개수만(실명은 화면에도 파일에도 쓰지 않는다). 하나라도 걸리면 종료 코드 1.
"""
import argparse
import bisect
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_demo as M  # noqa: E402

# 계획서의 실명 출처(보유 목록·미국 장부·코인·텐배거 후보·보유·시나리오 종목·규칙 카드) + 같은 쌍이 보이는 곳
REAL_SOURCES = ['ranking', 'ranking?scope=us', 'ranking?scope=coin', 'us_book', 'tenbagger', 'forecast', 'entry',
                'scorecard', 'sectors', 'sectors?scope=us', 'risk', 'risk?scope=us', 'risk?scope=coin',
                'changes?scope=kr', 'changes?scope=us', 'changes?scope=coin', 'quant?panel=whatif&scope=coin']
FORBIDDEN = [
    ('내부 주소', re.compile(r'100\.67\.98\.100')),
    ('포트 8787', re.compile(r'(?<!\d)8787(?!\d)')),
    ('seokho', re.compile(r'seokho', re.I)),
    ('계좌번호 모양', re.compile(r'(?<!\d)\d{8}-\d{2}(?!\d)')),
    ('실제 매매 일화 흔적', re.compile(r'강제청산|거래 동결|ADR —')),
]
TOL = 0.01


def live_real(api):
    raw = {}
    for p in REAL_SOURCES:
        try:
            raw[p] = M.fetch(api, p)
        except Exception as e:  # noqa: BLE001 — 받지 못하면 검사 실패로 본다
            raise SystemExit('검사용 라이브 응답을 받지 못함: %s (%s)' % (M.slug('/api/' + p), type(e).__name__))
    return M.collect_real(raw)


def scan_files(out_dir):
    files = sorted(glob.glob(os.path.join(out_dir, 'data', '*.json')))
    files += [os.path.join(out_dir, f) for f in ('index.html', 'tenbagger.html', 'forecast.html', 'demo.js',
                                                 'quant.js', 'quant.css')]
    return [f for f in files if os.path.exists(f)]


def long_strings(o, out):
    if isinstance(o, dict):
        for v in o.values():
            long_strings(v, out)
    elif isinstance(o, list):
        for v in o:
            long_strings(v, out)
    elif isinstance(o, str) and len(o) > M.MAX_STR and o not in M.POOL_SET:
        out.append(o)


def run(out_dir=ROOT, real=None, verbose=True, api=M.DEFAULT_API):
    real = real or live_real(api)
    allow = M.sample_tokens()                 # 표본 사전의 이름·코드·심볼은 실명과 겹쳐도 예외
    rx = M.token_regex(set(real['tokens']) - allow)
    sample_rx = M.token_regex(allow)
    files = scan_files(out_dir)
    name_hits, name_files = 0, 0
    distinct = set()
    forb = {k: 0 for k, _ in FORBIDDEN}
    long_n = 0
    for f in files:
        with open(f, encoding='utf-8') as fh:
            txt = fh.read()
        # 표본 이름 안에 들어 있는 글자(예: 표본 이름의 일부가 실명)는 실명으로 세지 않는다
        spans = [m.span() for m in sample_rx.finditer(txt)]
        starts = [s for s, _ in spans]

        def inside(m):
            i =bisect.bisect_right(starts, m.start()) - 1
            return i >= 0 and spans[i][1] >= m.end()
        hits = [m.group(0) for m in rx.finditer(txt) if not inside(m)]
        if hits:
            name_hits += len(hits)
            name_files += 1
            distinct.update(hits)
        for k, r in FORBIDDEN:
            forb[k] += len(r.findall(txt))
        if f.endswith('.json'):
            ls = []
            long_strings(json.loads(txt), ls)
            long_n += len(ls)
    total = None
    lp = os.path.join(out_dir, 'data', 'latest.json')
    if os.path.exists(lp):
        with open(lp, encoding='utf-8') as fh:
            total = (json.load(fh).get('krw') or {}).get('total')
    total_ok = total is not None and abs(total - M.KRW_TOTAL) <= M.KRW_TOTAL * TOL
    ok = name_hits == 0 and not any(forb.values()) and long_n == 0 and total_ok
    if verbose:
        print('검사 파일 %d개 · 실명 사전 %d개(메모리, 표본 사전과 겹치는 %d개는 예외)' % (
            len(files), len(real['tokens']), len(set(real['tokens']) & allow)))
        print('  실명 남음: %d건 (서로 다른 이름 %d개 · 파일 %d개)' % (name_hits, len(distinct), name_files))
        for k, v in forb.items():
            print('  %s: %d건' % (k, v))
        print('  40자 넘는 문장 중 풀에 없는 것: %d건' % long_n)
        print('  한국 총액: %s (목표 ₩%s ±1%%) %s' % ('—' if total is None else '₩{:,.0f}'.format(total),
                                                 '{:,}'.format(M.KRW_TOTAL), '통과' if total_ok else '실패'))
        print('검사 결과:', '통과' if ok else '실패')
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description='보여주기용 사이트가 새는지 검사')
    ap.add_argument('--api', default=M.DEFAULT_API)
    ap.add_argument('--out', default=ROOT)
    a = ap.parse_args(argv)
    return 0 if run(a.out, api=a.api) else 1


if __name__ == '__main__':
    sys.exit(main())
