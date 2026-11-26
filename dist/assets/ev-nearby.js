/* 전기차 충전소 '내 주변' — 위치는 이 브라우저 안에서만 쓰고 서버로 보내지 않는다.
   데이터 파일(ev-nearby-*.json)은 정적 자산이라 불러올 때 위치가 실리지 않는다.
   충전소 상태는 수집 시점의 마지막 확인값이라 '실시간'으로 표기하지 않는다. */
(function () {
  var section = document.getElementById('ev-nearby');
  var btn = document.getElementById('ev-nearby-btn');
  if (!section || !btn) return;
  var status = document.getElementById('ev-nearby-status');
  var box = document.getElementById('ev-nearby-results');
  var manifestUrl = section.getAttribute('data-manifest-url') || '/assets/ev-nearby-manifest.json';
  var RADIUS_M = 10000;   /* 기본 반경 10km */
  var MAX_SHOW = 20;
  var manifestPromise = null;

  function fetchJson(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('ev nearby data ' + r.status);
      return r.json();
    });
  }

  function loadManifest() {
    if (!manifestPromise) manifestPromise = fetchJson(manifestUrl);
    return manifestPromise;
  }

  function distM(la1, lo1, la2, lo2) {
    var R = 6371000, rad = Math.PI / 180;
    var dLa = (la2 - la1) * rad, dLo = (lo2 - lo1) * rad;
    var a = Math.sin(dLa / 2) * Math.sin(dLa / 2) +
            Math.cos(la1 * rad) * Math.cos(la2 * rad) *
            Math.sin(dLo / 2) * Math.sin(dLo / 2);
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  /* 거리는 km 소수 1자리로 표기한다. 100m 안은 '100m 이내'로 뭉뚱그린다
     (좌표 정밀도 한계 — 주차장 nearby.js 와 같은 기준). */
  function fmtDist(m) {
    if (m < 100) return '100m 이내';
    return (m / 1000).toFixed(1) + 'km';
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* 지도 링크는 build_site.py 의 ev_station_links 와 같은 형식으로 만든다 —
     핀 이름에 '전기차충전소'를 붙여 지도에서 충전소로 찍히게 한다. */
  function stationLinks(name, lat, lng) {
    var label = String(name || '전기차 충전소').replace(/,/g, '·');
    if (label.indexOf('충전소') === -1) label += ' 전기차충전소';
    var q = encodeURIComponent(label);
    return {
      kakao: 'https://map.kakao.com/link/map/' + q + ',' + lat + ',' + lng,
      naver: 'https://map.naver.com/?lat=' + lat + '&lng=' + lng + '&dlevel=12&title=' + q
    };
  }

  /* 행 배열: [이름, 위도, 경도, 급속, 완속, 충전가능, 상태확인시각, 주소, 지역인덱스] */
  function render(scored, regions) {
    var html = '';
    for (var i = 0; i < scored.length; i++) {
      var row = scored[i][1], d = scored[i][0];
      var links = stationLinks(row[0], row[1], row[2]);
      var rp = regions[row[8]] || '/ev/';
      html += '<article class="card ev-card">' +
        '<div class="lot-head"><h3>' + esc(row[0]) + '</h3>' +
        '<div class="badges"><span class="badge ev">' + fmtDist(d) + '</span></div></div>' +
        '<p class="addr">' + esc(row[7]) + '</p>' +
        '<p class="fee-line">급속 ' + row[3] + '기 · 완속 ' + row[4] + '기 · 지금 충전 가능 ' + row[5] + '대 ' +
        '<span class="ev-upd">(상태 확인 ' + esc(row[6]) + ')</span></p>' +
        '<div class="actions">' +
        '<a class="btn solid" href="' + esc(links.kakao) + '" target="_blank" rel="nofollow noopener">카카오맵</a>' +
        '<a class="btn" href="' + esc(links.naver) + '" target="_blank" rel="nofollow noopener">네이버지도</a>' +
        '<a class="btn" href="' + esc(rp) + '">이 지역 충전소 전체 보기</a>' +
        '</div></article>';
    }
    box.innerHTML = html;
  }

  function fallback(msg) {
    status.textContent = msg;
    box.innerHTML = '<p class="nearby-note">위치 대신 지역으로 찾을 수 있어요 — ' +
      '<a href="../">지역별 전기차 충전소 목록</a>에서 시·도를 고르세요.</p>';
  }

  /* 현재 위치가 든 시·도 파일만 골라 받는다. 경계 너머 10km 안 충전소를 놓치지
     않게 시·도 경계 상자를 0.15도(약 13~17km) 넓혀서 대조한다. */
  function pickFiles(manifest, la, lo) {
    var pad = 0.15, urls = [];
    var base = manifestUrl.split('?')[0].replace(/[^/]*$/, '');
    var query = manifestUrl.indexOf('?') !== -1 ? manifestUrl.slice(manifestUrl.indexOf('?')) : '';
    var files = manifest.files || {};
    for (var slug in files) {
      if (!Object.prototype.hasOwnProperty.call(files, slug)) continue;
      var b = files[slug].bbox;
      if (la >= b[0] - pad && la <= b[2] + pad && lo >= b[1] - pad && lo <= b[3] + pad) {
        urls.push(base + files[slug].file + query);
      }
    }
    return urls;
  }

  btn.addEventListener('click', function () {
    if (!navigator.geolocation) {
      fallback('이 기기에서는 위치 기능을 쓸 수 없어 지역 목록으로 안내합니다.');
      return;
    }
    status.textContent = '위치를 확인하고 있어요…';
    box.innerHTML = '';
    navigator.geolocation.getCurrentPosition(function (pos) {
      var la = pos.coords.latitude, lo = pos.coords.longitude;
      loadManifest().then(function (manifest) {
        var urls = pickFiles(manifest, la, lo);
        if (!urls.length) throw new Error('no province file for position');
        return Promise.all(urls.map(fetchJson));
      }).then(function (packs) {
        var regions = [], rows = [];
        for (var i = 0; i < packs.length; i++) {
          var base = regions.length;
          for (var j = 0; j < packs[i].r.length; j++) regions.push(packs[i].r[j]);
          for (var k = 0; k < packs[i].rows.length; k++) {
            var row = packs[i].rows[k].slice();
            row[8] = base + row[8];
            rows.push(row);
          }
        }
        var scored = [];
        for (var m = 0; m < rows.length; m++) {
          scored.push([distM(la, lo, rows[m][1], rows[m][2]), rows[m]]);
        }
        scored.sort(function (a, b) { return a[0] - b[0]; });
        var within = scored.filter(function (s) { return s[0] <= RADIUS_M; });
        if (within.length) {
          render(within.slice(0, MAX_SHOW), regions);
          status.textContent = '10km 안에서 가까운 순으로 ' +
            Math.min(within.length, MAX_SHOW) + '곳을 찾았어요. 거리는 직선거리 기준이에요.';
        } else if (scored.length) {
          render(scored.slice(0, MAX_SHOW), regions);
          status.textContent = '10km 안에는 충전소가 없어, 가장 가까운 충전소부터 보여 드립니다. ' +
            '거리는 직선거리 기준이에요.';
        } else {
          fallback('현재 위치 주변에서 충전소 정보를 찾지 못했어요. 지역 목록으로 안내합니다.');
        }
      }).catch(function () {
        fallback('충전소 정보를 불러오지 못했어요. 지역 목록으로 안내합니다.');
      });
    }, function (err) {
      if (err && err.code === 1) {
        fallback('위치 권한이 없어 지역 목록으로 안내합니다. 브라우저 설정에서 위치를 허용하면 주변 충전소를 찾을 수 있어요.');
      } else {
        fallback('위치를 확인하지 못했어요. 지역 목록으로 안내합니다.');
      }
    }, { timeout: 10000, maximumAge: 300000 });
  });
})();
