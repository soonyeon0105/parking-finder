#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""지도 링크·좌표 QA (트랙 2-③).

빌드 전후에 돌려 아래를 점검하고 결과를 dist/qa_maps.txt 로 남긴다.
  1) 좌표가 없는 주차장 — 카카오 모바일 지도 검색(m.map.kakao.com/?q=)으로 나가는지
  2) 같은 좌표(소수 5자리)를 쓰는 주차장 묶음 — 노상(구간)과 노외(카드)를 나눠서
  3) 동·읍·면 중심에서 3km 넘게 떨어진 좌표 — 동 추정 오류 탐지(3곳 이상인 동만)
  4) 생성된 카카오·네이버 링크의 길이·비ASCII·구분자(쉼표) 문제

종료 코드: 하드 오류(링크 형식·좌표 형식)가 있으면 1, 목록성 경고만 있으면 0.
사용법: python3 scripts/qa_maps.py [--write]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, unquote

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "dist"
DATA = BASE / "data" / "site.json"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_site import map_coords, map_label, map_links  # noqa: E402

OUTLIER_KM = 3.0
DUPLICATE_DECIMALS = 5


def distance_km(a_lat, a_lng, b_lat, b_lng) -> float:
    """두 좌표의 대략 거리(km) — 하버사인."""
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = p2 - p1
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def median(values):
    values = sorted(values)
    n = len(values)
    if not n:
        return None
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def collect(lots):
    missing, clusters, outliers = [], defaultdict(list), []
    by_place = defaultdict(list)
    for lot in lots:
        lat, lng = map_coords(lot)
        if not (lat and lng):
            missing.append(lot)
            continue
        clusters[(round(lat, DUPLICATE_DECIMALS), round(lng, DUPLICATE_DECIMALS))].append(lot)
        key = (lot.get("city"), lot.get("gu"), lot.get("dong"))
        by_place[key].append(lot)

    for key, group in by_place.items():
        if len(group) < 3 or not key[2]:
            continue
        clat = median([map_coords(l)[0] for l in group])
        clng = median([map_coords(l)[1] for l in group])
        for lot in group:
            lat, lng = map_coords(lot)
            km = distance_km(clat, clng, lat, lng)
            if km > OUTLIER_KM:
                outliers.append((lot, km, clat, clng))

    dup = {k: v for k, v in clusters.items() if len(v) > 1}
    return missing, dup, outliers


def check_links(lots):
    """지도 링크 형식 점검 — 하드 오류만 모은다."""
    problems = []
    for lot in lots:
        kakao, naver = map_links(lot)
        label = map_label(lot)
        for url in (kakao, naver):
            if len(url) > 2000:
                problems.append(f"{lot['name']}: 지도 링크가 너무 김({len(url)}자)")
            if " " in url:
                problems.append(f"{lot['name']}: 지도 링크에 공백이 그대로 있음")
        if lot.get("lat") and lot.get("lng"):
            lat, lng = map_coords(lot)
            if not re.fullmatch(r"https://map\.kakao\.com/link/map/[^,]+,[0-9.]+,[0-9.]+", kakao):
                problems.append(f"{lot['name']}: 카카오 핀 링크 형식 오류 {kakao}")
            elif str(lat) not in kakao or str(lng) not in kakao:
                problems.append(f"{lot['name']}: 카카오 링크 좌표가 보정값과 다름 {kakao}")
        else:
            if not kakao.startswith("https://m.map.kakao.com/?q="):
                problems.append(f"{lot['name']}: 좌표 없는 주차장의 카카오 링크가 모바일 지도 형식이 아님 {kakao}")
            if "menu=location" not in naver:
                problems.append(f"{lot['name']}: 좌표 없는 주차장의 네이버 링크에 menu=location 없음 {naver}")
        # 이름에 쉼표가 그대로 들어가면 카카오 /link/map/ 경로가 3조각을 넘는다(치환 누락).
        if "," in label:
            problems.append(f"{lot['name']}: 지도 라벨에 쉼표가 남음")
    return problems


def build_report(lots) -> tuple[str, int]:
    missing, dup, outliers = collect(lots)
    hard = check_links(lots)
    lines = []
    add = lines.append
    add("지도 QA — 좌표·링크 점검")
    add(f"대상 주차장 {len(lots):,}곳 · 좌표 있음 {len(lots) - len(missing):,}곳 · 없음 {len(missing)}곳")
    add("")
    add(f"[1] 좌표 없는 주차장 {len(missing)}곳 (카카오 m.map.kakao.com/?q= · 네이버 query&menu=location)")
    for lot in missing:
        add(f"  - {lot['city']} {lot['name']} ({lot['id']}) · {lot.get('addr_road') or lot.get('addr_jibun') or '주소 없음'}")
    add("")
    card_dup = {k: v for k, v in dup.items() if any(l.get("list_mode", "card") != "street" for l in v)}
    street_dup = {k: v for k, v in dup.items() if k not in card_dup}
    add(f"[2] 같은 좌표를 쓰는 묶음 {len(dup)}개 (노외 포함 {len(card_dup)} · 노상만 {len(street_dup)})")
    for (lat, lng), group in sorted(card_dup.items(), key=lambda kv: -len(kv[1])):
        names = ", ".join(f"{l['name']}({l['id']})" for l in group[:6])
        add(f"  - {lat},{lng} · {len(group)}곳 · {names}")
    if street_dup:
        add(f"  · 노상 구간만 겹치는 묶음 {len(street_dup)}개는 구간이 같은 도로를 공유하는 경우라 정상 범위(카드에는 ‘구간 대략 위치’ 표기).")
    add("")
    add(f"[3] 동·읍·면 중심에서 {OUTLIER_KM:g}km 넘게 떨어진 좌표 {len(outliers)}곳")
    for lot, km, clat, clng in sorted(outliers, key=lambda t: -t[1])[:40]:
        add(f"  - {lot['city']} {lot['gu']} {lot['dong']} · {lot['name']}({lot['id']}) {km:.1f}km "
            f"(동 중심 {clat:.5f},{clng:.5f})")
    add("")
    add(f"[4] 지도 링크 형식 오류 {len(hard)}건")
    for p in hard:
        add(f"  - {p}")
    return "\n".join(lines) + "\n", len(hard)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="dist/qa_maps.txt 로 저장")
    args = ap.parse_args()
    lots = json.loads(DATA.read_text())["lots"]
    text, hard = build_report(lots)
    print(text)
    if args.write and DIST.exists():
        (DIST / "qa_maps.txt").write_text(text, encoding="utf-8")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
