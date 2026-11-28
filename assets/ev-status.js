/* 전기차 충전소 상태 갈아끼우기 (상태 JSON 분리, 2026-11-28).
   지역 목록 페이지와 시·도 페이지에서만 쓰인다.
   정적 HTML에는 빌드 시점 상태가 들어 있고, 이 스크립트는 상태 응답
   Worker(parking-ev-status, D1 기반)의 최신 본문을 읽어 배지·요금 줄·
   집계를 화면에서만 갈아끼운다. 읽기에 실패하면 빌드 시점 값이 남는다.
   상태는 '상태 확인' 시각 기준이며 '실시간'으로 표기하지 않는다.
   판정 규칙은 build_ev.py 의 avail_text·avail_unknown·ev_cf_stale 과 같다. */
(function () {
  function isStaleCf(cf) {
    if (!cf) return false;
    var t = Date.parse(String(cf).slice(0, 16).replace(' ', 'T') + ':00+09:00');
    return !isNaN(t) && Date.now() - t > 24 * 3600 * 1000;
  }

  function fmt(n) { return Number(n).toLocaleString('en-US'); }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* 충전기 한 대는 가능/충전 중/점검·운영중지/미확인 중 하나라
     전체 대수는 네 수의 합과 같다(build_ev.py 의 셈 규칙과 동일). */
  function badgeHtml(a, c, dn, un, cf) {
    if (isStaleCf(cf)) return '<span class="badge unknown">상태 확인 중</span>';
    if (a) return '<span class="badge ev">지금 충전 가능 ' + a + '대</span>';
    if (a + c + dn + un > 0 && un === a + c + dn + un) {
      return '<span class="badge unknown">상태 모름</span>';
    }
    return '';
  }

  function feeHtml(a, c, dn, un, cf) {
    var total = a + c + dn + un;
    var head;
    if (isStaleCf(cf)) head = '상태 확인 중';
    else if (total > 0 && a === 0 && un === total) head = '상태 모름';
    else head = '지금 충전 가능 ' + a + '대';
    var upd = cf
      ? '<span class="ev-upd">(상태 확인 ' + esc(cf) + ')</span>'
      : '<span class="ev-upd">(상태 확인 시각 미확인)</span>';
    return head + ' · 충전 중 ' + c + '대 · 점검·운영중지 ' + dn +
      '대 · 상태 미확인 ' + un + '대\n  ' + upd;
  }

  function fetchJson(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error('ev status ' + r.status);
      return r.json();
    });
  }

  /* 지역 목록: 카드별 상태 + 첫 페이지 집계(충전 가능 있는 곳 수) */
  var list = document.querySelector('[data-ev-status]');
  if (list) {
    fetchJson(list.getAttribute('data-ev-status')).then(function (data) {
      var st = data.st || {}, cfs = data.cfs || [];
      var cards = list.querySelectorAll('[data-evsid]');
      for (var i = 0; i < cards.length; i++) {
        var rec = st[cards[i].getAttribute('data-evsid')];
        if (!rec) continue;
        var a = rec[0], c = rec[1], dn = rec[2], un = rec[3];
        var cf = cfs[rec[4]] || '';
        var badge = cards[i].querySelector('.ev-live-badge');
        if (badge) badge.innerHTML = badgeHtml(a, c, dn, un, cf);
        var fee = cards[i].querySelector('.ev-live-fee');
        if (fee) fee.innerHTML = feeHtml(a, c, dn, un, cf);
      }
      var cnt = document.querySelector('[data-ev-avail-count]');
      if (cnt) {
        var n = 0;
        for (var id in st) {
          if (Object.prototype.hasOwnProperty.call(st, id) && st[id][0] > 0) n++;
        }
        cnt.textContent = fmt(n);
      }
    }).catch(function () { /* 빌드 시점 값 유지 */ });
  }

  /* 시·도 페이지: 시·군·구별 '지금 충전 가능 있는 곳' 집계 */
  var table = document.querySelector('[data-ev-status-summary]');
  if (table) {
    fetchJson(table.getAttribute('data-ev-status-summary')).then(function (data) {
      var regs = data.r || {};
      var cells = table.querySelectorAll('[data-ev-region]');
      for (var i = 0; i < cells.length; i++) {
        var rec = regs[cells[i].getAttribute('data-ev-region')];
        if (rec) cells[i].textContent = fmt(rec[0]) + '곳';
      }
    }).catch(function () { /* 빌드 시점 값 유지 */ });
  }
})();
