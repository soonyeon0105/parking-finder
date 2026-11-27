#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전기차 충전소 상태 갱신 파이프라인 v1 — 스냅샷 병합 → 사이트 데이터 갱신.

prepare_ev.py 가 하루 1회 전수 재구축(지역·근처 주차장까지 전부 다시 계산)이라면,
이 스크립트는 그 사이를 메우는 상태 전용 갱신이다.

입력(수집 크론이 쌓는 스냅샷, 덮어쓰지 않는 시점별 파일):
  ~/workspace/goals/ai/hidden_files/datahunt/ev-charging/snapshots/
    inventory_*.json.gz  하루 1회 전수 목록(getChargerInfo, 충전기별 현재 stat 포함)
    status_*.json.gz     매시간 상태 변경분(getChargerStatus, 최근 변경분만)

병합 규칙:
  · 기준은 가장 최근 인벤토리다(전수라 모든 충전기의 상태·확인 시각이 여기서 시작).
  · 인벤토리보다 뒤에 수집된 상태 스냅샷을 시간순으로 얹는다. 충전기 키
    (statId, chgerId)로, statUpdDt(상태 변경 시각)가 더 최신인 쪽의 stat 을 채택
    (prepare_ev.py 와 같은 규칙).
  · 확인 시각(confirmed_at, 'cf')은 statUpdDt 가 아니라 '그 충전기가 스냅샷에
    마지막으로 등장한 수집 시각'이다. 상태가 안 바뀌면 statUpdDt 는 몇 달 전일
    수 있지만 방치가 아니라 미변경일 뿐이라, 표기는 확인 시각 기준으로 한다
    (2026-11-27 규칙 — build_ev.py·Functions 의 upd_span 이 'cf'를 읽는다).
  · 셈 규칙: 2 충전대기→가능(a), 3→충전 중(c), 4·5→점검·운영중지(dn),
    1 통신이상·9 상태미확인→미확인(un). 통신이상은 상태를 모르는 것이므로
    점검·운영중지에 넣지 않는다(prepare_ev.py 와 동일 규칙).
  · 새 인벤토리에 없는 미갱신 충전소도 예외가 아니다: 옛 집계는 구 규칙
    (1→dn)으로 계산된 것일 수 있어, 저장된 ch 행 라벨에서 a/c/dn/un을
    다시 유도한다(counts_from_ch_labels). f/s·upd·ch 행·cf(cf는 옛 수집
    시각)는 그대로 둔다.

갱신 대상(충전소 집합·지역 배치는 기존 데이터를 그대로 둔다 — 신규·삭제
충전소는 세서 보고만 한다):
  data/ev_stations.json   충전소별 f/s/a/c/dn/un/upd/ch + 'cf' 추가, meta 갱신
  data/ev_nearby.json     prepare_ev.py 와 같은 방식(1km 안 최대 3곳·'안에 있음'
                          합계는 시설 일치 판정 station_onsite 기준)으로 다시
                          계산하되 'upd' 자리에는 확인 시각(cf)을 넣는다
                          (build_site.py 가 '상태 확인'으로 표시하는 값과 일치).
  dist/                   build_ev.py 를 다시 실행해 /ev/ 목록·상세 JSON·내 주변
                          인덱스·템플릿을 재생성한다. build_ev.py 는 사이트맵에
                          EV 주소를 덧붙이므로, 실행 전에 기존 EV 항목을 걷어낸다.

사용법: python3 scripts/refresh_ev_status.py [--snapshot-dir 경로] [--no-build]
"""
from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent
DEFAULT_SNAP_DIR = Path.home() / "workspace/goals/ai/hidden_files/datahunt/ev-charging/snapshots"

sys.path.insert(0, str(BASE / "scripts"))
from prepare_ev import STAT_LABEL, TYPE_LABEL, SLOW_TYPES, fmt_ts, haversine, station_onsite  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
ONSITE_M = 100  # (구 거리 기준 — 'on' 판정은 prepare_ev.station_onsite 시설 일치로 대체됨)
NEARBY_M = 1000
NEARBY_MAX = 3

# 저장된 ch 행 라벨 → 상태 코드 (STAT_LABEL 역매핑). 미갱신 충전소의 집계
# 재유도용 — 라벨은 refresh 전 데이터가 가진 마지막 확인 상태 그대로이다.
LABEL_TO_STAT = {v: k for k, v in STAT_LABEL.items()}


def counts_from_ch_labels(ch_rows):
    """저장된 ch 행 라벨([chgerId, 타입라벨, 출력, 상태라벨])에서 a/c/dn/un
    집계를 다시 유도한다. 규칙은 prepare_ev.py와 동일: 2→a, 3→c, 4·5→dn,
    1(통신이상)·9(상태 미확인)→un. f/s는 타입이 바뀌지 않으므로 건드리지 않는다."""
    a = c = dn = un = 0
    for row in ch_rows:
        stat = LABEL_TO_STAT.get(row[3] if len(row) > 3 else "", "9")
        if stat == "2":
            a += 1
        elif stat == "3":
            c += 1
        elif stat in ("4", "5"):
            dn += 1
        else:
            un += 1
    return a, c, dn, un


def load_gz(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def collected_dt(data: dict) -> datetime:
    return datetime.fromisoformat(data["collected_at_kst"])


def fmt_collected(data: dict) -> str:
    """collected_at_kst(ISO) → 'YYYY-MM-DD HH:MM'."""
    return data["collected_at_kst"][:16].replace("T", " ")


def fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot-dir", default=str(DEFAULT_SNAP_DIR))
    ap.add_argument("--base", default="https://parking.9welfare.com")
    ap.add_argument("--no-build", action="store_true", help="build_ev.py 재실행 생략")
    args = ap.parse_args()
    snap_dir = Path(args.snapshot_dir)

    # ---- 1) 스냅샷 선택: 최신 인벤토리 + 그 이후 상태 스냅샷 전부
    inv_files = sorted(snap_dir.glob("inventory_*.json.gz"))
    if not inv_files:
        raise SystemExit(f"인벤토리 스냅샷이 없습니다: {snap_dir}")
    inv = load_gz(inv_files[-1])
    inv_dt = collected_dt(inv)
    print(f"인벤토리: {inv_files[-1].name} · 수집 {inv['collected_at_kst']} · {inv.get('item_count')}건")

    status_snaps = []
    for fp in sorted(snap_dir.glob("status_*.json.gz")):
        data = load_gz(fp)
        if collected_dt(data) > inv_dt:
            status_snaps.append((fp.name, data))
    status_snaps.sort(key=lambda t: collected_dt(t[1]))
    if status_snaps:
        print(f"상태 스냅샷: {len(status_snaps)}개 · {status_snaps[0][0]} ~ {status_snaps[-1][0]} "
              f"(마지막 수집 {status_snaps[-1][1]['collected_at_kst']})")
    else:
        print("상태 스냅샷: 인벤토리 이후 없음 (인벤토리만으로 갱신)")

    # ---- 2) 충전기 병합: (statId, chgerId) → 최신 stat + 확인 시각
    chargers = {}   # key → {stat, upd(원문 statUpdDt), type, output, statId}
    confirmed = {}  # key → 확인한 스냅샷 수집 시각(datetime)
    for it in inv["items"]:
        if it.get("delYn") == "Y":
            continue
        key = (it["statId"], it["chgerId"])
        chargers[key] = {"stat": it.get("stat") or "9",
                         "upd": it.get("statUpdDt") or "",
                         "type": it.get("chgerType") or "",
                         "output": it.get("output") or "",
                         "statId": it["statId"], "chgerId": it["chgerId"]}
        confirmed[key] = inv_dt
    n_status_only = 0
    n_adopted = 0
    for _name, snap in status_snaps:
        snap_dt = collected_dt(snap)
        for it in snap["items"]:
            key = (it["statId"], it["chgerId"])
            cur = chargers.get(key)
            if cur is None:
                n_status_only += 1
                continue
            confirmed[key] = snap_dt
            if (it.get("statUpdDt") or "") > cur["upd"]:
                cur["stat"] = it.get("stat") or "9"
                cur["upd"] = it.get("statUpdDt") or ""
                n_adopted += 1
    print(f"충전기 병합: {len(chargers):,}기 · 상태 스냅샷 채택 {n_adopted:,}건 · "
          f"인벤토리에 없는 상태 항목 {n_status_only:,}건(무시)")

    by_station = defaultdict(list)
    for key, ch in chargers.items():
        by_station[ch["statId"]].append((key, ch))

    # ---- 3) data/ev_stations.json 갱신 (충전소 집합·순서·지역은 기존 유지)
    ev_path = BASE / "data" / "ev_stations.json"
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    old_meta = ev["meta"]
    old_inv_at = old_meta.get("inv_at", "")
    n_changed = n_unrefreshed = n_rederived = 0
    changed_ids = []
    total_chargers_in_data = 0
    for region in ev["regions"]:
        for s in region["stations"]:
            rows = by_station.get(s["id"])
            if not rows:
                # 새 인벤토리에 없는 충전소 — 옛 상태 유지, 확인 시각은 옛 수집 기준.
                # 단, 집계(a/c/dn/un)는 저장된 ch 행 라벨에서 다시 유도한다. 옛 집계는
                # 구 규칙(통신이상 1→dn)으로 계산된 것이라, 그대로 두면 통신이상이
                # 점검·운영중지로 잡히는 7곳 예외가 남는다. f/s·upd·ch 행·cf는 그대로.
                a2, c2, dn2, un2 = counts_from_ch_labels(s.get("ch", []))
                if (s.get("a"), s.get("c"), s.get("dn"), s.get("un")) != (a2, c2, dn2, un2):
                    s.update({"a": a2, "c": c2, "dn": dn2, "un": un2})
                    n_rederived += 1
                s["cf"] = old_inv_at
                n_unrefreshed += 1
                continue
            f = sl = a = c = dn = un = 0
            upd_max = ""
            cf_max = None
            ch_rows = []
            for key, ch in sorted(rows, key=lambda t: t[1]["chgerId"]):
                fast = ch["type"] not in SLOW_TYPES
                if fast:
                    f += 1
                else:
                    sl += 1
                stat = ch["stat"]
                if stat == "2":
                    a += 1
                elif stat == "3":
                    c += 1
                elif stat in ("4", "5"):
                    dn += 1
                else:
                    un += 1
                if ch["upd"] > upd_max:
                    upd_max = ch["upd"]
                cf = confirmed[key]
                if cf_max is None or cf > cf_max:
                    cf_max = cf
                try:
                    out_f = float(ch["output"])
                    out_s = f"{out_f:g}" if out_f > 0 else ""
                except (TypeError, ValueError):
                    out_s = ""
                label = TYPE_LABEL.get(ch["type"]) or ("급속" if fast else "완속")
                ch_rows.append([ch["chgerId"], label, out_s,
                                STAT_LABEL.get(stat, "상태 미확인")])
            new_vals = {"f": f, "s": sl, "a": a, "c": c, "dn": dn, "un": un,
                        "upd": fmt_ts(upd_max), "ch": ch_rows}
            if any(s.get(k) != v for k, v in new_vals.items()):
                n_changed += 1
                changed_ids.append(s["id"])
            s.update(new_vals)
            s["cf"] = fmt_iso(cf_max)
            total_chargers_in_data += f + sl
    known_ids = {s["id"] for r in ev["regions"] for s in r["stations"]}
    n_new_stations = sum(1 for sid in by_station if sid not in known_ids)
    latest_dt = collected_dt(status_snaps[-1][1]) if status_snaps else inv_dt
    meta = dict(old_meta)
    meta.update({
        "onsite_rule": "facility",
        "inv_at": fmt_collected(inv),
        "inv_collected": inv["collected_at_kst"],
        "st_collected": status_snaps[-1][1]["collected_at_kst"] if status_snaps else inv["collected_at_kst"],
        "n_stations": len(known_ids),
        "n_chargers": total_chargers_in_data,
        "refreshed_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "cf_at": fmt_iso(latest_dt),
        "refresh": {
            "inventory_file": inv_files[-1].name,
            "status_files": [name for name, _ in status_snaps],
            "stations_changed": n_changed,
            "stations_unrefreshed": n_unrefreshed,
            "stations_new_ignored": n_new_stations,
        },
    })
    ev["meta"] = meta
    ev_path.write_text(json.dumps(ev, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"충전소 갱신: 전체 {len(known_ids):,}곳 · 상태 바뀐 곳 {n_changed:,}곳 · "
          f"새 인벤토리에 없는 곳 {n_unrefreshed:,}곳 · 미갱신 중 ch 라벨에서 집계 재유도 {n_rederived:,}곳 · "
          f"신규 충전소 {n_new_stations:,}곳(미반영, 보고만)")
    print(f"바뀐 충전소 예시: {', '.join(changed_ids[:10])}")

    # ---- 4) data/ev_nearby.json 재계산 (prepare_ev.py 와 같은 방식, 'upd' 자리 = cf)
    site = json.loads((BASE / "data" / "site.json").read_text(encoding="utf-8"))
    region_path = {}
    station_by_id = {}
    for r in ev["regions"]:
        for s in r["stations"]:
            region_path[s["id"]] = f"/ev/{r['pslug']}/{r['slug']}/"
            station_by_id[s["id"]] = s
    cell = 0.02
    grid = defaultdict(list)
    for s in station_by_id.values():
        grid[(int(s["lat"] / cell), int(s["lng"] / cell))].append(s)
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
        top = [{"id": s["id"], "nm": s["nm"], "d": round(d), "addr": s["addr"],
                "f": s["f"], "s": s["s"], "a": s["a"], "t": s["f"] + s["s"],
                "upd": s.get("cf") or "", "lat": s["lat"], "lng": s["lng"],
                "rp": region_path.get(s["id"], "/ev/"),
                "fc": 1 if fc_of[s["id"]] else 0} for d, s in found[:NEARBY_MAX]]
        onsite = [s for d, s in found if fc_of[s["id"]]]
        entry = {"d": round(found[0][0]), "on": 1 if onsite else 0, "st": top}
        if onsite:
            n_onsite += 1
            entry["f"] = sum(s["f"] for s in onsite)
            entry["s"] = sum(s["s"] for s in onsite)
            entry["a"] = sum(s["a"] for s in onsite)
        nearby[lot["id"]] = entry
    meta_nb = dict(meta)
    meta_nb["n_lots_near"] = len(nearby)
    meta_nb["n_lots_onsite"] = n_onsite
    (BASE / "data" / "ev_nearby.json").write_text(
        json.dumps({"meta": meta_nb, "lots": nearby}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    # ev_stations.json 의 meta 에도 근처 집계가 실려 있어(/ev/ 허브 lede) 함께 맞춘다.
    if meta.get("n_lots_near") != len(nearby) or meta.get("n_lots_onsite") != n_onsite:
        meta["n_lots_near"] = len(nearby)
        meta["n_lots_onsite"] = n_onsite
        ev_path.write_text(json.dumps(ev, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"근처 충전소 재계산: 주차장 {len(nearby):,}곳 · 안에 충전소가 있는 곳 {n_onsite:,}곳")

    if args.no_build:
        print("--no-build: dist 재생성을 건너뜁니다.")
        return

    # ---- 5) 사이트맵의 기존 EV 항목을 걷어내고 build_ev.py 재실행
    sm_path = BASE / "dist" / "sitemap.xml"
    sm = sm_path.read_text(encoding="utf-8")
    ev_marker = f"<loc>{args.base}/ev/"
    lines = sm.split("\n")
    kept = [ln for ln in lines if ev_marker not in ln]
    print(f"사이트맵 EV 항목 제거: {len(lines) - len(kept):,}개")
    sm_path.write_text("\n".join(kept), encoding="utf-8")
    r = subprocess.run([sys.executable, str(BASE / "scripts" / "build_ev.py"),
                        "--base", args.base],
                       cwd=str(BASE), capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"build_ev.py 실패 (rc={r.returncode}) — 사이트맵 EV 항목이 빠진 상태일 수 있습니다")
    print("갱신 완료.")


if __name__ == "__main__":
    main()
