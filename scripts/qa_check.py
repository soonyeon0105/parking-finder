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
                 "안양", "안양도시공사", "만안구", "동안구", "평택", "평택도시공사"),
    "yongin": ("수원", "수원도시공사", "성남", "성남도시개발공사", "영통구", "권선구", "수정구", "중원구", "분당구",
               "안양", "안양도시공사", "만안구", "동안구", "평택", "평택도시공사"),
    # 화성시는 2026-03-01 4개 구(만세·효행·병점·동탄) 체제 — 다른 도시의 구·자료·문구가 섞이면 실패
    "hwaseong": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
                 "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
                 "처인구", "기흥구", "수지구", "안양", "안양도시공사", "만안구", "동안구",
                 "평택", "평택도시공사"),
    # 안양시는 만안·동안 2개 구 — 다른 도시의 구·자료·문구가 섞이면 실패
    "anyang": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
               "화성", "화성도시공사", "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구",
               "분당구", "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
               "평택", "평택도시공사"),
    # 평택시는 자치구가 없다 — 다른 도시의 구·자료·문구가 섞이면 실패
    "pyeongtaek": ("수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
                   "화성", "화성도시공사", "안양", "안양도시공사",
                   "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
                   "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
                   "만안구", "동안구"),
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
