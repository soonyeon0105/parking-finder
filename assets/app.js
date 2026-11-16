/* 공영주차장 파인더 — 조건 즉시 계산기
 * 정적 페이지에 server-render 된 카드의 값만 다시 계산/재배치한다.
 */
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
    if (!f.base_min || f.base_fee === null || !f.unit_min || f.unit_fee === null) {
      return { state: 'unknown' };
    }
    var raw;
    if (minutes <= f.base_min) {
      raw = f.base_fee;
    } else {
      raw = f.base_fee + Math.ceil((minutes - f.base_min) / f.unit_min) * f.unit_fee;
    }
    var capped = false, daily = f.daily_fee;
    if (daily && daily > 0 && raw > daily) { raw = daily; capped = true; }
    var paid = Math.round(raw * (1 - rate));
    return { state: 'paid', amount: paid, before: Math.round(raw), capped: capped, discounted: rate > 0 };
  }

  function orderKey(r) {
    if (r.state === 'free') return [0, 0];
    if (r.state === 'paid') return [1, r.amount];
    if (r.state === 'unknown') return [2, 0];
    return [3, 0];
  }

  function paintCard(card, res) {
    var priceEl = card.querySelector('.price');
    var noteEl = card.querySelector('.price-note');
    var freeBadge = card.querySelector('.badge.free');
    card.classList.toggle('free', res.state === 'free');
    card.classList.toggle('closed', res.state === 'closed');

    priceEl.className = 'price ' + res.state;
    if (res.state === 'free') {
      priceEl.textContent = '0원';
      if (noteEl) {
        noteEl.textContent = res.exempt
          ? '면제 시간 이내 (' + fmtTime(res.exempt_min) + ' 면제)'
          : '무료 개방 (선택한 요일)';
      }
    } else if (res.state === 'paid') {
      priceEl.textContent = won(res.amount);
      if (noteEl) {
        var bits = [];
        if (res.capped) bits.push('1일권 상한 적용');
        if (res.discounted) bits.push('정상 ' + won(res.before) + '에서 감면');
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

    results.forEach(function (r) { paintCard(r.card, r.res); });

    // 저렴한 순 정렬 (무료 → 요금 오름차순 → 미상 → 휴무)
    var sorted = results.slice().sort(function (a, b) {
      var ka = orderKey(a.res), kb = orderKey(b.res);
      if (ka[0] !== kb[0]) return ka[0] - kb[0];
      if (ka[1] !== kb[1]) return ka[1] - kb[1];
      return (a.lot.name || '').localeCompare(b.lot.name || '', 'ko');
    });
    var anchor = list.querySelector('.ad-slot');   // 광고 슬롯: 5번째·6번째 사이 고정
    sorted.forEach(function (r) { list.insertBefore(r.card, anchor || null); });
    if (anchor) {
      var fifth = sorted[Math.min(4, sorted.length - 1)];
      if (fifth && fifth.card.nextElementSibling !== anchor) {
        list.insertBefore(anchor, fifth.card.nextSibling);
      }
    }

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
  }
  // 빠른 선택 칩
  document.querySelectorAll('[data-minutes]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      var m = parseInt(chip.getAttribute('data-minutes'), 10);
      if (slider) slider.value = m;
      state.minutes = m;
      paintTime();
      refresh();
    });
  });

  paintTime();
  refresh();
})();
