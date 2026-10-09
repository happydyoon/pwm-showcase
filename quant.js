/* 🔬 퀀트 분석 섹션 + 데이터 신뢰도 배지.
 *
 * index.html 의 전역(state·$·esc·won·usd)을 읽기만 한다. 패널은 접힌 채로 두고 펼칠 때
 * /api/quant?panel=…&scope=… 를 한 번 부른다(서버가 패널별로 메모). 탭(한국·미국·코인)이
 * 바뀌면 패널 목록을 그 시장 것으로 다시 그린다.
 *
 * ⚠️ 조회 전용. What-if 도 계산만 한다 — 주문 버튼·경로 없음.
 */
(function(){
'use strict';
const Q = {};
// index.html 의 최상위 const(state·$·esc)는 window 속성이 아니지만 전역 스코프라 이름으로 읽힌다
const mk = () => (typeof state !== 'undefined' && state.market) || 'kr';
const pct = (v, d = 1) => v == null ? '—' : Math.abs(v) < 0.5 / 10 ** d ? (0).toFixed(d) + '%'
  : (v > 0 ? '+' : '−') + Math.abs(v).toFixed(d) + '%';
const eokStr = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toLocaleString('ko-KR') + '억';
const num = (v, d = 1) => v == null ? '—' : Number(v).toFixed(d);
const pc = v => v == null ? '' : v > 0 ? 'up' : v < 0 ? 'down' : 'flat';
const money = (v, book) => v == null ? '—' : book === 'us'
  ? (v < 0 ? '−' : '') + '$' + Math.abs(Math.round(v)).toLocaleString('en-US')
  : (v < 0 ? '−' : '') + '₩' + Math.abs(Math.round(v)).toLocaleString('ko-KR');
const moneyShort = (v, book) => {
  if (v == null) return '—';
  if (book === 'us') return money(v, book);
  const a = Math.abs(v), s = v < 0 ? '−' : '';
  if (a >= 1e8) return s + (a / 1e8).toFixed(2) + '억';
  if (a >= 1e4) return s + Math.round(a / 1e4).toLocaleString('ko-KR') + '만';
  return s + Math.round(a).toLocaleString('ko-KR') + '원';
};
Q.util = {pct, num, pc, money, moneyShort};
const store = (k, v) => { try { v === undefined ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} };
const load = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };

/* ---------------- 선 그래프 (SVG, 날짜 문자열 x축) ---------------- */
// series: [{name, color, pts:[[d, v]], dash?, fill?}] · opt: {zero, fmt, height, band}
Q.line = function(series, opt = {}){
  const S = series.filter(s => s.pts && s.pts.length >= 2);
  if (!S.length) return '<div class="loading">그릴 데이터가 부족합니다.</div>';
  const dates = [...new Set(S.flatMap(s => s.pts.map(p => p[0])))].sort();
  const xi = new Map(dates.map((d, i) => [d, i]));
  const vals = S.flatMap(s => s.pts.map(p => p[1])).filter(v => v != null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (opt.zero != null){ lo = Math.min(lo, opt.zero); hi = Math.max(hi, opt.zero); }
  if (hi === lo){ hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
  const W = 600, H = opt.height || 190, L = 4, R = 44, T = 6, B = 18;
  const x = i => L + (dates.length < 2 ? 0 : i / (dates.length - 1)) * (W - L - R);
  const y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const fmt = opt.fmt || (v => v.toFixed(0));
  let g = '';
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
  ticks.forEach(t => {
    g += `<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" stroke="rgba(255,255,255,.06)"/>`;
    g += `<text class="ax" x="${W - R + 4}" y="${y(t) + 3}">${esc(fmt(t))}</text>`;
  });
  if (opt.zero != null)
    g += `<line x1="${L}" x2="${W - R}" y1="${y(opt.zero)}" y2="${y(opt.zero)}" stroke="rgba(255,255,255,.22)" stroke-dasharray="3 3"/>`;
  [0, Math.floor((dates.length - 1) / 2), dates.length - 1].forEach((i, k) => {
    const anchor = k === 0 ? 'start' : k === 2 ? 'end' : 'middle';
    g += `<text class="ax" x="${x(i)}" y="${H - 4}" text-anchor="${anchor}">${esc(String(dates[i]).slice(2))}</text>`;
  });
  for (const s of S){
    const pts = s.pts.filter(p => p[1] != null).map(p => `${x(xi.get(p[0])).toFixed(1)},${y(p[1]).toFixed(1)}`);
    if (s.fill){
      const first = s.pts[0], last = s.pts[s.pts.length - 1], base = y(opt.zero ?? lo);
      g += `<polygon points="${x(xi.get(first[0]))},${base} ${pts.join(' ')} ${x(xi.get(last[0]))},${base}" fill="${s.fill}"/>`;
    }
    g += `<polyline points="${pts.join(' ')}" fill="none" stroke="${s.color}" stroke-width="${s.width || 1.7}"
      ${s.dash ? `stroke-dasharray="${s.dash}"` : ''} vector-effect="non-scaling-stroke" stroke-linejoin="round"/>`;
  }
  const id = 'qc' + Math.random().toString(36).slice(2, 8);
  const lg = S.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('');
  Q._charts = Q._charts || {};
  Q._charts[id] = {S, dates, fmt: opt.tipFmt || fmt};
  return `<div class="qchart" data-chart="${id}"><div class="lg">${lg}</div>
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${g}
    <line class="hov" x1="0" x2="0" y1="${T}" y2="${H - B}" stroke="rgba(255,255,255,.25)" opacity="0"/></svg>
    <div class="tipq"></div></div>`;
};
// 호버 — 가장 가까운 날짜의 값들
document.addEventListener('mousemove', e => {
  const box = e.target.closest && e.target.closest('.qchart');
  document.querySelectorAll('.qchart .tipq').forEach(t => { if (!box || !box.contains(t)) t.style.opacity = 0; });
  if (!box) return;
  const c = (Q._charts || {})[box.dataset.chart]; if (!c) return;
  const svg = box.querySelector('svg'), r = svg.getBoundingClientRect();
  const W = 600, L = 4, R = 44;
  const fx = (e.clientX - r.left) / r.width * W;
  const i = Math.max(0, Math.min(c.dates.length - 1, Math.round((fx - L) / (W - L - R) * (c.dates.length - 1))));
  const d = c.dates[i];
  const rows = c.S.map(s => { const p = s.pts.find(q => q[0] === d);
    return p && p[1] != null ? `<div class="row"><span style="color:${s.color}">${esc(s.name)}</span><b>${esc(c.fmt(p[1]))}</b></div>` : ''; }).join('');
  const tip = box.querySelector('.tipq');
  tip.innerHTML = `<div style="color:var(--dim)">${esc(d)}</div>${rows}`;
  const hx = (L + i / Math.max(1, c.dates.length - 1) * (W - L - R)) / W * r.width;
  const hov = svg.querySelector('.hov'); hov.setAttribute('x1', L + i / Math.max(1, c.dates.length - 1) * (W - L - R));
  hov.setAttribute('x2', hov.getAttribute('x1')); hov.setAttribute('opacity', 1);
  tip.style.left = Math.min(r.width - 150, Math.max(0, hx + 10)) + 'px';
  tip.style.top = '24px'; tip.style.opacity = 1;
});

/* ---------------- 데이터 신뢰도 배지 ---------------- */
const LV_TXT = {ok: '데이터 정상', warn: '데이터 주의', bad: '데이터 문제'};
Q.trust = null;
async function refreshTrust(){
  const m = mk();
  try {
    const d = await fetch('/api/trust?scope=' + m).then(r => r.json());
    if (m !== mk() || d.error) return;
    Q.trust = d;
    renderTrust(d);
  } catch (e) {}
}
function renderTrust(d){
  const b = $('trustbadge');
  b.hidden = false;
  b.className = 'trust ' + d.level;
  b.innerHTML = `<i></i>${LV_TXT[d.level]}${d.level === 'ok' ? '' : ' · ' + esc(d.summary)}`;
  const rows = d.sources.map(s => `<tr><td class="lv"><i class="${s.level}"></i></td>
    <td><div class="nm">${esc(s.name)}</div><div class="af">영향: ${esc((s.affects || []).join(', ') || '—')}</div></td>
    <td class="dt">${esc(s.detail || s.last || '')}${s.coverage != null ? ` · ${s.coverage}%` : ''}</td></tr>`).join('');
  $('trustpop').innerHTML = `<table>${rows}</table>
    <div class="cap">초록=정상 · 노랑=늦거나 일부 빠짐 · 빨강=수집 실패/정지. 빨간 소스가 쓰이는 화면은 옛 숫자일 수 있습니다.</div>`;
  const bad = d.sources.filter(s => s.level === 'bad');
  const bar = $('trustbar');
  if (bad.length){
    const aff = [...new Set(bad.flatMap(s => s.affects || []))];
    bar.innerHTML = `⚠️ <b>${esc(bad[0].name)}</b>${bad.length > 1 ? ` 외 ${bad.length - 1}곳` : ''} 수집 문제 — ${esc(bad[0].detail || '')}.
      <span style="color:var(--dim)">${aff.slice(0, 3).map(esc).join(', ')}${aff.length > 3 ? ` 등 ${aff.length}개 화면` : ''}의 숫자가 옛것일 수 있습니다. 오른쪽 위 배지를 누르면 상세.</span>`;
    bar.classList.remove('hide');
  } else bar.classList.add('hide');
}

/* ---------------- 패널 레지스트리 ---------------- */
Q.panels = [];            // {id, title, hint, books, order, fetch?, render(d, el, book)}
const ORDER = {whatif: 10, risk: 20, stress: 30, ratios: 40, underwater: 50, factor: 60,
               calendar: 70, revisions: 80, flows: 90, track: 100};
Q.register = p => { Q.panels.push(p); Q.panels.sort((a, b) => (ORDER[a.id] || 99) - (ORDER[b.id] || 99)); };
const loaded = {};        // `${id}:${book}` → 응답

function renderSection(){
  const m = mk();
  const body = $('quantbody');
  const ps = Q.panels.filter(p => p.books.includes(m));
  body.innerHTML = ps.map(p => `<details class="qpanel" data-panel="${p.id}" ${load('pwm.q.' + p.id) === '1' ? 'open' : ''}>
    <summary><span class="t">${p.title}</span><span class="h">${esc(p.hint || '')}</span></summary>
    <div class="qbody" id="q-${p.id}"><div class="loading">불러오는 중…</div></div></details>`).join('');
  body.querySelectorAll('details.qpanel').forEach(det => {
    det.addEventListener('toggle', () => {
      store('pwm.q.' + det.dataset.panel, det.open ? '1' : undefined);
      if (det.open) openPanel(det.dataset.panel);
    });
    if (det.open) openPanel(det.dataset.panel);
  });
}

async function openPanel(id, force = false){
  const m = mk(), p = Q.panels.find(x => x.id === id), el = $('q-' + id);
  if (!p || !el) return;
  const key = id + ':' + m;
  if (!force && loaded[key]){ safeRender(p, loaded[key], el, m); return; }
  el.innerHTML = '<div class="loading">계산 중… (처음 한 번은 몇 초 걸립니다)</div>';
  try {
    const d = p.fetch ? await p.fetch(m) : await fetch(`/api/quant?panel=${id}&scope=${m}`).then(r => r.json());
    if (m !== mk()) return;
    if (d.error){ el.innerHTML = `<div class="err">계산 실패 — ${esc(d.detail || d.error)}</div>`; return; }
    loaded[key] = d;
    safeRender(p, d, el, m);
  } catch (e){ el.innerHTML = `<div class="err">불러오기 실패 — ${esc(e.message)}</div>`; }
}
Q.open = openPanel;
function safeRender(p, d, el, m){
  try { p.render(d, el, m); }
  catch (e){ el.innerHTML = `<div class="err">화면 그리기 실패 — ${esc(e.message)}</div>`; console.error(e); }
}

Q.setMarket = () => { $('trustpop').classList.add('hide'); renderSection(); refreshTrust(); };
Q.refresh = () => refreshTrust();

/* ================= 패널 8: 에이전트 적중률 · 섀도우 북 ================= */
function ciText(h){
  if (!h.ci) return '';
  return `<span class="thin" style="font-size:10.5px"> (${h.ci[0]}~${h.ci[1]})</span>`;
}
Q.register({
  id: 'track', title: '🎯 에이전트 적중률 · 섀도우 북', hint: '말대로 했으면?',
  books: ['kr', 'us', 'coin'],
  render(d, el, book){
    const parts = [];
    const sh = d.shadow || [];
    if (sh.length){
      const main = sh.find(s => s.book === 'all') || sh[0];
      const c = main.compare || {};
      if (!c.empty){
        const vs = c.shadow_vs_account;
        parts.push(`<p class="lead">${esc(c.start)}부터 <b>${esc(main.label)}</b>대로 다 했다면 <b class="${pc(c.shadow_pct)}">${pct(c.shadow_pct)}</b>,
          실제 계좌는 <b class="${pc(c.account_pct)}">${pct(c.account_pct)}</b>${vs != null ? ` — 에이전트가 <b class="${pc(vs)}">${pct(vs)}p</b> ${vs >= 0 ? '앞섰습니다' : '뒤졌습니다'}` : ''}.
          같은 기간 ${esc(c.bench_label)} ${pct(c.bench_pct)}.</p>`);
        parts.push(Q.line([
          {name: '섀도우 북', color: '#c471f5', pts: c.shadow},
          {name: '실계좌(입출금 제외)', color: '#4c8dff', pts: c.account},
          {name: c.bench_label, color: 'rgba(139,152,165,.8)', pts: c.bench, dash: '4 3'},
        ], {zero: 100, fmt: v => v.toFixed(0), tipFmt: v => (v - 100 >= 0 ? '+' : '−') + Math.abs(v - 100).toFixed(1) + '%'}));
      }
      const rows = sh.map(s => { const m = s.summary || {};
        return `<tr><td>${esc(s.label)}</td><td class="${pc(m.return_pct)}">${pct(m.return_pct)}</td>
          <td class="${pc(m.excess_pct)}">${pct(m.excess_pct)}</td><td>${pct(m.mdd_pct)}</td>
          <td>${m.trades ?? '—'}</td><td>${m.days ?? '—'}일</td></tr>`; }).join('');
      parts.push(`<h4>채널별 가상 포트폴리오 (T+1 종가 체결·수수료 반영)</h4><div class="qscroll"><table>
        <tr><th>채널</th><th>수익률</th><th>지수 대비</th><th>최대낙폭</th><th>거래</th><th>기간</th></tr>${rows}</table></div>`);
    } else if (book === 'us'){
      parts.push('<p class="lead">미국은 아직 섀도우 북이 없습니다 — 미국 AI 제안 기록이 쌓이면 채점만 먼저 보입니다.</p>');
    }
    const ch = d.channels || [];
    if (ch.length){
      const hz = ['1w', '1m', '3m'];
      const head = hz.map(h => `<th>${{'1w': '1주', '1m': '1달', '3m': '3달'}[h]} 적중</th>`).join('');
      const rows = ch.map(c => {
        const cells = hz.map(h => { const x = (c.horizons || []).find(r => r.horizon === h);
          if (!x || !x.n) return '<td class="thin">—</td>';
          return `<td class="${x.thin ? 'thin' : ''}">${x.hit_rate}%${ciText(x)}<div class="thin" style="font-size:10px">n=${x.n}${x.thin ? ' · 판단 보류' : ''}${x.expectancy != null ? ` · 평균 ${pct(x.expectancy)}` : ''}</div></td>`; }).join('');
        const rec = (c.records && c.records > c.calls) ? ` · 기록 ${c.records}회(반복 합침)` : '';
        return `<tr><td>${esc(c.label)}<div class="thin" style="font-size:10px">콜 ${c.calls}건${rec}</div></td>${cells}</tr>`;
      }).join('');
      parts.push(`<h4>채널별 적중률 — 괄호는 95% 신뢰구간</h4><div class="qscroll"><table><tr><th>채널</th>${head}</tr>${rows}</table></div>`);
    } else parts.push('<p class="why">이 시장에서 채점된 시그널이 아직 없습니다.</p>');
    const an = d.analysts || [];
    if (an.length){
      const rows = an.map(a => `<tr><td>${esc(a.author)}</td><td class="${a.thin ? 'thin' : ''}">${a.hit_rate ?? '—'}%${a.ci ? `<span class="thin" style="font-size:10.5px"> (${a.ci[0]}~${a.ci[1]})</span>` : ''}</td>
        <td>${a.n}</td><td>${a.avg_error_pct != null ? a.avg_error_pct + '%' : '—'}</td></tr>`).join('');
      parts.push(`<h4>증권사 적중률 (3개월 방향 · 표본 5건 이상)</h4><div class="qscroll"><table>
        <tr><th>증권사</th><th>적중률</th><th>표본</th><th>목표가 오차</th></tr>${rows}</table></div>`);
    }
    parts.push(`<p class="why">적중 = 방향을 건 콜이 기준(1주 ±2% · 1달 ±3% · 3달 ±5%)을 넘어 맞은 비율. 표본 ${d.min_n}건 미만은
      회색 '판단 보류' — 적은 표본의 높은 적중률은 운일 가능성이 큽니다. 섀도우 북은 시그널 다음 거래일 종가로 가상 체결하므로
      '그날 오른 걸 보고 산' 착시가 없습니다. 실계좌는 입출금을 뺀 운용 수익률(TWR)입니다.</p>`);
    el.innerHTML = parts.join('');
  },
});

/* ================= 패널 1: What-if 시뮬레이터 ================= */
const WI = {legs: [], fund: 'cash'};
function wiUnit(book){ return book === 'us' ? '달러' : '만원'; }
function wiToBase(v, book){ return book === 'us' ? v : v * 1e4; }
function wiLegText(l, book, names){
  const nm = names[l.code] || l.code;
  return l.side === 'sell' ? `매도 ${esc(nm)} 보유의 ${l.value}%`
    : `매수 ${esc(nm)} ${book === 'us' ? '$' + l.value.toLocaleString() : (l.value / 1e4).toLocaleString() + '만원'}`;
}
Q.register({
  id: 'whatif', title: '🧪 What-if — A를 팔고 B를 사면?', hint: '실행 전 검증', books: ['kr', 'us', 'coin'],
  render(c, el, book){
    WI.legs = []; WI.names = Object.fromEntries([...c.held, ...c.watch].map(x => [x.code, x.name]));
    const opts = [...c.held.map(h => `<option value="${esc(h.code)} · ${esc(h.name)}">보유 ${h.weight_pct}%</option>`),
                  ...c.watch.map(w => `<option value="${esc(w.code)} · ${esc(w.name)}">관심</option>`)].join('');
    el.innerHTML = `<p class="lead">매매를 입력하면 지금 포트폴리오를 그대로 복사해 가상으로 바꾼 뒤 <b>성적표·위험·스트레스·기대수익</b>을 다시 계산합니다.
      주문은 나가지 않습니다. 보유 현금 ${moneyShort(c.cash, book)}.</p>
      <div class="qform"><select id="wi-side"><option value="sell">매도</option><option value="buy">매수</option></select>
        <input id="wi-code" list="wi-list" placeholder="종목명 또는 코드" style="flex:1 1 180px" autocomplete="off">
        <datalist id="wi-list">${opts}</datalist>
        <input id="wi-val" type="number" min="0" step="any" placeholder="보유의 %">
        <button class="ghost" id="wi-add" type="button">+ 추가</button></div>
      <div class="qlegs" id="wi-legs"></div>
      <div class="qform"><span style="font-size:12px;color:var(--dim)">매수 자금</span>
        <select id="wi-fund"><option value="cash">보유 현금 먼저 (모자라면 새 입금)</option><option value="new">전액 새 입금</option></select>
        <button id="wi-run" type="button">계산</button></div>
      <div id="wi-out"></div>
      <p class="why">과거 1년 가격 움직임과 현재 컨센서스로 계산한 결과이며 예측이 아닙니다. 매도 비용 ${book === 'kr' ? '약 0.2%(수수료+거래세)' : book === 'coin' ? '0.2%(거래 수수료)' : '없음(수수료 무료), 이익엔 양도세 22%(연 250만원 공제 후)'} 가정.
        매도 대금은 현금으로 남아 같은 계산의 매수에 먼저 쓰입니다.</p>`;
    const side = $('wi-side'), val = $('wi-val');
    side.addEventListener('change', () => { val.placeholder = side.value === 'sell' ? '보유의 %' : `금액(${wiUnit(book)})`; });
    let timer = null;
    $('wi-code').addEventListener('input', e => {
      clearTimeout(timer);
      const q = e.target.value.split(' · ')[0].trim();
      if (q.length < 1 || e.target.value.includes(' · ')) return;
      timer = setTimeout(async () => {
        const r = await fetch(`/api/whatif_search?scope=${book}&q=${encodeURIComponent(q)}`).then(x => x.json()).catch(() => ({}));
        (r.items || []).forEach(x => { WI.names[x.code] = x.name; });
        $('wi-list').innerHTML = opts + (r.items || []).map(x => `<option value="${esc(x.code)} · ${esc(x.name)}">검색</option>`).join('');
      }, 250);
    });
    const draw = () => {
      $('wi-legs').innerHTML = WI.legs.map((l, i) => `<div class="leg"><span style="flex:1">${wiLegText(l, book, WI.names)}</span>
        <button type="button" data-i="${i}" aria-label="삭제">✕</button></div>`).join('');
    };
    $('wi-legs').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; WI.legs.splice(+b.dataset.i, 1); draw(); });
    $('wi-add').addEventListener('click', () => {
      const code = $('wi-code').value.split(' · ')[0].trim().toUpperCase(), v = +val.value;
      if (!code || !(v > 0)) { $('wi-out').innerHTML = '<div class="err">종목과 숫자를 입력하세요.</div>'; return; }
      if (side.value === 'sell' && v > 100) { $('wi-out').innerHTML = '<div class="err">매도는 보유의 100%까지입니다.</div>'; return; }
      if (WI.legs.length >= 6) { $('wi-out').innerHTML = '<div class="err">한 번에 6건까지입니다.</div>'; return; }
      WI.legs.push({code, side: side.value, value: side.value === 'sell' ? v : wiToBase(v, book)});
      $('wi-code').value = ''; val.value = ''; $('wi-out').innerHTML = ''; draw();
    });
    $('wi-run').addEventListener('click', async () => {
      if (!WI.legs.length) { $('wi-out').innerHTML = '<div class="err">매매를 하나 이상 추가하세요.</div>'; return; }
      const legs = WI.legs.map(l => `${l.code}:${l.side}:${l.value}`).join(',');
      $('wi-out').innerHTML = '<div class="loading">계산 중… (보유 전체를 다시 채점합니다)</div>';
      try {
        const d = await fetch(`/api/whatif?scope=${book}&fund=${$('wi-fund').value}&legs=${encodeURIComponent(legs)}`).then(r => r.json());
        if (mk() !== book) return;
        renderWhatif(d, book);
      } catch (e){ $('wi-out').innerHTML = `<div class="err">계산 실패 — ${esc(e.message)}</div>`; }
    });
  },
});
function renderWhatif(d, book){
  const out = $('wi-out');
  if (d.error){ out.innerHTML = `<div class="err">${esc(d.detail || d.error)}</div>`; return; }
  const b = d.before, a = d.after;
  const row = (label, x, y, fmt, better) => {
    const fx = v => v == null ? '—' : fmt(v);
    let cls = '';
    if (x != null && y != null && x !== y && better) cls = (better === 'up' ? y > x : y < x) ? 'up' : 'down';
    return `<tr><td>${label}</td><td>${fx(x)}</td><td class="${cls}"><b>${fx(y)}</b></td></tr>`;
  };
  const n1 = v => Number(v).toFixed(1), p1 = v => (v < 0 ? '−' : '') + Math.abs(Number(v)).toFixed(1) + '%';
  const axes = Object.keys(a.axes).map(k => row(`· ${esc(a.axes[k].label)}`, (b.axes[k] || {}).score, a.axes[k].score, n1, 'up')).join('');
  const trades = d.trades.map(t => `<div>${t.side === 'sell' ? '매도' : '매수'} ${esc(t.name)} ${moneyShort(t.amount, book)}${t.side === 'sell' && t.pnl_pct != null ? ` <span class="thin">(평가손익 ${pct(t.pnl_pct)})</span>` : ''}${t.new_money ? ` <span class="thin">· 새 입금 ${moneyShort(t.new_money, book)}</span>` : ''}</div>`).join('');
  const tax = d.tax ? (d.tax.tax_krw == null ? esc(d.tax.note) : `실현이익 $${d.tax.gain_usd.toLocaleString()} (≈${moneyShort(d.tax.gain_krw, 'kr')}) → 추정 양도세 <b>${moneyShort(d.tax.tax_krw, 'kr')}</b> <span class="thin">(공제 잔여 ${moneyShort(d.tax.deduction_left_krw, 'kr')} 먼저 사용)</span>`) : '';
  out.innerHTML = `<div class="qkpi" style="margin-top:10px">${d.summary.map(s => `<div class="c"><div class="s" style="font-size:12.5px;color:var(--fg)">${esc(s)}</div></div>`).join('')}</div>
    ${d.warnings.length ? `<div class="trustbar" style="margin:6px 0;color:#f5b74e;border-color:rgba(245,166,35,.4);background:rgba(245,166,35,.07)">${d.warnings.map(esc).join('<br>')}</div>` : ''}
    ${d.errors.length ? `<div class="err">${d.errors.map(esc).join('<br>')}</div>` : ''}
    <div class="qscroll"><table><tr><th>항목</th><th>지금</th><th>바꾸면</th></tr>
      ${row('<b>총점</b>', b.total, a.total, v => `${n1(v)}`, 'up')}
      ${row('등급', b.grade, a.grade, v => v, null)}${axes}
      ${row('연변동성', b.vol_pct, a.vol_pct, p1, 'down')}
      ${row('1일 VaR(95%)', b.var_pct, a.var_pct, v => '−' + Math.abs(v).toFixed(1) + '%', 'down')}
      ${row('최대낙폭(1년)', b.mdd_pct, a.mdd_pct, p1, 'up')}
      ${row('분산 효과', b.diversification_pct, a.diversification_pct, p1, 'up')}
      ${row('위험 1위', b.top_risk && `${b.top_risk.name} ${b.top_risk.risk_pct}%`, a.top_risk && `${a.top_risk.name} ${a.top_risk.risk_pct}%`, v => esc(v), null)}
      ${row('🔥 과위험 종목', (b.hot || []).length, (a.hot || []).length, v => v + '개', 'down')}
      ${row('최대 섹터', b.top_sector && `${b.top_sector.sector} ${b.top_sector.pct}%`, a.top_sector && `${a.top_sector.sector} ${a.top_sector.pct}%`, v => esc(v), null)}
      ${row('최악 위기 재생', b.worst_stress && b.worst_stress.pct, a.worst_stress && a.worst_stress.pct, v => pct(v), 'up')}
      ${row('12개월 기대수익(추정)', b.expected, a.expected, v => pct(v), 'up')}
      ${row('현금 비중', b.cash_pct, a.cash_pct, p1, null)}
    </table></div>
    <h4>가상 체결</h4><div style="font-size:12px">${trades}</div>
    <p class="why">매매 비용 ${moneyShort(d.costs, book)} · 새로 넣을 돈 ${moneyShort(d.new_money, book)} · 현금 ${moneyShort(d.cash_before, book)} → ${moneyShort(d.cash_after, book)}${tax ? '<br>' + tax : ''}</p>`;
}

/* ================= 패널 2: 위험 기여도 ================= */
Q.register({
  id: 'risk', title: '🔥 위험 기여도', hint: '비중 vs 위험', books: ['kr', 'us', 'coin'],
  render(d, el){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const hot = d.rows.filter(r => r.hot);
    const top = d.rows[0];
    const lead = hot.length
      ? `<b>${hot.map(r => esc(r.name)).join(', ')}</b>이(가) 비중보다 위험을 훨씬 많이 차지합니다 🔥 —
         ${esc(hot[0].name)}는 비중 ${hot[0].weight_pct}%로 위험의 <b>${hot[0].risk_pct}%</b>.`
      : `위험 1위는 <b>${esc(top.name)}</b>(비중 ${top.weight_pct}% → 위험 ${top.risk_pct}%). 비중 대비 과도한 종목은 없습니다.`;
    const bar = r => `<div class="r"><span class="n" title="${esc(r.name)}">${r.hot ? '🔥 ' : ''}${esc(r.name)}</span>
      <span class="b"><i class="w" style="width:${Math.min(100, r.weight_pct * 2)}%"></i><i class="k${r.hot ? ' hot' : ''}" style="width:${Math.min(100, Math.max(0, r.risk_pct) * 2)}%"></i></span>
      <span class="v">${r.risk_pct}%</span></div>`;
    const rows = d.rows.map(r => `<tr><td>${r.hot ? '🔥 ' : ''}${esc(r.name)}</td><td>${r.weight_pct}%</td><td><b>${r.risk_pct}%</b></td>
      <td>${r.ratio ?? '—'}×</td><td>${r.vol_pct}%</td><td>−${r.cut1_vol_pp}%p</td></tr>`).join('');
    const sec = d.sectors.map(s => `<tr><td>${esc(s.sector)}</td><td>${s.weight_pct}%</td><td><b>${s.risk_pct}%</b></td></tr>`).join('');
    el.innerHTML = `<p class="lead">${lead}</p>
      <div class="qkpi"><div class="c"><div class="k">포트 연변동성</div><div class="v">${d.port_vol_pct}%</div>
        <div class="s">종목 변동성 단순합 ${d.naive_vol_pct}%</div></div>
        <div class="c"><div class="k">분산 효과</div><div class="v">${d.diversification_pct ?? '—'}%</div>
        <div class="s">서로 달리 움직여 줄어든 위험</div></div>
        <div class="c"><div class="k">계산 범위</div><div class="v">${d.coverage_pct}%</div>
        <div class="s">${d.obs}거래일 · ${esc(d.start)}~</div></div></div>
      <div class="qbars">${d.rows.slice(0, 12).map(bar).join('')}</div>
      <p class="why" style="margin-top:4px">회색 = 비중, 파랑 = 위험 기여(빨강 = 비중의 1.5배 이상)</p>
      <h4>섹터 단위</h4><div class="qscroll"><table><tr><th>섹터</th><th>비중</th><th>위험</th></tr>${sec}</table></div>
      <h4>종목 전체</h4><div class="qscroll"><table><tr><th>종목</th><th>비중</th><th>위험 기여</th><th>배수</th><th>자체 변동성</th><th>1%p 줄이면</th></tr>${rows}</table></div>
      ${d.dropped.length ? `<p class="why">시세 60일 미만이라 제외: ${d.dropped.map(x => esc(x.name)).join(', ')}</p>` : ''}
      ${(d.proxy_filled || []).length ? `<p class="why">상장 전 기간은 "지수 × 민감도"로 추정해 1년 창을 맞춤: ${d.proxy_filled.map(x => esc(x.name)).join(', ')}</p>` : ''}
      <p class="why">위험 기여 = 이 종목이 포트 전체 흔들림에서 차지하는 몫(합 100%). 같이 움직이는 종목끼리는 위험이 겹쳐
        비중보다 커집니다. '1%p 줄이면' = 그만큼 현금으로 돌렸을 때 포트 연변동성이 줄어드는 폭. 최근 1년 일간 수익률 기준.</p>`;
  },
});

/* ================= 패널 3: 스트레스 테스트 ================= */
Q.register({
  id: 'stress', title: '🌪️ 스트레스 테스트', hint: '위기가 오면?', books: ['kr', 'us', 'coin'],
  render(d, el, book){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const sc = d.scenarios.map(s => s.port_pct == null
      ? `<tr><td>${esc(s.name)}</td><td colspan="4" class="thin">${esc(s.note || '시세 없음')}</td></tr>`
      : `<tr><td>${esc(s.name)}<div class="thin" style="font-size:10px">${esc(s.start)} ~ ${esc(s.end)}</div></td>
         <td class="${pc(s.port_pct)}"><b>${pct(s.port_pct)}</b></td>
         <td class="${pc(s.port_pct)}">${moneyShort(d.invested * s.port_pct / 100, book)}</td>
         <td>${pct(s.bench_pct)}${s.bench_src === 'history' ? '<span class="tag">역사값</span>' : ''}</td>
         <td class="thin">${s.proxy_pct ? s.proxy_pct + '% 대용' : '실측'}</td></tr>
         <tr><td colspan="5" class="thin" style="font-size:10.5px;border-top:0;padding-top:0">가장 크게: ${s.worst.map(w => `${esc(w.name)} ${pct(w.pct)}`).join(' · ')}</td></tr>`).join('');
    const sl = (id, label, min, max, val) => `<div class="qslide"><span>${label}</span>
      <input type="range" id="${id}" min="${min}" max="${max}" step="1" value="${val}"><b id="${id}v">${val}%</b></div>`;
    const ctl = book === 'coin'
      ? sl('qs-m', '대장 코인', -80, 30, -50) + sl('qs-x', '알트 추가 충격', -50, 20, -10)
      : sl('qs-m', `${esc(d.bench)}`, -50, 20, book === 'us' ? -25 : -20)
        + sl('qs-x', '반도체 추가 충격', -40, 20, -10)
        + (book === 'us' ? sl('qs-f', '원/달러 환율', -20, 20, 0) : '');
    el.innerHTML = `<p class="lead">포트 시장 민감도(β) <b>${d.port_beta}</b> — 지수가 10% 빠지면 평균적으로 약 ${Math.abs(d.port_beta * 10).toFixed(0)}% 빠지는 구성입니다.
      ${book !== 'coin' ? ` 반도체 비중 ${d.semis_pct}%.` : ''}</p>
      <h4>과거 위기 재생 — 지금 비중으로 그때를 겪었다면</h4>
      <div class="qscroll"><table><tr><th>위기</th><th>포트</th><th>금액</th><th>지수</th><th>근거</th></tr>${sc}</table></div>
      <h4>가상 충격 — 슬라이더로 조절</h4>${ctl}<div id="qs-out"></div>
      <p class="why">재생: 그 시절 시세가 있는 종목은 실제 수익률, 없는 종목(신규 상장·2016년 이전)은 "지수 × 그 종목의 시장 민감도(최근 1년 β, 상한 1.5 · 레버리지 상품 3)"로
        대신합니다('대용' 비율). '역사값' 지수는 웨어하우스 이전 구간이라 공개된 고점→저점 낙폭을 넣었습니다.
        가상 충격 = 종목별 β × 지수 변화 ${book === 'coin' ? '(대장 코인은 β 1 고정)' : ''} + 해당 섹터 추가 충격. 코어 종목 매도 권고가 아닙니다.</p>`;
    const run = () => {
      const m = +$('qs-m').value, x = +$('qs-x').value, f = $('qs-f') ? +$('qs-f').value : 0;
      ['qs-m', 'qs-x', 'qs-f'].forEach(i => { if ($(i)) $(i + 'v').textContent = $(i).value + '%'; });
      const res = d.items.map(it => {
        const b = book === 'coin' && it.code === 'BTC' ? 1 : (it.beta ?? 1);
        let r = b * m;
        if (book === 'coin' ? it.sector === '알트' : String(it.sector).includes('반도체')) r += x;
        r = Math.max(-100, r);
        if (f) r = ((1 + r / 100) * (1 + f / 100) - 1) * 100;          // 원화 환산
        return {...it, r};
      });
      const port = res.reduce((s, it) => s + it.w * it.r, 0);
      const worst = [...res].sort((a, b) => a.w * a.r - b.w * b.r).slice(0, 3);
      $('qs-out').innerHTML = `<div class="qkpi"><div class="c"><div class="k">포트 예상 변화${f ? ' (원화 환산)' : ''}</div>
        <div class="v ${pc(port)}">${pct(port)}</div><div class="s">${f ? '달러 자산을 원화로 본 변화' : moneyShort(d.invested * port / 100, book)}</div></div>
        <div class="c"><div class="k">손실 기여 상위</div><div class="s">${worst.map(w => `${esc(w.name)} ${pct(w.r)}`).join('<br>')}</div></div></div>`;
    };
    ['qs-m', 'qs-x', 'qs-f'].forEach(i => { if ($(i)) $(i).addEventListener('input', run); });
    run();
  },
});

/* ================= 패널 6·7: 롤링 비율 · 언더워터 (같은 /perf 응답) ================= */
const perfFetch = m => fetch(`/api/quant?panel=perf&scope=${m}`).then(r => r.json());
const RATIO_LBL = {sharpe: '샤프', sortino: '소르티노', calmar: '칼마'};
Q.register({
  id: 'ratios', title: '📐 샤프 · 소르티노 · 칼마', hint: '위험 대비 성과', books: ['kr', 'us', 'coin'], fetch: perfFetch,
  render(d, el){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const ws = Object.entries(d.windows);
    const avail = ws.filter(([, w]) => w.available).map(([k]) => k);
    const cell = (v, b) => `<td><b>${v ?? '—'}</b><div class="thin" style="font-size:10px">${esc(d.bench)} ${b ?? '—'}</div></td>`;
    const rows = ws.map(([k, w]) => !w.available
      ? `<tr><td>${k}일</td><td colspan="4" class="thin">기록 ${w.have}일 — ${w.need}일부터 표시</td></tr>`
      : `<tr><td>${k}일</td>${cell(w.now.sharpe, w.bench_now.sharpe)}${cell(w.now.sortino, w.bench_now.sortino)}${cell(w.now.calmar, w.bench_now.calmar)}
         <td>${pct(w.now.ann_ret)}<div class="thin" style="font-size:10px">변동 ${w.now.ann_vol}%</div></td></tr>`).join('');
    const f = d.full, bf = d.bench_full;
    el.innerHTML = `<p class="lead">전체 기간(${esc(d.start)}~, ${d.days}거래일) 샤프 <b>${f.sharpe ?? '—'}</b> vs ${esc(d.bench)} ${bf.sharpe ?? '—'} —
      ${f.sharpe != null && bf.sharpe != null ? (f.sharpe >= bf.sharpe ? '같은 위험당 지수보다 더 벌었습니다.' : '같은 위험당 지수보다 덜 벌었습니다.') : ''}</p>
      <div class="qscroll"><table><tr><th>창</th><th>샤프</th><th>소르티노</th><th>칼마</th><th>연환산</th></tr>${rows}</table></div>
      ${avail.length ? `<div class="tabs" id="qr-tabs" style="margin-top:12px">${avail.map((k, i) => `<button data-w="${k}" class="${i === avail.length - 1 ? 'on' : ''}">${k}일</button>`).join('')}
        <span style="width:8px"></span>${Object.keys(RATIO_LBL).map((k, i) => `<button data-m="${k}" class="${i ? '' : 'on'}">${RATIO_LBL[k]}</button>`).join('')}</div>
        <div id="qr-chart"></div>` : ''}
      <p class="why">샤프 = 무위험(연 ${num(d.rf_pct)}%)을 넘는 수익 ÷ 변동성. 소르티노 = 하락 변동만 위험으로 본 샤프. 칼마 = 연수익 ÷ 최대낙폭.
        1 이상이면 양호, 0 미만이면 예금보다 못한 구간. 입출금을 뺀 운용 수익률로 계산하며, 재구성(추정) 구간이 포함될 수 있습니다.</p>`;
    if (!avail.length) return;
    let W = avail[avail.length - 1], M = 'sharpe';
    const draw = () => {
      const w = d.windows[W];
      $('qr-chart').innerHTML = Q.line([
        {name: '내 계좌', color: '#4c8dff', pts: w.mine.map(p => [p.d, p[M]])},
        {name: d.bench, color: 'rgba(139,152,165,.8)', pts: w.bench.map(p => [p.d, p[M]]), dash: '4 3'},
      ], {zero: 0, fmt: v => v.toFixed(1)});
    };
    $('qr-tabs').addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.w) W = b.dataset.w; if (b.dataset.m) M = b.dataset.m;
      [...$('qr-tabs').children].forEach(x => { if (x.dataset.w) x.classList.toggle('on', x.dataset.w === W);
        if (x.dataset.m) x.classList.toggle('on', x.dataset.m === M); });
      draw();
    });
    draw();
  },
});
Q.register({
  id: 'underwater', title: '🌊 고점 대비 하락 · 회복', hint: '언더워터', books: ['kr', 'us', 'coin'], fetch: perfFetch,
  render(d, el){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const on = d.episodes.find(e => e.ongoing);
    const lead = d.current_dd > -0.5 ? '지금 <b>고점 근처</b>입니다(입출금 제외 기준).'
      : `지금 고점 대비 <b class="down">${pct(d.current_dd)}</b>${on ? ` — ${esc(on.peak)} 고점 이후 ${on.total_days}일째 회복 중` : ''}.`;
    const rows = d.episodes.map(e => `<tr><td>${esc(e.peak)}</td><td class="down"><b>${pct(e.depth_pct)}</b></td>
      <td>${esc(e.trough)}<div class="thin" style="font-size:10px">${e.to_trough_days}일 하락</div></td>
      <td>${e.ongoing ? `<span class="tag warn">진행 중 ${e.total_days}일</span>` : `${e.recover_days}일<div class="thin" style="font-size:10px">${esc(e.recovered)}</div>`}</td></tr>`).join('');
    const bep = (d.bench_episodes || []).map(e => `${esc(e.peak.slice(0, 7))} ${pct(e.depth_pct)}${e.ongoing ? '(진행 중)' : ` · ${e.recover_days}일 회복`}`).join(' · ');
    el.innerHTML = `<p class="lead">${lead}</p>
      ${Q.line([
        {name: '내 계좌', color: '#ff5b45', pts: d.underwater, fill: 'rgba(255,91,69,.18)'},
        {name: d.bench, color: 'rgba(139,152,165,.8)', pts: d.bench_underwater, dash: '4 3'},
      ], {zero: 0, fmt: v => v.toFixed(0) + '%', tipFmt: v => v.toFixed(1) + '%'})}
      <h4>역대 하락 TOP ${d.episodes.length} (−3% 이상)</h4>
      ${rows ? `<div class="qscroll"><table><tr><th>고점</th><th>깊이</th><th>저점</th><th>회복</th></tr>${rows}</table></div>` : '<p class="why">−3% 넘는 하락이 없었습니다.</p>'}
      ${bep ? `<p class="why">${esc(d.bench)} 같은 기간 큰 하락: ${bep}</p>` : ''}
      <p class="why">입출금을 뺀 운용 수익률(TWR) 기준 — 하락 중에 돈을 넣어도 회복으로 보이지 않습니다. 회복 = 이전 고점을 다시 넘은 날.</p>`;
  },
});

/* 히트맵 칸 색 — 대시보드 관례대로 상승=초록·하락=빨강, 크기는 진하기(scale 에서 포화) */
function heatColor(v, scale){
  if (v == null) return 'rgba(255,255,255,.03)';
  const a = Math.min(1, Math.abs(v) / scale) * 0.75 + 0.08;
  return v >= 0 ? `rgba(0,200,5,${a.toFixed(2)})` : `rgba(255,91,69,${a.toFixed(2)})`;
}

/* ================= 패널 4: 이벤트 캘린더 ================= */
const KIND_ICON = {earnings: '📊', ex_div: '💰', div_pay: '💵', macro: '🏛️', expiry: '⏳', holiday: '🚫'};
Q.register({
  id: 'calendar', title: '🗓️ 이벤트 캘린더', hint: '45일', books: ['kr', 'us', 'coin'],
  render(d, el, book){
    const byDay = {};
    d.events.forEach(e => (byDay[e.date] = byDay[e.date] || []).push(e));
    const wd = s => '일월화수목금토'[new Date(s + 'T00:00:00').getDay()];
    const days = Object.keys(byDay).sort().map(k => {
      const evs = byDay[k].map(e => `<div class="e${e.held ? ' hold' : ''}${e.confidence === '추정' ? ' est' : ''}">
        ${KIND_ICON[e.kind] || '•'} ${esc(e.title)}${e.big ? ' <span class="tag warn">주요</span>' : ''}
        <span class="x">${e.held ? `내 비중 ${e.exposure_pct}%` : e.exposure_pct === 100 ? '계좌 전체' : ''}${e.source ? ' · ' + esc(e.source) : ''}</span></div>`).join('');
      const soon = k <= new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10);
      return `<div class="d"><div class="dt">${esc(k.slice(5))} (${wd(k)})${soon ? '<br><span class="tag">7일 내</span>' : ''}</div><div>${evs}</div></div>`;
    }).join('');
    const earn = d.events.filter(e => e.kind === 'earnings');
    const lead = book === 'coin' ? '코인은 실적·배당이 없어 거시 일정과 옵션 만기만 봅니다.'
      : earn.length ? `45일 안에 보유 종목 실적 발표 <b>${earn.length}건</b> — 합계 비중 ${earn.reduce((s, e) => s + (e.exposure_pct || 0), 0).toFixed(1)}%.
         ${d.week_earnings_exposure_pct ? ` 이번 주에만 <b>${d.week_earnings_exposure_pct}%</b>가 실적을 냅니다.` : ''}`
      : '45일 안에 알려진 보유 종목 실적 발표가 없습니다.';
    const upd = d.stock_updated ? new Date(d.stock_updated * 1000).toISOString().slice(0, 10) : null;
    el.innerHTML = `<p class="lead">${lead}</p>
      ${!d.macro_ok ? `<div class="trustbar" style="margin:0 0 8px">거시 일정은 ${esc(d.macro_registered_through || '—')}까지만 등록돼 있습니다 — config/macro_calendar.yml 갱신 필요.</div>` : ''}
      <div class="qcal">${days || '<p class="why">일정 없음</p>'}</div>
      <p class="why">📊 실적 · 💰 배당락 · 💵 배당 지급 · 🏛️ 거시 · ⏳ 만기 · 🚫 휴장. 종목 일정은 야간에 yfinance 에서 받습니다${upd ? `(마지막 ${upd})` : '(아직 수집 전 — 다음 야간 동기화 후 표시)'}.
        한국 실적일은 회사 공시 전까지 <span style="color:#f5a623">추정</span>입니다. 거시 일정은 연준·한국은행·미 노동통계국 공식 발표, 만기는 거래소 규칙으로 계산.</p>`;
  },
});

/* ================= 패널 10: 목표가 수정 히트맵 ================= */
Q.register({
  id: 'revisions', title: '🎯 목표가 수정 흐름', hint: '올리나 내리나', books: ['kr', 'us'],
  render(d, el){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const head = d.weeks.map(w => `<th>${esc(w.slice(5).replace('-', '/'))}</th>`).join('');
    const rows = d.rows.map(r => `<tr><td class="nm" title="${esc(r.name)}">${esc(r.name)}</td>
      ${r.weeks.map(v => `<td style="background:${heatColor(v, 3)}" title="${v == null ? '자료 없음' : pct(v, 2)}">${v == null ? '' : (Math.abs(v) >= 0.05 ? (v > 0 ? '+' : '−') + Math.abs(v).toFixed(1) : '0')}</td>`).join('')}
      <td style="background:none!important;text-align:right!important;padding-left:8px!important;color:var(--fg);white-space:nowrap">${r.chg4w == null ? '—' : pct(r.chg4w)}</td></tr>`).join('');
    const tbl = d.rows.map(r => `<tr><td>${esc(r.name)}</td><td>${r.weight_pct}%</td><td class="${pc(r.chg4w)}">${pct(r.chg4w)}</td>
      <td class="${pc(r.chg_all)}">${pct(r.chg_all)}<div class="thin" style="font-size:10px">${esc(r.since || '')}~</div></td>
      <td>${r.reports30}${r.reports30_with_target ? `<span class="thin"> (목표가 ${r.reports30_with_target})</span>` : ''}</td>
      <td><span class="tag ${/상향/.test(r.signal) ? 'ok' : /하향/.test(r.signal) ? 'bad' : ''}">${esc(r.signal)}</span></td></tr>`).join('');
    el.innerHTML = `<p class="lead">보유 비중 가중 최근 4주 컨센서스 목표가 <b class="${pc(d.score_4w_pct)}">${pct(d.score_4w_pct, 2)}</b>
      ${d.up.length ? ` · 상향: ${d.up.slice(0, 4).map(esc).join(', ')}` : ''}${d.down.length ? ` · 하향: <span class="down">${d.down.slice(0, 4).map(esc).join(', ')}</span>` : ''}</p>
      <div class="qscroll"><table class="qheat"><tr><th></th>${head}<th style="text-align:right!important">4주</th></tr>${rows}</table></div>
      <h4>종목별</h4><div class="qscroll"><table><tr><th>종목</th><th>비중</th><th>4주</th><th>기록 이후</th><th>30일 리포트</th><th>신호</th></tr>${tbl}</table></div>
      <p class="why">칸 = 그 주 시장 컨센서스 평균 목표가의 전주 대비 변화(%). 빈칸은 자료가 없는 주(0이 아님) — 컨센서스 기록은 2026-08 초부터 쌓였습니다.
        목표가를 올리는 흐름(수정 모멘텀)은 주가에 앞서는 경향이 알려진 신호지만 단독 매매 근거는 아닙니다. 커버리지 ${d.covered_pct}%(ETF 제외).</p>`;
  },
});

/* ================= 패널 11: 수급 흐름 ================= */
Q.register({
  id: 'flows', title: '🌊 외국인·기관 수급', hint: '한국', books: ['kr'],
  render(d, el){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const eok = v => v == null ? '—' : (v < 0 ? '−' : '+') + Math.abs(v / 1e8).toLocaleString('ko-KR', {maximumFractionDigits: 0}) + '억';
    const dd = v => v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(2) + '일';
    const stk = s => s ? `${s > 0 ? '매수' : '매도'} ${Math.abs(s)}일째` : '—';
    const mk = d.market.map(m => `<div class="c"><div class="k">${esc(m.label)} 전체 (20일)</div>
      <div class="v ${pc(m.f20)}" style="font-size:15px">외국인 ${eokStr(m.f20)}</div>
      <div class="s">기관 ${eokStr(m.i20)} · 외국인 ${stk(m.f_streak)} · ${esc(m.last)}</div></div>`).join('');
    const heatDates = (d.rows[0] || {}).heat ? d.rows[0].heat.map(h => h.d) : [];
    const maxAbs = Math.max(1, ...d.rows.flatMap(r => r.heat.map(h => Math.abs(h.amt))));
    const heat = d.rows.map(r => {
      const m = Object.fromEntries(r.heat.map(h => [h.d, h.amt]));
      return `<tr><td class="nm" title="${esc(r.name)}">${esc(r.name)}</td>${heatDates.map(x => { const v = m[x];
        return `<td style="background:${heatColor(v == null ? null : v / maxAbs * 3, 1)}" title="${esc(x)} ${eok(v)}"></td>`; }).join('')}</tr>`;
    }).join('');
    const rows = d.rows.map(r => `<tr><td>${esc(r.name)}<div class="thin" style="font-size:10px">비중 ${r.weight_pct}%</div></td>
      <td class="${pc(r.f20_amt)}">${eok(r.f20_amt)}<div class="thin" style="font-size:10px">${stk(r.f_streak)}</div></td>
      <td class="${pc(r.i20_amt)}">${eok(r.i20_amt)}<div class="thin" style="font-size:10px">${stk(r.i_streak)}</div></td>
      <td class="${pc(r.f60_amt)}">${eok(r.f60_amt)}</td><td class="${pc(r.i60_amt)}">${eok(r.i60_amt)}</td>
      <td class="${pc(r.both20_days)}"><b>${dd(r.both20_days)}</b></td>
      <td><span class="tag ${/매집/.test(r.verdict) ? 'ok' : /이탈/.test(r.verdict) ? 'bad' : ''}">${esc(r.verdict)}</span></td></tr>`).join('');
    el.innerHTML = `<p class="lead">보유 개별주(비중 ${d.covered_pct}%)에 최근 20일 외국인+기관이 <b class="${pc(d.score_days)}">평소 하루 거래량의 ${dd(d.score_days)}치</b>를 ${d.score_days >= 0 ? '순매수' : '순매도'}했습니다(비중 가중).</p>
      ${mk ? `<div class="qkpi">${mk}</div>` : ''}
      <h4>최근 20거래일 외국인+기관 순매수 (초록 매수 · 빨강 매도)</h4>
      <div class="qscroll"><table class="qheat">${heat}</table></div>
      <h4>종목별 누적</h4><div class="qscroll"><table><tr><th>종목</th><th>외국인 20일</th><th>기관 20일</th><th>외국인 60일</th><th>기관 60일</th><th>강도(20일)</th><th>판정</th></tr>${rows}</table></div>
      <p class="why">금액 = 순매수 주식 수 × 그날 종가. 강도 = 20일 외국인+기관 누적 순매수 ÷ 20일 평균 거래량 → "평소 하루 거래량의 며칠치"
        (±0.3일 이상 매집/이탈, ±1일 이상 강함). ETF 는 유동성공급자 매매가 섞여 제외. 원천: 네이버 증권(야간 갱신), 마지막 ${esc(d.last || '—')}.</p>`;
  },
});

/* ================= 패널 9: 팩터 노출 ================= */
Q.register({
  id: 'factor', title: '🧬 팩터 노출', hint: '실제로 무엇에 베팅 중?', books: ['kr', 'us'],
  render(d, el, book){
    if (d.empty){ el.innerHTML = `<div class="loading">${esc(d.note)}</div>`; return; }
    const L = d.labels || {};
    const keys = Object.keys(d.betas || {});
    const mkt = keys[0];
    const bar = k => { const b = d.betas[k], isM = k === mkt;
      // 시장은 1 이 기준(지수와 같이 움직임), 스타일은 0 이 기준
      const dev = isM ? b - 1 : b, w = Math.min(50, Math.abs(dev) * (isM ? 50 : 80));
      return `<div class="r"><span class="n">${esc(L[k] || k)}</span>
        <span class="b" style="background:linear-gradient(90deg,transparent calc(50% - .5px),rgba(255,255,255,.25) calc(50% - .5px),rgba(255,255,255,.25) calc(50% + .5px),transparent calc(50% + .5px))">
        <i style="top:4px;height:6px;${dev >= 0 ? `left:50%;width:${w}%` : `left:${50 - w}%;width:${w}%`};background:${dev >= 0 ? 'var(--g2)' : 'var(--g3)'}"></i></span>
        <span class="v">${b.toFixed(2)}</span></div>`; };
    const contrib = Object.entries(d.contrib || {}).filter(([k, v]) => v.length && k !== mkt).map(([k, v]) =>
      `<tr><td>${esc(L[k] || k)}</td><td style="text-align:left">${v.slice(0, 3).map(c => `${esc(c.name)} <span class="${c.part >= 0 ? 'up' : 'down'}">${c.part >= 0 ? '+' : '−'}${Math.abs(c.part).toFixed(2)}</span>`).join(' · ')}</td></tr>`).join('');
    const drift = (d.drift || []).length ? `<h4>노출 추이 (지금 비중을 각 시점 직전 120거래일에 적용)</h4><div class="qscroll"><table>
      <tr><th>시점</th>${keys.map(k => `<th>${esc((L[k] || k).split('(')[0])}</th>`).join('')}</tr>
      ${d.drift.map(r => `<tr><td>${esc(r.end.slice(0, 7))}</td>${keys.map(k => `<td>${r[k] == null ? '—' : r[k].toFixed(2)}</td>`).join('')}</tr>`).join('')}</table></div>` : '';
    el.innerHTML = `<p class="lead"><b>${esc(d.note || '')}</b></p>
      <div class="qkpi"><div class="c"><div class="k">설명력(R²)</div><div class="v">${d.r2 == null ? '—' : Math.round(d.r2 * 100) + '%'}</div><div class="s">팩터로 설명되는 일간 움직임 비율</div></div>
        <div class="c"><div class="k">팩터로 설명 안 되는 초과(연)</div><div class="v ${pc(d.alpha_ann_pct)}">${pct(d.alpha_ann_pct)}</div><div class="s">현재 구성의 과거 1년 기준 · 운 포함</div></div>
        <div class="c"><div class="k">방법</div><div class="v" style="font-size:14px">${esc(d.method)}</div><div class="s">${d.n || '—'}거래일</div></div></div>
      <div class="qbars">${keys.map(bar).join('')}</div>
      <p class="why" style="margin-top:2px">${esc(L[mkt] || '시장')}은 1이 지수와 같은 움직임, 나머지는 0이 중립 — 오른쪽(파랑)은 그 쪽으로 기울어짐, 왼쪽(주황)은 반대.</p>
      ${contrib ? `<h4>어느 종목이 그 노출을 만드나 (비중 × 종목 민감도)</h4><div class="qscroll"><table>${contrib}</table></div>` : ''}
      ${drift}
      <p class="why">${book === 'kr'
        ? `한국은 공개 팩터 수익률이 없어 <b>ETF 수익률 차이로 근사</b>합니다: 코스닥 = ${esc(d.etfs['316140'])} − ${esc(d.etfs['069500'])}, 반도체 = ${esc(d.etfs['091160'])} − KODEX 200, 고배당 = ${esc(d.etfs['161510'])} − KODEX 200, 미국 기술주 = ${esc(d.etfs['133690'])} − KODEX 200.
           KODEX 200 자체에 반도체 비중이 커서 반도체 수치는 '코스피보다 더' 쏠린 정도입니다. 순수 가치·모멘텀·저변동 ETF 는 한국에 유동성 있는 상품이 없어 제외.`
        : 'Ken French 공개 일별 팩터(시장·소형·가치·수익성·투자·모멘텀)에 현재 구성의 1년 수익률을 회귀했습니다.'}
        현재 비중을 과거에 그대로 적용한 결과라 실제 과거 성과와 다를 수 있습니다.</p>`;
  },
});

/* ---------------- 부팅 — index.html 본 스크립트 뒤에 실리므로 DOM·전역이 준비돼 있다 ---------------- */
window.Quant = Q;
Q.boot = () => {
  $('trustbadge').addEventListener('click', () => $('trustpop').classList.toggle('hide'));
  renderSection(); refreshTrust();
};
// 패널 정의(quant_*.js 가 뒤에 더 실릴 수 있다)가 다 등록된 뒤 부팅 — 마이크로태스크로 미룬다
setTimeout(Q.boot, 0);
})();
