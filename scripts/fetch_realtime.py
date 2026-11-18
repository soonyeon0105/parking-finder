#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실시간 잔여면수 수집 (트랙 2-②).

키 없이 부를 수 있는 지자체 공개 목록에서 주차장별 잔여면수를 받아
data/realtime/{city}.json 으로 남긴다. build_site.py 는 이 파일을 읽어 카드에
‘실시간 N면’ 배지를 붙이고, 30분이 지난 스냅숏은 싣지 않는다.

지금 붙인 소스
  · 평택도시공사  POST https://parking.puc.or.kr/parking/searchParkingList.json  (키 불필요)
      CURRENT_CNT = 남은 면수(초과 주차로 음수가 나올 수 있어 0으로 자른다)
      CELL_CNT/SUM_CELL_CNT = 총면
  (수원도시공사는 prepare_data.py 가 지도 페이지 스냅숏에서 이미 읽는다.)

사용법:
  python3 scripts/fetch_realtime.py                 # 평택
  python3 scripts/fetch_realtime.py --city pyeongtaek --min-match 90
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data" / "site.json"
OUT = BASE / "data" / "realtime"
KST = timezone(timedelta(hours=9))

PUC_URL = "https://parking.puc.or.kr/parking/searchParkingList.json"
UA = "Mozilla/5.0 (compatible; parking-finder/1.0; +https://parking.9welfare.com)"


def norm_name(name: str) -> str:
    """주차장 이름 비교용 — 공백·‘공영’·‘주차장’·괄호·구분기호를 없앤다."""
    s = re.sub(r"\([^)]*\)", "", name or "")
    s = s.replace(" ", "")
    for token in ("공영주차장", "공영", "주차장", "주차타워", "주차빌딩"):
        s = s.replace(token, "")
    return re.sub(r"[·\-,._]", "", s)


def km(a_lat, a_lng, b_lat, b_lng) -> float:
    import math
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def fetch_puc() -> list[dict]:
    body = urllib.parse.urlencode({"searchParking": "", "parkingDong": ""}).encode()
    req = urllib.request.Request(PUC_URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    rows = payload.get("parkingList") or []
    # 구역(SECTN)별로 나뉜 행을 주차장 단위로 합친다.
    agg: dict[int, dict] = {}
    for r in rows:
        pid = r.get("PARKING_ID")
        a = agg.setdefault(pid, {"name": r.get("PARKING_NM"), "free": 0, "total": 0,
                                 "lat": None, "lng": None, "tel": r.get("TEL_NO")})
        a["free"] += int(r.get("CURRENT_CNT") or 0)
        a["total"] += int(r.get("CELL_CNT") or r.get("SUM_CELL_CNT") or 0)
        try:
            a["lat"] = float(r.get("LAT")) if r.get("LAT") else a["lat"]
            a["lng"] = float(r.get("LNG")) if r.get("LNG") else a["lng"]
        except (TypeError, ValueError):
            pass
    return [dict(v, src_id=str(k)) for k, v in agg.items()]


def match_lots(rows: list[dict], lots: list[dict]) -> tuple[list[dict], list[dict]]:
    """이름 → 좌표(150m) → 수동 예외(data/realtime_map.json) 순서로 짝짓는다."""
    by_name: dict[str, list[dict]] = {}
    for lot in lots:
        by_name.setdefault(norm_name(lot["name"]), []).append(lot)
    overrides = {}
    map_file = BASE / "data" / "realtime_map.json"
    if map_file.exists():
        try:
            overrides = json.loads(map_file.read_text())
        except (json.JSONDecodeError, OSError):
            overrides = {}

    matched, unmatched = [], []
    for r in rows:
        key = norm_name(r["name"])
        pool = by_name.get(key) or []
        if len(pool) > 1 and r.get("lat") and r.get("lng"):
            pool = sorted(pool, key=lambda l: km(r["lat"], r["lng"], l["lat"], l["lng"])
                          if l.get("lat") and l.get("lng") else 99)[:1]
        lot = pool[0] if pool else None
        if lot is None and r.get("lat") and r.get("lng"):
            near = [(km(r["lat"], r["lng"], l["lat"], l["lng"]), l) for l in lots
                    if l.get("lat") and l.get("lng")]
            near = [x for x in near if x[0] <= 0.15]
            if near:
                lot = min(near, key=lambda x: x[0])[1]
        if lot is None and r.get("src_id") in overrides:
            wanted = overrides[r["src_id"]]
            lot = next((l for l in lots if l["id"] == wanted), None)
        if lot is None:
            unmatched.append(r)
            continue
        matched.append({"id": lot["id"], "name": r["name"],
                        "free": max(int(r["free"]), 0), "total": int(r["total"]),
                        "src": "puc", "src_id": r.get("src_id")})
    return matched, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="pyeongtaek")
    ap.add_argument("--min-match", type=float, default=90.0,
                    help="매칭률이 이 값보다 낮으면 파일을 쓰지 않고 종료 코드 2 (기본 90%%)")
    args = ap.parse_args()

    site = json.loads(DATA.read_text())
    city_lots = [l for l in site["lots"] if l.get("city_slug") == args.city or l.get("city") == args.city]
    if not city_lots:
        print(f"site.json 에 {args.city} 주차장이 없습니다.")
        return 1

    rows = fetch_puc()
    matched, unmatched = match_lots(rows, city_lots)
    rate = len(matched) / len(rows) * 100 if rows else 0
    print(f"평택도시공사 응답 {len(rows)}곳 · 매칭 {len(matched)}곳({rate:.1f}%) · 미매칭 {len(unmatched)}곳")
    for r in unmatched[:10]:
        print(f"  미매칭: {r['name']} ({r['free']}/{r['total']})")
    if rate < args.min_match:
        print(f"매칭률이 기준({args.min_match:.0f}%)보다 낮아 파일을 쓰지 않습니다.")
        return 2

    ts = datetime.now(KST).replace(microsecond=0).isoformat()
    for m in matched:
        m["ts"] = ts
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{args.city}.json"
    out.write_text(json.dumps(matched, ensure_ascii=False, indent=1))
    print(f"저장: {out.relative_to(BASE)} · {len(matched)}곳 · {ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
