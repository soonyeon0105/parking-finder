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
# 김포시는 자치구가 없다 — 다른 도시 페이지에 김포 자료가 섞이면 실패.
GIMPO_TOKENS = ("김포", "김포도시관리공사", "김포시청", "김포 스마트 주차포털")
# 파주시는 자치구가 없다 — 다른 도시 페이지에 파주 자료가 섞이면 실패.
PAJU_TOKENS = ("파주", "파주시청", "파주도시관광공사", "파주파킹", "파주시 통합주차 포털")
GWANGJU_TOKENS = ("광주", "광주시청", "광주도시관리공사", "통합주차관리", "광주시 주차장 설치 및 관리 조례")
for _k in list(MIX):
    MIX[_k] = (MIX[_k] + GOYANG_TOKENS + NAMYANGJU_TOKENS + ANSAN_TOKENS + SIHEUNG_TOKENS
               + UIJEONGBU_TOKENS + GIMPO_TOKENS + PAJU_TOKENS + GWANGJU_TOKENS)
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
MIX["gimpo"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사", "남양주", "남양주도시공사", "원패스파킹",
    "안산", "안산도시공사", "시흥", "시흥도시공사", "시흥공영주차", "의정부", "의정부도시공사",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구", "덕양구", "일산동구", "일산서구",
)
# 파주시 페이지에는 다른 도시 자료가 섞이면 실패(파주는 구가 없다).
MIX["paju"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사", "남양주", "남양주도시공사", "원패스파킹",
    "안산", "안산도시공사", "시흥", "시흥도시공사", "시흥공영주차", "의정부", "의정부도시공사",
    "김포", "김포도시관리공사",
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
# 광주시(경기도) 페이지에는 다른 도시 자료가 섞이면 실패(광주는 구가 없다).
MIX["gwangju"] = (
    "수원", "수원도시공사", "성남", "성남도시개발공사", "용인", "용인도시공사",
    "화성", "화성도시공사", "안양", "안양도시공사", "평택", "평택도시공사",
    "부천", "부천도시공사", "고양", "고양도시관리공사", "남양주", "남양주도시공사", "원패스파킹",
    "안산", "안산도시공사", "시흥", "시흥도시공사", "시흥공영주차", "의정부", "의정부도시공사",
    "김포", "김포도시관리공사", "파주", "파주도시관광공사", "파주파킹",
    "영통구", "권선구", "팔달구", "장안구", "수정구", "중원구", "분당구",
    "처인구", "기흥구", "수지구", "만세구", "효행구", "병점구", "동탄구",
    "만안구", "동안구", "원미구", "소사구", "오정구", "덕양구", "일산동구", "일산서구",
)
# 하남시는 자치구가 없다 — 다른 도시 페이지에 하남 자료가 섞이면 실패.
#   (‘하남시’로 좁힌다: 광주시 노상 예시에 ‘하남21세기자동차학원 앞’이 들어 있다.)
HANAM_TOKENS = ("하남시", "하남도시공사", "하남시청")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + HANAM_TOKENS
_others = set()
for _k, _v in MIX.items():
    _others.update(t for t in _v if t not in HANAM_TOKENS)
MIX["hanam"] = tuple(sorted(_others))
# 군포시도 자치구가 없다 — 다른 도시 페이지에 군포 자료가 섞이면 실패.
#   (‘산본로데오’처럼 군포에만 있는 이름으로 좁힌다.)
GUNPO_TOKENS = ("군포시", "군포도시공사", "군포시청", "산본로데오")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + GUNPO_TOKENS
_others2 = set()
for _k, _v in MIX.items():
    _others2.update(t for t in _v if t not in GUNPO_TOKENS)
MIX["gunpo"] = tuple(sorted(_others2))
# 광명시도 자치구가 없다 — 다른 도시 페이지에 광명 자료가 섞이면 실패.
#   (‘광명로’(성남 노상)·‘광명교회’(시흥 노상) 같은 도로·상호 이름과 겹치지 않게 ‘광명시’ 단위로 좁힌다.)
GM_TOKENS = ("광명시", "광명도시공사", "광명시청")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + GM_TOKENS
_others3 = set()
for _k, _v in MIX.items():
    _others3.update(t for t in _v if t not in GM_TOKENS)
MIX["gwangmyeong"] = tuple(sorted(_others3))
# 구리시도 자치구가 없다 — 다른 도시 페이지에 구리 자료가 섞이면 실패.
#   (‘구리시’ 단위로 좁힌다: 도로·상호 이름에 ‘구리’가 들어가는 경우와 겹치지 않게.)
GR_TOKENS = ("구리시", "구리도시공사", "구리시청", "옥밭굴공원", "인창유수지")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + GR_TOKENS
_others4 = set()
for _k, _v in MIX.items():
    _others4.update(t for t in _v if t not in GR_TOKENS)
MIX["guri"] = tuple(sorted(_others4))
# 오산시도 자치구가 없다 — 다른 도시 페이지에 오산 자료가 섞이면 실패.
#   (‘오산시’ ‘오산도시공사’처럼 시 단위 이름과 오산에만 있는 ‘필봉산’으로 좁힌다.)
OS_TOKENS = ("오산시", "오산도시공사", "오산시청", "필봉산")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + OS_TOKENS
_others5 = set()
for _k, _v in MIX.items():
    _others5.update(t for t in _v if t not in OS_TOKENS)
MIX["osan"] = tuple(sorted(_others5))
# 이천시도 자치구가 없다 — 다른 도시 페이지에 이천 자료가 섞이면 실패.
#   (‘이천시’ ‘이천시시설관리공단’처럼 시 단위 이름과 이천스마트주차포털로 좁힌다.)
IC_TOKENS = ("이천시", "이천시시설관리공단", "이천스마트주차포털", "설봉공원")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + IC_TOKENS
_others6 = set()
for _k, _v in MIX.items():
    _others6.update(t for t in _v if t not in IC_TOKENS)
MIX["icheon"] = tuple(sorted(_others6))
# 안성시도 자치구가 없다 — 다른 도시 페이지에 안성 자료가 섞이면 실패.
#   (‘안성시’ ‘안성시시설관리공단’처럼 시 단위 이름과 안성맞춤·공도저류지로 좁힌다.)
AS_TOKENS = ("안성시", "안성시시설관리공단", "안성맞춤", "공도저류지", "아양지구")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + AS_TOKENS
_others7 = set()
for _k, _v in MIX.items():
    _others7.update(t for t in _v if t not in AS_TOKENS)
MIX["anseong"] = tuple(sorted(_others7))
# 양주시도 자치구가 없다 — 다른 도시 페이지에 양주 자료가 섞이면 실패.
#   (‘양주시’는 ‘남양주시’에 들어 있어 쓰지 않고, 양주에만 있는 이름으로 좁힌다.)
#   (‘양주도시공사’는 ‘남양주도시공사’에, ‘양주시’는 ‘남양주시’에 들어 있어 쓰지 않는다.)
YJ_TOKENS = ("덕계역", "장흥관광지", "가석지구", "기산저수지", "옥정호수공원",
             "광적복개", "덕정주공상가")
for _k in list(MIX):
    MIX[_k] = tuple(MIX[_k]) + YJ_TOKENS
_others8 = set()
for _k, _v in MIX.items():
    _others8.update(t for t in _v if t not in YJ_TOKENS)
MIX["yangju"] = tuple(sorted(_others8))
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

# 김포시: 「김포시 주차장 조례」 별표1(2026-09-28 시행) — 기본 30분 뒤 10분 단위,
#   유료 노외 1급지 30분 600원·10분당 300원·1일 7,000원, 2급지 300·100·3,500원,
#   유료 노외 공영주차장에 ‘최초 1시간 무료’(김포시 정책, 2027-04-30까지) 적용.
GP_OFF = {1: (600, 300, 7000), 2: (300, 100, 3500)}
gp_cards = [l for l in LOTS if l.get("city") == "김포시" and l.get("list_mode") == "card"]
gp_street = [l for l in LOTS if l.get("city") == "김포시" and l.get("list_mode") == "street"]
if not gp_cards:
    fails.append("김포시 카드 데이터가 없음")
gp_paid = [l for l in gp_cards if l["fee"]["type"] == "유료"]
gp_free = [l for l in gp_cards if l["fee"]["type"] == "무료"]
gp_bad = []
for l in gp_paid:
    g = l["fee"]["grade"]
    if g not in GP_OFF:
        gp_bad.append(f'{l["name"]}(급지 {g})')
        continue
    base, unit, day = GP_OFF[g]
    f = l["fee"]
    if (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"], f.get("daily_fee")) \
            != (30, base, 10, unit, day) or f.get("free_min") not in (None, 10):
        gp_bad.append(f'{l["name"]}(요금 {f["base_min"]}분 {f["base_fee"]}원·{f["unit_fee"]}원·'
                      f'일 {f.get("daily_fee")}·최초 {f.get("free_min")}분)')
if gp_bad:
    fails.append(f"김포시 유료 주차장 요금이 조례 별표1과 다름 {len(gp_bad)}곳 {gp_bad[:3]}")
# 계산 결과: 최초 1시간은 0원, 2시간 1,500원, 4시간 5,100원, 24시간은 1일 주차요금 7,000원(상한).
from build_site import price_for as _pf  # noqa: E402
gp_price_bad = []
for l in gp_paid:
    for mins, want in ((60, "free"), (120, 1500), (240, 5100), (1440, 7000)):
        r = _pf(l, mins, "weekday")
        if want == "free":
            if r.get("state") != "free":
                gp_price_bad.append(f'{l["name"]} {mins}분 {r}')
        elif r.get("state") != "paid" or r.get("amount") != want:
            gp_price_bad.append(f'{l["name"]} {mins}분 {r}')
if gp_price_bad:
    fails.append(f"김포시 최초 1시간 무료 계산이 다름 {len(gp_price_bad)}건 {gp_price_bad[:3]}")
gp_no_free_hour = [l["name"] for l in gp_paid if l["fee"].get("deduct_min") != 60]
if gp_no_free_hour:
    fails.append(f"김포시 유료 노외에 ‘최초 1시간 무료’가 없음: {gp_no_free_hour[:3]}")
gp_free_hour_on_street = [l["name"] for l in gp_street if l["fee"].get("deduct_min")]
if gp_free_hour_on_street:
    fails.append(f"김포시 노상에 1시간 무료가 잘못 적용됨: {gp_free_hour_on_street[:3]}")
if any(l["name"] == "하성공영주차장" and l["fee"]["type"] != "미상" for l in gp_cards):
    fails.append("김포 하성공영주차장은 요금표 미공개라 ‘요금 정보 미상’이어야 함")
gp_street_paid = [l for l in gp_street if l["fee"]["type"] == "유료"]
if len(gp_street_paid) != len(gp_street):
    fails.append(f"김포시 노상 {len(gp_street)}구간이 모두 유료가 아님")
if any(not l["free_days"]["sun"] for l in gp_street):
    fails.append("김포시 노상 구간에 일요일·공휴일 무료 표시가 없음")
if len(gp_free) != 2:
    fails.append(f"김포시 무료 주차장이 2곳이 아님: {len(gp_free)}곳")
if len([l for l in gp_cards if l.get("city") == "김포시" and not l.get("dong")]):
    fails.append("김포시 카드에 동·읍·면이 없는 주차장이 있음")
gp_dup = [k for k, v in Counter(l["name"] for l in gp_cards).items() if v > 1]
if gp_dup:
    fails.append(f"김포시 카드 이름 중복: {gp_dup[:3]}")
gp_root = DIST / "parking" / "gyeonggi" / "gimpo"
gp_hub = gp_root / "index.html"
if not gp_hub.exists():
    fails.append("김포시 시 페이지 없음")
else:
    gp_html = gp_hub.read_text()
    for label in ("김포시 급지별 주차요금표", "1급지", "2급지", "최초 1시간 무료", "00:00~09:00",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc', "노상주차장", "북변 공영주차장"):
        if label not in gp_html:
            fails.append(f"김포시 시 페이지에 {label} 없음")
    if gp_html.count('class="card lot') != len(gp_cards):
        fails.append(f"김포시 시 페이지 카드 수 불일치({gp_html.count(chr(34)+'card lot')} vs {len(gp_cards)})")
gp_dong_pages = sorted(q.parent.name for q in gp_root.rglob("index.html")
                       if q.parent.parent == gp_root and q.parent.name != "street-parking")
gp_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in gp_cards if l.get("dong")).items() if n >= 3)
if gp_dong_pages != gp_expect:
    fails.append(f"김포시 읍·면·동 페이지 구성이 다름: {gp_dong_pages} ≠ {gp_expect}")
gp_street_page = gp_root / "street-parking" / "index.html"
if not gp_street_page.exists():
    fails.append("김포시 노상주차장 페이지 없음(street-parking)")
else:
    gp_rows = len(re.findall(r"<tr><td>", gp_street_page.read_text()))
    if gp_rows < len(gp_street):
        fails.append(f"김포시 노상 페이지 행 {gp_rows} < 구간 {len(gp_street)}")

# 파주시: 「파주시 주차장 설치 및 관리 조례」 제3조제1항 별표1(포털 요금안내 2026-11-17 확인)
#   1급지 30분 600원·10분당 250원·1일 9,000원, 2급지 500·200·8,000원, 3급지 400·150·7,000원.
#   주차장별 기본시간(80·90·150분)과 최초 무료시간(10~120분)은 포털 등록값, 관광지 4곳은 종일 2,000원.
PJ_FEES = {1: (600, 250, 9000), 2: (500, 200, 8000), 3: (400, 150, 7000)}
# 포털이 주차장별로 다르게 설정한 기본시간·기본요금·간격·1일 요금(괄호는 1일 상한).
PJ_SPECIAL_BASE = {(80, 1000, 20, 500): 7000, (90, 500, 10, 200): 8000,
                   (90, 400, 10, 150): 7000, (150, 500, 10, 200): 8000}
PJ_TOURIST = {"감악산 제3주차장", "감악산 제5주차장", "마장호수 제1주차장", "임진각 주차장"}
pj_cards = [l for l in LOTS if l.get("city") == "파주시" and l.get("list_mode") == "card"]
pj_street = [l for l in LOTS if l.get("city") == "파주시" and l.get("list_mode") == "street"]
if not pj_cards:
    fails.append("파주시 카드 데이터가 없음")
pj_paid = [l for l in pj_cards if l["fee"]["type"] == "유료"]
pj_free = [l for l in pj_cards if l["fee"]["type"] == "무료"]
pj_bad = []
for l in pj_paid:
    f = l["fee"]
    if l["name"] in PJ_TOURIST:
        if not f.get("flat_day") or f.get("grade") or f["base_fee"] != 2000 or f.get("daily_fee") != 2000:
            pj_bad.append(f'{l["name"]}(관광지 종일요금 아님 {f["base_fee"]})')
        continue
    if f["grade"] not in PJ_FEES:
        pj_bad.append(f'{l["name"]}(급지 {f["grade"]})')
        continue
    base, unit, day = PJ_FEES[f["grade"]]
    key = (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"])
    if key == (30, base, 10, unit):
        want_day = day
    elif key in PJ_SPECIAL_BASE:
        want_day = PJ_SPECIAL_BASE[key]
    else:
        pj_bad.append(f'{l["name"]}(기본 {f["base_min"]}분 {f["base_fee"]}원·{f["unit_min"]}분당 {f["unit_fee"]}원)')
        continue
    if f.get("daily_fee") != want_day:
        pj_bad.append(f'{l["name"]}(1일 {f.get("daily_fee")} ≠ {want_day})')
if pj_bad:
    fails.append(f"파주시 유료 주차장 요금이 조례·포털 값과 다름 {len(pj_bad)}곳 {pj_bad[:3]}")
pj_deduct_bad = [f'{l["name"]}({l["fee"].get("deduct_min")})' for l in pj_paid
                 if l["fee"].get("deduct_min") not in (10, 15, 20, 60, 120)]
if pj_deduct_bad:
    fails.append(f"파주시 최초 무료시간이 포털 값(10·15·20·60·120분)과 다름: {pj_deduct_bad[:3]}")
# 계산 표본 — 조례·포털 값으로 손으로 계산한 값
from build_site import price_for as _pj_pf  # noqa: E402
PJ_SAMPLES = {
    "금촌2": [(30, 600), (120, 2600), (240, 5600), (1440, 9000)],
    "가람마을공원 공영주차장": [(60, "free"), (120, 500), (240, 2300), (1440, 8000)],
    "광탄경매시장": [(60, "free"), (120, 400), (240, 1750), (1440, 7000)],
    "시청주차장": [(60, "free"), (120, 1000), (240, 3500)],
    "봉일천 공영주차장": [(120, "free"), (240, 500)],
    "감악산 제3주차장": [(120, 2000), (1440, 2000)],
    "문산고가다리": [(120, 2600), (1440, 9000)],
}
pj_price_bad = []
for name, cases in PJ_SAMPLES.items():
    lot = next((l for l in pj_paid if l["name"] == name), None)
    if not lot:
        pj_price_bad.append(f"{name} 없음")
        continue
    for mins, want in cases:
        r = _pj_pf(lot, mins, "weekday")
        if want == "free":
            if r.get("state") != "free":
                pj_price_bad.append(f"{name} {mins}분 {r}")
        elif r.get("state") != "paid" or r.get("amount") != want:
            pj_price_bad.append(f"{name} {mins}분 {r} ≠ {want}")
if pj_price_bad:
    fails.append(f"파주시 요금 계산이 조례·포털 값과 다름 {len(pj_price_bad)}건 {pj_price_bad[:3]}")
# 주말 무료 개방: 관광지·포털 미등록(문산고가다리)을 뺀 유료 노외는 토·일 모두 무료
pj_paid_free_weekend = [l for l in pj_paid
                        if l["name"] not in PJ_TOURIST and l["name"] != "문산고가다리"]
if len([l for l in pj_paid_free_weekend if not (l["free_days"]["sat"] and l["free_days"]["sun"])]):
    fails.append("파주시 유료 노외에 토·일 무료 개방 표시가 없음")
if len([l for l in pj_paid if l["name"] in PJ_TOURIST and (l["free_days"]["sat"] or l["free_days"]["sun"])]):
    fails.append("파주시 관광지 주차장이 주말 무료로 잘못 표시됨")
if len(pj_cards) != 96:
    fails.append(f"파주시 카드 수가 예상(96)과 다름: {len(pj_cards)}")
if len(pj_free) != 65:
    fails.append(f"파주시 무료 주차장이 65곳이 아님: {len(pj_free)}곳")
if len(pj_street) != 64:
    fails.append(f"파주시 노상 구간이 64곳이 아님: {len(pj_street)}")
if len([l for l in pj_street if l["fee"]["type"] == "유료"]) != 19:
    fails.append("파주시 유료 노상 구간이 19곳이 아님")
if len([l for l in pj_cards if not l.get("dong")]):
    fails.append("파주시 카드에 읍·면·동이 없는 주차장이 있음")
pj_dup = [k for k, v in Counter(l["name"] for l in pj_cards).items() if v > 1]
if pj_dup:
    fails.append(f"파주시 카드 이름 중복: {pj_dup[:3]}")
if any(l["name"] in ("놀이구름 제1주차장", "(주기장) 월롱임시공영주기장") for l in pj_cards):
    fails.append("파주시 카드에 넣지 않기로 한 포털 주차장이 들어감")
pj_names = {l["name"] for l in pj_cards}
for extra in PJ_TOURIST | {"시청주차장", "시의회주차장"}:
    if extra not in pj_names:
        fails.append(f"파주시 카드에 {extra} 없음")
pj_root = DIST / "parking" / "gyeonggi" / "paju"
pj_hub = pj_root / "index.html"
if not pj_hub.exists():
    fails.append("파주시 시 페이지 없음")
else:
    pj_html = pj_hub.read_text()
    for label in ("파주시 급지별 주차요금표", "1급지", "2급지", "3급지", "10분당",
                  "월 정기권", "종일 2,000원", "환승요금", "토요일·일요일·공휴일",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc', "시청주차장"):
        if label not in pj_html:
            fails.append(f"파주시 시 페이지에 {label} 없음")
    if pj_html.count('class="card lot') != len(pj_cards):
        fails.append(f"파주시 시 페이지 카드 수 불일치({pj_html.count(chr(34)+'card lot')} vs {len(pj_cards)})")
pj_dong_pages = sorted(q.parent.name for q in pj_root.rglob("index.html")
                       if q.parent.parent == pj_root and q.parent.name != "street-parking")
pj_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in pj_cards if l.get("dong")).items() if n >= 3)
if pj_dong_pages != pj_expect:
    fails.append(f"파주시 읍·면·동 페이지 구성이 다름: {pj_dong_pages} ≠ {pj_expect}")
pj_street_page = pj_root / "street-parking" / "index.html"
if not pj_street_page.exists():
    fails.append("파주시 노상주차장 페이지 없음(street-parking)")
else:
    pj_rows = len(re.findall(r"<tr><td>", pj_street_page.read_text()))
    if pj_rows < len(pj_street):
        fails.append(f"파주시 노상 페이지 행 {pj_rows} < 구간 {len(pj_street)}")

# 광주시(경기도): 「광주시 주차장 설치 및 관리 조례」 제5조제1항 별표1(시행 2026-02-23)
#   · 1급지 30분 800원·10분당 300원·1일 7,000원, 2급지 500·200·5,000원.
#   · 포털(광주도시관리공사 통합주차관리)의 ‘최초 10분 미만(회차) 무료’를 적용(free_min=10).
#   · 노상·노외 같은 요금표, 유료 12곳(1급지 7·2급지 5), 나머지 43곳과 노상 10구간은 무료.
GJ_FEES = {1: (800, 300, 7000), 2: (500, 200, 5000)}
gj_cards = [l for l in LOTS if l.get("city") == "광주시" and l.get("list_mode") == "card"]
gj_street = [l for l in LOTS if l.get("city") == "광주시" and l.get("list_mode") == "street"]
if not gj_cards:
    fails.append("광주시 카드 데이터가 없음")
gj_paid = [l for l in gj_cards if l["fee"]["type"] == "유료"]
gj_free = [l for l in gj_cards if l["fee"]["type"] == "무료"]
gj_bad = []
for l in gj_paid:
    g = l["fee"]["grade"]
    f = l["fee"]
    if g not in GJ_FEES:
        gj_bad.append(f'{l["name"]}(급지 {g})')
        continue
    base, unit, day = GJ_FEES[g]
    if (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"], f.get("daily_fee"),
            f.get("free_min")) != (30, base, 10, unit, day, 10):
        gj_bad.append(f'{l["name"]}(요금 {f["base_min"]}분 {f["base_fee"]}원·{f["unit_fee"]}원·'
                      f'일 {f.get("daily_fee")}·최초 {f.get("free_min")}분)')
if gj_bad:
    fails.append(f"광주시 유료 주차장 요금이 조례 별표1과 다름 {len(gj_bad)}곳 {gj_bad[:3]}")
# 계산 결과: 10분은 무료(회차), 30분 기본요금, 2시간 3,500·2,300원, 24시간은 1일 주차요금 상한.
gj_price_bad = []
for l in gj_paid:
    base, unit, day = GJ_FEES[l["fee"]["grade"]]
    want2h = base + 9 * unit
    for mins, want in ((10, "free"), (30, base), (120, want2h), (1440, day)):
        r = _pf(l, mins, "weekday")
        if want == "free":
            if r.get("state") != "free":
                gj_price_bad.append(f'{l["name"]} {mins}분 {r}')
        elif r.get("state") != "paid" or r.get("amount") != want:
            gj_price_bad.append(f'{l["name"]} {mins}분 {r} ≠ {want}')
if gj_price_bad:
    fails.append(f"광주시 요금 계산이 조례·포털 값과 다름 {len(gj_price_bad)}건 {gj_price_bad[:3]}")
# 감면: 경차·경증장애인 60%, 국가유공자 4시간(240분) 면제, 중증장애인·성실납세자 100%.
gj_disc = {d["label"]: (d["rate"], d.get("exempt_min") or 0) for d in
           next(c for c in CITIES if c["city"] == "광주시").get("discounts") or []}
if (gj_disc.get("경차·경증장애인 60%") or (None,))[0] != 0.6:
    fails.append("광주시 감면표에 경차·경증장애인 60%가 없음")
if (gj_disc.get("국가유공자 4시간 면제 후 50%") or (None, None))[1] != 240:
    fails.append("광주시 감면표의 국가유공자 면제 시간이 240분이 아님")
if (gj_disc.get("중증장애인·성실납세자 100%") or (None,))[0] != 1.0:
    fails.append("광주시 감면표에 중증장애인·성실납세자 100%가 없음")
gj_sv = [l for l in gj_paid if l["name"] == "경안시장 공영주차장"]
if not gj_sv or _pf(gj_sv[0], 120, "weekday").get("amount") != 3500:
    fails.append("경안시장(1급지) 2시간 요금이 3,500원이 아님")
gj_grades = Counter(l["fee"]["grade"] for l in gj_paid)
if dict(gj_grades) != {1: 7, 2: 5}:
    fails.append(f"광주시 유료 급지 구성이 다름: {dict(gj_grades)} ≠ {{1: 7, 2: 5}}")
if len(gj_paid) != 12:
    fails.append(f"광주시 유료 주차장이 12곳이 아님: {len(gj_paid)}곳")
if len(gj_free) != 33:
    fails.append(f"광주시 무료 노외 주차장이 33곳이 아님: {len(gj_free)}곳")
if len(gj_cards) != 45 or len(gj_street) != 10:
    fails.append(f"광주시 카드·노상 구성이 다름: 카드 {len(gj_cards)} · 노상 {len(gj_street)}")
if len([l for l in gj_street if l["fee"]["type"] != "무료"]):
    fails.append("광주시 노상 10구간이 모두 무료가 아님")
if len([l for l in gj_cards if not l.get("dong")]):
    fails.append("광주시 카드에 읍·면·동이 없는 주차장이 있음")
gj_dup = [k for k, v in Counter(l["name"] for l in gj_cards).items() if v > 1]
if gj_dup:
    fails.append(f"광주시 카드 이름 중복: {gj_dup[:3]}")
if [l["name"] for l in gj_cards if l["name"] in ("송정동 임시(1) 공영주차장", "송정동 임시(2) 공영주차장")].__len__() != 2:
    fails.append("광주시 ‘송정동 임시(1)·(2)’가 한 곳으로 묶임(이름 중복 제거 오류)")
gj_root = DIST / "parking" / "gyeonggi" / "gwangju"
gj_hub = gj_root / "index.html"
if not gj_hub.exists():
    fails.append("광주시 시 페이지 없음")
else:
    gj_html = gj_hub.read_text()
    for label in ("광주시 급지별 주차요금표", "1급지", "2급지", "10분당", "최초 10분", "월 정기권",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc', "노상주차장", "경안시장 공영주차장"):
        if label not in gj_html:
            fails.append(f"광주시 시 페이지에 {label} 없음")
    if gj_html.count('class="card lot') != len(gj_cards):
        fails.append(f"광주시 시 페이지 카드 수 불일치({gj_html.count(chr(34)+'card lot')} vs {len(gj_cards)})")
    if "광주광역시 주차장" in gj_html:
        fails.append("광주시 페이지에 광주광역시 자료가 섞임")
    if "경기도 광주시" not in gj_html:
        fails.append("광주시 페이지에 ‘경기도 광주시’ 표기가 없음(광주광역시와 구분)")
gj_dong_pages = sorted(q.parent.name for q in gj_root.rglob("index.html")
                       if q.parent.parent == gj_root and q.parent.name != "street-parking")
gj_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in gj_cards if l.get("dong")).items() if n >= 3)
if gj_dong_pages != gj_expect:
    fails.append(f"광주시 읍·면·동 페이지 구성이 다름: {gj_dong_pages} ≠ {gj_expect}")
if not gj_dong_pages:
    fails.append("광주시 읍·면·동 페이지가 없음")
gj_street_page = gj_root / "street-parking" / "index.html"
if not gj_street_page.exists():
    fails.append("광주시 노상주차장 페이지 없음(street-parking)")
else:
    gj_rows = len(re.findall(r"<tr><td>", gj_street_page.read_text()))
    if gj_rows < len(gj_street):
        fails.append(f"광주시 노상 페이지 행 {gj_rows} < 구간 {len(gj_street)}")

# 하남시: 「하남시 주차장 조례」 [별표 1] 공영주차장 주차요금표(제3조제1항, 시행 2023-08-04)
#   · 1~3급지 30분 800·600·400원 + 10분당 300·200·100원, 1일 주차권 노상 5,000·4,000·3,000원 / 노외 7,000·6,000·4,000원.
#   · 주거지 전용 13곳은 주간 무료 개방(fee.type=무료, category=resident), 정기권 전용 3곳은 요금 미상.
HN_OFF = {1: (800, 300, 7000), 2: (600, 200, 6000), 3: (400, 100, 4000)}
HN_ST = {1: (800, 300, 5000), 2: (600, 200, 4000), 3: (400, 100, 3000)}
hn_cards = [l for l in LOTS if l.get("city") == "하남시" and l.get("list_mode") == "card"]
hn_street = [l for l in LOTS if l.get("city") == "하남시" and l.get("list_mode") == "street"]
if not hn_cards:
    fails.append("하남시 카드 데이터가 없음")
hn_paid = [l for l in hn_cards if l["fee"]["type"] == "유료"]
hn_free = [l for l in hn_cards if l["fee"]["type"] == "무료"]
hn_resident = [l for l in LOTS if l.get("city") == "하남시" and l["fee"].get("category") == "resident"]
hn_ticket = [l for l in LOTS if l.get("city") == "하남시" and l["fee"].get("ticket_only")]
hn_bad = []
for l in hn_paid:
    g = l["fee"]["grade"]
    table = HN_ST if l["ptype"] == "노상" else HN_OFF
    if g not in table:
        hn_bad.append(f'{l["name"]}(급지 {g})')
        continue
    base, unit, day = table[g]
    f = l["fee"]
    if f.get("flat_day"):
        if (f["base_fee"], f.get("daily_fee")) != (2000, 2000):
            hn_bad.append(f'{l["name"]}(종일 {f["base_fee"]}원)')
        continue
    if (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"], f.get("daily_fee")) != (30, base, 10, unit, day):
        hn_bad.append(f'{l["name"]}(요금 {f["base_min"]}분 {f["base_fee"]}원·{f["unit_min"]}분 {f["unit_fee"]}원·'
                      f'일 {f.get("daily_fee")})')
if hn_bad:
    fails.append(f"하남시 유료 주차장 요금이 조례 별표1과 다름 {len(hn_bad)}곳 {hn_bad[:3]}")
# 계산 결과: 30분 기본요금, 2시간 = 기본 + 9×10분 요율, 24시간은 1일 주차요금 상한.
hn_price_bad = []
for l in hn_paid:
    if l["fee"].get("flat_day"):
        for mins in (30, 120, 1440):
            r = _pf(l, mins, "weekday")
            if r.get("state") != "paid" or r.get("amount") != 2000:
                hn_price_bad.append(f'{l["name"]} {mins}분 {r}')
        continue
    base, unit, day = (HN_ST if l["ptype"] == "노상" else HN_OFF)[l["fee"]["grade"]]
    for mins, want in ((30, base), (120, base + 9 * unit), (1440, day)):
        r = _pf(l, mins, "weekday")
        if r.get("state") != "paid" or r.get("amount") != want:
            hn_price_bad.append(f'{l["name"]} {mins}분 {r} ≠ {want}')
if hn_price_bad:
    fails.append(f"하남시 요금 계산이 조례 값과 다름 {len(hn_price_bad)}건 {hn_price_bad[:3]}")
hn_disc = {d["label"]: (d["rate"], d.get("exempt_min") or 0) for d in
           next(c for c in CITIES if c["city"] == "하남시").get("discounts") or []}
if (hn_disc.get("경차·저공해 50%") or (None,))[0] != 0.5:
    fails.append("하남시 감면표에 경차·저공해 50%가 없음")
if (hn_disc.get("부제운행 20%") or (None,))[0] != 0.2:
    fails.append("하남시 감면표에 부제운행 20%가 없음")
if (hn_disc.get("국가유공자·장애인 2시간 면제 후 50%") or (None, None))[1] != 120:
    fails.append("하남시 감면표의 국가유공자·장애인 면제 시간이 120분이 아님")
if (hn_disc.get("모범·성실납세자 100%") or (None,))[0] != 1.0:
    fails.append("하남시 감면표에 모범·성실납세자 100%가 없음")
# 카드(노외) 유료 14곳 = 1급지 6 · 2급지 3 · 3급지 5, 노상 유료 2곳(에코1단지 2급지·검단산 3급지)
if dict(Counter(l["fee"]["grade"] for l in hn_paid)) != {1: 6, 2: 3, 3: 5}:
    fails.append(f"하남시 카드 유료 급지 구성이 다름: {dict(Counter(l['fee']['grade'] for l in hn_paid))} ≠ {{1: 6, 2: 3, 3: 5}}")
if dict(Counter(l["fee"]["grade"] for l in LOTS
                if l.get("city") == "하남시" and l["fee"]["type"] == "유료")) != {1: 6, 2: 4, 3: 6}:
    fails.append("하남시 전체 유료 급지 구성이 {1: 6, 2: 4, 3: 6}이 아님")
if len(hn_cards) != 20 or len(hn_street) != 17:
    fails.append(f"하남시 카드·노상 구성이 다름: 카드 {len(hn_cards)} · 노상 {len(hn_street)}")
if len(hn_paid) != 14 or len(hn_free) != 5 or len([l for l in hn_cards if l['fee'].get('ticket_only')]) != 1:
    fails.append(f"하남시 카드 요금 구분이 다름: 유료 {len(hn_paid)}·무료 {len(hn_free)}·"
                 f"정기권전용 {len([l for l in hn_cards if l['fee'].get('ticket_only')])}")
if len(hn_ticket) != 3:
    fails.append(f"하남시 정기권 전용 주차장이 3곳이 아님: {len(hn_ticket)}곳")
if len([l for l in LOTS if l.get("city") == "하남시" and l["fee"]["type"] == "무료"]) != 18:
    fails.append("하남시 무료(주거지 전용 포함) 주차장이 18곳이 아님")
if len(hn_resident) != 13:
    fails.append(f"하남시 주거지 전용 구역이 13곳이 아님: {len(hn_resident)}곳")
if sum(l["spaces"] or 0 for l in hn_cards) != 1391 or sum(l["spaces"] or 0 for l in hn_street) != 613:
    fails.append(f"하남시 구획 합계가 다름: 노외 {sum(l['spaces'] or 0 for l in hn_cards)} · "
                 f"노상 {sum(l['spaces'] or 0 for l in hn_street)}")
if len([l for l in hn_cards if not l.get("dong")]):
    fails.append("하남시 카드에 동이 없는 주차장이 있음")
hn_dup = [k for k, v in Counter(l["name"] for l in hn_cards).items() if v > 1]
if hn_dup:
    fails.append(f"하남시 카드 이름 중복: {hn_dup[:3]}")
if not [l for l in hn_cards if l["name"] == "미사중앙제1주차장"]:
    fails.append("하남시 카드에 미사중앙제1주차장(공사 직영) 없음")
if [l for l in hn_cards if l["name"] == "미사중앙제1주차장" and not l["hours"]["weekday"]["24h"]]:
    fails.append("미사중앙제1주차장이 24시간 운영으로 등록되지 않음")
hn_root = DIST / "parking" / "gyeonggi" / "hanam"
hn_hub = hn_root / "index.html"
if not hn_hub.exists():
    fails.append("하남시 시 페이지 없음")
else:
    hn_html = hn_hub.read_text()
    for label in ("하남시 급지별 주차요금표", "1급지", "2급지", "3급지", "10분당", "최초 30분",
                  "월 정기권", "주거지 전용", "노상주차장", "평일 2시간 기준 가장 저렴한 곳",
                  'class="calc', "미사중앙제1주차장", "검단산"):
        if label not in hn_html:
            fails.append(f"하남시 시 페이지에 {label} 없음")
    if hn_html.count('class="card lot') != len(hn_cards):
        fails.append(f"하남시 시 페이지 카드 수 불일치({hn_html.count(chr(34)+'card lot')} vs {len(hn_cards)})")
hn_dong_pages = sorted(q.parent.name for q in hn_root.rglob("index.html")
                       if q.parent.parent == hn_root and q.parent.name != "street-parking")
hn_expect = sorted(__import__("build_site").dong_slug(d)
                   for d, n in Counter(l.get("dong") for l in hn_cards if l.get("dong")).items() if n >= 3)
if hn_dong_pages != hn_expect:
    fails.append(f"하남시 동 페이지 구성이 다름: {hn_dong_pages} ≠ {hn_expect}")
if not hn_dong_pages:
    fails.append("하남시 동 페이지가 없음")
hn_street_page = hn_root / "street-parking" / "index.html"
if not hn_street_page.exists():
    fails.append("하남시 노상주차장 페이지 없음(street-parking)")
else:
    hn_rows = len(re.findall(r"<tr><td>", hn_street_page.read_text()))
    if hn_rows < len(hn_street):
        fails.append(f"하남시 노상 페이지 행 {hn_rows} < 구간 {len(hn_street)}")

# 군포시: 「군포시 주차장 설치 및 관리 조례」 [별표 1](시행 2025-01-01, 조례 제2236호)
#   · 1~3급지 최초 15분 무료 + 30분 800·600·300원 + 10분당 400·200·200원 + 1일 최대 9,000·6,000·4,000원.
#   · 특수관리대상(중심·산본로데오·산본시장·군포역환승·군포역1길)은 별도 누진표, 2급지 10곳은 월 정기권 전용.
GPO_GRADE = {1: (800, 400, 9000), 2: (600, 200, 6000), 3: (300, 200, 4000)}
gpo_cards = [l for l in LOTS if l.get("city") == "군포시" and l.get("list_mode") == "card"]
gpo_street = [l for l in LOTS if l.get("city") == "군포시" and l.get("list_mode") == "street"]
if not gpo_cards:
    fails.append("군포시 카드 데이터가 없음")
gpo_paid = [l for l in gpo_cards if l["fee"]["type"] == "유료"]
gpo_free = [l for l in gpo_cards if l["fee"]["type"] == "무료"]
gpo_ticket = [l for l in LOTS if l.get("city") == "군포시" and l["fee"].get("ticket_only")]
gpo_special = [l for l in gpo_paid if l["fee"].get("grade") is None]   # 특수관리대상(급지 없음·별도 요금)
gpo_bad = []
for l in gpo_paid:
    f = l["fee"]
    if f.get("steps") or f.get("grade") is None:
        continue
    base, unit, day = GPO_GRADE.get(f["grade"], (None, None, None))
    if base is None:
        gpo_bad.append(f'{l["name"]}(급지 {f["grade"]})')
        continue
    if (f["base_min"], f["base_fee"], f["unit_min"], f["unit_fee"], f.get("free_min")) != (30, base, 10, unit, 15):
        gpo_bad.append(f'{l["name"]}(요금 {f["base_min"]}분 {f["base_fee"]}원·{f["unit_min"]}분 '
                       f'{f["unit_fee"]}원·최초 {f.get("free_min")}분)')
    if l["name"] not in ("산본천공영주차장", "바위백이공영주차장") and f.get("daily_fee") != day:
        gpo_bad.append(f'{l["name"]}(1일 최대 {f.get("daily_fee")} ≠ {day})')
if gpo_bad:
    fails.append(f"군포시 유료 주차장 요금이 조례 별표1과 다름 {len(gpo_bad)}곳 {gpo_bad[:3]}")
# 계산 결과: 최초 15분 0원, 30분 기본요금, 2시간 = 기본 + 9×10분 요율, 하루는 1일 최대 상한.
gpo_price_bad = []
for l in gpo_paid:
    f = l["fee"]
    if f.get("steps") or f.get("grade") is None:
        continue
    base, unit, day = GPO_GRADE[f["grade"]]
    r15 = _pf(l, 15, "weekday")
    if r15.get("state") != "free":
        gpo_price_bad.append(f'{l["name"]} 15분 {r15}')
    for mins, want in ((30, base), (120, min(base + 9 * unit, day or 10 ** 9))):
        r = _pf(l, mins, "weekday")
        if r.get("state") != "paid" or r.get("amount") != want:
            gpo_price_bad.append(f'{l["name"]} {mins}분 {r} ≠ {want}')
    if l["name"] not in ("산본천공영주차장", "바위백이공영주차장"):
        r = _pf(l, 1440, "weekday")
        if r.get("state") != "paid" or r.get("amount") != day:
            gpo_price_bad.append(f'{l["name"]} 1440분 {r} ≠ {day}')
if gpo_price_bad:
    fails.append(f"군포시 요금 계산이 조례 값과 다름 {len(gpo_price_bad)}건 {gpo_price_bad[:3]}")
# 특수관리대상 누진: 중심 1시간 2,000·2시간 5,600·3시간 11,600원, 산본로데오 최초 1시간 무료,
#   산본시장 1시간 1,200·2시간 4,800원, 군포역환승 2시간 3,600원(모두 군포도시공사 안내 값).
gpo_special_bad = []
_expect = {"중심1공영주차장": [(60, 2000), (120, 5600), (180, 11600)],
           "산본로데오공영주차장": [(60, 0), (120, 2400)],
           "산본시장공영주차장": [(60, 1200), (120, 4800), (180, 10200)],
           "산본시장제2공영주차장": [(120, 4800)],
           "군포역환승공영주차장": [(120, 3600)],
           "군포역1길공영주차장": [(30, 0), (120, 3600)]}
for _name, _rows in _expect.items():
    _lot = next((l for l in LOTS if l.get("city") == "군포시" and l["name"] == _name), None)
    if not _lot:
        gpo_special_bad.append(f"{_name} 없음")
        continue
    for _m, _want in _rows:
        _r = _pf(_lot, _m, "weekday")
        _got = 0 if _r.get("state") == "free" else _r.get("amount")
        if _got != _want:
            gpo_special_bad.append(f"{_name} {_m}분 {_got} ≠ {_want}")
if gpo_special_bad:
    fails.append(f"군포시 특수관리대상 누진 요금이 공사 안내와 다름 {len(gpo_special_bad)}건 {gpo_special_bad[:3]}")
# 1일 주차권을 운영하지 않는 2곳은 상한 없이 계산한다(0원이 아니라 ‘요금 미상’도 아니다).
for _n in ("산본천공영주차장", "바위백이공영주차장"):
    _lot = next((l for l in LOTS if l.get("city") == "군포시" and l["name"] == _n), None)
    if _lot and _lot["fee"].get("daily_fee"):
        fails.append(f"군포시 {_n}에 1일 주차요금이 남아 있음")
gpo_disc = {d["label"]: (d["rate"], d.get("exempt_min") or 0) for d in
            next(c for c in CITIES if c["city"] == "군포시").get("discounts") or []}
if (gpo_disc.get("경차·전기차 50%") or (None,))[0] != 0.5:
    fails.append("군포시 감면표에 경차·전기차 50%가 없음")
if (gpo_disc.get("유공자·장애인 2시간 면제 후 50%") or (None, None))[1] != 120:
    fails.append("군포시 감면표의 유공자·장애인 면제 시간이 120분이 아님")
if (gpo_disc.get("긴급·공무 차량 면제") or (None,))[0] != 1.0:
    fails.append("군포시 감면표에 긴급·공무 차량 면제가 없음")
if len(gpo_cards) != 50 or len(gpo_street) != 29:
    fails.append(f"군포시 카드·노상 구성이 다름: 카드 {len(gpo_cards)} · 노상 {len(gpo_street)}")
if len(gpo_paid) != 29 or len(gpo_free) != 11 or len([l for l in gpo_cards if l["fee"].get("ticket_only")]) != 10:
    fails.append(f"군포시 카드 요금 구분이 다름: 유료 {len(gpo_paid)}·무료 {len(gpo_free)}·"
                 f"정기권전용 {len([l for l in gpo_cards if l['fee'].get('ticket_only')])}")
if dict(Counter(l["fee"]["grade"] for l in gpo_paid if l["fee"].get("grade"))) != {1: 7, 2: 14, 3: 1}:
    fails.append("군포시 카드 유료 급지 구성이 {1: 7, 2: 14, 3: 1}이 아님")
if len(gpo_special) != 7:
    fails.append(f"군포시 특수관리대상(누진) 카드가 7곳이 아님: {len(gpo_special)}곳")
if len(gpo_ticket) != 11:
    fails.append(f"군포시 월 정기권 전용 주차장이 11곳이 아님: {len(gpo_ticket)}곳")
if sum(l["spaces"] or 0 for l in gpo_cards) != 3536 or sum(l["spaces"] or 0 for l in gpo_street) != 974:
    fails.append(f"군포시 구획 합계가 다름: 노외 {sum(l['spaces'] or 0 for l in gpo_cards)} · "
                 f"노상 {sum(l['spaces'] or 0 for l in gpo_street)}")
if len([l for l in gpo_cards if not l.get("dong")]):
    fails.append("군포시 카드에 동이 없는 주차장이 있음")
gpo_dup = [k for k, v in Counter(l["name"] for l in gpo_cards).items() if v > 1]
if gpo_dup:
    fails.append(f"군포시 카드 이름 중복: {gpo_dup[:3]}")
# 야간(평일·토 00:01~07:59, 일 22:01~09:59) 무료 표기가 카드에 남아 있어야 한다.
if len([l for l in gpo_cards if l.get("free_hour_note")]) < 20:
    fails.append("군포시 카드의 무료 시간 안내가 20곳 미만임")
gpo_root = DIST / "parking" / "gyeonggi" / "gunpo"
gpo_hub = gpo_root / "index.html"
if not gpo_hub.exists():
    fails.append("군포시 시 페이지 없음")
else:
    gpo_html = gpo_hub.read_text()
    for label in ("군포시 급지별 주차요금표", "1급지", "2급지", "3급지", "10분당", "최초 15분",
                  "월 정기권", "특수관리대상·별도 요금 주차장", "산본로데오", "군포역환승",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc', "군포도시공사"):
        if label not in gpo_html:
            fails.append(f"군포시 시 페이지에 {label} 없음")
    if gpo_html.count('class="card lot') != len(gpo_cards):
        fails.append(f"군포시 시 페이지 카드 수 불일치({gpo_html.count(chr(34)+'card lot')} vs {len(gpo_cards)})")
if "&lt;b&gt;" in gpo_hub.read_text() if gpo_hub.exists() else False:
    fails.append("군포시 시 페이지에 이스케이프된 <b> 태그가 보임")
gpo_dong_pages = sorted(q.parent.name for q in gpo_root.rglob("index.html")
                        if q.parent.parent == gpo_root and q.parent.name != "street-parking")
gpo_expect = sorted(__import__("build_site").dong_slug(d)
                    for d, n in Counter(l.get("dong") for l in gpo_cards if l.get("dong")).items() if n >= 3)
if gpo_dong_pages != gpo_expect:
    fails.append(f"군포시 동 페이지 구성이 다름: {gpo_dong_pages} ≠ {gpo_expect}")
if not gpo_dong_pages:
    fails.append("군포시 동 페이지가 없음")
gpo_street_page = gpo_root / "street-parking" / "index.html"
if not gpo_street_page.exists():
    fails.append("군포시 노상주차장 페이지 없음(street-parking)")
else:
    gpo_rows = len(re.findall(r"<tr><td>", gpo_street_page.read_text()))
    if gpo_rows < len(gpo_street):
        fails.append(f"군포시 노상 페이지 행 {gpo_rows} < 구간 {len(gpo_street)}")

# 광명시: 「광명시 주차장 설치 및 관리 조례」 [별표 1](2023-11-10 개정, 2026-08-14 일부개정)
#   · 1급지 최초 30분 800원 → 10분당 300원 → 2시간 초과 10분당 400원, 노외 1일 13,000원.
#   · 2급지(옥길동·학온동) 500·200·300원·1일 8,000원, 전통시장 2시간 초과 10분당 500원(1일 한도 없음).
gmy_cards = [l for l in LOTS if l.get("city") == "광명시" and l.get("list_mode") == "card"]
gmy_street = [l for l in LOTS if l.get("city") == "광명시" and l.get("list_mode") == "street"]
if not gmy_cards:
    fails.append("광명시 카드 데이터가 없음")
gmy_paid = [l for l in gmy_cards if l["fee"]["type"] == "유료"]
gmy_free = [l for l in gmy_cards if l["fee"]["type"] == "무료"]
gmy_ticket = [l for l in gmy_cards if l["fee"].get("ticket_only")]
gmy_bad = [l["name"] for l in gmy_paid
           if l["name"] != "광명동(전통시장) 지하"
           and (l["fee"]["base_min"] != 30 or l["fee"]["base_fee"] != 800
           or l["fee"]["unit_min"] != 10 or l["fee"]["unit_fee"] != 300
                or [st["unit_fee"] for st in (l["fee"].get("steps") or [])] != [300, 400])]
if gmy_bad:
    fails.append(f"광명시 유료 주차장 요금이 조례 별표1과 다름 {len(gmy_bad)}곳 {gmy_bad[:3]}")
gmy_day_bad = [l["name"] for l in gmy_paid
               if l["name"] != "광명동(전통시장) 지하" and l["fee"]["daily_fee"] != 13_000]
if gmy_day_bad:
    fails.append(f"광명시 1일 주차권이 13,000원이 아님 {gmy_day_bad[:3]}")
gmy_market = next((l for l in gmy_cards if l["name"] == "광명동(전통시장) 지하"), None)
if not gmy_market:
    fails.append("광명시 전통시장 지하 카드가 없음")
elif [st["unit_fee"] for st in (gmy_market["fee"].get("steps") or [])] != [300, 500]         or gmy_market["fee"]["daily_fee"]:
    fails.append("광명시 전통시장 요금(2시간 초과 500원·1일 한도 없음)이 아님")
# 계산 규칙: 2시간 3,500원 · 4시간 5,900원 · 24시간 13,000원(전통시장은 69,500원, 상한 없음)
_gmy_p = next((l for l in gmy_paid if l["name"] == "광북"), None)
if not _gmy_p:
    fails.append("광명시 광북 카드가 없음")
else:
    _want = [(120, 3500), (180, 5900), (240, 8300), (1440, 13000)]
    _bad = [(m, price_for(_gmy_p, m, "weekday").get("amount")) for m, v in _want
            if price_for(_gmy_p, m, "weekday").get("amount") != v]
    if _bad:
        fails.append(f"광명시 요금 계산이 조례 값과 다름 {_bad[:3]}")
if gmy_market and price_for(gmy_market, 1440, "weekday").get("amount") != 69500:
    fails.append(f"광명시 전통시장 24시간 요금이 69,500원이 아님: "
                 f"{price_for(gmy_market, 1440, 'weekday').get('amount')}")
# 감면표: 경차·저공해 50%, 유공자·장애인 2시간 면제 후 50%, 긴급·납세자 면제
_gmy_disc = next(c for c in CITIES if c["city"] == "광명시").get("discounts") or []
if not any(d.get("rate") == 0.5 and (d.get("exempt_min") or 0) == 120 for d in _gmy_disc):
    fails.append("광명시 감면표의 유공자·장애인 면제 시간이 120분이 아님")
if not any(d.get("rate") == 0.5 and not d.get("exempt_min") for d in _gmy_disc):
    fails.append("광명시 감면표에 경차·저공해 50%가 없음")
if not any(d.get("rate") == 1.0 for d in _gmy_disc):
    fails.append("광명시 감면표에 긴급·모범납세자 면제가 없음")
# 구성: 카드 22곳(유료 17·무료 2·정기권 전용 3) · 노상 10구간 · 구획 1,708면 / 716면
if len(gmy_cards) != 22 or len(gmy_street) != 10:
    fails.append(f"광명시 카드·노상 구성이 다름: 카드 {len(gmy_cards)} · 노상 {len(gmy_street)}")
if len(gmy_paid) != 17 or len(gmy_free) != 2 or len(gmy_ticket) != 3:
    fails.append(f"광명시 카드 요금 구분이 다름: 유료 {len(gmy_paid)}·무료 {len(gmy_free)}·"
                 f"정기권전용 {len(gmy_ticket)}")
if dict(Counter(l["fee"]["grade"] for l in gmy_paid if l["fee"].get("grade"))) != {1: 16}:
    fails.append("광명시 카드 유료 급지 구성이 {1: 16}이 아님")
if sum(l["spaces"] or 0 for l in gmy_cards) != 1708 or sum(l["spaces"] or 0 for l in gmy_street) != 716:
    fails.append(f"광명시 구획 합계가 다름: 노외 {sum(l['spaces'] or 0 for l in gmy_cards)} · "
                 f"노상 {sum(l['spaces'] or 0 for l in gmy_street)}")
if len([l for l in gmy_cards if not l.get("dong")]):
    fails.append("광명시 카드에 동이 없는 주차장이 있음")
_gmy_dup = [k for k, v in Counter(l["name"] for l in gmy_cards).items() if v > 1]
if _gmy_dup:
    fails.append(f"광명시 카드 이름 중복: {_gmy_dup[:3]}")
for _n in ("광명동(전통시장) 지하", "안현철골", "새빛공원", "광명시청 철산동지하"):
    if not any(l["name"] == _n for l in gmy_cards):
        fails.append(f"광명시 카드에 {_n} 없음")
# 노상 주말 무료 개방 6구간 + 새빛공원
if len([l for l in LOTS if l.get("city") == "광명시" and l["free_days"].get("sun")
        and l["fee"]["type"] != "무료"]) != 7:
    fails.append("광명시 일요일 무료 개방 주차장이 7곳이 아님")
gmy_root = DIST / "parking" / "gyeonggi" / "gwangmyeong"
gmy_hub = gmy_root / "index.html"
if not gmy_hub.exists():
    fails.append("광명시 시 페이지 없음")
else:
    gmy_html = gmy_hub.read_text()
    for label in ("광명시 급지별 주차요금표", "1급지", "2급지", "10분당", "2시간 초과",
                  "30분", "월 정기권", "별도 요금 주차장", "광명동(전통시장) 지하",
                  "평일 2시간 기준 가장 저렴한 곳", 'class="calc', "광명도시공사",
                  "경기도 광명시 28행"):
        if label not in gmy_html:
            fails.append(f"광명시 시 페이지에 {label} 없음")
    if gmy_html.count('class="card lot') != len(gmy_cards):
        fails.append(f"광명시 시 페이지 카드 수 불일치({gmy_html.count(chr(34)+'card lot')} vs {len(gmy_cards)})")
    if "&lt;b&gt;" in gmy_html:
        fails.append("광명시 시 페이지에 이스케이프된 <b> 태그가 보임")
    if "옥길동" not in gmy_html:
        fails.append("광명시 시 페이지에 2급지 대상 지역(옥길동) 안내 없음")
gmy_dong_pages = sorted(q.parent.name for q in gmy_root.rglob("index.html")
                        if q.parent.parent == gmy_root and q.parent.name != "street-parking")
gmy_expect = sorted(__import__("build_site").dong_slug(d)
                    for d, n in Counter(l.get("dong") for l in gmy_cards if l.get("dong")).items()
                    if n >= 3)
if gmy_dong_pages != gmy_expect:
    fails.append(f"광명시 동 페이지 구성이 다름: {gmy_dong_pages} ≠ {gmy_expect}")
if len(gmy_dong_pages) != 3:
    fails.append(f"광명시 동 페이지가 3개가 아님: {gmy_dong_pages}")
gmy_street_page = gmy_root / "street-parking" / "index.html"
if not gmy_street_page.exists():
    fails.append("광명시 노상주차장 페이지 없음(street-parking)")
else:
    gmy_rows = len(re.findall(r"<tr><td>", gmy_street_page.read_text()))
    if gmy_rows < len(gmy_street):
        fails.append(f"광명시 노상 페이지 행 {gmy_rows} < 구간 {len(gmy_street)}")

# 구리시: 「구리시 주차장 조례」 [별표 1] 공영주차장 주차요금표(별표/서식에서 확인)
#   · 노외 1급지 30분 600원·10분당 200원·1일 8,000원·월 70,000원, 2급지 500·200·6,000·50,000원,
#     3급지 400·100·5,000·40,000원 — 노외는 1일 주차권이 시간 요금의 상한이다.
#   · 노상 1급지 30분 700원·10분당 300원·1일 9,000원(적용 10시간), 2급지 500·200·6,000원, 월 정기권 없음.
gri_cards = [l for l in LOTS if l.get("city") == "구리시" and l.get("list_mode") == "card"]
gri_street = [l for l in LOTS if l.get("city") == "구리시" and l.get("list_mode") == "street"]
if not gri_cards:
    fails.append("구리시 카드 데이터가 없음")
gri_paid = [l for l in gri_cards if l["fee"]["type"] == "유료"]
gri_free = [l for l in gri_cards if l["fee"]["type"] != "유료"]
if gri_free:
    fails.append(f"구리시 카드에 유료가 아닌 주차장이 있음: {[l['name'] for l in gri_free][:3]}")
_gr_want = {1: (600, 200, 8_000, 70_000), 2: (500, 200, 6_000, 50_000), 3: (400, 100, 5_000, 40_000)}
_gr_bad = [(l["name"], l["fee"]["grade"], l["fee"]["base_fee"], l["fee"]["unit_fee"],
            l["fee"]["daily_fee"], l["fee"]["monthly"]) for l in gri_paid
           if (l["fee"]["base_min"], l["fee"]["unit_min"]) != (30, 10)
           or _gr_want.get(l["fee"]["grade"]) != (l["fee"]["base_fee"], l["fee"]["unit_fee"],
                                                 l["fee"]["daily_fee"], l["fee"]["monthly"])]
if _gr_bad:
    fails.append(f"구리시 노외 요금이 조례 별표1과 다름 {_gr_bad[:3]}")
_gr_st_want = {1: (700, 300, 9_000), 2: (500, 200, 6_000)}
_gr_st_bad = [(l["name"], l["fee"]["grade"], l["fee"]["base_fee"], l["fee"]["unit_fee"],
               l["fee"]["daily_fee"], l["fee"]["monthly"]) for l in gri_street
              if _gr_st_want.get(l["fee"]["grade"]) != (l["fee"]["base_fee"], l["fee"]["unit_fee"],
                                                        l["fee"]["daily_fee"]) or l["fee"]["monthly"]]
if _gr_st_bad:
    fails.append(f"구리시 노상 요금이 조례 별표1과 다름 {_gr_st_bad[:3]}")
# 계산 규칙: 노외 1급지 2시간 2,400·4시간 4,800·24시간 8,000원(1일 상한),
#   노외 3급지 2시간 1,300원, 노상 1급지 2시간 3,400원·24시간 9,000원(1일 주차권 상한)
_gr1 = next((l for l in gri_paid if l["fee"]["grade"] == 1), None)
_gr3 = next((l for l in gri_paid if l["fee"]["grade"] == 3), None)
_gr_st = next((l for l in gri_street if l["fee"]["grade"] == 1), None)
if not (_gr1 and _gr3 and _gr_st):
    fails.append("구리시 1급지·3급지·노상 표본 주차장이 없음")
else:
    for lot, mins, want in ((_gr1, 120, 2_400), (_gr1, 240, 4_800), (_gr1, 1440, 8_000),
                            (_gr3, 120, 1_300), (_gr_st, 120, 3_400), (_gr_st, 1440, 9_000)):
        got = price_for(lot, mins, "weekday").get("amount")
        if got != want:
            fails.append(f"구리시 요금 계산이 조례 값과 다름: {lot['name']} {mins}분 {got} ≠ {want}")
# 일요일·공휴일 무료 개방 9곳(노외 3 + 노상 6)
if len([l for l in LOTS if l.get("city") == "구리시" and l["free_days"].get("sun")]) != 9:
    fails.append("구리시 일요일·공휴일 무료 개방 주차장이 9곳이 아님")
# 감면표: 장애인·유공자 3시간 면제 후 50%, 환경친화 2시간 면제 후 50%, 요일제 20%, 면제
_gr_disc = next(c for c in CITIES if c["city"] == "구리시").get("discounts") or []
if not any(d.get("rate") == 0.5 and (d.get("exempt_min") or 0) == 180 for d in _gr_disc):
    fails.append("구리시 감면표의 장애인·유공자 면제 시간이 180분이 아님")
if not any(d.get("rate") == 0.5 and (d.get("exempt_min") or 0) == 120 for d in _gr_disc):
    fails.append("구리시 감면표의 환경친화 자동차 면제 시간이 120분이 아님")
if not any(d.get("rate") == 0.2 for d in _gr_disc):
    fails.append("구리시 감면표에 승용차 요일제 20%가 없음")
if not any(d.get("rate") == 1.0 for d in _gr_disc):
    fails.append("구리시 감면표에 면제 대상이 없음")
# 구성: 카드 9곳(1급지 3·2급지 5·3급지 1) · 노상 6구간 · 구획 1,518면 / 145면
if len(gri_cards) != 9 or len(gri_street) != 6:
    fails.append(f"구리시 카드·노상 구성이 다름: 카드 {len(gri_cards)} · 노상 {len(gri_street)}")
if dict(Counter(l["fee"]["grade"] for l in gri_paid)) != {1: 3, 2: 5, 3: 1}:
    fails.append(f"구리시 카드 급지 구성이 다름: {dict(Counter(l['fee']['grade'] for l in gri_paid))}")
if sum(l["spaces"] or 0 for l in gri_cards) != 1518 or sum(l["spaces"] or 0 for l in gri_street) != 145:
    fails.append(f"구리시 구획 합계가 다름: 노외 {sum(l['spaces'] or 0 for l in gri_cards)} · "
                 f"노상 {sum(l['spaces'] or 0 for l in gri_street)}")
if len([l for l in gri_cards if not l.get("dong")]) or len([l for l in gri_street if not l.get("dong")]):
    fails.append("구리시 주차장에 동이 없는 곳이 있음")
_gr_dup = [k for k, v in Counter(l["name"] for l in gri_cards).items() if v > 1]
if _gr_dup:
    fails.append(f"구리시 카드 이름 중복: {_gr_dup[:3]}")
for _n in ("제1공영노외주차장", "제6공영노외주차장", "제9공영노외주차장", "제10공영노외주차장"):
    if not any(l["name"] == _n for l in gri_cards):
        fails.append(f"구리시 카드에 {_n} 없음")
gri_root = DIST / "parking" / "gyeonggi" / "guri"
gri_hub = gri_root / "index.html"
if not gri_hub.exists():
    fails.append("구리시 시 페이지 없음")
else:
    gri_html = gri_hub.read_text()
    for label in ("구리시 급지별 주차요금표", "노외주차장", "노상주차장", "1급지", "2급지", "3급지",
                  "10분당", "30분", "1일 주차권", "월 정기권", "평일 2시간 기준 가장 저렴한 곳",
                  'class="calc', "구리도시공사", "인창유수지", "옥밭굴", "경기도 구리시 15행",
                  "공유주차장"):
        if label not in gri_html:
            fails.append(f"구리시 시 페이지에 {label} 없음")
    if gri_html.count('class="card lot') != len(gri_cards):
        fails.append(f"구리시 시 페이지 카드 수 불일치({gri_html.count(chr(34)+'card lot')} vs {len(gri_cards)})")
    if "&lt;b&gt;" in gri_html:
        fails.append("구리시 시 페이지에 이스케이프된 <b> 태그가 보임")
    if "일반주거지역" not in gri_html:
        fails.append("구리시 시 페이지에 급지 기준(일반주거지역) 안내 없음")
gri_dong_pages = sorted(q.parent.name for q in gri_root.rglob("index.html")
                        if q.parent.parent == gri_root and q.parent.name != "street-parking")
if gri_dong_pages != ["sutaek-dong"]:
    fails.append(f"구리시 동 페이지 구성이 다름: {gri_dong_pages} ≠ ['sutaek-dong']")
gri_street_page = gri_root / "street-parking" / "index.html"
if not gri_street_page.exists():
    fails.append("구리시 노상주차장 페이지 없음(street-parking)")
else:
    gri_rows = len(re.findall(r"<tr><td>", gri_street_page.read_text()))
    if gri_rows < len(gri_street):
        fails.append(f"구리시 노상 페이지 행 {gri_rows} < 구간 {len(gri_street)}")

# ---------------------------------------------------------------- 오산시 (T-03 Phase 19)
# 「오산시 주차장 조례」 [별표 1](별표 1 개정 2025-05-22, 조례 시행 2026-05-06)과 오산도시공사
# 주차포털(2026-11-17): 최초 1시간(2시간·1시간 30분) 무료 + 10분당 250·200원(1·2급지),
# 12시간 주차권 6,000·4,000원, 월 정기권 80,000·60,000원, 환승주차장 60% 경감(100원).
os_cards = [l for l in LOTS if l.get("city") == "오산시" and l.get("list_mode") == "card"]
os_paid = [l for l in os_cards if l["fee"]["type"] == "유료"]
os_free = [l for l in os_cards if l["fee"]["type"] == "무료"]
os_by = {l["name"]: l for l in os_cards}
if not os_cards:
    fails.append("오산시 카드 데이터가 없음")
# 구성: 카드 44곳(유료 19·무료 25) · 구획 3,653면 · 동 12개
if len(os_cards) != 44 or len(os_paid) != 19 or len(os_free) != 25:
    fails.append(f"오산시 카드 구성이 다름: 카드 {len(os_cards)} · 유료 {len(os_paid)} · 무료 {len(os_free)}")
if sum(l["spaces"] or 0 for l in os_cards) != 3653:
    fails.append(f"오산시 구획 합계가 다름: {sum(l['spaces'] or 0 for l in os_cards)}")
if len({l.get("dong") for l in os_cards}) != 12 or any(not l.get("dong") for l in os_cards):
    fails.append(f"오산시 동 구성이 다름: {sorted({l.get('dong') for l in os_cards})}")
_os_dup = [k for k, v in Counter(l["name"] for l in os_cards).items() if v > 1]
if _os_dup:
    fails.append(f"오산시 카드 이름 중복: {_os_dup[:3]}")
# 급지·요금 — 별표1 값
_O_FEE = {"운암공영주차장": (1, 60, 250, 6000, 80000),
          "궐동 공영주차장": (2, 60, 200, 4000, 60000),
          "궐동 제3공영주차장": (1, 60, 250, 6000, 80000),
          "오색시장 주차장": (None, 90, 200, None, None),
          "오산천공영주차장": (None, 120, 300, 4000, 60000),
          "독산성입구(동문) 공영주차장": (None, 120, 200, None, 60000),
          "오산역제2환승주차장": (1, 60, 100, 2400, 40000)}
for _n, (_g, _free, _unit, _day, _month) in _O_FEE.items():
    _l = os_by.get(_n)
    if not _l:
        fails.append(f"오산시 카드에 {_n} 없음")
        continue
    _f = _l["fee"]
    if (_f.get("grade"), _f.get("free_min"), _f.get("unit_fee"), _f.get("daily_fee"),
            _f.get("monthly")) != (_g, _free, _unit, _day, _month):
        fails.append(f"오산시 요금이 별표1과 다름: {_n} {_f.get('grade')}/{_f.get('free_min')}/"
                     f"{_f.get('unit_fee')}/{_f.get('daily_fee')}/{_f.get('monthly')}")
# 운암2는 노상 카드(별표1 노상 2급지: 1시간 무료, 2시간까지 100원, 이후 200원)
_os_st = os_by.get("운암2 노상주차장")
if not _os_st or _os_st["ptype"] != "노상" or _os_st["fee"]["unit_fee"] != 100:
    fails.append("오산시 운암2 노상주차장 카드가 노상 2급지로 만들어지지 않음")
if any(l.get("list_mode") == "street" for l in LOTS if l.get("city") == "오산시"):
    fails.append("오산시에 노상 구간(list_mode=street)이 섞여 있음")
# 계산 표본 — 별표1로 직접 계산한 값
for _n, _mins, _want in (("운암공영주차장", 30, 0), ("운암공영주차장", 60, 0),
                         ("운암공영주차장", 120, 1500), ("운암공영주차장", 300, 6000),
                         ("궐동 공영주차장", 120, 1200), ("오산역제2환승주차장", 120, 600),
                         ("오산역제2환승주차장", 1440, 2400), ("오산천공영주차장", 120, 0),
                         ("오색시장 주차장", 120, 600), ("오색시장 주차장", 240, 3600),
                         ("운암2 노상주차장", 120, 600), ("운암2 노상주차장", 180, 1800)):
    _l = os_by.get(_n)
    if not _l:
        continue
    _r = price_for(_l, _mins, "weekday")
    _got = 0 if _r["state"] == "free" else _r.get("amount")
    if _got != _want:
        fails.append(f"오산시 요금 계산이 별표1과 다름: {_n} {_mins}분 {_got} ≠ {_want}")
# 감면표 — 조례 제10조(환승·경차 60%, 전기차 2시간 면제 후 50%, 12시간 면제)
_os_disc = next(c for c in CITIES if c["city"] == "오산시").get("discounts") or []
if not any(d["rate"] == 0.6 for d in _os_disc):
    fails.append("오산시 감면표에 60% 경감(경차·경증장애인·환승)이 없음")
if not any(d["rate"] == 0.5 and d.get("exempt_min") == 120 for d in _os_disc):
    fails.append("오산시 감면표에 전기차 2시간 면제 후 50%가 없음")
if not any(d.get("exempt_min") == 720 for d in _os_disc):
    fails.append("오산시 감면표에 12시간 면제 대상이 없음")
# 주차장 요금표(품질 리포트) — 면수 차이 13곳, 시 요금표 차이 2건
_os_q = next(c for c in CITIES if c["city"] == "오산시").get("quality") or {}
if len(_os_q.get("면수_차이") or []) != 13:
    fails.append(f"오산시 면수 차이가 13곳이 아님: {len(_os_q.get('면수_차이') or [])}")
if len(_os_q.get("시_요금표_차이") or []) != 2:
    fails.append("오산시 시 누리집 요금표 차이가 2건이 아님")
os_root = DIST / "parking" / "gyeonggi" / "osan"
os_hub = os_root / "index.html"
if not os_hub.exists():
    fails.append("오산시 시 페이지 없음")
else:
    os_html = os_hub.read_text()
    for label in ("오산시 급지별 주차요금표", "노외주차장", "노상주차장", "1급지", "2급지",
                  "최초 1시간", "12시간 주차권", "월 야간권", "평일 2시간 기준 가장 저렴한 곳",
                  'class="calc', "오산도시공사", "상업지역", "경기도 오산시 44행", "명절연휴",
                  "부설주차장", "오산역 제1 환승"):
        if label not in os_html:
            fails.append(f"오산시 시 페이지에 {label} 없음")
    if os_html.count('class="card lot') != len(os_cards):
        fails.append(f"오산시 시 페이지 카드 수 불일치({os_html.count(chr(34)+'card lot')} vs {len(os_cards)})")
    if "&lt;b&gt;" in os_html:
        fails.append("오산시 시 페이지에 이스케이프된 <b> 태그가 보임")
    for _t in ("오산시", "오산도시공사"):
        if _t not in os_html:
            fails.append(f"오산시 시 페이지에 {_t} 표기 없음")
os_dong_pages = sorted(q.parent.name for q in os_root.rglob("index.html") if q.parent.parent == os_root)
if os_dong_pages != ["cheonghak-dong", "gwol-dong", "naesammi-dong", "osan-dong", "segyo-dong",
                     "sucheong-dong", "won-dong"]:
    fails.append(f"오산시 동 페이지 구성이 다름: {os_dong_pages}")
if (os_root / "street-parking" / "index.html").exists():
    fails.append("오산시에 노상 전용 페이지가 생김(구간 0 — 빈 페이지)")
for _slug, _n in (("osan-dong", 9), ("won-dong", 8), ("gwol-dong", 6), ("sucheong-dong", 5),
                  ("cheonghak-dong", 3), ("segyo-dong", 3), ("naesammi-dong", 3)):
    _p = os_root / _slug / "index.html"
    if not _p.exists():
        fails.append(f"오산시 동 페이지 없음: {_slug}")
    elif _p.read_text().count('class="card lot') != _n:
        fails.append(f"오산시 {_slug} 카드 수 불일치({_p.read_text().count(chr(34)+'card lot')} ≠ {_n})")


# ---------------------------------------------------------------- 이천시 (T-03 Phase 20)
# 「이천시 주차장 설치 및 관리 조례」 [별표 1](공포 2025-05-16, 경기도이천시조례 제2224호)과
# 이천스마트주차포털 이용안내(2026-11-17): 노외 1급지 30분 600원·10분당 250원·1일 7,000원,
# 2급지 500·200·5,000원, 3급지 400·150·4,000원, 노상 1급지 600·250·7,000원.
ic_cards = [l for l in LOTS if l.get("city") == "이천시" and l.get("list_mode") == "card"]
ic_paid = [l for l in ic_cards if l["fee"]["type"] == "유료"]
ic_free = [l for l in ic_cards if l["fee"]["type"] == "무료"]
ic_by = {l["name"]: l for l in ic_cards}
if not ic_cards:
    fails.append("이천시 카드 데이터가 없음")
# 구성: 카드 28곳(유료 11·무료 17) · 구획 3,537면 · 노상 52구간 1,976면
if len(ic_cards) != 28 or len(ic_paid) != 11 or len(ic_free) != 17:
    fails.append(f"이천시 카드 구성이 다름: 카드 {len(ic_cards)} · 유료 {len(ic_paid)} · 무료 {len(ic_free)}")
if sum(l["spaces"] or 0 for l in ic_cards) != 3537:
    fails.append(f"이천시 구획 합계가 다름: {sum(l['spaces'] or 0 for l in ic_cards)}")
ic_street = [l for l in LOTS if l.get("city") == "이천시" and l.get("list_mode") == "street"]
if len(ic_street) != 52 or sum(l["spaces"] or 0 for l in ic_street) != 1976:
    fails.append(f"이천시 노상 구간이 다름: {len(ic_street)}구간 "
                 f"{sum(l['spaces'] or 0 for l in ic_street)}면")
if len({l.get("dong") for l in ic_cards}) != 11 or any(not l.get("dong") for l in ic_cards):
    fails.append(f"이천시 동 구성이 다름: {sorted({l.get('dong') for l in ic_cards})}")
_ic_dup = [k for k, v in Counter(l["name"] for l in ic_cards).items() if v > 1]
if _ic_dup:
    fails.append(f"이천시 카드 이름 중복: {_ic_dup[:3]}")
# 급지·요금 — 별표1 값(무료시간은 주차포털 이용안내)
_IC_FEE = {"중리천로공영주차장": (1, None, 600, 250, 7000, None),
           "남천상가주차장": (1, 30, 600, 250, 7000, None),
           "창전동 임시 공영주차장": (1, 30, 600, 250, 7000, None),
           "북샛말공영주차장": (2, None, 500, 200, 5000, 60000),
           "사동리 제1공영주차장": (2, None, 500, 200, 5000, 60000),
           "공설운동장공영주차장": (2, 30, 500, 200, 5000, 60000),
           "서희청소년문화센터공영주차장": (2, 120, 500, 200, 5000, 60000),
           "마장택지지구 공영주차장1": (2, None, 500, 200, 5000, None),
           "택시쉼터공영주차장": (3, 60, 400, 150, 4000, 40000)}
for _n, (_g, _free, _base, _unit, _day, _month) in _IC_FEE.items():
    _l = ic_by.get(_n)
    if not _l:
        fails.append(f"이천시 카드에 {_n} 없음")
        continue
    _f = _l["fee"]
    if (_f.get("grade"), _f.get("free_min"), _f.get("base_fee"), _f.get("unit_fee"),
            _f.get("daily_fee"), _f.get("monthly")) != (_g, _free, _base, _unit, _day, _month):
        fails.append(f"이천시 요금이 별표1과 다름: {_n} {_f.get('grade')}/{_f.get('free_min')}/"
                     f"{_f.get('base_fee')}/{_f.get('unit_fee')}/{_f.get('daily_fee')}/{_f.get('monthly')}")
# 마장 제1·2는 기본요금이 최초 60분 500원이다(표준데이터 등록값).
for _n in ("마장택지지구 공영주차장1", "마장택지지구 공영주차장2"):
    _l = ic_by.get(_n)
    if _l and (_l["fee"]["base_min"], _l["fee"]["base_fee"]) != (60, 500):
        fails.append(f"이천시 {_n} 기본요금이 60분 500원이 아님: "
                     f"{_l['fee']['base_min']}/{_l['fee']['base_fee']}")
# 노상은 전부 1급지요, 주말·공휴일 무료 개방(터미널 8-2 제외).
for _l in ic_street:
    if _l["fee"]["type"] == "유료":
        if _l["fee"].get("grade") != 1:
            fails.append(f"이천시 유료 노상 {_l['name']}이 1급지가 아님")
        if _l["name"] == "8-2 터미널공영":
            if _l["free_days"].get("sat") or _l["free_days"].get("sun"):
                fails.append("이천시 터미널 8-2가 주말 무료로 표기됨")
        elif not (_l["free_days"].get("sat") and _l["free_days"].get("sun")):
            fails.append(f"이천시 유료 노상 {_l['name']}의 주말 무료 표기 없음")
# 계산 표본 — 별표1·포털 무료시간으로 직접 계산한 값
for _n, _mins, _want in (("중리천로공영주차장", 30, 600), ("중리천로공영주차장", 120, 2850),
                         ("중리천로공영주차장", 600, 7000), ("남천상가주차장", 30, 0),
                         ("남천상가주차장", 120, 2100), ("북샛말공영주차장", 120, 2300),
                         ("북샛말공영주차장", 480, 5000), ("공설운동장공영주차장", 30, 0),
                         ("공설운동장공영주차장", 120, 1700), ("서희청소년문화센터공영주차장", 120, 0),
                         ("서희청소년문화센터공영주차장", 180, 1100), ("택시쉼터공영주차장", 60, 0),
                         ("택시쉼터공영주차장", 120, 850), ("마장택지지구 공영주차장1", 60, 500),
                         ("마장택지지구 공영주차장1", 120, 1700)):
    _l = ic_by.get(_n)
    if not _l:
        continue
    _r = price_for(_l, _mins, "weekday")
    _got = 0 if _r["state"] == "free" else _r.get("amount")
    if _got != _want:
        fails.append(f"이천시 요금 계산이 별표1과 다름: {_n} {_mins}분 {_got} ≠ {_want}")
# 감면표 — 조례 별표1(중증장애인 2시간·유공자 4시간 면제 후 50%, 요일제 30%, 100% 면제)
_ic_disc = next(c for c in CITIES if c["city"] == "이천시").get("discounts") or []
if not any(d["rate"] == 0.5 and d.get("exempt_min") == 120 for d in _ic_disc):
    fails.append("이천시 감면표에 중증장애인 2시간 면제 후 50%가 없음")
if not any(d["rate"] == 0.5 and d.get("exempt_min") == 240 for d in _ic_disc):
    fails.append("이천시 감면표에 국가유공자 4시간 면제 후 50%가 없음")
if not any(d["rate"] == 0.3 for d in _ic_disc):
    fails.append("이천시 감면표에 승용차 요일제 30%가 없음")
if not any(d["rate"] == 1.0 for d in _ic_disc):
    fails.append("이천시 감면표에 100% 면제 대상이 없음")
# 품질 리포트 — 두 세트 등록 35행, 정기권 차이, 면수 차이
_ic_q = next(c for c in CITIES if c["city"] == "이천시").get("quality") or {}
if len(_ic_q.get("중복제거_행") or []) != 35:
    fails.append(f"이천시 두 세트 등록 정리가 35행이 아님: {len(_ic_q.get('중복제거_행') or [])}")
if len(_ic_q.get("정기권_차이") or []) != 9:
    fails.append(f"이천시 월 정기권 차이가 9건이 아님: {len(_ic_q.get('정기권_차이') or [])}")
ic_root = DIST / "parking" / "gyeonggi" / "icheon"
ic_hub = ic_root / "index.html"
if not ic_hub.exists():
    fails.append("이천시 시 페이지 없음")
else:
    ic_html = ic_hub.read_text()
    for label in ("이천시 급지별 주차요금표", "노외주차장", "노상주차장", "1급지", "2급지",
                  "1일 최대요금", "최초 무료시간이 있는 주차장", "평일 2시간 기준 가장 저렴한 곳",
                  'class="calc', "이천시시설관리공단", "상업지역", "경기도 이천시", "무료 회차",
                  "터미널 앞 노상주차장", "남천상가", "월 정기권"):
        if label not in ic_html:
            fails.append(f"이천시 시 페이지에 {label} 없음")
    if ic_html.count('class="card lot') != len(ic_cards):
        fails.append(f"이천시 시 페이지 카드 수 불일치({ic_html.count(chr(34)+'card lot')} vs {len(ic_cards)})")
    if "&lt;b&gt;" in ic_html:
        fails.append("이천시 시 페이지에 이스케이프된 <b> 태그가 보임")
ic_dong_pages = sorted(q.parent.name for q in ic_root.rglob("index.html") if q.parent.parent == ic_root)
for _slug in ("changjeon-dong", "gwango-dong", "jungri-dong", "sindun-myeon", "majang-myeon"):
    if _slug not in ic_dong_pages:
        fails.append(f"이천시 동 페이지 없음: {_slug}")
for _slug, _n in (("changjeon-dong", 5), ("gwango-dong", 4), ("jungri-dong", 3),
                  ("sindun-myeon", 3), ("majang-myeon", 5), ("bubal-eup", 2),
                  ("janghowon-eup", 2)):
    _p = ic_root / _slug / "index.html"
    if not _p.exists():
        if _n >= 3:      # 카드 3곳 이상인 동·읍·면만 페이지를 만든다(빈 페이지 방지)
            fails.append(f"이천시 동 페이지 없음: {_slug}")
        continue
    elif _p.read_text().count('class="card lot') != _n:
        fails.append(f"이천시 {_slug} 카드 수 불일치({_p.read_text().count(chr(34)+'card lot')} ≠ {_n})")

# ---------------------------------------------------------------- 안성시 (T-03 Phase 21)
# 「안성시 주차장 설치 및 관리조례」 [별표 1](공포 2026-03-13, 경기도안성시조례 제2217호 · 별표1 개정
# 2025-04-18)과 안성시시설관리공단 이용요금 안내(2026-11-17): 30분 미만 무료 뒤 2시간까지 30분당
# 노외 1급지 500원·2급지·3급지 200원, 2시간 초과 30분당 1급지 2,000원·2급지·3급지 1,000원.
# 1일 주차권 노외 1급지 10,000원·2급지 6,000원·3급지 5,000원, 노상 1급지 8,000원·2급지 4,000원.
as_cards = [l for l in LOTS if l.get("city") == "안성시" and l.get("list_mode") == "card"]
as_paid = [l for l in as_cards if l["fee"]["type"] == "유료"]
as_free = [l for l in as_cards if l["fee"]["type"] == "무료"]
as_by = {l["name"]: l for l in as_cards}
if not as_cards:
    fails.append("안성시 카드 데이터가 없음")
# 구성: 카드 40곳(유료 12·무료 28) · 구획 2,348면 · 노상 17구간 1,158면
if len(as_cards) != 40 or len(as_paid) != 12 or len(as_free) != 28:
    fails.append(f"안성시 카드 구성이 다름: 카드 {len(as_cards)} · 유료 {len(as_paid)} · 무료 {len(as_free)}")
if sum(l["spaces"] or 0 for l in as_cards) != 2348:
    fails.append(f"안성시 구획 합계가 다름: {sum(l['spaces'] or 0 for l in as_cards)}")
as_street = [l for l in LOTS if l.get("city") == "안성시" and l.get("list_mode") == "street"]
if len(as_street) != 17 or sum(l["spaces"] or 0 for l in as_street) != 1158:
    fails.append(f"안성시 노상 구간이 다름: {len(as_street)}구간 "
                 f"{sum(l['spaces'] or 0 for l in as_street)}면")
if len({l.get("dong") for l in as_cards}) != 21 or any(not l.get("dong") for l in as_cards):
    fails.append(f"안성시 동 구성이 다름: {sorted({l.get('dong') for l in as_cards})}")
_as_dup = [k for k, v in Counter(l["name"] for l in as_cards).items() if v > 1]
if _as_dup:
    fails.append(f"안성시 카드 이름 중복: {_as_dup[:3]}")
# 급지·요금 — 별표1 값(30분 미만 무료는 deduct_min 으로 계산)
_AS_FEE = {
    "석정동공영주차장(건축물식)": (1, 500, 2_000, 10_000, 100_000),
    "동본동공영주차장(건축물식)": (1, 500, 2_000, 10_000, 100_000),
    "공도저류지 공영주차장": (1, 500, 2_000, 10_000, 100_000),
    "아양지구 제2공영주차장": (1, 500, 2_000, 10_000, 100_000),
    "안성맞춤공감센터 공영주차장": (1, 500, 2_000, 10_000, 100_000),
    "아양지구 제3공영주차장": (1, 500, 2_000, 10_000, 100_000),
    "대덕 내리 공영주차장": (2, 200, 1_000, 6_000, 60_000),
    "대덕면 광덕 공영주차장": (2, 200, 1_000, 6_000, 60_000),
    "원곡면 공영주차장": (2, 200, 1_000, 6_000, 60_000),
    "안성 제2산업단지 공영주차장": (3, 200, 1_000, 5_000, 40_000),
}
for _n, (_g, _base, _unit, _day, _month) in _AS_FEE.items():
    _l = as_by.get(_n)
    if not _l:
        fails.append(f"안성시 카드에 {_n} 없음")
        continue
    _f = _l["fee"]
    if (_f.get("grade"), _f.get("base_fee"), _f.get("unit_fee"), _f.get("daily_fee"),
            _f.get("monthly")) != (_g, _base, _unit, _day, _month):
        fails.append(f"안성시 요금이 별표1과 다름: {_n} {_f.get('grade')}/{_f.get('base_fee')}/"
                     f"{_f.get('unit_fee')}/{_f.get('daily_fee')}/{_f.get('monthly')}")
    if _f.get("free_min") != 30 or _f.get("deduct_min") != 30:
        fails.append(f"안성시 {_n}의 30분 미만 무료 표기가 없음: "
                     f"{_f.get('free_min')}/{_f.get('deduct_min')}")
# 유료 노상 3구간은 1급지 · 1일 8,000원이고, 안성맞춤2구간만 주말·공휴일 무료다.
_as_st_paid = [l for l in as_street if l["fee"]["type"] == "유료"]
if len(_as_st_paid) != 3:
    fails.append(f"안성시 유료 노상이 3구간이 아님: {[l['name'] for l in _as_st_paid]}")
for _l in _as_st_paid:
    _f = _l["fee"]
    if (_f.get("grade"), _f.get("base_fee"), _f.get("unit_fee"), _f.get("daily_fee"),
            _f.get("monthly")) != (1, 500, 2_000, 8_000, 80_000):
        fails.append(f"안성시 유료 노상 {_l['name']} 요금이 별표1 노상 1급지와 다름")
    _wk = _l["hours"]["weekday"]
    if _l["name"] == "안성맞춤대로2구간":
        if not (_l["free_days"].get("sat") and _l["free_days"].get("sun")):
            fails.append("안성시 안성맞춤대로2구간의 주말 무료 표기 없음")
        if (_wk["start"], _wk["end"]) != (9 * 60, 18 * 60):
            fails.append(f"안성시 안성맞춤대로2구간 평일 운영시간이 09:00~18:00이 아님: "
                         f"{_wk['start']}/{_wk['end']}")
    elif _l["free_days"].get("sat") or _l["free_days"].get("sun"):
        fails.append(f"안성시 유료 노상 {_l['name']}이 주말 무료로 표기됨")
# 표준데이터가 ‘무료’로 등록한 2곳을 공단 안내(유료)에 맞춰 바로잡았다.
_as_q = next(c for c in CITIES if c["city"] == "안성시").get("quality") or {}
if len(_as_q.get("요금구분_보정") or []) != 2:
    fails.append(f"안성시 요금구분 보정이 2건이 아님: {_as_q.get('요금구분_보정')}")
if len(_as_q.get("운영시간_보정") or []) != 1:
    fails.append(f"안성시 운영시간 보정이 1건이 아님: {_as_q.get('운영시간_보정')}")
if len(_as_q.get("면수_차이") or []) != 6:
    fails.append(f"안성시 면수 차이가 6건이 아님: {len(_as_q.get('면수_차이') or [])}")
if len(_as_q.get("노상_자료차이") or []) != 3:
    fails.append(f"안성시 노상 자료 차이가 3건이 아님: {len(_as_q.get('노상_자료차이') or [])}")
# 계산 표본 — 별표1(30분 미만 무료를 뺀 시간에 30분 단위)로 직접 계산한 값
for _n, _mins, _want in (("석정동공영주차장(건축물식)", 30, 0), ("석정동공영주차장(건축물식)", 31, 500),
                         ("석정동공영주차장(건축물식)", 60, 500), ("석정동공영주차장(건축물식)", 120, 1500),
                         ("석정동공영주차장(건축물식)", 150, 2000), ("석정동공영주차장(건축물식)", 180, 4000),
                         ("석정동공영주차장(건축물식)", 600, 10000), ("대덕 내리 공영주차장", 120, 600),
                         ("대덕 내리 공영주차장", 1440, 6000), ("안성 제2산업단지 공영주차장", 120, 600),
                         ("안성 제2산업단지 공영주차장", 1440, 5000)):
    _l = as_by.get(_n)
    if not _l:
        continue
    _r = price_for(_l, _mins, "weekday")
    _got = 0 if _r["state"] == "free" else _r.get("amount")
    if _got != _want:
        fails.append(f"안성시 요금 계산이 별표1과 다름: {_n} {_mins}분 {_got} ≠ {_want}")
# 감면표 — 조례 제3조의2(경차 60%, 1시간 면제 뒤 50%, 50%, 차량부제 30%, 100% 면제)
_as_disc = next(c for c in CITIES if c["city"] == "안성시").get("discounts") or []
if not any(d["rate"] == 0.6 for d in _as_disc):
    fails.append("안성시 감면표에 경차 60%가 없음")
if not any(d["rate"] == 0.5 and d.get("exempt_min") == 60 for d in _as_disc):
    fails.append("안성시 감면표에 1시간 면제 후 50%가 없음")
if not any(d["rate"] == 0.3 for d in _as_disc):
    fails.append("안성시 감면표에 차량부제 30%가 없음")
if not any(d["rate"] == 1.0 for d in _as_disc):
    fails.append("안성시 감면표에 100% 면제 대상이 없음")
as_root = DIST / "parking" / "gyeonggi" / "anseong"
as_hub = as_root / "index.html"
if not as_hub.exists():
    fails.append("안성시 시 페이지 없음")
else:
    as_html = as_hub.read_text()
    for label in ("안성시 급지별 주차요금표", "노외주차장(건축물식 포함)", "노상주차장",
                  "2시간까지 30분당", "2시간 초과 30분당", "1일 주차권", "월 정기권",
                  "30분", "안성시시설관리공단", "안성맞춤2구간", "경기도 안성시",
                  "동·읍의 도시계획 지역", "3급지", "공업지역"):
        if label not in as_html:
            fails.append(f"안성시 시 페이지에 {label} 없음")
    if as_html.count('class="card lot') != len(as_cards):
        fails.append(f"안성시 시 페이지 카드 수 불일치({as_html.count(chr(34)+'card lot')} vs {len(as_cards)})")
    if "&lt;b&gt;" in as_html:
        fails.append("안성시 시 페이지에 이스케이프된 <b> 태그가 보임")
as_street_page = as_root / "street-parking" / "index.html"
if not as_street_page.exists():
    fails.append("안성시 노상 페이지 없음")
else:
    as_st = as_street_page.read_text()
    if as_st.count('class="strow') + as_st.count("<tr>") == 0:
        fails.append("안성시 노상 페이지에 표 행이 없음")
    for label in ("안성맞춤대로2구간", "장기로1구간", "신시장로", "하절기 08:00~20:00"):
        if label not in as_st:
            fails.append(f"안성시 노상 페이지에 {label} 없음")
as_dong_pages = sorted(q.parent.name for q in as_root.rglob("index.html") if q.parent.parent == as_root)
for _slug, _n in (("gongdo-eup", 8), ("seokjeong-dong", 3), ("dangwang-dong", 3),
                  ("oksan-dong", 3), ("daedeok-myeon", 3), ("geumsan-dong", 2),
                  ("wongok-myeon", 1)):
    _p = as_root / _slug / "index.html"
    if not _p.exists():
        if _n >= 3:      # 카드 3곳 이상인 동·읍·면만 페이지를 만든다(빈 페이지 방지)
            fails.append(f"안성시 동 페이지 없음: {_slug}")
        continue
    elif _p.read_text().count('class="card lot') != _n:
        fails.append(f"안성시 {_slug} 카드 수 불일치({_p.read_text().count(chr(34)+'card lot')} ≠ {_n})")

# ---------------------------------------------------------------- 양주시 (T-03 Phase 22)
# 「양주시 주차장 조례」 [별표 1](공포 2026-02-02, 경기도양주시조례 제1498호 · 별표1 개정 2021-08-02)과
# 양주도시공사 요금안내(2026-10-31 기준)·통합주차포털(2026-11-17 조회): 최초 10분 무료 뒤 30분까지
# 1급지 600원, 이후 10분당 200원, 1일 주차권(선납) 7,000원·월 정기권(선납) 60,000원(2급지 300·100·
# 3,000·40,000원). 조례 비고3은 야간·주말·공휴일 요금을 무료로 정한다.
yj_cards = [l for l in LOTS if l.get("city") == "양주시" and l.get("list_mode") == "card"]
yj_paid = [l for l in yj_cards if l["fee"]["type"] == "유료"]
yj_free = [l for l in yj_cards if l["fee"]["type"] == "무료"]
yj_by = {l["name"]: l for l in yj_cards}
if not yj_cards:
    fails.append("양주시 카드 데이터가 없음")
# 구성: 카드 38곳(유료 18·무료 20) · 구획 2,406면 · 노상 11구간 278면
if len(yj_cards) != 38 or len(yj_paid) != 18 or len(yj_free) != 20:
    fails.append(f"양주시 카드 구성이 다름: 카드 {len(yj_cards)} · 유료 {len(yj_paid)} · 무료 {len(yj_free)}")
if sum(l["spaces"] or 0 for l in yj_cards) != 2406:
    fails.append(f"양주시 구획 합계가 다름: {sum(l['spaces'] or 0 for l in yj_cards)}")
yj_street = [l for l in LOTS if l.get("city") == "양주시" and l.get("list_mode") == "street"]
if len(yj_street) != 11 or sum(l["spaces"] or 0 for l in yj_street) != 278:
    fails.append(f"양주시 노상 구간이 다름: {len(yj_street)}구간 "
                 f"{sum(l['spaces'] or 0 for l in yj_street)}면")
if len({l.get("dong") for l in yj_cards}) != 11 or any(not l.get("dong") for l in yj_cards):
    fails.append(f"양주시 동 구성이 다름: {sorted({l.get('dong') for l in yj_cards})}")
_yj_dup = [k for k, v in Counter(l["name"] for l in yj_cards).items() if v > 1]
if _yj_dup:
    fails.append(f"양주시 카드 이름 중복: {_yj_dup[:3]}")
# 민영 주차장은 싣지 않는다(공영주차장 파인더) — 40행
_yj_q = next(c for c in CITIES if c["city"] == "양주시").get("quality") or {}
if _yj_q.get("민영_제외") != 40:
    fails.append(f"양주시 민영 제외가 40행이 아님: {_yj_q.get('민영_제외')}")
if any(l["kind"] == "민영" for l in LOTS if l.get("city") == "양주시"):
    fails.append("양주시에 민영 주차장이 실려 있음")
# 시간 요금 13곳 — 별표1 1급지(최초 10분 무료·30분 600원·10분당 200원·1일 7,000원·월 60,000원)
_yj_timed = [l for l in yj_paid if not l["fee"].get("flat_day")]
if len(_yj_timed) != 13:
    fails.append(f"양주시 시간 요금 주차장이 13곳이 아님: {[l['name'] for l in _yj_timed]}")
for _l in _yj_timed:
    _f = _l["fee"]
    if (_f.get("grade"), _f.get("base_min"), _f.get("base_fee"), _f.get("unit_min"),
            _f.get("unit_fee"), _f.get("daily_fee"), _f.get("monthly")) != (1, 30, 600, 10, 200, 7000, 60000):
        fails.append(f"양주시 요금이 별표1 1급지와 다름: {_l['name']} "
                     f"{_f.get('grade')}/{_f.get('base_fee')}/{_f.get('unit_fee')}/"
                     f"{_f.get('daily_fee')}/{_f.get('monthly')}")
    if _f.get("free_min") != 10:
        fails.append(f"양주시 {_l['name']}의 최초 10분 무료 표기가 없음: {_f.get('free_min')}")
# 장흥관광지 — 당일 정액 2,000원(카드 5곳·노상 1곳)
_yj_flat = [l for l in LOTS if l.get("city") == "양주시" and l["fee"].get("flat_day")]
if len(_yj_flat) != 6:
    fails.append(f"양주시 당일 정액 주차장이 6곳이 아님: {[l['name'] for l in _yj_flat]}")
for _l in _yj_flat:
    if _l["fee"].get("base_fee") != 2000:
        fails.append(f"양주시 {_l['name']}의 당일 정액이 2,000원이 아님: {_l['fee'].get('base_fee')}")
# 덕정역 공영주차장 — 표준데이터는 무료였고, 2026-05-04부터 평일 08:00~20:00만 유료다.
_yj_deokjeong = yj_by.get("덕정역 공영주차장")
if not _yj_deokjeong:
    fails.append("양주시 카드에 덕정역 공영주차장 없음")
elif _yj_deokjeong["fee"]["type"] != "유료":
    fails.append(f"양주시 덕정역 공영주차장이 유료가 아님: {_yj_deokjeong['fee']['type']}")
else:
    _wk = _yj_deokjeong["hours"]["weekday"]
    if (_wk["start"], _wk["end"]) != (8 * 60, 20 * 60):
        fails.append(f"양주시 덕정역 평일 운영시간이 08:00~20:00이 아님: {_wk['start']}/{_wk['end']}")
    if not (_yj_deokjeong["free_days"].get("sat") and _yj_deokjeong["free_days"].get("sun")):
        fails.append("양주시 덕정역의 주말·공휴일 무료 표기 없음")
# 조례 비고3 — 평일만 요금을 받는 8곳과 주말에도 받는 5곳
_yj_wk_free = [l["name"] for l in yj_paid if not l["fee"].get("flat_day")
               and l["free_days"].get("sat") and l["free_days"].get("sun")]
if len(_yj_wk_free) != 8:
    fails.append(f"양주시 주말 무료 개방 주차장이 8곳이 아님: {_yj_wk_free}")
_yj_wk_paid = [l["name"] for l in yj_paid if not l["fee"].get("flat_day")
               and not (l["free_days"].get("sat") or l["free_days"].get("sun"))]
if sorted(_yj_wk_paid) != sorted(["기산저수지(1) 공영주차장", "기산저수지(2) 공영주차장",
                                  "마장호수 공영주차장", "옥정(2) 공영주차장", "옥정(3) 공영주차장"]):
    fails.append(f"양주시 주말에도 요금을 받는 주차장이 다름: {_yj_wk_paid}")
if len(_yj_q.get("요금구분_보정") or []) != 1:
    fails.append(f"양주시 요금구분 보정이 1건이 아님: {_yj_q.get('요금구분_보정')}")
if len(_yj_q.get("운영시간_보정") or []) != 16:
    fails.append(f"양주시 운영시간 보정이 16건이 아님: {len(_yj_q.get('운영시간_보정') or [])}")
if len(_yj_q.get("면수_차이") or []) != 13:
    fails.append(f"양주시 면수 차이가 13건이 아님: {len(_yj_q.get('면수_차이') or [])}")
if len(_yj_q.get("정기권_차이") or []) != 5:
    fails.append(f"양주시 정기권 차이가 5건이 아님: {len(_yj_q.get('정기권_차이') or [])}")
# 계산 표본 — 별표1(최초 10분 무료·30분 600원·10분당 200원·1일 7,000원 상한)로 직접 계산한 값
for _n, _mins, _want in (("덕정역 공영주차장", 10, 0), ("덕정역 공영주차장", 11, 600),
                         ("덕정역 공영주차장", 30, 600), ("덕정역 공영주차장", 60, 1200),
                         ("덕정역 공영주차장", 120, 2400), ("덕정역 공영주차장", 350, 7000),
                         ("덕정역 공영주차장", 1440, 7000), ("고읍저류지 공영주차장", 120, 2400),
                         ("장흥관광지 제1주차장(하천변)", 120, 2000),
                         ("장흥관광지 제1주차장(하천변)", 1440, 2000)):
    _l = next((x for x in LOTS if x.get("city") == "양주시" and x["name"] == _n), None)
    if not _l:
        continue
    _r = price_for(_l, _mins, "weekday")
    _got = 0 if _r["state"] == "free" else _r.get("amount")
    if _got != _want:
        fails.append(f"양주시 요금 계산이 별표1과 다름: {_n} {_mins}분 {_got} ≠ {_want}")
# 주말·공휴일 무료(비고3) — 평일만 요금을 받는 곳은 토·일에 0원, 주말에도 받는 곳은 같은 요금
_yj_sat = price_for(_yj_deokjeong, 120, "sat") if _yj_deokjeong else None
if _yj_sat and _yj_sat["state"] != "free":
    fails.append(f"양주시 덕정역 토요일 계산이 무료가 아님: {_yj_sat}")
_yj_ok = yj_by.get("옥정(2) 공영주차장")
if _yj_ok and price_for(_yj_ok, 120, "sat").get("amount") != 2400:
    fails.append(f"양주시 옥정(2) 토요일 계산이 2,400원이 아님: {price_for(_yj_ok, 120, 'sat')}")
# 감면표 — 조례 제7조(4시간 면제 뒤 50%·전기차 2시간 면제 뒤 50%·50%·면제)
_yj_disc = next(c for c in CITIES if c["city"] == "양주시").get("discounts") or []
if not any(d["rate"] == 0.5 and d.get("exempt_min") == 240 for d in _yj_disc):
    fails.append("양주시 감면표에 국가유공자 4시간 면제 뒤 50%가 없음")
if not any(d["rate"] == 0.5 and d.get("exempt_min") == 120 for d in _yj_disc):
    fails.append("양주시 감면표에 전기차 2시간 면제 뒤 50%가 없음")
if not any(d["rate"] == 0.5 and not d.get("exempt_min") for d in _yj_disc):
    fails.append("양주시 감면표에 50% 감면이 없음")
if not any(d["rate"] == 1.0 for d in _yj_disc):
    fails.append("양주시 감면표에 100% 면제 대상이 없음")
_yj_root = DIST / "parking" / "gyeonggi" / "yangju"
_yj_hub = _yj_root / "index.html"
if not _yj_hub.exists():
    fails.append("양주시 시 페이지 없음")
else:
    _yj_html = _yj_hub.read_text()
    for label in ("양주시 급지별 주차요금표", "최초 30분", "10분당 추가", "1일 주차권(선납)",
                  "월 정기권(선납)", "2급지", "장흥관광지", "거주자 전용 주차구획",
                  "양주도시공사", "덕정역", "최초 10분", "주말·공휴일 운영",
                  "국도·지방도·시도로부터 500m 이내"):
        if label not in _yj_html:
            fails.append(f"양주시 시 페이지에 {label} 없음")
    if _yj_html.count('class="card lot') != len(yj_cards):
        fails.append(f"양주시 시 페이지 카드 수 불일치({_yj_html.count(chr(34)+'card lot')} vs {len(yj_cards)})")
    if "&lt;b&gt;" in _yj_html:
        fails.append("양주시 시 페이지에 이스케이프된 <b> 태그가 보임")
_yj_st_page = _yj_root / "street-parking" / "index.html"
if not _yj_st_page.exists():
    fails.append("양주시 노상 페이지 없음")
else:
    _yj_st = _yj_st_page.read_text()
    for label in ("장흥관광지(노상)", "당일 정액", "무료 10곳"):
        if label not in _yj_st:
            fails.append(f"양주시 노상 페이지에 {label} 없음")
    if "&lt;b&gt;" in _yj_st:
        fails.append("양주시 노상 페이지에 이스케이프된 <b> 태그가 보임")
for _slug, _n in (("gwangjeok-myeon", 8), ("deokjeong-dong", 5), ("deokgye-dong", 5),
                  ("jangheung-myeon", 5), ("gwangsa-dong", 4), ("baekseok-eup", 3),
                  ("okjeong-dong", 3)):
    # 카드 3곳 이상인 동·읍·면만 페이지를 만든다(빈 페이지 방지)
    _p = _yj_root / _slug / "index.html"
    if not _p.exists():
        fails.append(f"양주시 동 페이지 없음: {_slug}")
    elif _p.read_text().count('class="card lot') != _n:
        fails.append(f"양주시 {_slug} 카드 수 불일치({_p.read_text().count(chr(34)+'card lot')} ≠ {_n})")
for _slug in ("goam-dong", "goeup-dong", "nambang-dong", "mansong-dong"):
    if (_yj_root / _slug / "index.html").exists():
        fails.append(f"양주시 카드 3곳 미만인 동 페이지가 만들어짐: {_slug}")

print()
if warns:
    print(f"주의 {len(warns)}건")
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
