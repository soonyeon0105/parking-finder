/* 제휴 안내 블록 — 링크·문구는 data/affiliate.json(배포본 /affiliate.json)에만 있다.
   이 파일을 고치지 않고 JSON만 교체하면 링크 교체·OFF(enabled=false)가 재빌드 없이 된다.
   고지 문구는 접지 않고 항상 표시한다(공정위 추천·보증 심사지침).
   클릭 측정: 링크 클릭 시 dataLayer.push 로 affiliate_click 이벤트를 보내고,
   GTM 컨테이너(GTM-THM2WBPJ)의 GA4 이벤트 태그가 GA4로 전송한다(app.js 통계
   훅과 같은 방식). */
(function () {
  var slots = document.querySelectorAll('[data-affiliate-slot]');
  if (!slots.length) return;
  var url = slots[0].getAttribute('data-affiliate-url') || '/affiliate.json';

  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('a[data-affiliate-item]') : null;
    if (!a) return;
    try {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'affiliate_click',
        affiliate_partner: a.getAttribute('data-affiliate-partner') || '',
        affiliate_item: a.getAttribute('data-affiliate-item') || '',
        affiliate_placement: a.getAttribute('data-affiliate-placement') || ''
      });
    } catch (err) {
      /* 통계 전송 실패가 링크 이동을 막지 않도록 무시한다. */
    }
  });

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function card(item, placement) {
    var track = ' data-affiliate-item="' + esc(item.id || '') + '"'
      + ' data-affiliate-partner="' + esc(item.network || '') + '"'
      + ' data-affiliate-placement="' + esc(placement || '') + '"';
    var html = '<article class="affiliate-card">';
    if (item.label) {
      html += '<span class="affiliate-label">' + esc(item.label) + '</span>';
    }
    html += '<a class="affiliate-name" href="' + esc(item.url) + '" target="_blank"'
      + ' rel="sponsored nofollow"' + track + '>' + esc(item.title) + '</a>';
    if (item.desc) {
      html += '<p class="affiliate-desc">' + esc(item.desc) + '</p>';
    }
    if (item.cta) {
      html += '<a class="affiliate-cta" href="' + esc(item.url) + '" target="_blank"'
        + ' rel="sponsored nofollow"' + track + '>' + esc(item.cta) + ' →</a>';
    }
    if (item.notice) {
      html += '<p class="affiliate-card-notice">' + esc(item.notice) + '</p>';
    }
    return html + '</article>';
  }

  function render(data) {
    if (!data || data.enabled === false) return;
    var items = data.items || [];
    for (var i = 0; i < slots.length; i++) {
      var placement = slots[i].getAttribute('data-placement') || '';
      var mine = [];
      for (var j = 0; j < items.length; j++) {
        if (items[j].placement === placement && items[j].enabled !== false && items[j].url) {
          mine.push(items[j]);
        }
      }
      if (!mine.length) continue;
      var html = '<section class="affiliate" aria-label="' + esc(data.title || '제휴 안내') + '">'
        + '<h2>' + esc(data.title || '차량 서비스 안내') + '</h2>';
      if (data.notice) {
        html += '<p class="affiliate-notice">' + esc(data.notice) + '</p>';
      }
      html += '<div class="affiliate-cards">';
      for (var k = 0; k < mine.length; k++) {
        html += card(mine[k], placement);
      }
      html += '</div></section>';
      slots[i].innerHTML = html;
    }
  }

  fetch(url).then(function (r) {
    if (!r.ok) throw new Error('affiliate data ' + r.status);
    return r.json();
  }).then(render).catch(function () {
    /* 데이터를 못 읽으면 블록을 비워 둔다 — 본문 이용에는 영향이 없다. */
  });
})();
