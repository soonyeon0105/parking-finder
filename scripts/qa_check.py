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

# ---------------------------------------------------------------- 지도 링크 (T-04, T-04b)
# 2026-11-16 버그: ① 네이버 링크가 c=lng,lat,16(3칸)이라 모바일에서 좌표가 버려지고
# 서울 기본 화면으로 떴다. ② 카카오 핀 이름이 '원천호수'처럼 주차장이 아닌 이름이라
# 호수·공원에 찍힌 것처럼 보였다. ③ 만석공원 제1~5·원천호수·신대호수 좌표가 실제
# 주차장이 아닌 곳을 가리켰다.
# 2026-11-17(T-04b) 버그: c=lng,lat,16,0,0,0,dh(7칸)도 모바일에서는 좌표만 지키고
# 핀이 없었다. 모바일 UA로 따라가면 m.map.naver.com/appLink.naver?…&appTargetPage=map
# 로 끝나 지도 앱이 '중심만 맞춘 화면'으로 열렸다. 지금은 lat/lng/dlevel/title 형식을
# 쓴다(PC는 map.naver.com/p/?title=…&zoom=16, 모바일은 m.map.naver.com/map?…&title=…
# 로 가서 핀+이름 카드가 뜨는 것을 확인).
import html as html_lib  # noqa: E402
from urllib.parse import unquote, quote  # noqa: E402
from build_site import map_links, map_coords, map_label  # noqa: E402

all_html = html_lib.unescape("\n".join(pg.read_text() for pg in pages))
naver_urls = set(re.findall(r'https://map\.naver\.com/\?[^"<>]+', all_html))
kakao_urls = set(re.findall(r'https://map\.kakao\.com/link/map/[^"<>]+', all_html))
print(f"지도 링크: 네이버 {len(naver_urls)}종 · 카카오 {len(kakao_urls)}종")
if not naver_urls or not kakao_urls:
    fails.append("지도 링크가 생성물에 없음")
for u in naver_urls:
    q = u.split("?", 1)[1]
    if "appTargetPage=" in q or "appSchemeName=" in q:
        fails.append(f"네이버 링크가 앱 링크 페이지로 넘어가는 형식임(핀 없이 앱만 열림): {u}")
        continue
    if "/p?c=" in u or "c=" in q.split("&")[0]:
        fails.append(f"구형 네이버 링크(c=)가 남아 있음: {u}")
    if "query=" in q:
        if "menu=location" not in q:
            fails.append(f"좌표 없는 주차장의 네이버 검색 링크에 menu=location이 없음: {u}")
        continue
    for key in ("lat=", "lng=", "dlevel=12", "title="):
        if key not in q:
            fails.append(f"네이버 링크에 {key} 파라미터가 없음(핀·이름이 뜨지 않음): {u}")
    if "주차" not in unquote(q) and "차고지" not in unquote(q):
        fails.append(f"네이버 핀 이름에 '주차장' 표기 없음: {unquote(q)}")
if any("map.naver.com/p?c=" in h or "/p/search/" in h for h in (all_html,)):
    fails.append("구형 네이버 지도 링크(/p?c= 또는 /p/search/)가 남아 있음")
for u in kakao_urls:
    parts = u.split("/link/map/", 1)[1].split(",")
    if len(parts) != 3:
        fails.append(f"카카오 링크가 이름,위도,경도 3조각이 아님(이름에 쉼표?): {u}")
        continue
    if not re.fullmatch(r"3[0-9.]+|1[0-9.]+", parts[1]) or not re.fullmatch(r"1[0-9.]+", parts[2]):
        fails.append(f"카카오 링크 좌표 형식 오류: {u}")
    if "주차" not in unquote(parts[0]) and "차고지" not in unquote(parts[0]):
        fails.append(f"카카오 핀 이름에 '주차장' 표기 없음: {unquote(parts[0])}")
for lot in LOTS:
    kakao, naver = map_links(lot)
    if lot.get("list_mode") == "street":
        continue      # 노상은 카드 대신 표(주소 링크)로 나간다
    for u in (kakao, naver):
        if u not in all_html:
            fails.append(f"{lot['name']} 카드에 지도 링크 누락: {u}")
    if lot.get("lat") and lot.get("lng"):
        lat, lng = map_coords(lot)
        if str(lat) not in kakao or str(lng) not in kakao:
            fails.append(f"{lot['name']} 카카오 링크 좌표가 보정값과 다름: {kakao}")
        if naver != f"https://map.naver.com/?lat={lat}&lng={lng}&dlevel=12&title={quote(map_label(lot))}":
            fails.append(f"{lot['name']} 네이버 링크가 좌표+이름(핀) 형식이 아님: {naver}")
    elif "menu=location" not in naver:
        fails.append(f"{lot['name']}(좌표 없음) 네이버 링크가 검색 형식이 아님: {naver}")
    if not map_label(lot).strip():
        fails.append(f"{lot['name']} 지도 라벨 비었음")
street_links = set(re.findall(r'https://map\.kakao\.com/link/search/[^"<>]+', all_html))
print(f"노상 구간 지도 링크(주소 검색): {len(street_links)}종")
if any("map.kakao.com/?q=" in h for h in (all_html,)):
    fails.append("구형 카카오 지도 링크(map.kakao.com/?q=)가 남아 있음")
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

# ---------------------------------------------------------------- 개인정보처리방침 · GA4 훅 (T-05)
# ① /privacy/ 페이지가 있고 푸터에서 어느 페이지로든 들어갈 수 있는지,
# ② 오류 제보 구글 폼 링크가 /privacy/ 와 모든 푸터에 들어갔는지,
# ③ ga_measurement_id 가 비어 있을 때 GA4 스크립트가 한 장에도 들어가지 않았는지
#    (값을 채우면 모든 페이지에 들어가는지)를 본다.
ERROR_FORM_URL = ("https://docs.google.com/forms/d/e/"
                  "1FAIpQLSfRQ0lo_FnZ9PqQ25CU6e43cfrc5_QHDEITMn8lUG9VNgirCw/viewform")
form_link_re = re.compile(
    r'<a href="' + re.escape(ERROR_FORM_URL) + r'" target="_blank" rel="noopener noreferrer">')

priv = DIST / "privacy" / "index.html"
if not priv.exists():
    fails.append("dist/privacy/index.html 없음 (/privacy/ 페이지)")
else:
    h_priv = priv.read_text()
    if h_priv.count("<h1>") != 1:
        fails.append(f"privacy: h1 {h_priv.count('<h1>')}개")
    for word in ("개인정보처리방침", "개인정보를 직접 수집하지 않", "쿠키", "접속 기록",
                 "Google Analytics 4", "Cloudflare Web Analytics", "오류 제보", "거부 방법"):
        if word not in h_priv:
            fails.append(f"privacy: '{word}' 안내 없음")
    if '<link rel="canonical" href="https://parking.9welfare.com/privacy/">' not in h_priv:
        fails.append("privacy: canonical 이 https://parking.9welfare.com/privacy/ 아님")
    if "noindex" in h_priv:
        fails.append("privacy: robots noindex (색인되어야 하는 페이지)")
    if not form_link_re.search(h_priv):
        fails.append("privacy: 오류 제보 구글 폼 링크(href·target=_blank·noopener) 없음")
    if "온라인 제보 창구를 준비" in h_priv:
        fails.append("privacy: '온라인 제보 창구를 준비' 옛 안내가 남아 있음")
    for word in ("지역·주차장명", "오류 유형", "자동으로 모으지 않습니다"):
        if word not in h_priv:
            fails.append(f"privacy: 폼 안내 '{word}' 없음")
if "https://parking.9welfare.com/privacy/" not in (DIST / "sitemap.xml").read_text():
    fails.append("사이트맵에 /privacy/ 없음")

foot_re = re.compile(r'<footer class="site-foot">.*?</footer>', re.S)
foot_pages = list(pages) + ([p404] if p404.exists() else [])
for pg in foot_pages:
    m = foot_re.search(pg.read_text())
    rel = pg.relative_to(DIST).as_posix()
    if not m:
        fails.append(f"{rel}: 푸터(site-foot) 없음")
    elif "개인정보처리방침" not in m.group(0):
        fails.append(f"{rel}: 푸터에 개인정보처리방침 링크 없음")
    else:
        href = re.search(r'href="([^"]*privacy/[^"]*)"', m.group(0))
        if not href:
            fails.append(f"{rel}: 푸터 개인정보처리방침 링크 주소 이상")
    if not m:
        pass
    elif "오류 제보" not in m.group(0):
        fails.append(f"{rel}: 푸터에 오류 제보 링크 없음")
    elif not form_link_re.search(m.group(0)):
        fails.append(f"{rel}: 푸터 오류 제보 링크가 구글 폼 주소·target=_blank·noopener 아님")
print(f"개인정보처리방침 검사 완료 (푸터 링크 {len(foot_pages)}페이지 · 오류 제보 폼 링크 포함)")

GA_ID = (DATA.get("ga_measurement_id") or "").strip()
all_pages_html = {pg.relative_to(DIST).as_posix(): pg.read_text() for pg in foot_pages}
if GA_ID:
    missing = [rel for rel, h in all_pages_html.items()
               if f"googletagmanager.com/gtag/js?id={GA_ID}" not in h
               or f"gtag('config', '{GA_ID}')" not in h]
    if missing:
        fails.append(f"GA4 측정 ID({GA_ID})가 설정됐는데 태그 없는 페이지: {missing[:5]}")
    print(f"GA4 삽입 확인: {GA_ID} · {len(all_pages_html)}페이지")
else:
    leaked = [rel for rel, h in all_pages_html.items()
              if "googletagmanager" in h or "gtag(" in h or "dataLayer" in h]
    if leaked:
        fails.append(f"ga_measurement_id 가 비었는데 GA4 코드가 들어간 페이지: {leaked[:5]}")
    print(f"GA4 미삽입 확인 (ga_measurement_id 비어 있음 · {len(all_pages_html)}페이지)")

app_js = (DIST / "assets" / "app.js").read_text()
for ev in ("calc_use", "map_outbound_click", "free_filter_click", "404_hit"):
    if ev not in app_js:
        fails.append(f"app.js: '{ev}' 이벤트 훅 없음")
if "typeof window.gtag" not in app_js:
    fails.append("app.js: gtag 존재를 확인하지 않고 이벤트를 보냄(무동작 안전 처리 없음)")
if "weekend-free" not in app_js:
    fails.append("app.js: free_filter_click 을 걸 대상(주말·공휴일 무료 개방 링크) 선택자 없음")
if "data-page" not in app_js or 'data-page="404"' not in (p404.read_text() if p404.exists() else ""):
    fails.append("404.html 이 404_hit 를 알릴 body 표시(data-page)를 갖추지 않음")
print("통계 훅 검사 완료 (calc_use·map_outbound_click·free_filter_click·404_hit)")

# ---------------------------------------------------------------- 검색엔진 소유확인 (T-02)
# 네이버 서치어드바이저 소유확인은 두 방식으로 둔다 — ① 모든 페이지 <head> 의 meta 태그,
# ② 사이트 루트의 확인용 HTML 파일(한 줄). 둘 중 하나만 빠져도 서치어드바이저 확인이 안 되므로
# 여기서 둘 다 본다. 확인 파일은 index.html 이 아니라 pages 목록에 들어가지 않으므로
# JSON-LD·링크 검사 대상이 아니다(별도 파일로 존재만 검사).
from build_site import (NAVER_VERIFICATION_CONTENT, NAVER_VERIFICATION_FILE,  # noqa: E402
                        NAVER_VERIFICATION_FILE_BODY)

naver_meta = f'<meta name="naver-site-verification" content="{NAVER_VERIFICATION_CONTENT}">'
missing_meta = [rel for rel, h in all_pages_html.items() if naver_meta not in h]
if missing_meta:
    fails.append(f"네이버 소유확인 meta 태그 없는 페이지: {missing_meta[:5]}")
nv_file = DIST / NAVER_VERIFICATION_FILE
if not nv_file.exists():
    fails.append(f"네이버 소유확인 파일 없음: dist/{NAVER_VERIFICATION_FILE}")
else:
    body = nv_file.read_text()
    if body.strip() != NAVER_VERIFICATION_FILE_BODY:
        fails.append(f"네이버 소유확인 파일 내용 이상: {body!r}")
    if "<" in body or "\n" in body.strip():
        fails.append("네이버 소유확인 파일이 한 줄 텍스트가 아님(HTML 태그·여러 줄)")
print(f"네이버 소유확인 검사 완료 (meta {len(all_pages_html)}페이지 · {NAVER_VERIFICATION_FILE})")

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
    "seongnam": ("수원", "수원도시공사", "영통구", "권선구", "용인", "용인도시공사",
                 "안양", "안양도시공사", "만안구", "동안구", "평택", "평택도시공사",
                 "부천", "부천도시공사", "원미구", "소사구", "오정구"),
    "yongin": ("수원", "수원도시공사", "성남", "성남도시개발공사", "영통구", "권선구", "수정구", "중원구", "분당구",
               "안양", "안양도시공사", "만안구", "동안구", "평택", "평택도시공사",
               "부천", "부천도시공사", "원미구", "소사구", "오정구"),
    # 화성시는 2026-03-01 4개 구(만세·효행·병점·동탄) 체제 — 다른 도시의 구·자료·문구가 섞이면 실패
    "hwaseong": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
                 "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
                 "처인구", "기흥구", "수지구", "안양", "안양도시공사", "만안구", "동안구",
                 "평택", "평택도시공사", "부천", "부천도시공사", "원미구", "소사구", "오정구"),
    # 안양시는 만안·동안 2개 구 — 다른 도시의 구·자료·문구가 섞이면 실패
    "anyang": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
               "화성", "화성도시공사", "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구",
               "분당구", "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
               "평택", "평택도시공사", "부천", "부천도시공사", "원미구", "소사구", "오정구"),
    # 평택시는 자치구가 없다 — 다른 도시의 구·자료·문구가 섞이면 실패
    "pyeongtaek": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
                   "화성", "화성도시공사", "안양", "안양도시공사",
                   "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
                   "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
                   "만안구", "동안구",
                   "부천", "부천도시공사", "원미구", "소사구", "오정구"),
    # 부천시는 2024-01-01 원미·소사·오정 3개 구로 다시 나뉘었다 — 다른 도시의 구·자료·문구가 섞이면 실패
    "bucheon": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
                "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
                "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
                "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
                "만안구", "동안구"),
}
# 고양시는 덕양구·일산동구·일산서구 3개 구다 — 다른 도시 페이지에 고양 자료가 들어가거나
# 고양 페이지에 다른 도시 자료가 섞이면 실패한다(도시를 추가할 때마다 이 목록에 이름을 더한다).
GOYANG_TOKENS = ("고양", "고양도시관리공사", "덕양구", "일산동구", "일산서구")
# 남양주시는 자치구가 없다(6읍 3면 + 동) — 다른 도시 페이지에 남양주 자료가 섞이면 실패.
NAMYANGJU_TOKENS = ("남양주", "남양주도시공사", "원패스파킹")
# 안산시는 상록구·단원구 2개 구 — 다른 도시 페이지에 안산 자료가 섞이면 실패.
ANSAN_TOKENS = ("안산", "안산도시공사", "상록구", "단원구")
# 시흥시는 자치구가 없다 — 다른 도시 페이지에 시흥 자료가 섞이면 실패.
SIHEUNG_TOKENS = ("시흥", "시흥도시공사", "시흥공영주차")
# 의정부시는 자치구가 없다 — 다른 도시 페이지에 의정부 자료가 섞이면 실패.
UIJEONGBU_TOKENS = ("의정부", "의정부도시공사", "의정부시청")
for _k in list(MIX):
    MIX[_k] = (MIX[_k] + GOYANG_TOKENS + NAMYANGJU_TOKENS + ANSAN_TOKENS + SIHEUNG_TOKENS
               + UIJEONGBU_TOKENS)
MIX["namyangju"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구", "덕양구", "일산동구", "일산서구",
)
MIX["siheung"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사", "남양주", "남양주도시공사", "원패스파킹",
    "안산", "안산도시공사", "상록구", "단원구",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구", "덕양구", "일산동구", "일산서구",
)
MIX["ansan"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사", "남양주", "남양주도시공사", "원패스파킹",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구", "덕양구", "일산동구", "일산서구",
)
MIX["uijeongbu"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사", "남양주", "남양주도시공사", "원패스파킹",
    "안산", "안산도시공사", "시흥", "시흥도시공사", "시흥공영주차",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구", "덕양구", "일산동구", "일산서구",
)
MIX["goyang"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구",
)
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
    # 주소에 든 상호·건물 이름(예: 시흥 배곧동 ‘안양축산농협’)도 자료 혼입이 아니므로 함께 지운다.
    for a in sorted({l.get("addr_jibun") or "" for l in LOTS} | {l.get("addr_road") or "" for l in LOTS},
                    key=len, reverse=True):
        if len(a) > 4:
            probe = probe.replace(a, "")
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

# 3-1) 시 페이지의 '가장 저렴한 곳' 표 링크(#lot-N)가 구 페이지의 같은 주차장 카드를 가리켜야 한다.
#      (카드 번호는 구 페이지 정렬 순서이고, 표의 순위와 다르다)
for city in CITIES:
    hub = DIST / "parking" / "gyeonggi" / city["slug"] / "index.html"
    if not hub.exists():
        continue
    for href, num, label in re.findall(r'<a href="\.\./([^"/]+)/#lot-(\d+)">([^<]+)</a>', hub.read_text()):
        page = DIST / "parking" / "gyeonggi" / href / "index.html"
        if not page.exists():
            fails.append(f"{city['city']}: 저렴한 곳 링크 대상 페이지 없음 {href}")
            continue
        m_card = re.search(rf'id="lot-{num}">.*?<h3>([^<]+)</h3>', page.read_text(), re.S)
        if not m_card:
            fails.append(f"{city['city']} {href}: #lot-{num} 카드 없음({label})")
        elif html_lib.unescape(m_card.group(1)) != html_lib.unescape(label):
            fails.append(f"{city['city']} {href}#lot-{num}: 링크 이름 '{label}' ≠ 카드 '{m_card.group(1)}'")

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
    # 안양시(조례 별표1 급지별 누진): 1급지 최초 30분 600원 + 10분당 300→600→900→1,200원, 최초 15분 무료
    ("일번가노외 주차장", 15, "weekday", 0, 0, "free", None),              # 최초 15분 무료
    ("일번가노외 주차장", 30, "weekday", 0, 0, "paid", 600),
    ("일번가노외 주차장", 60, "weekday", 0, 0, "paid", 1500),             # 600 + 300×3
    ("일번가노외 주차장", 120, "weekday", 0, 0, "paid", 5100),            # 600 + 300×3 + 600×6
    ("일번가노외 주차장", 240, "weekday", 0, 0, "paid", 15000),           # 17,700 → 일일 최대 15,000
    ("개나리놀이터 주차장", 120, "weekday", 0, 0, "paid", 1700),          # 4급지 200 + 100×3 + 200×6
    ("개나리놀이터 주차장", 120, "weekday", 0.5, 0, "paid", 850),
    ("개나리놀이터 주차장", 120, "weekday", 1.0, 0, "paid", 0),
    ("개나리놀이터 주차장", 240, "weekday", 0.5, 120, "paid", 2000),      # 2시간 면제 후 50%
    ("개나리놀이터 주차장", 120, "weekday", 0.5, 120, "free", None),
    ("관악역1환승 주차장", 120, "weekday", 0, 0, "paid", 2300),           # 3급지
    ("먹거리촌노외 주차장", 120, "weekday", 0, 0, "paid", 3400),         # 2급지
    ("호현마을1 공영주차장", 1440, "weekday", 0, 0, "paid", 1500),       # 5급지 일일 최대 1,500
    ("운동장파출소 뒤 주차장", 120, "weekday", 0, 0, "free", None),      # 요금 구분 무료
    # 평택시(2026-11-16 시행 1~3급지): 1급지 90분 무료 뒤 10분 400원 / 2급지 30분 800원+10분 300원 /
    #   3급지 30분 600원+10분 200원, 1일 최대 10,000원
    ("평택동공영주차장", 60, "weekday", 0, 0, "free", None),             # 1급지 90분 무료
    ("평택동공영주차장", 90, "weekday", 0, 0, "free", None),
    ("평택동공영주차장", 120, "weekday", 0, 0, "paid", 1200),            # 90분 뒤 30분 = 400×3
    ("평택동공영주차장", 240, "weekday", 0, 0, "paid", 6000),            # 150분 = 400×15
    ("평택동공영주차장", 1440, "weekday", 0, 0, "paid", 10000),          # 54,000 → 1일 최대
    ("원평제1공영주차장", 30, "weekday", 0, 0, "paid", 800),             # 2급지
    ("원평제1공영주차장", 120, "weekday", 0, 0, "paid", 3500),
    ("매봉공영주차장", 120, "weekday", 0, 0, "paid", 2400),              # 3급지
    ("매봉공영주차장", 240, "weekday", 0, 0, "paid", 4800),
    ("매봉공영주차장", 600, "weekday", 0, 0, "paid", 10000),             # 12,000 → 1일 최대
    # 평택시 조례: 경차·저공해 등 50%, 장애인·전기차 2시간 면제 후 50%, 국가유공자·성실납세자 4시간 면제 후 50%
    ("매봉공영주차장", 120, "weekday", 0.5, 0, "paid", 1200),
    ("매봉공영주차장", 120, "weekday", 0.5, 120, "free", None),
    ("매봉공영주차장", 240, "weekday", 0.5, 120, "paid", 2400),
    ("매봉공영주차장", 240, "weekday", 0.5, 240, "free", None),
    ("매봉공영주차장", 300, "weekday", 0.5, 240, "paid", 3000),          # 6,000의 50%
    ("매봉공영주차장", 120, "weekday", 0.2, 0, "paid", 1920),            # 승용차부제 20%
    ("서정충혼탑 공영주차장", 120, "weekday", 0, 0, "free", None),       # 요금 구분 무료
    # 부천시(조례 별표1 급지별 고정 요금): 1급지 30분 900원+10분 400원 / 2급지 700+300 /
    #   3급지 300+200, 1일 주차권 9,500·7,000·4,000원, 부설(공공시설) 30분 400원+10분 200원
    ("미관광장", 30, "weekday", 0, 0, "paid", 900),                  # 1급지 기본
    ("미관광장", 120, "weekday", 0, 0, "paid", 4500),                # 900 + 400×9
    ("미관광장", 1440, "weekday", 0, 0, "paid", 9500),               # 45,900 → 1일 주차권
    ("소사종합시장", 120, "weekday", 0, 0, "paid", 3400),            # 2급지 700 + 300×9
    ("소사종합시장", 1440, "weekday", 0, 0, "paid", 7000),
    ("소사역환승", 120, "weekday", 0, 0, "paid", 2100),              # 3급지 300 + 200×9
    ("소사역환승", 1440, "weekday", 0, 0, "paid", 4000),
    ("부천체육관", 120, "weekday", 0, 0, "paid", 2200),              # 부설 400 + 200×9
    ("부천체육관", 1440, "weekday", 0, 0, "paid", 6000),
    ("시청부설", 60, "weekday", 0, 0, "free", None),                 # 최초 60분 무료
    ("시청부설", 120, "weekday", 0, 0, "paid", 1200),                # 60분 초과분 200×6
    ("시청부설", 120, "sat", 0, 0, "closed", None),                  # 토·일 휴무
    ("중동먹거리", 120, "weekday", 0, 0, "paid", 4500),              # 노상 1급지(평일 09~18시)
    ("중동먹거리", 120, "sun", 0, 0, "closed", None),
    ("복사초앞", 120, "weekday", 0, 0, "free", None),                # 요금 구분 무료
    ("교통정보센터", 120, "weekday", 0, 0, "unknown", None),          # 월정기 전용 → 0원 아님
    ("송내파인", 120, "weekday", 0, 0, "unknown", None),
    # 부천시 조례 감면: 경차·저공해 등 50%, 65세·명예시민·장기기증 2시간 면제 후 50%,
    #   장애인·국가유공자 면제, 모범·유공납세자 100%
    ("미관광장", 120, "weekday", 0.5, 0, "paid", 2250),
    ("미관광장", 240, "weekday", 0.5, 120, "paid", 4650),            # 2시간 면제 대상이 2시간을 넘겨 50%
    ("미관광장", 120, "weekday", 0.5, 120, "free", None),
    ("미관광장", 120, "weekday", 1.0, 0, "paid", 0),                 # 장애인·국가유공자 면제
    # 고양시(조례 별표1 2026년 구간 2026-07-01~2027-06-30): 노외 1급지 30분 720원 + 5분당 120원·1일 9,500원 /
    #   2급지 600+120·7,200 / 3급지 240+70·3,600, 노상은 5분당 190·120·100(2시간 초과분은 2배)
    ("장항 제1", 30, "weekday", 0, 0, "paid", 720),                 # 노외 1급지 기본
    ("장항 제1", 120, "weekday", 0, 0, "paid", 2880),               # 720 + 120×18
    ("장항 제1", 1440, "weekday", 0, 0, "paid", 9500),              # 34,560 → 1일 주차권
    ("탄현 제1", 120, "weekday", 0, 0, "paid", 2760),               # 노외 2급지 600 + 120×18
    ("행신 제1", 120, "weekday", 0, 0, "paid", 1500),               # 노외 3급지 240 + 70×18
    ("행신 제1", 1440, "weekday", 0, 0, "paid", 3600),
    ("탄현 제1", 120, "sat", 0, 0, "closed", None),                 # 운영요일 평일
    ("노상 5권역", 60, "weekday", 0, 0, "paid", 2280),              # 노상 1급지 5분당 190
    ("노상 5권역", 240, "weekday", 0, 0, "paid", 13680),            # 4,560 + 380×24 (2시간 초과 할증)
    ("노상 1권역", 120, "weekday", 0, 0, "paid", 2400),             # 노상 3급지 5분당 100
    ("노상 1권역", 1440, "weekday", 0, 0, "paid", 5500),            # 49,920 → 1일 주차권
    ("화정역 환승", 120, "weekday", 0, 0, "paid", 2400),            # 4급지 폐지 → 노상 3급지
    ("화정역 환승", 1440, "weekday", 0, 0, "paid", 5500),
    ("호수공원 부설 3", 60, "weekday", 0, 0, "paid", 1200),         # 도시공원 부설 → 노상 3급지
    ("호수공원 부설 3", 1440, "weekday", 0, 0, "paid", 5500),
    ("고양시청 부설", 60, "weekday", 0, 0, "free", None),           # 최초 1시간 무료
    ("고양시청 부설", 120, "weekday", 0, 0, "paid", 2280),          # 190×12
    ("행주산성 부설 하", 120, "weekday", 0, 0, "paid", 2000),       # 입차 때 1구획 2,000원
    ("고양일산", 120, "weekday", 0, 0, "paid", 2880),               # 노외 1급지
    ("고양 제1", 120, "weekday", 0, 0, "free", None),               # 요금 구분 무료
    ("약산공영", 120, "weekday", 0, 0, "free", None),               # 노상·무료
    # 고양시 감면: 경차·저공해·임산부·다자녀 등 50%, 국가유공자·심한 장애인 12시간 면제 후 50%,
    #   모범·유공납세자 100%
    ("장항 제1", 120, "weekday", 0.5, 0, "paid", 1440),
    ("장항 제1", 600, "weekday", 0.5, 720, "free", None),           # 12시간 면제
    ("장항 제1", 120, "weekday", 1.0, 0, "paid", 0),
    ("노상 5권역", 120, "weekday", 0.5, 0, "paid", 2280),
    # 남양주시(조례 별표1, 2026-02-26 시행): 노상·노외 1급지 30분 600원 + 10분당 300원,
    #   1일 주차요금 7,000원이 상한, 최초 10분 무료
    ("다산 제1공영", 10, "weekday", 0, 0, "free", None),              # 최초 10분 무료
    ("다산 제1공영", 30, "weekday", 0, 0, "paid", 600),              # 기본 30분
    ("다산 제1공영", 60, "weekday", 0, 0, "paid", 1500),             # 600 + 300×3
    ("다산 제1공영", 120, "weekday", 0, 0, "paid", 3300),            # 600 + 300×9
    ("다산 제1공영", 1440, "weekday", 0, 0, "paid", 7000),           # 42,900 → 1일 주차요금
    ("다산 제1공영", 120, "sat", 0, 0, "paid", 3300),               # 토요일도 유료
    ("다산 제1공영", 120, "sun", 0, 0, "closed", None),             # 공휴일 미운영 등록
    ("별내동 노상제1", 120, "weekday", 0, 0, "paid", 3300),         # 노상 1급지 유료
    ("별내동 노상제1", 120, "sun", 0, 0, "paid", 3300),             # 유일하게 일·공휴일 운영
    ("금곡 노상제1", 120, "weekday", 0, 0, "free", None),           # 노상 무료 구간
    ("물의정원제1공영", 120, "weekday", 0, 0, "free", None),        # 노외 무료
    # 남양주시 감면: 경차·저공해·다자녀(2명)·65세 50%, 환경친화적 차 1시간 면제 후 50%,
    #   장애인·국가유공자·임산부·다자녀(3명) 24시간 면제 후 50%, 모범·유공·성실납세자 100%
    ("다산 제1공영", 120, "weekday", 0.5, 0, "paid", 1650),
    ("다산 제1공영", 120, "weekday", 0.5, 60, "paid", 1650),        # 1시간 면제 대상이 2시간
    ("다산 제1공영", 60, "weekday", 0.5, 60, "free", None),
    ("다산 제1공영", 600, "weekday", 0.5, 1440, "free", None),      # 24시간 면제
    ("별내동 노상제1", 120, "weekday", 0.5, 0, "paid", 1650),       # 노상 유료 구간 50%
    ("다산 제1공영", 120, "weekday", 1.0, 0, "paid", 0),
    # 안산시(조례 별표2, 2026-04-29 시행): 1급지 30분 600원 + 10분당 300원·1일 9,000원,
    #   2급지 400+200, 3·4급지 300+200·1일 4,500원. 공영주차장 전체 최초 무료시간은 없다.
    ("중앙하이츠빌앞", 30, "weekday", 0, 0, "paid", 600),
    ("중앙하이츠빌앞", 120, "weekday", 0, 0, "paid", 3300),          # 600 + 300×9
    ("중앙하이츠빌앞", 1440, "weekday", 0, 0, "paid", 9000),         # 42,900 → 1일 주차요금
    ("안산세무서뒤", 120, "weekday", 0, 0, "paid", 2200),            # 2급지 400 + 200×9
    ("신천길앞", 120, "weekday", 0, 0, "paid", 2100),                # 3급지 300 + 200×9
    ("공단삼거리(1주차장-중앙일보)", 240, "weekday", 0, 0, "paid", 4500),  # 4급지 4,500 상한
    ("안산세무서뒤", 120, "sun", 0, 0, "closed", None),              # 평일+토요일만 운영
    ("수암봉", 120, "weekday", 0, 0, "closed", None),                # 주말·공휴일만 유료
    ("수암봉", 120, "sat", 0, 0, "paid", 2200),                      # 2시간까지 2급지
    ("시청부설주차장", 20, "weekday", 0, 0, "free", None),           # 20분 이내 무료
    ("시청부설주차장", 60, "weekday", 0, 0, "paid", 1000),           # 30분당 500원
    ("와~스타디움부설주차장", 180, "weekday", 0, 0, "free", None),   # 최초 3시간 무료
    ("와~스타디움부설주차장", 240, "weekday", 0, 0, "paid", 1800),   # 3시간 뒤 10분당 300원
    ("월피동 화물주차장", 120, "weekday", 0, 0, "unknown", None),    # 월 정기권 전용
    ("선부광장", 120, "weekday", 0, 0, "paid", 3300),                # 노상 1급지
    # 안산시 감면: 심한 장애인·국가보훈대상자·행복플러스카드 3시간 면제 후 50%, 경차·저공해 50%
    ("중앙하이츠빌앞", 120, "weekday", 0.5, 180, "free", None),
    ("중앙하이츠빌앞", 240, "weekday", 0.5, 180, "paid", 3450),      # 6,900의 50%
    ("중앙하이츠빌앞", 120, "weekday", 0.5, 0, "paid", 1650),
    ("중앙하이츠빌앞", 120, "weekday", 1.0, 0, "paid", 0),           # 모범·성실납세자
    # 시흥시(조례 별표1, 2026-05-07 시행): 노외 1급지 30분 800원 + 10분당 300원(2시간 초과 400원)·1일 8,000원,
    #   2급지 500+200(300)·5,000원, 3급지 300+100(200)·3,000원. 노상은 같은 요율에 1일 주차요금 없음.
    ("장곡농협", 30, "weekday", 0, 0, "paid", 800),                 # 노외 1급지 기본
    ("장곡농협", 60, "weekday", 0, 0, "paid", 1700),                # 800 + 300×3
    ("장곡농협", 120, "weekday", 0, 0, "paid", 3500),               # 800 + 300×9
    ("장곡농협", 240, "weekday", 0, 0, "paid", 8000),               # 8,300 → 1일 주차요금 8,000
    ("장곡농협", 180, "weekday", 0, 0, "paid", 5900),               # 800 + 300×9 + 400×6 (2시간 초과 할증)
    ("어린이도서관", 120, "weekday", 0, 0, "paid", 2300),            # 노외 2급지 500 + 200×9
    ("어린이도서관", 240, "weekday", 0, 0, "paid", 5000),            # 5,900 → 1일 5,000
    ("정왕역", 120, "weekday", 0, 0, "paid", 1200),                  # 노외 3급지 300 + 100×9
    ("정왕역", 240, "weekday", 0, 0, "paid", 3000),                  # 3,600 → 1일 3,000
    ("물왕호수", 120, "weekday", 0, 0, "paid", 2300),                # 시 현황 2급지
    ("장곡농협", 120, "sun", 0, 0, "free", None),                    # 공휴일 무료 개방
    ("장곡농협", 120, "sat", 0, 0, "paid", 3500),                    # 토요일은 유료
    ("시청 부설주차장", 120, "weekday", 0, 0, "free", None),         # 시 등록 현황 무료
    ("관곡지로 노상", 120, "weekday", 0, 0, "free", None),           # 노상 무료 구간
    ("오이도", 120, "weekday", 0, 0, "paid", 2300),                  # 노상 2급지(1일 주차요금 없음)
    ("오이도", 240, "weekday", 0, 0, "paid", 5900),                  # 500 + 200×9 + 300×12
    ("오이도", 120, "sun", 0, 0, "paid", 2300),                      # 공휴일 무료 개방 제외(명절만)
    ("배다리 선착장", 120, "sun", 0, 0, "paid", 1200),               # 공휴일 무료 개방 제외
    # 시흥시 감면: 국가유공자·심한 장애인 100%, 경차·저공해 60%, 전통시장·병역명문가 50%,
    #   장애인·다자녀 등 2시간 면제 후 50%, 승용차요일제 30%
    ("장곡농협", 120, "weekday", 0.5, 0, "paid", 1750),
    ("어린이도서관", 120, "weekday", 0.6, 0, "paid", 920),
    ("장곡농협", 120, "weekday", 0.3, 0, "paid", 2450),
    ("어린이도서관", 120, "weekday", 0.5, 120, "free", None),         # 2시간 면제
    ("어린이도서관", 180, "weekday", 0.5, 120, "paid", 2050),         # 4,100의 50%
    ("오이도", 120, "weekday", 1.0, 0, "paid", 0),
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

# 안양시 카드: 요금 미상이 없고, 유료·무료가 각각 그 상태로 계산되어야 한다.
#  표준데이터에 추가요금 칸이 비어 있어 조례 별표1 급지별 누진표를 적용했으므로,
#  유료 카드는 모두 누진표(steps)와 일일 상한(cap_fee)을 갖고 있어야 한다.
ay_cards = [l for l in LOTS if l.get("city") == "안양시" and l.get("list_mode") == "card"]
if not ay_cards:
    fails.append("안양시 카드 데이터가 없음")
if any(l["fee"]["type"] == "미상" for l in ay_cards):
    fails.append("안양시 카드에 요금 미상 주차장이 있음(자료 확인 필요)")
ay_paid = [l for l in ay_cards if l["fee"]["type"] == "유료"]
ay_no_steps = [l["name"] for l in ay_paid if not l["fee"].get("steps")]
if ay_no_steps:
    fails.append(f"안양시 유료 카드에 누진 요금표가 없음 {len(ay_no_steps)}곳 {ay_no_steps[:3]}")
ay_no_cap = [l["name"] for l in ay_paid if not l["fee"].get("cap_fee")]
if ay_no_cap:
    fails.append(f"안양시 유료 카드에 일일 최대요금(상한)이 없음 {len(ay_no_cap)}곳 {ay_no_cap[:3]}")
ay_bad = [l["name"] for l in ay_paid if price_for(l, 120, "weekday")["state"] != "paid"]
if ay_bad:
    fails.append(f"안양시 유료 카드 중 평일 2시간 계산 불가 {len(ay_bad)}곳 {ay_bad[:3]}")
ay_free_bad = [l["name"] for l in ay_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if ay_free_bad:
    fails.append(f"안양시 무료 카드가 무료로 계산되지 않음 {len(ay_free_bad)}곳 {ay_free_bad[:3]}")
# 누진 할증이 실제로 붙는지: 4시간 요금 > 2시간 요금 + (2시간/10분 × 1시간 구간요율)
ay_sample = next((l for l in ay_paid if l["fee"]["grade"] == 1 and price_for(l, 240, "weekday").get("capped") is False), None)
if ay_sample:
    p2 = price_for(ay_sample, 120, "weekday")["amount"]
    p4 = price_for(ay_sample, 240, "weekday")["amount"]
    if p4 <= p2 + 12 * ay_sample["fee"]["steps"][1]["unit_fee"]:
        fails.append(f"안양시 누진 할증 미적용 의심: {ay_sample['name']} 2시간 {p2}원·4시간 {p4}원")
# 최초 15분 무료 표기: 15분 이내는 무료, 30분은 기본요금
if ay_paid:
    r_free, r_base = price_for(ay_paid[0], 15, "weekday"), price_for(ay_paid[0], 30, "weekday")
    if not (r_free["state"] == "free" and r_free.get("free_min") == 15
            and r_base["state"] == "paid" and r_base["amount"] == ay_paid[0]["fee"]["base_fee"]):
        fails.append(f"안양시 최초 15분 무료 규칙 불일치: {ay_paid[0]['name']} {r_free} / {r_base}")

# 평택시 카드: 2026-11-16 조례 개정 요금(1~3급지)이 포털 값으로 들어가야 한다.
#  · 카드(노외)에 요금 미상이 없고, 유료는 모두 1일 최대요금(상한)을 갖는다.
#  · 1급지는 90분 무료(기본요금 0), 2급지는 30분 800원, 3급지는 30분 600원 — 조례 별표1과 같다.
pt_cards = [l for l in LOTS if l.get("city") == "평택시" and l.get("list_mode") == "card"]
if not pt_cards:
    fails.append("평택시 카드 데이터가 없음")
if any(l["fee"]["type"] == "미상" for l in pt_cards):
    fails.append("평택시 카드에 요금 미상 주차장이 있음(자료 확인 필요)")
pt_paid = [l for l in pt_cards if l["fee"]["type"] == "유료"]
pt_no_cap = [l["name"] for l in pt_paid if not l["fee"].get("cap_fee")]
if pt_no_cap:
    fails.append(f"평택시 유료 카드에 1일 최대요금이 없음 {len(pt_no_cap)}곳 {pt_no_cap[:3]}")
pt_bad = [l["name"] for l in pt_paid if price_for(l, 120, "weekday")["state"] != "paid"]
if pt_bad:
    fails.append(f"평택시 유료 카드 중 평일 2시간 계산 불가 {len(pt_bad)}곳 {pt_bad[:3]}")
pt_free_bad = [l["name"] for l in pt_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if pt_free_bad:
    fails.append(f"평택시 무료 카드가 무료로 계산되지 않음 {len(pt_free_bad)}곳 {pt_free_bad[:3]}")
pt_grade_expect = {1: (0, 90, 400), 2: (800, 0, 300), 3: (600, 0, 200)}
pt_grade_bad = [f"{l['name']}({l['fee']['grade']}급지 {l['fee']['base_fee']}/{l['fee']['unit_fee']})"
                for l in pt_paid
                if l["fee"].get("grade") in pt_grade_expect
                and (l["fee"]["base_fee"], l["fee"].get("free_min") or 0, l["fee"]["unit_fee"])
                != pt_grade_expect[l["fee"]["grade"]]]
if pt_grade_bad:
    fails.append(f"평택시 급지별 요금이 조례 표와 다름 {len(pt_grade_bad)}곳 {pt_grade_bad[:3]}")
if not any(l["fee"].get("grade") == 1 and l["fee"].get("free_min") == 90 for l in pt_paid):
    fails.append("평택시 1급지 90분 무료 카드가 없음")
# 시 페이지가 계산기·목록·급지 요금표를 모두 갖는지(구가 없는 시는 시 페이지가 목록 페이지를 겸한다)
pt_hub = DIST / "parking" / "gyeonggi" / "pyeongtaek" / "index.html"
if not pt_hub.exists():
    fails.append("평택시 시 페이지 없음")
else:
    hub_html = pt_hub.read_text()
    for need, label in (('id="lot-list"', "주차장 목록"), ('class="calc', "요금 계산기"),
                        ("급지별 주차요금표", "급지 요금표")):
        if need not in hub_html:
            fails.append(f"평택시 시 페이지에 {label} 없음")
    if hub_html.count('class="card lot') != len(pt_cards):
        fails.append(f"평택시 시 페이지 카드 수 불일치({hub_html.count('class=\"card lot')} vs {len(pt_cards)})")

# 부천시 카드: 표준데이터에 요금 칸이 비어 있어 포털 등록요금으로 채웠다.
#  · ‘요금 미상’은 월정기(정기권) 전용으로 시간 요금을 받지 않는 주차장만 있어야 한다.
#  · 유료 카드는 모두 1일 상한(포털 1일 최대요금·현황표 1일 요금·조례 1일 주차권)을 갖는다.
bc_cards = [l for l in LOTS if l.get("city") == "부천시" and l.get("list_mode") == "card"]
if not bc_cards:
    fails.append("부천시 카드 데이터가 없음")
bc_ticket_only = sorted(l["name"] for l in bc_cards if l["fee"]["type"] == "미상")
bc_expect = sorted(["송내IC 화물", "교통정보센터", "무지개고가", "구소새울어울마당", "구소사경찰서별관",
                    "송내파인", "삼정1호", "도당교1호", "오정동1호", "오정동2호"])
if bc_ticket_only != bc_expect:
    fails.append(f"부천시 요금 미상 대상이 예상과 다름: {bc_ticket_only}")
for l in bc_cards:
    if l["fee"]["type"] == "미상" and not l["fee"].get("ticket_only"):
        fails.append(f"부천시 요금 미상 카드가 정기권 전용 표시가 아님: {l['name']}")
bc_paid = [l for l in bc_cards if l["fee"]["type"] == "유료"]
bc_no_cap = [l["name"] for l in bc_paid if not l["fee"].get("cap_fee")]
if bc_no_cap:
    fails.append(f"부천시 유료 카드에 1일 상한이 없음 {len(bc_no_cap)}곳 {bc_no_cap[:3]}")
bc_bad = [l["name"] for l in bc_paid if price_for(l, 120, "weekday")["state"] != "paid"]
if bc_bad:
    fails.append(f"부천시 유료 카드 중 평일 2시간 계산 불가 {len(bc_bad)}곳 {bc_bad[:3]}")
bc_free_bad = [l["name"] for l in bc_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if bc_free_bad:
    fails.append(f"부천시 무료 카드가 무료로 계산되지 않음 {len(bc_free_bad)}곳 {bc_free_bad[:3]}")
bc_null_cap = [l["name"] for l in bc_paid if l["fee"]["cap_fee"] == 0]
if bc_null_cap:
    fails.append(f"부천시 유료 카드 1일 상한이 0원: {bc_null_cap[:3]}")
# 급지·부설이 카드에 모두 있는지(1·2·3급지 노외 + 부설)
for g in (1, 2, 3):
    if not any(l["fee"].get("grade") == g for l in bc_paid):
        fails.append(f"부천시 {g}급지 유료 카드가 없음")
if not any(l["ptype"] == "부설" for l in bc_cards):
    fails.append("부천시 부설(공공시설) 카드가 없음")
# 조례 별표1 급지 요금과 카드 등록요금이 같은지(포털 값이 조례와 어긋난 주차장은 제외 목록으로 확인)
bc_tab = {1: (900, 400, 9500), 2: (700, 300, 7000), 3: (300, 200, 4000)}
bc_mismatch = [f"{l['name']}({l['fee']['grade']}급지 {l['fee']['base_fee']}/{l['fee']['unit_fee']})"
               for l in bc_paid
               if l["ptype"] != "부설" and l["fee"].get("grade") in bc_tab
               and l["fee"].get("portal_name") is None
               and (l["fee"]["base_fee"], l["fee"]["unit_fee"], l["fee"]["cap_fee"]) != bc_tab[l["fee"]["grade"]]]
if bc_mismatch:
    fails.append(f"부천시 조례 급지 요금과 다른 카드 {len(bc_mismatch)}곳 {bc_mismatch[:3]}")

# 부천시 페이지: 시 허브 + 구 3개 + 동 페이지 + 노상 페이지, 시 허브에 급지 요금표·계산기·목록
bc_root = DIST / "parking" / "gyeonggi" / "bucheon"
bc_hub = bc_root / "index.html"
if not bc_hub.exists():
    fails.append("부천시 시 페이지 없음")
else:
    hub_html = bc_hub.read_text()
    for need, label in (("/bucheon-wonmi/", "원미구 링크"), ("/bucheon-sosa/", "소사구 링크"),
                        ("/bucheon-ojeong/", "오정구 링크"),
                        ("급지별 주차요금표", "급지 요금표"), ("구별 현황", "구별 현황")):
        if need not in hub_html:
            fails.append(f"부천시 시 페이지에 {label} 없음")
    for gu in ("원미구", "소사구", "오정구"):
        if gu not in hub_html:
            fails.append(f"부천시 시 페이지에 {gu} 없음")
for slug, gu in (("bucheon-wonmi", "원미구"), ("bucheon-sosa", "소사구"), ("bucheon-ojeong", "오정구")):
    page = DIST / "parking" / "gyeonggi" / slug / "index.html"
    if not page.exists():
        fails.append(f"부천시 {gu} 페이지 없음")
        continue
    html = page.read_text()
    if f"{gu} 공영주차장" not in html:
        fails.append(f"부천시 {gu} 페이지 제목에 구 이름 없음")
    if 'class="calc' not in html:
        fails.append(f"부천시 {gu} 페이지에 요금 계산기 없음")
bc_dongs = [l for l in bc_cards if l.get("dong")]
for (gu, dong) in {(l["gu"], l["dong"]) for l in bc_dongs}:
    n = len([l for l in bc_dongs if l["gu"] == gu and l["dong"] == dong])
    gu_slug_d = "bucheon-" + {"원미구": "wonmi", "소사구": "sosa", "오정구": "ojeong"}[gu]
    page_d = (DIST / "parking" / "gyeonggi" / gu_slug_d
              / f"{__import__('build_site').dong_slug(dong)}" / "index.html")
    if n >= 3 and not page_d.exists():
        fails.append(f"부천시 동 페이지 없음: {gu} {dong}({n}곳)")
    if n < 3 and page_d.exists():
        fails.append(f"부천시 3곳 미만 동 페이지가 만들어짐: {gu} {dong}({n}곳)")

# 고양시: 요금은 표준데이터 등록값(2025-08-01 인상 전)이 아니라 조례 별표1의 2026년
# (2026-07-01~2027-06-30) 요금표를 쓴다. 급지표·부설 갈래와 카드의 등록값이 일치해야 한다.
GY_FEES = {1: (720, 5, 120, 9500), 2: (600, 5, 120, 7200), 3: (240, 5, 70, 3600)}
GY_STREET = {1: (190, 380), 2: (120, 240), 3: (100, 180)}
gy_cards = [l for l in LOTS if l.get("city") == "고양시" and l.get("list_mode") == "card"]
gy_street = [l for l in LOTS if l.get("city") == "고양시" and l.get("list_mode") == "street"]
if not gy_cards:
    fails.append("고양시 카드 데이터가 없음")
if any(l["fee"]["type"] == "미상" for l in gy_cards):
    fails.append("고양시 카드에 요금 미상 주차장이 있음(자료 확인 필요)")
gy_paid = [l for l in gy_cards if l["fee"]["type"] == "유료"]
gy_off = [l for l in gy_paid if l["fee"].get("category") in ("off1", "off2", "off3")]
gy_bad_grade = [f"{l['name']}({l['fee']['category']} {l['fee']['base_fee']}/{l['fee']['unit_fee']}/{l['fee']['daily_fee']})"
                for l in gy_off
                if (l["fee"]["base_fee"], l["fee"]["unit_min"], l["fee"]["unit_fee"], l["fee"]["daily_fee"])
                != GY_FEES[int(l["fee"]["category"][3:])]]
if gy_bad_grade:
    fails.append(f"고양시 노외 급지별 요금이 조례 표와 다름 {len(gy_bad_grade)}곳 {gy_bad_grade[:3]}")
if not all(any(f"off{g}" == l["fee"].get("category") for l in gy_off) for g in (1, 2, 3)):
    fails.append("고양시 노외 1·2·3급지 카드가 모두 있지 않음")
gy_no_day = [l["name"] for l in gy_paid
             if l["fee"].get("category") != "office" and not l["fee"].get("daily_fee")]
if gy_no_day:
    fails.append(f"고양시 유료 카드에 1일 주차권(상한)이 없음 {len(gy_no_day)}곳 {gy_no_day[:3]}")
if not any(l["fee"].get("category") == "office" and l["fee"].get("free_min") == 60 for l in gy_paid):
    fails.append("고양시 시·구청 부설(최초 60분 무료) 카드가 없음")
if len([l for l in gy_paid if l["fee"].get("category") == "transfer"]) != 3:
    fails.append("고양시 환승주차장(노상 3급지 적용) 카드가 3곳이 아님")
gy_st_bad = [l["name"] for l in gy_street
             if l["fee"]["type"] == "유료"
             and (l["fee"]["unit_fee"], l["fee"]["steps"][1]["unit_fee"])
             != GY_STREET.get(l["fee"]["std_grade"], GY_STREET[3])]
if gy_st_bad:
    fails.append(f"고양시 노상 요금이 조례 표와 다름: {gy_st_bad[:3]}")
gy_st_calc = [l["name"] for l in gy_street if l["fee"]["type"] == "유료"
              and price_for(l, 120, "weekday").get("amount") != 24 * l["fee"]["unit_fee"]]
if gy_st_calc:
    fails.append(f"고양시 노상 2시간 요금이 24×5분요금과 다름: {gy_st_calc[:3]}")
# 구 3개·동 13개·노상 8구간·시 허브의 급지 요금표·구 페이지 계산기
gy_hub = DIST / "parking" / "gyeonggi" / "goyang" / "index.html"
if not gy_hub.exists():
    fails.append("고양시 시 페이지 없음")
else:
    hub_html = gy_hub.read_text()
    for need, label in (("급지별 주차요금표", "급지 요금표"), ("goyang-deogyang/", "덕양구 링크"),
                        ("goyang-ilsandong/", "일산동구 링크"), ("goyang-ilsanseo/", "일산서구 링크")):
        if need not in hub_html:
            fails.append(f"고양시 시 페이지에 {label} 없음")
for slug, gu in (("goyang-deogyang", "덕양구"), ("goyang-ilsandong", "일산동구"), ("goyang-ilsanseo", "일산서구")):
    page = DIST / "parking" / "gyeonggi" / slug / "index.html"
    if not page.exists():
        fails.append(f"고양시 {gu} 페이지 없음")
        continue
    html = page.read_text()
    if f"{gu} 공영주차장" not in html:
        fails.append(f"고양시 {gu} 페이지 제목에 구 이름 없음")
    if 'class="calc' not in html:
        fails.append(f"고양시 {gu} 페이지에 요금 계산기 없음")
gy_street_page = DIST / "parking" / "gyeonggi" / "goyang" / "street-parking" / "index.html"
if not gy_street_page.exists():
    fails.append("고양시 노상주차장 페이지 없음(street-parking)")
else:
    rows = len(re.findall(r"<tr><td>", gy_street_page.read_text()))
    if rows < len(gy_street):
        fails.append(f"고양시 노상 페이지 행 {rows} < 구간 {len(gy_street)}")

# 남양주시: 「남양주시 주차장 조례」 별표1(2026-02-26 시행) — 노상·노외 1급지 30분 600원·10분당 300원·
# 1일 7,000원, 최초 10분 무료. 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸한다.
NJ_FEE = (600, 10, 300, 7000, 10)
nj_cards = [l for l in LOTS if l.get("city") == "남양주시" and l.get("list_mode") == "card"]
nj_street = [l for l in LOTS if l.get("city") == "남양주시" and l.get("list_mode") == "street"]
if not nj_cards:
    fails.append("남양주시 카드 데이터가 없음")
if any(l["fee"]["type"] == "미상" for l in nj_cards + nj_street):
    fails.append("남양주시 주차장에 요금 미상이 있음(자료 확인 필요)")
nj_paid = [l for l in nj_cards + nj_street if l["fee"]["type"] == "유료"]
nj_bad_fee = [f"{l['name']}({l['fee']['grade']}급지 {l['fee']['base_fee']}/{l['fee']['unit_fee']}/{l['fee']['daily_fee']})"
              for l in nj_paid
              if (l["fee"]["base_fee"], l["fee"]["unit_min"], l["fee"]["unit_fee"],
                  l["fee"]["daily_fee"], l["fee"]["free_min"]) != NJ_FEE]
if nj_bad_fee:
    fails.append(f"남양주시 유료 주차장 요금이 조례 별표1과 다름 {len(nj_bad_fee)}곳 {nj_bad_fee[:3]}")
if sorted({l["fee"]["grade"] for l in nj_paid}) != [1]:
    fails.append(f"남양주시 유료 주차장 급지가 1급지가 아님: {sorted({l['fee']['grade'] for l in nj_paid})}")
if not all(l["fee"].get("monthly") for l in nj_paid):
    fails.append("남양주시 유료 주차장에 월 정기권(주간) 금액이 없음")
nj_card_bad = [l["name"] for l in nj_cards if l["fee"]["type"] == "유료"
               and price_for(l, 120, "weekday")["state"] != "paid"]
if nj_card_bad:
    fails.append(f"남양주시 유료 카드 중 평일 2시간 계산 불가 {len(nj_card_bad)}곳 {nj_card_bad[:3]}")
nj_free_bad = [l["name"] for l in nj_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if nj_free_bad:
    fails.append(f"남양주시 무료 카드가 무료로 계산되지 않음 {len(nj_free_bad)}곳 {nj_free_bad[:3]}")
# 최초 10분 무료가 카드에 실제로 적용되는지 (10분 0원 · 30분 기본요금)
nj_sample = next((l for l in nj_cards if l["fee"]["type"] == "유료"), None)
if nj_sample:
    r10, r30 = price_for(nj_sample, 10, "weekday"), price_for(nj_sample, 30, "weekday")
    if not (r10["state"] == "free" and r10.get("free_min") == 10
            and r30["state"] == "paid" and r30["amount"] == nj_sample["fee"]["base_fee"]):
        fails.append(f"남양주시 최초 10분 무료 규칙 불일치: {nj_sample['name']} {r10} / {r30}")
# 노상은 무료·유료가 섞여 있고, 무료 구간은 요일과 관계없이 무료로 계산돼야 한다
nj_st_free = [l for l in nj_street if l["fee"]["type"] == "무료"]
nj_st_paid = [l for l in nj_street if l["fee"]["type"] == "유료"]
if not (nj_st_free and nj_st_paid):
    fails.append(f"남양주시 노상 구간의 무료·유료 구성이 예상과 다름(무료 {len(nj_st_free)}·유료 {len(nj_st_paid)})")
if len(nj_st_free) != 28 or len(nj_st_paid) != 7:
    fails.append(f"남양주시 노상 무료/유료 수가 자료와 다름(무료 {len(nj_st_free)}·유료 {len(nj_st_paid)})")
# 도시공사가 공지한 임시 폐쇄(태양광 공사) 안내가 카드에 실려야 한다
nj_closed = {l["name"]: l.get("notice") for l in nj_cards if l.get("notice")}
if sorted(nj_closed) != ["별내동 제2공영", "오남 제1공영"]:
    fails.append(f"남양주시 임시 폐쇄 안내 대상이 예상과 다름: {sorted(nj_closed)}")
nj_hub_html = (DIST / "parking" / "gyeonggi" / "namyangju" / "index.html").read_text() \
    if (DIST / "parking" / "gyeonggi" / "namyangju" / "index.html").exists() else ""
if "임시 폐쇄 2026-11-02" not in nj_hub_html:
    fails.append("남양주시 시 페이지에 별내동 제2공영 임시 폐쇄 안내가 없음")
# 같은 84행이 제공기관명만 바꿔 한 번 더 들어 있어도 카드가 중복되지 않아야 한다
nj_dup = [k for k, v in Counter(l["name"] for l in nj_cards).items() if v > 1]
if nj_dup:
    fails.append(f"남양주시 카드 이름 중복(도시공사 중복 행 혼입 의심): {nj_dup[:3]}")
# 시 페이지가 계산기·목록·급지 요금표를 모두 갖고, 급지 요금표에 노상·노외 표가 있어야 한다
nj_hub = DIST / "parking" / "gyeonggi" / "namyangju" / "index.html"
if not nj_hub.exists():
    fails.append("남양주시 시 페이지 없음")
else:
    hub_html = nj_hub.read_text()
    for need, label in (('id="lot-list"', "주차장 목록"), ('class="calc', "요금 계산기"),
                        ("급지별 주차요금표", "급지 요금표"), ("노외주차장", "노외 요금표"),
                        ("노상주차장", "노상 요금표"), ("최초 10분은 무료", "최초 10분 무료 안내")):
        if need not in hub_html:
            fails.append(f"남양주시 시 페이지에 {label} 없음")
    if hub_html.count('class="card lot') != len(nj_cards):
        fails.append(f"남양주시 시 페이지 카드 수 불일치({hub_html.count('class=\"card lot')} vs {len(nj_cards)})")
# 읍·면·동 페이지: 카드 3곳 이상인 곳만 9개(다산동·화도읍·진접읍·와부읍·진건읍·퇴계원읍·호평동·조안면·오남읍)
nj_root = DIST / "parking" / "gyeonggi" / "namyangju"
nj_dong_pages = sorted(q.parent.name for q in nj_root.rglob("index.html")
                       if q.parent != nj_root and q.parent.name != "street-parking")
nj_by_dong = Counter(l.get("dong") for l in nj_cards if l.get("dong"))
nj_expect = sorted(__import__("build_site").dong_slug(d) for d, n in nj_by_dong.items() if n >= 3)
if nj_dong_pages != nj_expect:
    fails.append(f"남양주시 동 페이지 구성이 다름: {nj_dong_pages} ≠ {nj_expect}")
nj_street_page = nj_root / "street-parking" / "index.html"
if not nj_street_page.exists():
    fails.append("남양주시 노상주차장 페이지 없음(street-parking)")
else:
    nj_rows = len(re.findall(r"<tr><td>", nj_street_page.read_text()))
    if nj_rows < len(nj_street):
        fails.append(f"남양주시 노상 페이지 행 {nj_rows} < 구간 {len(nj_street)}")

# 안산시: 「안산시 주차장 조례」 별표2(시행 2026-04-29) — 1~4급지 30분 기본 + 10분당 가산 + 1일 주차요금.
#   시청부설(30분당 500원·20분 무료), 와~스타디움(3시간 무료 뒤 10분당 300원), 차량등록사업소부설(30분당 500원),
#   수암봉(2시간까지 2급지·이후 1급지)은 조례표와 다른 별도 요금이라 검사에서 뺀다.
AS_FEE = {1: (600, 300, 9000, 80000), 2: (400, 200, 4500, 50000),
          3: (300, 200, 4500, 40000), 4: (300, 200, 4500, 20000)}
AS_SPECIAL = {"시청부설주차장", "와~스타디움부설주차장", "차량등록사업소부설주차장", "수암봉"}
as_cards = [l for l in LOTS if l.get("city") == "안산시" and l.get("list_mode") == "card"]
as_street = [l for l in LOTS if l.get("city") == "안산시" and l.get("list_mode") == "street"]
if not as_cards:
    fails.append("안산시 카드 데이터가 없음")
as_paid = [l for l in as_cards + as_street if l["fee"]["type"] == "유료"]
as_bad_fee = [f"{l['name']}({l['fee']['grade']}급지 {l['fee']['base_fee']}/{l['fee']['unit_fee']}/{l['fee']['daily_fee']})"
              for l in as_paid if l["name"] not in AS_SPECIAL
              and (l["fee"]["base_fee"], l["fee"]["unit_fee"], l["fee"]["daily_fee"])
              != (AS_FEE[l["fee"]["grade"]][0], AS_FEE[l["fee"]["grade"]][1], AS_FEE[l["fee"]["grade"]][2])]
if as_bad_fee:
    fails.append(f"안산시 유료 주차장 요금이 조례 별표2와 다름 {len(as_bad_fee)}곳 {as_bad_fee[:3]}")
if sorted({l["fee"]["grade"] for l in as_paid}) != [1, 2, 3, 4]:
    fails.append(f"안산시 유료 주차장 급지가 1~4급지가 아님: {sorted({l['fee']['grade'] for l in as_paid})}")
if not all(l["fee"].get("monthly") for l in as_paid):
    fails.append("안산시 유료 주차장에 월 정기권 금액이 없음")
# 수암봉(평일 미운영)·와~스타디움(최초 3시간 무료)은 2시간 계산이 유료가 아니어도 정상이다.
as_card_bad = [l["name"] for l in as_cards
               if l["fee"]["type"] == "유료" and l["name"] not in ("수암봉", "와~스타디움부설주차장")
               and price_for(l, 120, "weekday")["state"] != "paid"]
if as_card_bad:
    fails.append(f"안산시 유료 카드 중 평일 2시간 계산 불가 {len(as_card_bad)}곳 {as_card_bad[:3]}")
as_free_bad = [l["name"] for l in as_cards
               if l["fee"]["type"] == "무료" and price_for(l, 120, "weekday")["state"] != "free"]
if as_free_bad:
    fails.append(f"안산시 무료 카드가 무료로 계산되지 않음 {len(as_free_bad)}곳 {as_free_bad[:3]}")
# 급지별 대표 요금 — 1급지 30분 600원, 2급지 400원, 3·4급지 300원, 1일 주차요금 1급지 9,000원·그 밖 4,500원
as_by = {l["name"]: l for l in as_cards}
for name, want in (("중앙하이츠빌앞", 600), ("안산세무서뒤", 400), ("신천길앞", 300), ("공단삼거리(1주차장-중앙일보)", 300)):
    lot = as_by.get(name)
    if not lot:
        fails.append(f"안산시 표본 주차장 없음: {name}")
    elif price_for(lot, 30, "weekday").get("amount") != want:
        fails.append(f"안산시 30분 요금 불일치: {name} → {price_for(lot, 30, 'weekday')} (기대 {want})")
# 수암봉: 1시간 1,000원 · 2시간 2,200원 · 3시간 4,000원 (2시간까지 2급지, 이후 1급지)
as_sm = as_by.get("수암봉")
if not as_sm:
    fails.append("안산시 수암봉 카드 없음")
else:
    for minutes, want in ((60, 1000), (120, 2200), (180, 4000)):
        r = price_for(as_sm, minutes, "sat")
        if r.get("state") != "paid" or r.get("amount") != want:
            fails.append(f"안산시 수암봉 {minutes}분 요금 불일치: {r} (기대 {want})")
    if price_for(as_sm, 120, "weekday")["state"] != "closed":
        fails.append("안산시 수암봉이 평일에 유료로 계산됨(주말·공휴일만 유료)")
# 시청부설: 20분 이내 무료, 1시간 1,000원 / 와~스타디움: 3시간 무료, 3시간 10분 300원
as_ch = as_by.get("시청부설주차장")
if not as_ch:
    fails.append("안산시 시청부설 카드 없음")
else:
    r20, r60 = price_for(as_ch, 20, "weekday"), price_for(as_ch, 60, "weekday")
    if not (r20["state"] == "free" and r60.get("amount") == 1000):
        fails.append(f"안산시 시청부설 요금 불일치: 20분 {r20} / 60분 {r60}")
as_st = as_by.get("와~스타디움부설주차장")
if not as_st:
    fails.append("안산시 와~스타디움 카드 없음")
else:
    r180, r190 = price_for(as_st, 180, "weekday"), price_for(as_st, 190, "weekday")
    if not (r180["state"] == "free" and r190.get("amount") == 300):
        fails.append(f"안산시 와~스타디움 요금 불일치: 180분 {r180} / 190분 {r190}")
# 지하철 환승 주차장(2·3급지 중복급지)은 카드에 3급지 안내가 있어야 한다
as_transfer = [l["name"] for l in as_cards if l.get("notice") and "환승" in l["notice"]]
if len(as_transfer) < 10 or "상록수역환승주차장" not in as_transfer:
    fails.append(f"안산시 환승 주차장 안내가 예상과 다름({len(as_transfer)}곳): {as_transfer}")
# 화물차고지(월 정기권 전용)는 0원이 아니라 요금 미상(정기권 전용)으로 표시
as_ticket = sorted(l["name"] for l in as_cards if l["fee"].get("ticket_only"))
if as_ticket != sorted(["부곡동 화물전용주차장", "월피동 화물주차장", "팔곡동 화물차고지"]):
    fails.append(f"안산시 월 정기권 전용 주차장이 예상과 다름: {as_ticket}")
# 노상은 무료 1곳 + 유료 14곳
as_st_free = [l for l in as_street if l["fee"]["type"] == "무료"]
as_st_paid = [l for l in as_street if l["fee"]["type"] == "유료"]
if (len(as_st_free), len(as_st_paid)) != (1, 14):
    fails.append(f"안산시 노상 무료/유료 수가 자료와 다름(무료 {len(as_st_free)}·유료 {len(as_st_paid)})")
# 시·도시공사 두 제공기관 행이 겹쳐도 카드가 중복되지 않아야 한다(유료 카드 이름 기준)
as_dup = [k for k, v in Counter(l["name"] for l in as_paid).items() if v > 1]
if as_dup:
    fails.append(f"안산시 유료 카드 이름 중복(제공기관 중복 행 혼입 의심): {as_dup[:3]}")
# 시 페이지: 급지 요금표(1~4급지)·계산기·목록 / 구 페이지 2개(계산기) / 동 페이지 15개 / 노상 페이지
as_hub = DIST / "parking" / "gyeonggi" / "ansan" / "index.html"
if not as_hub.exists():
    fails.append("안산시 시 페이지 없음")
else:
    hub_html = as_hub.read_text()
    for need, label in (("급지별 주차요금표", "급지 요금표"),
                        ("1급지", "1급지 행"), ("2급지", "2급지 행"), ("3급지", "3급지 행"),
                        ("4급지", "4급지 행"), ("수암봉", "수암봉 안내"), ("지하철 환승 주차장", "환승 안내"),
                        ("ansan-sangrok/", "상록구 링크")):
        if need not in hub_html:
            fails.append(f"안산시 시 페이지에 {label} 없음")
    if hub_html.count('class="card lot') != 0:
        fails.append("안산시 시 페이지에 카드가 그려짐(구 페이지로 나뉘어야 함)")
    for slug, gu in (("ansan-sangrok", "상록구"), ("ansan-danwon", "단원구")):
        page = DIST / "parking" / "gyeonggi" / slug / "index.html"
        if not page.exists():
            fails.append(f"안산시 {gu} 페이지 없음")
            continue
        html_gu = page.read_text()
        if f"{gu} 공영주차장" not in html_gu:
            fails.append(f"안산시 {gu} 페이지 제목에 구 이름 없음")
        if 'class="calc' not in html_gu:
            fails.append(f"안산시 {gu} 페이지에 요금 계산기 없음")
        want_cards = len([l for l in as_cards if l["gu"] == gu])
        if html_gu.count('class="card lot') != want_cards:
            fails.append(f"안산시 {gu} 카드 수 불일치({html_gu.count('class="card lot')} vs {want_cards})")
# 동 페이지는 구 페이지 아래에 있다(ansan-sangrok/<동>/, ansan-danwon/<동>/). 카드 3곳 이상인 동만 만든다.
as_root = DIST / "parking" / "gyeonggi" / "ansan"
as_dong_pages = []
for slug_g in ("ansan-sangrok", "ansan-danwon"):
    g = DIST / "parking" / "gyeonggi" / slug_g
    if g.exists():
        as_dong_pages += sorted(q.parent.name for q in g.rglob("index.html") if q.parent != g)
as_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in as_cards if l.get("dong")).items() if n >= 3)
if sorted(as_dong_pages) != sorted(as_expect):
    fails.append(f"안산시 동 페이지 구성이 다름: {as_dong_pages} ≠ {as_expect}")
as_street_page = as_root / "street-parking" / "index.html"
if not as_street_page.exists():
    fails.append("안산시 노상주차장 페이지 없음(street-parking)")
else:
    as_rows = len(re.findall(r"<tr><td>", as_street_page.read_text()))
    if as_rows < len(as_street):
        fails.append(f"안산시 노상 페이지 행 {as_rows} < 구간 {len(as_street)}")

# 시흥시: 「시흥시 주차장 설치 및 관리 조례」 별표1(2026-05-07 시행) — 1~3급지, 노외만 1일 주차요금.
#   · 2시간까지는 최초 30분 기본요금 뒤 10분당, 2시간을 넘기면 10분당 요율이 올라간다(1급지 300→400원).
#   · 공휴일 무료 개방이 원칙이고, 오이도·삼미시장·신천천·월곶·배다리선착장은 명절 연휴만 무료다.
SH_OFF = {1: (800, 300, 400, 8000, 70000), 2: (500, 200, 300, 5000, 50000), 3: (300, 100, 200, 3000, 30000)}
sh_cards = [l for l in LOTS if l.get("city") == "시흥시" and l.get("list_mode") == "card"]
sh_street = [l for l in LOTS if l.get("city") == "시흥시" and l.get("list_mode") == "street"]
if not sh_cards:
    fails.append("시흥시 카드 데이터가 없음")
sh_paid = [l for l in sh_cards if l["fee"]["type"] == "유료"]
sh_free = [l for l in sh_cards if l["fee"]["type"] == "무료"]
sh_bad = []
for l in sh_paid:
    g = l["fee"]["grade"]
    if g not in SH_OFF:
        sh_bad.append(f'{l["name"]}(급지 {g})')
        continue
    base, unit, over, day, month = SH_OFF[g]
    f = l["fee"]
    steps = f.get("steps") or []
    if (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"], f.get("daily_fee"), f.get("cap_fee")) != \
            (30, base, 10, unit, day, None):
        sh_bad.append(f'{l["name"]}(요금 {f["base_fee"]}/{f["unit_fee"]}/{f.get("daily_fee")})')
    elif len(steps) != 2 or steps[0]["unit_fee"] != unit or steps[1]["unit_fee"] != over:
        sh_bad.append(f'{l["name"]}(2시간 초과 할증 {[x["unit_fee"] for x in steps]})')
    elif f.get("monthly") != month:
        sh_bad.append(f'{l["name"]}(월 정기권 {f.get("monthly")})')
if sh_bad:
    fails.append(f"시흥시 유료 주차장 요금이 조례 별표1과 다름 {len(sh_bad)}곳 {sh_bad[:3]}")
if sorted({l["fee"]["grade"] for l in sh_paid}) != [1, 2, 3]:
    fails.append(f"시흥시 유료 주차장 급지가 1~3급지가 아님: {sorted({l['fee']['grade'] for l in sh_paid})}")
if len([l for l in sh_free if not (l["free_days"]["sat"] and l["free_days"]["sun"])]):
    fails.append("시흥시 무료 주차장이 주말 무료로 표시되지 않음")
sh_sun_charged = sorted(l["name"] for l in sh_cards if l["fee"]["type"] == "유료" and not l["free_days"]["sun"])
if sh_sun_charged != ["배다리 선착장"]:
    fails.append(f"시흥시 공휴일 무료 개방 제외 주차장이 예상과 다름: {sh_sun_charged}")
sh_dup = [k for k, v in Counter(l["name"] for l in sh_cards).items() if v > 1]
if sh_dup:
    fails.append(f"시흥시 카드 이름 중복(같은 지번 중복 행 혼입 의심): {sh_dup[:3]}")
sh_st_free = [l for l in sh_street if l["fee"]["type"] == "무료"]
sh_st_paid = [l for l in sh_street if l["fee"]["type"] == "유료"]
if (len(sh_st_free), len(sh_st_paid)) != (21, 8):
    fails.append(f"시흥시 노상 무료/유료 수가 자료와 다름(무료 {len(sh_st_free)}·유료 {len(sh_st_paid)})")
if [l for l in sh_st_paid if l["fee"].get("daily_fee") or l["fee"].get("cap_fee")]:
    fails.append("시흥시 노상 구간에 1일 주차요금(상한)이 붙음 — 조례상 노상은 시간제만")
sh_root = DIST / "parking" / "gyeonggi" / "siheung"
sh_hub = sh_root / "index.html"
if not sh_hub.exists():
    fails.append("시흥시 시 페이지 없음")
else:
    sh_html = sh_hub.read_text()
    for label in ("시흥시 급지별 주차요금표", "1급지", "2급지", "3급지", "2시간 초과",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc'):
        if label not in sh_html:
            fails.append(f"시흥시 시 페이지에 {label} 없음")
    if sh_html.count('class="card lot') != len(sh_cards):
        fails.append(f"시흥시 시 페이지 카드 수 불일치({sh_html.count(chr(34)+'card lot')} vs {len(sh_cards)})")
sh_dong_pages = sorted(q.parent.name for q in sh_root.rglob("index.html")
                       if q.parent.parent == sh_root and q.parent.name != "street-parking")
sh_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in sh_cards if l.get("dong")).items() if n >= 3)
if sh_dong_pages != sh_expect:
    fails.append(f"시흥시 동 페이지 구성이 다름: {sh_dong_pages} ≠ {sh_expect}")
sh_street_page = sh_root / "street-parking" / "index.html"
if not sh_street_page.exists():
    fails.append("시흥시 노상주차장 페이지 없음(street-parking)")
else:
    sh_rows = len(re.findall(r"<tr><td>", sh_street_page.read_text()))
    if sh_rows < len(sh_street):
        fails.append(f"시흥시 노상 페이지 행 {sh_rows} < 구간 {len(sh_street)}")

# 의정부시: 「의정부시 주차장 설치 및 관리 조례」 별표1(2026-01-09 시행) — 기본시간 없이 10분 단위,
#   노외 1~3급지 10분당 300·200·150원, 1일 주차권(12시간) 9,000·5,000·3,000원.
#   대형자동차 전용은 기준요금의 2배, 캠핑카 전용은 등록요금(10분 200원·1일 5,000원·월 84,000원),
#   부설은 「공공시설 부설주차장 운영 조례」 별표3(최초 30분·1시간·3시간 무료 뒤 10분당 300·200원).
UJ_OFF = {1: (300, 9000, 104000), 2: (200, 5000, 56000), 3: (150, 3000, 32000)}
uj_cards = [l for l in LOTS if l.get("city") == "의정부시" and l.get("list_mode") == "card"]
uj_street = [l for l in LOTS if l.get("city") == "의정부시" and l.get("list_mode") == "street"]
if not uj_cards:
    fails.append("의정부시 카드 데이터가 없음")
uj_paid = [l for l in uj_cards if l["fee"]["type"] == "유료"]
uj_free = [l for l in uj_cards if l["fee"]["type"] == "무료"]
uj_big = [l for l in uj_paid if "대형자동차" in l["name"]]
uj_camp = [l for l in uj_paid if "캠핑카" in l["name"]]
uj_fac = [l for l in uj_paid if l["ptype"] == "부설"]
uj_norm = [l for l in uj_paid if l not in uj_big and l not in uj_camp and l not in uj_fac]
uj_bad = []
for l in uj_norm:
    g = l["fee"]["grade"]
    if g not in UJ_OFF:
        uj_bad.append(f'{l["name"]}(급지 {g})')
        continue
    unit, day, month = UJ_OFF[g]
    f = l["fee"]
    if (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"], f.get("daily_fee"), f.get("monthly")) != \
            (10, unit, 10, unit, day, month):
        uj_bad.append(f'{l["name"]}(요금 {f["base_min"]}분 {f["base_fee"]}원·{f["unit_fee"]}원·'
                      f'일 {f.get("daily_fee")}·월 {f.get("monthly")})')
if uj_bad:
    fails.append(f"의정부시 유료 주차장 요금이 조례 별표1과 다름 {len(uj_bad)}곳 {uj_bad[:3]}")
uj_grades = {l["fee"]["grade"] for l in uj_paid if l["fee"].get("grade")}
if sorted(uj_grades) != [1, 2, 3]:
    fails.append(f"의정부시 유료 주차장 급지가 1~3급지가 아님: {sorted(uj_grades)}")
uj_big_bad = [l["name"] for l in uj_big
              if (l["fee"]["unit_fee"], l["fee"]["daily_fee"], l["fee"].get("monthly")) != (400, 10000, 112000)]
if uj_big_bad:
    fails.append(f"의정부시 대형자동차 전용 요금(2배)이 아님: {uj_big_bad}")
uj_camp_bad = [l["name"] for l in uj_camp
               if (l["fee"]["unit_fee"], l["fee"]["daily_fee"], l["fee"].get("monthly")) != (200, 5000, 84000)]
if uj_camp_bad:
    fails.append(f"의정부시 캠핑카 전용 요금이 등록값과 다름: {uj_camp_bad}")
uj_fac_bad = [f'{l["name"]}({l["fee"].get("free_min")}분·{l["fee"].get("unit_fee")}원·{l["fee"].get("daily_fee")})'
              for l in uj_fac
              if l["fee"].get("free_min") not in (30, 60, 180)
              or l["fee"].get("unit_fee") not in (200, 300)
              or l["fee"].get("daily_fee") not in (5000, 7000)]
if uj_fac_bad:
    fails.append(f"의정부시 부설주차장 요금이 부설 조례 별표3과 다름: {uj_fac_bad}")
if len([l for l in uj_free if not (l["free_days"]["sat"] and l["free_days"]["sun"])]):
    fails.append("의정부시 무료 주차장이 주말 무료로 표시되지 않음")
if len(uj_cards) != 68:
    fails.append(f"의정부시 카드 수가 예상(68)과 다름: {len(uj_cards)}")
if len(uj_street) != 13 or [l for l in uj_street if l["fee"]["type"] != "무료"]:
    fails.append(f"의정부시 노상 13구간이 모두 무료가 아님: {len(uj_street)}구간")
uj_dup = [k for k, v in Counter(l["name"] for l in uj_cards).items() if v > 1]
if uj_dup:
    fails.append(f"의정부시 카드 이름 중복: {uj_dup[:3]}")
uj_root = DIST / "parking" / "gyeonggi" / "uijeongbu"
uj_hub = uj_root / "index.html"
if not uj_hub.exists():
    fails.append("의정부시 시 페이지 없음")
else:
    uj_html = uj_hub.read_text()
    for label in ("의정부시 급지별 주차요금표", "1급지", "2급지", "3급지", "10분당",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc', "부설주차장", "유료 운영시간"):
        if label not in uj_html:
            fails.append(f"의정부시 시 페이지에 {label} 없음")
    if uj_html.count('class="card lot') != len(uj_cards):
        fails.append(f"의정부시 시 페이지 카드 수 불일치({uj_html.count(chr(34)+'card lot')} vs {len(uj_cards)})")
uj_dong_pages = sorted(q.parent.name for q in uj_root.rglob("index.html")
                       if q.parent.parent == uj_root and q.parent.name != "street-parking")
uj_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in uj_cards if l.get("dong")).items() if n >= 3)
if uj_dong_pages != uj_expect:
    fails.append(f"의정부시 동 페이지 구성이 다름: {uj_dong_pages} ≠ {uj_expect}")
uj_street_page = uj_root / "street-parking" / "index.html"
if not uj_street_page.exists():
    fails.append("의정부시 노상주차장 페이지 없음(street-parking)")
else:
    uj_rows = len(re.findall(r"<tr><td>", uj_street_page.read_text()))
    if uj_rows < len(uj_street):
        fails.append(f"의정부시 노상 페이지 행 {uj_rows} < 구간 {len(uj_street)}")

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
