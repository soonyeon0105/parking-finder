#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공영주차장 파인더 - 데이터 정제 스크립트 (수원시 + 성남시 + 용인시 + 화성시 + 안양시 + 평택시 + 부천시 + 고양시)

입력(모두 실제 공개 데이터, data/raw/):
  1) 전국주차장정보표준데이터 (공공데이터포털 15012896, CSV, EUC-KR)  -> 요금/운영시간/좌표/특기사항
     - 수원시 59행 : 요금·운영시간·좌표
     - 성남시 164행: 요금·운영시간·좌표 (노외 98행 + 노상 66행)
     - 용인시 214행: 요금·운영시간·좌표 (노외 71 + 부설 89 + 노상 54)
     - 화성시 127행: 요금·운영시간·좌표 (노외 78 + 노상 49, 만세·효행·병점·동탄 4개 구)
     - 안양시 107행: 요금·운영시간·좌표 (노외 78 + 노상 29, 만안·동안 2개 구)
     - 평택시 161행: 요금·운영시간·좌표 (노외 75 + 노상 86, 구 없이 3읍 5면·동)
     - 부천시 109행: 요금·운영시간·좌표 (노외 72 + 부설 29 + 노상 8, 원미·소사·오정 3개 구)
     - 고양시 88행: 요금·운영시간·좌표 (노외 63 + 부설 17 + 노상 8, 덕양·일산동·일산서 3개 구)
  2) 수원도시공사 공영주차장 통합 안내 지도(parking.suwonudc.co.kr/parking/parkingMap) 임베드 JSON 스냅샷
     -> 실시간 잔여면수, 장애인/경차/전기차/여성/임산부 구획수 (수원시만)
  3) 경기도 수원시_공영노외주차장현황 (공공데이터포털 15157772, CSV, EUC-KR) -> 주소/면수 보강 (수원시만)
  4) 안양도시공사 통합주차포털(parking.auc.or.kr) 주차장 목록 JSON 스냅샷
     -> 법정동이 적힌 주소, 일일 최대요금, 1일 선불요금, 월정기권, 장애인·전기차 구획 (안양시만)
  5) 평택도시공사 공영주차장 포털(parking.puc.or.kr) 주차장 목록 JSON 스냅샷
     -> 급지(1~3급지)·기본시간·기본요금·간격요금·1일 최대요금·월정기권, 법정동 주소 (평택시만)
  6) 부천주차포털(parking.bcits.go.kr) 공영주차장 목록 JSON 스냅샷 + 부천도시공사 공영주차장 일반현황(엑셀)
     -> 주차장별 급지·기본 30분·10분당·1일 최대요금·정기권(주간·야간·전일)·장애인 구획 (부천시만)

출력:
  data/site.json             도시 통합 결과(사이트 생성기 입력: cities[] + lots[])
  data/suwon_parking.json    수원시 단독 결과(기존 경로 호환)
  data/seongnam_parking.json 성남시 단독 결과
  data/yongin_parking.json   용인시 단독 결과
  data/hwaseong_parking.json 화성시 단독 결과
  data/anyang_parking.json   안양시 단독 결과
  data/pyeongtaek_parking.json 평택시 단독 결과
  data/bucheon_parking.json  부천시 단독 결과
  data/goyang_parking.json   고양시 단독 결과
  data/data_quality.json     수원시 정합성 점검 결과(기존 경로 호환)
  scripts/summary.md         사람이 읽는 정제 요약 (도시별)
  scripts/summary.json       기계가 읽는 정제 요약 (도시별)

사용법:  python3 scripts/prepare_data.py [--city suwon|seongnam|yongin|hwaseong|anyang|pyeongtaek|bucheon|goyang|all]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
DATA = BASE / "data"

STD_CSV = RAW / "전국주차장정보표준데이터_data.go.kr_15012896.csv"
UDC_JSON = RAW / "parking.suwonudc.co.kr_parkingMap_20261116.json"
NOOE_CSV = RAW / "경기도수원시_공영노외주차장현황_data.go.kr_15157772.csv"

KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)


def _snapshot_time(path: Path) -> datetime:
    """원자료 스냅샷의 수집 시각.

    파일 mtime 은 저장소를 새로 clone 할 때마다 바뀌므로, 수집 시각을 적어 둔
    sidecar(*_fetched_at.txt)가 있으면 그 값을 쓴다. 없을 때만 mtime 으로 대체한다.
    """
    sidecar = path.with_name(path.stem + "_fetched_at.txt")
    if sidecar.exists():
        return datetime.strptime(sidecar.read_text().strip(), "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    return datetime.fromtimestamp(path.stat().st_mtime, KST)


UDC_FETCHED = _snapshot_time(UDC_JSON)

GU_SLUG = {"영통구": "suwon-yeongtong", "권선구": "suwon-gwonseon",
           "팔달구": "suwon-paldal", "장안구": "suwon-jangan"}
GU_ORDER = ["영통구", "권선구", "팔달구", "장안구"]


# ---------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv_kr(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"인코딩 판별 실패: {path}")


def to_int(v):
    if v is None:
        return None
    s = re.sub(r"[^0-9.-]", "", str(v))
    if s in ("", "-", ".", "-."):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f == int(f) else f


def norm_name(s: str) -> str:
    return re.sub(r"[\s()\[\]·,.ㆍ\-]", "", s or "")


def km(a_lat, a_lng, b_lat, b_lng) -> float:
    """근사 미터 거리 (수도권 위도 기준)"""
    dy = (float(a_lat) - float(b_lat)) * 111_000
    dx = (float(a_lng) - float(b_lng)) * 88_000
    return math.hypot(dx, dy)


def parse_hm(v):
    """'09:00' -> 540 (분). 값이 없으면 None."""
    if not v:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})", str(v).strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h == 0 and mi == 0:
        return 0
    return h * 60 + mi


def day_window(start, end):
    """운영 시작/종료 문자열 -> (열림여부, 시작분, 종료분, 24시간여부)"""
    s, e = parse_hm(start), parse_hm(end)
    if s is None or e is None:
        return False, None, None, False
    if s == 0 and e == 0:
        return False, 0, 0, False          # 00:00~00:00 = 휴무
    if e == 24 * 60 or (s == 0 and e == 23 * 60 + 59):
        return True, 0, 24 * 60, True
    if e <= s:                             # 자정 넘김
        return True, s, 24 * 60, False
    return True, s, e, False


def fmt_time(v):
    if not v:
        return "정보 없음"
    m = re.match(r"^(\d{1,2}):(\d{2})", str(v))
    if not m:
        return str(v)
    h, mi = int(m.group(1)), int(m.group(2))
    if h == 0 and mi == 0:
        return "00:00"
    if h == 23 and mi == 59:
        return "24:00"
    return f"{h:02d}:{mi:02d}"


# ---------------------------------------------------------------- 1) 표준데이터
def load_standard():
    rows = read_csv_kr(STD_CSV)
    suwon = []
    for r in rows:
        addr = f"{r.get('소재지지번주소', '')} {r.get('소재지도로명주소', '')}"
        if "수원시" not in addr:
            continue
        suwon.append(r)
    return rows, suwon


def parse_free_days(note: str):
    """특기사항의 '무료개방' 표현에서 무료 요일을 뽑는다. (일/공휴일 기준만 신뢰)"""
    out = {"sat": False, "sun": False}
    if not note:
        return out
    txt = note.replace(" ", "")
    if "무료개방" not in txt and "무료운영" not in txt and "무료" not in txt:
        return out
    # 시간대 한정 무료개방(예: 04~07:00 무료개방)은 요일 무료가 아니다
    time_limited = re.search(r"\d{1,2}\s*~\s*\d{1,2}:?\d{0,2}\s*무료개방", txt)
    if time_limited and not re.search(r"(일|공휴일|주말|토)[^)]{0,8}무료개방", txt):
        return out
    if re.search(r"(일요일|일|주말|토요일|토|공휴일)[+,·]*", txt):
        if "주말" in txt or re.search(r"토(요일)?[+\-·]?일", txt) or re.search(r"토(요일)?\+", txt):
            out["sat"] = True
        if "일" in txt or "공휴일" in txt:
            out["sun"] = True
    return out


def parse_free_window(note: str):
    m = re.search(r"(\d{1,2})\s*~\s*(\d{1,2}):?(\d{2})?\s*무료개방", note or "")
    if not m:
        return None
    h1 = int(m.group(1))
    h2 = int(m.group(2))
    return f"{h1:02d}:00~{h2:02d}:{m.group(3) or '00'}"


def dong_from_jibun(addr: str):
    if not addr:
        return None
    m = re.search(r"([가-힣]{1,5}\d?동)\s*\d", addr)
    if m:
        return m.group(1)
    m = re.search(r"([가-힣]{1,5}동)\b", addr)
    return m.group(1) if m else None


def gu_from_addr(addr: str):
    m = re.search(r"수원시\s*(\S+구)", addr or "")
    return m.group(1) if m else None


def parse_schedule(row, note):
    """\uc6b4\uc601\uc694\uc77c\u00b7\uc694\uc77c\ubcc4 \uc6b4\uc601\uc2dc\uac04 \uce78\uc744 \uc77d\uc5b4 (hours, oper, closed_from_note) \ub97c \ub9cc\ub4e0\ub2e4.

    hours[key] = {open, start, end, 24h, listed, raw[, note_closed]}
    \ud2b9\uae30\uc0ac\ud56d\uc5d0 \uc801\ud78c \uc694\uc77c \ud734\ubb34(\uc608: '\uc6d4\uc694\uc77c+\uacf5\ud734\uc77c \ud3d0\uc1c4')\ub294 \uc6b4\uc601\uc2dc\uac04 \uce78\ubcf4\ub2e4 \uc6b0\uc120\ud55c\ub2e4.
    """
    raw_oper = (row.get("\uc6b4\uc601\uc694\uc77c") or "").replace(" ", "")
    oper = {key for key, token in (("weekday", "\ud3c9\uc77c"), ("sat", "\ud1a0\uc694\uc77c"), ("sun", "\uacf5\ud734\uc77c"))
            if token in raw_oper}
    win = {}
    for key, (cs, ce) in {
        "weekday": ("\ud3c9\uc77c\uc6b4\uc601\uc2dc\uc791\uc2dc\uac01", "\ud3c9\uc77c\uc6b4\uc601\uc885\ub8cc\uc2dc\uac01"),
        "sat": ("\ud1a0\uc694\uc77c\uc6b4\uc601\uc2dc\uc791\uc2dc\uac01", "\ud1a0\uc694\uc77c\uc6b4\uc601\uc885\ub8cc\uc2dc\uac01"),
        "sun": ("\uacf5\ud734\uc77c\uc6b4\uc601\uc2dc\uc791\uc2dc\uac01", "\uacf5\ud734\uc77c\uc6b4\uc601\uc885\ub8cc\uc2dc\uac01"),
    }.items():
        opened, s, e, full = day_window(row.get(cs), row.get(ce))
        win[key] = {"open": opened and key in oper, "start": s, "end": e,
                    "24h": full, "listed": key in oper,
                    "raw": [fmt_time(row.get(cs)), fmt_time(row.get(ce))]}

    # \ud2b9\uae30\uc0ac\ud56d\uc5d0 \uba85\uc2dc\ub41c \uc694\uc77c \ud734\ubb34\ub294 \uc6b4\uc601\uc2dc\uac04 \uce78\ubcf4\ub2e4 \uc6b0\uc120\ud55c\ub2e4.
    closed_note = False
    partial = re.search(r"\d\s*[,\u00b7]\s*\d\s*\uc8fc", note) or re.search(r"(\uccab\uc9f8|\ub458\uc9f8|\uc14b\uc9f8|\ub137\uc9f8)\s*\uc8fc", note)
    for key, pat in ([] if partial else (("sun", r"\uacf5\ud734\uc77c[^)]{0,6}(\ud3d0\uc1c4|\ud734\ubb34)"),
                                      ("sun", r"\uc77c\uc694\uc77c[^)]{0,6}(\ud3d0\uc1c4|\ud734\ubb34)"),
                                      ("sat", r"\ud1a0\uc694\uc77c[^)]{0,6}(\ud3d0\uc1c4|\ud734\ubb34)"))):
        if re.search(pat, note):
            if win[key]["open"]:
                closed_note = True
            win[key]["open"] = False
            win[key]["note_closed"] = True
    return win, {k: v["open"] for k, v in win.items()}, closed_note


# ---------------------------------------------------------------- 2) 도시공사 실시간
def load_udc():
    raw = json.loads(UDC_JSON.read_text())
    lots = []
    for d in raw:
        lots.append({
            "udc_id": d.get("PARKING_ID"),
            "name": (d.get("PARKING_NM") or "").strip(),
            "spaces": to_int(d.get("CELL_CNT")),
            "lat": float(d["LAT"]) if d.get("LAT") else None,
            "lng": float(d["LNG"]) if d.get("LNG") else None,
            "div": (d.get("PARKING_DIV_NM") or "").strip(),
            "operator": (d.get("OPERATE_NM") or "").strip(),
            "open_yn": d.get("OPEN_YN"),
            "free_now": to_int(d.get("CURRENT_CNT")),
            "in_use": to_int(d.get("USE_CNT")),
            "congestion": d.get("CONGESTION_LEVEL"),
            "disabled": to_int(d.get("DISABLED_TOTAL_CELL_CNT")),
            "compact": to_int(d.get("COMPACT_TOTAL_CELL_CNT")),
            "eco": to_int(d.get("ECO_TOTAL_CELL_CNT")),
            "elec": to_int(d.get("ELEC_TOTAL_CELL_CNT")),
            "woman": to_int(d.get("WOMAN_TOTAL_CELL_CNT")),
            "pregnant": to_int(d.get("PREGNANT_TOTAL_CELL_CNT")),
        })
    return lots


# ---------------------------------------------------------------- 3) 노외주차장현황
def load_nooe():
    rows = read_csv_kr(NOOE_CSV)
    out = []
    for r in rows:
        name = (r.get("주차장명") or "").strip()
        addr = (r.get("소재지지번주소") or "").strip()
        out.append({
            "name": name,
            "nname": norm_name(name),
            "addr": addr,
            "spaces": to_int(r.get("주차면수")),
            "tel": (r.get("전화번호") or "").strip(),
            "fee_type": (r.get("요금형태") or "").strip(),
            "form": (r.get("급지 및 운영형태") or "").strip(),
        })
    return out


# ---------------------------------------------------------------- 수원시
CITY_META = {
    # dong_page_min_lots: 동별 페이지를 만드는 최소 노외 주차장 수.
    #   수원시는 이미 색인된 동 페이지(29개)를 그대로 유지해야 하므로 1곳부터 만든다.
    #   새로 확장하는 성남·용인·화성시는 3곳 미만 동을 구 페이지 표에만 두어 빈 페이지를 만들지 않는다.
    "수원시": {"slug": "suwon", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 1},
    "성남시": {"slug": "seongnam", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "용인시": {"slug": "yongin", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "화성시": {"slug": "hwaseong", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "안양시": {"slug": "anyang", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "평택시": {"slug": "pyeongtaek", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "부천시": {"slug": "bucheon", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "고양시": {"slug": "goyang", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
}


# 수원시 공영주차장 요금 감면 — 「수원시 주차장 조례」(경기도수원시조례 제4645호, 2024-11-14 개정,
# 2025-01-01 시행)와 수원도시공사·수원컨벤션센터 요금 감면 안내(2026-11-16 확인).
#   · 100%     : 모범·유공납세자(성실납세자) 인증서 소지 차량 — 교부일부터 1년
#   · 24시간 면제 후 50% : 국가유공자 본인·유족, 5·18민주유공자, 특수임무유공자, 중증장애인(기존 1~3급)
#   · 2시간 면제 후 50%  : 경증장애인(기존 4~6급), 저공해자동차 1종
#   · 50%     : 경차(1,000cc 미만)·저공해 2·3종·다자녀가정(2자녀 이상, 최연소 만 18세 이하)·
#               병역명문가·임산부(동승 포함)·자원봉사자·장기기증등록자
#   · 감면이 겹치면 비율이 높은 하나만 적용
SUWON_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·다자녀·임산부 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경차(1,000cc 미만)·저공해 2·3종·다자녀·임산부·병역명문가 등"},
    {"label": "경증장애인·저공해1종 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "경증장애인(4~6급)·저공해 1종, 2시간까지 면제"},
    {"label": "중증장애인·국가유공자 24시간 면제 후 50%", "rate": 0.5, "exempt_min": 1440,
     "note": "중증장애인(1~3급)·국가유공자, 24시간까지 면제"},
    {"label": "모범·유공납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "모범·유공·성실납세자 인증서 소지 차량(1년)"},
]


def build_suwon():
    std_all, std_suwon = load_standard()
    udc = load_udc()
    nooe = load_nooe()

    # --- 동 중심좌표(추정용): 지번주소가 있는 행만 사용
    centroid = defaultdict(list)
    for r in std_suwon:
        d = dong_from_jibun(r.get("소재지지번주소", ""))
        g = gu_from_addr(r.get("소재지지번주소") or r.get("소재지도로명주소", ""))
        if d and g and r.get("위도") and r.get("경도"):
            centroid[(g, d)].append((float(r["위도"]), float(r["경도"])))
    centroid = {k: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v))
                for k, v in centroid.items()}

    lots = []
    for _seq, r in enumerate(std_suwon, 1):
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        gu = gu_from_addr(addr)
        dong = dong_from_jibun(jibun)
        dong_src = "지번주소"
        if not dong:
            m = re.search(r"([가-힣]{1,5}\d?동)", r.get("주차장명", ""))
            if m:
                dong, dong_src = m.group(1), "주차장명"
        fee_type = (r.get("요금정보") or "").strip()
        base_min = to_int(r.get("주차기본시간"))
        base_fee = to_int(r.get("주차기본요금"))
        unit_min = to_int(r.get("추가단위시간"))
        unit_fee = to_int(r.get("추가단위요금"))
        daily_h = to_int(r.get("1일주차권요금적용시간"))
        daily_fee = to_int(r.get("1일주차권요금"))
        note = (r.get("특기사항") or "").strip()

        win, oper, closed_note = parse_schedule(r, note)

        free_days = parse_free_days(note)
        if fee_type == "무료":
            free_days = {"sat": True, "sun": True}

        lots.append({
            "id": f"std-{_seq:03d}",
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "name": (r.get("주차장명") or "").strip(),
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),          # 공영/민영
            "ptype": (r.get("주차장유형") or "").strip(),          # 노외/노상/부설
            "addr_jibun": jibun,
            "addr_road": road,
            "spaces": to_int(r.get("주차구획수")),
            "tel": (r.get("전화번호") or "").strip(),
            "lat": float(r["위도"]) if r.get("위도") else None,
            "lng": float(r["경도"]) if r.get("경도") else None,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": {
                "type": fee_type or "미상",
                "base_min": base_min, "base_fee": base_fee,
                "unit_min": unit_min, "unit_fee": unit_fee,
                "daily_hours": daily_h, "daily_fee": daily_fee,
                "monthly": to_int(r.get("월정기권요금")),
                "pay": (r.get("결제방법") or "").strip(),
            },
            "oper": {k: v["open"] for k, v in win.items()},
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "realtime": None,
            "udc_id": None,
        })

    # --- 동 추정(좌표 최근접)
    for lot in lots:
        if lot["dong"] or lot["lat"] is None or lot["gu"] is None:
            continue
        cand = {k: v for k, v in centroid.items() if k[0] == lot["gu"]}
        if not cand:
            continue
        best = min(cand.items(), key=lambda kv: km(lot["lat"], lot["lng"], kv[1][0], kv[1][1]))
        lot["dong"], lot["dong_src"] = best[0][1], "좌표근접(추정)"

    # --- 표준데이터 행에 도시공사 실시간 정보 매칭
    #     (좌표 거리 + 구획수 차이 가중, 전역 그리디 배정)
    udc_by_id = {u["udc_id"]: u for u in udc}
    cand = []
    for li, lot in enumerate(lots):
        if lot["lat"] is None:
            continue
        ln = norm_name(lot["name"])
        for u in udc:
            if u["lat"] is None:
                continue
            d = km(lot["lat"], lot["lng"], u["lat"], u["lng"])
            capa_diff = abs((lot["spaces"] or 0) - (u["spaces"] or 0))
            un = norm_name(u["name"])
            name_hit = bool(ln and un and (ln == un or ln in un or un in ln))
            ok = ((d <= 120 and capa_diff <= 25)
                  or (capa_diff == 0 and d <= 300)
                  or (name_hit and d <= 1500 and capa_diff <= 40))
            if not ok:
                continue
            score = d + 5 * capa_diff - (60 if ln == un else 0)
            cand.append((score, li, u["udc_id"]))
    cand.sort()
    used_udc, matched_idx = set(), set()
    for score, li, uid in cand:
        if li in matched_idx or uid in used_udc:
            continue
        matched_idx.add(li)
        used_udc.add(uid)
        u = udc_by_id[uid]
        lots[li]["udc_id"] = uid
        lots[li]["realtime"] = {
            "free": u["free_now"], "total": u["spaces"],
            "level": u["congestion"], "src_name": u["name"],
        }
        if lots[li]["spaces"] is None:
            lots[li]["spaces"] = u["spaces"]

    # 남은 표준데이터 행: 같은 동 + 구획수 완전 일치(유일)로 보정 매칭
    for li, lot in enumerate(lots):
        if li in matched_idx or lot["spaces"] is None:
            continue
        pool = [u for u in udc if u["udc_id"] not in used_udc
                and u["spaces"] == lot["spaces"] and u["lat"] is not None
                and km(lot["lat"], lot["lng"], u["lat"], u["lng"]) <= 2000]
        if len(pool) == 1:
            u = pool[0]
            used_udc.add(u["udc_id"])
            matched_idx.add(li)
            lot["udc_id"] = u["udc_id"]
            lot["realtime"] = {"free": u["free_now"], "total": u["spaces"],
                              "level": u["congestion"], "src_name": u["name"]}

    # --- 도시공사에만 있는 주차장 추가
    added = 0
    existing_names = {norm_name(l["name"]) for l in lots}
    for u in udc:
        if u["udc_id"] in used_udc:
            continue
        if u["lat"] is None or not u["name"]:
            continue
        if norm_name(u["name"]) in existing_names:
            continue  # 이름이 같은 주차장이 이미 목록에 있으면 중복 추가하지 않음
        # 구 판정: 같은 구의 동 중심과의 최근접
        best_gu, best_d = None, None
        for (g, d), c in centroid.items():
            dd = km(u["lat"], u["lng"], c[0], c[1])
            if best_d is None or dd < best_d:
                best_gu, best_d = g, dd
        gu = best_gu
        # 동 판정
        cand = {k: v for k, v in centroid.items() if k[0] == gu}
        dong, dong_src = None, "좌표근접(추정)"
        if cand:
            best = min(cand.items(), key=lambda kv: km(u["lat"], u["lng"], kv[1][0], kv[1][1]))
            dong = best[0][1]
        # 노외주차장현황에서 주소 보강
        naddr, ntel, nspaces = None, None, None
        un = norm_name(u["name"])
        for row in nooe:
            rn = row["nname"]
            if not rn:
                continue
            if rn == un or (len(un) >= 3 and (rn.startswith(un) or un.startswith(rn))) \
                    or (len(un) >= 4 and un in rn):
                naddr, ntel = row["addr"], row["tel"] or None
                nspaces = row["spaces"]
                break
        lots.append({
            "id": f"udc-{u['udc_id']}",
            "src": "수원도시공사 실시간 목록",
            "name": u["name"],
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": "공영" if u["div"] in ("공영", "부설") else (u["div"] or "공영"),
            "ptype": "부설" if u["div"] == "부설" else "노외",
            "addr_jibun": naddr or "",
            "addr_road": "",
            "spaces": nspaces or u["spaces"],
            "tel": ntel or "",
            "lat": u["lat"], "lng": u["lng"],
            "base_date": NOW.strftime("%Y-%m-%d"),
            "manager": u["operator"],
            "note": "",
            "fee": {"type": "미상", "base_min": None, "base_fee": None,
                    "unit_min": None, "unit_fee": None, "daily_hours": None,
                    "daily_fee": None, "monthly": None, "pay": ""},
            "oper": {"weekday": True, "sat": True, "sun": True},
            "hours": {k: {"open": True, "start": 0, "end": 24 * 60, "24h": True,
                          "listed": True, "raw": ["00:00", "24:00"]}
                      for k in ("weekday", "sat", "sun")},
            "free_days": {"sat": False, "sun": False},
            "free_window": None,
            "disabled_area": "Y" if (u["disabled"] or 0) > 0 else "",
            "realtime": {"free": u["free_now"], "total": u["spaces"],
                         "level": u["congestion"], "src_name": u["name"]},
            "udc_id": u["udc_id"],
            "capa_detail": {k: u[k] for k in ("disabled", "compact", "eco", "elec", "woman", "pregnant")},
        })
        added += 1

    # --- 정렬용 파생값
    for lot in lots:
        lot["price_key"] = lot["fee"]["base_fee"] if lot["fee"]["type"] != "미상" else None

    # --- 정합성 점검
    quality = check_quality(std_all, std_suwon, udc, lots, added)

    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": UDC_FETCHED.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "수원시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-16", "rows_total": len(std_all),
                    "rows_suwon": len(std_suwon),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": "공공데이터포털 '그리드 다운로드'로 받은 CSV(EUC-KR). 로그인·인증키 없이 수령.",
                },
                {
                    "id": "udc", "name": "수원도시공사 공영주차장 통합 안내(지도) 실시간 목록",
                    "org": "수원도시공사",
                    "url": "https://parking.suwonudc.co.kr/parking/parkingMap",
                    "file": UDC_JSON.name, "sha256": sha256(UDC_JSON),
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": UDC_FETCHED.strftime("%Y-%m-%d"),
                    "rows_total": len(udc),
                    "fetched_at": UDC_FETCHED.strftime("%Y-%m-%d %H:%M (KST)")
                                  + " (페이지 저장 시각 기준)",
                    "note": "지도 페이지에 내장된 주차장 목록(잔여면수·구획 구성) 스냅샷. 실시간 값은 조회 시점 기준.",
                },
                {
                    "id": "nooe", "name": "경기도 수원시_공영노외주차장현황",
                    "org": "경기도 수원시",
                    "url": "https://www.data.go.kr/data/15157772/fileData.do",
                    "file": NOOE_CSV.name, "sha256": sha256(NOOE_CSV),
                    "license": "이용허락범위 제한 없음",
                    "base_date": "2026-08-01", "rows_total": len(nooe),
                    "fetched_at": "2026-11-16 19:11 (KST)",
                    "note": "주소·면수 보강용.",
                },
            ],
        },
        "districts": [
            {"name": g, "slug": GU_SLUG[g]} for g in GU_ORDER
        ],
        "lots": lots,
        "quality": quality,
    }
    payload.update(CITY_META["수원시"] | {
        "city": "수원시",
        "weekend_free_pages": True,
        "discounts": SUWON_DISCOUNTS,   # T-02 B안: 조례 기준 감면 버튼(2025-01-01 시행)
        "realtime": True,
    })
    for lot in lots:
        lot["city"] = "수원시"
        lot["city_slug"] = "suwon"
        lot.setdefault("list_mode", "card")      # 카드 목록에 그리는 주차장

    (DATA / "suwon_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    (DATA / "data_quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=1))
    return payload


# ---------------------------------------------------------------- quality
def check_quality(std_all, std_suwon, udc, lots, added):
    by_gu = Counter(l["gu"] for l in lots)
    by_dong = Counter((l["gu"], l["dong"]) for l in lots)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    no_coord = [l["name"] for l in lots if l["lat"] is None or l["lng"] is None]
    no_addr = [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])]
    fee_missing = [l["name"] for l in lots if l["fee"]["type"] == "미상"]
    fee_broken = []
    for l in lots:
        f = l["fee"]
        if f["type"] in ("미상", "무료"):
            continue
        if not f["base_min"] or f["base_fee"] in (None, "") or not f["unit_min"] \
                or f["unit_fee"] is None:
            fee_broken.append(l["name"])
    free_lots = [l["name"] for l in lots if l["fee"]["type"] == "무료"]
    weekend_free = [l["name"] for l in lots if l["free_days"]["sat"] or l["free_days"]["sun"]]
    sun_free = [l["name"] for l in lots if l["free_days"]["sun"]]
    sat_free = [l["name"] for l in lots if l["free_days"]["sat"]]
    closed_sat = [l["name"] for l in lots if not l["oper"]["sat"]]
    closed_sun = [l["name"] for l in lots if not l["oper"]["sun"]]
    rt = [l for l in lots if l["realtime"]]
    dup_names = [k for k, v in Counter(l["name"] for l in lots).items() if v > 1]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    dup_mgmt = [{"번호": k, "주차장": [l["name"] for l in lots if l.get("mgmt_no") == k]}
                for k, v in mgmt.items() if v > 1]
    base_fees = [l["fee"]["base_fee"] for l in lots
                 if l["fee"]["type"] not in ("미상", "무료") and l["fee"]["base_fee"]]
    avg_base = round(sum(base_fees) / len(base_fees)) if base_fees else None
    # 좌표 범위(수원시 대략 경계) 점검
    bad_coord = [(l["name"], l["lat"], l["lng"]) for l in lots
                 if l["lat"] and (not (37.20 <= l["lat"] <= 37.36) or not (126.92 <= l["lng"] <= 127.12))]
    # 표준데이터 면수 vs 도시공사 면수 차이
    capa_diff = []
    for l in lots:
        if l["realtime"] and l["spaces"] and l["realtime"].get("total"):
            if l["fee"]["type"] != "미상":
                delta = l["spaces"] - l["realtime"]["total"]
                if abs(delta) >= 10:
                    capa_diff.append((l["name"], l["spaces"], l["realtime"]["total"]))

    summary = {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "총_주차장": len(lots),
        "원자료_전국행수": len(std_all),
        "원자료_수원시행수": len(std_suwon),
        "도시공사_목록행수": len(udc),
        "도시공사_추가행수": added,
        "실시간_연계_표준데이터": len([l for l in lots if l["realtime"] and l["src"] == "표준데이터"]),
        "실시간_연계_전체": len(rt),
        "구별": dict(by_gu),
        "특기사항_기준_휴무": [l["name"] for l in lots if l.get("closed_from_note")],
        "동별": {f"{g} {d}": c for (g, d), c in sorted(by_dong.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
        "요금구분": dict(fee_types),
        "무료_요금구분": free_lots,
        "주말무료_표기": weekend_free,
        "일공휴일무료": sun_free,
        "토요일무료": sat_free,
        "토요일_미운영": len(closed_sat),
        "일공휴일_미운영": len(closed_sun),
        "평균_기본요금": avg_base,
        "좌표_없음": no_coord,
        "주소_없음": no_addr,
        "요금_미상": fee_missing,
        "요금_필드불완전": fee_broken,
        "이름중복": dup_names,
        "관리번호중복": dup_mgmt,
        "좌표_범위이탈": bad_coord,
        "면수_차이_10면이상": capa_diff,
        "총_구획수": sum(l["spaces"] or 0 for l in lots),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }
    return summary


# ---------------------------------------------------------------- 성남시 (T-03 Phase 1)
SEONGNAM_PROVIDER = "경기도 성남시"
SEONGNAM_DISTRICTS = [("수정구", "seongnam-sujeong"),
                      ("중원구", "seongnam-jungwon"),
                      ("분당구", "seongnam-bundang")]
SEONGNAM_BBOX = (37.33, 37.48, 127.05, 127.20)      # 성남시 대략 경계(좌표 점검용)

# 성남시 공영주차장 요금 감면 — 성남도시개발공사(park.isdc.co.kr) '노외주차장 > 요금감면' 및
# 「성남시 주차장 설치 및 관리 운영에 관한 조례」 별표2 (2026-11-16 확인).
#   · 50%     : 경차, 저공해차, 만 65세 이상, 임산부, 다자녀, 병역명문가, 환승
#   · 1시간 면제 후 50% : 장애인, 자원봉사활동 차량
#   · 12시간 면제 후 50%: 국가유공자·유족, 5·18 부상자, 고엽제환자, 참전유공자
#   · 100%    : 모범·유공·성실납세자 (월정기 감면 안내)
SEONGNAM_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경차·저공해차·만 65세 이상·임산부·다자녀·병역명문가·환승"},
    {"label": "장애인 1시간 면제 후 50%", "rate": 0.5, "exempt_min": 60,
     "note": "장애인 복지카드·장애인 자동차표지"},
    {"label": "국가유공자 12시간 면제 후 50%", "rate": 0.5, "exempt_min": 720,
     "note": "국가유공자·유족, 5·18부상자, 고엽제환자, 참전유공자"},
]


def seongnam_gu(addr: str):
    for g, _ in SEONGNAM_DISTRICTS:
        if g in (addr or ""):
            return g
    return None


def road_name(addr: str):
    """도로명주소에서 도로 이름만 뽑다(예: '경기도 성남시 중원구 산성대로 415' → '산성대로')."""
    body = re.sub(r"^\S+\s+\S+\s+\S+구\s+", "", (addr or "").strip())
    m = re.match(r"([가-힣A-Za-z0-9]+?(?:대로|로|길))", body)
    return m.group(1) if m else None


def build_seongnam():
    """성남시 공영주차장을 표준데이터에서 추출한다(도시공사 실시간 목록은 미수집).

    노외(건물식) 주차장은 카드 목록(list_mode='card')으로, 노상(거리) 구간은
    이름이 '중상32-75'처럼 구간 번호라 카드로 빚으면 정보가 반복되는 껍데기 페이지가 된다.
    따라서 노상 66구간은 list_mode='street'으로 분리해 별도 표·전용 페이지에서 다룬다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == SEONGNAM_PROVIDER]
    lots, excluded = [], []
    seq = card_no = street_no = 0

    for r in rows:
        seq += 1
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 기준 — 이름·주소·좌표·구획수 중 하나라도 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif not (SEONGNAM_BBOX[0] <= lat <= SEONGNAM_BBOX[1]
                  and SEONGNAM_BBOX[2] <= lng <= SEONGNAM_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        gu = seongnam_gu(addr)
        dong = dong_from_jibun(jibun)
        dong_src = "지번주소"
        if not dong:
            m = re.search(r"([가-힣]{1,5}\d?동)", name)
            if m:
                dong, dong_src = m.group(1), "주차장명"
            else:
                dong_src = "없음"

        note = (r.get("특기사항") or "").strip()
        fee_raw = (r.get("요금정보") or "").strip()
        base_min = to_int(r.get("주차기본시간"))
        base_fee = to_int(r.get("주차기본요금"))
        unit_min = to_int(r.get("추가단위시간"))
        unit_fee = to_int(r.get("추가단위요금"))
        daily_h = to_int(r.get("1일주차권요금적용시간"))
        daily_fee = to_int(r.get("1일주차권요금"))
        monthly = to_int(r.get("월정기권요금"))

        # 요금정보: 무료 / 유료 / 혼합 (혼합 = 운영시간만 유료, 그 외 시간 미운영으로 등록된 노상 구간)
        if fee_raw == "무료":
            ftype = "무료"
        elif fee_raw in ("유료", "혼합"):
            ftype = "유료" if (base_min and base_fee is not None and base_min and unit_fee is not None) else "미상"
        else:
            ftype = "미상"

        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)
        if ftype == "무료":
            free_days = {"sat": True, "sun": True}

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"sn-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"sn-{card_no:03d}"

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": {
                "type": ftype,
                "raw_type": fee_raw,          # 원자료 표기(유료/무료/혼합)
                "mixed": fee_raw == "혼합",
                "grade": (r.get("급지구분") or "").strip(),
                "base_min": base_min, "base_fee": base_fee,
                "unit_min": unit_min, "unit_fee": unit_fee,
                "daily_hours": daily_h, "daily_fee": daily_fee,
                "monthly": monthly if monthly else None,
                "pay": (r.get("결제방법") or "").strip(),
            },
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "realtime": None,
            "udc_id": None,
            "price_key": base_fee if ftype == "유료" else None,
            "city": "성남시",
            "city_slug": "seongnam",
        })

    quality = check_quality_seongnam(rows_all, rows, lots, excluded)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": None,
            "region": {"province": "경기도", "city": "성남시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-12", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": "성남시가 등록한 행만(제공기관명 '경기도 성남시') 추출. 요금·운영시간·좌표·특기사항 사용.",
                },
                {
                    "id": "isdc", "name": "성남도시개발공사 공영주차장 요금·감면 안내",
                    "org": "성남도시개발공사",
                    "url": "https://park.isdc.co.kr/roadout/useinfo_fee3.do",
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": None,
                    "fetched_at": "2026-11-16 (KST)",
                    "note": "요금 감면율(50%·1시간 면제 후 50%·12시간 면제 후 50%) 확인용 — 계산기 감면 버튼 근거.",
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in SEONGNAM_DISTRICTS],
        "lots": lots,
        "quality": quality,
    }
    payload.update(CITY_META["성남시"] | {
        "city": "성남시",
        "weekend_free_pages": False,     # 무료 개방 표기가 없어 '주말 무료' 페이지를 만들지 않는다
        "discounts": SEONGNAM_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "seongnam_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_seongnam(std_all, rows, lots, excluded):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_gu = Counter(l["gu"] for l in card)
    by_dong = Counter((l["gu"], l["dong"]) for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    fee_missing = [l["name"] for l in lots if l["fee"]["type"] == "미상"]
    fee_broken = [l["name"] for l in lots
                  if l["fee"]["type"] == "유료"
                  and not (l["fee"]["base_min"] and l["fee"]["base_fee"] is not None
                           and l["fee"]["unit_min"] and l["fee"]["unit_fee"] is not None)]
    paid = [l["fee"]["base_fee"] for l in lots
            if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_성남시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(by_gu),
        "동별": {f"{g} {d}": c for (g, d), c in sorted(by_dong.items(),
                                                   key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
        "동수": len({(l["gu"], l["dong"]) for l in card if l["dong"]}),
        "요금구분": dict(fee_types),
        "요금_미상": fee_missing,
        "요금_필드불완전": fee_broken,
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": [l["name"] for l in lots if l["fee"]["type"] == "무료"],
        "혼합_요금구분": [l["name"] for l in lots if l["fee"].get("mixed")],
        "무료개방_표기": [l["name"] for l in lots if l["fee"]["type"] != "무료"
                      and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 용인시 (T-03 Phase 2)
YONGIN_PROVIDER = "경기도 용인시"
YONGIN_DISTRICTS = [("처인구", "yongin-cheoin"),
                    ("기흥구", "yongin-giheung"),
                    ("수지구", "yongin-suji")]
YONGIN_BBOX = (37.05, 37.40, 127.00, 127.45)     # 용인시 대략 경계(좌표 점검용)
YONGIN_UNIT_RE = re.compile(r"([가-힣]{1,6}(?:동|읍|면))")
# 동·읍·면 위치를 좌표로 추정할 때 허용하는 거리. 용인시는 구 면적이 넓어
# 넓게 잡으면 옆 동으로 잘못 붙는다. 400m 안에서만 인정하고 나머지는 '동 미상'으로 둔다.
YONGIN_ESTIMATE_M = 400

# 용인시 공영주차장 요금 감면 — 용인도시공사 '주차장 요금 안내'(park.yuc.co.kr) 감면할인 안내
# 및 「용인시 주차장 설치 및 관리 조례」 별표2 (2026-11-16 확인).
#   · 100%    : 국가유공자(본인 탑승)·고엽제환자·유공납세자·제1종 저공해(2시간 이내)·공무수행 차량 등
#   · 50%     : 경형차(1,000cc 미만)·2·3종 저공해·임산부·병역명문가·우수자원봉사자·환승 등
#   · 다자녀  : 최소 2시간 무료 후 50%
#   · 장애인  : 6시간 면제 및 이후 50%
#   · 감면이 겹치면 비율이 높은 하나만 적용
YONGIN_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·임산부 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형(1,000cc 미만)·2·3종 저공해·임산부·병역명문가 등"},
    {"label": "다자녀 2시간 무료 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "경기 I-Plus·경기똑D카드 등"},
    {"label": "장애인 6시간 면제 후 50%", "rate": 0.5, "exempt_min": 360,
     "note": "등록 장애인 운전·동승 차량"},
    {"label": "국가유공자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "국가유공자 본인 탑승 차량(유족증 포함)"},
]


def gu_in(addr, districts):
    for g, _ in districts:
        if g in (addr or ""):
            return g
    return None


def unit_from_jibun(addr):
    """지번주소에서 행정동·읍·면을 뽑는다(예: '… 처인구 포곡읍 둔전리 139-6' → 포곡읍)."""
    a = addr or ""
    m = re.search(r"([가-힣]{1,6}(?:읍|면))\s+[가-힣]{1,6}리", a)
    if m:
        return m.group(1)
    m = re.search(r"([가-힣]{1,6}동)\s*\d", a)
    if m:
        return m.group(1)
    m = re.search(r"([가-힣]{1,6}(?:읍|면))\s*\d", a)
    return m.group(1) if m else None


def unit_from_road(addr):
    """도로명주소에서 읍·면만 뽑는다(도로명주소에는 동이 들어가지 않는다)."""
    m = re.search(r"(?:구|읍|면)\s+([가-힣]{1,6}(?:읍|면))\s", (addr or "") + " ")
    return m.group(1) if m else None


def yongin_known_units(rows):
    """구별로 존재하는 행정동·읍·면 이름 집합(지번주소·읍면 도로명·동 이름인 주차장명)."""
    known = defaultdict(set)
    for r in rows:
        addr = (r.get("소재지지번주소") or "") + (r.get("소재지도로명주소") or "")
        gu = gu_in(addr, YONGIN_DISTRICTS)
        if not gu:
            continue
        unit = unit_from_jibun(r.get("소재지지번주소")) or unit_from_road(r.get("소재지도로명주소"))
        if unit:
            known[gu].add(unit)
        name = (r.get("주차장명") or "").strip()
        if YONGIN_UNIT_RE.fullmatch(name):
            known[gu].add(name)
    return known


def yongin_unit(row, gu, known):
    """한 행의 행정동·읍·면과 그 근거를 정한다(주소 → 이름 → 좌표는 뒤에서)."""
    jibun = (row.get("소재지지번주소") or "").strip()
    road = (row.get("소재지도로명주소") or "").strip()
    name = (row.get("주차장명") or "").strip()
    unit = unit_from_jibun(jibun)
    if unit:
        return unit, "지번주소"
    if YONGIN_UNIT_RE.fullmatch(name):          # '유림동', '양지면'처럼 주차장명이 곧 동·읍·면
        return name, "주차장명"
    for cand in sorted(known.get(gu, ()), key=len, reverse=True):
        if cand in name:                        # '서농동 서농도서관' → 서농동
            return cand, "주차장명"
    unit = unit_from_road(road)
    if unit:
        return unit, "도로명주소"
    return None, "없음"


def build_yongin():
    """용인시 공영주차장을 표준데이터에서 추출한다(도시공사 실시간 목록은 미수집).

    성남시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 용인시 범위를 벗어난 행은 제외.
      · 노상(거리) 구간은 이름이 '전대리'·'용인성당 주변'처럼 구간 설명이라 카드 대신
        전용 표 페이지로 분리(list_mode='street').
      · 동·읍·면 페이지는 노외·부설 카드가 3곳 이상인 곳만 만든다.
    성남시와 다른 점은 용인시에 **부설(청사·도서관·공원) 주차장 89곳**이 포함된다는 것이고,
    이들은 주차구획·주소·운영시간이 모두 등록되어 있어 카드로 그린다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == YONGIN_PROVIDER]
    known = yongin_known_units(rows)
    lots, excluded = [], []
    card_no = street_no = 0

    for r in rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (YONGIN_BBOX[0] <= lat <= YONGIN_BBOX[1]
                                      and YONGIN_BBOX[2] <= lng <= YONGIN_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        gu = gu_in(addr, YONGIN_DISTRICTS)
        if not gu:
            excluded.append({"name": name, "reason": "구 판정 불가"})
            continue
        unit, unit_src = yongin_unit(r, gu, known)

        note = (r.get("특기사항") or "").strip()
        fee_raw = (r.get("요금정보") or "").strip()
        base_min = to_int(r.get("주차기본시간"))
        base_fee = to_int(r.get("주차기본요금"))
        unit_min = to_int(r.get("추가단위시간"))
        unit_fee = to_int(r.get("추가단위요금"))
        daily_h = to_int(r.get("1일주차권요금적용시간"))
        daily_fee = to_int(r.get("1일주차권요금"))
        monthly = to_int(r.get("월정기권요금"))

        if fee_raw == "무료":
            ftype = "무료"
        elif fee_raw in ("유료", "혼합"):
            ftype = "유료" if (base_min and base_fee is not None and unit_min
                               and unit_fee is not None) else "미상"
        else:
            ftype = "미상"

        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)
        if ftype == "무료":
            free_days = {"sat": True, "sun": True}

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"yn-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"yn-{card_no:03d}"

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": unit,
            "dong_src": unit_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": {
                "type": ftype,
                "raw_type": fee_raw,
                "mixed": fee_raw == "혼합",
                "grade": (r.get("급지구분") or "").strip(),
                "base_min": base_min, "base_fee": base_fee,
                "unit_min": unit_min, "unit_fee": unit_fee,
                "daily_hours": daily_h, "daily_fee": daily_fee,
                "monthly": monthly if monthly else None,
                "pay": (r.get("결제방법") or "").strip(),
            },
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "realtime": None,
            "udc_id": None,
            "price_key": base_fee if ftype == "유료" else None,
            "city": "용인시",
            "city_slug": "yongin",
        })

    # --- 동·읍·면 좌표 추정: 지번이 없어 이름으로도 못 정한 주차장만,
    #     같은 구의 확인된 동·읍·면 중심에서 400m 안일 때만 인정한다.
    centroid = defaultdict(list)
    for lot in lots:
        if lot["dong"] and lot["dong_src"] == "지번주소" and lot["lat"] is not None:
            centroid[(lot["gu"], lot["dong"])].append((lot["lat"], lot["lng"]))
    centroid = {k: (sum(x for x, _ in v) / len(v), sum(y for _, y in v) / len(v))
                for k, v in centroid.items()}
    for lot in lots:
        if lot["dong"] or lot["lat"] is None:
            continue
        cand = {k: v for k, v in centroid.items() if k[0] == lot["gu"]}
        if not cand:
            continue
        key = min(cand, key=lambda k: km(lot["lat"], lot["lng"], cand[k][0], cand[k][1]))
        if km(lot["lat"], lot["lng"], cand[key][0], cand[key][1]) <= YONGIN_ESTIMATE_M:
            lot["dong"], lot["dong_src"] = key[1], "좌표근접(추정)"

    order = {g: i for i, (g, _) in enumerate(YONGIN_DISTRICTS)}
    lots.sort(key=lambda l: (order[l["gu"]], l["list_mode"] != "card", l["name"]))

    quality = check_quality_yongin(rows_all, rows, lots, excluded)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": None,
            "region": {"province": "경기도", "city": "용인시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-24", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": "용인시가 등록한 행만(제공기관명 '경기도 용인시') 추출. 요금·운영시간·좌표·특기사항 사용.",
                },
                {
                    "id": "yuc", "name": "용인시 공영주차장 주차장 요금 안내",
                    "org": "용인도시공사",
                    "url": "https://park.yuc.co.kr/views/parkinglot/fee/fee.html",
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": None,
                    "fetched_at": "2026-11-16 (KST)",
                    "note": "요금 감면율(50%·2시간 무료 후 50%·6시간 면제 후 50%·100%)과 급지별 요금표 확인용 — 계산기 감면 버튼 근거.",
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in YONGIN_DISTRICTS],
        "lots": lots,
        "quality": quality,
    }
    payload.update(CITY_META["용인시"] | {
        "city": "용인시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": YONGIN_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "yongin_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_yongin(std_all, rows, lots, excluded):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_gu = Counter(l["gu"] for l in card)
    by_dong = Counter((l["gu"], l["dong"]) for l in card if l["dong"])
    fee_types = Counter(l["fee"]["type"] for l in lots)
    fee_broken = [l["name"] for l in lots
                  if l["fee"]["type"] == "유료"
                  and not (l["fee"]["base_min"] and l["fee"]["base_fee"] is not None
                           and l["fee"]["unit_min"] and l["fee"]["unit_fee"] is not None)]
    paid = [l["fee"]["base_fee"] for l in lots
            if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_용인시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(by_gu),
        "동별": {f"{g} {d}": c for (g, d), c in sorted(by_dong.items(),
                                                   key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
        "동수": len({(l["gu"], l["dong"]) for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_추정": [l["name"] for l in card if (l["dong_src"] or "").startswith("좌표")],
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "요금_필드불완전": fee_broken,
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots if l["fee"]["type"] != "무료"
                      and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 화성시 (T-03 Phase 3)
HWASEONG_PROVIDER = "경기도 화성시"
# 화성시는 2026-03-01부터 만세·효행·병점·동탄 4개 일반구 체제다(행정안전부 승인 2025-08-22).
# 표준데이터 주소도 구를 포함해 등록되어 있고, 구청 관할은 만세구(3읍·6면·1동),
# 효행구(1읍·3면·1동), 병점구(5동), 동탄구(동탄1~9동)이다.
HWASEONG_DISTRICTS = [("만세구", "hwaseong-manse"),
                      ("효행구", "hwaseong-hyohaeng"),
                      ("병점구", "hwaseong-byeongjeom"),
                      ("동탄구", "hwaseong-dongtan")]
HWASEONG_BBOX = (37.00, 37.36, 126.55, 127.20)   # 화성시 대략 경계(제부도 126.6~127.14 포함)

# 화성시 공영주차장 요금 감면 — 「화성시 주차장 설치 및 관리 조례」 제8조·별표 4
# (2026-11-16 확인, law.go.kr 자치법규) 및 화성시 통합주차포털·화성도시공사 안내.
#   · 100%             : 국가유공자·유족, 5·18민주화운동 부상자, 장애인(심한 장애), 모범·유공납세자(1년)
#   · 2시간 면제 후 50% : 장애인(심하지 않은 장애), 환경친화적 자동차 충전시설 이용차량
#   · 50%              : 경차(1,000cc 미만 경승용), 저공해자동차, 다자녀(경기 I-PLUS·화성다자녀카드),
#                        병역명문가, 우수자원봉사자, 환승주차, 재래시장 활성화 지정 주차장
#   · 감면이 겹치면 감면율이 가장 높은 하나만 적용
HWASEONG_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경승용(1,000cc 미만)·저공해·다자녀·병역명문가·환승·재래시장"},
    {"label": "경증장애인 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "심하지 않은 장애, 최초 2시간 면제(전기차 충전 포함)"},
    {"label": "국가유공자·중증장애인 100%", "rate": 1.0, "exempt_min": 0,
     "note": "국가유공자·유족, 5·18부상자, 심한 장애"},
    {"label": "모범·유공납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "모범·유공·성실납세자 지정차량 1대(1년)"},
]


def build_hwaseong():
    """화성시 공영주차장을 표준데이터에서 추출한다(도시공사 실시간 목록은 미수집).

    성남·용인시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나, 좌표가 화성시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 위치 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동·읍·면 페이지는 노외 카드가 3곳 이상인 곳만 만든다.
      · 요금 필드가 비면 0원이 아니라 '미상'으로 두어 화면에 ‘현장 확인’으로 나가게 한다.
    화성시는 4개 구가 있고 동 이름이 법정동(장지동·여울동 등)이라, 구는 주소의 ‘…구’를,
    동·읍·면은 지번주소를 그대로 쓴다(추정하지 않는다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == HWASEONG_PROVIDER]
    lots, excluded = [], []
    card_no = street_no = 0

    for r in rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (HWASEONG_BBOX[0] <= lat <= HWASEONG_BBOX[1]
                                      and HWASEONG_BBOX[2] <= lng <= HWASEONG_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        gu = gu_in(addr, HWASEONG_DISTRICTS)
        if not gu:
            excluded.append({"name": name, "reason": "구 판정 불가"})
            continue
        unit = unit_from_jibun(jibun)
        unit_src = "지번주소"
        if not unit:
            unit = unit_from_road(road)
            unit_src = "도로명주소"

        note = (r.get("특기사항") or "").strip()
        fee_raw = (r.get("요금정보") or "").strip()
        base_min = to_int(r.get("주차기본시간"))
        base_fee = to_int(r.get("주차기본요금"))
        unit_min = to_int(r.get("추가단위시간"))
        unit_fee = to_int(r.get("추가단위요금"))
        daily_h = to_int(r.get("1일주차권요금적용시간"))
        daily_fee = to_int(r.get("1일주차권요금"))
        monthly = to_int(r.get("월정기권요금"))

        if fee_raw == "무료":
            ftype = "무료"
        elif fee_raw in ("유료", "혼합"):
            ftype = "유료" if (base_min and base_fee is not None and unit_min
                               and unit_fee is not None) else "미상"
        else:
            ftype = "미상"

        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)
        if ftype == "무료":
            free_days = {"sat": True, "sun": True}

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"hs-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"hs-{card_no:03d}"

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": unit,
            "dong_src": unit_src if unit else "없음",
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": {
                "type": ftype,
                "raw_type": fee_raw,
                "mixed": fee_raw == "혼합",
                "grade": (r.get("급지구분") or "").strip(),
                "base_min": base_min, "base_fee": base_fee,
                "unit_min": unit_min, "unit_fee": unit_fee,
                "daily_hours": daily_h, "daily_fee": daily_fee,
                "monthly": monthly if monthly else None,
                "pay": (r.get("결제방법") or "").strip(),
            },
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "realtime": None,
            "udc_id": None,
            "price_key": base_fee if ftype == "유료" else None,
            "city": "화성시",
            "city_slug": "hwaseong",
        })

    order = {g: i for i, (g, _) in enumerate(HWASEONG_DISTRICTS)}
    lots.sort(key=lambda l: (order[l["gu"]], l["list_mode"] != "card", l["name"]))

    quality = check_quality_hwaseong(rows_all, rows, lots, excluded)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": None,
            "region": {"province": "경기도", "city": "화성시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-20", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 (KST)",
                    "note": "화성시가 등록한 행만(제공기관명 '경기도 화성시') 추출. 요금·운영시간·좌표·특기사항 사용.",
                },
                {
                    "id": "hsc", "name": "화성시 통합주차포털(공영주차장 요금·감면 안내)",
                    "org": "화성특례시·화성도시공사",
                    "url": "https://smartparking.hscity.go.kr/Main",
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": None,
                    "fetched_at": "2026-11-16 (KST)",
                    "note": "「화성시 주차장 설치 및 관리 조례」 별표 4의 감면(100%·2시간 면제 후 50%·50%) 확인용 — 계산기 감면 버튼 근거.",
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in HWASEONG_DISTRICTS],
        "lots": lots,
        "quality": quality,
    }
    payload.update(CITY_META["화성시"] | {
        "city": "화성시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": HWASEONG_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "hwaseong_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_hwaseong(std_all, rows, lots, excluded):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_gu = Counter(l["gu"] for l in card)
    by_dong = Counter((l["gu"], l["dong"]) for l in card if l["dong"])
    fee_types = Counter(l["fee"]["type"] for l in lots)
    fee_broken = [l["name"] for l in lots
                  if l["fee"]["type"] == "유료"
                  and not (l["fee"]["base_min"] and l["fee"]["base_fee"] is not None
                           and l["fee"]["unit_min"] and l["fee"]["unit_fee"] is not None)]
    paid = [l["fee"]["base_fee"] for l in lots
            if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_화성시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(by_gu),
        "동별": {f"{g} {d}": c for (g, d), c in sorted(by_dong.items(),
                                                   key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
        "동수": len({(l["gu"], l["dong"]) for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_추정": [],
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "요금_필드불완전": fee_broken,
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots if l["fee"]["type"] != "무료"
                      and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 안양시 (T-03 Phase 4)
ANYANG_PROVIDER = "경기도 안양시"
ANYANG_DISTRICTS = [("만안구", "anyang-manan"), ("동안구", "anyang-dongan")]
ANYANG_BBOX = (37.35, 37.46, 126.86, 127.00)     # 안양시 대략 경계(좌표 점검용)
# 안양시 법정동(구별). 표준데이터 주소에 행정동 이름이 들어간 행이 있어 아래 FIX 로 맞춘다.
#   - 행정동 안양1~9동 → 법정동 안양동, 석수3동 → 석수동, 호계1~3동 → 호계동, 관양1·2동 → 관양동
#   - 동안구의 평촌·귀인·범계·갈산·신촌·부흥·달안동은 법정동 이름 그대로 쓴다.
ANYANG_DONGS = {
    "만안구": ("안양동", "석수동", "박달동"),
    "동안구": ("비산동", "관양동", "호계동", "평촌동", "귀인동", "범계동",
             "신촌동", "갈산동", "부흥동", "달안동"),
}
ANYANG_DONG_FIX = {
    "안양1동": "안양동", "안양2동": "안양동", "안양3동": "안양동", "안양4동": "안양동",
    "안양5동": "안양동", "안양6동": "안양동", "안양7동": "안양동", "안양8동": "안양동",
    "안양9동": "안양동",
    "석수1동": "석수동", "석수2동": "석수동", "석수3동": "석수동",
    "호계1동": "호계동", "호계2동": "호계동", "호계3동": "호계동",
    "관양1동": "관양동", "관양2동": "관양동",
    "비산1동": "비산동", "비산2동": "비산동", "비산3동": "비산동", "비산4동": "비산동",
}
ANYANG_ALL_DONGS = tuple(d for v in ANYANG_DONGS.values() for d in v)
ANYANG_AUC_JSON = RAW / "parking.auc.or.kr_searchParkingList_20261117.json"
# 표준데이터에 지번주소가 없고 포털 목록에서도 이름으로 찾지 못한 주차장의 법정동.
# 도로명주소 확인 결과(2026-11-17, 도로명주소 안내)를 한 곳씩 대조해 적었다.
# 같은 도로라도 동이 갈리는 곳이 있어(만안로·양화로·박달우회로·병목안로가 안양동/석수동/박달동에 걸침)
# 도로 이름만으로 추정하지 않고 이 표에 있는 주차장만 확정한다.
ANYANG_DONG_VERIFIED = {
    # 양화로37번길 일대 법정동 안양동(양화로37번길 32 = 안양동 922, 안양서초초등학교)
    "서초교 옆 주차장": ("안양동", "도로명주소 확인"),
    # 박달우회로150번길 일대 법정동 안양동(박달우회로150번길 33-8 = 안양동 822-26)
    "공원아파트 뒤 주차장": ("안양동", "도로명주소 확인"),
    # 만안로 471 = 석수동 259-34(스카이빌), 만안로 461 = 석수동 262-19
    "관악역1환승 주차장": ("석수동", "도로명주소 확인"),
    "관악역2환승 주차장": ("석수동", "도로명주소 확인"),
    # 병목안로 일대 법정동 안양동(병목안로 132 = 안양동 996-1)
    "수리산교 하부 주차장": ("안양동", "도로명주소 확인"),
    "양지초등학교 앞 주차장": ("안양동", "도로명주소 확인"),
    # 박달로416번길 19 = 박달동 603-2
    "우주타운옆 주차장": ("박달동", "도로명주소 확인"),
    # 경수대로610번길 36 = 호계동 1287(평촌더샵아이파크)
    "더샵아이파크 옆 노외 주차장": ("호계동", "도로명주소 확인"),
    # 벌말로 174 = 관양동 1482(인덕원중학교)
    "관양2동복개 주차장": ("관양동", "도로명주소 확인"),
}

# 안양시 공영주차장 요금 — 「안양시 주차장 설치 및 관리 조례」 제10조 별표1 ‘공영주차장 주차요금표’
# (2021-01-01 시행, 2026-11-17 안양도시공사 통합주차포털 안내로 확인).
#   · 최초 15분은 무료 회차, 1회 주차요금 = 최초 30분 + 시간대별 누진할증(10분마다)
#   · 일일 최대요금 상한 25,000원(후불). 운영시간 전 선납하는 ‘선불 일일주차’는 주차장별로 더 싸다.
#   · 표준데이터에는 최초 30분 기본요금·급지만 있고 추가요금·일일권 칸이 비어 있어,
#     급지별 이 표를 계산기에 적용한다(급지 4·5급지는 노외주차장만).
ANYANG_FEES = {
    1: {"base_min": 30, "base_fee": 600, "tiers": (300, 600, 900, 1200)},
    2: {"base_min": 30, "base_fee": 400, "tiers": (200, 400, 600, 800)},
    3: {"base_min": 30, "base_fee": 200, "tiers": (100, 300, 400, 400)},
    4: {"base_min": 30, "base_fee": 200, "tiers": (100, 200, 200, 200)},
    5: {"base_min": 30, "base_fee": 200, "tiers": (100, 100, 100, 100)},
}
ANYANG_UNIT_MIN = 10        # 누진 할증 단위(10분)
ANYANG_FREE_MIN = 15        # 최초 15분 무료
ANYANG_DAY_CAP = 25_000     # 일일 최대요금(조례 상한)

# 안양시 공영주차장 요금 감면 — 「안양시 주차장 설치 및 관리 조례」 별표2(주차요금 감면)와
# 안양도시공사 ‘주차요금 감면대상’ 안내(2026-11-17 확인).
#   · 100%             : 긴급자동차, 공무수행 관용차, 병원진료 목적(국가유공자·고엽제·심한 장애 등),
#                        유공·모범납세자증 부착차량(1년)
#   · 최초 2시간 면제 후 50% : 국가유공자·의사상자·심한 장애인·고엽제·병역명문가·5·18부상자·우수기업인증
#                        (일일·월정주차는 70% 감면)
#   · 50%              : 심하지 않은 장애인, 65세 이상, 경차(1,000cc 미만), 저공해차, 환승, 다자녀, 임산부,
#                        우수자원봉사자, 한부모가족, 장기기증자, 명예시민, 효행, 당일 헌혈
#   · 감면이 겹치면 비율이 높은 하나만 적용
ANYANG_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·65세·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경차(1,000cc 미만)·저공해·65세 이상·다자녀·임산부·환승"},
    {"label": "심하지 않은 장애인 50%", "rate": 0.5, "exempt_min": 0,
     "note": "장애인 복지카드·자동차표지"},
    {"label": "국가유공자·심한 장애 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "국가유공자·의사상자·심한 장애·고엽제·병역명문가·5·18부상자"},
    {"label": "유공·모범납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "유공·모범납세자증 부착차량(발행일부터 1년)"},
]


# 이름 비교에서 빼는 꾸밈말 — 단계별로 넓힌다(위 anyang_auc_candidates 주석 참고).
ANYANG_KEY_FULL = ("주차장", "주차타워")
ANYANG_KEY_LIGHT = ANYANG_KEY_FULL + ("공영", "임시", "일반", "지하")
ANYANG_KEY_HARD = ANYANG_KEY_LIGHT + ("노외", "노상", "주민")
# 포털 목록의 이름이 표준데이터와 완전히 달라 이름으로는 찾지 못하는 주차장.
#   안양도시공사 요금 안내의 ‘명학동노외 (구)안양8동노외’ 표기와 같은 자리(안양동 1287)임을 확인.
ANYANG_AUC_ALIAS = {"안양8동 지하 주차장": "명학동노외"}


def anyang_name_key(s: str, strip=None) -> str:
    """주차장 이름 비교용 키 — 공백·괄호와 꾸밈말(노외/노상/지하/공영 등)을 뺀다.

    예: ‘호현마을1 공영주차장’ ↔ ‘호현마을1노외’, ‘원스퀘어 임시공영 주차장’ ↔ ‘원스퀘어임시’
    """
    t = re.sub(r"[\s()\[\]·,.ㆍ\-]", "", s or "")
    for w in (strip or ANYANG_KEY_LIGHT):
        t = t.replace(w, "")
    return t


def anyang_addr_dong(text: str):
    """주소에서 안양시 법정동을 뽑는다(‘… (관양동)’ 괄호 또는 ‘호계동 1006-4’ 지번)."""
    t = text or ""
    m = re.search(r"\(([가-힣]{1,6}동)", t)
    if m:
        return ANYANG_DONG_FIX.get(m.group(1), m.group(1))
    for d in sorted(ANYANG_ALL_DONGS, key=len, reverse=True):
        if re.search(re.escape(d) + r"(?=\s|$|[^가-힣])", t):
            return d
    return None


def load_anyang_auc() -> dict:
    """안양도시공사 통합주차포털 주차장 목록 스냅샷 → 주차장 이름별 정보.

    포털 주소에는 법정동이 괄호로 적혀 있어(예: ‘… 관악대로 479-2 (관양동)’) 표준데이터에
    지번주소가 없는 주차장의 동을 확인하는 데 쓴다. 시간 요금은 조례 별표1(급지별 누진)로
    계산하므로 여기서는 일일 최대요금·1일 선불요금·월정기권·구획 구성만 받아 쓴다.
    """
    if not ANYANG_AUC_JSON.exists():
        return {}
    rows = json.loads(ANYANG_AUC_JSON.read_text()).get("parkingList", [])
    out: dict[str, dict] = {}
    for r in rows:
        nm = (r.get("PARKING_NM") or "").strip()
        if not nm:
            continue
        row = {
            "name": nm,
            "gu": (r.get("REGION_DIV_NM") or "").strip() or None,
            "grade": to_int(r.get("GRADE")),
            "addr": (r.get("CELL_ADDR_JIBUN") or "").strip(),
            "spaces": to_int(r.get("CELL_CNT")),
            "lat": float(r["LAT"]) if r.get("LAT") else None,
            "lng": float(r["LNG"]) if r.get("LNG") else None,
            "cap": to_int(r.get("ONEDAY_AMT")),
            "prepaid": to_int(r.get("WDAYS_TICKET_AMT")),
            "prepaid_weekend": to_int(r.get("WEND_TICKET_AMT")),
            "monthly": to_int(r.get("PERIOD_TICKET_AMT")),
            "disabled": to_int(r.get("HNDCAP_CELL_CNT")),
            "elec": to_int(r.get("ELEC_CELL_CNT")),
            "open": (r.get("START_TM") or "").strip(),
            "close": (r.get("END_TM") or "").strip(),
            "tel": (r.get("TEL_NO") or "").strip(),
            "note": (r.get("NOTE") or "").strip(),
        }
        cur = out.get(nm)
        if cur is None:
            out[nm] = row
            continue
        # 같은 이름이 구간(SECTN)·요일별 여러 행으로 오면 빈 칸만 채운다.
        for k, v in row.items():
            if cur.get(k) in (None, "", 0) and v not in (None, "", 0):
                cur[k] = v
    return out


def anyang_auc_candidates(name: str, auc: dict, lat=None, lng=None):
    """표준데이터 한 행에 대응할 만한 포털 주차장 후보들(이름 → 좌표 50m 순).

    이름이 꾸밈말을 뺐을 때 같은 것 → 서로 포함하는 것 → 같은 자리(50m 이내)에 있는 것 순서로
    찾는다. 후보가 여럿이면 값이 일치할 때만 쓰고, 엇갈리면 쓰지 않는다(anyang_auc_pick).
    """
    # 이름 비교는 꾸밈말을 어디까지 뺄지에 따라 세 단계로 한다.
    #   full  : ‘노상/노외’까지 남겨 남부노상·남부노외를 가른다
    #   light : ‘지하·공영·임시’만 더 뺀다
    #   hard  : ‘노상/노외/주민’까지 뺀다(호현마을1 공영주차장 ↔ 호현마을1노외)
    for strip in (ANYANG_KEY_FULL, ANYANG_KEY_LIGHT, ANYANG_KEY_HARD):
        key = anyang_name_key(name, strip)
        if not key:
            continue
        exact = [r for nm, r in auc.items() if anyang_name_key(nm, strip) == key]
        if exact:
            return exact
    for strip in (ANYANG_KEY_FULL, ANYANG_KEY_LIGHT, ANYANG_KEY_HARD):
        key = anyang_name_key(name, strip)
        if not key:
            continue
        cont = [r for nm, r in auc.items()
                if (k2 := anyang_name_key(nm, strip)) and len(k2) >= 2 and (k2 in key or key in k2)]
        if cont:
            return cont
    if name in ANYANG_AUC_ALIAS and ANYANG_AUC_ALIAS[name] in auc:
        return [auc[ANYANG_AUC_ALIAS[name]]]
    if lat is not None and lng is not None:
        near = [r for r in auc.values()
                if r["lat"] is not None and r["lng"] is not None
                and km(lat, lng, r["lat"], r["lng"]) <= 50]
        if near:
            return near
    return []


def anyang_auc_pick(cands, field):
    """후보들이 한 값으로 모이는 항목만 돌려준다(법정동·일일 최대요금 등).

    예: ‘관악노상1’은 포털에 1-2~1-5 네 구간이 있지만 일일 최대요금이 모두 13,000원이라
    그 값을 쓰고, 값이 엇갈리면 그 항목은 비워 둔다.
    """
    vals = {r.get(field) for r in cands if r.get(field) not in (None, "", 0)}
    return vals.pop() if len(vals) == 1 else None


def anyang_dong_of(row, gu: str, auc: dict):
    """안양시 한 행의 법정동과 근거를 정한다(지번 → 이름 → 좌표 → 도로명)."""
    jibun = (row.get("소재지지번주소") or "").strip()
    road = (row.get("소재지도로명주소") or "").strip()
    name = (row.get("주차장명") or "").strip()
    legal = set(ANYANG_DONGS[gu])
    try:
        lat = float(row["위도"]) if (row.get("위도") or "").strip() else None
        lng = float(row["경도"]) if (row.get("경도") or "").strip() else None
    except ValueError:
        lat = lng = None

    raw = dong_from_jibun(jibun)
    dong = ANYANG_DONG_FIX.get(raw, raw) if raw else None
    if dong in legal:
        return dong, "지번주소"

    # 이름으로 포털 주차장을 찾아 그 주소의 법정동을 쓴다(예: ‘안양6동1 노외 주차장’ → 안양동).
    cands = anyang_auc_candidates(name, auc, lat, lng)
    dongs = {anyang_addr_dong(r["addr"]) for r in cands} & legal
    if len(dongs) == 1:
        return dongs.pop(), "포털주소"

    if lat is not None and lng is not None:
        near = {anyang_addr_dong(r["addr"]) for r in auc.values()
                if r["lat"] is not None and r["lng"] is not None
                and km(lat, lng, r["lat"], r["lng"]) <= 80}
        near &= legal
        if len(near) == 1:
            return near.pop(), "포털좌표"

    # 같은 도로가 여러 동에 걸쳐 있어(만안로·양화로·박달우회로·병목안로) 도로명만으로는 정하지 않는다.
    fix = ANYANG_DONG_VERIFIED.get(name)
    if fix and fix[0] in legal:
        return fix[0], fix[1]
    return None, "없음"


def anyang_fee_steps(grade):
    """급지별 누진 할증을 계산기용 계단(steps)으로 만든다.

    steps[i] = {"until": 이 시간(분) 전까지, "unit_min": 10, "unit_fee": 요율}
    1급지 2시간 = 600 + 300×3 + 600×6 = 5,100원(조례 별표1 표와 같다).
    """
    table = ANYANG_FEES.get(grade) or ANYANG_FEES[1]
    bounds = (60, 120, 180, None)
    return [{"until": b, "unit_min": ANYANG_UNIT_MIN, "unit_fee": f}
            for b, f in zip(bounds, table["tiers"])]


def build_anyang():
    """안양시 공영주차장을 표준데이터 + 안양도시공사 포털 스냅샷으로 추출한다.

    성남·용인·화성시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 안양시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 구간 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 노외 카드가 3곳 이상인 법정동만 만든다.
    안양시는 표준데이터에 **추가요금·1일권 칸이 비어 있고 최초 30분 기본요금과 급지만 등록**되어 있다.
    그래서 시간 요금은 조례 별표1의 급지별 누진표(10분 단위, 최초 15분 무료, 일일 최대 25,000원)로
    계산하고, 일일 최대요금·선불 일일주차·월정기권은 포털 목록 값을 쓴다(없으면 상한 25,000원).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == ANYANG_PROVIDER]
    auc = load_anyang_auc()
    lots, excluded = [], []
    card_no = street_no = 0

    for r in rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (ANYANG_BBOX[0] <= lat <= ANYANG_BBOX[1]
                                      and ANYANG_BBOX[2] <= lng <= ANYANG_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        gu = gu_in(addr, ANYANG_DISTRICTS)
        if not gu:
            excluded.append({"name": name, "reason": "구 판정 불가"})
            continue
        dong, dong_src = anyang_dong_of(r, gu, auc)
        cands = anyang_auc_candidates(name, auc, lat, lng)
        cap_hint = anyang_auc_pick(cands, "cap")
        prepaid = anyang_auc_pick(cands, "prepaid")
        prepaid_weekend = anyang_auc_pick(cands, "prepaid_weekend")
        monthly_hint = anyang_auc_pick(cands, "monthly")
        tel_hint = anyang_auc_pick(cands, "tel")
        disabled_hint = anyang_auc_pick(cands, "disabled")
        elec_hint = anyang_auc_pick(cands, "elec")
        auc_name = cands[0]["name"] if len(cands) == 1 else None

        note = (r.get("특기사항") or "").strip()
        fee_raw = (r.get("요금정보") or "").strip()
        base_min = to_int(r.get("주차기본시간"))
        base_fee = to_int(r.get("주차기본요금"))
        grade = to_int(r.get("급지구분"))        # ‘기타’는 None → 1급지 요금표를 쓴다(원스퀘어 임시)
        grade = grade if grade in ANYANG_FEES else 1

        if fee_raw == "무료":
            ftype = "무료"
        elif fee_raw in ("유료", "혼합"):
            ftype = "유료" if (base_min and base_fee is not None) else "미상"
        else:
            ftype = "미상"

        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)
        if ftype == "무료":
            free_days = {"sat": True, "sun": True}

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"ay-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"ay-{card_no:03d}"

        table = ANYANG_FEES[grade]
        steps = anyang_fee_steps(grade) if ftype == "유료" else None
        cap = None
        if ftype == "유료":
            cap = cap_hint or ANYANG_DAY_CAP

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip() or (tel_hint or ""),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": {
                "type": ftype,
                "raw_type": fee_raw,
                "mixed": fee_raw == "혼합",
                "grade": grade,
                "base_min": base_min if ftype == "유료" else base_min,
                "base_fee": base_fee,
                "unit_min": ANYANG_UNIT_MIN if ftype == "유료" else None,
                "unit_fee": table["tiers"][0] if ftype == "유료" else None,
                "steps": steps,
                "free_min": ANYANG_FREE_MIN if ftype == "유료" else 0,
                "cap_fee": cap,
                "cap_src": ("포털 일일최대요금" if (cap_hint and ftype == "유료") else "조례 상한") if cap else None,
                "daily_hours": None, "daily_fee": None,
                "prepaid_day": prepaid or None,
                "prepaid_weekend": prepaid_weekend or None,
                "monthly": monthly_hint or to_int(r.get("월정기권요금")),
                "pay": (r.get("결제방법") or "").strip(),
                "basis": ("조례 별표1 급지별 누진(최초 15분 무료 · 일일 최대 25,000원)"
                          if ftype == "유료" else None),
            },
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": ({"disabled": disabled_hint, "elec": elec_hint}
                            if (disabled_hint or elec_hint) else None),
            "auc_name": auc_name,
            "realtime": None,
            "udc_id": None,
            "price_key": base_fee if ftype == "유료" else None,
            "city": "안양시",
            "city_slug": "anyang",
        })

    order = {g: i for i, (g, _) in enumerate(ANYANG_DISTRICTS)}
    lots.sort(key=lambda l: (order[l["gu"]], l["list_mode"] != "card", l["name"]))

    quality = check_quality_anyang(rows_all, rows, lots, excluded, auc)
    fee_rows = [{"grade": g, "base_fee": t["base_fee"], "tiers": list(t["tiers"]),
                 "note": "노외·노상 공통" if g <= 3 else "노외주차장만"}
                for g, t in sorted(ANYANG_FEES.items())]
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(ANYANG_AUC_JSON).strftime("%Y-%m-%d %H:%M")
                            if ANYANG_AUC_JSON.exists() else None,
            "region": {"province": "경기도", "city": "안양시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-09-15", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": "안양시가 등록한 행만(제공기관명 '경기도 안양시') 추출. 요금은 최초 30분 기본요금·급지만 등록되어 있다.",
                },
                {
                    "id": "auc", "name": "안양도시공사 통합주차포털 주차장 목록",
                    "org": "안양도시공사",
                    "url": "https://parking.auc.or.kr/parkinglist",
                    "file": ANYANG_AUC_JSON.name,
                    "sha256": sha256(ANYANG_AUC_JSON) if ANYANG_AUC_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(auc),
                    "fetched_at": _snapshot_time(ANYANG_AUC_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if ANYANG_AUC_JSON.exists() else None,
                    "note": "주차장별 법정동 주소·일일 최대요금·1일 선불요금·월정기권·장애인/전기차 구획 확인용.",
                },
                {
                    "id": "ordinance", "name": "안양시 주차장 설치 및 관리 조례 (제10조 별표1·별표2)",
                    "org": "안양시",
                    "url": "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1908307",
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "2024-02-20 시행", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": "급지별 누진 주차요금표(별표1)·요금 감면(별표2) 근거. 안양도시공사 요금 안내로 교차 확인.",
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in ANYANG_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "unit_min": ANYANG_UNIT_MIN,
            "free_min": ANYANG_FREE_MIN,
            "cap_fee": ANYANG_DAY_CAP,
            "rows": fee_rows,
            "basis": "「안양시 주차장 설치 및 관리 조례」 별표1 · 안양도시공사 통합주차포털 안내(2026-11-17 확인)",
        },
    }
    payload.update(CITY_META["안양시"] | {
        "city": "안양시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": ANYANG_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "anyang_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_anyang(std_all, rows, lots, excluded, auc):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_gu = Counter(l["gu"] for l in card)
    by_dong = Counter((l["gu"], l["dong"]) for l in card if l["dong"])
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["base_fee"] for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    # 표준데이터 기본요금이 조례 급지별 표와 다른 행(자료 정합성 점검용)
    fee_mismatch = [f"{l['name']}({l['fee']['grade']}급지 {l['fee']['base_fee']}원)"
                    for l in lots if l["fee"]["type"] == "유료"
                    and l["fee"]["base_fee"] != ANYANG_FEES[l["fee"]["grade"]]["base_fee"]]
    # 포털 일일 최대요금을 확인하지 못해 조례 상한(25,000원)을 쓴 주차장
    cap_default = [l["name"] for l in lots if l["fee"]["type"] == "유료"
                   and l["fee"].get("cap_src") == "조례 상한"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_안양시행수": len(rows),
        "포털_주차장수": len(auc),
        "포털_매칭": len([l for l in lots if l.get("auc_name")]),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(by_gu),
        "동별": {f"{g} {d}": c for (g, d), c in sorted(by_dong.items(),
                                                   key=lambda kv: (str(kv[0][0]), str(kv[0][1])))},
        "동수": len({(l["gu"], l["dong"]) for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots if l["fee"]["type"] == "유료")),
        "기본요금_표와불일치": fee_mismatch,
        "일일상한_조례값사용": cap_default,
        "일일상한_포털값": len([l for l in lots if l["fee"].get("cap_src") == "포털 일일최대요금"]),
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 평택시 (T-03 Phase 5)
PYEONGTAEK_PROVIDER = "경기도 평택시"
PYEONGTAEK_BBOX = (36.85, 37.15, 126.75, 127.20)   # 평택시 대략 경계(좌표 점검용)
# 평택도시공사 공영주차장 포털 목록 스냅샷 — POST /parking/searchParkingList.json
# (searchParking=, parkingDong= 빈 값으로 전체 조회). 급지(GRADE)와 주차장별 최신 요금이 들어 있다.
PYEONGTAEK_PORTAL_JSON = RAW / "parking.puc.or.kr_searchParkingList_20261117.json"
# 평택시는 자치구가 없다(3읍 5면 + 동). 다른 도시의 '구' 자리에 시 이름 하나만 두고,
# 시 페이지가 계산기·목록 페이지를 겸하며 그 아래에 읍·면·동 페이지를 만든다.
PYEONGTAEK_DISTRICTS = [("평택시", "pyeongtaek")]
PYEONGTAEK_EUP_MYEON = ("안중읍", "팽성읍", "포승읍", "청북읍", "진위면", "서탄면",
                        "고덕면", "오성면", "현덕면")

# 평택시 공영주차장 요금 — 「평택시 주차장 설치 및 관리 조례」 별표1
# (2026-11-16 시행 개정: 1~3급지 차등 요금제. 평택시 보도자료 2026-11-12·평택도시공사
#  포털 주차장별 요금 안내 2026-11-17 확인).
#   · 1급지 : 전통시장·상점가 인근 — 당일 최초 90분 무료, 이후 10분당 400원
#   · 2급지 : 상업·준주거지역      — 최초 30분 800원, 이후 10분당 300원
#   · 3급지 : 그 밖의 지역        — 최초 30분 600원, 이후 10분당 200원
#   · 1일 최대요금 10,000원(모든 급지), 월 정기권은 주차장별 70,000~80,000원
# 노상 구간은 같은 급지라도 포털에 등록된 기본시간·기본요금이 다를 수 있어(예: 서정전통
# 120분 800원) 주차장별 등록값을 그대로 쓴다.
PYEONGTAEK_FEES = {
    1: {"base_min": 90, "base_fee": 0, "free_min": 90, "unit_min": 10, "unit_fee": 400},
    2: {"base_min": 30, "base_fee": 800, "free_min": 0, "unit_min": 10, "unit_fee": 300},
    3: {"base_min": 30, "base_fee": 600, "free_min": 0, "unit_min": 10, "unit_fee": 200},
}
PYEONGTAEK_UNIT_MIN = 10
PYEONGTAEK_DAY_CAP = 10_000          # 1일 최대요금(모든 급지)

# 평택시 공영주차장 요금 감면 — 「평택시 주차장 설치 및 관리 조례」 별표2와
# 평택도시공사 ‘즉시감면 안내’(2026-11-17 확인), 표준데이터 특기사항(평택시 등록값)으로 교차 확인.
#   · 4시간 면제 후 50% : 국가유공자·고엽제후유증환자·참전유공자·국가보훈대상자·성실납세자·
#                        우수자원봉사증 소지자
#   · 2시간 면제 후 50% : 장애인자동차·전기자동차
#   · 50%              : 장기기증자·저공해자동차·경형자동차·병역명문가·다자녀가정(두 자녀 이상,
#                        2026-11-16부터 경기도 거주 가정까지)
#   · 20%              : 승용차부제·함께타기 표지부착 차량
#   · 감면이 겹치면 비율이 높은 하나만 적용
PYEONGTAEK_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형(1,000cc 미만)·저공해·장기기증·병역명문가·다자녀(두 자녀 이상)"},
    {"label": "승용차부제·함께타기 20%", "rate": 0.2, "exempt_min": 0,
     "note": "승용차부제 및 함께타기 표지부착 차량"},
    {"label": "장애인·전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "장애인자동차·전기자동차, 2시간까지 면제"},
    {"label": "국가유공자·성실납세자 4시간 면제 후 50%", "rate": 0.5, "exempt_min": 240,
     "note": "국가유공자·고엽제·참전유공자·국가보훈대상자·성실납세자·우수자원봉사자"},
]
# 포털 이름이 표준데이터와 달라 이름으로 찾지 못하는 주차장(좌표 60m 밖).
PYEONGTAEK_PORTAL_ALIAS = {
    "신장쇼핑제2공영주차장": "신장쇼핑몰 제2",
    # 표준데이터 ‘안정리 39-12’(60면) ↔ 포털 ‘안정리쇼핑몰’(58면, 안정순환로 107). 40m 옆의
    # ‘안정커뮤니티광장주차장’(388면)은 다른 주차장이라 이름으로 짝을 정한다.
    "팽성안정리쇼핑몰 공영주차장": "안정리쇼핑몰",
}
PY_KEY_STRIP = ("주차장", "공영", "노외", "노상", "지하", "임시")


def pyeongtaek_name_key(s: str, strip=PY_KEY_STRIP) -> str:
    """주차장 이름 비교용 키 — 공백·괄호와 꾸밈말(공영/주차장/노외/노상/지하/임시)을 뺀다.

    예: ‘신장쇼핑제3공영주차장’ ↔ ‘신장쇼핑몰 제3’, ‘서정제1공영’ ↔ ‘서정-제1’
    """
    t = re.sub(r"[\s()\[\]·,.ㆍ\-]", "", s or "")
    for w in strip:
        t = t.replace(w, "")
    return t


def pyeongtaek_unit_of(text: str):
    """주소에서 평택시 읍·면·동을 뽑는다(읍·면 → 동 순, ‘… (평택동)’ 괄호도 읽는다)."""
    t = text or ""
    for u in PYEONGTAEK_EUP_MYEON:
        if re.search(re.escape(u) + r"(\s|$|[^가-힣])", t):
            return u
    m = re.search(r"\(([가-힣]{1,6}(?:동|읍|면))", t)
    if m:
        return m.group(1)
    return dong_from_jibun(t)


def load_pyeongtaek_portal() -> dict:
    """평택도시공사 포털 주차장 목록 스냅샷 → 주차장 이름별 정보.

    급지(GRADE)·기본시간·기본요금·간격요금·1일 최대요금·월정기권과 법정동이 적힌 주소,
    좌표, 24시간 운영 여부를 담는다. 2026-11-16 조례 개정 뒤 요금이 표준데이터보다 최신이다.
    """
    if not PYEONGTAEK_PORTAL_JSON.exists():
        return {}
    rows = json.loads(PYEONGTAEK_PORTAL_JSON.read_text()).get("parkingList", [])
    out: dict[str, dict] = {}
    for r in rows:
        nm = (r.get("PARKING_NM") or "").strip()
        if not nm:
            continue
        out[nm] = {
            "name": nm,
            "grade": to_int(r.get("GRADE")),
            "ptype": (r.get("PARKING_DIV_NM") or "").strip(),
            "addr": (r.get("CELL_ADDR_JIBUN") or "").strip(),
            "spaces": to_int(r.get("CELL_CNT")),
            "base_min": to_int(r.get("DFLT_TM")),
            "base_fee": to_int(r.get("DFLT_AMT")),
            "unit_min": to_int(r.get("INTVL_TM")),
            "unit_fee": to_int(r.get("INTVL_AMT")),
            "cap": to_int(r.get("DAY_PARKING_AMT")),
            "monthly": to_int(r.get("PERIOD_TICKET_AMT")),
            "anyhour": (r.get("ANYHOUR_RUN_YN") or "").strip() == "24시간운영함",
            "tel": (r.get("TEL_NO") or "").strip(),
            "lat": float(r["LAT"]) if r.get("LAT") else None,
            "lng": float(r["LNG"]) if r.get("LNG") else None,
        }
    return out


def pyeongtaek_portal_match(name: str, portal: dict, lat=None, lng=None):
    """표준데이터 한 행에 대응하는 포털 주차장을 정한다.

    이름이 꾸밈말을 뺐을 때 같은 것 → 이름이 서로 포함되고 120m 안에 있는 것 →
    같은 자리(40m 이내)에 있는 것 → 별칭표 순으로 찾는다. 통복장터·통복공영처럼 이름이
    비슷한 주차장이 한 동네에 몰려 있어, 이름만으로 정하지 않고 좌표를 함께 본다.
    """
    if not portal:
        return None
    key = pyeongtaek_name_key(name)
    exact = [r for nm, r in portal.items() if pyeongtaek_name_key(nm) == key]
    if exact:
        if len(exact) == 1 or lat is None:
            return exact[0]
        return min(exact, key=lambda r: km(lat, lng, r["lat"], r["lng"])
                   if r["lat"] is not None else 9e9)
    if lat is not None and lng is not None:
        cont = [r for nm, r in portal.items()
                if (k2 := pyeongtaek_name_key(nm)) and len(k2) >= 2 and (k2 in key or key in k2)
                and r["lat"] is not None and km(lat, lng, r["lat"], r["lng"]) <= 120]
        if cont:
            return min(cont, key=lambda r: km(lat, lng, r["lat"], r["lng"]))
        near = [r for r in portal.values()
                if r["lat"] is not None and km(lat, lng, r["lat"], r["lng"]) <= 40]
        if near:
            return min(near, key=lambda r: km(lat, lng, r["lat"], r["lng"]))
    alias = PYEONGTAEK_PORTAL_ALIAS.get(name)
    if alias and alias in portal:
        return portal[alias]
    return None


def build_pyeongtaek():
    """평택시 공영주차장을 표준데이터 + 평택도시공사 포털 스냅샷으로 추출한다.

    성남·용인·화성·안양시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 평택시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 구간 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 노외 카드가 3곳 이상인 읍·면·동만 만든다.
    평택시는 2026-11-16부터 1~3급지 차등 요금제를 시행해, 표준데이터(기준일 2026-04-17)의
    일괄 30분 800원·10분 300원이 이미 지난 요금이다. 그래서 주차장별 급지·기본시간·요금은
    평택도시공사 포털의 최신 등록값을 쓰고, 포털에서 찾지 못한 주차장만 표준데이터 값을 쓴다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == PYEONGTAEK_PROVIDER]
    portal = load_pyeongtaek_portal()
    lots, excluded = [], []
    card_no = street_no = 0

    for r in rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (PYEONGTAEK_BBOX[0] <= lat <= PYEONGTAEK_BBOX[1]
                                      and PYEONGTAEK_BBOX[2] <= lng <= PYEONGTAEK_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        hit = pyeongtaek_portal_match(name, portal, lat, lng)
        dong = pyeongtaek_unit_of(jibun)
        dong_src = "지번주소"
        if not dong:
            dong = pyeongtaek_unit_of(road)
            dong_src = "도로명주소"
        if not dong and hit:
            dong = pyeongtaek_unit_of(hit["addr"])
            dong_src = "포털주소"
        if not dong and lat is not None:
            near = [(pyeongtaek_unit_of(x["addr"]), x) for x in portal.values()
                    if x["lat"] is not None and km(lat, lng, x["lat"], x["lng"]) <= 120]
            near = [d for d in (u for u, _ in near) if d]
            if len(set(near)) == 1:
                dong, dong_src = near[0], "포털좌표"
        if not dong:
            dong_src = "없음"

        note = (r.get("특기사항") or "").strip()
        fee_raw = (r.get("요금정보") or "").strip()
        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"pt-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"pt-{card_no:03d}"

        fee = {
            "type": "무료" if fee_raw == "무료" else ("유료" if fee_raw in ("유료", "혼합") else "미상"),
            "raw_type": fee_raw,
            "mixed": fee_raw == "혼합",
            "grade": None, "base_min": None, "base_fee": None,
            "unit_min": None, "unit_fee": None, "steps": None,
            "free_min": 0, "cap_fee": None, "cap_src": None,
            "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": to_int(r.get("월정기권요금")),
            "pay": (r.get("결제방법") or "").strip(),
            "basis": None,
        }
        if fee["type"] == "유료":
            free_days = {"sat": False, "sun": False}
            if hit and hit["base_min"] and hit["base_fee"] is not None:
                fee.update({
                    "grade": hit["grade"],
                    "base_min": hit["base_min"],
                    "base_fee": hit["base_fee"],
                    "unit_min": hit["unit_min"] or PYEONGTAEK_UNIT_MIN,
                    "unit_fee": hit["unit_fee"],
                    "free_min": hit["base_min"] if not hit["base_fee"] else 0,
                    "cap_fee": hit["cap"] or PYEONGTAEK_DAY_CAP,
                    "cap_src": "포털 일일최대요금" if hit["cap"] else "조례 일일 최대",
                    "monthly": hit["monthly"] or fee["monthly"],
                    "basis": ("「평택시 주차장 설치 및 관리 조례」 별표1 급지별 요금"
                              + (f"({hit['grade']}급지)" if hit["grade"] else "")
                              + " · 평택도시공사 포털 요금 안내(2026-11-17 확인)"),
                })
            else:
                base_min = to_int(r.get("주차기본시간"))
                base_fee = to_int(r.get("주차기본요금"))
                unit_min = to_int(r.get("추가단위시간"))
                unit_fee = to_int(r.get("추가단위요금"))
                if base_min and base_fee is not None:
                    fee.update({
                        "base_min": base_min, "base_fee": base_fee,
                        "unit_min": unit_min or PYEONGTAEK_UNIT_MIN,
                        "unit_fee": unit_fee,
                        "cap_fee": PYEONGTAEK_DAY_CAP,
                        "cap_src": "조례 일일 최대",
                        "basis": "표준데이터 등록요금(급지 미확인 · 포털 미등록)",
                    })
                else:
                    fee["type"] = "미상"
        if fee["type"] == "무료":
            free_days = {"sat": True, "sun": True}

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "평택시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip() or (hit["tel"] if hit else ""),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": hit["name"] if hit else None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["base_fee"] if fee["base_fee"] else (fee["unit_fee"] or None),
            "city": "평택시",
            "city_slug": "pyeongtaek",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))

    quality = check_quality_pyeongtaek(rows_all, rows, lots, excluded, portal)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(PYEONGTAEK_PORTAL_JSON).strftime("%Y-%m-%d %H:%M")
                            if PYEONGTAEK_PORTAL_JSON.exists() else None,
            "region": {"province": "경기도", "city": "평택시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-17", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("평택시가 등록한 행만(제공기관명 '경기도 평택시') 추출. 요금은 급지 없이 "
                             "30분 800원·10분 300원으로 일괄 등록되어 있다."),
                },
                {
                    "id": "puc", "name": "평택도시공사 공영주차장 포털 주차장 목록",
                    "org": "평택도시공사",
                    "url": "https://parking.puc.or.kr/parking/list.do",
                    "file": PYEONGTAEK_PORTAL_JSON.name,
                    "sha256": sha256(PYEONGTAEK_PORTAL_JSON) if PYEONGTAEK_PORTAL_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(portal),
                    "fetched_at": _snapshot_time(PYEONGTAEK_PORTAL_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if PYEONGTAEK_PORTAL_JSON.exists() else None,
                    "note": ("주차장별 급지(1~3급지)·기본시간·기본요금·간격요금·1일 최대요금·월정기권과 "
                             "법정동 주소 확인용. 2026-11-16 조례 개정 요금이 반영되어 있다."),
                },
                {
                    "id": "ordinance", "name": "평택시 주차장 설치 및 관리 조례 (별표1·별표2)",
                    "org": "평택시",
                    "url": "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2076351",
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "2026-11-16 시행(급지별 차등 요금제)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("1~3급지 주차요금표(별표1)·요금 감면(별표2) 근거. 2026-11-12 시 보도자료와 "
                             "평택도시공사 포털 요금 안내로 교차 확인."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in PYEONGTAEK_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "grade_flat",
            "unit_min": PYEONGTAEK_UNIT_MIN,
            "cap_fee": PYEONGTAEK_DAY_CAP,
            "rows": [
                {"grade": g, "base_min": t["base_min"], "base_fee": t["base_fee"],
                 "free_min": t["free_min"], "unit_fee": t["unit_fee"],
                 "note": note}
                for g, t, note in (
                    (1, PYEONGTAEK_FEES[1], "전통시장·상점가 인근 — 90분 무료"),
                    (2, PYEONGTAEK_FEES[2], "상업·준주거지역"),
                    (3, PYEONGTAEK_FEES[3], "그 밖의 지역"),
                )
            ],
            "basis": ("「평택시 주차장 설치 및 관리 조례」 별표1(2026-11-16 시행) · "
                      "평택도시공사 포털 요금 안내(2026-11-17 확인)"),
        },
    }
    payload.update(CITY_META["평택시"] | {
        "city": "평택시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": PYEONGTAEK_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "pyeongtaek_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_pyeongtaek(std_all, rows, lots, excluded, portal):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["base_fee"] for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_평택시행수": len(rows),
        "포털_주차장수": len(portal),
        "포털_매칭": len([l for l in lots if l.get("portal_name")]),
        "포털_미매칭_유료": [l["name"] for l in lots
                            if l["fee"]["type"] == "유료" and not l.get("portal_name")],
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": {"평택시": len(card)},
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots if l["fee"]["type"] == "유료")),
        "일일상한_포털값": len([l for l in lots if l["fee"].get("cap_src") == "포털 일일최대요금"]),
        "일일상한_조례값": len([l for l in lots if l["fee"].get("cap_src") == "조례 일일 최대"]),
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 부천시 (T-03 Phase 6)
BUCHEON_PROVIDER = "경기도 부천시"
BUCHEON_BBOX = (37.44, 37.58, 126.70, 126.88)   # 부천시 대략 경계(좌표 점검용)
# 부천시는 2016-07 일반구를 폐지했다가 2024-01-01 원미구·소사구·오정구 3개 구를 다시 설치했다
# (법정동 24개는 그대로, 2024-01-01 법정동코드 부여 내역 41192/41194/41196).
BUCHEON_DISTRICTS = [("원미구", "bucheon-wonmi"), ("소사구", "bucheon-sosa"),
                     ("오정구", "bucheon-ojeong")]
BUCHEON_DONGS = {
    "원미구": ("원미동", "심곡동", "춘의동", "도당동", "약대동", "소사동", "역곡동", "중동", "상동"),
    "소사구": ("소사본동", "심곡본동", "범박동", "괴안동", "송내동", "옥길동", "계수동"),
    "오정구": ("오정동", "여월동", "작동", "원종동", "고강동", "대장동", "삼정동", "내동"),
}
BUCHEON_ALL_DONGS = tuple(d for v in BUCHEON_DONGS.values() for d in v)
# 부천주차포털(parking.bcits.go.kr) 공영주차장 목록 스냅샷 — POST /publicparking/ajax_select_publicparking_list.do
# (검색조건 없이 전체 조회). 급지·기본요금·10분당·1일 최대·정기권·장애인 구획이 주차장별로 들어 있다.
BUCHEON_PORTAL_JSON = RAW / "parking.bcits.go.kr_searchParkingList_20261117.json"
# 부천도시공사 ‘공영주차장 일반현황’(102개소) 엑셀 — 급지·주차면·위치(지번)·구조·운영시간·운영방식·
# 기본요금·10분당·1일 요금·정기권(주간/야간/전일). 포털에 없는 주차장의 요금·지번을 보강한다.
BUCHEON_STATUS_XLSX = RAW / "best.or.kr_parkingStatus_20261117.xlsx"

# 부천시 공영주차장 요금 — 「부천시 주차장 설치 및 관리 조례」 별표1 ‘공영주차장 주차요금 부과 기준’
# (현행 조례: 시행 2026-05-18, 경기도부천시조례 제4326호). 2026-11-17 부천도시공사 요금 안내와
# 부천주차포털 주차장별 등록요금(같은 날 08:10 갱신분)으로 교차 확인했다.
#   · 1회 주차요금 = 최초 30분 기본요금 + 30분 초과분 10분 단위 가산(10분 미만은 10분으로 봄)
#   · 노상·노외가 같은 1회 요금을 쓰고, 급지별로 1일 주차권·월정기 주차권이 다르다
#   · 일요일·공휴일은 무료 운영이 원칙이지만 시장이 필요하다고 인정하면 유료로 운영할 수 있다(비고 1 라)
#   · 부설(공공시설 부설주차장)은 「부천시 공공시설 부설주차장 운영조례」에 따라 최초 30분 400원·
#     10분당 200원, 1일 4,000~6,000원을 쓴다(도시공사 안내).
BUCHEON_FEES = {
    1: {"base_min": 30, "base_fee": 900, "unit_fee": 400, "day": 9_500,
        "street_monthly": 80_000, "off_day": 70_000, "off_night": 50_000, "off_all": 100_000},
    2: {"base_min": 30, "base_fee": 700, "unit_fee": 300, "day": 7_000,
        "street_monthly": 60_000, "off_day": 50_000, "off_night": 40_000, "off_all": 70_000},
    3: {"base_min": 30, "base_fee": 300, "unit_fee": 200, "day": 4_000,
        "street_monthly": 50_000, "off_day": 40_000, "off_night": 30_000, "off_all": 50_000},
}
BUCHEON_UNIT_MIN = 10
BUCHEON_FACILITY_FEE = {"base_min": 30, "base_fee": 400, "unit_fee": 200, "day": 6_000}

# 부천시 공영주차장 요금 감면 — 「부천시 주차장 설치 및 관리 조례」 별표1 비고 3과
# 부천도시공사 ‘주차요금 감면제도’ 안내(2026-11-17 확인).
#   · 면제            : 장애인(24시간 초과 시 1일 50%·월정기 90% 감경), 국가유공자등(같은 조건),
#                       모범·유공납세증 부착차량(1년), 기부자(1년), 시 인정 행사, 자율방범대 차량(동별 1대)
#   · 80% 감경        : 전통시장·상점가 상인·상인회가 월정기 주차권을 신청한 경우
#   · 50% 감경        : 경형(1,000cc 미만)·저공해자동차, 주거·녹지지역 노외주차장 인접 주민,
#                       65세 이상 운전자(최초 2시간 전액 면제), 명예시민(최초 2시간 전액 면제),
#                       장기·인체조직 기증자(최초 2시간 전액 면제), 다자녀(두 자녀 이상, 세 자녀 이상은 전액 면제),
#                       환경친화적 자동차 충전 차량(최초 1시간 전액 면제), 병역명문가, 우수자원봉사자,
#                       승용차공동이용자동차(50% 범위), 임산부
#   · 감면이 겹치면 비율이 높은 하나만 적용
BUCHEON_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·임산부·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형(1,000cc 미만)·저공해·임산부·다자녀(세 자녀 이상은 전액 면제)·병역명문가·자원봉사자"},
    {"label": "65세·명예시민·장기기증 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "65세 이상 운전자·명예시민·장기 및 인체조직 기증자, 최초 2시간 면제"},
    {"label": "장애인·국가유공자 면제", "rate": 1.0, "exempt_min": 0,
     "note": "장애인등록증·국가유공자 증서 제시(24시간 초과분은 50%)"},
    {"label": "모범·유공납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "표지(스티커) 부착 차량, 발급일부터 1년"},
]
# 이름 비교에서 빼는 꾸밈말 — ‘제1’과 ‘1’을 같게 보기 위해 ‘제’도 뺀다
# (예: 심곡시민의강1 ↔ 심곡 시민의 강 제1공영주차장).
BUCHEON_KEY_STRIP = ("주차장", "공영", "노외", "노상", "지하", "임시", "제")
# 포털 이름이 표준데이터와 달라 이름만으로 짝을 찾지 못하는 주차장(좌표 대조로 확인).
BUCHEON_PORTAL_ALIAS = {
    "부천역 남부": "부천남부역",              # 심곡본동 550-10 ↔ 자유로 66
    "소원지하": "소원",                       # 소사동 32 ↔ 소사로300번길 41
    "수주": "수주 공영(운산)",                 # 고강동 250-20 ↔ 고강로161번길 5
    "중동사랑시장": "중동시장",                # 중동 737 ↔ 중동로161번길 37
    "원미지하(별빛공원)": "별빛공원(구 원미지하)",   # 원미동 127-5 ↔ 부천로90번길 51
    "삼정1호": "삼정동 제1호",
    "삼정2호": "삼정동 제2호",
    "삼정3호": "삼정동 제3호",
    "송내IC 화물": "송내IC북측대형",           # 상동 21(북측) 화물 전용
    "무지개고가": "무지개고가1",               # 64면 = 무지개고가1(38) + 무지개고가2(26), 요금 같음
    "고강차고지진입로": "고강차고지진입로(화물)",   # 고강동 1-12 화물 전용 노상 구간
}
# 포털·현황표에 없는 주차장은 아래 값(현황표 기준)을 쓴다 — 도당공원2는 포털에 형제 주차장만 있다.
BUCHEON_PORTAL_SKIP = {"도당공원2", "부천아트센터"}

# 표준데이터에 지번주소가 없어 동을 확인하지 못한 주차장 — 도로명주소의 지번을 2026-11-17 확인했다.
# (도로명주소 안내·부천도시공사 시설 안내·현황표 지번 대조)
BUCHEON_DONG_VERIFIED = {
    "부천체육관": ("중동", "도로명주소 확인"),        # 석천로 293 = 중동 1024
    "종합운동장": ("춘의동", "도로명주소 확인"),       # 소사로 482 = 춘의동(부천도시공사 주소)
    "도당어울마당": ("도당동", "도로명주소 확인"),      # 부천로 360 = 도당동 32-4
    "송내국민체육센터": ("송내동", "도로명주소 확인"),   # 경인로120번길 45 = 송내동 457
    "버들공원": ("옥길동", "도로명주소 확인"),        # 옥길로56번길 140 = 옥길동 752-1
    "구소사경찰서": ("송내동", "도로명주소 확인"),      # 경인로160번길 70 = 송내동 601
    "구소사구청": ("송내동", "도로명주소 확인"),       # 경인로160번길 52 = 송내동 594-5
    "심곡시민의강1": ("심곡동", "도로명주소 확인"),     # 부흥로 399 = 심곡동 121-5
    "심곡시민의강2": ("원미동", "도로명주소 확인"),     # 부흥로 441 = 원미동 204-22
    "심곡본동어울림복합센터": ("심곡본동", "시설명·주소 확인"),   # 경인로224번길 54
    "상동시장": ("상동", "도로명주소 확인"),          # 석천로38번길 53 = 상동 244-5
    "다산(중동역)": ("송내동", "도로명주소 확인"),      # 경인로101번길 45 = 송내동 371-2
}


def bucheon_name_key(s: str) -> str:
    """주차장 이름 비교용 키 — 공백·괄호와 꾸밈말(공영/주차장/노외/노상/지하/임시/제)을 뺀다.

    예: ‘심곡 시민의 강 제1공영주차장’ ↔ ‘심곡시민의강1’, ‘오정동 제1호’ ↔ ‘오정동1호’
    """
    t = re.sub(r"[\s()\[\]·,.ㆍ\-]", "", s or "")
    for w in BUCHEON_KEY_STRIP:
        t = t.replace(w, "")
    return t


def bucheon_dong_of(text: str, gu: str = None):
    """주소에서 부천시 법정동을 뽑는다(법정동 목록 대조, 행정동 접미사 번호는 떼지 않는다)."""
    t = text or ""
    legal = set(BUCHEON_DONGS.get(gu, BUCHEON_ALL_DONGS))
    m = re.search(r"([가-힣]{1,6}동)\s*\d", t)
    if m and m.group(1) in legal:
        return m.group(1)
    for d in sorted(legal, key=len, reverse=True):
        if re.search(re.escape(d) + r"(?=\s|$|[^가-힣])", t):
            return d
    return None


def load_bucheon_portal() -> dict:
    """부천주차포털 공영주차장 목록 스냅샷 → 주차장 이름별 정보.

    급지(GRADE)·기본시간·기본요금·간격요금·1일 최대요금·정기권·장애인 구획·운영시간이 들어 있다.
    같은 이름이 여러 행(구획·요금제)으로 오면 빈 칸만 채워 합친다.
    """
    if not BUCHEON_PORTAL_JSON.exists():
        return {}
    rows = json.loads(BUCHEON_PORTAL_JSON.read_text()).get("result", [])
    out: dict[str, dict] = {}
    for r in rows:
        nm = (r.get("PARKING_NM") or "").strip()
        if not nm:
            continue
        row = {
            "name": nm,
            "div": (r.get("PARKING_DIV_CD") or "").strip(),
            "grade": to_int(r.get("GRADE")),
            "addr": (r.get("CELL_ADDR_JIBUN") or "").strip(),
            "spaces": to_int(r.get("CELL_CNT")),
            "disabled": to_int(r.get("HNDCAP_CELL_CNT")),
            "base_min": to_int(r.get("DFLT_TM")),
            "base_fee": to_int(r.get("DFLT_AMT")),
            "unit_min": to_int(r.get("INTVL_TM")),
            "unit_fee": to_int(r.get("INTVL_AMT")),
            "cap": to_int(r.get("DAY_PARKING_AMT")),
            "monthly": to_int(r.get("PERIOD_TICKET_AMT")),
            "monthly_day": to_int(r.get("PERIOD_DAYTM_AMT")),
            "monthly_night": to_int(r.get("PERIOD_NIGHT_AMT")),
            "anyhour": (r.get("ANYHOUR_RUN_YN") or "").strip() == "24시간운영함",
            "tel": (r.get("TEL_NO") or "").strip(),
            "lat": float(r["LAT"]) if r.get("LAT") else None,
            "lng": float(r["LNG"]) if r.get("LNG") else None,
        }
        cur = out.get(nm)
        if cur is None:
            out[nm] = row
            continue
        for k, v in row.items():
            if cur.get(k) in (None, "", 0) and v not in (None, "", 0):
                cur[k] = v
    return out


def _xlsx_rows(path: Path):
    """엑셀(.xlsx) 한 시트를 ‘행 번호 → {열 문자: 값}’으로 읽는다(openpyxl 없이 zipfile 파싱)."""
    import zipfile
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        sx = z.read("xl/sharedStrings.xml").decode("utf-8")
        ss = ["".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))
              for si in re.findall(r"<si>(.*?)</si>", sx, re.S)]
    x = z.read("xl/worksheets/sheet1.xml").decode("utf-8")
    out = []
    for rn, body in re.findall(r'<row[^>]*r="(\d+)"[^>]*>(.*?)</row>', x, re.S):
        cells = {}
        for col, attrs, c in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', body, re.S):
            v = re.search(r"<v>(.*?)</v>", c, re.S)
            if not v:
                continue
            val = v.group(1)
            if 't="s"' in attrs:
                val = ss[int(val)]
            cells[col] = re.sub(r"\s+", " ", val).strip()
        out.append((int(rn), cells))
    return out


def load_bucheon_status() -> dict:
    """부천도시공사 공영주차장 일반현황 엑셀 → 주차장 이름별 정보(급지·면수·위치·요금·정기권).

    포털에 없는 주차장의 요금·지번 보강과, 포털과 현황표가 어긋날 때의 교차 확인에 쓴다.
    """
    if not BUCHEON_STATUS_XLSX.exists():
        return {}
    out: dict[str, dict] = {}
    for rn, c in _xlsx_rows(BUCHEON_STATUS_XLSX):
        name = c.get("A", "")
        if rn < 8 or not name or name.startswith("("):
            continue
        def num(v):
            v = (v or "").replace(",", "")
            m = re.match(r"^\d+$", v)
            return int(v) if m else None
        out[bucheon_name_key(name)] = {
            "name": name,
            "grade": num(c.get("B")),
            "spaces": num(c.get("C")),
            "addr": c.get("D", ""),
            "structure": c.get("E", ""),
            "hours": c.get("F", ""),
            "way": c.get("G", ""),
            "base_fee": num(c.get("I")),
            "unit_fee": num(c.get("J")),
            "day": num(c.get("K")),
            "monthly_day": num(c.get("N")),
            "monthly_night": num(c.get("O")),
            "monthly_all": num(c.get("P")),
        }
    return out


def bucheon_candidates(name: str, portal: dict, lat=None, lng=None):
    """표준데이터 한 행에 대응할 만한 포털 주차장 후보들.

    이름이 꾸밈말을 뺐을 때 같은 것 → 별칭표 → 서로 포함하는 것(좌표 150m 안) 순서로 찾는다.
    ‘부천역 남부’와 ‘부천역 남부 제2호’, ‘구소사경찰서’와 ‘구소사경찰서별관’처럼 이름이 겹치는
    주차장이 있어, 정확히 같은 이름을 먼저 찾고 포함 관계는 좌표를 함께 본다.
    """
    if not portal:
        return []
    key = bucheon_name_key(name)
    exact = [r for nm, r in portal.items() if bucheon_name_key(nm) == key]
    if exact:
        return exact
    alias = BUCHEON_PORTAL_ALIAS.get(name)
    if alias and alias in portal:
        return [portal[alias]]
    if lat is not None and lng is not None:
        cont = [r for nm, r in portal.items()
                if (k2 := bucheon_name_key(nm)) and len(k2) >= 2
                and (k2.startswith(key) or key.startswith(k2))
                and r["lat"] is not None and km(lat, lng, r["lat"], r["lng"]) <= 150]
        if cont:
            return sorted(cont, key=lambda r: km(lat, lng, r["lat"], r["lng"]))
    return []


def bucheon_pick(cands, field):
    """후보들이 한 값으로 모이는 항목만 돌려준다(값이 엇갈리면 비워 둔다)."""
    vals = {c.get(field) for c in cands if c.get(field) not in (None, "", 0)}
    return vals.pop() if len(vals) == 1 else None


def build_bucheon():
    """부천시 공영주차장을 표준데이터 + 부천주차포털 + 부천도시공사 현황표로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 부천시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 구간 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    부천시 표준데이터는 기본요금·추가요금·일일권·정기권 칸이 모두 비어 있고 급지구분만 등록되어 있다.
    그래서 주차장별 요금은 부천주차포털의 최신 등록값(급지·기본 30분·10분당·1일 최대·정기권)을 쓰고,
    포털에 없는 주차장은 부천도시공사 현황표, 그것도 없으면 조례 별표1의 급지 요금을 쓴다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == BUCHEON_PROVIDER]
    portal = load_bucheon_portal()
    status = load_bucheon_status()
    lots, excluded = [], []
    card_no = street_no = 0

    for r in rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (BUCHEON_BBOX[0] <= lat <= BUCHEON_BBOX[1]
                                      and BUCHEON_BBOX[2] <= lng <= BUCHEON_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        gu = gu_in(addr, BUCHEON_DISTRICTS)
        if not gu:
            excluded.append({"name": name, "reason": "구 판정 불가"})
            continue

        cands = [] if name in BUCHEON_PORTAL_SKIP else bucheon_candidates(name, portal, lat, lng)
        hit = cands[0] if len(cands) == 1 else None
        st = status.get(bucheon_name_key(name))

        # 동 — 지번주소 → 포털·현황표 주소 → 확인표 → 같은 구에서 좌표가 가장 가까운 주차장
        dong = bucheon_dong_of(jibun, gu)
        dong_src = "지번주소"
        if not dong:
            for src, text in (("포털주소", hit["addr"] if hit else ""),
                              ("현황표주소", st["addr"] if st else "")):
                dong = bucheon_dong_of(text, gu)
                if dong:
                    dong_src = src
                    break
        if not dong:
            fix = BUCHEON_DONG_VERIFIED.get(name)
            if fix and fix[0] in BUCHEON_DONGS[gu]:
                dong, dong_src = fix
        if not dong and lat is not None:
            near = [(bucheon_dong_of(x["addr"], gu), x) for x in portal.values()
                    if x["lat"] is not None and km(lat, lng, x["lat"], x["lng"]) <= 100]
            dongs = {d for d, _ in near if d}
            if len(dongs) == 1:
                dong, dong_src = dongs.pop(), "포털좌표"
        if not dong:
            dong_src = "없음"

        note = (r.get("특기사항") or "").strip()
        fee_raw = (r.get("요금정보") or "").strip()
        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)
        # 급지 — 포털에 등록된 급지가 가장 최신이라 우선하고, 없으면 표준데이터 급지구분을 쓴다.
        # (부천역 남부 제2호처럼 표준데이터는 1급지·포털은 2급지로 등록된 주차장이 있다)
        std_grade = to_int(r.get("급지구분"))
        grade = (hit["grade"] if hit and hit["grade"] in BUCHEON_FEES
                 else (std_grade if std_grade in BUCHEON_FEES else None))

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"bc-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"bc-{card_no:03d}"

        fee = {
            "type": "무료" if fee_raw == "무료" else ("유료" if fee_raw in ("유료", "혼합") else "미상"),
            "raw_type": fee_raw,
            "mixed": fee_raw == "혼합",
            "grade": grade,
            "std_grade": std_grade,
            "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None, "steps": None,
            "free_min": 0, "cap_fee": None, "cap_src": None,
            "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": None,
            "pay": (r.get("결제방법") or "").strip(),
            "basis": None,
            "ticket_only": False,
        }
        if fee["type"] == "유료":
            free_days = {"sat": False, "sun": False}
            src = None
            base_min = base_fee = unit_min = unit_fee = cap = None
            # 시간(회차) 주차요금이 있는 자료만 쓴다 — 기본요금·10분당이 모두 0인 등록값은
            # 정기권만 파는 주차장이라 0원 요금으로 계산하면 안 된다.
            # 1) 포털 등록값
            if hit and hit["base_min"] and ((hit["base_fee"] or 0) > 0 or (hit["unit_fee"] or 0) > 0):
                base_min, base_fee = hit["base_min"], hit["base_fee"] or 0
                unit_min, unit_fee = hit["unit_min"] or BUCHEON_UNIT_MIN, hit["unit_fee"] or 0
                cap = hit["cap"] or None
                src = "부천주차포털 등록요금"
            # 2) 현황표(엑셀) — 포털에 없거나 시간 요금이 비어 있는 주차장
            #    (현황표의 무인월정 주차장 기본요금 ‘31’은 자리표시 값이라 쓰지 않는다)
            if src is None and st and (st["unit_fee"] or 0) > 0:
                base_min, base_fee = 30, st["base_fee"] or 0
                unit_min, unit_fee = BUCHEON_UNIT_MIN, st["unit_fee"]
                cap = st["day"] or None
                src = "부천도시공사 공영주차장 일반현황"
            # 3) 월정기(정기권) 전용 — 시간 주차요금을 받지 않는 주차장은 0원으로 계산하지 않는다
            if src is None and ("월정기 전용" in note or "정기권 전용" in note):
                fee["type"] = "미상"
                fee["ticket_only"] = True
                fee["basis"] = "정기권(월정기) 전용 — 시간 주차요금 미등록"
            # 4) 조례 별표1 급지 요금 — 위 두 자료에 요금이 없는 주차장
            if src is None and fee["type"] == "유료" and grade in BUCHEON_FEES:
                t = BUCHEON_FEES[grade]
                base_min, base_fee = t["base_min"], t["base_fee"]
                unit_min, unit_fee = BUCHEON_UNIT_MIN, t["unit_fee"]
                cap = t["day"]
                src = f"「부천시 주차장 설치 및 관리 조례」 별표1 {grade}급지"
            if src is None:
                if fee["type"] != "미상":
                    # 어느 자료에도 시간 요금이 없는 주차장 — 0원으로 계산하지 않고 ‘요금 미상’으로 둔다.
                    fee["type"] = "미상"
                    fee["basis"] = "시간 주차요금 미등록 — 현장 확인"
            else:
                fee.update({
                    "base_min": base_min,
                    "base_fee": base_fee,
                    "unit_min": unit_min or BUCHEON_UNIT_MIN,
                    "unit_fee": unit_fee,
                    "free_min": base_min if not base_fee else 0,
                    "cap_fee": cap,
                    "cap_src": ("포털 일일최대요금" if (hit and hit["cap"])
                                else "현황표 1일 요금" if (st and st["day"] and src.startswith("부천도시공사"))
                                else "조례 1일 주차권"),
                    "basis": src,
                })
            monthly = None
            if hit:
                monthly = hit["monthly"] or hit["monthly_day"] or hit["monthly_night"]
            if not monthly and st:
                monthly = st["monthly_all"] or st["monthly_day"] or st["monthly_night"]
            fee["monthly"] = monthly
            if "월정기" in note and fee["type"] == "유료":
                fee["basis"] = (fee["basis"] or "") + " · 특기사항: " + note
        if fee["type"] == "무료":
            free_days = {"sat": True, "sun": True}

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            # 현황표의 ‘위치’는 지번을 괄호로 덧붙인 도로명주소라 그대로 지번주소로 쓰지 않는다.
            "addr_jibun": jibun,
            "addr_status": st["addr"] if st else "",
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip() or (hit["tel"] if hit else ""),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": ({"disabled": hit["disabled"]} if (hit and hit["disabled"]) else None),
            "portal_name": hit["name"] if hit else None,
            "status_name": st["name"] if st else None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["base_fee"] if fee["base_fee"] else (fee["unit_fee"] or None),
            "city": "부천시",
            "city_slug": "bucheon",
        })

    order = {g: i for i, (g, _) in enumerate(BUCHEON_DISTRICTS)}
    lots.sort(key=lambda l: (order[l["gu"]], l["list_mode"] != "card", l["dong"] or "힣", l["name"]))

    quality = check_quality_bucheon(rows_all, rows, lots, excluded, portal, status)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(BUCHEON_PORTAL_JSON).strftime("%Y-%m-%d %H:%M")
                            if BUCHEON_PORTAL_JSON.exists() else None,
            "region": {"province": "경기도", "city": "부천시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-16", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("부천시가 등록한 행만(제공기관명 '경기도 부천시') 추출. 기본요금·추가요금·"
                             "일일권·정기권 칸이 비어 있고 급지구분(1~3급지·기타)만 등록되어 있다."),
                },
                {
                    "id": "bcits", "name": "부천주차포털 공영주차장 목록",
                    "org": "부천도시공사",
                    "url": "https://parking.bcits.go.kr/publicparking/select_publicparking_list.do",
                    "file": BUCHEON_PORTAL_JSON.name,
                    "sha256": sha256(BUCHEON_PORTAL_JSON) if BUCHEON_PORTAL_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(portal),
                    "fetched_at": _snapshot_time(BUCHEON_PORTAL_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if BUCHEON_PORTAL_JSON.exists() else None,
                    "note": ("주차장별 급지·기본 30분 요금·10분당 요금·1일 최대요금·정기권(주간·야간·전일)·"
                             "장애인 구획 확인용. 2026-11-17 08:10 갱신분."),
                },
                {
                    "id": "bcuc", "name": "부천도시공사 공영주차장 일반현황",
                    "org": "부천도시공사",
                    "url": "https://www.best.or.kr/fmcs/1152",
                    "file": BUCHEON_STATUS_XLSX.name,
                    "sha256": sha256(BUCHEON_STATUS_XLSX) if BUCHEON_STATUS_XLSX.exists() else None,
                    "license": "공공기관 공개 자료(참고용)",
                    "base_date": None, "rows_total": len(status),
                    "fetched_at": _snapshot_time(BUCHEON_STATUS_XLSX).strftime("%Y-%m-%d %H:%M (KST)")
                                  if BUCHEON_STATUS_XLSX.exists() else None,
                    "note": ("102개소(노상 8·노외 72·부설 22)의 급지·주차면·위치(지번)·구조·운영시간·"
                             "요금·정기권 현황. 포털에 없는 주차장의 요금·지번 보강에 썼다."),
                },
                {
                    "id": "ordinance", "name": "부천시 주차장 설치 및 관리 조례 (별표1)",
                    "org": "부천시",
                    "url": "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2130259",
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "시행 2026-05-18 (경기도부천시조례 제4326호)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("공영주차장 주차요금 부과 기준(별표1)과 요금 감면·급지 구분 근거. "
                             "2026-11-17 부천도시공사 요금 안내·부천주차포털 등록요금으로 교차 확인."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in BUCHEON_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "grade_base",
            "unit_min": BUCHEON_UNIT_MIN,
            "rows": [
                {"grade": g, "base_min": t["base_min"], "base_fee": t["base_fee"],
                 "unit_fee": t["unit_fee"], "day": t["day"],
                 "street_monthly": t["street_monthly"], "off_day": t["off_day"],
                 "off_night": t["off_night"], "off_all": t["off_all"]}
                for g, t in sorted(BUCHEON_FEES.items())
            ],
            "facility": BUCHEON_FACILITY_FEE,
            "basis": ("「부천시 주차장 설치 및 관리 조례」 별표1(시행 2026-05-18) · "
                      "부천도시공사 공영주차장 요금 안내·부천주차포털 등록요금(2026-11-17 확인)"),
        },
    }
    payload.update(CITY_META["부천시"] | {
        "city": "부천시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": BUCHEON_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "bucheon_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_bucheon(std_all, rows, lots, excluded, portal, status):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(f'{l["gu"]} {l["dong"] or "동 미상"}' for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["base_fee"] for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_부천시행수": len(rows),
        "포털_주차장수": len(portal),
        "포털_매칭": len([l for l in lots if l.get("portal_name")]),
        "현황표_주차장수": len(status),
        "현황표_매칭": len([l for l in lots if l.get("status_name")]),
        "포털_미매칭_유료": [l["name"] for l in lots
                            if l["fee"]["type"] == "유료" and not l.get("portal_name")],
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(Counter(l["gu"] for l in card)),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({(l["gu"], l["dong"]) for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "정기권전용": [l["name"] for l in lots if l["fee"].get("ticket_only")],
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots if l["fee"]["type"] == "유료")),
        "요금근거": dict(Counter(l["fee"]["basis"] for l in lots if l["fee"]["type"] == "유료")),
        "급지_불일치": [f'{l["name"]}(표준 {l["fee"]["std_grade"]}급지·포털 {l["fee"]["grade"]}급지)'
                       for l in lots
                       if l.get("portal_name") and l["fee"]["std_grade"] in BUCHEON_FEES
                       and l["fee"]["grade"] and l["fee"]["std_grade"] != l["fee"]["grade"]],
        "일일상한_포털값": len([l for l in lots if l["fee"].get("cap_src") == "포털 일일최대요금"]),
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 고양시 (T-03 Phase 7)
GOYANG_PROVIDER = "경기도 고양시"
GOYANG_BBOX = (37.55, 37.72, 126.70, 126.96)      # 고양시 대략 경계(좌표 점검용)
# 고양시는 덕양구·일산동구·일산서구 3개 일반구 체제다(1992년 일산구 설치, 2005년 일산동구·일산서구 분구).
GOYANG_DISTRICTS = [("덕양구", "goyang-deogyang"), ("일산동구", "goyang-ilsandong"),
                    ("일산서구", "goyang-ilsanseo")]

# 고양시 공영주차장 요금 — 「고양시 주차장 설치 및 관리 조례」 별표1
# (시행 2026-07-10, 경기도고양시조례 제3013호)과 고양도시관리공사 요금안내(2026-11-17 확인).
# 2008년 이후 17년 동결했던 공영주차장 요금을 2025-08-01·2026-07-01·2027-07-01 세 차례에 걸쳐
# 단계적으로 현실화하는 연도별 요금표를 두고 있어, 지금(2026-11-17) 적용 구간은 2026년
# (2026-07-01~2027-06-30)이다. 2027-07-01부터는 다시 오른다.
#   · 노외: 최초 30분 기본요금 + 30분 초과분 5분 단위 가산, 1일 주차권·월 정기권
#   · 노상: 1구획 5분 단위 요금, 2시간을 넘기면 2시간 초과분부터 2배(할증)
#   · 4급지는 폐지되어 환승주차장과 도시공원(호수공원 등) 부설주차장은 노상 3급지 요금을 적용
GOYANG_APPLIES = "2026-07-01 ~ 2027-06-30 (2026년 구간)"
GOYANG_FEES = {
    1: {"base_min": 30, "base_fee": 720, "unit_min": 5, "unit_fee": 120,
        "day": 9_500, "monthly": 100_000},
    2: {"base_min": 30, "base_fee": 600, "unit_min": 5, "unit_fee": 120,
        "day": 7_200, "monthly": 90_000},
    3: {"base_min": 30, "base_fee": 240, "unit_min": 5, "unit_fee": 70,
        "day": 3_600, "monthly": 70_000},
}
GOYANG_STREET = {
    1: {"unit_fee": 190, "over_fee": 380, "day": None, "monthly": None},
    2: {"unit_fee": 120, "over_fee": 240, "day": None, "monthly": None},
    3: {"unit_fee": 100, "over_fee": 180, "day": 5_500, "monthly": 60_000},
}
GOYANG_STREET_UNIT_MIN = 5
# 2025-08-01 인상 전(17년 동결) 급지 요금 — 표준데이터 등록값과 대조해 ‘주차장 자체 등록요금’을 가려낸다.
# (등록값이 이 표와 다르면 그 주차장만의 요금이거나 등록 오류라 품질 리포트에 따로 적는다)
GOYANG_OLD_FEES = {1: (600, 5, 100, 8_000), 2: (500, 5, 100, 6_000), 3: (200, 5, 50, 3_000)}
GOYANG_OLD_STREET = {1: 150, 2: 100, 3: 80}
# 부설주차장 — 고양도시관리공사 부설주차장 요금 안내(2026-11-17 확인)
#   · 시·구청, 차량등록과, 행정복지센터, 일산사회복지관: 최초 1시간 무료 이후 5분당 190원
#   · 고양시 도시공원(호수공원, 행주산성역사공원 등): 노상 3급지 요금(평상시) · 행사 시 1구획 2,200원
#   · 행주산성: 1구획당 2,000원
#   · 그 밖의 부설주차장: 시청부설주차장 요금
GOYANG_OFFICE_FEE = {"free_min": 60, "base_min": 60, "unit_min": 5, "unit_fee": 190}
GOYANG_HAENGJU_DAY = 2_000
GOYANG_EVENT_FEE = 2_200

# 고양시 공영주차장 요금 감면 — 고양도시관리공사 ‘주차요금 할인’ 안내(2026-11-17 확인)와
# 「고양시 주차장 설치 및 관리 조례」 별표1 비고.
#   · 100%     : 국가유공자, 고엽제후유의증환자·2세환자, 5·18민주화운동 부상자,
#                장애의 정도가 심한 장애인, 자원봉사 실적 상위 100명(이상 12시간 이내 주차에 한함.
#                12시간을 넘기면 50% 감경), 모범·유공납세자 표지 부착 차량, 전기차 충전 2시간 이내
#   · 50%      : 장애의 정도가 심하지 않은 장애인, 임산부, 장기복무 제대군인, 경형자동차,
#                저공해자동차, 다자녀(두 자녀 이상) 카드 제시 차량, 병역명문가, 환경친화적자동차,
#                65세 이상 자가운전 차량
#   · 감면이 겹치면 비율이 높은 하나만 적용
GOYANG_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·임산부·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형(1,000cc 미만)·저공해·임산부·다자녀·병역명문가·장기복무 제대군인·65세 이상"},
    {"label": "심하지 않은 장애인 50%", "rate": 0.5, "exempt_min": 0,
     "note": "장애의 정도가 심하지 않은 장애인 등록 차량"},
    {"label": "국가유공자·심한 장애인 12시간 면제 후 50%", "rate": 0.5, "exempt_min": 720,
     "note": "국가유공자·고엽제·5·18부상자·심한 장애인, 12시간까지 면제"},
    {"label": "모범·유공납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "모범납세자 스티커·유공납세자 차량"},
]
# 표준데이터(기준일 2026-04-15)의 주차장별 금액은 2025-08-01 인상 전(2008년 이후 동결 요금) 값이라
# 현재 조례 요금과 다르다. 그래서 요금은 급지·부설 갈래별 최신 요금표로 계산하고,
# 등록값과 크게 다른 주차장은 품질 리포트(등록값_차이)와 페이지 안내에 함께 적는다.
GOYANG_CATEGORY_LABEL = {
    "off1": "노외 1급지", "off2": "노외 2급지", "off3": "노외 3급지",
    "street1": "노상 1급지", "street2": "노상 2급지", "street3": "노상 3급지",
    "transfer": "환승주차장(노상 3급지)", "park": "도시공원 부설(노상 3급지)",
    "office": "시·구청·행정복지센터 부설(1시간 무료)", "haengju": "행주산성 부설(1구획 2,000원)",
}


def goyang_dong_of(text: str):
    """지번주소에서 고양시 법정동을 뽑는다(‘일산동구’처럼 구 이름이 붙은 토큰은 동이 아니다)."""
    t = (text or "").strip()
    m = re.search(r"([가-힣]{1,6}동)\s*\d", t) or re.search(r"([가-힣]{1,6}동)\s*$", t)
    if not m:
        return None
    d = m.group(1)
    return None if d.endswith("구") or d in ("고양시",) else d


def goyang_facility_kind(name: str, ptype: str):
    """부설주차장의 요금 갈래 — 고양도시관리공사 부설주차장 요금 안내의 구분을 따른다."""
    if ptype != "부설":
        return None
    if "역사공원" in name or "공원" in name:
        return "park"        # 도시공원(호수공원·행주산성역사공원 등) → 노상 3급지
    if "행주산성" in name:
        return "haengju"     # 행주산성 부설 → 1구획당 2,000원
    return "office"          # 시·구청·차량등록과·행정복지센터·사회복지관, 그 밖의 부설


def goyang_street_fee(grade: int = 3):
    """노상 요금 — 5분 단위로 매기고 2시간을 넘기면 2시간 초과분부터 2배(할증)."""
    t = GOYANG_STREET[grade]
    return {
        "base_min": GOYANG_STREET_UNIT_MIN, "base_fee": t["unit_fee"],
        "unit_min": GOYANG_STREET_UNIT_MIN, "unit_fee": t["unit_fee"],
        "steps": [{"until": 120, "unit_fee": t["unit_fee"]},
                  {"until": None, "unit_fee": t["over_fee"]}],
        "steps_label": "2시간 초과 할증",
        "free_min": 0,
        "daily_hours": 24 if t["day"] else None, "daily_fee": t["day"],
        "monthly": t["monthly"],
    }


def build_goyang():
    """고양시 공영주차장을 표준데이터 + 조례 별표1(2026년 요금표)로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 고양시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 권역 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    요금은 표준데이터의 주차장별 금액이 2025-08-01 인상 전 값이라, 조례 별표1의 2026년(2026-07-01~
    2027-06-30) 요금표를 급지·부설 갈래별로 적용한다. 환승주차장은 노상 3급지, 도시공원 부설은
    노상 3급지, 시·구청 부설은 최초 1시간 무료 뒤 5분당 190원, 행주산성 부설은 1구획 2,000원이다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GOYANG_PROVIDER]
    lots, excluded = [], []
    card_no = street_no = 0

    for r in rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        addr = jibun or road
        ptype = (r.get("주차장유형") or "").strip() or "주차장"
        fee_raw = (r.get("요금정보") or "").strip()
        spaces = to_int(r.get("주차구획수"))
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (GOYANG_BBOX[0] <= lat <= GOYANG_BBOX[1]
                                      and GOYANG_BBOX[2] <= lng <= GOYANG_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        gu = gu_in(addr, GOYANG_DISTRICTS)
        if not gu:
            excluded.append({"name": name, "reason": "구 판정 불가"})
            continue

        dong = goyang_dong_of(jibun)
        dong_src = "지번주소" if dong else "없음"

        note = (r.get("특기사항") or "").strip()
        win, oper, closed_note = parse_schedule(r, note)
        free_days = parse_free_days(note)
        std_grade = to_int(r.get("급지구분"))
        std_fee = {
            "base_min": to_int(r.get("주차기본시간")),
            "base_fee": to_int(r.get("주차기본요금")),
            "unit_min": to_int(r.get("추가단위시간")),
            "unit_fee": to_int(r.get("추가단위요금")),
            "day": to_int(r.get("1일주차권요금")),
            "monthly": to_int(r.get("월정기권요금")),
        }

        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"gy-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"gy-{card_no:03d}"

        fee = {
            "type": "무료" if fee_raw == "무료" else ("유료" if fee_raw in ("유료", "혼합") else "미상"),
            "raw_type": fee_raw,
            "mixed": fee_raw == "혼합",
            "grade": std_grade,
            "std_grade": std_grade,
            "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None, "steps": None,
            "free_min": 0, "cap_fee": None, "cap_src": None,
            "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": None,
            "pay": (r.get("결제방법") or "").strip(),
            "basis": None,
            "category": None,
            "std": std_fee,
        }

        if fee["type"] == "유료":
            free_days = {"sat": False, "sun": False}
            category = None
            if street:
                category = f"street{std_grade if std_grade in GOYANG_STREET else 3}"
                fee.update(goyang_street_fee(std_grade if std_grade in GOYANG_STREET else 3))
                fee["cap_src"] = "노상 3급지 1일 주차권" if fee["daily_fee"] else None
            elif ptype == "부설":
                category = goyang_facility_kind(name, ptype)
                if category == "haengju":
                    # 행주산성 부설 — 1구획당 2,000원(입차 기준). 시간 요금은 두지 않는다.
                    fee.update({"base_min": 1_440, "base_fee": GOYANG_HAENGJU_DAY,
                                "unit_min": 1_440, "unit_fee": GOYANG_HAENGJU_DAY,
                                "daily_hours": 24, "daily_fee": GOYANG_HAENGJU_DAY})
                    fee["cap_src"] = "행주산성 1구획당 요금"
                elif category == "park":
                    fee.update(goyang_street_fee(3))
                    fee["cap_src"] = "노상 3급지 1일 주차권"
                else:
                    fee.update({
                        "free_min": GOYANG_OFFICE_FEE["free_min"],
                        "base_min": GOYANG_OFFICE_FEE["base_min"], "base_fee": 0,
                        "unit_min": GOYANG_OFFICE_FEE["unit_min"],
                        "unit_fee": GOYANG_OFFICE_FEE["unit_fee"],
                        "monthly": std_fee["monthly"],
                    })
                    fee["cap_src"] = None
            elif "환승" in name and std_grade == 4:
                # 4급지가 폐지되면서 4급지 환승주차장은 노상 3급지 요금을 적용한다(공사 요금안내 비고).
                # 삼송역 환승처럼 노외 1급지로 등록된 환승주차장은 급지 요금을 그대로 쓴다.
                category = "transfer"
                fee.update(goyang_street_fee(3))
                fee["cap_src"] = "노상 3급지 1일 주차권"
            else:
                grade = std_grade if std_grade in GOYANG_FEES else 3
                category = f"off{grade}"
                t = GOYANG_FEES[grade]
                fee.update({
                    "base_min": t["base_min"], "base_fee": t["base_fee"],
                    "unit_min": t["unit_min"], "unit_fee": t["unit_fee"],
                    "daily_hours": 24, "daily_fee": t["day"],
                    "cap_src": "조례 1일 주차권",
                })
                fee["monthly"] = t["monthly"]
            fee["category"] = category
            fee["basis"] = (f"「고양시 주차장 설치 및 관리 조례」 별표1 {GOYANG_CATEGORY_LABEL[category]}"
                            f" · {GOYANG_APPLIES}")
            # 등록값이 급지 요금표와 다른 주차장 — 조례 개정과 무관한 ‘자체 등록요금·등록 오류’라
            # 품질 리포트에 따로 적는다(예: 고양일산의 60분 무료·1일 4,000원).
            reg = fee["std"]
            if not street and ptype == "노외" and std_grade in GOYANG_OLD_FEES:
                old_base, old_unit_min, old_unit, old_day = GOYANG_OLD_FEES[std_grade]
                if (reg["base_fee"], reg["unit_min"], reg["unit_fee"], reg["day"]) != \
                        (old_base, old_unit_min, old_unit, old_day):
                    fee["std_diff"] = (f"등록값 {reg['base_min'] or 0}분 {reg['base_fee'] or 0}원·"
                                       f"5분당 {reg['unit_fee'] or 0}원·1일 {reg['day'] or 0}원"
                                       f" → 적용 {fee['base_min']}분 {fee['base_fee']}원·"
                                       f"5분당 {fee['unit_fee']}원·1일 {fee['daily_fee'] or 0}원")
            elif street and std_grade in GOYANG_OLD_STREET and reg["base_fee"] != GOYANG_OLD_STREET[std_grade]:
                fee["std_diff"] = (f"등록값 5분 {reg['base_fee'] or 0}원(급지 {std_grade}급지 표와 다름)"
                                   f" → 적용 5분 {fee['unit_fee']}원")
        if fee["type"] == "무료":
            free_days = {"sat": True, "sun": True}

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_name(road) if street else None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["base_fee"] if fee["base_fee"] else (fee["unit_fee"] or None),
            "city": "고양시",
            "city_slug": "goyang",
        })

    order = {g: i for i, (g, _) in enumerate(GOYANG_DISTRICTS)}
    lots.sort(key=lambda l: (order[l["gu"]], l["list_mode"] != "card", l["dong"] or "힣", l["name"]))

    quality = check_quality_goyang(rows_all, rows, lots, excluded)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": None,
            "region": {"province": "경기도", "city": "고양시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-15", "rows_total": len(rows_all),
                    "rows_city": len(rows),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("고양시가 등록한 행만(제공기관명 '경기도 고양시') 추출. 주차장별 요금 칸에는 "
                             "2025-08-01 인상 전(17년 동결) 금액이 남아 있어, 요금은 조례 별표1의 2026년 "
                             "요금표로 계산하고 등록값은 카드에 함께 적었다."),
                },
                {
                    "id": "gys", "name": "고양도시관리공사 주차장 현황·요금안내",
                    "org": "고양도시관리공사",
                    "url": "https://m.gys.or.kr/page/facilities/traffic/parking.php",
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": GOYANG_APPLIES, "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("연도별 주차요금표(2025년 2025-08-01~2026-06-30 · 2026년 2026-07-01~"
                             "2027-06-30 · 2027년 2027-07-01~), 부설주차장 요금, 감면·차종 할증, "
                             "급지 구분. 시설현황은 노외 64·노상 11·부설 20개소(10,275면)."),
                },
                {
                    "id": "ordinance", "name": "고양시 주차장 설치 및 관리 조례 (별표1)",
                    "org": "고양시",
                    "url": "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2148065",
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "시행 2026-07-10 (경기도고양시조례 제3013호)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("공영주차장 주차요금(별표1)과 급지 구분 근거. 노상·노외 급지별 요금, "
                             "2시간 초과 할증, 4급지 폐지에 따른 환승주차장·도시공원 부설의 노상 3급지 "
                             "적용. 2026-11-17 고양도시관리공사 요금안내와 교차 확인."),
                },
                {
                    "id": "its", "name": "고양특례시 교통정보시스템 주차정보",
                    "org": "고양시",
                    "url": "https://its.goyang.go.kr/parking-info",
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": 105,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("주차장 105곳의 면수·주소·이용시간 확인용(예: 고양일산 129면 08:00~22:00). "
                             "요금은 등록되어 있지 않아 요금 근거로 쓰지 않았다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GOYANG_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "goyang_grade_year",
            "applies": GOYANG_APPLIES,
            "off": [{"grade": g, "base_min": t["base_min"], "base_fee": t["base_fee"],
                     "unit_min": t["unit_min"], "unit_fee": t["unit_fee"],
                     "day": t["day"], "monthly": t["monthly"]}
                    for g, t in sorted(GOYANG_FEES.items())],
            "street": [{"grade": g, "unit_min": GOYANG_STREET_UNIT_MIN, "unit_fee": t["unit_fee"],
                        "over_fee": t["over_fee"], "day": t["day"], "monthly": t["monthly"]}
                       for g, t in sorted(GOYANG_STREET.items())],
            "facility": {
                "office_free_min": GOYANG_OFFICE_FEE["free_min"],
                "office_unit_min": GOYANG_OFFICE_FEE["unit_min"],
                "office_unit_fee": GOYANG_OFFICE_FEE["unit_fee"],
                "haengju_day": GOYANG_HAENGJU_DAY,
                "event_fee": GOYANG_EVENT_FEE,
            },
            "basis": ("「고양시 주차장 설치 및 관리 조례」 별표1(시행 2026-07-10) · "
                      "고양도시관리공사 요금안내(2026-11-17 확인) — 2026-07-01~2027-06-30 적용"),
        },
    }
    payload.update(CITY_META["고양시"] | {
        "city": "고양시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": GOYANG_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "goyang_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_goyang(std_all, rows, lots, excluded):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(f'{l["gu"]} {l["dong"] or "동 미상"}' for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["base_fee"] for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_고양시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(Counter(l["gu"] for l in card)),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({(l["gu"], l["dong"]) for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "요금갈래": dict(Counter(l["fee"]["category"] for l in lots if l["fee"]["category"])),
        "급지별": dict(Counter(l["fee"]["std_grade"] for l in lots if l["fee"]["type"] == "유료")),
        "등록값_차이": [f'{l["name"]}: {l["fee"]["std_diff"]}' for l in lots if l["fee"].get("std_diff")],
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


def build_summary_city(payload):
    q = payload["quality"]
    city = payload["city"]
    lines = [f"## {city} — 정제 결과 요약\n",
             f"생성 시각: {q['generated_at']} (KST)\n"]
    for s in payload["meta"]["sources"]:
        rows = s.get("rows_city") or s.get("rows_suwon") or s.get("rows_total")
        lines.append(f"- **{s['name']}** · {s['org']} · {s['url']} · 행 {rows} · 기준일 {s['base_date']}\n")
    if city == "수원시":
        lines.append(f"- 주차장 **{q['총_주차장']}곳**(표준데이터 {q['원자료_수원시행수']} + 도시공사 추가 {q['도시공사_추가행수']}) "
                     f"· 총 구획 {q['총_구획수']:,}면 · 실시간 연계 {q['실시간_연계_전체']}곳")
    else:
        lines.append(f"- 노외·부설 주차장 **{q['총_주차장']}곳** · 총 구획 {q['총_구획수']:,}면 "
                     f"(+ 노상 구간 {q['노상_구간']}곳 {q['노상_구획수']:,}면)")
        lines.append(f"- 원자료 {city} {q['원자료_행수']}행 중 껍데기 행 {q['제외_행수']}행 제외")
        if city == "평택시":
            lines.append(f"- 구 없음(자치구 미설치) · 동·읍·면 {q['동수']}개 · 노상 {q['노상_구간']}구간")
        else:
            lines.append(f"- 구별: {q['구별']} · 동(읍·면) {q['동수']}개")
        if q.get("노외_부설"):
            lines.append(f"- 유형: {q['노외_부설']}")
        lines.append(f"- 요금 구분: {q['요금구분']} · 무료 개방 표기 {len(q['무료개방_표기'])}곳 · 평균 기본요금 {q['평균_기본요금']:,}원"
                     if q["평균_기본요금"] else f"- 요금 구분: {q['요금구분']}")
        lines.append(f"- 토·일 공휴일 미운영: 토 {q['토요일_미운영']} / 일·공휴일 {q['일공휴일_미운영']}")
        lines.append(f"- 전화번호 미등록 {q['전화번호_없음']}곳(원자료에 없음)")
        if q.get("동_추정"):
            lines.append(f"- 동 위치 좌표 추정 {len(q['동_추정'])}곳 · 동 미상 {len(q['동_미상'])}곳(구 페이지 표에만 표시)")
    return "\n".join(lines) + "\n"


def build_site_payload(cities):
    """도시 결과를 사이트 생성기용 단일 파일(data/site.json)로 합친다.

    data/site.json 에 사람이 넣어 둔 사이트 설정값(예: ga_measurement_id, T-05 GA4 측정 ID)은
    다시 만들 때 사라지면 안 되므로, 기존 파일에서 그대로 이어받는다.
    """
    keep = {}
    if (DATA / "site.json").exists():
        try:
            old = json.loads((DATA / "site.json").read_text())
            keep = {k: v for k, v in old.items() if k not in ("meta", "cities", "lots")}
        except (json.JSONDecodeError, OSError):
            keep = {}
    lots = []
    for c in cities:
        lots.extend(c["lots"])
    sources, seen = [], set()
    for c in cities:
        for s in c["meta"]["sources"]:
            key = (s["id"], s["url"])
            if key in seen:
                continue
            seen.add(key)
            sources.append(dict(s, city=c["city"]))
    return {
        **keep,
        "meta": {
            "generated_at": max(c["meta"]["generated_at"] for c in cities),
            "snapshot_at": next((c["meta"]["snapshot_at"] for c in cities if c["meta"].get("snapshot_at")), None),
            "provinces": [{"name": "경기도", "slug": "gyeonggi"}],
            "cities": [{k: c[k] for k in ("city", "slug", "province", "province_slug")} for c in cities],
            "sources": sources,
        },
        "cities": [{k: c.get(k) for k in ("city", "slug", "province", "province_slug", "districts",
                                          "quality", "weekend_free_pages", "discounts", "realtime",
                                          "dong_page_min_lots", "fee_table")}
                   for c in cities],
        "lots": lots,
    }


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="공영주차장 파인더 데이터 정제")
    ap.add_argument("--city", choices=["suwon", "seongnam", "yongin", "hwaseong", "anyang", "pyeongtaek", "bucheon", "goyang", "all"], default="all")
    args = ap.parse_args()

    want = (["수원시", "성남시", "용인시", "화성시", "안양시", "평택시", "부천시", "고양시"] if args.city == "all" else \
            {"suwon": ["수원시"], "seongnam": ["성남시"], "yongin": ["용인시"],
             "hwaseong": ["화성시"], "anyang": ["안양시"], "pyeongtaek": ["평택시"],
             "bucheon": ["부천시"], "goyang": ["고양시"]}[args.city])
    cities = []
    if "수원시" in want:
        cities.append(build_suwon())
    if "성남시" in want:
        cities.append(build_seongnam())
    if "용인시" in want:
        cities.append(build_yongin())
    if "화성시" in want:
        cities.append(build_hwaseong())
    if "안양시" in want:
        cities.append(build_anyang())
    if "평택시" in want:
        cities.append(build_pyeongtaek())
    if "부천시" in want:
        cities.append(build_bucheon())
    if "고양시" in want:
        cities.append(build_goyang())

    if args.city == "all":
        site = build_site_payload(cities)
        (DATA / "site.json").write_text(json.dumps(site, ensure_ascii=False, indent=1))

    summary = "\n".join(build_summary_city(c) for c in cities)
    (BASE / "scripts" / "summary.md").write_text(
        "# 공영주차장 파인더 — 도시별 정제 결과\n\n" + summary)
    (BASE / "scripts" / "summary.json").write_text(
        json.dumps({c["city"]: c["quality"] for c in cities}, ensure_ascii=False, indent=1))
    print(summary)


if __name__ == "__main__":
    main()
