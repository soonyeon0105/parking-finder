#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""좌표가 없는 주차장 좌표를 주소·장소 검색으로 찾는다 (T-03 후속, 2026-11-18).

표준데이터에 위도·경도가 비어 있는 행은 사이트에서 지도 링크가 '주소 검색'으로만
연결된다. 이 스크립트는 그런 주차장의 지번·도로명주소를 지도 서비스(maps CLI)로
지오코딩하고, 같은 이름의 주차장 장소(카카오·구글 POI)도 함께 찾아 후보를 모은 뒤,
검증 규칙(같은 구·시 서명, 시·군 좌표 분포 상자, 출처 간 거리)으로 쓸 수 있는
좌표만 골라 JSON 으로 남긴다. 좌표를 지어내지 않는다 — 검증을 통과한 후보가 없으면
비워 두고 사람이 본다.

결과: data/raw/좌표누락_지오코딩_20261118.json
사용법: python3 scripts/geocode_missing_coords.py [--cities "광주 동구,제주시"] [--limit N]
        [--out 다른경로.json]   (기존 결과에 이어서 채운다 — 재실행해도 같은 곳을 다시 부르지 않음)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
RAW = DATA / "raw"
SITE = DATA / "site.json"
OUT = RAW / "좌표누락_지오코딩_20261118.json"

# 시·군 경계 상자 여유 — 기존 좌표 분포에 이만큼(약 4km)을 더해 이웃 시·군 좌표가
# 섞여 들어오는 것을 막는다.
BBOX_PAD = 0.04
# 같은 동 안 다른 주차장 좌표들의 중앙값에서 이만큼 떨어지면 사람이 다시 본다.
DONG_FAR_M = 2000
# 출처가 다른 두 후보가 이 안에 있으면 서로 맞는 것으로 본다.
AGREE_M = 200
GENERIC_NAMES = {"주차장", "공영주차장", "공영주차", "주차타워", "노외주차장", "부설주차장"}

# 행정구역이 새로 생겨 좌표가 있는 주차장이 하나도 없고, 지도 서비스 주소도 옛 구 이름으로
# 돌아오는 곳의 대략 경계(2026년 인천 2군·9구 재편). 좌표가 있는 기존 주차장이 없는 곳에만 쓴다.
#   ・검단구·서해구 = 옛 인천 서구, 제물포구·영종구 = 옛 인천 중구, 미추홀구 = 옛 인천 남구
CITY_BBOX_OVERRIDE = {
    "검단구": (37.540, 37.660, 126.620, 126.780),
    "서해구": (37.490, 37.600, 126.550, 126.720),
    "제물포구": (37.440, 37.500, 126.560, 126.670),
    "영종구": (37.400, 37.560, 126.350, 126.620),
    "미추홀구": (37.410, 37.480, 126.620, 126.730),
}


def hav(a, b, c, d) -> float:
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(min(1.0, h)))


def maps_json(args: list[str]):
    """maps CLI 호출 → data 부분(dict) 또는 None."""
    try:
        out = subprocess.run(["maps", *args, "--country", "KR"],
                             capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        payload = json.loads(out.stdout)
    except json.JSONDecodeError:
        return None
    if not payload.get("ok"):
        return None
    return payload.get("data")


def clean_jibun(addr: str) -> str:
    """‘계림동280 외 6필지’ → ‘계림동 280’, ‘대흥동 1-1, 2’ → ‘대흥동 1-1’."""
    a = (addr or "").split(",")[0].strip()
    a = re.sub(r"\s*(외\s*\d+\s*필지|일원|부근)\s*$", "", a).strip()
    a = re.sub(r"(?<=[동가리])(?=\d)", " ", a)          # 계림동280 → 계림동 280
    a = re.sub(r"\s+", " ", a).strip()
    return a


def is_road(addr: str) -> bool:
    return bool(re.search(r"[로길]\s*\d", addr or ""))


def norm_name(name: str) -> str:
    n = re.sub(r"\(주\)|주식회사", "", name or "")
    n = re.sub(r"\s+", "", n)
    n = n.replace("공영주차장", "주차장").replace("공영 ", "주차장")
    return n


def name_score(lot_name: str, cand_name: str) -> float:
    """이름 유사도(0~1). ‘공영주차장’ 같은 일반 명칭만 맞는 후보는 0으로 본다."""
    a, b = norm_name(lot_name), norm_name(cand_name)
    if not a or not b:
        return 0.0
    if b in GENERIC_NAMES or a in GENERIC_NAMES:
        return 0.0
    core = re.sub(r"(공영|주차장|주차타워)+", "", a) or a
    if len(re.sub(r"(공영|주차장|주차타워)+", "", b)) < max(2, len(core) * 0.5):
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.85
    def grams(s):
        s = re.sub(r"(공영|주차장)+", "", s)
        return {s[i:i + 2] for i in range(len(s) - 1)} or {s}
    ga, gb = grams(a), grams(b)
    return len(ga & gb) / len(ga | gb) if ga and gb else 0.0


ROMA_FIX = (("kwangju", "gwangju"), ("cheju", "jeju"), ("chonnam", "jeonnam"),
            ("chungnam", "chungcheongnam"), ("chungbuk", "chungcheongbuk"),
            ("kangwon", "gangwon"), ("kyonggi", "gyeonggi"), ("pusan", "busan"),
            ("taegu", "daegu"), ("taejon", "daejeon"), ("inchon", "incheon"),
            ("soul", "seoul"))


def addr_signature(addr: str) -> str | None:
    """주소의 끝 두 토막 — ‘Dong-gu, Kwangju, South Korea’ 같은 구·시 서명.

    구글 표기(Gwangju/Kwangju·Jeju/Cheju)·대소문자·‘South Korea’ 차이는 같은 곳으로 본다.
    """
    parts = [p.strip().lower() for p in (addr or "").split(",") if p.strip()]
    parts = [p for p in parts if p not in ("south korea", "korea", "republic of korea")]
    if len(parts) < 2:
        return None
    for a, b in ROMA_FIX:
        parts = [p.replace(a, b) for p in parts]
    return ", ".join(parts[-2:])


def sig_match(a: str | None, b: str | None) -> bool:
    """두 서명이 같은 구·시를 가리키는지 — 끝 두 토막을 느슨하게 비교한다."""
    if not a or not b:
        return False
    try:
        a1, a2 = a.split(", ")[-2:]
        b1, b2 = b.split(", ")[-2:]
    except ValueError:
        return a == b
    prov = a2 == b2 or a2 in b2 or b2 in a2
    dist = a1 == b1 or a1 in b1 or b1 in a1
    return prov and dist


def in_bbox(lat, lng, bbox) -> bool:
    return bool(bbox) and bbox[0] <= lat <= bbox[1] and bbox[2] <= lng <= bbox[3]


def district_match(city: str, addr: str) -> bool:
    """주소가 그 시·군 안인지 — ‘광주 동구’·‘부산 해운대구’의 낱말이 주소에 다 있는지."""
    flat = re.sub(r"\s", "", addr or "")
    toks = [t for t in (city or "").split() if t]
    if not toks:
        return False
    short = {"광주": "광주", "부산": "부산", "인천": "인천", "대구": "대구", "대전": "대전",
             "울산": "울산", "세종": "세종", "서울": "서울", "제주": "제주"}
    for t in toks:
        if t in flat:
            continue
        if t in short and short[t] in flat:
            continue
        return False
    return True


def jibun_key(addr: str) -> str | None:
    """주소에서 ‘동·읍·면·리 + 번지’만 — 지오코딩 결과가 같은 필지인지 볼 때."""
    a = re.sub(r"\s", " ", (addr or ""))
    m = re.search(r"([가-힣]{1,6}(?:동|읍|면|리))\s*\d+(?:-\d+)?", a)
    return re.sub(r"\s", "", m.group(0)) if m else None


class CityIndex:
    """한 시·군의 기존 좌표 분포 — 경계 상자, 동별 중심, 주소 서명."""

    def __init__(self, lots):
        pts = [(l["lat"], l["lng"]) for l in lots if l.get("lat") and l.get("lng")]
        self.bbox = None
        self.wide = None
        self.signature = None
        self.dong_center = {}
        if pts:
            lats = sorted(p[0] for p in pts)
            lngs = sorted(p[1] for p in pts)
            self.bbox = (lats[0] - BBOX_PAD, lats[-1] + BBOX_PAD,
                         lngs[0] - BBOX_PAD, lngs[-1] + BBOX_PAD)
            # 서명(구·시)을 확인한 후보에는 넓은 상자만 적용한다 — 큰 구·군은 기존 좌표가
            # 한쪽에 몰려 있어 좁은 상자로는 같은 구 안의 먼 동을 걸러 버린다.
            self.wide = (lats[0] - 0.25, lats[-1] + 0.25, lngs[0] - 0.25, lngs[-1] + 0.25)
        by_dong = defaultdict(list)
        for l in lots:
            if l.get("lat") and l.get("lng") and l.get("dong"):
                by_dong[l["dong"]].append((l["lat"], l["lng"]))
        self.dong_center = {d: (sorted(p[0] for p in v)[len(v) // 2],
                                sorted(p[1] for p in v)[len(v) // 2])
                            for d, v in by_dong.items() if len(v) >= 2}


def learn_signatures(lots, only=None) -> dict[str, set[str]]:
    """시·군마다 이미 좌표가 있는 주차장 2곳의 주소를 지오코딩해 구·시 서명을 익힌다."""
    by_city = defaultdict(list)
    for l in lots:
        if l.get("lat") and l.get("lng") and (l.get("addr_road") or l.get("addr_jibun")):
            by_city[l["city"]].append(l)
    if only:
        by_city = {c: v for c, v in by_city.items() if c in only}
    sigs: dict[str, set[str]] = {}
    for city, group in by_city.items():
        found: Counter = Counter()
        for l in group[:2]:
            for q in (l.get("addr_road") or "", clean_jibun(l.get("addr_jibun") or "")):
                if not q:
                    continue
                got = maps_json(["geocode", q])
                if got and got.get("address"):
                    sig = addr_signature(got["address"])
                    if sig:
                        found[sig] += 1
                        break
        if found:
            sigs[city] = {found.most_common(1)[0][0]}
    return sigs


def harvest_lot(lot, idx: CityIndex, sigs: set[str], province: str):
    """한 주차장의 후보 좌표를 모은다 — 지오코딩 1~2회 + 이름 장소 검색 1회."""
    name, jibun, road = lot["name"], lot.get("addr_jibun") or "", lot.get("addr_road") or ""
    tok = lot["city"].split()[-1]
    queries = []
    if is_road(road):
        queries.append(("지오코딩(도로명)", road))
    jb = clean_jibun(jibun)
    if jb and (jibun or not road):
        queries.append(("지오코딩(지번)", jb))
    elif road:
        queries.append(("지오코딩(지번)", clean_jibun(road)))

    cands = []
    for how, q in queries:
        got = maps_json(["geocode", q])
        if not got or not got.get("latitude"):
            continue
        addr = got.get("address") or ""
        cands.append({"kind": "geocode", "how": how, "query": q,
                      "lat": round(float(got["latitude"]), 7), "lng": round(float(got["longitude"]), 7),
                      "addr": addr, "source": got.get("source"),
                      "sig_ok": (any(sig_match(addr_signature(addr), s) for s in sigs)
                                 or tok in addr) if sigs else None})

    place_q = f"{name} {province} {tok}".strip()
    places = maps_json(["places", place_q, "--limit", "5"])
    got_places = []
    for p in (places or {}).get("places", []):
        addr = p.get("address") or ""
        got_places.append({"kind": "place", "how": "장소 검색", "query": place_q,
                           "name": p.get("name"), "lat": round(p["latitude"], 7),
                           "lng": round(p["longitude"], 7), "addr": addr,
                           "source": p.get("source"), "category": p.get("category"),
                           "sim": round(name_score(name, p.get("name", "")), 3),
                           "sig_ok": (any(sig_match(addr_signature(addr), s) for s in sigs)
                                      or tok in addr) if sigs else None})
    got_places.sort(key=lambda c: (-c["sim"], c["source"] != "Kakao Map"))
    cands.extend(got_places[:4])

    for c in cands:
        c["bbox_ok"] = in_bbox(c["lat"], c["lng"], idx.bbox)
        c["wide_ok"] = in_bbox(c["lat"], c["lng"], idx.wide)
        if not c.get("sig_ok"):
            # 카카오·일부 구글 주소는 한국어·다른 표기라 서명이 안 맞는다 — 시·군 낱말로 한 번 더 본다.
            c["sig_ok"] = district_match(lot["city"], c.get("addr") or "")
        if not c.get("sig_ok") and in_bbox(c["lat"], c["lng"], idx.bbox):
            # 기존 좌표 분포 상자 안이면 같은 시·군으로 본다(주소 표기가 낯설어도).
            c["sig_ok"] = True
        if c["kind"] == "geocode":
            c["addr_match"] = bool(jibun_key(c.get("addr") or "") and
                                   jibun_key(c.get("addr") or "") == jibun_key(lot.get("addr_jibun") or lot.get("addr_road") or ""))
        dc = idx.dong_center.get(lot.get("dong") or "")
        c["dong_m"] = round(hav(dc[0], dc[1], c["lat"], c["lng"])) if dc else None
    return cands


def pick(lot, cands, has_sig: bool, bbox_only: bool = False):
    """검증을 통과한 후보 중 하나를 고른다 — 없으면 None(좌표를 비워 둔다)."""
    def district_ok(c):
        if bbox_only:
            return c["bbox_ok"]
        if has_sig:
            # 서명이 맞으면 그 구·시 안이다 — 상자는 이웃 구가 섞이지 않게 넓게만 본다.
            return c["sig_ok"] is True and c["wide_ok"]
        # 서명을 익힐 기존 좌표가 없으면, 주소의 시·군 낱말과 상자를 함께 본다.
        return c["sig_ok"] is True and c["bbox_ok"]

    ok = [c for c in cands if district_ok(c)]
    if not ok:
        return None
    named = [c for c in ok if c["kind"] == "place" and c.get("sim", 0) >= 0.6
             and "주차" in (c.get("category") or "")]
    named.sort(key=lambda c: (c.get("dong_m") is not None and c["dong_m"] > DONG_FAR_M,
                              -c["sim"], c["source"] != "Kakao Map"))
    addr = [c for c in ok if c["kind"] == "geocode"]
    addr.sort(key=lambda c: (c.get("dong_m") is not None and c["dong_m"] > DONG_FAR_M,
                             c["source"] != "Kakao Map"))
    named2 = [c for c in ok if c["kind"] == "place" and c.get("sim", 0) >= 0.85]

    order = named + addr + named2
    if not order:
        return None
    top = order[0]
    agree = [c for c in ok if c["source"] != top["source"]
             and hav(top["lat"], top["lng"], c["lat"], c["lng"]) <= AGREE_M]
    high = bool(agree) or (top["kind"] == "place" and top.get("sim", 0) >= 0.9) \
        or bool(top.get("addr_match"))
    conf = "high" if high else "medium"
    if top.get("dong_m") is not None and top["dong_m"] > DONG_FAR_M \
            and not top.get("addr_match"):
        conf = "review"
    return {**top, "confidence": conf, "agree": [f"{c['source']}:{c['kind']}:{c.get('how')}" for c in agree]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", default="", help="쉼표로 구분한 시·군 이름(기본: 좌표 없는 곳 전부)")
    ap.add_argument("--limit", type=int, default=0, help="이번 실행에서 처리할 최대 건수")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--workers", type=int, default=1,
                    help="동시에 조회할 건수(지도 API 호출을 나눠 빨리 끝낸다. 기본 1)")
    ap.add_argument("--redo-fixed", action="store_true",
                    help="이미 좌표를 채운 곳(coord_src=지오코딩)도 다시 계산해 결과 파일을 온전하게 만든다")
    args = ap.parse_args()
    out_path = Path(args.out) if Path(args.out).is_absolute() else BASE / args.out

    site = json.loads(SITE.read_text())
    lots = site["lots"]
    cities_meta = {c["city"]: c["province"] for c in site["meta"]["cities"]}
    want = [s.strip() for s in args.cities.split(",") if s.strip()]
    missing = [l for l in lots if not (l.get("lat") and l.get("lng"))]
    if want:
        missing = [l for l in missing if l["city"] in want]

    prev = {"source": "maps CLI(카카오맵·구글맵) 지오코딩·장소 검색",
            "fetched_at": "2026-11-18 (KST)", "rows": []}
    prev_ids = set()
    if out_path.exists():
        prev = json.loads(out_path.read_text())
        if want:
            # 다시 돌릴 때도 그 시·군의 기존 행(이미 좌표를 확보한 곳 포함)을 모두 다시 채운다.
            prev_ids = {r["id"] for r in prev["rows"] if r["city"] in want}
            prev["rows"] = [r for r in prev["rows"] if r["city"] not in want]
    done = {(r["city"], r["name"], r["addr_jibun"]) for r in prev["rows"]}
    by_city = defaultdict(list)
    for l in lots:
        by_city[l["city"]].append(l)
    idx = {c: CityIndex(v) for c, v in by_city.items()}
    sigs_all = learn_signatures(lots, {l["city"] for l in missing})

    # 좌표가 있는 주차장이 한 곳도 없는 구·시(예: 마포구·검단구)는 경계 상자를 만들 수 없다.
    # 시·군 이름을 지오코딩해 그 중심으로 상자를 잡는다(±8km / ±25km).
    bbox_only_cities = set()
    for city in {l["city"] for l in missing}:
        ix = idx[city]
        if ix.bbox:
            continue
        if city in CITY_BBOX_OVERRIDE:
            ix.bbox = CITY_BBOX_OVERRIDE[city]
            ix.wide = CITY_BBOX_OVERRIDE[city]
            bbox_only_cities.add(city)
            print(f"경계 표 사용 {city}: {ix.bbox}", file=sys.stderr)
            continue
        meta = cities_meta.get(city, "")
        got = maps_json(["geocode", f"{meta} {city}".strip()])
        if got and got.get("latitude"):
            la, ln = float(got["latitude"]), float(got["longitude"])
            ix.bbox = (la - 0.08, la + 0.08, ln - 0.08, ln + 0.08)
            ix.wide = (la - 0.25, la + 0.25, ln - 0.25, ln + 0.25)
            ix.signature = addr_signature(got.get("address") or "")
            print(f"중심 기준 상자 {city}: {la:.4f},{ln:.4f} · 서명 {ix.signature}", file=sys.stderr)
    prev["city_signatures"] = {k: sorted(v) for k, v in sigs_all.items()}

    todo = [l for l in missing if (l["city"], l["name"], l["addr_jibun"]) not in done]
    if want:
        # 사이트에 이미 좌표가 들어간 곳도(이전 실행 결과) 다시 계산해 최신 규칙으로 덮어쓴다.
        extra = [l for l in lots if l["city"] in want and l["id"] in prev_ids
                 and l["id"] not in {t["id"] for t in todo}]
        todo = todo + extra
    if args.redo_fixed:
        todo_ids = {t["id"] for t in todo}
        todo += [l for l in lots if l["city"] in want and l["id"] not in todo_ids
                 and (l.get("coord_src") or "").startswith("지오코딩")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"대상 {len(todo)}곳 (좌표 없는 곳 {len(missing)}곳)", file=sys.stderr)

    def work(lot):
        sigs = sigs_all.get(lot["city"], set())
        if not sigs:
            # 기존 좌표가 없는 구·시는 시·군 이름 지오코딩으로 익힌 서명을 쓴다.
            s = getattr(idx[lot["city"]], "signature", None)
            if s:
                sigs = {s}
        cands = harvest_lot(lot, idx[lot["city"]], sigs, cities_meta.get(lot["city"], ""))
        chosen = pick(lot, cands, bool(sigs), lot["city"] in bbox_only_cities)
        return {"id": lot["id"], "city": lot["city"], "gu": lot.get("gu"),
                "dong": lot.get("dong"), "name": lot["name"],
                "addr_jibun": lot.get("addr_jibun"), "addr_road": lot.get("addr_road"),
                "chosen": chosen, "candidates": cands}

    if args.workers and args.workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(work, lot): lot for lot in todo}
            done_n = 0
            for fut in as_completed(futs):
                lot = futs[fut]
                done_n += 1
                try:
                    row = fut.result()
                except Exception as e:  # noqa
                    print(f"[{done_n}/{len(todo)}] {lot['city']} {lot['name']}: 실패 {e}", file=sys.stderr)
                    continue
                prev["rows"].append(row)
                ch = row["chosen"]
                status = "—" if not ch else f"{ch['lat']:.6f},{ch['lng']:.6f} {ch['confidence']}"
                print(f"[{done_n}/{len(todo)}] {lot['city']} {lot['name']}: {status}", file=sys.stderr)
                if done_n % 20 == 0:
                    out_path.write_text(json.dumps(prev, ensure_ascii=False, indent=1))
    else:
        for i, lot in enumerate(todo, 1):
            row = work(lot)
            prev["rows"].append(row)
            chosen = row["chosen"]
            status = "—" if not chosen else f"{chosen['lat']:.6f},{chosen['lng']:.6f} {chosen['confidence']}"
            print(f"[{i}/{len(todo)}] {lot['city']} {lot['name']}: {status}", file=sys.stderr)
            if i % 10 == 0:
                out_path.write_text(json.dumps(prev, ensure_ascii=False, indent=1))
    out_path.write_text(json.dumps(prev, ensure_ascii=False, indent=1))
    picked = [r for r in prev["rows"] if r.get("chosen")]
    print(f"저장 {out_path} · 행 {len(prev['rows'])} · 좌표 확보 {len(picked)}", file=sys.stderr)


if __name__ == "__main__":
    main()
