#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""생성물 정적 검사: JSON-LD 유효성, 내부 링크, 계산 규칙 표본, 도시별 확장 안전 규칙."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "dist"
DATA = json.loads((BASE / "data" / "site.json").read_text())
CITIES = DATA["cities"]
LOTS = DATA["lots"]

fails, warns = [], []


def page_text(rel):
    return (DIST / rel).read_text()


def pages_under(prefix):
    return sorted(p for p in DIST.rglob("index.html") if p.relative_to(DIST).as_posix().startswith(prefix))


# ---------------------------------------------------------------- JSON-LD
pages = sorted(DIST.rglob("index.html"))
types_seen = {}
for pg in pages:
    html = pg.read_text()
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    for b in blocks:
        if b.strip() == "":
            continue
        try:
            obj = json.loads(b)
        except Exception as e:
            fails.append(f"{pg}: JSON-LD 파싱 실패 {e}")
            continue
        t = obj.get("@type")
        types_seen.setdefault(t, 0)
        types_seen[t] += 1
        if t == "BreadcrumbList":
            for it in obj["itemListElement"]:
                if "position" not in it or "name" not in it:
                    fails.append(f"{pg}: BreadcrumbList 항목 누락 {it}")
        if t == "ItemList":
            if obj.get("numberOfItems") != len(obj.get("itemListElement", [])):
                fails.append(f"{pg}: ItemList 개수 불일치")
        if t == "FAQPage":
            for q in obj["mainEntity"]:
                if not q["name"].strip() or not q["acceptedAnswer"]["text"].strip():
                    fails.append(f"{pg}: FAQ 빈 항목")

print("페이지 수:", len(pages))
print("JSON-LD 유형:", types_seen)

# ---------------------------------------------------------------- 내부 링크
link_re = re.compile(r'href="([^"#:]+)(?:#[^"]*)?"')
checked = set()
for pg in pages:
    html = pg.read_text()
    for href in link_re.findall(html):
        if href.startswith(("http", "mailto", "tel", "/assets", "#")):
            continue
        if href.startswith("/"):
            target = DIST / href.lstrip("/")
        else:
            target = (pg.parent / href).resolve()
        key = (str(pg), str(target))
        if key in checked:
            continue
        checked.add(key)
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            fails.append(f"{pg.relative_to(DIST)} → 깨진 링크 {href}")

print("검사한 내부 링크:", len(checked))
# ---------------------------------------------------------------- 페이지 기본 구조
for pg in pages:
    html = pg.read_text()
    if html.count("<h1>") != 1:
        fails.append(f"{pg.relative_to(DIST)}: h1 {html.count('<h1>')}개")
    if "<title>" not in html or "<meta name=\"description\"" not in html:
        fails.append(f"{pg.relative_to(DIST)}: title/description 누락")
    if 'class="site-nav"' not in html:
        fails.append(f"{pg.relative_to(DIST)}: 지역 메뉴 누락")
    for c in CITIES:
        hub = f"parking/{c['province_slug']}/{c['slug']}/"
        if hub not in html:
            fails.append(f"{pg.relative_to(DIST)}: {c['city']} 허브 링크 없음({hub})")

# ---------------------------------------------------------------- 404 페이지
# Cloudflare Pages 는 없는 주소에 dist/404.html 을 돌려주고 주소창 경로는 그대로 둔다.
# 따라서 이 파일의 링크·에셋은 상대경로가 아니라 사이트 절대경로(/...)여야 한다.
p404 = DIST / "404.html"
if not p404.exists():
    fails.append("dist/404.html 없음 (build_site.py 재실행 필요)")
else:
    h404 = p404.read_text()
    if "noindex" not in h404:
        fails.append("404.html: robots noindex 아님")
    if "<link rel=\"canonical\"" in h404:
        fails.append("404.html: canonical 태그가 있음(색인 대상 아님)")
    for name in ("홈으로", "수원시 주차장 목록", "성남시 주차장 목록", "화성시 주차장 목록"):
        if name not in h404:
            fails.append(f"404.html: '{name}' 링크 없음")
    for href in re.findall(r'(?:href|src)="([^"#]+)"', h404):
        if href.startswith(("http", "mailto:", "tel:", "data:")):
            continue
        if not href.startswith("/"):
            fails.append(f"404.html: 절대경로 아님 {href}")
            continue
        target = DIST / href.lstrip("/")
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            fails.append(f"404.html → 깨진 링크 {href}")
    print("404.html 검사 완료 (절대경로 링크·noindex)")

# ---------------------------------------------------------------- 슬러그(전국 확장)
from build_site import (DONG_SLUG, GU_SLUG, UNKNOWN_DONG, base_slug,  # noqa: E402
                        dong_slug, dong_slug_map, gu_slug)

# 1) 수원시 29개 동·4개 구는 수동 매핑 그대로 (기존 색인 URL 불변)
for name, slug in DONG_SLUG.items():
    if dong_slug(name) != slug:
        fails.append(f"동 슬러그 변경: {name} {slug} → {dong_slug(name)}")
for name, slug in GU_SLUG.items():
    if gu_slug(name) != slug:
        fails.append(f"구 슬러그 변경: {name} {slug} → {gu_slug(name)}")
for name, slug in DONG_SLUG.items():
    if not any(p.parent.name == slug and p.parent.parent.name.startswith("suwon-")
               for p in pages):
        fails.append(f"동 슬러그 페이지 없음: {name} → {slug}")

# 2) 매핑에 없는 지역은 로마자 fallback 으로 자동 생성
expect = {
    "경기도": "gyeonggi-do", "성남시": "seongnam-si", "분당구": "bundang-gu",
    "판교동": "pangyo-dong", "정자동": "jeongja-dong", "별내동": "byeolnae-dong",
    "옥정동": "okjeong-dong", "새솔동": "saesol-dong", "중앙동": "jungang-dong",
    "우만2동": "uman2-dong", "경수대로": "gyeongsu-daero", "가평군": "gapyeong-gun",
}
for name, want in expect.items():
    got = base_slug(name)
    if got != want:
        fails.append(f"로마자 fallback 불일치: {name} {want} ≠ {got}")
for name, want in {"분당구": "seongnam-bundang", "영통구": "suwon-yeongtong"}.items():
    got = gu_slug(name, "성남시" if name == "분당구" else "수원시")
    if got != want:
        fails.append(f"구 슬러그 fallback 불일치: {name} {want} ≠ {got}")

# 3) 같은 구에서 슬러그가 겹쳐도 결정적으로 분리
m = dong_slug_map(["중앙동", "중앙동(가)"])
if len(set(m.values())) != len(m):
    fails.append(f"동 슬러그 충돌 미해결: {m}")
if (DIST / "parking" / "gyeonggi" / "suwon-yeongtong" / "etc").exists():
    fails.append("미등록 동이 etc/ 로 빠짐")

# 4) canonical·JSON-LD URL 은 지정한 배포 도메인 기준
SITE_BASE = "https://parking.9welfare.com"
for pg in pages:
    html = pg.read_text()
    for m2 in re.findall(r'<link rel="canonical" href="([^"]+)"', html):
        if not m2.startswith(SITE_BASE + "/") or "//" in m2[len("https://"):]:
            fails.append(f"{pg.relative_to(DIST)}: canonical 이상 {m2}")
        if ".html" in m2:
            fails.append(f"{pg.relative_to(DIST)}: canonical 에 .html 포함 {m2}")
    for b2 in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        if '"url": "' in b2 and SITE_BASE not in b2:
            fails.append(f"{pg.relative_to(DIST)}: JSON-LD URL 이 배포 도메인 아님")
print("슬러그·canonical 검사 완료")

# ---------------------------------------------------------------- 도시별 확장 규칙
# 1) 수원시 39페이지(랜딩·시·구·주말·동) 는 그대로 남아 있어야 한다.
suwon_pages = [p for p in pages if "/suwon" in p.as_posix()]
if len(suwon_pages) != 38:
    fails.append(f"수원시 페이지 수 변경: {len(suwon_pages)} (기대 38 = 허브 1 + 구 4 + 주말 4 + 동 29)")

# 2) 도시별 페이지 구성: 허브 1 + 구 1 + (주말 페이지) + 동 페이지(기준 이상) + (노상 페이지)
for city in CITIES:
    slug = city["slug"]
    hub = DIST / "parking" / "gyeonggi" / slug / "index.html"
    if not hub.exists():
        fails.append(f"{city['city']}: 시 허브 없음")
        continue
    card_lots = [l for l in LOTS if l.get("city") == city["city"] and l.get("list_mode", "card") != "street"]
    street_lots = [l for l in LOTS if l.get("city") == city["city"] and l.get("list_mode") == "street"]
    for d in city["districts"]:
        p = DIST / "parking" / "gyeonggi" / d["slug"] / "index.html"
        if not p.exists():
            fails.append(f"{city['city']} {d['name']}: 구 페이지 없음")
            continue
        d_lots = [l for l in card_lots if l["gu"] == d["name"]]
        # 카드 수 = 목록에 그린 주차장 수
        cards = len(re.findall(r'class="card lot', p.read_text()))
        if cards != len(d_lots):
            fails.append(f"{d['name']}: 카드 {cards}장 vs 데이터 {len(d_lots)}곳")
        weekend = p.parent / "weekend-free" / "index.html"
        if bool(city.get("weekend_free_pages")) != weekend.exists():
            fails.append(f"{d['name']}: 주말 페이지 존재 여부 불일치")
        # 동 페이지: 기준 미만 동은 페이지가 없어야 한다(빈 페이지 방지)
        by_dong = Counter(l["dong"] or UNKNOWN_DONG for l in d_lots)
        minimum = city.get("dong_page_min_lots", 3)
        slugs_map = dong_slug_map(by_dong)
        dong_dirs = {q.parent.name: q for q in p.parent.rglob("index.html")
                     if q.parent.parent == p.parent and q.parent.name not in ("weekend-free", "street-parking")}
        for dong, n in by_dong.items():
            if dong == UNKNOWN_DONG:
                continue      # 주소·좌표로 동을 정하지 못한 묶음은 페이지를 만들지 않는다(의도된 동작)
            slug_d = slugs_map[dong]
            hit = dong_dirs.get(slug_d)
            if n >= minimum and not hit:
                warns.append(f"{d['name']} {dong}: {n}곳인데 동 페이지 없음")
            if n < minimum and hit:
                fails.append(f"{d['name']} {dong}: {n}곳인데 동 페이지가 생성됨(기준 {minimum}곳)")
            if hit:
                cards_d = len(re.findall(r'class="card lot', hit.read_text()))
                if cards_d != n:
                    fails.append(f"{slug_d}: 카드 {cards_d}장 vs {dong} {n}곳")
    street_page = DIST / "parking" / "gyeonggi" / slug / "street-parking" / "index.html"
    if bool(street_lots) != street_page.exists():
        fails.append(f"{city['city']}: 노상 페이지 존재 여부 불일치")
    if street_page.exists():
        rows = len(re.findall(r"<tr><td>", street_page.read_text()))
        if rows < len(street_lots):
            fails.append(f"{city['city']}: 노상 페이지 행 {rows} < 구간 {len(street_lots)}")

# 3) 도시 간 자료 혼입 금지: 도시 페이지에 다른 도시의 자료/문구가 없어야 한다.
MIX = {
    "seongnam": ("수원", "수원도시공사", "영통구", "권선구", "용인", "용인도시공사"),
    "yongin": ("수원", "수원도시공사", "성남", "성남도시개발공사", "영통구", "권선구", "수정구", "중원구", "분당구"),
    # 화성시는 2026-03-01 4개 구(만세·효행·병점·동탄) 체제 — 다른 도시의 구·자료·문구가 섞이면 실패
    "hwaseong": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
                 "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
                 "처인구", "기흥구", "수지구"),
}
for p in pages:
    rel = p.relative_to(DIST).as_posix()
    city_key = next((k for k in MIX if f"/{k}" in rel), None)
    if not city_key:
        continue
    html = p.read_text()
    main = html.split('<main class="wrap">', 1)[-1].split("</main>", 1)[0]
    # 주차장 이름 자체가 다른 도시 이름을 담은 경우(예: 용인 영덕동의 노상 구간 '수원교회 인근')는
    # 자료 혼입이 아니므로, 이름을 지운 나머지 본문에서만 다른 도시 이름을 찾는다.
    probe = main
    for n in sorted({l["name"] for l in LOTS
                     if any(b in l["name"] for b in MIX[city_key])}, key=len, reverse=True):
        probe = probe.replace(n, "")
    for bad in MIX[city_key]:
        if bad in probe:
            fails.append(f"{rel}: 본문에 다른 도시 자료 '{bad}' 혼입")
    # 껍데기 방지: 카드·표·계산기 중 하나는 있어야 한다(시 허브는 표, 노상 페이지는 표)
    if not re.search(r'class="card lot|class="data"|class="calc"', main):
        fails.append(f"{rel}: 본문에 카드·표·계산기가 없는 페이지(껍데기)")
    # 노상 구간이 카드로 그려지지 않았는지
    for lot in LOTS:
        if lot.get("list_mode") == "street" and f'data-lot="{lot["id"]}"' in html:
            fails.append(f"{rel}: 노상 구간이 카드로 렌더링됨({lot['name']})")
            break

# 4) 사이트맵 = 실제 페이지 집합 (404 제외, 중복 없음)
sm = (DIST / "sitemap.xml").read_text()
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
want_urls = set()
for p in pages:
    rel = p.relative_to(DIST).as_posix().replace("/index.html", "/")
    if rel == "index.html":
        rel = ""
    want_urls.add(SITE_BASE + "/" + rel)
if set(locs) != want_urls:
    fails.append(f"사이트맵 불일치: 누락 {sorted(want_urls - set(locs))[:5]} / 초과 {sorted(set(locs) - want_urls)[:5]}")
if len(locs) != len(set(locs)):
    fails.append("사이트맵 URL 중복")
if any("404" in u for u in locs):
    fails.append("사이트맵에 404 포함")
print(f"도시별 확장 규칙 검사 완료 (페이지 {len(pages)} · 사이트맵 {len(locs)})")

# ---------------------------------------------------------------- 계산 규칙
from build_site import price_for, hours_text, fee_text  # noqa: E402

by_name = {}
for l in LOTS:
    by_name.setdefault(l["name"], l)

cases = [
    # (주차장, 시간, 요일, 감면, 면제분, 기대 상태, 기대 금액)
    ("영통구청", 60, "weekday", 0, 0, "paid", 1500),
    ("영통구청", 120, "weekday", 0, 0, "paid", 3300),
    ("영통구청", 120, "sun", 0, 0, "free", None),
    ("신대호수", 120, "weekday", 0, 0, "paid", 700),
    ("신대호수", 120, "weekday", 0.5, 0, "paid", 350),
    ("농수산시장", 1440, "weekday", 0, 0, "paid", 6000),          # 1일권 상한
    ("화성박물관,팔달구청", 120, "sat", 0, 0, "closed", None),     # 토요일 미운영
    ("시청정문", 120, "sat", 0, 0, "closed", None),
    # 성남시: 유료 30분 400원 + 10분 200원, 1일권 6,000원(24시간)
    ("수진역환승공영주차장", 30, "weekday", 0, 0, "paid", 400),
    ("수진역환승공영주차장", 120, "weekday", 0, 0, "paid", 2200),
    ("수진역환승공영주차장", 1440, "weekday", 0, 0, "paid", 6000),
    # 성남시 조례: 장애인 1시간 면제 후 50% / 국가유공자 12시간 면제 후 50%
    ("수진역환승공영주차장", 30, "weekday", 0.5, 60, "free", None),
    ("수진역환승공영주차장", 120, "weekday", 0.5, 60, "paid", 1100),
    ("수진역환승공영주차장", 600, "weekday", 0.5, 720, "free", None),
    ("수진역환승공영주차장", 1440, "weekday", 0.5, 720, "paid", 3000),
    # 용인시: 유료 10분 600원 + 10분 300원, 1일권 9,000원 / 부설 30분 600원 + 10분 300원
    ("금학공영", 30, "weekday", 0, 0, "paid", 1200),
    ("금학공영", 120, "weekday", 0, 0, "paid", 3900),
    ("금학공영", 1440, "weekday", 0, 0, "paid", 9000),
    ("마북동", 30, "weekday", 0, 0, "paid", 600),
    ("마북동", 120, "weekday", 0, 0, "paid", 3300),
    ("유방동1공영", 120, "weekday", 0, 0, "paid", 1500),
    ("상갈공영", 120, "weekday", 0.5, 0, "paid", 750),
    # 용인시 조례: 장애인 6시간 면제 후 50%
    ("금학공영", 120, "weekday", 0.5, 360, "free", None),
    ("금학공영", 600, "weekday", 0.5, 360, "paid", 4500),
    # 용인시는 요금 구분 '무료'인 주차장이 다수
    ("미르스타디움", 120, "weekday", 0, 0, "free", None),
    ("미르스타디움", 1440, "sun", 0, 0, "free", None),
    # 화성시(2026-10-20 기준): 30분 기본 400원 + 10분 600원, 1일권 없음 / 재래시장은 120분 300원 + 10분 400원
    ("동탄2지구 주63", 120, "weekday", 0, 0, "paid", 2200),
    ("동탄2지구 주63", 240, "weekday", 0, 0, "paid", 9400),
    ("동탄2지구 주63", 120, "sun", 0, 0, "free", None),          # 특기사항 '주말 및 공휴일 무료'
    ("남양재래시장", 120, "weekday", 0, 0, "paid", 300),
    ("남양재래시장", 240, "weekday", 0, 0, "paid", 5100),
    ("제부도임시", 120, "weekday", 0, 0, "paid", 3000),         # 시간당 3,000원
    ("제부도임시", 240, "weekday", 0, 0, "paid", 9000),
    ("영천1", 120, "weekday", 0, 0, "paid", 2200),              # 노상 구간도 같은 요금표
    ("영천1", 120, "sun", 0, 0, "free", None),
    # 화성시 조례: 국가유공자·심한 장애 100% / 심하지 않은 장애 2시간 면제 후 50%
    ("남양재래시장", 240, "weekday", 1.0, 0, "paid", 0),
    ("남양재래시장", 120, "weekday", 0.5, 120, "free", None),
    ("남양재래시장", 240, "weekday", 0.5, 120, "paid", 2550),
    ("신리천 카페거리", 120, "weekday", 0, 0, "free", None),
    ("동탄 캠핑카(임시)", 120, "weekday", 0, 0, "unknown", None),  # 요금 필드 비어 있음 → 0원 아님
]
for name, minutes, day, rate, exempt, want_state, want_amt in cases:
    lot = by_name.get(name)
    if not lot:
        fails.append(f"표본 계산: '{name}' 데이터 없음")
        continue
    r = price_for(lot, minutes, day, rate, exempt)
    ok = r["state"] == want_state and (want_amt is None or r.get("amount") == want_amt)
    print(f"{'OK ' if ok else 'FAIL'} {name} {minutes}분 {day} 감면{rate:.0%} 면제{exempt}분 → {r}")
    if not ok:
        fails.append(f"계산 규칙 불일치: {name} {minutes}분 {day} → {r} (기대 {want_state}/{want_amt})")

# 요금 미상 표시 확인
unknown = [l for l in LOTS if l["fee"]["type"] == "미상"]
if unknown:
    r = price_for(unknown[0], 120, "weekday", 0)
    ok = r["state"] == "unknown"
    print(f"{'OK ' if ok else 'FAIL'} 요금 미상 표본 '{unknown[0]['name']}' → {r}")
    if not ok:
        fails.append("요금 미상 주차장이 0원으로 계산됨")

# 화면 문구 표본
for name in ("영통구청", "시청정문", "곡반정동제7공영", "수진역환승공영주차장",
             "남양재래시장", "제부도임시", "동탄 캠핑카(임시)"):
    if name in by_name:
        print(f"문구 · {name}: {fee_text(by_name[name])} / {hours_text(by_name[name])}")

# 성남시 카드에 '요금 미상' 이 없어야 하고, 무료로 계산되는 곳이 없어야 한다(자료 기준).
sn_cards = [l for l in LOTS if l.get("city") == "성남시" and l.get("list_mode") == "card"]
if any(l["fee"]["type"] == "미상" for l in sn_cards):
    fails.append("성남시 카드에 요금 미상 주차장이 있음(자료 확인 필요)")
paid_sn = [l for l in sn_cards if price_for(l, 120, "weekday")["state"] == "paid"]
if len(paid_sn) != len(sn_cards):
    fails.append(f"성남시 카드 중 평일 2시간 계산 불가 {len(sn_cards) - len(paid_sn)}곳")

# 용인시 카드: 요금 미상이 없어야 하고, 무료·유료가 각각 그 상태로 계산되어야 한다.
yn_cards = [l for l in LOTS if l.get("city") == "용인시" and l.get("list_mode") == "card"]
if any(l["fee"]["type"] == "미상" for l in yn_cards):
    fails.append("용인시 카드에 요금 미상 주차장이 있음(자료 확인 필요)")
yn_paid = [l for l in yn_cards if l["fee"]["type"] == "유료"]
yn_bad = [l["name"] for l in yn_paid if price_for(l, 120, "weekday")["state"] != "paid"]
if yn_bad:
    fails.append(f"용인시 유료 카드 중 평일 2시간 계산 불가 {len(yn_bad)}곳 {yn_bad[:3]}")
yn_free_bad = [l["name"] for l in yn_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if yn_free_bad:
    fails.append(f"용인시 무료 카드가 무료로 계산되지 않음 {len(yn_free_bad)}곳 {yn_free_bad[:3]}")

# 화성시 카드: 요금 필드가 빈 캠핑카 전용 2곳만 '요금 미상'이고, 나머지는 등록값대로 계산되어야 한다.
hs_cards = [l for l in LOTS if l.get("city") == "화성시" and l.get("list_mode") == "card"]
if not hs_cards:
    fails.append("화성시 카드 데이터가 없음")
hs_unknown = [l["name"] for l in hs_cards if l["fee"]["type"] == "미상"]
if sorted(hs_unknown) != sorted(["동탄 캠핑카(임시)", "하길리 캠핑카(임시)"]):
    fails.append(f"화성시 카드 요금 미상 대상이 예상과 다름: {hs_unknown}")
hs_bad = [l["name"] for l in hs_cards if l["fee"]["type"] == "유료"
          and price_for(l, 120, "weekday")["state"] != "paid"]
if hs_bad:
    fails.append(f"화성시 유료 카드 중 평일 2시간 계산 불가 {len(hs_bad)}곳 {hs_bad[:3]}")
hs_free_bad = [l["name"] for l in hs_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if hs_free_bad:
    fails.append(f"화성시 무료 카드가 무료로 계산되지 않음 {len(hs_free_bad)}곳 {hs_free_bad[:3]}")
for l in hs_cards:
    if l["fee"]["type"] == "미상" and price_for(l, 120, "weekday").get("amount") == 0:
        fails.append(f"화성시 요금 미상 카드가 0원으로 계산됨: {l['name']}")

print()
if warns:
    print(f"주의 {len(warns)}건")
    for w in warns[:10]:
        print(" -", w)
if fails:
    print(f"실패 {len(fails)}건")
    for f in fails[:20]:
        print(" -", f)
    sys.exit(1)
print("모두 통과: JSON-LD, 내부 링크, 404, 슬러그/canonical, 도시별 확장 규칙, 계산 규칙")
