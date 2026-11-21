/* 제휴 안내 블록 — 링크·문구는 data/affiliate.json(배포본 /affiliate.json)에만 있다.
   이 파일을 고치지 않고 JSON만 교체하면 링크 교체·OFF(enabled=false)가 재빌드 없이 된다.
   고지 문구는 접지 않고 항상 표시한다(공정위 추천·보증 심사지침). */
(function () {
  var slots = document.querySelectorAll('[data-affiliate-slot]');
  if (!slots.length) return;
  var url = slots[0].getAttribute('data-affiliate-url') || '/affiliate.json';

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function card(item) {
    var html = '<article class="affiliate-card">';
    if (item.label) {
      html += '<span class="affiliate-label">' + esc(item.label) + '</span>';
    }
    html += '<a class="affiliate-name" href="' + esc(item.url) + '" target="_blank"'
      + ' rel="sponsored nofollow">' + esc(item.title) + '</a>';
    if (item.desc) {
      html += '<p class="affiliate-desc">' + esc(item.desc) + '</p>';
    }
    if (item.cta) {
      html += '<a class="affiliate-cta" href="' + esc(item.url) + '" target="_blank"'
        + ' rel="sponsored nofollow">' + esc(item.cta) + ' →</a>';
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
        html += card(mine[k]);
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
