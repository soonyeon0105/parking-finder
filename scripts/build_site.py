#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공영주차장 파인더 수원 — 정적 사이트 생성기

data/suwon_parking.json 을 읽어 dist/ 아래에
  · 시 랜딩 / 시 허브
  · 구 허브 (계산기 + 목록)
  · 주말·공휴일 무료 개방 필터
  · 행정동 상세
페이지를 만든다. 각 페이지에 BreadcrumbList · FAQPage · ItemList JSON-LD 를 넣는다.

사용법:  python3 scripts/build_site.py [--base https://example.com]
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import statistics
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "data" / "suwon_parking.json"
DIST = BASE / "dist"
ASSETS = BASE / "assets"

SITE_NAME = "공영주차장 파인더"
SITE_BASE = "https://parking.9welfare.com"   # 배포 시 실제 도메인으로 바꾼다
BUILD_TS = ""
SNAPSHOT_TS = ""

DONG_SLUG = {
    "고색동": "goseak-dong", "곡반정동": "gokbanjeong-dong", "권선동": "gwonseon-dong",
    "대황교동": "daehwanggyo-dong", "서둔동": "seodun-dong", "장지동": "jangji-dong",
    "탑동": "tap-dong",
    "매탄동": "maetan-dong", "신동": "sin-dong", "영통동": "yeongtong-dong",
    "원천동": "woncheon-dong", "이의동": "ui-dong", "하동": "ha-dong",
    "송죽동": "songjuk-dong", "영화동": "yeonghwa-dong", "율전동": "yuljeon-dong",
    "정자동": "jeongja-dong", "파장동": "pajang-dong", "하광교동": "hagwanggyo-dong",
    "고등동": "godeung-dong", "교동": "gyo-dong", "남수동": "namsu-dong",
    "매향동": "maehyang-dong", "신풍동": "sinpung-dong", "우만2동": "uman2-dong",
    "우만동": "uman-dong", "인계동": "ingye-dong", "장안동": "jangan-dong",
    "화서동": "hwaseo-dong",
}
GU_SLUG = {"영통구": "suwon-yeongtong", "권선구": "suwon-gwonseon",
           "팔달구": "suwon-paldal", "장안구": "suwon-jangan"}
GU_ORDER = ["영통구", "권선구", "팔달구", "장안구"]
CITY_SLUG = {"수원시": "suwon"}   # 시·군 슬러그 색인 (전국 확장 시 추가; 없으면 자동 생성)
DAY_LABEL = {"weekday": "평일", "sat": "토요일", "sun": "일요일·공휴일"}


# ------------------------------------------------------- 자동 슬러그 (전국 확장)
# 국어의 로마자 표기법(문화체육관광부 고시)을 따르는 자동 슬러그 생성기.
#   · 이미 색인된 URL 은 GU_SLUG / DONG_SLUG / districts[].slug 매핑이 항상 우선하므로
#     수원시 39페이지 주소는 그대로 유지된다.
#   · 매핑에 없는 지역(다른 시·군·구·동)은 이름만으로 슬러그를 만들어 수동 딕셔너리 없이
#     같은 파이프라인에 편입할 수 있다.
#   · 음운 변화는 대표음(종성 ㄱ·ㄷ·ㅂ → k·t·p)과 ㄹ의 비음화·유음화만 반영한 간략 규칙이다.
CHO_ROM = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "",
           "j", "jj", "ch", "k", "t", "p", "h"]
JUNG_ROM = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe",
            "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
JONG_ROM = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p",
            "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]
JONG_BIEUM = {1, 2, 3, 9, 24}      # ㄱ ㄲ ㄳ ㄺ ㅋ  → ㄹ 앞에서 [ŋ]
JONG_YUEUM = {4, 8}                # ㄴ ㄹ           → ㄹ 앞/뒤에서 [l]
CHO_N, CHO_R = 2, 5

ADMIN_SUFFIX = [("대로", "daero"), ("동", "dong"), ("읍", "eup"), ("면", "myeon"), ("리", "ri"),
                ("가", "ga"), ("길", "gil"), ("구", "gu"), ("시", "si"), ("군", "gun"), ("로", "ro"), ("도", "do")]


def romanize(text: str) -> str:
    """한글 문자열을 로마자로 옮긴다(한글 음절 단위, 음운 변화 일부 반영)."""
    chars = list(str(text or ""))
    out = []
    pending_cho = None          # 앞 음절의 영향으로 바뀐 다음 초성
    for i, ch in enumerate(chars):
        code = ord(ch)
        if not (0xAC00 <= code <= 0xD7A3):
            out.append(ch)
            pending_cho = None
            continue
        s = code - 0xAC00
        cho, jung, jong = s // 588, (s % 588) // 28, s % 28
        nxt = None
        if i + 1 < len(chars) and 0xAC00 <= ord(chars[i + 1]) <= 0xD7A3:
            nxt = (ord(chars[i + 1]) - 0xAC00) // 588

        jong_rom, cho_rom = JONG_ROM[jong], CHO_ROM[cho]
        if pending_cho is not None:
            cho_rom = pending_cho
        pending_cho = None
        if nxt == CHO_R:
            if jong in JONG_BIEUM:          # 백로 → baengno
                jong_rom, pending_cho = "ng", "n"
            elif jong in JONG_YUEUM:        # 신라 → silla
                jong_rom, pending_cho = "l", "l"
        out.append(cho_rom + JUNG_ROM[jung] + jong_rom)
    return "".join(out)


def base_slug(name: str) -> str:
    """행정 접미사를 분리해 소문자·하이픈 슬러그를 만든다. 예: 정자동 → jeongja-dong"""
    n = re.sub(r"\s+", "", str(name or ""))
    suffix = ""
    for tail, roman in ADMIN_SUFFIX:
        if n.endswith(tail) and len(n) - len(tail) >= 1:
            suffix, n = roman, n[: -len(tail)]
            break
    core = re.sub(r"[^a-z0-9]+", "-", romanize(n).lower()).strip("-")
    if not core:
        core = "x"
    return f"{core}-{suffix}" if suffix else core


def city_slug(city: str) -> str:
    """시·군 슬러그. 매핑이 없으면 이름으로 생성(성남시 → seongnam)."""
    if city in CITY_SLUG:
        return CITY_SLUG[city]
    core = base_slug(city)
    for suf in ("si", "gun", "gu"):
        if core.endswith("-" + suf):
            core = core[: -(len(suf) + 1)]
    return core or "region"


def gu_slug(gu: str, city: str = "수원시") -> str:
    """구 슬러그: 기존 매핑 우선, 없으면 시 슬러그 + 로마자(영통구 → suwon-yeongtong)."""
    if gu in GU_SLUG:
        return GU_SLUG[gu]
    core = base_slug(gu)
    for suf in ("gu", "gun", "si"):
        if core.endswith("-" + suf):
            core = core[: -(len(suf) + 1)]
    cs = city_slug(city)
    return f"{cs}-{core}" if core and core != cs else cs


def dong_slug(dong: str) -> str:
    """동 슬러그: 기존 매핑 우선, 없으면 로마자 자동 생성(정자동 → jeongja-dong)."""
    if dong in DONG_SLUG:
        return DONG_SLUG[dong]
    return base_slug(dong) or "etc"


def dong_slug_map(names) -> dict:
    """한 구 안에서 슬러그 충돌을 결정적으로 푸는 매핑(정렬 순서 고정)."""
    out, used = {}, set()
    for n in sorted(names):
        slug, k = dong_slug(n), 2
        while slug in used:
            slug = f"{dong_slug(n)}-{k}"
            k += 1
        used.add(slug)
        out[n] = slug
    return out


# ------------------------------------------------------------------ utils
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def won(n) -> str:
    if n is None:
        return "—"
    return f"{int(round(n)):,}원"


def hhmm(m):
    if m is None:
        return ""
    h, mi = divmod(int(m), 60)
    return f"{h:02d}:{mi:02d}"


def price_for(lot, minutes=120, day="weekday", rate=0.0):
    """JS 계산기와 동일한 규칙 (서버 선계산용)."""
    if not lot["oper"].get(day):
        return {"state": "closed"}
    fee = lot["fee"]
    if fee["type"] == "무료" or (day != "weekday" and lot["free_days"].get(day)):
        return {"state": "free"}
    if fee["type"] != "유료" or not fee["base_min"] or fee["base_fee"] is None \
            or not fee["unit_min"] or fee["unit_fee"] is None:
        return {"state": "unknown"}
    if minutes <= fee["base_min"]:
        raw = fee["base_fee"]
    else:
        raw = fee["base_fee"] + math.ceil((minutes - fee["base_min"]) / fee["unit_min"]) * fee["unit_fee"]
    capped = False
    if fee["daily_fee"] and raw > fee["daily_fee"]:
        raw = fee["daily_fee"]
        capped = True
    return {"state": "paid", "amount": round(raw * (1 - rate)), "before": round(raw),
            "capped": capped, "discounted": rate > 0}


def hours_text(lot) -> str:
    hs = lot["hours"]
    all24 = all(hs[k]["open"] and hs[k]["24h"] for k in ("weekday", "sat", "sun"))
    if all24:
        return "24시간 운영(연중)"
    parts = []
    for k, label in (("weekday", "평일"), ("sat", "토"), ("sun", "일·공휴일")):
        h = hs[k]
        if not h["open"]:
            parts.append(f"{label} 휴무")
        elif h["24h"]:
            parts.append(f"{label} 24시간")
        else:
            parts.append(f"{label} {hhmm(h['start'])}~{hhmm(h['end'])}")
    return " · ".join(parts)


def fee_text(lot) -> str:
    f = lot["fee"]
    if f["type"] == "미상":
        return "요금 정보 없음 · 현장 확인"
    if f["type"] == "무료":
        return "무료"
    bits = [f"기본 {f['base_min']}분 {won(f['base_fee'])}"]
    if f["unit_min"] and f["unit_fee"] is not None:
        bits.append(f"추가 {f['unit_min']}분 {won(f['unit_fee'])}")
    if f["daily_fee"]:
        bits.append(f"1일권 {won(f['daily_fee'])}" + (f"({f['daily_hours']}시간)" if f["daily_hours"] else ""))
    if f["monthly"]:
        bits.append(f"월 {won(f['monthly'])}")
    return " · ".join(bits)


def addr_text(lot) -> str:
    a = lot["addr_jibun"] or lot["addr_road"]
    if a:
        return a
    dong = lot["dong"] or "수원시"
    return f"상세 주소 미제공 · {dong} 인근(지도 좌표 기준)"


def map_links(lot):
    name = lot["name"]
    lat, lng = lot["lat"], lot["lng"]
    if lat and lng:
        kakao = f"https://map.kakao.com/link/map/{quote(name)},{lat},{lng}"
        naver = f"https://map.naver.com/p?c={lng},{lat},16"
    else:
        kakao = f"https://map.kakao.com/?q={quote(name + ' 수원')}"
        naver = f"https://map.naver.com/p/search/{quote(name + ' 수원')}"
    return kakao, naver


def free_note(lot):
    """무료 개방 관련 표기 문장."""
    if lot["fee"]["type"] == "무료":
        return "원자료상 요금 구분이 '무료'입니다."
    out = []
    if lot["free_days"].get("sun"):
        out.append("일요일·공휴일 무료 개방")
    if lot["free_days"].get("sat"):
        out.append("토요일 무료 개방")
    if out:
        return " · ".join(out) + " (원자료 특기사항 기준)"
    return None


def is_free_lot(lot) -> bool:
    return lot["fee"]["type"] == "무료" or lot["free_days"]["sat"] or lot["free_days"]["sun"]


def capa_note(lot) -> str:
    """구획수(표준데이터 등록면수)와 실시간 스냅샷 총면수가 다를 때의 짧은 설명.

    두 값은 기준이 다르다. 예: 매탄4지구는 구획 60면으로 등록됐지만
    스냅샷 합계는 58면이다. 두 숫자가 한 카드에 같이 나오면 모순처럼 보이므로
    차이를 숫자로 밝힌다.
    """
    rt = lot.get("realtime") or {}
    spaces, total = lot.get("spaces") or 0, rt.get("total") or 0
    if not (spaces and total) or spaces == total:
        return ""
    return f"등록 구획 {spaces:,}면과 {abs(total - spaces):,}면 차이"


def stats_for(lots):
    paid = [l["fee"]["base_fee"] for l in lots
            if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    return {
        "n": len(lots),
        "spaces": sum(l["spaces"] or 0 for l in lots),
        "free": len([l for l in lots if is_free_lot(l)]),
        "sun_free": len([l for l in lots if l["free_days"]["sun"] or l["fee"]["type"] == "무료"]),
        "sat_free": len([l for l in lots if l["free_days"]["sat"] or l["fee"]["type"] == "무료"]),
        "avg_base": round(sum(paid) / len(paid)) if paid else None,
        "unknown_fee": len([l for l in lots if l["fee"]["type"] == "미상"]),
        "closed_sat": len([l for l in lots if not l["oper"]["sat"]]),
        "closed_sun": len([l for l in lots if not l["oper"]["sun"]]),
        "live": len([l for l in lots if l.get("realtime")]),
        "capa_gap": len([l for l in lots if capa_note(l)]),
    }


# ------------------------------------------------------------------ jsonld
def jsonld_breadcrumb(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            dict([("@type", "ListItem"), ("position", i + 1), ("name", name)]
                 + ([("item", SITE_BASE + path if path else SITE_BASE + "/")] if path is not None else []))
            for i, (name, path) in enumerate(items)
        ],
    }


def jsonld_itemlist(lots, path):
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "공영주차장 목록",
        "numberOfItems": len(lots),
        "itemListOrder": "https://schema.org/ItemListOrderAscending",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1,
             "name": lot["name"],
             "url": f"{SITE_BASE}{path}#lot-{i + 1}"}
            for i, lot in enumerate(lots)
        ],
    }


def jsonld_faq(qa, path):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qa
        ],
    }


def script_jsonld(objs):
    return "\n".join(
        '<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False) + "</script>"
        for o in objs if o
    )


# ------------------------------------------------------------------ layout
def layout(*, title, description, path, body, crumbs, jsonld, nav_active, extra_head="",
           absolute_links=False, robots="index,follow,max-image-preview:large", canonical=None):
    """공통 껍데기.

    absolute_links=True 이면 링크를 사이트 절대경로(/parking/...)로 쓴다. 404.html 처럼
    요청 주소가 그대로 유지되는 페이지는 상대경로가 어긋나므로 반드시 절대경로여야 한다.
    """
    canonical = SITE_BASE + path if canonical is None else canonical
    url = (lambda t: "/" + t.lstrip("/")) if absolute_links else (lambda t: rel(path, t))
    # canonical·og:url 은 색인하지 않는 페이지(404)에서는 비운다
    canonical_tag = f'<link rel="canonical" href="{canonical}">\n' if canonical else ""
    og_url_tag = f'<meta property="og:url" content="{canonical}">\n' if canonical else ""
    nav = "".join(
        f'<a href="{url(f"/parking/gyeonggi/{gu_slug(g)}/")}"'
        f'{" class=on" if nav_active == g else ""}>{g}</a>'
        for g in GU_ORDER
    )
    nav = f'<a href="{url("/parking/gyeonggi/suwon/")}"' + \
          (' class="on"' if nav_active == "수원시" else '') + '>수원시 전체</a>' + nav
    crumb_html = '<nav aria-label="현재 위치"><ol class="crumbs">' + "".join(
        f'<li><a href="{url(p)}">{esc(n)}</a></li>' if p else f"<li>{esc(n)}</li>"
        for n, p in crumbs) + "</ol></nav>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{canonical_tag}<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
{og_url_tag}<meta name="robots" content="{robots}">
<meta name="generator" content="parking-finder static builder">
{extra_head}
<link rel="stylesheet" href="{url('/assets/style.css')}">
{script_jsonld(jsonld)}
</head>
<body>
<header class="site-head">
  <div class="inner">
    <a class="brand" href="{url('/')}">
      <span class="dot">P</span>
      <span>{SITE_NAME}<small>공영주차장 요금·무료 개방 계산</small></span>
    </a>
    <nav class="site-nav" aria-label="지역">{nav}</nav>
  </div>
</header>
<main class="wrap">
{crumb_html}{body}
</main>
<footer class="site-foot">
  <div class="inner">
    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 <a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">전국주차장정보표준데이터</a>(기준일 2026-04-16)와 <a href="https://parking.suwonudc.co.kr/parking/parkingMap" rel="nofollow noopener" target="_blank">수원도시공사 공영주차장 안내</a>,
    <a href="https://www.data.go.kr/data/15157772/fileData.do" rel="nofollow noopener" target="_blank">경기도 수원시 공영노외주차장현황</a>(기준일 2026-08-01)을 결합해 만든 참고용 정보입니다. 실제 요금·운영시간은 현장에서 확인하세요.</p>
    <p>생성 시각 {esc(BUILD_TS)} · 페이지 내 잔여면수는 조회 시점 스냅샷입니다.</p>
    <p><a href="{url('/parking/gyeonggi/suwon/')}">수원시 전체 보기</a> · <a href="{url('/sitemap.xml')}">사이트맵</a></p>
  </div>
</footer>
<script src="{url('/assets/app.js')}" defer></script>
</body>
</html>
"""


def rel_prefix(path: str) -> str:
    """현재 페이지 깊이에 맞는 상대 루트 접두어."""
    parts = [x for x in path.strip("/").split("/") if x]
    return "../" * len(parts)


def rel(path: str, target: str) -> str:
    """사이트 절대경로(/parking/...)를 현재 페이지 기준 상대경로로."""
    t = target.lstrip("/")
    return rel_prefix(path) + t if t else (rel_prefix(path) or "./")


# ------------------------------------------------------------------ pieces
def ad_slot(kind="inline"):
    return ('<div class="ad-slot" role="complementary" aria-label="광고">'
            '<span class="ad-label">Sponsored · 광고 영역(테스트)</span>'
            '<div class="ad-box"><span>Google AdSense 광고 자리</span>'
            '<span>모바일 320×100 / 데스크톱 728×90 · 실제 게재 시 이 자리표시자를 교체</span></div>'
            '</div>')


def stat_cards(lots, *, extra_free_label=""):
    s = stats_for(lots)
    return f"""<div class="stats">
  <div class="stat"><span class="k">등록 주차장</span><span class="v">{s['n']}<small>곳</small></span></div>
  <div class="stat free"><span class="k">{esc(extra_free_label or '무료·주말무료')}</span><span class="v">{s['free']}<small>곳</small></span></div>
  <div class="stat"><span class="k">평균 기본요금</span><span class="v">{won(s['avg_base']) if s['avg_base'] else '—'}</span></div>
</div>"""


def calculator(lots, default_day="weekday", default_minutes=120, path="", mode="district"):
    s = stats_for(lots)
    day_btn = "".join(
        f'<button type="button" class="seg-btn" data-day="{k}" aria-pressed="{"true" if k == default_day else "false"}">'
        f'{DAY_LABEL[k]}'
        + (f"<small>{s['sat_free']}곳 무료</small>" if k == "sat" else "")
        + (f"<small>{s['sun_free']}곳 무료</small>" if k == "sun" else "")
        + "</button>"
        for k in ("weekday", "sat", "sun")
    )
    disc_btn = "".join(
        f'<button type="button" class="seg-btn" data-rate="{r}" aria-pressed="{"true" if r == "0" else "false"}">{label}</button>'
        for r, label in (("0", "일반 차량"), ("0.5", "경차·저공해·다자녀 50%"), ("0.8", "국가유공자·장애인 80%"))
    )
    return f"""<section class="calc" aria-labelledby="calc-title">
  <h2 id="calc-title">내 주차 조건으로 바로 계산</h2>
  <p class="hint">요일과 시간을 고르면 아래 목록의 예상 요금이 즉시 다시 계산되고 저렴한 순으로 정렬됩니다.</p>

  <div class="field">
    <span class="label">이용 요일</span>
    <div class="seg cols-3" id="day-group" role="group" aria-label="이용 요일">{day_btn}</div>
  </div>

  <div class="field">
    <div class="slider-row">
      <span class="label" style="margin:0">예상 주차 시간</span>
      <span class="time-value" id="time-label" aria-live="polite">2<span class="w">시간</span></span>
    </div>
    <input type="range" id="time-slider" min="30" max="1440" step="10" value="{default_minutes}"
           aria-label="예상 주차 시간(분)" aria-valuetext="2시간">
    <div class="ticks"><span>30분</span><span>6시간</span><span>12시간</span><span>24시간</span></div>
    <div class="chips">
      <button type="button" class="chip" data-minutes="30">30분</button>
      <button type="button" class="chip" data-minutes="60">1시간</button>
      <button type="button" class="chip" data-minutes="120">2시간</button>
      <button type="button" class="chip" data-minutes="240">4시간</button>
      <button type="button" class="chip" data-minutes="1440">하루</button>
    </div>
  </div>

  <div class="field">
    <span class="label">차량 감면(가정)</span>
    <div class="seg cols-3" id="discount-group" role="group" aria-label="차량 감면">{disc_btn}</div>
  </div>

  <div class="calc-result" id="calc-summary">계산 중…</div>
</section>"""


def lot_card(lot, idx, default_day="weekday", default_minutes=120):
    res = price_for(lot, default_minutes, default_day)
    if res["state"] == "free":
        price_html = '<span class="price free">0원</span><span class="price-note">무료 개방 (선택한 요일)</span>'
    elif res["state"] == "paid":
        extra = []
        if res["capped"]:
            extra.append("1일권 상한 적용")
        price_html = (f'<span class="price paid">{won(res["amount"])}</span>'
                      f'<span class="price-note">{esc(" · ".join(extra) or "기본요금·추가요금 기준")}</span>')
    elif res["state"] == "unknown":
        price_html = '<span class="price unknown">요금 정보 미상</span><span class="price-note">현장 확인 필요</span>'
    else:
        price_html = '<span class="price closed">휴무</span><span class="price-note">선택한 요일에 운영하지 않음</span>'

    badges = [f'<span class="badge kind">{esc(lot["kind"] or "공영")}</span>',
              f'<span class="badge">{esc(lot["ptype"] or "주차장")}</span>']
    if is_free_lot(lot):
        badges.append('<span class="badge free">무료개방</span>')
    if lot.get("realtime"):
        rt = lot["realtime"]
        badges.append(f'<span class="badge live">실시간 {rt["free"]}면</span>')
    if lot["fee"]["type"] == "미상":
        badges.append('<span class="badge unknown">요금 미확인</span>')

    addr_full = lot["addr_jibun"] or lot["addr_road"]
    show_dong = bool(lot["dong"]) and (not addr_full or lot["dong"] not in addr_full)
    meta = [f'<li><b>구획</b> {lot["spaces"]:,}면</li>' if lot["spaces"] else "",
            f'<li><b>운영</b> {esc(hours_text(lot))}</li>',
            f'<li><b>동</b> {esc(lot["dong"])}' + ("(추정)" if lot.get("dong_src", "").startswith("좌표") else "") + '</li>' if show_dong else '']
    if lot["tel"]:
        meta.append(f'<li><b>전화</b> <a href="tel:{esc(lot["tel"])}">{esc(lot["tel"])}</a></li>')

    lines = [f'<p class="fee-line">요금: {esc(fee_text(lot))}</p>']
    if lot["fee"].get("pay"):
        lines.append(f'<p class="fee-line">결제: {esc(lot["fee"]["pay"])}</p>')
    if lot.get("realtime"):
        rt = lot["realtime"]
        gap = capa_note(lot)
        lines.append(f'<p class="fee-line">실시간 잔여 {rt["free"]}면 / {rt["total"]}면 · '
                     f'{esc(SNAPSHOT_TS)} 조회' + (f' · {esc(gap)}' if gap else '') + '</p>')
    fn = free_note(lot)
    if fn:
        lines.append(f'<p class="note-line">무료: {esc(fn)}</p>')
    note = lot["note"]
    if note and not (fn and "무료개방" in note.replace(" ", "")):
        lines.append(f'<p class="note-line">특기사항: {esc(note)}</p>')
    if lot.get("capa_detail"):
        cd = lot["capa_detail"]
        bits = [f'{k} {v}면' for k, v in (("장애인", cd.get("disabled")), ("경차", cd.get("compact")),
                                          ("전기차", cd.get("elec")), ("여성우선", cd.get("woman")),
                                          ("임산부", cd.get("pregnant"))) if v]
        if bits:
            lines.append(f'<p class="fee-line">구획 구성: {esc(" · ".join(bits))}</p>')
    lines.append(f'<p class="fee-line">자료 기준일: {esc(lot["base_date"])}</p>')

    kakao, naver = map_links(lot)
    return f"""<article class="card lot{' free' if res['state'] == 'free' else ''}" data-lot="{esc(lot['id'])}" id="lot-{idx}">
  <div class="lot-head">
    <h3>{esc(lot['name'])}</h3>
    <div class="badges">{''.join(badges)}</div>
  </div>
  <p class="addr">{esc(addr_text(lot))}</p>
  <ul class="meta">{''.join(m for m in meta if m)}</ul>
  <div class="price-row">{price_html}</div>
  {''.join(lines)}
  <div class="actions">
    <a class="btn solid" href="{esc(kakao)}" target="_blank" rel="nofollow noopener">카카오맵</a>
    <a class="btn" href="{esc(naver)}" target="_blank" rel="nofollow noopener">네이버지도</a>
  </div>
</article>"""


def lot_list(lots, path, default_day="weekday", with_ad=True, default_minutes=120):
    cards = []
    for i, lot in enumerate(lots, 1):
        cards.append(lot_card(lot, i, default_day))
        if with_ad and i == 5:
            cards.append(ad_slot())
    data = json.dumps([{
        "id": l["id"], "name": l["name"],
        "oper": l["oper"], "free_days": l["free_days"],
        "fee": {k: l["fee"][k] for k in ("type", "base_min", "base_fee", "unit_min", "unit_fee",
                                         "daily_hours", "daily_fee")},
    } for l in lots], ensure_ascii=False)
    return (f'<div class="list" id="lot-list" data-day="{default_day}" data-minutes="{default_minutes}">{"".join(cards)}</div>'
            f'<script type="application/json" id="lot-data">{data.replace("</", "<\\/")}</script>')


def faq_block(qa):
    items = "".join(
        f'<details class="faq"{" open" if i == 0 else ""}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'
        for i, (q, a) in enumerate(qa))
    return f'<h2>자주 묻는 질문</h2>{items}'


# ------------------------------------------------------------------ pages
def build_district(d, lots, data):
    gu = d["name"]
    slug = d.get("slug") or gu_slug(gu, data["meta"]["region"]["city"])
    path = f"/parking/gyeonggi/{slug}/"
    s = stats_for(lots)
    lots_sorted = sorted(lots, key=lambda l: (
        0 if is_free_lot(l) else 1,
        l["fee"]["base_fee"] if l["fee"]["type"] == "유료" and l["fee"]["base_fee"] is not None else 9_999_999,
        l["name"]))

    dongs = {}
    for l in lots:
        dongs.setdefault(l["dong"] or "기타", []).append(l)
    dong_slugs = dong_slug_map(dongs)
    dong_rows = "".join(
        f'<tr><td><a href="{dong_slugs[k]}/">{esc(k)}</a></td>'
        f'<td class="num">{len(v)}</td><td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
        f'<td class="num">{sum(1 for x in v if is_free_lot(x))}</td></tr>'
        for k, v in sorted(dongs.items(), key=lambda kv: -len(kv[1])))

    # 구획수(등록면수) vs 스냅샷 총면수 차이 — 이 구에서 실제로 다른 곳만 예시로 든다
    gap = [l for l in lots if capa_note(l)]
    gap_line = (f"기준이 달라 {len(gap)}곳에서 숫자가 다르며(예: {esc(gap[0]['name'])} 구획 "
                f"{gap[0]['spaces']:,}면 ↔ 스냅샷 {gap[0]['realtime']['total']:,}면), 카드에 차이를 함께 적었습니다."
                if gap else "이 구 주차장은 두 값이 모두 일치합니다.")
    qa = [
        (f"{gu} 공영주차장은 모두 몇 곳인가요?",
         f"공공데이터포털 전국주차장정보표준데이터와 수원도시공사 안내 목록을 합쳐 {s['n']}곳이 등록되어 있습니다. "
         f"주차 구획은 총 {s['spaces']:,}면입니다."),
        (f"{gu}에서 일요일·공휴일에 무료로 주차할 수 있는 곳은?",
         (f"자료에 무료 개방으로 표기된 곳은 {s['sun_free']}곳입니다. "
          + ("'영통구청'처럼 특기사항에 '일+공휴일 무료개방'이 적힌 주차장이 여기에 해당합니다. "
             if s['sun_free'] else "현재 공식 자료에는 일요일·공휴일 무료 개방 표기가 없습니다. ")
          + "표에 없는 주차장의 현장 무료 개방 여부는 관리기관(수원도시공사 031-695-0900)에 확인하세요.")),
        (f"{gu} 공영주차장 2시간 요금은 얼마인가요?",
         (lambda prices: f"표준데이터 요금 기준 2시간 예상요금은 최저 {won(min(prices))}, "
                         f"중간값 {won(statistics.median(prices))}, 최고 {won(max(prices))}입니다. "
                         f"기본요금·추가단위요금을 그대로 계산한 값이며 1일권 요금이 더 싸면 그 값으로 제한했습니다."
          if prices else "요금 정보가 있는 주차장이 없어 계산할 수 없습니다.")(
             [price_for(l, 120, "weekday")["amount"] for l in lots
              if price_for(l, 120, "weekday")["state"] == "paid"])),
        ("이 페이지의 요금·운영시간은 최신인가요?",
         "요금·운영시간은 공공데이터포털 표준데이터(데이터 기준일 2026-04-16)를 그대로 반영했고, "
         f"실시간 잔여면수는 {SNAPSHOT_TS} 조회 값입니다. 요금 개편이나 현장 정책(최초 N분 무료 등)으로 "
         "실제와 다를 수 있으니 방문 전에 관리기관에 확인하시기 바랍니다."),
    ]

    body = f"""
<h1>{esc(gu)} 공영주차장 {s['n']}곳 · 요금 계산과 무료 개방</h1>
<p class="lede">{esc(gu)} 공영주차장의 요금·운영시간·구획수를 공공데이터로 정리했습니다.
요일과 주차 시간을 고르면 예상 요금이 바로 계산되고, 무료로 개방되는 주차장이 맨 위로 올라옵니다.</p>
<p class="updated">자료 기준일 {esc(data['meta']['sources'][0]['base_date'])} · 실시간 잔여면수 {esc(SNAPSHOT_TS)} 조회</p>
{stat_cards(lots)}
{ad_slot()}
{calculator(lots, path=path)}
<section class="note-box" style="margin-top:16px">
  <h2>요금 계산 방식</h2>
  <ul>
    <li>기본시간 이내는 기본요금, 초과분은 <b>추가단위시간마다 올림</b>해서 더합니다.</li>
    <li>1일 주차권 요금이 있으면 그 금액을 상한으로 적용합니다(예: 24시간 7,000원).</li>
    <li>차량 감면은 50%·80%를 <b>가정값</b>으로 계산합니다. 수원시 조례의 실제 감면(국가유공자·중증장애인 24시간 전액면제, 임산부·소상공인 50% 등)은 현장 확인이 필요합니다.</li>
    <li>요금 필드가 비어 있는 주차장은 0원으로 표시하지 않고 <b>‘요금 정보 미상(현장 확인)’</b>으로 구분합니다.</li>
  </ul>
</section>

<div class="toolbar">
  <h2>주차장 목록</h2>
  <span class="count">저렴한 순 자동 정렬 · 총 {s['n']}곳</span>
</div>
{lot_list(lots_sorted, path, with_ad=True)}

<h2>{esc(gu)} 동별 주차장</h2>
<table class="data">
  <thead><tr><th>동</th><th class="num">주차장</th><th class="num">구획</th><th class="num">무료</th></tr></thead>
  <tbody>{dong_rows}</tbody>
</table>
<p class="updated">동 이름을 누르면 해당 동의 주차장만 모아 볼 수 있습니다.</p>

<h2>{esc(gu)} 주말·공휴일 무료 개방</h2>
<p class="lede">주말에 무료로 열리는 곳 {s['sun_free']}곳을 따로 모았습니다.
표기가 없는 주차장은 유료로 계산되니, 주말 방문 전에 확인하세요.</p>
<p><a class="btn solid" href="weekend-free/">주말·공휴일 무료 개방 주차장 보기 →</a></p>

{faq_block(qa)}

<section class="note-box" style="margin-top:20px">
  <h2>데이터 출처와 한계</h2>
  <ul>
    <li><b>요금·운영시간·구획수</b>: 공공데이터포털 전국주차장정보표준데이터(수원시 {data['quality']['원자료_수원시행수']}행, 기준일 2026-04-16)</li>
    <li><b>실시간 잔여면수·구획 구성</b>: 수원도시공사 공영주차장 안내 지도({esc(SNAPSHOT_TS)} 조회 스냅샷)</li>
    <li><b>구획수와 스냅샷 총면수</b>: 구획수는 표준데이터 <b>등록면수</b>, 잔여면수 옆 총면수는 안내 지도 <b>스냅샷 합계</b>입니다. {gap_line}</li>
    <li><b>주소·면수 보강</b>: 경기도 수원시 공영노외주차장현황(기준일 2026-08-01)</li>
    <li>표준데이터에는 일요일 전용 운영시간 칸이 없어 <b>일요일은 공휴일 칸을 준용</b>했습니다.</li>
    <li>동 위치가 지번주소에 없는 주차장은 이름이나 좌표 최근접으로 추정했고, 카드에 ‘동 위치 추정’으로 표시했습니다.</li>
  </ul>
</section>
"""
    crumbs = [("홈", "/"), ("경기도", None), ("수원시", "/parking/gyeonggi/suwon/"),
              (f"{gu} 공영주차장", "")]
    return path, layout(
        title=f"{gu} 공영주차장 {s['n']}곳 요금·무료 개방 총정리 | {SITE_NAME}",
        description=f"{gu} 공영주차장 {s['n']}곳의 주차요금, 운영시간, 구획수, 주말·공휴일 무료 개방 정보를 "
                    f"공공데이터로 정리했습니다. 2시간 주차 예상요금과 무료 개방 여부를 바로 계산해 보세요.",
        path=path, body=body, crumbs=crumbs, nav_active=gu,
        jsonld=[jsonld_breadcrumb(crumbs),
                jsonld_itemlist(lots_sorted, path),
                jsonld_faq(qa, path)])


def build_weekend(d, lots, data):
    gu = d["name"]
    slug = d.get("slug") or gu_slug(gu, data["meta"]["region"]["city"])
    path = f"/parking/gyeonggi/{slug}/weekend-free/"
    free_lots = [l for l in lots if is_free_lot(l)]
    # 주말 대안: 일요일 기준 예상요금 낮은 순
    alt = sorted(
        [l for l in lots if price_for(l, 120, "sun")["state"] == "paid"],
        key=lambda l: price_for(l, 120, "sun")["amount"])[:8]
    s = stats_for(lots)

    qa = [
        (f"{gu}에서 주말에 무료로 주차할 수 있는 공영주차장은?",
         f"공식 자료에 무료 개방으로 표기된 곳은 {len(free_lots)}곳입니다. "
         + (", ".join(l["name"] for l in free_lots) + "입니다. " if free_lots else "")
         + "나머지 주차장은 토요일·일요일에도 요금이 부과되며, 현장 무료 개방 여부는 관리기관에 확인해야 합니다."),
        (f"{gu} 공영주차장 중 일요일에 문을 닫는 곳이 있나요?",
         f"일요일·공휴일 미운영으로 등록된 곳은 {s['closed_sun']}곳, 토요일 미운영은 {s['closed_sat']}곳입니다. "
         "토요일에 운영하지 않는 곳은 카드의 운영시간에 ‘토 휴무’로 표시됩니다."),
        ("무료 개방 표기가 없는 주차장은 주말에 얼마인가요?",
         cheapeast_sun_sentence(alt)),
    ]

    if free_lots:
        list_html = lot_list(sorted(free_lots, key=lambda l: l["name"]), path, default_day="sun")
    else:
        list_html = ('<div class="note-box">현재 자료에는 이 구에서 주말·공휴일 무료 개방으로 표기된 주차장이 없습니다. '
                     '아래는 주말 기준 예상요금이 낮은 대안 목록입니다.</div>')

    alt_rows = "".join(
        f'<tr><td><a href="../#lot-{i+1}">{esc(l["name"])}</a></td>'
        f'<td class="num">{won(price_for(l, 120, "sun")["amount"])}</td>'
        f'<td class="num">{l["spaces"] or "-"}</td></tr>'
        for i, l in enumerate(alt))

    body = f"""
<h1>{esc(gu)} 주말·공휴일 무료 개방 공영주차장</h1>
<p class="lede">토요일·일요일·공휴일에 <b>요금 없이</b> 이용할 수 있는 주차장만 모았습니다.
공공데이터 특기사항에 무료 개방이 적힌 곳만 넣었고, 표기가 없는 곳은 넣지 않았습니다.</p>
<p class="updated">자료 기준일 {esc(data['meta']['sources'][0]['base_date'])} · 총 {s['n']}곳 중 무료 개방 {len(free_lots)}곳</p>
{stat_cards(lots, extra_free_label='주말·공휴일 무료')}
{ad_slot()}
<h2>무료 개방 주차장 {len(free_lots)}곳</h2>
{list_html}

<section class="note-box" style="margin-top:18px">
  <h2>‘무료 개방’이 적게 표시되는 이유</h2>
  <ul>
    <li>수원시 공영주차장은 주말·공휴일에도 요금을 받는 곳이 대부분입니다. 조례상 감면은 경차·저공해차, 임산부, 국가유공자·장애인 등 <b>차량·사유별</b>로 적용됩니다.</li>
    <li>표준데이터에서 ‘무료 개방’은 주차장별 특기사항 칸에만 적히기 때문에, 적혀 있지 않다고 해서 반드시 유료라는 뜻은 아닙니다.</li>
    <li>현장에서 무료로 개방하는지 확인하려면 수원도시공사 주차관리팀(031-695-0900)에 문의하세요.</li>
  </ul>
</section>

<h2>주말 대안: 예상요금이 낮은 곳</h2>
<p class="lede">무료 개방 표기가 없는 주차장 중 일요일 2시간 기준 예상요금이 낮은 순서입니다.</p>
<table class="data">
  <thead><tr><th>주차장</th><th class="num">일요일 2시간</th><th class="num">구획</th></tr></thead>
  <tbody>{alt_rows}</tbody>
</table>

{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), ("수원시", "/parking/gyeonggi/suwon/"),
              (f"{gu} 공영주차장", f"/parking/gyeonggi/{slug}/"), ("주말·공휴일 무료 개방", "")]
    return path, layout(
        title=f"{gu} 주말·공휴일 무료 개방 공영주차장 {len(free_lots)}곳 | {SITE_NAME}",
        description=f"{gu}에서 토요일·일요일·공휴일에 무료로 이용할 수 있는 공영주차장 목록과 "
                    f"주말 예상요금이 낮은 대안 주차장을 공공데이터 기준으로 정리했습니다.",
        path=path, body=body, crumbs=crumbs, nav_active=gu,
        jsonld=[jsonld_breadcrumb(crumbs),
                jsonld_itemlist(free_lots or alt, path),
                jsonld_faq(qa, path)])


def cheapeast_sun_sentence(alt):
    if not alt:
        return "일요일에도 요금 정보가 있는 주차장이 없습니다. 계산기의 요일을 ‘일요일·공휴일’로 바꾸면 목록이 다시 정렬됩니다."
    first = alt[0]
    return (f"일요일 2시간 기준 예상요금이 가장 낮은 곳은 {first['name']} "
            f"{won(price_for(first, 120, 'sun')['amount'])}입니다. "
            "계산기의 요일을 ‘일요일·공휴일’로 바꾸면 전체 목록이 그날 기준으로 다시 정렬됩니다.")


def build_dong(d, dong, lots, data, slug_override=None):
    gu, slug = d["name"], d.get("slug") or gu_slug(d["name"], data["meta"]["region"]["city"])
    dslug = slug_override or dong_slug(dong)
    path = f"/parking/gyeonggi/{slug}/{dslug}/"
    s = stats_for(lots)
    lots_sorted = sorted(lots, key=lambda l: (0 if is_free_lot(l) else 1,
                                              l["fee"]["base_fee"] or 9_999_999, l["name"]))
    qa = [
        (f"{gu} {dong} 공영주차장은 몇 곳인가요?",
         f"{dong}에 등록된 공영주차장은 {s['n']}곳, 주차 구획은 총 {s['spaces']:,}면입니다. "
         f"이 가운데 무료 또는 주말 무료 개방 표기가 있는 곳은 {s['free']}곳입니다."),
        (f"{dong}에서 2시간 주차하면 얼마인가요?",
         (lambda prices: f"표준데이터 요금 기준 2시간 예상요금은 {won(min(prices))}부터 {won(max(prices))}까지입니다."
          if prices else "요금 정보가 있는 주차장이 없습니다.")
         ([price_for(l, 120)["amount"] for l in lots if price_for(l, 120)["state"] == "paid"])),
        ("야간이나 주말에도 운영하나요?",
         "주차장마다 운영시간이 다릅니다. 카드의 ‘운영’ 항목에 평일·토요일·일요일·공휴일 시간이 표시되고, "
         "24시간 운영하는 곳은 ‘24시간 운영(연중)’으로 표기했습니다."),
    ]
    body = f"""
<h1>{esc(gu)} {esc(dong)} 공영주차장 {s['n']}곳</h1>
<p class="lede">{esc(dong)}에 있는 공영주차장만 모았습니다. 요일·시간을 고르면 예상 요금이 바로 바뀝니다.</p>
<p class="updated">자료 기준일 {esc(data['meta']['sources'][0]['base_date'])}</p>
{stat_cards(lots)}
{ad_slot()}
{calculator(lots, path=path)}
<div class="toolbar"><h2>주차장 목록</h2><span class="count">총 {s['n']}곳</span></div>
{lot_list(lots_sorted, path)}
<p style="margin-top:16px"><a class="btn" href="../">← {esc(gu)} 전체 주차장 보기</a></p>
{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), ("수원시", "/parking/gyeonggi/suwon/"),
              (f"{gu} 공영주차장", f"/parking/gyeonggi/{slug}/"), (dong, "")]
    return path, layout(
        title=f"{gu} {dong} 공영주차장 {s['n']}곳 요금·운영시간 | {SITE_NAME}",
        description=f"{gu} {dong} 공영주차장 {s['n']}곳의 위치, 주차요금, 운영시간, 무료 개방 여부를 "
                    f"공공데이터로 정리했습니다. 예상 주차요금을 바로 계산해 보세요.",
        path=path, body=body, crumbs=crumbs, nav_active=gu,
        jsonld=[jsonld_breadcrumb(crumbs), jsonld_itemlist(lots_sorted, path), jsonld_faq(qa, path)])


def build_city(data, lots):
    path = "/parking/gyeonggi/suwon/"
    s = stats_for(lots)
    rows = []
    for g in GU_ORDER:
        gl = [l for l in lots if l["gu"] == g]
        gs = stats_for(gl)
        rows.append(f'<tr><td><a href="../{gu_slug(g)}/">{g}</a></td><td class="num">{gs["n"]}</td>'
                    f'<td class="num">{gs["spaces"]:,}</td><td class="num">{won(gs["avg_base"]) if gs["avg_base"] else "-"}</td>'
                    f'<td class="num">{gs["free"]}</td></tr>')
    cheap = sorted([l for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"] is not None],
                   key=lambda l: price_for(l, 120)["amount"])[:8]
    cheap_rows = "".join(
        f'<tr><td><a href="../{gu_slug(l["gu"])}/#lot-{i+1}">{esc(l["name"])}</a></td>'
        f'<td>{esc(l["gu"])}</td><td class="num">{won(price_for(l, 120)["amount"])}</td>'
        f'<td class="num">{l["spaces"] or "-"}</td></tr>' for i, l in enumerate(cheap))
    qa = [
        ("수원시 공영주차장은 모두 몇 곳인가요?",
         f"공공데이터와 수원도시공사 안내 목록을 합쳐 {s['n']}곳, 주차 구획 {s['spaces']:,}면입니다. "
         f"이 가운데 무료·주말 무료 개방 표기가 있는 곳은 {s['free']}곳입니다."),
        ("수원시에서 주말에 무료인 공영주차장은 어디인가요?",
         f"공식 자료에 일요일·공휴일 무료 개방으로 표기된 곳은 {s['sun_free']}곳입니다. "
         "구별 ‘주말·공휴일 무료 개방’ 페이지에서 확인할 수 있습니다."),
        ("평일 2시간 주차요금이 가장 싼 곳은?",
         (f"{cheap[0]['name']}({cheap[0]['gu']})이 {won(price_for(cheap[0], 120)['amount'])}으로 가장 낮습니다."
          if cheap else "요금 정보가 없습니다.")),
    ]
    body = f"""
<h1>수원시 공영주차장 {s['n']}곳 · 요금과 무료 개방 한눈에</h1>
<p class="lede">수원시 4개 구(영통·권선·팔달·장안)의 공영주차장을 공공데이터로 정리했습니다.
구를 고르면 요금 계산기와 주차장 목록으로 이동합니다.</p>
<p class="updated">자료 기준일 {esc(data['meta']['sources'][0]['base_date'])} · 실시간 잔여면수 {esc(SNAPSHOT_TS)} 조회</p>
{stat_cards(lots)}
{ad_slot()}
<h2>구별 현황</h2>
<table class="data">
  <thead><tr><th>구</th><th class="num">주차장</th><th class="num">구획</th><th class="num">평균 기본요금</th><th class="num">무료</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>

<h2>구별로 찾기</h2>
<div class="grid-2">
{''.join(f'''<a class="link-card" href="../{gu_slug(g)}/">
  <span class="t">{g} 공영주차장<span class="go">{stats_for([l for l in lots if l['gu'] == g])['n']}곳 →</span></span>
  <span class="d">요금 계산기 · 주말 무료 개방 · 동별 목록</span>
</a>''' for g in GU_ORDER)}
</div>

<h2>평일 2시간 기준 가장 저렴한 곳</h2>
<table class="data">
  <thead><tr><th>주차장</th><th>구</th><th class="num">2시간</th><th class="num">구획</th></tr></thead>
  <tbody>{cheap_rows}</tbody>
</table>
{ad_slot()}
{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), ("수원시 공영주차장", "")]
    return path, layout(
        title=f"수원시 공영주차장 {s['n']}곳 요금·무료 개방 지도 | {SITE_NAME}",
        description=f"수원시 4개 구 공영주차장 {s['n']}곳의 주차요금, 운영시간, 무료 개방 정보를 정리했습니다. "
                    f"구별 요금 계산기로 2시간·하루 주차비를 바로 확인하세요.",
        path=path, body=body, crumbs=crumbs, nav_active="수원시",
        jsonld=[jsonld_breadcrumb(crumbs), jsonld_itemlist(cheap, path), jsonld_faq(qa, path)])


def build_landing(data, lots):
    path = "/"
    s = stats_for(lots)
    cards = "".join(
        f'''<a class="link-card" href="parking/gyeonggi/{gu_slug(g)}/">
  <span class="t">{g}<span class="go">{stats_for([l for l in lots if l['gu'] == g])['n']}곳 →</span></span>
  <span class="d">주차요금 계산 · 주말 무료 개방 · 동별 목록</span>
</a>''' for g in GU_ORDER)
    body = f"""
<h1>공영주차장 파인더 — 수원시</h1>
<p class="lede">"여기 2시간 주차하면 얼마지?"를 바로 확인하는 페이지입니다.
공공데이터로 등록된 공영주차장 {s['n']}곳의 요금·운영시간·무료 개방 정보를 요일과 시간에 맞춰 계산합니다.</p>
{stat_cards(lots)}
{ad_slot()}
<h2>구 선택</h2>
<div class="grid-2">{cards}</div>
<h2>이런 걸 확인할 수 있어요</h2>
<div class="note-box">
  <ul>
    <li><b>요일별 무료 개방</b>: 평일·토요일·일요일·공휴일 중 언제 무료인지, 언제 문을 닫는지</li>
    <li><b>내 조건 요금</b>: 30분~24시간 슬라이더로 계산, 1일권 상한 자동 적용</li>
    <li><b>차량 감면</b>: 경차·저공해·다자녀 50%, 국가유공자·장애인 80% 가정 계산</li>
    <li><b>실시간 잔여면수</b>: 수원도시공사 안내 지도 기준(조회 시점 스냅샷) · 등록 구획수와 스냅샷 총면수가 다른 곳은 차이를 함께 표시</li>
    <li><b>지도 연결</b>: 카카오맵·네이버지도로 바로 이동</li>
  </ul>
</div>
<h2>데이터</h2>
<p class="lede">공공데이터포털 전국주차장정보표준데이터(수원시 {data['quality']['원자료_수원시행수']}행, 기준일 2026-04-16),
수원도시공사 공영주차장 안내 지도({esc(SNAPSHOT_TS)} 조회), 경기도 수원시 공영노외주차장현황(기준일 2026-08-01)을 결합했습니다.
구획수(표준데이터 등록면수)와 잔여면수 옆의 스냅샷 총면수는 기준이 달라 {s['capa_gap']}곳에서 차이가 있으며, 해당 카드에 차이를 함께 표시했습니다.
요금과 운영시간은 현장과 다를 수 있으니 방문 전에 확인하세요.</p>
<p><a class="btn solid" href="parking/gyeonggi/suwon/">수원시 전체 주차장 보기 →</a></p>
"""
    return path, layout(
        title=f"{SITE_NAME} — 수원시 공영주차장 요금·무료 개방 계산",
        description="수원시 공영주차장 요금을 요일·시간·감면 조건으로 바로 계산하고, "
                    "주말·공휴일 무료 개방 주차장과 실시간 잔여면수를 확인하세요.",
        path=path, body=body, crumbs=[("홈", "")], nav_active="", jsonld=[])


# ------------------------------------------------------------------ 404
def build_404(data, lots):
    """없는 주소로 들어왔을 때 보여 줄 404 페이지 (dist/404.html).

    Cloudflare Pages 는 매칭되는 파일이 없으면 dist/404.html 을 그대로 돌려주고
    주소창의 경로는 바꾸지 않는다. 따라서 깊이를 알 수 없어 상대경로(../)를 쓸 수 없고,
    이 페이지 안의 링크·에셋은 모두 사이트 절대경로(/...)로 만든다.
    검색 결과에 남지 않도록 noindex 로 둔다.
    """
    s = stats_for(lots)
    cards = "".join(
        f'<a class="link-card" href="/parking/gyeonggi/{gu_slug(g)}/">\n'
        f'  <span class="t">{g}<span class="go">{stats_for([l for l in lots if l["gu"] == g])["n"]}곳 →</span></span>\n'
        f'  <span class="d">주차요금 계산 · 주말 무료 개방 · 동별 목록</span>\n</a>' for g in GU_ORDER)
    body = f"""
<h1>페이지를 찾을 수 없습니다 (404)</h1>
<p class="lede">주소가 바뀌었거나 없는 경로입니다. 아래에서 원하는 주차장을 다시 찾아보세요.</p>
<p>
  <a class="btn solid" href="/">홈으로</a>
  <a class="btn" href="/parking/gyeonggi/suwon/">수원시 주차장 목록</a>
</p>
<h2>구별로 찾기</h2>
<div class="grid-2">{cards}</div>
<h2>이런 걸 확인할 수 있어요</h2>
<div class="note-box">
  <ul>
    <li><b>내 조건 요금</b>: 요일·시간·감면을 고르면 30분~24시간 예상요금을 바로 계산</li>
    <li><b>주말·공휴일 무료 개방</b>: 언제 무료로 열리는지, 언제 문을 닫는지</li>
    <li><b>실시간 잔여면수</b>: {esc(SNAPSHOT_TS)} 조회 스냅샷 기준</li>
  </ul>
</div>
<p class="updated">수원시 공영주차장 {s['n']}곳 · 구획 {s['spaces']:,}면</p>
"""
    return layout(
        title=f"페이지를 찾을 수 없습니다 (404) | {SITE_NAME}",
        description="요청한 주소의 페이지가 없습니다. 공영주차장 파인더에서 수원시 공영주차장 요금과 무료 개방 정보를 확인하세요.",
        path="/404.html", body=body, crumbs=[("홈", "/")], nav_active="", jsonld=[],
        absolute_links=True, robots="noindex,follow", canonical="")


# ------------------------------------------------------------------ main
def main():
    global BUILD_TS, SITE_BASE, SNAPSHOT_TS
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=SITE_BASE)
    args = ap.parse_args()
    SITE_BASE = args.base.rstrip("/")

    data = json.loads(DATA_FILE.read_text())
    BUILD_TS = data["meta"]["generated_at"]
    SNAPSHOT_TS = data["meta"].get("snapshot_at") or BUILD_TS
    lots = data["lots"]
    for l in lots:
        if not l.get("dong"):
            l["dong"] = "기타"

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    for f in ("style.css", "app.js"):
        shutil.copy(ASSETS / f, DIST / "assets" / f)

    pages = []
    pages.append(build_landing(data, lots))
    pages.append(build_city(data, lots))
    for d in data["districts"]:
        gu_lots = [l for l in lots if l["gu"] == d["name"]]
        pages.append(build_district(d, gu_lots, data))
        pages.append(build_weekend(d, gu_lots, data))
        by_dong = {}
        for l in gu_lots:
            by_dong.setdefault(l["dong"], []).append(l)
        slugs = dong_slug_map(by_dong)
        for dong, dl in sorted(by_dong.items()):
            pages.append(build_dong(d, dong, dl, data, slug_override=slugs[dong]))

    for path, html_text in pages:
        out = DIST / path.strip("/") / "index.html" if path != "/" else DIST / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")

    # 없는 주소용 404 (사이트맵에는 넣지 않는다)
    (DIST / "404.html").write_text(build_404(data, lots), encoding="utf-8")

    urls = "\n".join(
        f"  <url><loc>{SITE_BASE}{p}</loc><changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if p == '/' else ('0.9' if p.count('/') <= 4 else '0.7')}</priority></url>"
        for p, _ in pages)
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n')
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}/sitemap.xml\n")

    print(f"생성 완료: {len(pages)}페이지 + 404.html · dist/")
    for p, _ in pages:
        print("  ", p)


if __name__ == "__main__":
    main()
