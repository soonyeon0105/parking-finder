#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전기차 충전소 데이터 정제 — 한국환경공단 충전소 스냅샷을 사이트 입력 JSON으로.

입력(수집 크론이 쌓는 스냅샷, 덮어쓰지 않는 시점별 파일):
  ~/workspace/goals/ai/hidden_files/datahunt/ev-charging/snapshots/
    inventory_*.json.gz  하루 1회 전수 목록(getChargerInfo) — 위치·주소·운영기관·타입
    status_*.json.gz     10분 간격 상태(getChargerStatus, 최근 10분 변경분만)
  상태 병합: (statId, chgerId) 키로 statUpdDt(상태 갱신 시각)이 더 최신인 쪽을 채택한다.
  인벤토리의 stat 은 전수 수집 시각 기준이라, 그 뒤 상태 스냅샷이 이긴다.

출력:
  data/ev_stations.json  지역(시·군·구)별 충전소 집계 — build_ev.py 입력
  data/ev_nearby.json    주차장별 근처 충전소(1km 안 최대 3곳) — build_site.py 입력

판정 기준:
  · 급속/완속 — 환경공단 충전기 타입 기준. AC완속(02)만 완속, 나머지는 급속으로 센다
    (공표 통계의 급속 대수와 대체로 일치: 2026-11-26 스냅샷 기준 급속 59,424기).
  · '충전 가능' 표시(주차장) — 거리 근접이 아니라 **그 주차장 안에 충전소가 있는
    경우**만(2026-11-28 운영자 확정). 판정은 station_onsite(): 이름 일치 ·
    주소 일치 · 좌표 15m 안 중 하나. 거리만 가까운 남의 시설(상가·오피스텔·
    가로등형 노상 충전기 등)에는 표시하지 않고, 큰 부지라 중심 좌표에서 100m를
    넘어도 이름·주소가 같은 시설이면 표시한다. 가까운 충전소 목록(상세 페이지용,
    1km 안 최대 3곳)은 거리 기준 그대로 유지하되 시설 일치 여부를 'fc'로 실어
    상세·FAQ가 같은 충전소를 가리키게 한다.
  · 지역 — 주소 문자열이 제각각이라(강원도/강원특별자치도 혼재 등) 행정구역 코드
    (zscode, 신 코드 체계)를 키로 쓰고, 이름은 그 지역 주소들의 다수결로 정한다.
    시·도 이름·슬러그는 주차장 데이터(site.json cities)와 맞춰 상호 링크를 건다.

사용법: python3 scripts/prepare_ev.py [--snapshot-dir 경로]
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_SNAP_DIR = Path.home() / "workspace/goals/ai/hidden_files/datahunt/ev-charging/snapshots"

sys.path.insert(0, str(BASE / "scripts"))
import build_site as bs  # 슬러그 생성 규칙(로마자 변환)을 주차장 빌더와 공유한다

# 충전기 타입 코드(한국환경공단) — 표시 이름이 확정된 코드만 이름을 붙이고,
# 나머지는 급속/완속 구분만 표시한다(지어내지 않는다).
TYPE_LABEL = {
    "01": "DC차데모", "02": "AC완속", "03": "DC차데모·AC 3상", "04": "DC콤보",
    "05": "DC차데모·DC콤보", "06": "DC차데모·AC 3상·DC콤보", "07": "AC 3상",
}
SLOW_TYPES = {"02"}
STAT_LABEL = {"1": "통신이상", "2": "충전 가능", "3": "충전 중",
              "4": "운영 중지", "5": "점검 중", "9": "상태 미확인"}

# 신 행정구역 코드(zcode 2자리) → 주차장 데이터의 시·도 이름·슬러그.
# 12는 2026년 출범한 전남광주통합특별시 코드로, 광주광역시 구도 함께 들어 있다.
ZPROV = {
    "11": ("서울특별시", "seoul"), "12": ("전남광주통합특별시", "jeonnam"),
    "26": ("부산광역시", "busan"), "27": ("대구광역시", "daegu"),
    "28": ("인천광역시", "incheon"), "29": ("광주광역시", "gwangju"),
    "30": ("대전광역시", "daejeon"), "31": ("울산광역시", "ulsan"),
    "36": ("세종특별자치시", "sejong"), "41": ("경기도", "gyeonggi"),
    "43": ("충청북도", "chungbuk"), "44": ("충청남도", "chungnam"),
    "47": ("경상북도", "gyeongbuk"), "48": ("경상남도", "gyeongnam"),
    "50": ("제주특별자치도", "jeju"), "51": ("강원특별자치도", "gangwon"),
    "52": ("전북특별자치도", "jeonbuk"),
}
# zcode 12(전남광주) 안의 광주광역시 구는 주차장 데이터에서 광주광역시 소속이다.
ZPROV_CANDIDATES = {"12": ["전남광주통합특별시", "광주광역시"]}

ONSITE_M = 100          # (구 기준·build_ev.py의 충전소→주차장 근접 판정용으로만 유지)
NEARBY_M = 1000         # 상세 페이지 근처 충전소 표시 범위
NEARBY_MAX = 3
COORD_SAME_M = 15       # 좌표가 사실상 같은 지점 — 시설 일치 보조 판정

# ---- '같은 시설' 판정 (2026-11-28 운영자 확정) ------------------------------
# 이름은 표기가 제각각이라(예: 주차장명 '수원역환승' vs 충전소명 '수원역환승주차장')
# 접미를 단계적으로 벗긴 변형들을 만들어 대조한다. '인계공영주차장'처럼 '공영'이
# 이름 몸통인 경우를 위해 한 번에 끝까지 벗기지 않고 단계별 변형을 전부 후보로 둔다.
NAME_SUFFIXES = ["공영주차장", "민영주차장", "노외주차장", "노상주차장", "부설주차장",
                 "주차타워", "주차빌딩", "주차장"]
ROAD_RE = re.compile(r"([가-힣A-Za-z0-9]+(?:로|길))\s*(\d+(?:-\d+)?)")
JIBUN_RE = re.compile(r"([가-힣]+(?:동|리|가))\s*(\d+(?:-\d+)?)\s*(?:번지)?")


def name_variants(n: str) -> set:
    base = re.sub(r"[\s()\[\]·,./\-_]", "", n or "")
    out = {base} if base else set()
    cur = base
    for _ in range(3):
        nxt = None
        for suf in NAME_SUFFIXES:
            if cur.endswith(suf) and len(cur) > len(suf):
                nxt = cur[: -len(suf)]
                break
        if not nxt or nxt == cur:
            break
        out.add(nxt)
        cur = nxt
    return out


def facility_name_match(lot_name: str, st_name: str) -> bool:
    va, vb = name_variants(lot_name), name_variants(st_name)
    if not va or not vb:
        return False
    if va & vb:
        return True
    for a in va:
        for b in vb:
            short, long = (a, b) if len(a) <= len(b) else (b, a)
            # 포함 관계는 짧은 쪽이 4자 이상일 때만 — '시청'·'고등동' 같은 짧은
            # 일반명이 남의 시설 이름에 들어간 것으로는 판정하지 않는다.
            if len(short) >= 4 and short in long:
                return True
    return False


def _norm_addr(a: str) -> str:
    a = re.sub(r"\([^)]*\)", "", a or "")
    return re.sub(r"\s+", "", a)


def _city_token(a: str) -> str:
    toks = (a or "").split()
    return toks[1] if len(toks) >= 2 else ""


def facility_addr_match(addr_road: str, addr_jibun: str, st_addr: str) -> bool:
    sa = _norm_addr(st_addr)
    if not sa:
        return False
    for la_raw in (addr_road, addr_jibun):
        la = _norm_addr(la_raw or "")
        if la and (sa == la or sa.startswith(la) or la.startswith(sa)):
            return True
    lr = ROAD_RE.search(addr_road or "")
    sr = ROAD_RE.search(st_addr or "")
    if (lr and sr and lr.groups() == sr.groups()
            and _city_token(addr_road) == _city_token(st_addr)):
        return True
    lj = JIBUN_RE.search(addr_jibun or "")
    sj = JIBUN_RE.search(st_addr or "")
    if (lj and sj and lj.groups() == sj.groups()
            and _city_token(addr_jibun) == _city_token(st_addr)):
        return True
    return False


def station_onsite(lot: dict, st_nm: str, st_addr: str, dist: float) -> bool:
    """충전소가 그 주차장 '안'에 있는가 — 이름·주소·좌표 중 하나로 판정한다."""
    if dist <= COORD_SAME_M:
        return True
    if facility_name_match(lot.get("name") or "", st_nm or ""):
        return True
    return facility_addr_match(lot.get("addr_road") or "", lot.get("addr_jibun") or "",
                               st_addr or "")


def fmt_ts(raw: str) -> str:
    """'20261126124735' → '2026-11-26 12:47'. 형식이 다르면 원문 앞부분만."""
    raw = (raw or "").strip()
    if len(raw) >= 12 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {raw[8:10]}:{raw[10:12]}"
    return raw[:16]


def haversine(lat1, lng1, lat2, lng2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_snapshot(snap_dir: Path, prefix: str) -> dict:
    files = sorted(snap_dir.glob(f"{prefix}_*.json.gz"))
    if not files:
        raise SystemExit(f"스냅샷이 없습니다: {snap_dir}/{prefix}_*.json.gz")
    with gzip.open(files[-1], "rt", encoding="utf-8") as f:
        data = json.load(f)
    print(f"{prefix}: {files[-1].name} · 수집 {data.get('collected_at_kst')} · {data.get('item_count')}건")
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot-dir", default=str(DEFAULT_SNAP_DIR))
    args = ap.parse_args()
    snap_dir = Path(args.snapshot_dir)

    inv = load_snapshot(snap_dir, "inventory")
    st = load_snapshot(snap_dir, "status")

    # ---- 상태 병합: (statId, chgerId) → 더 최신인 stat/statUpdDt
    status_map = {}
    for it in st["items"]:
        status_map[(it["statId"], it["chgerId"])] = it

    chargers = {}
    for it in inv["items"]:
        if it.get("delYn") == "Y":
            continue
        key = (it["statId"], it["chgerId"])
        s = status_map.get(key)
        if s and (s.get("statUpdDt") or "") > (it.get("statUpdDt") or ""):
            it = {**it, "stat": s["stat"], "statUpdDt": s["statUpdDt"],
                  "lastTsdt": s.get("lastTsdt") or it.get("lastTsdt"),
                  "lastTedt": s.get("lastTedt") or it.get("lastTedt"),
                  "nowTsdt": s.get("nowTsdt") or it.get("nowTsdt")}
        chargers[key] = it
    print(f"충전기(삭제 제외): {len(chargers)}기")

    # ---- 충전소 집계
    stations = {}
    for (stat_id, chger_id), it in chargers.items():
        s = stations.get(stat_id)
        if s is None:
            s = stations[stat_id] = {
                "id": stat_id, "nm": it.get("statNm") or "(이름 없음)",
                "addr": (it.get("addr") or "").strip(), "ad": (it.get("addrDetail") or "").strip(),
                "lat": float(it["lat"]), "lng": float(it["lng"]),
                "op": it.get("busiNm") or "", "call": it.get("busiCall") or "",
                "ut": it.get("useTime") or "", "zs": it.get("zscode") or "", "zc": it.get("zcode") or "",
                "pf": "", "lim": "", "note": "", "f": 0, "s": 0,
                "a": 0, "c": 0, "dn": 0, "un": 0, "upd": "", "ch": [],
            }
        t = it.get("chgerType") or ""
        fast = t not in SLOW_TYPES
        if fast:
            s["f"] += 1
        else:
            s["s"] += 1
        stat = it.get("stat") or "9"
        if stat == "2":
            s["a"] += 1
        elif stat == "3":
            s["c"] += 1
        elif stat in ("4", "5"):
            s["dn"] += 1
        else:
            # 통신이상(1)·상태미확인(9)은 상태를 모르는 것이므로 미확인으로 센다
            # (2026-11-27 규칙 — refresh_ev_status.py 와 동일).
            s["un"] += 1
        upd = it.get("statUpdDt") or ""
        if upd > s["upd"]:
            s["upd"] = upd
        if it.get("parkingFree") == "Y":
            s["pf"] = "Y"
        elif it.get("parkingFree") == "N" and not s["pf"]:
            s["pf"] = "N"
        if it.get("limitYn") == "Y" and it.get("limitDetail"):
            s["lim"] = it["limitDetail"]
        if it.get("note"):
            s["note"] = it["note"]
        out = it.get("output") or ""
        try:
            out_f = float(out)
            out_s = f"{out_f:g}" if out_f > 0 else ""
        except ValueError:
            out_s = ""
        label = TYPE_LABEL.get(t) or ("급속" if fast else "완속")
        s["ch"].append([chger_id, label, out_s, STAT_LABEL.get(stat, "상태 미확인")])
    for s in stations.values():
        s["ch"].sort(key=lambda r: r[0])
        s["upd"] = fmt_ts(s["upd"])
    print(f"충전소: {len(stations)}곳")

    # ---- 지역: zscode 키, 이름은 주소 다수결
    site = json.loads((BASE / "data" / "site.json").read_text(encoding="utf-8"))
    parking_city = {}
    for c in site["cities"]:
        parking_city[(c.get("province"), c["city"])] = c

    votes = defaultdict(Counter)
    for s in stations.values():
        toks = s["addr"].split()
        if len(toks) >= 2:
            votes[s["zs"]][toks[1]] += 1

    def short_of(prov: str) -> str:
        return prov.replace("특별시", "").replace("광역시", "").replace("특별자치시", "").replace("특별자치도", "")

    regions = {}
    for zs, s_list in sorted(_group_by(stations.values(), "zs").items()):
        zc = zs[:2]
        prov, pslug = ZPROV.get(zc, ("기타", ""))
        if zs == "36110":
            name = "세종시"
        elif votes.get(zs):
            name = votes[zs].most_common(1)[0][0]
        else:
            name = zs
        # 주차장 도시 매칭 — 이름 표기 차이(예: '부산 중구' vs '중구')를 후보 키로 흡수한다.
        city = None
        name_cands = [name, "세종특별자치시"] if zs == "36110" else [name]
        for prov_cand in ZPROV_CANDIDATES.get(zc, [prov]):
            for name_cand in name_cands + [f"{short_of(prov_cand)} {name}"]:
                city = parking_city.get((prov_cand, name_cand))
                if city:
                    prov, pslug = prov_cand, city.get("province_slug") or pslug
                    break
            if city:
                break
        slug = city["slug"] if city else bs.city_slug(name)
        regions[zs] = {
            "zs": zs, "prov": prov, "pslug": pslug, "name": name, "slug": slug,
            "pk": f"/parking/{pslug}/{slug}/" if city else "",
            "stations": sorted(s_list, key=lambda s: s["nm"]),
        }
    matched = sum(1 for r in regions.values() if r["pk"])
    print(f"지역: {len(regions)}개 · 주차장 도시 매칭 {matched}개")

    # ---- 주차장별 근처 충전소
    cell = 0.02
    grid = defaultdict(list)
    for s in stations.values():
        grid[(int(s["lat"] / cell), int(s["lng"] / cell))].append(s)

    def region_path(s) -> str:
        r = regions.get(s["zs"])
        return f"/ev/{r['pslug']}/{r['slug']}/" if r else "/ev/"

    nearby = {}
    n_onsite = 0
    for lot in site["lots"]:
        if not lot.get("lat") or not lot.get("lng"):
            continue
        la, ln = float(lot["lat"]), float(lot["lng"])
        ci, cj = int(la / cell), int(ln / cell)
        found = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for s in grid.get((ci + di, cj + dj), ()):
                    d = haversine(la, ln, s["lat"], s["lng"])
                    if d <= NEARBY_M:
                        found.append((d, s))
        if not found:
            continue
        found.sort(key=lambda x: x[0])
        fc_of = {s["id"]: station_onsite(lot, s["nm"], s["addr"], d) for d, s in found}
        top = [{
            "id": s["id"], "nm": s["nm"], "d": round(d), "addr": s["addr"],
            "f": s["f"], "s": s["s"], "a": s["a"], "t": s["f"] + s["s"],
            "upd": s["upd"], "lat": s["lat"], "lng": s["lng"], "rp": region_path(s),
            "fc": 1 if fc_of[s["id"]] else 0,
        } for d, s in found[:NEARBY_MAX]]
        onsite = [s for d, s in found if fc_of[s["id"]]]
        entry = {"d": round(found[0][0]), "on": 1 if onsite else 0, "st": top}
        if onsite:
            n_onsite += 1
            entry["f"] = sum(s["f"] for s in onsite)
            entry["s"] = sum(s["s"] for s in onsite)
            entry["a"] = sum(s["a"] for s in onsite)
        nearby[lot["id"]] = entry
    print(f"근처 충전소가 있는 주차장: {len(nearby)}곳 · 안에 충전소가 있는 곳(충전 가능) {n_onsite}곳")

    meta = {
        "inv_at": fmt_ts(inv["collected_at_kst"].replace("-", "").replace(":", "").replace("T", "")[:14]) if inv.get("collected_at_kst") else "",
        "inv_collected": inv.get("collected_at_kst", ""),
        "st_collected": st.get("collected_at_kst", ""),
        "n_stations": len(stations), "n_chargers": len(chargers),
        "n_lots_near": len(nearby), "n_lots_onsite": n_onsite,
        "onsite_m": ONSITE_M, "nearby_m": NEARBY_M,
        "onsite_rule": "facility",  # 'on'은 거리 기준이 아니라 같은 시설 판정(2026-11-28)
    }
    out_stations = {"meta": meta, "regions": [regions[zs] for zs in sorted(regions)]}
    (BASE / "data" / "ev_stations.json").write_text(
        json.dumps(out_stations, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (BASE / "data" / "ev_nearby.json").write_text(
        json.dumps({"meta": meta, "lots": nearby}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("저장: data/ev_stations.json, data/ev_nearby.json")


def _group_by(items, key):
    out = defaultdict(list)
    for it in items:
        out[it[key]].append(it)
    return out


if __name__ == "__main__":
    main()
