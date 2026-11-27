#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전기차 충전소 페이지 생성 — /ev/ 아래 지역별 충전소 목록(보조 위치).

중심은 주차+충전 결합(주차장 상세의 근처 충전소 블록·목록의 '전기차 충전 가능'
필터 — build_site.py)이고, 이 스크립트의 지역 목록은 충전소 단독 확인용으로
간소하게 만든다. build_site.py 를 먼저 실행해 dist/ 가 만들어진 뒤에 실행하고,
만든 주소는 dist/sitemap.xml 에 덧붙인다.

충전소 단독 상세 페이지(/ev/{도}/{구}/{충전소 id}/)는 정적 파일로 만들지 않는다
(PR #154: 23,456개 정적 생성 → Pages 배포 파일 상한 20,000개 초과로 배포 실패).
대신 지역별 JSON(dist/assets/ev-detail/{pslug}-{slug}.json, 충전소 전량)과
템플릿 1개(dist/assets/ev-detail-template.html)를 만들고, Pages Function
(functions/ev/[pslug]/[slug]/[id].js)이 요청 시점에 서버에서 완성된 HTML을
내보낸다(안 A — 설계 #948 §4). URL·서버 HTML·OG·사이트맵은 정적 때와 같다.

입력: data/ev_stations.json (prepare_ev.py 산출)
실행: python3 scripts/build_site.py --base https://parking.9welfare.com
      python3 scripts/prepare_ev.py
      python3 scripts/build_ev.py --base https://parking.9welfare.com
      python3 scripts/qa_check.py
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
import build_site as bs

PER_PAGE = 60

# P0-3 데이터 품질 가드 — 좌표-주소 불일치 47곳 (검수 #840·#845 후속 점검).
# 이 충전소의 상세 페이지에서는 '가까운 공영주차장' 블록을 숨긴다 (본문·충전기
# 정보는 그대로). 원본 수정이 끝나면 data/ev_coord_mismatch_47.json 에서
# 제거해 블록을 복원한다. Functions JS는 JSON rec의 "mm" 플래그로 본다.
_MISMATCH_FILE = BASE / "data" / "ev_coord_mismatch_47.json"
try:
    MISMATCH_47 = frozenset(json.loads(_MISMATCH_FILE.read_text(encoding="utf-8"))["ids"])
except (OSError, ValueError, KeyError):
    MISMATCH_47 = frozenset()

# 상세 페이지 템플릿 토큰 — functions/ev/[pslug]/[slug]/[id].js 가 같은
# 목록으로 채운다. 토큰을 추가·삭제·이름 변경하면 함수도 함께 고칠 것.
DETAIL_TOKENS = ("{{PSLUG}}", "{{SLUG}}", "{{ID}}", "{{STATION_NAME}}",
                 "{{PROV}}", "{{REGION_NAME}}", "{{ADDR}}", "{{F}}", "{{S}}",
                 "{{A_TEXT}}", "{{UPD_SUFFIX}}", "{{BADGES}}", "{{META_ITEMS}}",
                 "{{FEE_LINE}}", "{{KAKAO}}", "{{NAVER}}",
                 "{{CHARGER_BLOCK}}", "{{LOTS_BLOCK}}",
                 "{{JSONLD_BREADCRUMB}}")


def upd_span(s) -> str:
    """상태 확인 시각 표기 — 확인 시각('cf', 상태를 확인한 스냅샷 시각) 기준.

    statUpdDt(상태 변경 시각)가 아니라 우리가 상태를 확인한 시각을 적는다.
    변경이 없는 충전기는 statUpdDt 가 몇 달 전일 수 있는데, 그건 방치가
    아니라 상태가 안 바뀐 것뿐이라 '오래됨'으로 단정하지 않는다(2026-11-27).
    없으면 빈 괄호가 되지 않게 '미확인'으로 둔다.
    """
    if s.get("cf"):
        return f'<span class="ev-upd">(상태 확인 {bs.esc(s["cf"])})</span>'
    return '<span class="ev-upd">(상태 확인 시각 미확인)</span>'


def avail_unknown(s) -> bool:
    """충전 가능 대수가 0인데 충전기 전부가 '상태 미확인' — 0대가 아니라 모르는 상태."""
    total = s["f"] + s["s"]
    return total > 0 and s["a"] == 0 and s["un"] == total


def avail_stale(s) -> bool:
    """P0-3: 상태 확인 시각(cf)이 24시간을 넘었는지 — build_site.ev_cf_stale과 같은 기준."""
    return bs.ev_cf_stale(s.get("cf"))


def avail_text(s) -> str:
    """fee-line 첫머리 — 모르면 '상태 모름'으로 적는다(검수 #992: 0대로 보이면 고장으로 오해).
    P0-3: 확인이 24시간을 넘었으면 '지금 충전 가능'을 쓰지 않고 '상태 확인 중'으로 적는다
    (upd_span에 이미 '(상태 확인 …)'이 있어 시각을 두 번 적지 않는다)."""
    if avail_stale(s):
        return "상태 확인 중"
    return "상태 모름" if avail_unknown(s) else f"지금 충전 가능 {s['a']}대"


def avail_desc(s) -> str:
    """meta 설명용 — 모르면 '충전 가능 여부 미확인', 오래됐으면 '상태 확인 중'."""
    if avail_stale(s):
        return "상태 확인 중"
    return "충전 가능 여부 미확인" if avail_unknown(s) else f"지금 충전 가능 {s['a']}대"


def station_card(s, path, detail_url=None) -> str:
    kakao, naver = bs.ev_station_links(s["nm"], s.get("lat"), s.get("lng"), s.get("addr"))
    total = s["f"] + s["s"]
    name_html = bs.esc(s['nm'])
    if detail_url:
        name_html = f'<a href="{bs.rel(path, detail_url)}">{name_html}</a>'
    badges = [f'<span class="badge kind">충전소</span>']
    if s["f"]:
        badges.append(f'<span class="badge">급속 {s["f"]}기</span>')
    if s["s"]:
        badges.append(f'<span class="badge">완속 {s["s"]}기</span>')
    if avail_stale(s):
        badges.append('<span class="badge unknown">상태 확인 중</span>')
    elif s["a"]:
        badges.append(f'<span class="badge ev">지금 충전 가능 {s["a"]}대</span>')
    elif avail_unknown(s):
        badges.append('<span class="badge unknown">상태 모름</span>')
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
    <h3>{name_html}</h3>
    <div class="badges">{''.join(badges)}</div>
  </div>
  <p class="addr">{bs.esc(addr)}</p>
  <ul class="meta">{''.join(meta)}</ul>
  <p class="fee-line">{avail_text(s)} · 충전 중 {s['c']}대 · 점검·운영중지 {s['dn']}대 · 상태 미확인 {s['un']}대
  {upd_span(s)}</p>
  {detail}{extra}
  <div class="actions">
    <a class="btn solid" href="{bs.esc(kakao)}" target="_blank" rel="nofollow noopener">카카오맵</a>
    <a class="btn" href="{bs.esc(naver)}" target="_blank" rel="nofollow noopener">네이버지도</a>
    {f'<a class="btn" href="{bs.rel(path, detail_url)}">충전소 상세 보기</a>' if detail_url else ""}
  </div>
</article>"""


def lot_link(city, lot, path) -> str:
    """가까운 주차장 링크 — 상세페이지 대상이면 상세페이지, 아니면 구·시 목록 페이지.

    구 페이지는 lot['gu']와 city['districts']의 이름으로 찾는다. 못 찾으면 시 페이지.
    """
    if city is None:
        return None
    if bs.is_detail_target(lot):
        return bs.detail_path(city, lot)
    for d in city.get("districts") or []:
        if d.get("name") == lot.get("gu"):
            return bs.district_path(city, d)
    return bs.city_path(city)


# ------------------------------------------------------------------ 충전소 상세
# 상세 페이지는 Functions 가 내보내지만, 본문 조각은 여기서 한 번만 만든다.
# 파이썬 기준본(station_detail_page)과 템플릿(station_detail_template)이 같은
# 조각 함수를 써서, 두 렌더링이 어긋나지 않게 한다.

def detail_badges(s) -> str:
    badges = ['<span class="badge kind">충전소</span>']
    if s["f"]:
        badges.append(f'<span class="badge">급속 {s["f"]}기</span>')
    if s["s"]:
        badges.append(f'<span class="badge">완속 {s["s"]}기</span>')
    if avail_stale(s):
        badges.append('<span class="badge unknown">상태 확인 중</span>')
    elif s["a"]:
        badges.append(f'<span class="badge ev">지금 충전 가능 {s["a"]}대</span>')
    elif avail_unknown(s):
        badges.append('<span class="badge unknown">상태 모름</span>')
    return "".join(badges)


def detail_meta_items(s) -> str:
    items = []
    if s.get("op"):
        items.append(f'<li><b>운영</b> {bs.esc(s["op"])}</li>')
    if s.get("ut"):
        items.append(f'<li><b>이용시간</b> {bs.esc(s["ut"])}</li>')
    if s.get("pf") == "Y":
        items.append('<li><b>주차</b> 무료</li>')
    elif s.get("pf") == "N":
        items.append('<li><b>주차</b> 유료·확인 필요</li>')
    if s.get("call"):
        items.append(f'<li><b>문의</b> <a href="tel:{bs.esc(s["call"])}">{bs.esc(s["call"])}</a></li>')
    if s.get("lim"):
        items.append(f'<li><b>이용 제한</b> {bs.esc(s["lim"])}</li>')
    if s.get("note"):
        items.append(f'<li><b>안내</b> {bs.esc(s["note"])}</li>')
    return "".join(items)


def detail_fee_line(s) -> str:
    return (f"{avail_text(s)} · 충전 중 {s['c']}대 · 점검·운영중지 {s['dn']}대 · 상태 미확인 {s['un']}대\n"
            f"  {upd_span(s)}")


def detail_charger_block(s) -> str:
    rows = "".join(
        f'<tr><td>{bs.esc(c[0])}번</td><td>{bs.esc(c[1])}</td>'
        f'<td class="num">{bs.esc(c[2] + "kW") if c[2] else "-"}</td><td>{bs.esc(c[3])}</td></tr>'
        for c in s["ch"])
    if not rows:
        return ""
    total = s["f"] + s["s"]
    # table-scroll 래퍼를 조각에 넣어 둔다 — layout() 의 _wrap_data_tables 가
    # 이미 감싼 표는 건드리지 않으므로 파이썬 기준본과 Functions 출력이 같다.
    return (f'<h2>충전기 {total}기</h2>'
            f'<div class="table-scroll"><table class="data">\n<thead><tr><th>번호</th><th>종류</th>'
            f'<th class="num">출력</th><th>상태</th></tr></thead>\n'
            f'<tbody>{rows}</tbody>\n</table></div>')


def detail_lots_block(r, path, nearby_lots, meta, station_id=None) -> str:
    """가까운 공영주차장 블록. nearby_lots: (주차장 dict, 거리m, 100m 안 여부), 거리순, 최대 5곳.

    P0-3: 좌표-주소 불일치 47곳(MISMATCH_47)은 블록을 표시하지 않는다 — 잘못된
    주차장을 안내하는 것보다 안 보여주는 것이 낫다. 본문(주소·충전기 정보)은 그대로 둔다.
    """
    if station_id in MISMATCH_47:
        return ""
    onsite_m = meta.get("onsite_m", 100)
    lot_rows = []
    for lot, d, onsite in nearby_lots:
        city = bs.city_of(lot)
        href = lot_link(city, lot, path)
        lot_addr = lot.get("addr_road") or lot.get("addr_jibun") or ""
        lot_badges = [f'<span class="badge ev">{bs.ev_dist_text(d)}</span>']
        if onsite:
            lot_badges.append('<span class="badge">주차하면서 충전 가능</span>')
        fee = lot["fee"]["type"]
        lot_rows.append(f"""<article class="card">
  <div class="lot-head">
    <h3>{f'<a href="{bs.rel(path, href)}">{bs.esc(lot["name"])}</a>' if href else bs.esc(lot["name"])}</h3>
    <div class="badges">{''.join(lot_badges)}</div>
  </div>
  <p class="addr">{bs.esc(lot_addr)}</p>
  <p class="fee-line">요금 구분 {bs.esc(fee)}</p>
</article>""")
    if lot_rows:
        return (f'<h2>가까운 공영주차장</h2>'
                f'<p class="lede">이 충전소 {meta["nearby_m"]}m 안에 있는 공영주차장입니다. '
                f'주차하면서 충전할 수 있는 곳은 {onsite_m}m 안에 있는 곳입니다.</p>'
                f'<div class="list">{"".join(lot_rows)}</div>')
    if r.get("pk"):
        return (f'<h2>가까운 공영주차장</h2>'
                f'<p class="lede">이 충전소 근처 공영주차장은 '
                f'<a href="{bs.rel(path, r["pk"])}">{bs.esc(r["name"])} 공영주차장 목록</a>에서 확인하세요.</p>')
    return ""


def station_detail_body(slots) -> str:
    """상세 페이지 본문 뼈대 — slots 는 조각 HTML(파이썬 기준본은 완성된 조각,
    템플릿은 {{토큰}})을 받는다. 뼈대는 한 곳에서만 관리한다."""
    return f"""
<h1>{slots['h1']}</h1>
<p class="lede">{slots['lede']}</p>
<article class="card ev-card">
  <div class="lot-head">
    <div class="badges">{slots['badges']}</div>
  </div>
  <p class="addr">{slots['addr']}</p>
  <ul class="meta">{slots['meta_items']}</ul>
  <p class="fee-line">{slots['fee_line']}</p>
  <div class="actions">
    <a class="btn solid" href="{slots['kakao']}" target="_blank" rel="nofollow noopener">카카오맵</a>
    <a class="btn" href="{slots['naver']}" target="_blank" rel="nofollow noopener">네이버지도</a>
  </div>
</article>
{slots['charger_block']}
{slots['lots_block']}
<p style="margin-top:16px">
  <a class="btn" href="{slots['region_url']}">← {slots['region_name']} 충전소 목록으로 돌아가기</a>
  <a class="btn" href="{slots['ev_home_url']}">전기차 충전소 찾기</a>
</p>
<p class="updated">'지금 충전 가능'은 마지막으로 확인된 충전기 상태(상태 확인 시각 표기) 기준이라
실제와 다를 수 있습니다. 출처: 한국환경공단 전기자동차 충전소 정보.</p>
"""


def station_detail_page(s, r, path, nearby_lots, meta) -> str:
    """충전소 단독 상세 페이지(/ev/{pslug}/{slug}/{id}/) — 파이썬 기준본.

    빌드에서는 이 함수를 쓰지 않는다(Functions 가 템플릿을 채워 내보낸다).
    Functions 렌더링과 같은 HTML을 내는지 대조하는 검수용으로 둔다.
    없는 값은 표시하지 않거나 '미확인'으로 둔다 — 데이터를 지어내지 않는다.
    """
    kakao, naver = bs.ev_station_links(s["nm"], s.get("lat"), s.get("lng"), s.get("addr"))
    slots = {
        "h1": bs.esc(s["nm"]),
        "lede": (f"{bs.esc(r['prov'])} {bs.esc(r['name'])}의 전기차 충전소입니다.\n"
                 f"충전소 정보는 {bs.esc(meta['inv_at'][:10])} 수집 기준입니다."),
        "badges": detail_badges(s),
        "addr": bs.esc(s["addr"] + (f' {s["ad"]}' if s.get("ad") else "")),
        "meta_items": detail_meta_items(s),
        "fee_line": detail_fee_line(s),
        "kakao": bs.esc(kakao),
        "naver": bs.esc(naver),
        "charger_block": detail_charger_block(s),
        "lots_block": detail_lots_block(r, path, nearby_lots, meta, station_id=s["id"]),
        "region_url": bs.rel(path, f"/ev/{r['pslug']}/{r['slug']}/"),
        "region_name": bs.esc(r["name"]),
        "ev_home_url": bs.rel(path, "/ev/"),
    }
    body = station_detail_body(slots)
    addr = s["addr"] + (f' {s["ad"]}' if s.get("ad") else "")
    crumbs = [("홈", "/"), ("전기차 충전소", "/ev/"),
              (r["prov"], f"/ev/{r['pslug']}/"), (r["name"], f"/ev/{r['pslug']}/{r['slug']}/"),
              (s["nm"], "")]
    return bs.layout(
        title=f"{s['nm']} 전기차 충전소 — {r['prov']} {r['name']} | {bs.SITE_NAME}",
        description=(f"{r['prov']} {r['name']} {s['nm']} — {addr}. "
                     f"급속 {s['f']}기 · 완속 {s['s']}기 · {avail_desc(s)}"
                     + (f" (상태 확인 {s['cf']})." if s.get("cf")
                        else " (상태 확인 시각 미확인).")),
        path=path, body=body, crumbs=crumbs, nav_active="ev", city=None,
        jsonld=[bs.jsonld_breadcrumb(crumbs, path)])


def station_detail_template(meta) -> str:
    """상세 페이지 템플릿 — dist/assets/ev-detail-template.html 로 쓴다.

    Functions 가 토큰을 채워 반환한다. 제목·설명·본문의 충전소별 값은 토큰으로
    두고, 껍데기(내비·푸터·폰트·측정 코드)는 빌드 시점에 그대로 박는다.
    JSON-LD는 이름에 따옴표가 들어갈 수 있어 토큰 치환이 아니라 통째로
    교체한다 — 템플릿에는 "{{JSONLD_BREADCRUMB}}" 문자열 하나만 두고,
    Functions 가 JSON.stringify 한 breadcrumb 객체로 바꾼다.
    """
    token_path = "/ev/{{PSLUG}}/{{SLUG}}/{{ID}}/"
    slots = {
        "h1": "{{STATION_NAME}}",
        "lede": ("{{PROV}} {{REGION_NAME}}의 전기차 충전소입니다.\n"
                 f"충전소 정보는 {bs.esc(meta['inv_at'][:10])} 수집 기준입니다."),
        "badges": "{{BADGES}}",
        "addr": "{{ADDR}}",
        "meta_items": "{{META_ITEMS}}",
        "fee_line": "{{FEE_LINE}}",
        "kakao": "{{KAKAO}}",
        "naver": "{{NAVER}}",
        "charger_block": "{{CHARGER_BLOCK}}",
        "lots_block": "{{LOTS_BLOCK}}",
        "region_url": bs.rel(token_path, "/ev/{{PSLUG}}/{{SLUG}}/"),
        "region_name": "{{REGION_NAME}}",
        "ev_home_url": bs.rel(token_path, "/ev/"),
    }
    body = station_detail_body(slots)
    crumbs = [("홈", "/"), ("전기차 충전소", "/ev/"),
              ("{{PROV}}", "/ev/{{PSLUG}}/"), ("{{REGION_NAME}}", "/ev/{{PSLUG}}/{{SLUG}}/"),
              ("{{STATION_NAME}}", "")]
    return bs.layout(
        title="{{STATION_NAME}} 전기차 충전소 — {{PROV}} {{REGION_NAME}} | " + bs.SITE_NAME,
        description=("{{PROV}} {{REGION_NAME}} {{STATION_NAME}} — {{ADDR}}. "
                     "급속 {{F}}기 · 완속 {{S}}기 · {{A_TEXT}}{{UPD_SUFFIX}}."),
        path=token_path, body=body, crumbs=crumbs, nav_active="ev", city=None,
        jsonld=["{{JSONLD_BREADCRUMB}}"])


def build_ev_detail_data(ev, meta, regions, nearby_lots_by_station, detail_url_by_id):
    """지역별 상세 JSON + 템플릿 1개 — dist/assets/ev-detail/ 에 쓴다.

    충전소는 지역 전량을 싣는다(설계 §4 A안 — 합계 약 57MB). 상세 대상(d=1)인
    곳만 Functions 가 페이지를 내보내고, 그 밖의 id 는 404 다. 근처 주차장
    (lots)은 상세 대상에만 싣는다(최대 5곳, 거리순). 카카오맵·네이버지도 링크는
    빌드 시점에 계산해 넣어 Functions 가 URL 인코딩을 다시 하지 않게 한다.
    """
    out_dir = bs.DIST / "assets" / "ev-detail"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):  # 지역이 줄면 옛 파일이 남지 않게 한다
        old.unlink()
    total_bytes = 0
    biggest = ("", 0)
    n_detail = 0
    onsite_m = meta.get("onsite_m", 100)
    for r in regions:
        stations = []
        for s in r["stations"]:
            kakao, naver = bs.ev_station_links(s["nm"], s.get("lat"), s.get("lng"), s.get("addr"))
            rec = {"id": s["id"], "nm": s["nm"], "addr": s["addr"], "ad": s.get("ad") or "",
                   "lat": s.get("lat"), "lng": s.get("lng"),
                   "f": s["f"], "s": s["s"], "a": s["a"], "c": s["c"],
                   "dn": s["dn"], "un": s["un"],
                   "upd": s.get("upd") or "", "cf": s.get("cf") or "",
                   "op": s.get("op") or "",
                   "ut": s.get("ut") or "", "pf": s.get("pf") or "",
                   "call": s.get("call") or "", "lim": s.get("lim") or "",
                   "note": s.get("note") or "", "ch": s.get("ch") or [],
                   "kakao": kakao, "naver": naver,
                   "d": 1 if s["id"] in detail_url_by_id else 0}
            if s["id"] in MISMATCH_47:
                # P0-3: Functions JS가 lots 블록을 숨기게 하는 플래그 (상세 대상만 의미 있음).
                rec["mm"] = 1
            if rec["d"]:
                n_detail += 1
                lots = []
                for lot, d, onsite in nearby_lots_by_station.get(s["id"], [])[:5]:
                    city = bs.city_of(lot)
                    href = lot_link(city, lot, f"/ev/{r['pslug']}/{r['slug']}/{s['id']}/")
                    lots.append({"nm": lot["name"],
                                 "addr": lot.get("addr_road") or lot.get("addr_jibun") or "",
                                 "fee": lot["fee"]["type"],
                                 "dist": bs.ev_dist_text(d),
                                 "on": 1 if onsite else 0,
                                 "href": href or ""})
                rec["lots"] = lots
            stations.append(rec)
        pack = {"prov": r["prov"], "pslug": r["pslug"], "name": r["name"], "slug": r["slug"],
                "pk": r.get("pk") or "", "inv_at": meta["inv_at"],
                "nearby_m": meta["nearby_m"], "onsite_m": onsite_m,
                "base": bs.SITE_BASE, "stations": stations}
        name = f"{r['pslug']}-{r['slug']}.json"
        text = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
        (out_dir / name).write_text(text, encoding="utf-8")
        n_bytes = len(text.encode("utf-8"))
        total_bytes += n_bytes
        if n_bytes > biggest[1]:
            biggest = (name, n_bytes)
    template = station_detail_template(meta)
    for tok in DETAIL_TOKENS:
        assert tok in template, f"템플릿에 토큰 없음: {tok}"
    (bs.DIST / "assets" / "ev-detail-template.html").write_text(template, encoding="utf-8")
    print(f"충전소 상세 JSON: {len(regions)}개 파일 · 합계 {total_bytes / 1e6:.1f}MB "
          f"(최대 {biggest[0]} {biggest[1] / 1e6:.2f}MB · 상세 대상 {n_detail:,}곳) + 템플릿 1개")
    return {"n_files": len(regions), "total_bytes": total_bytes,
            "biggest": biggest, "n_detail": n_detail}


def build_ev_nearby_index(ev, meta, detail_url_by_id=None):
    """'내 주변 충전소'(/ev/nearby/)용 브라우저 경량 인덱스 — dist/assets/ 에 쓴다.

    충전소가 10만 곳이 넘어 한 파일로 만들면 10MB를 훌쩍 넘으므로(주차장
    nearby.json 은 1.7만 곳에 2.5MB), 시·도(pslug)별 파일로 나누고 위치가 든
    파일만 받게 한다. 어느 파일이 필요한지는 경계 상자(bbox)를 담은 매니페스트로
    고른다 — assets/ev-nearby.js 가 상자를 0.15도 넓혀 대조해 시·도 경계 너머
    10km 안 충전소도 놓치지 않는다.
    행 배열: [이름, 위도(5자리), 경도(5자리), 급속, 완속, 지금 충전 가능,
              상태 확인 시각, 주소(상세 포함), 지역 인덱스, 상세 페이지 경로(없으면 "")].
    지역 경로는 파일별 'r' 배열에 한 번만 싣는다. 거리 계산은 전부 브라우저에서 하고 방문자 위치는
    서버로 보내지도 저장하지도 않는다 — 주차장 nearby.json 과 같은 원칙.
    """
    detail_url_by_id = detail_url_by_id or {}
    by_prov = {}
    for r in ev["regions"]:
        pack = by_prov.setdefault(r["pslug"], {"r": [], "rows": [], "bbox": None})
        ridx = len(pack["r"])
        pack["r"].append(f"/ev/{r['pslug']}/{r['slug']}/")
        for s in r["stations"]:
            lat, lng = round(s["lat"], 5), round(s["lng"], 5)
            addr = s["addr"] + (f' {s["ad"]}' if s.get("ad") else "")
            pack["rows"].append([s["nm"], lat, lng, s["f"], s["s"], s["a"],
                                 s.get("cf") or "", addr, ridx,
                                 detail_url_by_id.get(s["id"], "")])
            b = pack["bbox"]
            pack["bbox"] = ([min(b[0], lat), min(b[1], lng), max(b[2], lat), max(b[3], lng)]
                            if b else [lat, lng, lat, lng])
    assets = bs.DIST / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    files = {}
    total_bytes = 0
    for pslug, pack in sorted(by_prov.items()):
        name = f"ev-nearby-{pslug}.json"
        text = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
        (assets / name).write_text(text, encoding="utf-8")
        total_bytes += len(text.encode("utf-8"))
        files[pslug] = {"file": name, "bbox": pack["bbox"], "n": len(pack["rows"])}
    manifest = {"inv_at": meta.get("inv_at", ""),
                "st_at": (meta.get("st_collected") or "")[:16].replace("T", " "),
                "files": files}
    mtext = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    (assets / "ev-nearby-manifest.json").write_text(mtext, encoding="utf-8")
    biggest = max(files.items(), key=lambda kv: kv[1]["n"])
    print(f"내 주변 충전소 인덱스: {len(files)}개 파일 · 합계 {total_bytes / 1e6:.1f}MB "
          f"(최대 {biggest[0]} {biggest[1]['n']:,}곳) + 매니페스트 {len(mtext.encode('utf-8'))}B")


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
    # build_site.main()과 같은 도시별 주차장 묶음 — nav_html 지역 이동 메뉴의
    # 곳수와 푸터 지역 디렉터리의 합계가 EV 페이지에서도 주차 페이지와 같게 한다.
    # 채우지 않으면 EV 페이지는 전부 "0곳"으로 보인다(검수 #991·#995).
    for c in site["cities"]:
        city_lots = [l for l in site["lots"] if l.get("city") == c["city"]
                     and l.get("province_slug", c.get("province_slug")) == c.get("province_slug")]
        c["_lots"] = city_lots
        c["_card_lots"] = [l for l in city_lots if l.get("list_mode", "card") != bs.STREET_MODE]
        c["_street_lots"] = [l for l in city_lots if l.get("list_mode") == bs.STREET_MODE]
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
    # 역방향: 충전소 id → [(주차장 dict, 거리m, 100m 안 여부)] (거리순, 상세 페이지용).
    # 상세 페이지 범위는 '공영주차장 1km 안에 있는 충전소' — ev_nearby.json에 드는 곳.
    lots_by_id = {l["id"]: l for l in site["lots"]}
    nearby_lots_by_station = {}
    try:
        nearby = json.loads((BASE / "data" / "ev_nearby.json").read_text(encoding="utf-8"))
        lot_city = {l["id"]: l.get("city") for l in site["lots"]}
        lot_prov = {l["id"]: l.get("province") for l in site["lots"]}
        for lot_id, e in nearby["lots"].items():
            if e.get("on"):
                key = (lot_prov.get(lot_id), lot_city.get(lot_id))
                onsite_by_city[key] = onsite_by_city.get(key, 0) + 1
            lot = lots_by_id.get(lot_id)
            if not lot:
                continue
            for st in e.get("st") or []:
                nearby_lots_by_station.setdefault(st["id"], []).append(
                    (lot, st["d"], st["d"] <= nearby["meta"].get("onsite_m", 100)))
        for lst in nearby_lots_by_station.values():
            lst.sort(key=lambda t: t[1])
    except (OSError, json.JSONDecodeError):
        onsite_by_city = {}
        nearby_lots_by_station = {}
    detail_url_by_id = {}
    for r0 in regions:
        for s0 in r0["stations"]:
            if s0["id"] in nearby_lots_by_station:
                detail_url_by_id[s0["id"]] = f"/ev/{r0['pslug']}/{r0['slug']}/{s0['id']}/"
    print(f"충전소 상세 페이지 범위: {len(detail_url_by_id):,}곳 "
          f"(공영주차장 {meta['nearby_m']}m 안 · 전체 {meta['n_stations']:,}곳 중)")

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

<div class="note-box" style="margin-bottom:14px">
  <p><b>지금 있는 곳에서 가까운 충전소</b> — 위치를 허용하면 주변 10km 안의 충전소를
  거리순으로 보여 드립니다. 위치는 이 기기에서만 계산하고 서버로 보내지 않습니다.</p>
  <div class="actions" style="margin-top:10px">
    <a class="btn solid" href="{bs.rel('/ev/', '/ev/nearby/')}">내 주변 충전소 찾기 →</a>
  </div>
</div>

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

    # ---------------- 내 주변 /ev/nearby/
    nearby_path = "/ev/nearby/"
    manifest_url = f"{bs.rel(nearby_path, '/assets/ev-nearby-manifest.json')}?v={bs.asset_ver()}"
    nearby_body = f"""
<h1>내 주변 전기차 충전소</h1>
<p class="lede">지금 계신 곳에서 가까운 전기차 충전소를 거리순으로 보여 드립니다.
버튼을 누르면 10km 안에서 가까운 충전소 {20}곳을 찾고, 10km 안에 없으면
가장 가까운 충전소부터 보여 드립니다.</p>

<section class="nearby" id="ev-nearby" data-manifest-url="{bs.esc(manifest_url)}">
  <button type="button" class="btn solid nearby-btn" id="ev-nearby-btn">내 주변 충전소 찾기</button>
  <p class="nearby-note">위치는 이 기기(브라우저)에서만 계산하고 서버로 보내거나 저장하지 않아요.
  '지금 충전 가능' 대수는 충전소마다 적힌 상태 확인 시각 기준이라 실제와 다를 수 있습니다.</p>
  <p class="nearby-status" id="ev-nearby-status" role="status" aria-live="polite"></p>
  <div class="nearby-results" id="ev-nearby-results"></div>
</section>

<div class="note-box">
  <p><b>위치를 쓸 수 없을 때</b> — 지역별 목록에서 시·도 → 시·군·구 순으로 찾을 수 있어요.</p>
  <div class="actions" style="margin-top:10px">
    <a class="btn" href="{bs.rel(nearby_path, '/ev/')}">지역별 전기차 충전소 목록 →</a>
  </div>
</div>

<h2>데이터</h2>
<p class="lede">한국환경공단 전기자동차 충전소 정보(공공데이터포털)를 {bs.esc(meta['inv_at'])}에 수집해 정리했습니다.
충전소 상태는 마지막으로 확인된 시각을 함께 적었고, 실제와 다를 수 있으니
급할 때는 충전소 운영기관 앱이나 내비를 확인하세요.</p>
<script src="{bs.rel(nearby_path, '/assets/ev-nearby.js')}?v={bs.asset_ver()}" defer></script>
"""
    pages.append((nearby_path, bs.layout(
        title="내 주변 전기차 충전소 — 현재 위치에서 가까운 충전소 찾기 | " + bs.SITE_NAME,
        description="현재 위치에서 가까운 전기차 충전소를 거리순으로 찾으세요. 급속·완속 대수와 지금 충전 가능한 대수를 확인할 수 있습니다.",
        path=nearby_path, body=nearby_body,
        crumbs=[("홈", "/"), ("전기차 충전소", "/ev/"), ("내 주변 충전소", "")],
        nav_active="ev", city=None,
        jsonld=[bs.jsonld_breadcrumb([("홈", "/"), ("전기차 충전소", "/ev/"), ("내 주변 충전소", "")],
                                     nearby_path)])))

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
            cards = "".join(station_card(s, path, detail_url_by_id.get(s["id"]))
                            for s in chunk)
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
                              "url": bs.SITE_BASE + (detail_url_by_id.get(s["id"])
                                                     or path + f"#st-{s['id']}")}
                             for i, s in enumerate(chunk)]}])))

    # ---------------- 충전소 상세 — 정적 생성 없음(안 A)
    # 상세 페이지는 Functions 가 지역별 JSON + 템플릿으로 내보낸다. 정적 생성은
    # PR #154에서 배포 파일 상한(20,000개)을 초과해 실패했다. 상세 URL은
    # 사이트맵에만 싣고, 카드·목록의 상세 링크(detail_url_by_id)는 그대로 둔다.
    detail_paths = sorted(detail_url_by_id.values())
    print(f"충전소 상세 페이지: {len(detail_paths):,}개 (Functions 동적 렌더링 — 정적 파일 없음)")

    build_ev_nearby_index(ev, meta, detail_url_by_id)
    build_ev_detail_data(ev, meta, regions, nearby_lots_by_station, detail_url_by_id)

    dist = bs.DIST
    for path, html_text in pages:
        out = dist / path.strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")

    # 사이트맵에 EV 주소 덧붙이기 (build_site.py 가 만든 sitemap.xml 의 </urlset> 앞).
    # 상세 페이지는 우선순위 0.6 — 목록·허브(0.7~0.9)보다 낮게 둔다.
    # 합계 6,396 + 상세 23,456 ≈ 29,852개로 50,000개 상한 안에 든다.
    sm_path = dist / "sitemap.xml"
    sm = sm_path.read_text(encoding="utf-8")
    lastmod = (meta.get("inv_collected") or "")[:10]
    lastmod_tag = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
    detail_set = set(detail_paths)
    all_ev_paths = [p for p, _ in pages] + detail_paths
    urls = "\n".join(
        f"  <url><loc>{bs.SITE_BASE}{p}</loc>{lastmod_tag}<changefreq>weekly</changefreq>"
        f"<priority>{'0.9' if p == '/ev/' else '0.6' if p in detail_set else '0.7'}</priority></url>"
        for p in all_ev_paths)
    sm_path.write_text(sm.replace("</urlset>", urls + "\n</urlset>"), encoding="utf-8")
    print(f"전기차 충전소 페이지 생성 완료: {len(pages)}페이지 "
          f"(충전소 {meta['n_stations']:,}곳 · 상세 {len(detail_paths):,}개 Functions)")


if __name__ == "__main__":
    main()
