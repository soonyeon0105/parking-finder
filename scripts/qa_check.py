#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""생성물 정적 검사: JSON-LD 유효성, 내부 링크, 계산 규칙 표본 검증."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "dist"
DATA = json.loads((BASE / "data" / "suwon_parking.json").read_text())

fails, warns = [], []

# ---------------------------------------------------------------- JSON-LD
pages = sorted(DIST.rglob("index.html"))
types_seen = {}
for pg in pages:
    html = pg.read_text()
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    for b in blocks:
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

# ---------------------------------------------------------------- 슬러그(전국 확장)
sys.path.insert(0, str(BASE / "scripts"))
from build_site import (DONG_SLUG, GU_SLUG, base_slug, dong_slug,  # noqa: E402
                        dong_slug_map, gu_slug)

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

# ---------------------------------------------------------------- 계산 규칙
sys.path.insert(0, str(BASE / "scripts"))
from build_site import price_for, hours_text, fee_text  # noqa: E402

by_name = {}
for l in DATA["lots"]:
    by_name.setdefault(l["name"], l)

cases = [
    # (주차장, 시간, 요일, 감면, 기대 상태, 기대 금액)
    ("영통구청", 60, "weekday", 0, "paid", 1500),
    ("영통구청", 120, "weekday", 0, "paid", 3300),
    ("영통구청", 120, "sun", 0, "free", None),
    ("신대호수", 120, "weekday", 0, "paid", 700),
    ("신대호수", 120, "weekday", 0.5, "paid", 350),
    ("농수산시장", 1440, "weekday", 0, "paid", 6000),          # 1일권 상한
    ("화성박물관,팔달구청", 120, "sat", 0, "closed", None),     # 토요일 미운영
    ("시청정문", 120, "sat", 0, "closed", None),
]
for name, minutes, day, rate, want_state, want_amt in cases:
    lot = by_name.get(name)
    if not lot:
        fails.append(f"표본 계산: '{name}' 데이터 없음")
        continue
    r = price_for(lot, minutes, day, rate)
    ok = r["state"] == want_state and (want_amt is None or r.get("amount") == want_amt)
    print(f"{'OK ' if ok else 'FAIL'} {name} {minutes}분 {day} 감면{rate:.0%} → {r}")
    if not ok:
        fails.append(f"계산 규칙 불일치: {name} {minutes}분 {day} → {r} (기대 {want_state}/{want_amt})")

# 요금 미상 표시 확인
unknown = [l for l in DATA["lots"] if l["fee"]["type"] == "미상"]
if unknown:
    r = price_for(unknown[0], 120, "weekday", 0)
    ok = r["state"] == "unknown"
    print(f"{'OK ' if ok else 'FAIL'} 요금 미상 표본 '{unknown[0]['name']}' → {r}")
    if not ok:
        fails.append("요금 미상 주차장이 0원으로 계산됨")

# 화면 문구 표본
for name in ("영통구청", "시청정문", "곡반정동제7공영"):
    if name in by_name:
        print(f"문구 · {name}: {fee_text(by_name[name])} / {hours_text(by_name[name])}")

print()
if fails:
    print(f"실패 {len(fails)}건")
    for f in fails[:20]:
        print(" -", f)
    sys.exit(1)
print("모두 통과: JSON-LD, 내부 링크, 계산 규칙")
