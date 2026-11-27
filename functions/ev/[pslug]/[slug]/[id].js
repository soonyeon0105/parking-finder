/* EV 충전소 단독 상세 페이지 — Pages Functions 동적 렌더링(안 A, 설계 #948 §4).
 *
 * 정적 파일은 만들지 않는다. /ev/{pslug}/{slug}/{id} 요청이 오면 지역 JSON
 * (dist/assets/ev-detail/{pslug}-{slug}.json)에서 충전소를 찾아 템플릿
 * (dist/assets/ev-detail-template.html)에 채워 반환한다. 토큰 목록은
 * scripts/build_ev.py 의 DETAIL_TOKENS 와 같다 — 한쪽을 고치면 다른 쪽도
 * 함께 고칠 것.
 *
 * 동작:
 *  ① id 가 숫자만이면 지역 목록 페이지네이션(/ev/{도}/{구}/{숫자}/)이므로
 *     정적 자산을 그대로 반환한다(env.ASSETS.fetch).
 *  ② 그 외는 지역 JSON에서 id 일치 충전소를 찾아 템플릿에 채워 반환한다.
 *     상세 대상(d=1)이 아닌 충전소는 상세 페이지가 없으므로 404 다.
 *  ③ 없으면 사이트 404 페이지를 404 상태로 반환한다.
 *  ④ 말미 슬래시 없는 요청은 슬래시 있는 URL로 301 한다.
 *
 * 응답 헤더: Cache-Control: public, max-age=3600, stale-while-revalidate=86400
 * (반복 조회는 엣지 캐시가 받아 Functions 호출을 줄인다).
 */

const CACHE = 'public, max-age=3600, stale-while-revalidate=86400';
const NOT_FOUND_CACHE = 'public, max-age=300';

/* build_site.py 의 esc() (html.escape, quote=True)와 같은 규칙. */
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
  })[c]);
}

/* build_site.py 의 rel() 과 같은 규칙 — 현재 페이지 깊이 기준 상대경로. */
function relPrefix(path) {
  return '../'.repeat(path.split('/').filter(Boolean).length);
}

function rel(path, target) {
  const t = String(target).replace(/^\/+/, '');
  return t ? relPrefix(path) + t : (relPrefix(path) || './');
}

function updSpan(st) {
  return st.cf
    ? `<span class="ev-upd">(상태 확인 ${esc(st.cf)})</span>`
    : '<span class="ev-upd">(상태 확인 시각 미확인)</span>';
}

/* build_site.py 의 ev_cf_stale() 과 같은 기준 — 상태 확인 시각(cf)이
 * 24시간을 넘었는지. cf는 'YYYY-MM-DD HH:MM' (KST)이라 +09:00을 붙여 파싱한다.
 * statUpdDt 가 오래됐다는 이유만으로 '오래됐습니다' 안내를 붙이지 않는다
 * (상태가 안 바뀐 것뿐일 수 있다). 기획안 v1.2 P0-3. */
function isStaleCf(cf) {
  if (!cf) return false;
  var t = Date.parse(String(cf).slice(0, 16).replace(' ', 'T') + ':00+09:00');
  if (Number.isNaN(t)) return false;
  return Date.now() - t > 24 * 3600 * 1000;
}

/* build_ev.py 의 avail_text/avail_desc 와 같은 규칙.
 * 한쪽을 고치면 다른 쪽도 함께 고칠 것 — 파이썬 기준본과 Functions 출력이
 * 어긋나지 않게 한다.
 * '상태 확인'은 statUpdDt(상태 변경 시각)가 아니라 확인 시각(cf — 상태를
 * 확인한 스냅샷 시각) 기준이다. statUpdDt 가 오래됐다는 이유만으로
 * '오래됐습니다' 안내를 붙이지 않는다(상태가 안 바뀐 것뿐일 수 있다).
 * P0-3: cf가 24시간을 넘었으면 '지금 충전 가능'을 쓰지 않고 '상태 확인 중'으로 적는다. */
function availUnknown(st) {
  const total = st.f + st.s;
  return total > 0 && st.a === 0 && st.un === total;
}

function availText(st) {
  if (isStaleCf(st.cf)) return '상태 확인 중';
  return availUnknown(st) ? '상태 모름' : `지금 충전 가능 ${st.a}대`;
}

function availDesc(st) {
  if (isStaleCf(st.cf)) return '상태 확인 중';
  return availUnknown(st) ? '충전 가능 여부 미확인' : `지금 충전 가능 ${st.a}대`;
}

function feeLine(st) {
  return `${availText(st)} · 충전 중 ${st.c}대 · 점검·운영중지 ${st.dn}대 · 상태 미확인 ${st.un}대\n  ${updSpan(st)}`;
}

function badges(st) {
  let out = '<span class="badge kind">충전소</span>';
  if (st.f) out += `<span class="badge">급속 ${st.f}기</span>`;
  if (st.s) out += `<span class="badge">완속 ${st.s}기</span>`;
  if (isStaleCf(st.cf)) out += '<span class="badge unknown">상태 확인 중</span>';
  else if (st.a) out += `<span class="badge ev">지금 충전 가능 ${st.a}대</span>`;
  else if (availUnknown(st)) out += '<span class="badge unknown">상태 모름</span>';
  return out;
}

function metaItems(st) {
  let out = '';
  if (st.op) out += `<li><b>운영</b> ${esc(st.op)}</li>`;
  if (st.ut) out += `<li><b>이용시간</b> ${esc(st.ut)}</li>`;
  if (st.pf === 'Y') out += '<li><b>주차</b> 무료</li>';
  else if (st.pf === 'N') out += '<li><b>주차</b> 유료·확인 필요</li>';
  if (st.call) out += `<li><b>문의</b> <a href="tel:${esc(st.call)}">${esc(st.call)}</a></li>`;
  if (st.lim) out += `<li><b>이용 제한</b> ${esc(st.lim)}</li>`;
  if (st.note) out += `<li><b>안내</b> ${esc(st.note)}</li>`;
  return out;
}

function chargerBlock(st) {
  const rows = (st.ch || []).map((c) =>
    `<tr><td>${esc(c[0])}번</td><td>${esc(c[1])}</td>` +
    `<td class="num">${c[2] ? esc(`${c[2]}kW`) : '-'}</td><td>${esc(c[3])}</td></tr>`,
  ).join('');
  if (!rows) return '';
  const total = st.f + st.s;
  return `<h2>충전기 ${total}기</h2>` +
    '<div class="table-scroll"><table class="data">\n<thead><tr><th>번호</th><th>종류</th>' +
    '<th class="num">출력</th><th>상태</th></tr></thead>\n' +
    `<tbody>${rows}</tbody>\n</table></div>`;
}

function lotsBlock(region, st, path) {
  /* P0-3: 좌표-주소 불일치 47곳(st.mm=1)은 블록을 표시하지 않는다 — 잘못된
     주차장을 안내하는 것보다 안 보여주는 것이 낫다. 본문은 그대로 둔다. */
  if (st.mm) return '';
  const lots = st.lots || [];
  if (lots.length) {
    const rows = lots.map((lot) => {
      const badge = `<span class="badge ev">${esc(lot.dist)}</span>` +
        (lot.on ? '<span class="badge">주차하면서 충전 가능</span>' : '');
      const name = lot.href
        ? `<a href="${esc(rel(path, lot.href))}">${esc(lot.nm)}</a>`
        : esc(lot.nm);
      return '<article class="card">\n  <div class="lot-head">\n' +
        `    <h3>${name}</h3>\n    <div class="badges">${badge}</div>\n  </div>\n` +
        `  <p class="addr">${esc(lot.addr)}</p>\n` +
        `  <p class="fee-line">요금 구분 ${esc(lot.fee)}</p>\n</article>`;
    }).join('');
    return '<h2>가까운 공영주차장</h2>' +
      `<p class="lede">이 충전소 ${region.nearby_m}m 안에 있는 공영주차장입니다. ` +
      `주차하면서 충전할 수 있는 곳은 '주차하면서 충전 가능'으로 표시한 곳입니다.</p>` +
      `<div class="list">${rows}</div>`;
  }
  if (region.pk) {
    return '<h2>가까운 공영주차장</h2>' +
      '<p class="lede">이 충전소 근처 공영주차장은 ' +
      `<a href="${esc(rel(path, region.pk))}">${esc(region.name)} 공영주차장 목록</a>에서 확인하세요.</p>`;
  }
  return '';
}

/* build_site.py 의 jsonld_breadcrumb() 과 같은 BreadcrumbList. */
function breadcrumbJsonld(region, st, path) {
  const items = [
    ['홈', '/'],
    ['전기차 충전소', '/ev/'],
    [region.prov, `/ev/${region.pslug}/`],
    [region.name, `/ev/${region.pslug}/${region.slug}/`],
    [st.nm, ''],
  ];
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map(([name, target], i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name,
      item: region.base + (target || path),
    })),
  };
}

function renderDetail(template, region, st, path) {
  const addr = st.addr + (st.ad ? ` ${st.ad}` : '');
  const updSuffix = st.cf ? ` (상태 확인 ${st.cf})` : ' (상태 확인 시각 미확인)';
  return template
    .replaceAll('{{PSLUG}}', region.pslug)
    .replaceAll('{{SLUG}}', region.slug)
    .replaceAll('{{ID}}', st.id)
    .replaceAll('{{STATION_NAME}}', esc(st.nm))
    .replaceAll('{{PROV}}', esc(region.prov))
    .replaceAll('{{REGION_NAME}}', esc(region.name))
    .replaceAll('{{ADDR}}', esc(addr))
    .replaceAll('{{F}}', String(st.f))
    .replaceAll('{{S}}', String(st.s))
    .replaceAll('{{A_TEXT}}', availDesc(st))
    .replaceAll('{{UPD_SUFFIX}}', esc(updSuffix))
    .replaceAll('{{BADGES}}', badges(st))
    .replaceAll('{{META_ITEMS}}', metaItems(st))
    .replaceAll('{{FEE_LINE}}', feeLine(st))
    .replaceAll('{{KAKAO}}', esc(st.kakao))
    .replaceAll('{{NAVER}}', esc(st.naver))
    .replaceAll('{{CHARGER_BLOCK}}', chargerBlock(st))
    .replaceAll('{{LOTS_BLOCK}}', lotsBlock(region, st, path))
    .replace('"{{JSONLD_BREADCRUMB}}"', JSON.stringify(breadcrumbJsonld(region, st, path)));
}

async function notFound(env, url) {
  const res = await env.ASSETS.fetch(new Request(new URL('/404.html', url)));
  const body = await res.text();
  return new Response(body, {
    status: 404,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': NOT_FOUND_CACHE,
    },
  });
}

export async function onRequest(context) {
  const { request, env, params } = context;
  const url = new URL(request.url);
  const { pslug, slug, id } = params;

  // ④ 말미 슬래시 정규화 — 슬래시 없는 요청은 슬래시 있는 URL로 301.
  if (!url.pathname.endsWith('/')) {
    const dest = new URL(url);
    dest.pathname += '/';
    return Response.redirect(dest.toString(), 301);
  }

  // ① 숫자 id — 지역 목록 페이지네이션이므로 정적 자산을 그대로 반환한다.
  if (/^\d+$/.test(id)) {
    return env.ASSETS.fetch(request);
  }

  const regionRes = await env.ASSETS.fetch(
    new Request(new URL(`/assets/ev-detail/${pslug}-${slug}.json`, url)),
  );
  if (!regionRes.ok) return notFound(env, url);
  const region = await regionRes.json();
  const st = region.stations.find((s) => s.id === id);
  // ② 상세 대상(d=1)이 아니면 상세 페이지가 없으므로 404.
  if (!st || !st.d) return notFound(env, url);

  const tplRes = await env.ASSETS.fetch(
    new Request(new URL('/assets/ev-detail-template.html', url)),
  );
  if (!tplRes.ok) {
    return new Response('상세 페이지를 불러올 수 없습니다.', { status: 500 });
  }
  const html = renderDetail(await tplRes.text(), region, st, url.pathname);
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': CACHE,
    },
  });
}
