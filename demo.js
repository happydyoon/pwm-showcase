/* 체험판 — /api/… 요청을 ./data/<slug>.json 으로 바꾸고, 맨 위에 체험판 띠를 붙인다.
 * 세 페이지(index·tenbagger·forecast)가 <head> 맨 앞에서 불러온다. 서버 없음 · 가상 데이터.
 * slug 규칙은 build/make_demo.py 의 slug() 와 같다(tests/test_showcase.py 가 대조).
 */
(function () {
  'use strict';
  window.DEMO = true;
  var SLUG_PATTERN = '[^A-Za-z0-9]+';
  var BANNER_TEXT = '체험판 · 가상 데이터 — 실제 계좌가 아닙니다 · 총액 ₩1,000만 고정';

  function slug(url) {
    var i = url.indexOf('/api/');
    var rest = i >= 0 ? url.slice(i + 5) : url;
    return rest.replace(new RegExp(SLUG_PATTERN, 'g'), '_').replace(/^_+|_+$/g, '');
  }
  // 입력해야 부르는 주소(What-if 계산·종목 검색)는 시장별 표본 응답 하나로
  function fallback(s) {
    var m = /^(whatif_search|whatif)_scope_([a-z]+)_/.exec(s);
    return m ? m[1] + '_scope_' + m[2] : null;
  }
  window.__demoSlug = slug;

  var realFetch = window.fetch.bind(window);
  function empty() {
    return new Response('{}', {status: 200, headers: {'Content-Type': 'application/json'}});
  }
  window.fetch = function (input, init) {
    var u = typeof input === 'string' ? input : (input && input.url) || '';
    var path = u.replace(/^https?:\/\/[^/]+/, '');
    if (path.indexOf('/api/') !== 0) return realFetch(input, init);
    var s = slug(path);
    var alt = fallback(s);
    return realFetch('./data/' + s + '.json').then(function (r) {
      if (r.ok) return r;
      if (!alt) { console.warn('DEMO missing', s); return empty(); }
      return realFetch('./data/' + alt + '.json').then(function (r2) {
        if (r2.ok) return r2;
        console.warn('DEMO missing', s);
        return empty();
      });
    }, function () { console.warn('DEMO missing', s); return empty(); });
  };

  function banner() {
    if (document.getElementById('demo-banner')) return;
    var b = document.createElement('div');
    b.id = 'demo-banner';
    b.setAttribute('role', 'note');
    b.textContent = BANNER_TEXT;
    b.style.cssText = 'position:sticky;top:0;z-index:2147483000;margin:0 0 8px;padding:6px 16px;'
      + 'background:#14110a;color:#ffd34d;border-bottom:1px solid #4a3d12;'
      + 'font:600 min(12.5px,2.7vw)/1.4 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;'
      + 'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:center;letter-spacing:0';
    document.body.insertBefore(b, document.body.firstChild);
  }
  if (document.body) banner();
  else document.addEventListener('DOMContentLoaded', banner);
})();
