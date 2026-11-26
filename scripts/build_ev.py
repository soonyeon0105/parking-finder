#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전기차 충전소 페이지 생성 — /ev/ 아래 지역별 충전소 목록(보조 위치).

중심은 주차+충전 결합(주차장 상세의 근처 충전소 블록·목록의 '전기차 충전 가능'
필터 — build_site.py)이고, 이 스크립트의 지역 목록은 충전소 단독 확인용으로
간소하게 만든다. build_site.py 를 먼저 실행해 dist/ 가 만들어진 뒤에 실행하고,
만든 주소는 dist/sitemap.xml 에 덧붙인다.

입력: data/ev_stations.json (prepare_ev.py 산출)
실행: python3 scripts/build_site.py --base https://parking.9welfare.com
      python3 scripts/prepare_ev.py
      python3 scripts/build_ev.py --base https://parking.9welfare.com
      python3 scripts/qa_check.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import build_site as bs

PER_PAGE = 60


def station_card(s, path) -> str:
    kakao, naver = bs.ev_station_links(s["nm"], s.get("lat"), s.get("lng"), s.get("addr"))
    total = s["f"] + s["s"]
    badges = [f'<span class="badge kind">충전소</span>']
    if s["f"]:
        badges.append(f'<span class="badge">급속 {s["f"]}기</span>')
    if s["s"]:
        badges.append(f'<span class="badge">완속 {s["s"]}기</span>')
    if s["a"]:
        badges.append(f'<span class="badge ev">지금 충전 가능 {s["a"]}대</span>')
    meta = []
    if s.get("op"):
        meta.append(f'<li><b>운영</b> {bs.esc(s["op"])}</li>')
    if s.get("ut"):
        meta.append(f'<li><b>이용시간</b> {bs.esc(s["ut"])}</li>')
    if s.get("pf") == "Y":
        meta.append('<li><b>주차</b> 무료</li>')
    elif s.get("pf") == "N":
        meta.append('<li><b>주차</b> 유료·확인 필요</li>')
    if s.get("call"):
        meta.append(f'<li><b>문의</b> <a href="tel:{bs.esc(s["call"])}">{bs.esc(s["call"])}</a></li>')
    rows = "".join(
        f'<tr><td>{bs.esc(r[0])}번</td><td>{bs.esc(r[1])}</td>'
        f'<td class="num">{bs.esc(r[2] + "kW") if r[2] else "-"}</td><td>{bs.esc(r[3])}</td></tr>'
        for r in s["ch"])
    detail = (f'<details class="ev-detail"><summary>충전기 {total}기 보기</summary>'
              f'<table class="data">\n<thead><tr><th>번호</th><th>종류</th>'
              f'<th class="num">출력</th><th>상태</th></tr></thead>\n'
              f'<tbody>{rows}</tbody>\n</table></details>') if rows else ""
    extra = ""
    if s.get("lim"):
        extra += f'<p class="note-line">이용 제한: {bs.esc(s["lim"])}</p>'
    if s.get("note"):
        extra += f'<p class="note-line">안내: {bs.esc(s["note"])}</p>'
    addr = s["addr"] + (f' {s["ad"]}' if s.get("ad") else "")
    return f"""<article class="card ev-card" id="st-{bs.esc(s['id'])}">
  <div class="lot-head">
    <h3>{bs.esc(s['nm'])}</h3>
    <div class="badges">{''.join(badges)}</div>
  </div>
  <p class="addr">{bs.esc(addr)}</p>
  <ul class="meta">{''.join(meta)}</ul>
  <p class="fee-line">지금 충전 가능 {s['a']}대 · 충전 중 {s['c']}대 · 점검·운영중지 {s['dn']}대 · 상태 미확인 {s['un']}대
  <span class="ev-upd">(상태 확인 {bs.esc(s['upd'])})</span></p>
  {detail}{extra}
  <div class="actions">
    <a class="btn solid" href="{bs.esc(kakao)}" target="_blank" rel="nofollow noopener">카카오맵</a>
    <a class="btn" href="{bs.esc(naver)}" target="_blank" rel="nofollow noopener">네이버지도</a>
  </div>
</article>"""


def pager(base_path, page, n_pages, cur_path) -> str:
    if n_pages <= 1:
        return ""

    def url(n):
        target = base_path if n == 1 else f"{base_path}{n}/"
        return bs.rel(cur_path, target)

    nums = sorted({1, n_pages, page - 1, page, page + 1} & set(range(1, n_pages + 1)))
    parts = []
    if page > 1:
        parts.append(f'<a href="{url(page - 1)}">← 이전</a>')
    last = 0
    for n in nums:
        if last and n > last + 1:
            parts.append('<span>…</span>')
        parts.append(f'<span class="on">{n}</span>' if n == page else f'<a href="{url(n)}">{n}</a>')
        last = n
    if page < n_pages:
        parts.append(f'<a href="{url(page + 1)}">다음 →</a>')
    return f'<nav class="ev-pager" aria-label="충전소 목록 페이지">{"".join(parts)}</nav>'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=bs.SITE_BASE)
    args = ap.parse_args()
    bs.SITE_BASE = args.base.rstrip("/")

    site = bs.load_site()
    bs.SITE_CITIES = site["cities"]
    bs.PROVINCE_ORDER = bs.province_order(site)
    bs.HOLIDAYS = bs.load_holidays()
    bs.GA_MEASUREMENT_ID = (site.get("ga_measurement_id") or "").strip()
    bs.ADSENSE = {"client": "", "slot_top": "", "slot_inline": "", "enabled": False,
                  **(site.get("adsense") or {})}
    bs.BUILD_TS = site["meta"]["generated_at"]
    bs.SNAPSHOT_TS = site["meta"].get("snapshot_at") or bs.BUILD_TS

    ev = json.loads((BASE / "data" / "ev_stations.json").read_text(encoding="utf-8"))
    meta = ev["meta"]
    regions = ev["regions"]

    # 지역별 '충전 가능한 공영주차장' 수 — 주차 페이지와 서로 잇는 핵심 숫자.
    onsite_by_city = {}
    try:
        nearby = json.loads((BASE / "data" / "ev_nearby.json").read_text(encoding="utf-8"))
        lot_city = {l["id"]: l.get("city") for l in site["lots"]}
        lot_prov = {l["id"]: l.get("province") for l in site["lots"]}
        for lot_id, e in nearby["lots"].items():
            if e.get("on"):
                key = (lot_prov.get(lot_id), lot_city.get(lot_id))
                onsite_by_city[key] = onsite_by_city.get(key, 0) + 1
    except (OSError, json.JSONDecodeError):
        onsite_by_city = {}

    pages = []  # (path, html)

    # ---------------- 전국 허브 /ev/
    prov_rows = {}
    for r in regions:
        prov_rows.setdefault((r["prov"], r["pslug"]), []).append(r)
    prov_cards = []
    for prov in bs.PROVINCE_ORDER:
        regs = next((v for (p, _), v in prov_rows.items() if p == prov), None)
        if not regs:
            continue
        pslug = regs[0]["pslug"]
        n_st = sum(len(r["stations"]) for r in regs)
        prov_cards.append(f'''<a class="link-card" href="{bs.rel('/ev/', f'/ev/{pslug}/')}">
  <span class="t">{bs.esc(prov)}<span class="go">충전소 {n_st:,}곳 →</span></span>
  <span class="d">{len(regs)}개 시·군·구 · 전기차 충전소 목록</span>
</a>''')
    body = f"""
<h1>전기차 충전소 찾기</h1>
<p class="lede">전국 전기차 충전소 {meta['n_stations']:,}곳 · 충전기 {meta['n_chargers']:,}기를 지역별로 정리했습니다.
충전소 위치와 지금 충전할 수 있는지는 내비·충전 앱이 더 빠릅니다. 이 사이트에서는
<b>주차하면서 충전할 수 있는 공영주차장</b>을 함께 확인할 수 있습니다 — 공영주차장
{meta['n_lots_onsite']:,}곳은 주차장 {meta['onsite_m']}m 안에 충전소가 있습니다.</p>

<h2>지역 선택</h2>
<div class="grid-2">{''.join(prov_cards)}</div>

<div class="note-box" style="margin-top:14px">
  <p><b>주차+충전 한 번에 확인하기</b> — 공영주차장 목록에서 '전기차 충전 가능' 필터를 켜면
  {meta['onsite_m']}m 안에 충전소가 있는 주차장만 골라 볼 수 있고, 주차장 상세 페이지에서는
  가까운 충전소와 거리·충전 가능 대수를 함께 보여 줍니다.</p>
  <div class="actions" style="margin-top:10px">
    <a class="btn" href="{bs.rel('/ev/', '/')}">공영주차장 요금계산기로 가기 →</a>
  </div>
</div>

<h2>데이터</h2>
<p class="lede">한국환경공단 전기자동차 충전소 정보(공공데이터포털)를 {bs.esc(meta['inv_at'])}에 수집해 정리했습니다.
'지금 충전 가능' 대수는 마지막으로 확인된 충전기 상태 기준이라 실제와 다를 수 있고,
실시간 정보가 필요하면 충전소 운영기관 앱이나 내비를 확인하세요.</p>
"""
    pages.append(("/ev/", bs.layout(
        title="전기차 충전소 찾기 — 지역별 충전소와 충전 가능한 공영주차장 | " + bs.SITE_NAME,
        description="전국 전기차 충전소를 지역별로 찾고, 주차하면서 충전할 수 있는 공영주차장까지 함께 확인하세요.",
        path="/ev/", body=body, crumbs=[("홈", "/"), ("전기차 충전소", "")],
        nav_active="ev", city=None,
        jsonld=[bs.jsonld_breadcrumb([("홈", "/"), ("전기차 충전소", "")], "/ev/"),
                {"@context": "https://schema.org", "@type": "ItemList",
                 "name": "시·도별 전기차 충전소", "numberOfItems": len(prov_cards),
                 "itemListElement": [
                     {"@type": "ListItem", "position": i + 1, "name": prov,
                      "url": bs.SITE_BASE + f"/ev/{regs[0]['pslug']}/"}
                     for i, (prov, regs) in enumerate(
                         [(p, next(v for (pp, _), v in prov_rows.items() if pp == p))
                          for p in bs.PROVINCE_ORDER if any(pp == p for (pp, _) in prov_rows)])]}])))

    # ---------------- 시·도 /ev/{pslug}/
    for (prov, pslug), regs in sorted(prov_rows.items()):
        path = f"/ev/{pslug}/"
        cards = []
        for r in sorted(regs, key=lambda x: x["name"]):
            n_st = len(r["stations"])
            cards.append(f'''<a class="link-card" href="{bs.rel(path, f'/ev/{pslug}/{r["slug"]}/')}">
  <span class="t">{bs.esc(r['name'])}<span class="go">충전소 {n_st:,}곳 →</span></span>
  <span class="d">{bs.esc(prov)} · 전기차 충전소 목록</span>
</a>''')
        rows = "".join(
            f'<tr><td><a href="{bs.rel(path, f"/ev/{pslug}/{r["slug"]}/")}">{bs.esc(r["name"])}</a></td>'
            f'<td class="num">{len(r["stations"]):,}곳</td>'
            f'<td class="num">{sum(s["f"] for s in r["stations"]):,}기</td>'
            f'<td class="num">{sum(s["s"] for s in r["stations"]):,}기</td>'
            f'<td class="num">{sum(1 for s in r["stations"] if s["a"]):,}곳</td></tr>'
            for r in sorted(regs, key=lambda x: x["name"]))
        body = f"""
<h1>{bs.esc(prov)} 전기차 충전소</h1>
<p class="lede">{bs.esc(prov)}의 전기차 충전소를 시·군·구별로 정리했습니다.
지역을 고르면 충전소 목록과 지금 충전 가능한 대수를 확인할 수 있습니다.</p>
<div class="grid-2">{''.join(cards)}</div>
<h2>시·군·구별 충전소 수</h2>
<table class="data">
<thead><tr><th>시·군·구</th><th class="num">충전소</th><th class="num">급속</th><th class="num">완속</th><th class="num">지금 충전 가능 있는 곳</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<p style="margin-top:16px"><a class="btn" href="{bs.rel(path, f'/parking/{pslug}/')}">← {bs.esc(prov)} 공영주차장 보기</a></p>
"""
        pages.append((path, bs.layout(
            title=f"{prov} 전기차 충전소 | {bs.SITE_NAME}",
            description=f"{prov} 전기차 충전소를 시·군·구별로 찾으세요. 급속·완속 대수와 지금 충전 가능한 대수를 확인할 수 있습니다.",
            path=path, body=body,
            crumbs=[("홈", "/"), ("전기차 충전소", "/ev/"), (prov, "")],
            nav_active="ev", city=None,
            jsonld=[bs.jsonld_breadcrumb([("홈", "/"), ("전기차 충전소", "/ev/"), (prov, "")], path)])))

    # ---------------- 시·군·구 /ev/{pslug}/{slug}/(+페이지)
    for r in regions:
        stations = r["stations"]
        total = len(stations)
        n_pages = math.ceil(total / PER_PAGE)
        base_path = f"/ev/{r['pslug']}/{r['slug']}/"
        n_fast = sum(s["f"] for s in stations)
        n_slow = sum(s["s"] for s in stations)
        n_avail_st = sum(1 for s in stations if s["a"])
        onsite_n = onsite_by_city.get((r["prov"], None), 0)
        # 주차장 도시 이름은 광역시에서 '부산 중구'처럼 접두가 붙어 있어 이름만으로 대조한다.
        if not onsite_n:
            for (pv, ct), n in onsite_by_city.items():
                if ct and (ct == r["name"] or ct.endswith(" " + r["name"])):
                    onsite_n += n
        for page in range(1, n_pages + 1):
            chunk = stations[(page - 1) * PER_PAGE: page * PER_PAGE]
            path = base_path if page == 1 else f"{base_path}{page}/"
            park_link = ""
            if r["pk"]:
                park_link = (f'<p style="margin-top:16px"><a class="btn" href="{bs.rel(path, r["pk"])}">'
                             f'{bs.esc(r["name"])} 공영주차장 요금·목록 보기</a></p>')
            head = ""
            if page > 1:
                _from = (page - 1) * PER_PAGE + 1
                head = f"""
<h1>{bs.esc(r['name'])} 전기차 충전소</h1>
<p class="lede">{bs.esc(r['prov'])} {bs.esc(r['name'])}의 전기차 충전소 {total:,}곳 중 {_from}~{min(page * PER_PAGE, total)}번째 충전소입니다. 충전소 정보는 {bs.esc(meta['inv_at'])} 수집 기준입니다.</p>
"""
            if page == 1:
                onsite_line = (f"이 지역 공영주차장 중 {onsite_n}곳은 {meta['onsite_m']}m 안에 충전소가 있어 "
                               "주차하면서 충전할 수 있습니다. ") if onsite_n else ""
                head = f"""
<h1>{bs.esc(r['name'])} 전기차 충전소</h1>
<p class="lede">{bs.esc(r['prov'])} {bs.esc(r['name'])}의 전기차 충전소 {total:,}곳입니다.
급속 {n_fast:,}기 · 완속 {n_slow:,}기가 있고, 지금 충전 가능한 충전소가 있는 곳은 {n_avail_st:,}곳입니다.
{onsite_line}충전소 정보는 {bs.esc(meta['inv_at'])} 수집 기준입니다.</p>
{park_link}
"""
            cards = "".join(station_card(s, path) for s in chunk)
            body = (head + f'<div class="list">{"".join(cards)}</div>'
                    + pager(base_path, page, n_pages, path)
                    + (park_link if page == n_pages and page != 1 else "")
                    + f'<p class="updated">\'지금 충전 가능\'은 마지막으로 확인된 충전기 상태'
                      f'(충전소별 상태 확인 시각 표기) 기준이라 실제와 다를 수 있습니다. '
                      f'출처: 한국환경공단 전기자동차 충전소 정보.</p>')
            crumbs = [("홈", "/"), ("전기차 충전소", "/ev/"),
                      (r["prov"], f"/ev/{r['pslug']}/"), (r["name"], "")]
            pages.append((path, bs.layout(
                title=f"{r['name']} 전기차 충전소 {total:,}곳 | {bs.SITE_NAME}",
                description=f"{r['prov']} {r['name']} 전기차 충전소 {total:,}곳의 위치·운영기관·급속/완속 대수와 지금 충전 가능한 대수를 확인하세요.",
                path=path, body=body, crumbs=crumbs, nav_active="ev", city=None,
                jsonld=[bs.jsonld_breadcrumb(crumbs, path),
                        {"@context": "https://schema.org", "@type": "ItemList",
                         "name": f"{r['name']} 전기차 충전소",
                         "numberOfItems": len(chunk),
                         "itemListElement": [
                             {"@type": "ListItem", "position": i + 1, "name": s["nm"],
                              "url": bs.SITE_BASE + path + f"#st-{s['id']}"}
                             for i, s in enumerate(chunk)]}])))

    dist = bs.DIST
    for path, html_text in pages:
        out = dist / path.strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")

    # 사이트맵에 EV 주소 덧붙이기 (build_site.py 가 만든 sitemap.xml 의 </urlset> 앞).
    sm_path = dist / "sitemap.xml"
    sm = sm_path.read_text(encoding="utf-8")
    lastmod = (meta.get("inv_collected") or "")[:10]
    lastmod_tag = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    urls = "\n".join(
        f"  <url><loc>{bs.SITE_BASE}{p}</loc>{lastmod_tag}<changefreq>weekly</changefreq>"
        f"<priority>{'0.9' if p == '/ev/' else '0.7'}</priority></url>" for p, _ in pages)
    sm_path.write_text(sm.replace("</urlset>", urls + "\n</urlset>"), encoding="utf-8")
    print(f"전기차 충전소 페이지 생성 완료: {len(pages)}페이지 (충전소 {meta['n_stations']:,}곳)")


if __name__ == "__main__":
    main()
