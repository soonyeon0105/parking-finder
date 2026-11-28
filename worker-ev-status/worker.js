/* 주차장 전기차 충전소 '상태 전용' 응답 Worker (2026-11-28).
 *
 * 왜 Worker + D1 인가:
 *  - 상태는 시간마다 바뀌지만, 바뀔 때마다 git push 로 Pages 전체를 다시
 *    배포하면 무료 플랜의 월 빌드 500회를 넘긴다(시간당 = 월 약 720회).
 *    그래서 상태만 이 Worker 가 D1에서 읽어 내보내고, 시간당 파이프라인
 *    (refresh_ev_status.py --publish)은 D1 행만 갈아끼운다 — Pages 배포는
 *    일어나지 않는다.
 *  - KV는 이 계정 토큰에 권한이 없고(401), 무료 쓰기 한도(일 1,000건)도
 *    시간당 약 250건 갱신을 감당하지 못한다. D1 무료는 일 쓰기 100,000건.
 *
 * 경로:
 *   GET /ev-status-summary.json          → files.path = 'summary'
 *   GET /ev-status/{pslug}-{slug}.json   → files.path = '{pslug}-{slug}'
 * 본문 형식은 scripts/ev_status.py 가 만드는 것과 같다.
 * EV 페이지(parking.9welfare.com)에서 교차 출처로 읽으므로 CORS를 연다.
 * 캐시는 120초만 — 상태가 시간 단위로 바뀌는 값이라 길게 잡지 않는다.
 */

const JSON_HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  'Access-Control-Allow-Origin': '*',
  'Cache-Control': 'public, max-age=120',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let key = null;
    if (url.pathname === '/ev-status-summary.json') {
      key = 'summary';
    } else {
      const m = url.pathname.match(/^\/ev-status\/([a-z0-9-]+)\.json$/);
      if (m) key = m[1];
    }
    if (!key) {
      return new Response('not found', { status: 404 });
    }
    const row = await env.DB
      .prepare('SELECT body FROM files WHERE path = ?')
      .bind(key)
      .first();
    if (!row) {
      return new Response('not found', { status: 404, headers: JSON_HEADERS });
    }
    return new Response(row.body, { headers: JSON_HEADERS });
  },
};
