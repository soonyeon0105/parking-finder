/* 공영주차장 파인더 — 조건 즉시 계산기
 * 정적 페이지에 server-render 된 카드의 값만 다시 계산/재배치한다.
 */

/* ---------------------------------------------------------------- 통계 훅 (T-05)
 * data/site.json 의 ga_measurement_id 가 비어 있으면 gtag.js 를 넣지 않으므로 window.gtag 가
 * 없다. 아래 훅은 gtag 가 함수일 때만 이벤트를 보내고, 없으면 아무 것도 하지 않는다(무동작).
 * 이벤트 4종: calc_use · map_outbound_click · free_filter_click · 404_hit
 * 계산기 코드와 분리해 두어 #lot-data 가 없는 404·개인정보처리방침 페이지에서도 돈다.
 */
(function () {
  'use strict';

  function track(name, params) {
    if (typeof window.gtag !== 'function') return;
    try {
      window.gtag('event', name, params || {});
    } catch (err) {
      /* 통계 전송 실패가 화면 동작을 막지 않도록 무시한다. */
    }
  }
  window.pfTrack = track;   // 계산기 쪽에서도 같은 가드를 쓰도록 노출

  function clean(s, max) {
    return String(s || '').replace(/\s+/g, ' ').trim().slice(0, max || 60);
  }

  function anchorName(el) {
    var card = el.closest ? el.closest('.lot') : null;
    if (card) {
      var h = card.querySelector('h3');
      if (h) return clean(h.textContent);
    }
    var row = el.closest ? el.closest('tr') : null;
    if (row) {
      var cell = row.querySelector('td');
      if (cell) return clean(cell.textContent);
    }
    return '';
  }

  // 404_hit — 404.html 은 <body data-page="404"> 로 표시된다.
  if (document.body && document.body.getAttribute('data-page') === '404') {
    track('404_hit', { page_path: location.pathname });
  }

  // map_outbound_click · free_filter_click — 링크 클릭을 문서 단위로 받는다.
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.getAttribute('href') || '';
    var isKakao = href.indexOf('map.kakao.com') > -1;
    var isNaver = href.indexOf('map.naver.com') > -1;
    if (isKakao || isNaver) {
      track('map_outbound_click', {
        map: isKakao ? 'kakao' : 'naver',
        lot_name: anchorName(a),
        page_path: location.pathname
      });
    } else if (href.indexOf('weekend-free') > -1) {
      track('free_filter_click', {
        link_text: clean(a.textContent),
        page_path: location.pathname
      });
    }
  });
})();

(function () {
  'use strict';

  var dataEl = document.getElementById('lot-data');
  if (!dataEl) return;
  var LOTS = JSON.parse(dataEl.textContent);
  var byId = {};
  LOTS.forEach(function (l) { byId[l.id] = l; });

  var list = document.getElementById('lot-list');
  var cards = list ? Array.prototype.slice.call(list.querySelectorAll('.lot')) : [];

  var state = {
    day: (list && list.getAttribute('data-day')) || 'weekday',
    minutes: 120,
    discount: 0,
    exempt: 0
  };

  var won = function (n) { return n.toLocaleString('ko-KR') + '원'; };

  function discountLabel() {
    var g = document.getElementById('discount-group');
    var b = g ? g.querySelector('button[aria-pressed="true"]') : null;
    return b ? (b.textContent || '').replace(/\s+/g, ' ').trim() : '';
  }

  // calc_use — 계산기 조작. 슬라이더는 input(움직일 때마다)이 아니라 change(손 뗄 때)에 한 번만 보낸다.
  function fireCalc(action) {
    if (typeof window.pfTrack !== 'function') return;
    window.pfTrack('calc_use', {
      calculator_action: action,
      day: state.day,
      minutes: state.minutes,
      discount: discountLabel(),
      page_path: location.pathname
    });
  }

  function priceFor(lot, minutes, day, rate, exempt) {
    if (!lot.oper[day]) return { state: 'closed' };
    var f = lot.fee;
    if (f.type === '무료' || (day !== 'weekday' && lot.free_days[day])) {
      return { state: 'free' };
    }
    // 조례상 면제 시간(분): 이 시간 이내 이용은 0원, 넘으면 감면율 적용 (예: 성남 장애인 1시간 면제 후 50%)
    if (exempt && minutes <= exempt) {
      return { state: 'free', exempt: true, exempt_min: exempt };
    }
    if (f.type !== '유료') return { state: 'unknown' };
    if (!f.base_min || f.base_fee === null) {
      return { state: 'unknown' };
    }
    // 최초 무료 시간(분): 이 시간 이내 이용은 0원 (예: 안양시 최초 15분 무료)
    if (f.free_min && minutes <= f.free_min) {
      return { state: 'free', free_min: f.free_min };
    }
    // 최초 N분 무료 정책(김포시 1시간 무료) — 그 시간 이내는 0원이다.
    if (f.deduct_min && minutes <= f.deduct_min) {
      return { state: 'free', deducted: true, deduct_min: f.deduct_min };
    }
    if (!(f.bands && f.bands.length) && (!f.unit_min || f.unit_fee === null)) {
      return { state: 'unknown' };
    }
    // 그 시간만큼 주차했을 때의 요금과 1일 상한 적용 여부
    function rawCharge(mins) {
      var raw;
      if (f.bands && f.bands.length) {
        // 구간 요금(의왕시 행락지) — 머문 시간이 속한 구간의 금액을 받는다.
        raw = f.bands[f.bands.length - 1].amount;
        for (var j = 0; j < f.bands.length; j++) {
          var b = f.bands[j];
          if (b.until === null || b.until === undefined || mins <= b.until) { raw = b.amount; break; }
        }
      } else if (f.steps && f.steps.length) {
        // 시간대별 누진 할증 (예: 안양시 — 1시간까지 10분당 300원, 2시간까지 600원 …)
        var t = f.base_min;
        raw = f.base_fee;
        while (t < mins) {
          var step = f.steps[f.steps.length - 1];
          for (var i = 0; i < f.steps.length; i++) {
            if (f.steps[i].until === null || f.steps[i].until === undefined || t < f.steps[i].until) {
              step = f.steps[i];
              break;
            }
          }
          raw += step.unit_fee;
          // 단계마다 단위 시간이 다를 수 있다(세종 — 2시간까지 10분, 2시간 초과 15분).
          t += step.unit_min || f.unit_min || 10;
        }
      } else if (mins <= f.base_min) {
        raw = f.base_fee;
      } else {
        raw = f.base_fee + Math.ceil((mins - f.base_min) / f.unit_min) * f.unit_fee;
      }
      var capped = false, daily = f.daily_fee, cap = f.cap_fee;
      if (cap && cap > 0 && raw > cap) { raw = cap; capped = true; }
      else if (daily && daily > 0 && raw > daily) { raw = daily; capped = true; }
      return { raw: raw, capped: capped };
    }
    var baseCharge = rawCharge(minutes);
    var best = baseCharge.raw, capped = baseCharge.capped, deducted = false, discounted = false;
    // 최초 N분 무료 정책(김포시 1시간 무료) — 그 시간을 뺀 요금으로 계산한다.
    if (f.deduct_min && minutes > f.deduct_min) {
      var d = rawCharge(minutes - f.deduct_min);
      if (d.raw < best) { best = d.raw; capped = d.capped; deducted = true; }
    }
    // 조례가 ‘감면은 한 가지만’이라고 정한 도시는 감면율을 적용한 요금과 비교해 싼 쪽을 쓴다.
    if (rate > 0) {
      var r = Math.round(baseCharge.raw * (1 - rate));
      if (r < best) { best = r; capped = baseCharge.capped; deducted = false; discounted = true; }
    }
    return { state: 'paid', amount: best, before: Math.round(baseCharge.raw),
             capped: capped, discounted: discounted, deducted: deducted };
  }

  function orderKey(r) {
    if (r.state === 'free') return [0, 0];
    if (r.state === 'paid') return [1, r.amount];
    if (r.state === 'unknown') return [2, 0];
    return [3, 0];
  }

  function paintCard(card, res, lot) {
    var priceEl = card.querySelector('.price');
    var noteEl = card.querySelector('.price-note');
    var freeBadge = card.querySelector('.badge.free');
    card.classList.toggle('free', res.state === 'free');
    card.classList.toggle('closed', res.state === 'closed');

    priceEl.className = 'price ' + res.state;
    if (res.state === 'free') {
      priceEl.textContent = '0원';
      if (noteEl) {
        var dmFree = res.deduct_min || (lot && lot.fee.deduct_min) || 0;
        noteEl.textContent = res.exempt
          ? '면제 시간 이내 (' + fmtTime(res.exempt_min) + ' 면제)'
          : (lot && lot.fee.type === '무료' ? '요금 구분 ‘무료’'
            : (res.deducted || dmFree
              ? (dmFree && dmFree % 60 === 0 ? '최초 ' + (dmFree / 60) + '시간 무료 적용'
                                             : '최초 ' + dmFree + '분 무료 적용')
              : (res.free_min ? '최초 ' + res.free_min + '분 무료' : '무료 개방 (선택한 요일)')));
      }
    } else if (res.state === 'paid') {
      priceEl.textContent = won(res.amount);
      if (noteEl) {
        var bits = [];
        if (res.deducted && lot && lot.fee.deduct_min) {
          var dm = lot.fee.deduct_min;
          bits.push(dm % 60 === 0 ? '최초 ' + (dm / 60) + '시간 무료 적용' : '최초 ' + dm + '분 무료 적용');
        }
        if (res.capped) bits.push((lot && lot.fee.cap_fee) ? '일일 최대요금 적용' : '1일권 상한 적용');
        if (res.discounted) bits.push('정상 ' + won(res.before) + '에서 감면');
        if (!bits.length && lot && !lot.fee.base_fee && lot.fee.free_min) {
          bits.push('최초 ' + lot.fee.free_min + '분 무료 기준');
        }
        noteEl.textContent = bits.join(' · ') || '기본요금·추가요금 기준';
      }
    } else if (res.state === 'unknown') {
      priceEl.textContent = '요금 정보 미상';
      if (noteEl) noteEl.textContent = '현장 확인 필요';
    } else {
      priceEl.textContent = '휴무';
      if (noteEl) noteEl.textContent = '선택한 요일에 운영하지 않음';
    }
    if (freeBadge) freeBadge.style.display = res.state === 'free' ? '' : 'none';
  }

  function updateSummary(results) {
    var box = document.getElementById('calc-summary');
    if (!box) return;
    var free = results.filter(function (r) { return r.res.state === 'free'; }).length;
    var paid = results.filter(function (r) { return r.res.state === 'paid'; });
    var unknown = results.filter(function (r) { return r.res.state === 'unknown'; }).length;
    var closed = results.filter(function (r) { return r.res.state === 'closed'; }).length;
    paid.sort(function (a, b) { return a.res.amount - b.res.amount; });
    var dayName = { weekday: '평일', sat: '토요일', sun: '일요일·공휴일' }[state.day];
    var parts = [];
    parts.push('<strong>' + dayName + ' · ' + fmtTime(state.minutes) + '</strong> 기준');
    parts.push('무료 <strong>' + free + '곳</strong>');
    if (paid.length) parts.push('가장 저렴 <strong>' + won(paid[0].res.amount) + '</strong>');
    if (unknown) parts.push('요금 미상 ' + unknown + '곳');
    if (closed) parts.push('휴무 ' + closed + '곳');
    box.innerHTML = parts.join(' · ');
  }

  function fmtTime(m) {
    var h = Math.floor(m / 60), mi = m % 60;
    if (h === 0) return mi + '분';
    if (mi === 0) return h + '시간';
    return h + '시간 ' + mi + '분';
  }

  function refresh() {
    var results = cards.map(function (card) {
      var lot = byId[card.getAttribute('data-lot')];
      if (!lot) return null;
      return { card: card, lot: lot, res: priceFor(lot, state.minutes, state.day, state.discount, state.exempt) };
    }).filter(Boolean);

    results.forEach(function (r) { paintCard(r.card, r.res, r.lot); });

    // 저렴한 순 정렬 (무료 → 요금 오름차순 → 미상 → 휴무)
    var sorted = results.slice().sort(function (a, b) {
      var ka = orderKey(a.res), kb = orderKey(b.res);
      if (ka[0] !== kb[0]) return ka[0] - kb[0];
      if (ka[1] !== kb[1]) return ka[1] - kb[1];
      return (a.lot.name || '').localeCompare(b.lot.name || '', 'ko');
    });
    // 정렬은 DOM 이동 대신 CSS `order` 로 한다. 예전에는 insertBefore 로 카드와 광고 슬롯을 함께
    // 옮겼는데, 실제 <ins class=adsbygoogle> 이 들어오면 노드 이동 = iframe 재생성 = 광고 재요청이
    // 되어 애드센스 정책(광고 새로고침 금지)에 어긋나고 CLS 도 생긴다.
    // 광고 슬롯은 서버가 style="order:5" 로 고정하고, 카드는 5번째까지 0~4, 그 뒤는 6부터 준다.
    sorted.forEach(function (r, i) { r.card.style.order = (i < 5 ? i : i + 1); });

    updateSummary(results);
  }

  function setPressed(group, value, attr) {
    group.querySelectorAll('button').forEach(function (b) {
      var on = String(b.getAttribute(attr)) === String(value);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  // 요일
  var dayGroup = document.getElementById('day-group');
  if (dayGroup) {
    dayGroup.addEventListener('click', function (e) {
      var btn = e.target.closest('button.seg-btn');
      if (!btn) return;
      state.day = btn.getAttribute('data-day');
      setPressed(dayGroup, state.day, 'data-day');
      refresh();
      fireCalc('day');
    });
  }

  // 감면
  var discGroup = document.getElementById('discount-group');
  if (discGroup) {
    discGroup.addEventListener('click', function (e) {
      var btn = e.target.closest('button.seg-btn');
      if (!btn) return;
      state.discount = parseFloat(btn.getAttribute('data-rate'));
      state.exempt = parseInt(btn.getAttribute('data-exempt') || '0', 10) || 0;
      // 감면율이 같은 버튼이 둘 이상일 수 있으므로(예: 성남 50% / 1시간 면제 후 50%) 누른 버튼 자체로 표시한다.
      Array.prototype.forEach.call(discGroup.querySelectorAll('button'), function (b) {
        b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
      });
      refresh();
      fireCalc('discount');
    });
  }

  // 시간 슬라이더
  var slider = document.getElementById('time-slider');
  var timeLabel = document.getElementById('time-label');
  function paintTime() {
    if (timeLabel) {
      var h = Math.floor(state.minutes / 60), mi = state.minutes % 60;
      var html = '';
      if (h) html += '<span class="w">' + h + '</span>시간 ';
      if (mi || !h) html += (mi ? '<span class="w">' + mi + '</span>분' : '0분');
      timeLabel.innerHTML = html;
    }
  }
  if (slider) {
    state.minutes = parseInt(slider.value, 10) || 120;
    slider.addEventListener('input', function () {
      state.minutes = parseInt(slider.value, 10);
      paintTime();
      refresh();
    });
    // change 는 손을 뗄 때 한 번만 발생한다 — 키 입력·드래그마다 이벤트를 보내지 않기 위해 여기서 기록한다.
    slider.addEventListener('change', function () { fireCalc('time_slider'); });
  }
  // 빠른 선택 칩
  document.querySelectorAll('[data-minutes]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var m = parseInt(chip.getAttribute('data-minutes'), 10);
      if (slider) slider.value = m;
      state.minutes = m;
      paintTime();
      refresh();
      fireCalc('quick_time');
    });
  });

  paintTime();
  refresh();
})();


/* ---------------------------------------------------------------- 지역 UI (2026-11-18)
 * ① 상단 헤더의 ‘지역 빠른 이동’ 선택 → 그 지역 페이지로 이동
 * ② 홈의 시·도 탭 → 한 번에 한 시·도만 보여 준다(다른 시·도의 링크는 HTML 에 그대로 남는다)
 * ③ 목록의 무료 필터 칩(?f=weekend · ?now=1) → 카드를 숨겨 걸러 낸다(정렬 order 와 별개)
 */
(function () {
  'use strict';

  // ① 지역 빠른 이동
  var jump = document.getElementById('region-jump');
  if (jump) {
    jump.addEventListener('change', function () {
      if (jump.value) location.href = jump.value;
    });
  }

  // ② 시·도 탭
  var tabs = document.querySelectorAll('.prov-tabs .ptab');
  if (tabs.length) {
    function selectPanel(key, track) {
      Array.prototype.forEach.call(tabs, function (t) {
        t.setAttribute('aria-selected', t.getAttribute('data-panel') === key ? 'true' : 'false');
      });
      Array.prototype.forEach.call(document.querySelectorAll('.prov-panel'), function (p) {
        if (p.getAttribute('data-prov') === key) p.removeAttribute('hidden');
        else p.setAttribute('hidden', '');
      });
      if (track && window.pfTrack) {
        window.pfTrack('region_tab_click', { tab: key, page_path: location.pathname });
      }
    }
    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener('click', function () { selectPanel(tab.getAttribute('data-panel'), true); });
    });
    // 빵부스러기의 시·도 링크(/#seoul 등)로 들어오면 그 시·도 탭을 열어 준다.
    var hash = (location.hash || '').replace('#', '');
    if (hash && document.querySelector('.prov-tabs .ptab[data-panel="' + hash + '"]')) {
      selectPanel(hash, false);
      var target = document.getElementById(hash);
      if (target && target.scrollIntoView) target.scrollIntoView();
    }
  }
})();

/* ---------------------------------------------------------------- 무료 필터 칩
 * 무료(요금 구분) · 주말·공휴일 · 야간 · 지금 무료·운영 중. 상태는 URL 에 남겨 공유·뒤로가기가 된다.
 * ‘지금’은 브라우저 시간을 KST(UTC+9)로 옮겨 계산하고, 공휴일은 페이지에 심은 2026~2027 목록을 쓴다.
 */
(function () {
  'use strict';
  var box = document.getElementById('free-filter');
  var list = document.getElementById('lot-list');
  var dataEl = document.getElementById('lot-data');
  if (!box || !list || !dataEl) return;

  var byId = {};
  try {
    JSON.parse(dataEl.textContent).forEach(function (l) { byId[l.id] = l; });
  } catch (e) { return; }
  var HOLIDAYS = [];
  var holEl = document.getElementById('holiday-data');
  if (holEl) {
    try { HOLIDAYS = JSON.parse(holEl.textContent) || []; } catch (e2) { HOLIDAYS = []; }
  }
  var cards = Array.prototype.slice.call(list.querySelectorAll('.lot'));
  var chips = Array.prototype.slice.call(box.querySelectorAll('.ff-chip'));
  var status = document.getElementById('ff-status');
  var state = { f: '', now: false };

  var q = new URLSearchParams(location.search || '');
  state.f = ['free', 'weekend', 'night'].indexOf(q.get('f')) >= 0 ? q.get('f') : '';
  state.now = q.get('now') === '1';

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function nowKst() {
    var d = new Date(Date.now() + 9 * 3600 * 1000);   // KST 고정(서머타임 없음)
    return {
      date: d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate()),
      dow: d.getUTCDay(),
      minutes: d.getUTCHours() * 60 + d.getUTCMinutes()
    };
  }

  function isFreeNow(lot) {
    var t = nowKst();
    var day = t.dow === 0 ? 'sun' : (t.dow === 6 ? 'sat' : 'weekday');
    var isHol = HOLIDAYS.indexOf(t.date) >= 0 && t.dow !== 0;
    var hk = isHol ? 'sun' : day;              // 공휴일에는 일요일 운영시간을 쓴다
    var h = lot.hours && lot.hours[hk];
    if (h && h.open === false) return false;   // 그날 문을 닫음
    if (lot.fee && lot.fee.type === '무료') return true;
    var fw = lot.free_window;
    if (fw) {
      var inWin = fw.wrap ? (t.minutes >= fw.start || t.minutes < fw.end)
                          : (t.minutes >= fw.start && t.minutes < fw.end);
      return inWin;                            // 무료 시간대가 정해진 곳은 그 시간대에만 무료
    }
    if (day === 'sat' && lot.free_days && lot.free_days.sat) return true;
    if (day === 'sun' && lot.free_days && lot.free_days.sun) return true;
    if (isHol && (lot.free_holiday || (lot.free_days && lot.free_days.sun))) return true;
    return false;
  }

  function matches(lot) {
    if (!state.f && !state.now) return true;
    if (lot.access === 'permit') return false;  // 월정기·공무원·화물 전용은 무료 목록에서 뺀다
    var tags = lot.free_tags || [];
    if (state.f === 'free' && tags.indexOf('무료') < 0) return false;
    if (state.f === 'weekend' && tags.indexOf('주말') < 0 && tags.indexOf('공휴일') < 0) return false;
    if (state.f === 'night' && tags.indexOf('심야') < 0) return false;
    if (state.now && !isFreeNow(lot)) return false;
    return true;
  }

  function syncUrl() {
    var params = new URLSearchParams();
    if (state.f) params.set('f', state.f);
    if (state.now) params.set('now', '1');
    var qs = params.toString();
    if (location.protocol === 'file:') return;
    try {
      history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
    } catch (e) { /* 파일 모드 등에서는 주소를 바꾸지 않는다 */ }
  }

  function apply(track) {
    var shown = 0, nowFree = 0;
    cards.forEach(function (card) {
      var lot = byId[card.getAttribute('data-lot')];
      var ok = lot ? matches(lot) : true;
      card.style.display = ok ? '' : 'none';
      if (ok) {
        shown += 1;
        if (lot && isFreeNow(lot)) nowFree += 1;
      }
    });
    chips.forEach(function (chip) {
      if (chip.hasAttribute('data-f')) {
        chip.setAttribute('aria-pressed', chip.getAttribute('data-f') === state.f ? 'true' : 'false');
      } else if (chip.id === 'ff-now') {
        chip.setAttribute('aria-pressed', state.now ? 'true' : 'false');
      }
    });
    if (status) {
      status.textContent = shown + '곳 표시 중' + (state.now ? ' · 지금 무료·운영 중 ' + nowFree + '곳' : '');
    }
    syncUrl();
    if (track && window.pfTrack) {
      window.pfTrack('free_filter_click', {
        link_text: (track.textContent || '').replace(/\s+/g, ' ').trim(),
        filter: state.f || 'now',
        page_path: location.pathname
      });
    }
  }

  box.addEventListener('click', function (e) {
    var chip = e.target.closest ? e.target.closest('.ff-chip') : null;
    if (!chip) return;
    if (chip.hasAttribute('data-f')) {
      state.f = chip.getAttribute('data-f');
    } else if (chip.id === 'ff-now') {
      state.now = !state.now;
    }
    apply(chip);
  });

  apply(false);
})();
