/* T-08: 랜딩 '내 주변 주차장' — 위치는 이 브라우저 안에서만 쓰고 서버로 보내지 않는다.
   데이터 파일(nearby.json)은 정적 자산이라 불러올 때 위치가 실리지 않는다. */
(function () {
  var section = document.getElementById('nearby');
  var btn = document.getElementById('nearby-btn');
  if (!section || !btn) return;
  var status = document.getElementById('nearby-status');
  var box = document.getElementById('nearby-results');
  var dataUrl = section.getAttribute('data-data-url') || '/assets/nearby.json';
  var dataPromise = null;

  function loadData() {
    if (!dataPromise) {
      dataPromise = fetch(dataUrl).then(function (r) {
        if (!r.ok) throw new Error('nearby data ' + r.status);
        return r.json();
      });
    }
    return dataPromise;
  }

  function distM(la1, lo1, la2, lo2) {
    var R = 6371000, rad = Math.PI / 180;
    var dLa = (la2 - la1) * rad, dLo = (lo2 - lo1) * rad;
    var a = Math.sin(dLa / 2) * Math.sin(dLa / 2) +
            Math.cos(la1 * rad) * Math.cos(la2 * rad) *
            Math.sin(dLo / 2) * Math.sin(dLo / 2);
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  /* 좌표 정밀도 한계에 맞춰 100m 단위로 반올림해 표기한다. */
  function fmtDist(m) {
    var r = Math.round(m / 100) * 100;
    if (r === 0) return '100m 이내';
    if (r < 1000) return r + 'm';
    return (r / 1000).toFixed(1) + 'km';
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function render(scored) {
    var html = '';
    for (var i = 0; i < scored.length; i++) {
      var row = scored[i][1], d = scored[i][0];
      html += '<article class="nearby-card">' +
        '<div class="nearby-top"><span class="nearby-name-wrap"><a class="nearby-name" href="' + esc(row[3]) + '">' +
          esc(row[0]) + '</a>' +
          /* row[9]: EV 표시 — [1, 충전기 수]. 그 주차장 안에 충전소가 있는
             곳만 실린다(거리만 가까운 남의 시설은 없음). 이름 바로 옆에 ⚡를
             붙인다 — 카드 아래 배지로 따로 두지 않는다(운영자 확정 2026-11-28).
             뜻은 섹션 설명란 하단 범례에 적어 둔다. */
          (row[9] ? ' <span class="ev-inline" role="img" aria-label="전기차 충전소 있음">⚡</span>' +
            '<span class="ev-count">충전기 ' + row[9][1] + '대</span>' : '') +
          '</span>' +
          '<span class="nearby-dist">' + fmtDist(d) + '</span></div>' +
        (row[7] ? '<p class="nearby-rt"><span class="badge live">실시간 잔여면수</span> ' +
          '<a href="' + esc(row[3]) + '">상세에서 확인</a>' +
          (row[8] ? ' <span class="nearby-rt-time">' + esc(row[8]) + ' 조회</span>' : '') + '</p>' : '') +
        '<p class="nearby-meta">' + esc(row[4]) + '</p>' +
        '<p class="nearby-meta">' + esc(row[5]) + '</p>' +
        '<p class="nearby-addr">' + esc(row[6]) + '</p>' +
        '</article>';
    }
    box.innerHTML = html;
  }

  function fallback(msg) {
    status.textContent = msg;
    box.innerHTML = '';
    var t = document.querySelector('.prov-tabs');
    if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  btn.addEventListener('click', function () {
    if (!navigator.geolocation) {
      fallback('이 기기에서는 위치 기능을 쓸 수 없어 지역 선택으로 안내합니다.');
      return;
    }
    status.textContent = '위치를 확인하고 있어요…';
    navigator.geolocation.getCurrentPosition(function (pos) {
      loadData().then(function (rows) {
        var la = pos.coords.latitude, lo = pos.coords.longitude;
        var scored = [];
        for (var i = 0; i < rows.length; i++) {
          scored.push([distM(la, lo, rows[i][1], rows[i][2]), rows[i]]);
        }
        scored.sort(function (a, b) { return a[0] - b[0]; });
        render(scored.slice(0, 20));
        status.textContent = '가까운 순으로 20곳을 찾았어요. 거리는 직선거리 기준이에요.';
      }).catch(function () {
        fallback('주차장 정보를 불러오지 못했어요. 지역 선택으로 안내합니다.');
      });
    }, function (err) {
      if (err && err.code === 1) {
        fallback('위치 권한이 없어 지역 선택으로 안내합니다.');
      } else {
        fallback('위치를 확인하지 못했어요. 지역 선택으로 안내합니다.');
      }
    }, { timeout: 10000, maximumAge: 300000 });
  });
})();
