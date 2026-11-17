#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공영주차장 파인더 - 데이터 정제 스크립트 (수원시 + 성남시 + 용인시 + 화성시 + 안양시 + 평택시 + 부천시 + 고양시 + 남양주시 + 안산시)

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
     - 남양주시 84행: 요금·운영시간·좌표 (노외 49 + 노상 35, 구 없이 6읍 3면·동)
     - 안산시 153행 + 안산도시공사 75행: 요금·운영시간·좌표 (노외 193 + 노상 28 + 부설 7, 상록·단원 2개 구)
  2) 수원도시공사 공영주차장 통합 안내 지도(parking.suwonudc.co.kr/parking/parkingMap) 임베드 JSON 스냅샷
     -> 실시간 잔여면수, 장애인/경차/전기차/여성/임산부 구획수 (수원시만)
  3) 경기도 수원시_공영노외주차장현황 (공공데이터포털 15157772, CSV, EUC-KR) -> 주소/면수 보강 (수원시만)
  4) 안양도시공사 통합주차포털(parking.auc.or.kr) 주차장 목록 JSON 스냅샷
     -> 법정동이 적힌 주소, 일일 최대요금, 1일 선불요금, 월정기권, 장애인·전기차 구획 (안양시만)
  5) 평택도시공사 공영주차장 포털(parking.puc.or.kr) 주차장 목록 JSON 스냅샷
     -> 급지(1~3급지)·기본시간·기본요금·간격요금·1일 최대요금·월정기권, 법정동 주소 (평택시만)
  6) 부천주차포털(parking.bcits.go.kr) 공영주차장 목록 JSON 스냅샷 + 부천도시공사 공영주차장 일반현황(엑셀)
     -> 주차장별 급지·기본 30분·10분당·1일 최대요금·정기권(주간·야간·전일)·장애인 구획 (부천시만)
  7) 남양주도시공사 원패스파킹(parking.ncuc.or.kr) 주차장 목록 JSON 스냅샷
     -> 주차장별 급지(1~2급지)·기본시간·기본요금·간격요금·1일 주차요금·월 정기권·구획 구성 (남양주시만)
  8) 안산도시공사 홈페이지 공영유료주차장 현황 표 + 주차장 세부내역(상세 팝업) 스냅샷
     -> 주차장별 급지(1~4급지)·주차면수·운영시간·요금·월 정기권·결제방법·환승할인 (안산시만)

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
  data/namyangju_parking.json 남양주시 단독 결과
  data/ansan_parking.json    안산시 단독 결과
  data/data_quality.json     수원시 정합성 점검 결과(기존 경로 호환)
  scripts/summary.md         사람이 읽는 정제 요약 (도시별)
  scripts/summary.json       기계가 읽는 정제 요약 (도시별)

사용법:  python3 scripts/prepare_data.py [--city suwon|seongnam|yongin|hwaseong|anyang|pyeongtaek|bucheon|goyang|namyangju|ansan|siheung|all]
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
    "남양주시": {"slug": "namyangju", "province": "경기도", "province_slug": "gyeonggi",
              "dong_page_min_lots": 3},
    "안산시": {"slug": "ansan", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "시흥시": {"slug": "siheung", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "의정부시": {"slug": "uijeongbu", "province": "경기도", "province_slug": "gyeonggi",
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


# ---------------------------------------------------------------- 남양주시
NAMYANGJU_PROVIDER = "경기도 남양주시"
# 표준데이터에는 같은 84행이 제공기관명만 바꿔 두 번(경기도 남양주시·남양주도시공사) 들어 있다.
# 시 행만 쓰고, 도시공사 행은 품질 리포트에 중복 등록으로 적는다(같은 주차장이 두 번 생기지 않게).
NAMYANGJU_CORP_PROVIDER = "남양주도시공사"
NAMYANGJU_BBOX = (37.48, 37.78, 127.05, 127.36)   # 남양주시 대략 경계(좌표 점검용)
# 남양주도시공사 원패스파킹(parking.ncuc.or.kr) 주차장 목록 스냅샷
#   GET /api/parking/searchParkingList.json?parkingDong=  (주차장 안내 > 주소 검색과 같은 목록)
#   주차장별 급지(GRADE)·기본시간·기본요금·간격요금·1일 주차요금·월 정기권·법정동 주소·구획 구성이 들어 있다.
NAMYANGJU_PORTAL_JSON = RAW / "parking.ncuc.or.kr_searchParkingList_20261117.json"
# 남양주시는 자치구가 없다(6읍 3면 + 동). 평택시와 같이 시 페이지가 계산기·목록 페이지를 겸하고
# 그 아래에 읍·면·동 페이지를 둔다.
NAMYANGJU_DISTRICTS = [("남양주시", "namyangju")]
NAMYANGJU_EUP_MYEON = ("화도읍", "진접읍", "진건읍", "오남읍", "와부읍", "퇴계원읍",
                       "별내면", "조안면", "수동면")

# 남양주시 공영주차장 요금 — 「남양주시 주차장 조례」 제5조 별표1(2026-02-26 개정·시행)과
# 남양주도시공사 원패스파킹 ‘공영주차장 요금안내(2026-02-26 ~ )’(2026-11-17 확인).
#   · 노상 1급지: 최초 30분 600원 · 30분 초과 10분마다 300원 · 1일 7,000원 · 월 정기(주간) 70,000원
#     노상 2급지: 최초 30분 500원 · 30분 초과 10분마다 150원 · 1일 5,000원 · 월 정기(주간) 50,000원
#   · 노외 1급지: 최초 30분 600원 · 30분 초과 10분마다 300원 · 1일 7,000원
#                월 정기 주간 70,000 · 야간 70,000 · 주야간 100,000원
#     노외 2급지: 최초 30분 500원 · 30분 초과 10분마다 200원 · 1일 5,000원
#                월 정기 주간 50,000 · 야간 50,000 · 주야간 80,000원
#   · 급지: 1급지 = 「국토의 계획 및 이용에 관한 법률」상 용도지역 중 도시지역, 2급지 = 그 밖의 지역
#   · 기본 10분 주차는 요금을 받지 않는다(요금안내 ‘기본 10분 주차시 요금면제’·감면표 ‘이용시간 10분 이내’).
#   · 유료운영시간은 공휴일을 제외한 평일과 토요일의 주간(08:00~20:00)이고, 1일 단위시간당
#     주차요금 합계는 1일 주차요금을 넘을 수 없다.
NAMYANGJU_FREE_MIN = 10
NAMYANGJU_UNIT_MIN = 10
NAMYANGJU_FEES = {
    "off": {
        1: {"base_min": 30, "base_fee": 600, "unit_min": 10, "unit_fee": 300,
            "day": 7_000, "month_day": 70_000, "month_night": 70_000, "month_all": 100_000},
        2: {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 200,
            "day": 5_000, "month_day": 50_000, "month_night": 50_000, "month_all": 80_000},
    },
    "street": {
        1: {"base_min": 30, "base_fee": 600, "unit_min": 10, "unit_fee": 300,
            "day": 7_000, "month_day": 70_000},
        2: {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 150,
            "day": 5_000, "month_day": 50_000},
    },
}
# 남양주시 공영주차장 요금 감면 — 조례 별표1 제6호(2026-02-26 시행)와 남양주도시공사
# 원패스파킹 요금안내의 감면표(2026-11-17 확인)를 그대로 옮겼다.
#   · 전액면제 : 공무 관련 자동차, 이용시간 10분 이내, 긴급자동차
#   · 최초 24시간 면제 이후 50% : 국가유공자(유족·가족)·고엽제후유증·5·18민주유공자·장애인·
#                               다자녀(3명 이상)·임산부
#   · 50% : 다자녀(2명)·인체조직 및 장기 기증자·병역명문가·장기복무제대군인·저공해자동차·
#           경형자동차·남양주사랑상품권 결제·승용차부제·함께타기·65세 이상 경로우대·철도 환승·전통시장 이용
#           (승용차부제·함께타기는 2016~2019년 입찰공고에는 20%로 적혀 있었으나,
#            2026-11-17 공사 요금안내 감면표는 50%감면 묶음에 두고 있어 50%로 적는다)
#   · 환경친화적 자동차 : 최초 1시간 면제 이후 50%
#   · 모범·유공납세자, 성실납세자 : 1년 전액면제 / 우수자원봉사자 : 1년 50%
#   · 감면이 겹치면 비율이 높은 하나만 적용하고, 10원 미만은 부과하지 않는다.
NAMYANGJU_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·다자녀(2명)·65세 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형(1,000cc 이하)·저공해·다자녀 2명·병역명문가·장기복무제대군인·65세 이상·철도 환승·전통시장·남양주사랑상품권·승용차부제·함께타기"},
    {"label": "환경친화적 자동차 1시간 면제 후 50%", "rate": 0.5, "exempt_min": 60,
     "note": "전기·수소·태양광·하이브리드차, 최초 1시간 면제"},
    {"label": "장애인·국가유공자·임산부 24시간 면제 후 50%", "rate": 0.5, "exempt_min": 1440,
     "note": "장애인·국가유공자(유족·가족)·고엽제·5·18·임산부·다자녀(3명 이상), 최초 24시간 면제"},
    {"label": "모범·유공·성실납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "모범·유공납세자 및 성실납세자 인증서(스티커) 부착 차량(1년)"},
]
# 포털 이름이 표준데이터와 달라 이름으로 찾지 못하는 주차장(좌표로도 60m 밖).
NAMYANGJU_PORTAL_ALIAS = {
    "정약용생가 다목적광장": "정약용 다목적광장",
}
# 남양주도시공사가 2026-11-17 원패스파킹 공지로 알린 임시 폐쇄 — 태양광 발전설비 설치공사.
#   · 별내 제2공영: 2026-11-02 ~ 2026-11-30
#   · 오남 제1공영 : 2026-10-01 ~ 2026-12-31
# 공사 기간에는 그 구역을 쓸 수 없어 카드와 페이지에 안내를 함께 적는다(요금·면수는 원자료 그대로).
NAMYANGJU_TEMP_CLOSED = {
    "별내동 제2공영": "임시 폐쇄 2026-11-02~11-30(태양광 발전설비 공사) — 공사 기간에는 이용할 수 없습니다",
    "오남 제1공영": "임시 폐쇄 2026-10-01~12-31(태양광 발전설비 공사) — 공사 기간에는 이용할 수 없습니다",
}
NJ_KEY_STRIP = ("주차장", "공영", "노외", "지하", "임시")


def namyangju_is_street_name(s: str) -> bool:
    """이름이 노상(거리) 구간을 가리키는지 — 노상·노외는 같은 번호로 이름이 겹져 구분에 쓴다."""
    return "노상" in re.sub(r"\s", "", s or "")


def namyangju_name_key(s: str, strip=NJ_KEY_STRIP) -> str:
    """주차장 이름 비교용 키 — 괄호 설명과 꾸밈말(공영/주차장/노외/지하/임시), 0으로 시작하는 번호를 뺀다.

    ‘노상’은 빼지 않는다. ‘다산 노상제1’과 ‘다산 제1공영’은 다른 주차장인데, 노상까지 빼면
    둘 다 ‘다산제1’이 되어 섞인다.
    예: ‘화도 제01공영’ ↔ ‘화도 제1공영’, ‘별내동노상 제9공영’ ↔ ‘별내동 노상제9’
    """
    t = re.sub(r"\([^)]*\)", "", s or "")
    t = re.sub(r"[\s()\[\]·,.ㆍ\-]", "", t)
    for w in strip:
        t = t.replace(w, "")
    return re.sub(r"제0+(\d)", r"제\1", t)


def namyangju_unit_of(text: str):
    """주소에서 남양주시 읍·면·동을 뽑는다(읍·면 → 동 순, ‘… (다산동)’ 괄호도 읽는다)."""
    t = text or ""
    for u in NAMYANGJU_EUP_MYEON:
        if re.search(re.escape(u) + r"(\s|$|[^가-힣])", t):
            return u
    m = re.search(r"\(([가-힣]{1,6}(?:동|읍|면))", t)
    if m:
        return m.group(1)
    return dong_from_jibun(t)


def load_namyangju_portal() -> dict:
    """남양주도시공사 원패스파킹 주차장 목록 스냅샷 → 주차장 이름별 정보.

    급지(GRADE)와 기본시간·기본요금·간격요금·1일 주차요금·월 정기권, 법정동 주소, 좌표,
    요일별 운영시간, 구획 구성(일반·장애인·전기·캠핑카·화물차)을 담는다.
    표준데이터에 없는 공공 부설(시청·공원·체육문화센터·한강공원) 주차장도 함께 들어 있어,
    표준데이터 84행과 매칭해 요금·급지 확인에만 쓴다.
    """
    if not NAMYANGJU_PORTAL_JSON.exists():
        return {}
    rows = json.loads(NAMYANGJU_PORTAL_JSON.read_text()).get("parkingList", [])
    out: dict[str, dict] = {}
    for r in rows:
        nm = (r.get("PARKING_NM") or "").strip()
        if not nm:
            continue
        addr = (r.get("CELL_ADDR_JIBUN") or "").strip()
        out[nm] = {
            "name": nm,
            "grade": to_int(r.get("GRADE")),
            "div": (r.get("PARKING_DIV_NM") or "").strip(),
            "addr": addr,
            "spaces": to_int(r.get("CELL_CNT")),
            "base_min": to_int(r.get("DFLT_TM")),
            "base_fee": to_int(r.get("DFLT_AMT")),
            "unit_min": to_int(r.get("INTVL_TM")),
            "unit_fee": to_int(r.get("INTVL_AMT")),
            "cap": to_int(r.get("DAY_PARKING_AMT")),
            "monthly": to_int(r.get("PERIOD_TICKET_AMT")),
            "anyhour": (r.get("ANYHOUR_RUN_YN") or "").strip() == "24시간운영함",
            "free_now": "무료운영중" in addr,
            "disabled": to_int(r.get("HNDCAP_CELL_CNT")),
            "elec": to_int(r.get("ELEC_CELL_CNT")),
            "camping": to_int(r.get("CAMPING_CAR_CELL_CNT")),
            "truck": to_int(r.get("TRUCK_CELL_CNT")),
            "tel": (r.get("TEL_NO") or "").strip(),
            "lat": float(r["LAT"]) if r.get("LAT") else None,
            "lng": float(r["LNG"]) if r.get("LNG") else None,
        }
    return out


def namyangju_portal_match(name: str, portal: dict, lat=None, lng=None):
    """표준데이터 한 행에 대응하는 포털 주차장을 정한다.

    이름이 꾸밈말을 뺐을 때 같은 것 → 이름이 서로 포함되고 120m 안에 있는 것 →
    같은 자리(40m 이내)에 있는 것 → 별칭표 순으로 찾는다.
    포털의 다른 갈래(공원·청사·체육문화센터·한강공원 부설)는 이름이 비슷해도 짝짓지 않고,
    노상 이름은 노상끼리만 짝짓는다(‘다산 노상제1’ ↔ ‘다산 제1공영’은 다른 주차장).
    """
    if not portal:
        return None
    key = namyangju_name_key(name)
    street = namyangju_is_street_name(name)
    pool = [r for r in portal.values()
            if r.get("div") == "공영" and namyangju_is_street_name(r["name"]) == street]
    if not pool:
        return None
    exact = [r for r in pool if namyangju_name_key(r["name"]) == key]
    if exact:
        if len(exact) == 1 or lat is None:
            return exact[0]
        return min(exact, key=lambda r: km(lat, lng, r["lat"], r["lng"])
                   if r["lat"] is not None else 9e9)
    if lat is not None and lng is not None:
        cont = [r for r in pool
                if (k2 := namyangju_name_key(r["name"])) and len(k2) >= 2 and (k2 in key or key in k2)
                and r["lat"] is not None and km(lat, lng, r["lat"], r["lng"]) <= 120]
        if cont:
            return min(cont, key=lambda r: km(lat, lng, r["lat"], r["lng"]))
        near = [r for r in pool
                if r["lat"] is not None and km(lat, lng, r["lat"], r["lng"]) <= 40]
        if near:
            return min(near, key=lambda r: km(lat, lng, r["lat"], r["lng"]))
    alias = NAMYANGJU_PORTAL_ALIAS.get(name)
    if alias and alias in portal:
        return portal[alias]
    return None


def build_namyangju():
    """남양주시 공영주차장을 표준데이터 + 조례 별표1(2026-02-26 요금표)로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 남양주시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 구간 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 카드가 3곳 이상인 읍·면·동만 만든다.
    요금은 조례 별표1의 급지별 요금표를 쓴다. 표준데이터(기준일 2026-09-15)의 주차장별 금액은
    유료 48곳 가운데 46곳이 급지 요금(30분 600원·10분당 300원·1일 7,000원·월 70,000원)과 같고,
    별내동 노상제1·제3 두 곳만 60분 1,000원·30분당 500원으로 등록되어 있어 조례 요금을 적용하고
    등록값 차이를 품질 리포트에 남긴다(포털에는 이 두 곳이 ‘무료운영중’으로 올라와 있어 카드에 함께 적는다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows = [r for r in rows_all if (r.get("제공기관명") or "").strip() == NAMYANGJU_PROVIDER]
    rows_dup = [r for r in rows_all if (r.get("제공기관명") or "").strip() == NAMYANGJU_CORP_PROVIDER]
    portal = load_namyangju_portal()
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
        elif lat is not None and not (NAMYANGJU_BBOX[0] <= lat <= NAMYANGJU_BBOX[1]
                                      and NAMYANGJU_BBOX[2] <= lng <= NAMYANGJU_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        hit = namyangju_portal_match(name, portal, lat, lng)
        dong = namyangju_unit_of(jibun)
        dong_src = "지번주소"
        if not dong:
            dong = namyangju_unit_of(road)
            dong_src = "도로명주소"
        if not dong and hit:
            dong = namyangju_unit_of(hit["addr"])
            dong_src = "포털주소"
        if not dong:
            dong_src = "없음"

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
            lot_id = f"nj-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"nj-{card_no:03d}"

        # 급지는 포털 등록값 → 표준데이터 급지구분 → 1급지 순으로 정한다(이 도시 유료 주차장은 모두 1급지).
        grade = (hit["grade"] if hit and hit.get("grade") in (1, 2) else None) or \
                (std_grade if std_grade in (1, 2) else 1)

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
            "monthly": None, "monthly_night": None, "monthly_all": None,
            "pay": (r.get("결제방법") or "").strip(),
            "basis": None,
            "category": None,
            "std": std_fee,
            "portal_free_now": bool(hit and hit.get("free_now")),
        }

        if fee["type"] == "유료":
            free_days = {"sat": False, "sun": False}
            table = NAMYANGJU_FEES["street" if street else "off"][grade]
            fee.update({
                "base_min": table["base_min"], "base_fee": table["base_fee"],
                "unit_min": table["unit_min"], "unit_fee": table["unit_fee"],
                "free_min": NAMYANGJU_FREE_MIN,
                "daily_hours": 24, "daily_fee": table["day"],
                "cap_src": "조례 1일 주차권",
                "monthly": table["month_day"],
                "monthly_night": table.get("month_night"),
                "monthly_all": table.get("month_all"),
                "category": f"{'street' if street else 'off'}{grade}",
            })
            fee["basis"] = (f"「남양주시 주차장 조례」 별표1 {'노상' if street else '노외'} {grade}급지"
                            f" · 남양주도시공사 요금안내(2026-11-17 확인)")
            # 등록값이 조례 급지표와 다른 주차장 — 품질 리포트에 남기고 급지 요금표를 따른다.
            reg = fee["std"]
            if any(reg[k] for k in ("base_min", "base_fee", "unit_min", "unit_fee")):
                if (reg["base_min"], reg["base_fee"], reg["unit_min"], reg["unit_fee"]) != \
                        (table["base_min"], table["base_fee"], table["unit_min"], table["unit_fee"]):
                    fee["std_diff"] = (f"등록값 {reg['base_min'] or 0}분 {reg['base_fee'] or 0}원·"
                                       f"{reg['unit_min'] or 0}분당 {reg['unit_fee'] or 0}원"
                                       f" → 적용 {table['base_min']}분 {table['base_fee']}원·"
                                       f"{table['unit_min']}분당 {table['unit_fee']}원"
                                       + (" (포털에 무료운영중으로 등록)" if fee["portal_free_now"] else ""))
        if fee["type"] == "무료":
            free_days = {"sat": True, "sun": True}
            # 무료로 등록된 주차장은 평일·토요일 00:00~24:00에 공휴일 칸이 비어 있다. 요금을 받지 않는
            # 주차장이라 다른 도시와 같이 ‘요일과 관계없이 24시간’으로 둔다.
            for k in ("weekday", "sat", "sun"):
                win[k] = {"open": True, "start": 0, "end": 1440, "24h": True,
                          "listed": True, "raw": ["00:00", "24:00"]}
                oper[k] = True

        capa = None
        if hit and (hit.get("disabled") or hit.get("elec") or hit.get("camping") or hit.get("truck")):
            capa = {k: v for k, v in (("disabled", hit.get("disabled")), ("elec", hit.get("elec")),
                                      ("camping", hit.get("camping")), ("truck", hit.get("truck"))) if v}

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "남양주시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip() or (hit["tel"] if hit else ""),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "notice": NAMYANGJU_TEMP_CLOSED.get(name),
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": capa,
            "portal_name": hit["name"] if hit else None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["base_fee"] if fee["base_fee"] else (fee["unit_fee"] or None),
            "city": "남양주시",
            "city_slug": "namyangju",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))

    quality = check_quality_namyangju(rows_all, rows, rows_dup, lots, excluded, portal)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(NAMYANGJU_PORTAL_JSON).strftime("%Y-%m-%d %H:%M")
                            if NAMYANGJU_PORTAL_JSON.exists() else None,
            "region": {"province": "경기도", "city": "남양주시"},
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
                    "note": ("남양주시가 등록한 행만(제공기관명 '경기도 남양주시') 추출. 같은 84행이 "
                             "'남양주도시공사' 이름으로 한 번 더 들어 있어 도시공사 행은 쓰지 않았다."),
                },
                {
                    "id": "ncuc", "name": "남양주도시공사 원패스파킹 주차장 목록",
                    "org": "남양주도시공사",
                    "url": "https://parking.ncuc.or.kr/list",
                    "file": NAMYANGJU_PORTAL_JSON.name,
                    "sha256": sha256(NAMYANGJU_PORTAL_JSON) if NAMYANGJU_PORTAL_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(portal),
                    "fetched_at": _snapshot_time(NAMYANGJU_PORTAL_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if NAMYANGJU_PORTAL_JSON.exists() else None,
                    "note": ("주차장별 급지·기본시간·기본요금·간격요금·1일 주차요금·월 정기권·구획 구성과 "
                             "법정동 주소 확인용. 공영 49곳과 공공 부설(시청·공원·체육문화센터·한강공원) "
                             "26곳이 들어 있다."),
                },
                {
                    "id": "ordinance", "name": "남양주시 주차장 조례 (별표1 주차요금표)",
                    "org": "남양주시",
                    "url": "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2112523",
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "2026-02-26 개정·시행", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("노상·노외 급지(1~2급지)별 요금표와 감면(별표1 제6호) 근거. 노상 1급지 "
                             "30분 600원·10분당 300원·1일 7,000원, 노외 1급지 같은 요금에 월 정기권 "
                             "주간·야간·주야간 구분. 2026-11-17 원패스파킹 요금안내와 교차 확인."),
                },
                {
                    "id": "nyj", "name": "남양주시 주차장정보(공영주차장 현황)",
                    "org": "남양주시청",
                    "url": "https://www.nyj.go.kr/www/contents.do?key=3113",
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-01-09", "rows_total": 84,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("노상 35개소(무료 28·유료 7)와 노외 49개소(무료 8·유료 41)의 위치·면수·"
                             "설치년도 확인용. 표준데이터 84행과 같은 목록이다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in NAMYANGJU_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "namyangju_dual",
            "unit_min": NAMYANGJU_UNIT_MIN,
            "free_min": NAMYANGJU_FREE_MIN,
            "applies": "2026-02-26 개정 조례",
            "off": [{"grade": g, **t} for g, t in sorted(NAMYANGJU_FEES["off"].items())],
            "street": [{"grade": g, **t} for g, t in sorted(NAMYANGJU_FEES["street"].items())],
            "facility": {"free_min": 60, "unit_min": 10, "unit_fee": 200,
                         "day_office": 5_000, "day_park": 7_000, "monthly": 30_000},
            "basis": ("「남양주시 주차장 조례」 별표1(2026-02-26 개정·시행) · "
                      "남양주도시공사 원패스파킹 공영주차장 요금안내(2026-11-17 확인)"),
        },
    }
    payload.update(CITY_META["남양주시"] | {
        "city": "남양주시",
        "weekend_free_pages": False,     # 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": NAMYANGJU_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "namyangju_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_namyangju(std_all, rows, rows_dup, lots, excluded, portal):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(f'{l["gu"]} {l["dong"] or "동 미상"}' for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["base_fee"] for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    matched = [l for l in lots if l.get("portal_name")]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_남양주시행수": len(rows),
        "중복제공기관_행수": len(rows_dup),
        "중복제공기관_이름": NAMYANGJU_CORP_PROVIDER,
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
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots if l["fee"]["type"] == "유료")),
        "등록값_차이": [f'{l["name"]}: {l["fee"]["std_diff"]}' for l in lots if l["fee"].get("std_diff")],
        "포털_목록수": len(portal),
        "포털_매칭": len(matched),
        "포털_미매칭": [l["name"] for l in lots if not l.get("portal_name")],
        "포털_무료운영중": [l["name"] for l in lots if l["fee"].get("portal_free_now")],
        "임시폐쇄_안내": [f'{l["name"]}: {l["notice"]}' for l in lots if l.get("notice")],
        "구획수_차이": [f'{l["name"]}: 등록 {l["spaces"]}면 ↔ 포털 {portal[l["portal_name"]]["spaces"]}면'
                       for l in matched
                       if portal.get(l["portal_name"], {}).get("spaces") and
                       portal[l["portal_name"]]["spaces"] != l["spaces"]],
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


# ---------------------------------------------------------------- 안산시 (T-03 Phase 9)
ANSAN_PROVIDER = "경기도 안산시"
ANSAN_CORP_PROVIDER = "안산도시공사"
# 안산시는 상록구·단원구 2개 구다. 동 이름은 법정동 기준으로 적는다.
#   · 상록구: 사동·본오동·이동·일동·성포동·월피동·부곡동·팔곡이동·수암동·건건동·장상동·장하동·안산동·양상동
#   · 단원구: 고잔동·원곡동·초지동·선부동·와동·신길동·대부북동·대부남동·대부동동·선감동·풍도동·원시동·성곡동·목내동
ANSAN_DISTRICTS = [("상록구", "ansan-sangrok"), ("단원구", "ansan-danwon")]
ANSAN_BBOX = (37.22, 37.38, 126.55, 126.93)     # 안산시 대략 경계(좌표 점검용)
ANSAN_DONGS = {
    "상록구": ("사동", "본오동", "이동", "일동", "성포동", "월피동", "부곡동", "팔곡이동",
             "수암동", "건건동", "장상동", "장하동", "안산동", "양상동"),
    "단원구": ("고잔동", "원곡동", "초지동", "선부동", "와동", "신길동", "대부북동",
             "대부남동", "대부동동", "선감동", "풍도동", "원시동", "성곡동", "목내동"),
}
ANSAN_ALL_DONGS = tuple(d for v in ANSAN_DONGS.values() for d in v)
ANSAN_CORP_JSON = RAW / "ansanuc.ansanuc.net_공영유료주차장현황_20261117.json"
ANSAN_PORTAL_JSON = RAW / "ansanuc.ansanuc.net_parkinglotPopup_20261117.json"
ANSAN_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2126431"
ANSAN_PAGE_URL = "https://www.ansan.go.kr/www/common/cntnts/selectContents.do?cntnts_id=C0001322"
ANSAN_CORP_PAGE_URL = "https://www.ansanuc.net/homenew/10221/40063/contents.do"

# 안산시 공영주차장 요금 — 「안산시 주차장 조례」 별표2 ‘공영유료주차장 주차요금표’(시행 2026-04-29)와
# 안산시 공영유료주차장 요금표·안산도시공사 시설현황/요금안내(2026-11-17 확인)를 그대로 옮겼다.
#   · 1회 주차 1구역 최초 30분 기본요금 뒤 30분을 넘기면 10분마다 가산, 1일 주차요금이 상한
#   · 1급지 600·300·9,000원 / 2급지 400·200·4,500원 / 3급지 300·200·4,500원 / 4급지 300·200·4,500원
#   · 월 정기권(선불) 1급지 80,000 / 2급지 50,000 / 3급지 40,000 / 4급지 20,000원
#   · 지하철 환승 주차장(안산역·고잔역·중앙역·상록수역·한대앞역·반월역)은 ‘2,3급지’ 중복급지로,
#     도시철도 이용확인증을 내면 3급지, 아니면 2급지 요금이다(카드에 안내).
#   · 수암봉은 입차 후 2시간까지 2급지, 이후 1급지 요금이고 주말·공휴일에만 유료 운영한다.
#   · 와~스타디움 부설은 최초 3시간 무료 뒤 1급지 요금(10분당 300원), 1일 9,000원이다.
ANSAN_FEES = {
    1: {"base_min": 30, "base_fee": 600, "unit_min": 10, "unit_fee": 300, "day": 9_000, "monthly": 80_000},
    2: {"base_min": 30, "base_fee": 400, "unit_min": 10, "unit_fee": 200, "day": 4_500, "monthly": 50_000},
    3: {"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 200, "day": 4_500, "monthly": 40_000},
    4: {"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 200, "day": 4_500, "monthly": 20_000},
}
ANSAN_UNIT_MIN = 10
# 안산시는 공영주차장 전체에 적용하는 ‘최초 N분 무료’가 없다(시청부설 20분, 와~스타디움 3시간만 별도).

# 안산시 공영주차장 요금 감면 — 안산시 ‘주차요금 할인 안내’와 안산도시공사 감면 안내(2026-11-17 확인).
#   · 100%               : 긴급자동차, 국가·지자체 공무수행 관용차, 모범납세자·안산시 성실납세자(1년)
#   · 3시간 면제 후 50%   : 행복플러스카드(다자녀·임산부), 국가보훈대상자, 장애 정도가 심한 장애인,
#                          5·18민주유공자, 고엽제
#   · 2시간 면제 후 50%   : 전기·태양광·수소자동차
#   · 1시간 면제 후 50%   : 장애 정도가 심하지 않은 장애인, VIP자원봉사증
#   · 50%                : 경형(1,000cc 미만), 저공해(경유 제외), 우수자원봉사증, 경기아이플러스카드,
#                          병역명문가, 장기등·인체조직 기증자, 병역 의무 이행 청년카드
#   · 감면은 중복 적용하지 않는다(현장 확인).
ANSAN_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·자원봉사 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형(1,000cc 미만)·저공해(경유 제외)·우수자원봉사증·경기아이플러스카드·병역명문가·장기기증자"},
    {"label": "심하지 않은 장애인 1시간 면제 후 50%", "rate": 0.5, "exempt_min": 60,
     "note": "장애 정도가 심하지 않은 장애인·VIP자원봉사증, 최초 1시간 면제"},
    {"label": "전기·수소차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "전기·태양광·수소자동차, 최초 2시간 면제"},
    {"label": "장애인·국가유공자 3시간 면제 후 50%", "rate": 0.5, "exempt_min": 180,
     "note": "심한 장애인·국가보훈대상자·5·18민주유공자·고엽제·행복플러스카드(다자녀·임산부), 최초 3시간 면제"},
    {"label": "모범·성실납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "국세청 모범납세자·안산시 성실납세자 표지 부착 차량(교부일부터 1년)"},
]
# 표준데이터 이름과 안산도시공사 홈페이지 이름이 달라 이름으로 찾지 못하는 주차장.
ANSAN_NAME_ALIAS = {
    "메가박스앞": "메가넥스앞",                       # 홈페이지 상세 팝업의 표기 오타
    "외국인본부부설주차장": "외국인지원본부",
    "상록수역환승주차장": "상록수역환승",
}
# 시간제 주차요금 없이 월 정기권만 받는 화물차 전용 차고지 — 0원이 아니라 ‘요금 미상(정기권 전용)’으로 표시한다.
ANSAN_TICKET_ONLY = {
    "월피동 화물주차장": 90_000,
    "팔곡동 화물차고지": 90_000,
    "부곡동 화물전용주차장": 90_000,
}
# 지하철 환승 할인(도시철도 이용확인증) 대상 — 2급지 요금으로 계산하고 카드에 3급지 요금을 함께 적는다.
ANSAN_TRANSFER_NOTE = ("도시철도 환승(이용확인증 제시) 시 3급지 요금(30분 300원·10분당 200원)이 적용됩니다"
                       " — 환승하지 않으면 2급지 요금입니다")


def ansan_name_key(s: str, drop_parens: bool = True) -> str:
    """주차장 이름 비교용 키 — 꾸밈말(주차장·공영·주차타워·지하·임시)을 뺀다.

    drop_parens=True  : ‘(소)’, ‘(대)’처럼 구획을 나눈 괄호를 빼 같은 주차장으로 본다
                        (고잔역환승(소) ↔ 고잔역환승).
    drop_parens=False : 괄호 안 설명을 남긴다 — ‘안산역환승(서측)’과 ‘안산역환승(동측)’,
                        ‘공단삼거리(1주차장-중앙일보)’와 ‘공단삼거리 1주차장’을 가르는 데 쓴다.
    """
    t = re.sub(r"[\s\[\]·,.ㆍ~]", "", s or "")
    if drop_parens:
        t = re.sub(r"\([^)]*\)", "", t)
    else:
        t = t.replace("(", "").replace(")", "")
    for w in ("주차장", "주차타워", "공영", "지하", "임시"):
        t = t.replace(w, "")
    return t


def ansan_addr_jibun(addr: str) -> str:
    """지번주소 비교용 — 공백·‘번지’·구 이름을 빼고 동+번지로 맞춘다."""
    t = re.sub(r"\s", "", addr or "").replace("번지", "")
    return t.replace("경기도안산시", "")


def ansan_dong_of(text: str):
    """주소에서 안산시 법정동을 뽑는다(긴 이름 우선 — 대부북동/대부동동 구분)."""
    t = re.sub(r"\s", "", text or "")
    for d in sorted(ANSAN_ALL_DONGS, key=len, reverse=True):
        # ‘고잔동 539-11’처럼 지번이 바로 붙거나, ‘본오동 산128-1’처럼 임야번지가 붙는다.
        if re.search(re.escape(d) + r"(?=$|\d|산\d|[^가-힣])", t):
            return d
    return None


def ansan_gu_of(dong: str):
    for gu, names in ANSAN_DONGS.items():
        if dong in names:
            return gu
    return None


def load_ansan_corp_list() -> list:
    """안산도시공사 홈페이지 ‘공영유료주차장 시설현황’ 표 스냅샷 → 주차장별 급지·면수·운영시간."""
    if not ANSAN_CORP_JSON.exists():
        return []
    raw = json.loads(ANSAN_CORP_JSON.read_text())
    out = []
    for r in raw.get("lots", []):
        grades = [int(x) for x in re.findall(r"\d", str(r.get("grade") or ""))]
        out.append({**r, "grades": grades, "grade": grades[0] if grades else None})
    return out


def load_ansan_portal() -> dict:
    """안산도시공사 주차장 상세(주차장세부내역) 팝업 스냅샷 → 이름별 요금·면수·결제방법·환승할인.

    팝업 본문은 ‘위치 … 주차면수 … 운영시간 … 결제방법 … 이용요금 월정기/30분기본/추가 10분당/1일주차요금’
    순서의 한 줄 텍스트라 필요한 값만 뽑는다. 수암봉처럼 월정기·기본요금 칸이 없는 주차장은 빈 값으로 둔다.
    """
    if not ANSAN_PORTAL_JSON.exists():
        return {}
    raw = json.loads(ANSAN_PORTAL_JSON.read_text())
    out: dict[str, dict] = {}
    for it in raw.get("items", []):
        text = it.get("text") or ""
        m = re.search(r"주차장세부내역(?:\s*주차장세부내역)?\s*(.*?)\s*공영유료주차장", text)
        if not m:
            continue
        name = m.group(1).strip()
        if not name:
            continue
        addr = re.search(r"표\s*위치\s*(.*?)\s*주차면수", text)
        spaces = re.search(r"주차면수\s*(\d+)", text)
        monthly = re.search(r"월정기\s*:\s*([\d,]+)", text)
        base = re.search(r"30분기본\s*:\s*([\d,]+)", text)
        unit = re.search(r"추가\s*10분당\s*([\d,]+)", text)
        daily = re.search(r"1일주차요금\s*:\s*([\d,]+)", text)
        pay = re.search(r"결제방법\s*([가-힣]+)\s*이용요금", text)
        rec = {
            "no": it.get("no"),
            "name": name,
            "addr": (addr.group(1) if addr else "").strip(),
            "spaces": to_int(spaces.group(1)) if spaces else None,
            "monthly": to_int(monthly.group(1)) if monthly else None,
            "base_fee": to_int(base.group(1)) if base else None,
            "unit_fee": to_int(unit.group(1)) if unit else None,
            "day": to_int(daily.group(1)) if daily else None,
            "pay": (pay.group(1) if pay else "").strip(),
            "transfer": "환승할인 : " in text,
            "text": text,
        }
        # 같은 이름이 여러 번(옛 이름·중복 행) 나오면 값이 더 많이 찬 쪽을 쓴다.
        cur = out.get(name)
        if cur is None or sum(bool(rec[k]) for k in ("monthly", "base_fee", "unit_fee", "day")) > \
                sum(bool(cur[k]) for k in ("monthly", "base_fee", "unit_fee", "day")):
            out[name] = rec
    return out


def ansan_name_pick(name: str, pool: dict):
    """이름이 같은(또는 서로 포함되는) 후보 하나를 고른다 — 괄호를 남긴 키를 먼저 본다.

    괄호를 남긴 키로 먼저 맞춰 ‘안산역환승(서측)’이 ‘(동측)’ 값으로 덮이지 않게 하고,
    그다음 괄호를 뺀 키로 ‘고잔역환승(소)’ ↔ ‘고잔역환승’처럼 구획만 나뉜 이름을 잇는다.
    """
    for drop in (False, True):
        key = ansan_name_key(name, drop)
        if not key:
            continue
        for k, r in pool.items():
            if ansan_name_key(k, drop) == key:
                return r
    for drop in (False, True):
        key = ansan_name_key(name, drop)
        if not key:
            continue
        cand = [r for k, r in pool.items()
                if (k2 := ansan_name_key(k, drop)) and len(k2) >= 2 and (k2 in key or key in k2)]
        if len(cand) == 1:
            return cand[0]
    return None


def ansan_portal_match(name: str, portal: dict, corp_list: list):
    """표준데이터 한 행에 대응하는 안산도시공사 상세 팝업을 정한다(별칭표 → 이름 비교 → 같은 지번)."""
    if not portal:
        return None
    alias = ANSAN_NAME_ALIAS.get(name)
    if alias and alias in portal:
        return portal[alias]
    return ansan_name_pick(name, portal)


def ansan_corp_match(name: str, addr: str, corp_list: list):
    """표준데이터 한 행에 대응하는 홈페이지 표(급지·면수·운영시간) 행을 정한다."""
    if not corp_list:
        return None
    alias = ANSAN_NAME_ALIAS.get(name)
    if alias:
        for r in corp_list:
            if r["name"] == alias:
                return r
    hit = ansan_name_pick(name, {r["name"]: r for r in corp_list})
    if hit:
        return hit
    jib = ansan_addr_jibun(addr)
    if jib:
        near = [r for r in corp_list if ansan_addr_jibun(r["addr"]) == jib]
        if len(near) == 1:
            return near[0]
    return None


def ansan_rows_merge(city_rows, corp_rows):
    """시·도시공사 두 제공기관의 행을 주차장 단위로 합친다.

    같은 주차장이 두 제공기관에 나뉘어 등록되어 있어(시 153행 · 도시공사 75행) 그대로 쓰면
    카드가 두 장씩 생긴다. 도시공사 행(요금·급지가 채워진 유료 주차장)을 먼저 두고,
    시 행은 이름 키가 같거나(괄호만 다른 경우 포함) 같은 지번에 이름이 겹치는 경우 중복으로 뺀다.
    """
    chosen = [{"row": r, "src": "도시공사"} for r in corp_rows]
    dropped = []
    for r in city_rows:
        key = ansan_name_key(r.get("주차장명"))
        jib = ansan_addr_jibun(r.get("소재지지번주소"))
        full = re.sub(r"[\s()·ㆍ\-]", "", r.get("주차장명") or "")
        dup = None
        for c in chosen:
            if c["src"] != "도시공사":
                # 시 행끼리는 같은 이름(주택가 주차장 등)이 여러 곳이라 서로 지우지 않는다.
                continue
            o = c["row"]
            okey = ansan_name_key(o.get("주차장명"))
            ofull = re.sub(r"[\s()·ㆍ\-]", "", o.get("주차장명") or "")
            if key and key == okey:
                dup = (c, "이름")
                break
            if jib and jib == ansan_addr_jibun(o.get("소재지지번주소")) and \
                    ((full and (full in ofull or ofull in full)) or not key):
                dup = (c, "지번+이름")
                break
        if dup:
            dropped.append({"name": r.get("주차장명"), "addr": r.get("소재지지번주소"),
                            "kept": dup[0]["row"].get("주차장명"), "why": dup[1]})
        else:
            chosen.append({"row": r, "src": "시"})
    return chosen, dropped


def build_ansan():
    """안산시 공영주차장을 표준데이터 + 안산도시공사 홈페이지 표·상세 팝업으로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 안산시 범위를 벗어난 행은 제외(껍데기 행).
      · 노상(거리) 구간은 이름이 구간 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    요금은 조례 별표2의 급지별 요금표(1~4급지)를 쓰고, 주차장별 요금·월 정기권·면수는 안산도시공사
    상세 팝업(2026-11-17 조회)의 등록값을 우선한다. 표준데이터의 등록값이 조례표와 다르면
    품질 리포트 ‘등록값_차이’에 남기고 조례표(또는 상세 팝업 값)를 적용한다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == ANSAN_PROVIDER]
    rows_corp = [r for r in rows_all if (r.get("제공기관명") or "").strip() == ANSAN_CORP_PROVIDER]
    corp_list = load_ansan_corp_list()
    portal = load_ansan_portal()
    chosen, dropped = ansan_rows_merge(rows_city, rows_corp)
    lots, excluded = [], []
    card_no = street_no = 0
    fee_counts = Counter()

    for item in sorted(chosen, key=lambda c: (c["row"].get("주차장명") or "")):
        r = item["row"]
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
        elif lat is not None and not (ANSAN_BBOX[0] <= lat <= ANSAN_BBOX[1]
                                     and ANSAN_BBOX[2] <= lng <= ANSAN_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        ref = ansan_portal_match(name, portal, corp_list) or {}
        crow = ansan_corp_match(name, addr, corp_list)
        dong = ansan_dong_of(jibun) or ansan_dong_of(road)
        dong_src = "지번주소"
        if not dong:
            dong = ansan_dong_of((ref or {}).get("addr") or (crow or {}).get("addr") or "")
            dong_src = "홈페이지주소"
        if not dong:
            dong_src = "없음"
        gu = ansan_gu_of(dong)

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
        facility = ptype == "부설"
        if street:
            street_no += 1
            lot_id = f"as-street-{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"as-{card_no:03d}"

        # 급지는 홈페이지 표(공영유료주차장 현황) → 표준데이터 급지구분 → 1급지 순으로 정한다.
        grade = (crow or {}).get("grade") or (std_grade if std_grade in ANSAN_FEES else 1)
        if grade not in ANSAN_FEES:
            grade = 1
        ticket_only = name in ANSAN_TICKET_ONLY

        fee = {
            "type": "무료" if fee_raw == "무료" else ("유료" if fee_raw in ("유료", "혼합") else "미상"),
            "raw_type": fee_raw,
            "mixed": fee_raw == "혼합",
            "grade": grade,
            "std_grade": std_grade,
            "grades": (crow or {}).get("grades") or [grade],
            "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None, "steps": None,
            "free_min": 0, "cap_fee": None, "cap_src": None,
            "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": None, "monthly_night": None, "monthly_all": None,
            "pay": ref.get("pay") or (r.get("결제방법") or "").strip(),
            "basis": None,
            "category": None,
            "std": std_fee,
            "portal_free_now": False,
            "ticket_only": False,
        }
        notice = None

        if ticket_only:
            # 화물차 전용 차고지 — 시간제 요금 없이 월 정기권만 받는다.
            fee.update({"type": "미상", "ticket_only": True,
                        "monthly": ANSAN_TICKET_ONLY[name],
                        "basis": "정기권(월정기) 전용 — 화물차 전용 차고지"})
            notice = (f"화물차 전용 차고지입니다 — 월 정기권 {ANSAN_TICKET_ONLY[name]:,}원, "
                      "시간제 주차는 받지 않습니다")
        elif fee["type"] == "유료":
            table = ANSAN_FEES[grade]
            base_fee = ref.get("base_fee") or table["base_fee"]
            unit_min = table["unit_min"]
            unit_fee = ref.get("unit_fee") or table["unit_fee"]
            day = ref.get("day") or table["day"]
            monthly = ref.get("monthly") or table["monthly"]
            fee.update({
                "base_min": table["base_min"], "base_fee": base_fee,
                "unit_min": unit_min, "unit_fee": unit_fee,
                "daily_fee": day, "cap_src": "조례 1일 주차요금",
                "monthly": monthly,
                "category": "facility" if facility else f"{'street' if street else 'off'}{grade}",
            })
            fee["basis"] = (f"「안산시 주차장 조례」 별표2 {grade}급지"
                            + (" · 안산도시공사 상세 안내(2026-11-17 확인)" if ref else ""))
            # 주차장별 예외 — 부설·수암봉·환승주차장
            if name == "시청부설주차장":
                fee.update({"base_min": 30, "base_fee": 500, "unit_min": 30, "unit_fee": 500,
                            "free_min": 20, "daily_fee": None, "cap_fee": None,
                            "monthly": std_fee["monthly"] or 10_000, "category": "facility",
                            "daily_hours": None})
                fee["basis"] = "안산도시공사 부설주차장 안내(시청) — 30분당 500원"
                notice = ("입차 후 20분 이내 또는 민원확인증을 받고 1시간 이내 출차하면 무료입니다"
                          " (민원확인증으로 1시간 무료, 초과분은 매 30분당 500원)")
            elif name == "와~스타디움부설주차장":
                fee.update({"base_min": 180, "base_fee": 0, "free_min": 180, "unit_min": 10,
                            "unit_fee": 300, "daily_fee": 9_000, "cap_fee": 9_000,
                            "monthly": 10_000, "category": "facility"})
                fee["basis"] = "안산도시공사 체육시설 부설주차장 안내 — 최초 3시간 무료, 이후 1급지 요금"
                notice = "최초 3시간은 무료이고, 3시간이 지나면 10분당 300원(1급지 요금)이 붙습니다"
            elif name == "차량등록사업소부설주차장":
                fee.update({"base_min": 30, "base_fee": 500, "unit_min": 30, "unit_fee": 500,
                            "daily_fee": None, "cap_fee": None,
                            "monthly": std_fee["monthly"] or 10_000, "category": "facility"})
                fee["basis"] = "안산도시공사 부설주차장 안내 — 30분당 500원"
            elif name == "외국인본부부설주차장":
                fee.update({"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 200,
                            "daily_fee": 4_500, "cap_fee": 4_500, "monthly": 40_000,
                            "category": "facility"})
                notice = "월 정기권(40,000원)은 상주 직원 대상입니다"
            elif name == "수암봉":
                fee.update({
                    "base_min": 30, "base_fee": 400, "unit_min": 10,
                    "steps": [{"until": 120, "unit_min": 10, "unit_fee": 200},
                              {"until": None, "unit_min": 10, "unit_fee": 300}],
                    "steps_label": "2시간까지 2급지 · 이후 1급지",
                    "daily_fee": None, "cap_fee": None, "monthly": std_fee["monthly"] or 90_000,
                    "category": None, "grade": 2,
                })
                fee["basis"] = "안산도시공사 요금 안내(수암봉) — 2시간까지 2급지, 이후 1급지"
                notice = ("평일에는 유료 운영을 하지 않습니다(안산시 안내로는 평일 무료 개방). "
                          "주말·공휴일 09시~20시(4~9월)·09시~18시(10~3월)만 유료입니다")
                # 주말·공휴일만 운영 — 등록값(평일 00:00~00:00, 공휴일 00:00~23:59) 대신 실제 운영시간으로 적는다.
                for k in ("weekday",):
                    win[k] = {"open": False, "start": 0, "end": 0, "24h": False, "listed": False,
                              "raw": ["-", "-"]}
                for k in ("sat", "sun"):
                    win[k] = {"open": True, "start": 540, "end": 1200, "24h": False, "listed": True,
                              "raw": ["09:00", "20:00"], "seasonal": True}
                oper = {"weekday": False, "sat": True, "sun": True}
            if ref.get("transfer") and name != "수암봉":
                notice = ANSAN_TRANSFER_NOTE
            elif name in ("선부광장", "선부우체국앞"):
                notice = "수~일요일만 운영합니다(월·화요일 휴무)"
            elif name == "초지동 화물전용":
                notice = ("화물차 전용 주차장입니다 — 2.5톤 이상~4톤 미만 30분 600원·10분당 400원·1일 9,000원, "
                          "4톤 이상 30분 900원·10분당 600원·1일 13,500원")
                # 표준데이터는 00:00~23:59(24시간)로 등록되어 있으나, 도시공사 홈페이지 운영시간은
                # 평일 09~18시·토 09~14시다(화물차 전용이라 주말 오후·공휴일은 운영하지 않는다).
                win["weekday"] = {"open": True, "start": 540, "end": 1080, "24h": False,
                                  "listed": True, "raw": ["09:00", "18:00"]}
                win["sat"] = {"open": True, "start": 540, "end": 840, "24h": False,
                              "listed": True, "raw": ["09:00", "14:00"]}
                win["sun"] = {"open": False, "start": 0, "end": 0, "24h": False, "listed": False,
                              "raw": ["-", "-"]}
                oper = {"weekday": True, "sat": True, "sun": False}

            # 등록값(표준데이터)이 조례표·상세 팝업과 다른 주차장 — 품질 리포트에 남긴다.
            reg = std_fee
            if (reg["base_fee"] or reg["unit_fee"]) and name != "수암봉":
                applied = (fee["base_min"], fee["base_fee"], fee["unit_min"], fee["unit_fee"])
                if reg["base_fee"] is not None and \
                        (reg["base_min"], reg["base_fee"], reg["unit_min"], reg["unit_fee"]) != applied:
                    fee["std_diff"] = (f"등록값 {reg['base_min'] or 0}분 {reg['base_fee'] or 0}원·"
                                       f"{reg['unit_min'] or 0}분당 {reg['unit_fee'] or 0}원 → 적용 "
                                       f"{applied[0]}분 {applied[1]}원·{applied[2]}분당 {applied[3]}원")
            fee_counts[f"{'street' if street else ('facility' if facility else 'off')}{grade}"] += 1
        if fee["type"] == "무료":
            free_days = {"sat": True, "sun": True}
            # 무료로 등록된 주차장은 평일·토요일 00:00~24:00에 공휴일 칸도 24시간이다.
            #   (구청 부설처럼 평일만 여는 곳은 등록된 운영요일을 그대로 둔다)
            if all(win[k]["open"] and win[k]["24h"] for k in ("weekday", "sat", "sun")) or \
                    win["weekday"]["24h"]:
                for k in ("weekday", "sat", "sun"):
                    win[k] = {"open": True, "start": 0, "end": 1440, "24h": True,
                              "listed": True, "raw": ["00:00", "24:00"]}
                oper = {"weekday": True, "sat": True, "sun": True}

        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip(),
            "src": f"표준데이터({item['src']})",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip(),
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": (ref or {}).get("name") or (crow or {}).get("name"),
            "realtime": None,
            "udc_id": None,
            "price_key": fee["base_fee"] if fee["base_fee"] else (fee["unit_fee"] or None),
            "city": "안산시",
            "city_slug": "ansan",
        })

    order = {g: i for i, (g, _) in enumerate(ANSAN_DISTRICTS)}
    lots.sort(key=lambda l: (order.get(l["gu"], 9), l["list_mode"] != "card",
                             l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"as-{i:03d}" if l["list_mode"] == "card" else f"as-s{i:03d}"

    quality = check_quality_ansan(rows_all, rows_city, rows_corp, lots, excluded, portal, corp_list, dropped)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(ANSAN_PORTAL_JSON).strftime("%Y-%m-%d %H:%M")
                            if ANSAN_PORTAL_JSON.exists() else None,
            "region": {"province": "경기도", "city": "안산시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-09-15", "rows_total": len(rows_all),
                    "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("안산시가 등록한 153행(제공기관명 '경기도 안산시')과 안산도시공사가 등록한 75행"
                             "(제공기관명 '안산도시공사')을 함께 읽었다. 유료 주차장은 도시공사 행을 기준으로 "
                             "삼고 시 행과 겹치는 50행은 중복으로 뺐다(quality.중복제거_행 참고)."),
                },
                {
                    "id": "auc", "name": "안산도시공사 공영유료주차장 시설현황·상세 안내",
                    "org": "안산도시공사",
                    "url": ANSAN_CORP_PAGE_URL,
                    "file": ANSAN_CORP_JSON.name,
                    "sha256": sha256(ANSAN_CORP_JSON) if ANSAN_CORP_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(corp_list),
                    "fetched_at": _snapshot_time(ANSAN_CORP_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if ANSAN_CORP_JSON.exists() else None,
                    "note": ("공영유료주차장 74곳의 권역·급지·주차면수·요일별 운영시간 확인용."),
                },
                {
                    "id": "auc_pop", "name": "안산도시공사 주차장 세부내역(상세 팝업)",
                    "org": "안산도시공사",
                    "url": "https://www.ansanuc.net/home/parking/parkinglotPopup.do",
                    "file": ANSAN_PORTAL_JSON.name,
                    "sha256": sha256(ANSAN_PORTAL_JSON) if ANSAN_PORTAL_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(portal),
                    "fetched_at": _snapshot_time(ANSAN_PORTAL_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if ANSAN_PORTAL_JSON.exists() else None,
                    "note": ("주차장별 30분 기본요금·10분당 가산·1일 주차요금·월 정기권·결제방법·"
                             "환승할인 대상 확인용(2026-11-17 09:10 조회)."),
                },
                {
                    "id": "ordinance", "name": "안산시 주차장 조례 (별표2 공영유료주차장 주차요금표)",
                    "org": "안산시",
                    "url": ANSAN_ORDINANCE_URL,
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "2026-04-29 개정·시행(경기도안산시조례 제3098호)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("1~4급지별 30분 기본요금·10분당 가산요금·1일 주차요금·월 정기권 근거. "
                             "요금 감면은 조례와 안산시 ‘주차요금 할인 안내’를 함께 확인."),
                },
                {
                    "id": "ansan", "name": "안산시 공영유료주차장 요금표·현황·할인 안내",
                    "org": "안산시청 교통정책과",
                    "url": ANSAN_PAGE_URL,
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2025-12 (공영유료주차장 현황)", "rows_total": 74,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("공영유료주차장 74곳의 급지·면수·운영시간과 감면 5단계(전액·3시간·2시간·1시간 면제 후 "
                             "50%·50%) 확인용. 지하철 환승 주차장은 이용 여부에 따라 2급지/3급지가 적용된다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in ANSAN_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "ansan_grade",
            "unit_min": ANSAN_UNIT_MIN,
            "applies": "2026-04-29 개정 조례",
            "rows": [{"grade": g, **t, "lots": quality["급지별"].get(g, 0)}
                     for g, t in sorted(ANSAN_FEES.items())],
            "transfer": {"from": 2, "to": 3, "base_fee": 300, "unit_fee": 200},
            "facility": {"city_hall": 500, "city_hall_free_min": 20, "stadium_free_min": 180,
                         "stadium_unit_fee": 300, "stadium_day": 9_000, "monthly": 10_000},
            "freight": [{"ton": "2.5톤 미만", "base_fee": 300, "unit_fee": 200, "day": 4_500, "monthly": 70_000},
                        {"ton": "2.5톤 이상~4톤 미만", "base_fee": 600, "unit_fee": 400, "day": 9_000, "monthly": 80_000},
                        {"ton": "4톤 이상", "base_fee": 900, "unit_fee": 600, "day": 13_500, "monthly": 90_000}],
            "basis": ("「안산시 주차장 조례」 별표2(2026-04-29 개정·시행) · 안산시 공영유료주차장 요금표 · "
                      "안산도시공사 시설현황·요금안내(2026-11-17 확인)"),
        },
    }
    payload.update(CITY_META["안산시"] | {
        "city": "안산시",
        "weekend_free_pages": False,     # 주말 무료 개방 '표기'가 없어 주말 무료 페이지를 만들지 않는다
        "discounts": ANSAN_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "ansan_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def _ansan_lot_pool(lots) -> dict:
    """이름 비교용 카드 목록 — 별칭(홈페이지 이름)도 함께 넣어 ‘홈페이지에만 있는 주차장’을 가려낸다."""
    pool = {l["name"]: l for l in lots}
    for l in lots:
        alias = ANSAN_NAME_ALIAS.get(l["name"])
        if alias:
            pool.setdefault(alias, l)
    return pool


def check_quality_ansan(std_all, rows_city, rows_corp, lots, excluded, portal, corp_list, dropped):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(f'{l["gu"]} {l["dong"] or "동 미상"}' for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["base_fee"] for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    matched = [l for l in lots if l.get("portal_name")]
    grade_mismatch = []
    for l in lots:
        stdg = l["fee"].get("std_grade")
        if l["fee"]["type"] == "유료" and stdg and stdg in ANSAN_FEES and stdg != l["fee"]["grade"]:
            grade_mismatch.append(f'{l["name"]}: 등록 급지 {stdg} → 적용 {l["fee"]["grade"]}급지')
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows_city) + len(rows_corp),
        "원자료_안산시행수": len(rows_city),
        "원자료_도시공사행수": len(rows_corp),
        "중복제거_행수": len(dropped),
        "중복제거_행": dropped,
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
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots if l["fee"]["type"] == "유료")),
        "등록값_차이": [f'{l["name"]}: {l["fee"]["std_diff"]}' for l in lots if l["fee"].get("std_diff")],
        "급지_차이": grade_mismatch,
        "홈페이지_목록수": len(corp_list),
        "포털_목록수": len(portal),
        "포털_매칭": len(matched),
        "포털_미매칭": [l["name"] for l in lots if not l.get("portal_name")],
        # 안산도시공사 홈페이지(표·상세)에만 있고 표준데이터에는 없는 주차장 — 카드로 만들지 않았다.
        #   이름이 괄호·꾸밈말만 다른 곳((대,소)·부설 등)은 이미 카드가 있으므로 이름 비교로 걸러낸다.
        "포털에만_있음": sorted(n for n in ({r["name"] for r in corp_list} | set(portal))
                              if not ansan_name_pick(n, _ansan_lot_pool(lots))),
        "구획수_차이": [f'{l["name"]}: 등록 {l["spaces"]}면 ↔ 홈페이지 {portal[l["portal_name"]]["spaces"]}면'
                       for l in matched
                       if portal.get(l["portal_name"], {}).get("spaces") and
                       portal[l["portal_name"]]["spaces"] != l["spaces"]],
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
        "정기권전용": [l["name"] for l in lots if l["fee"].get("ticket_only")],
    }


# ---------------------------------------------------------------- 시흥시 (T-03 Phase 10)
SIHEUNG_PROVIDER = "경기도 시흥시"
# 시흥시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고 그 아래 동 페이지를 둔다.
SIHEUNG_DISTRICTS = [("시흥시", "siheung")]
SIHEUNG_BBOX = (37.28, 37.48, 126.60, 126.92)      # 시흥시 대략 경계(좌표 점검용)
# 시흥시 법정동(2026-11 기준 28개) — 표준데이터 지번주소에서 동을 뽑는 데 쓴다.
SIHEUNG_DONGS = ("거모동", "군자동", "논곡동", "능곡동", "대야동", "도창동", "매화동", "목감동",
                 "미산동", "방산동", "배곧동", "산현동", "신천동", "안현동", "월곶동", "은행동",
                 "장곡동", "장현동", "정왕동", "조남동", "죽률동", "포동", "하상동", "하중동",
                 "광석동", "계수동", "물왕동", "화정동")
SIHEUNG_LIST_JSON = RAW / "siheung.go.kr_주차시설현황_20261117.json"
SIHEUNG_PORTAL_TXT = RAW / "parking.shsi.or.kr_주차요금체계_20261117.txt"
SIHEUNG_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2128143"
SIHEUNG_PAGE_URL = "https://www.siheung.go.kr/portal/parkinglotState/list.do?mId=0517010300"
SIHEUNG_PORTAL_URL = "https://parking.shsi.or.kr/main/mainPage.do"
SIHEUNG_ANNEX_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2076383"

# 시흥시 공영주차장 요금 — 「시흥시 주차장 설치 및 관리 조례」 별표1(시행 2026-05-07, 경기도시흥시조례 제2621호)과
# 시흥시 ‘주차시설현황’ 요금표·시흥공영주차 포털 ‘주차장 요금체계’(2026-11-17 확인)를 그대로 옮겼다.
#   · 2시간 이내는 최초 30분 기본요금 뒤 10분마다 가산하고, 2시간을 넘기면 10분당 요율이 올라간다.
#   · 노외 1급지 800·300·400(2시간 초과)·1일 8,000 / 2급지 500·200·300·5,000 / 3급지 300·100·200·3,000
#   · 노상은 1일 주차요금이 없다(시간제만). 노상 1급지 800·300·400 / 2급지 500·200·300 / 3급지 300·100·200
#   · 월 정기권(주간) 70,000·50,000·30,000원, 야간 50,000·30,000·20,000원
#   · 공공청사 부설주차장은 최초 30분 500원·10분당 100원·1일 3,000원·월 10,000원(별도 조례)
SIHEUNG_FEES = {
    "off": {
        1: {"base_min": 30, "base_fee": 800, "unit_min": 10, "unit_fee": 300, "over_fee": 400,
            "day": 8_000, "night": 5_000, "month_day": 70_000, "month_night": 50_000},
        2: {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 200, "over_fee": 300,
            "day": 5_000, "night": 3_000, "month_day": 50_000, "month_night": 30_000},
        3: {"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 100, "over_fee": 200,
            "day": 3_000, "night": 2_000, "month_day": 30_000, "month_night": 20_000},
    },
    "street": {
        1: {"base_min": 30, "base_fee": 800, "unit_min": 10, "unit_fee": 300, "over_fee": 400,
            "month_day": 70_000, "month_night": 50_000},
        2: {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 200, "over_fee": 300,
            "month_day": 50_000, "month_night": 30_000},
        3: {"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 100, "over_fee": 200,
            "month_day": 30_000, "month_night": 20_000},
    },
}
SIHEUNG_OVER_MIN = 120        # 2시간을 넘기면 10분당 요율이 올라간다
SIHEUNG_ANNEX = {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 100,
                 "day": 3_000, "month_day": 10_000}
# 「시흥시 주차장 설치 및 관리 조례」 제6조(감면)·제5조의2(면제)와 시흥공영주차 포털 감면·면제 기준(2026-11-17 확인).
#   · 100%              : 긴급자동차·공무수행 관용차, 국가유공자·독립유공자·참전유공자·고엽제·5·18·특수임무유공자·
#                         의사상자·국군포로, 심한 장애인, 모범·유공·성실납세자
#   · 2시간 면제 후 50% : 심하지 않은 장애인, 성실·모범·유공납세자 스티커, 자원봉사자, 다자녀(경기I-PLUS),
#                         장기·인체조직 기증자, 헌혈자 (전기·환경친화 자동차는 2시간 무료 후 60%)
#   · 60%               : 경형자동차(1,000cc 미만), 저공해자동차, 환경친화적 자동차
#   · 50%               : 전통시장 이용차량, 병역명문가
#   · 30%               : 승용차요일제 참여차량
#   · 20%               : 자가용 10부제·승용차 함께타기 등 시책 참여차량
#   · 감면·할인은 할인율이 가장 높은 1개만 적용하고, 100원 미만은 버린다.
SIHEUNG_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "전통시장·병역명문가 50%", "rate": 0.5, "exempt_min": 0,
     "note": "전통시장 이용차량·병역명문가 예우대상자 차량"},
    {"label": "경차·저공해·환경친화 60%", "rate": 0.6, "exempt_min": 0,
     "note": "경형(1,000cc 미만)·저공해 표지·환경친화적 자동차 표지 부착 차량"},
    {"label": "전기차 2시간 면제 후 60%", "rate": 0.6, "exempt_min": 120,
     "note": "전기자동차, 최초 2시간 면제"},
    {"label": "장애인·다자녀 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "심하지 않은 장애인·성실납세자·자원봉사자·다자녀(경기I-PLUS)·장기기증자·헌혈자, 최초 2시간 면제"},
    {"label": "승용차요일제 30%", "rate": 0.3, "exempt_min": 0,
     "note": "승용차요일제 전자태그 부착·운휴일 준수 차량"},
    {"label": "국가유공자·심한 장애인 100%", "rate": 1.0, "exempt_min": 0,
     "note": "국가유공자·독립·참전유공자·고엽제·5·18·특수임무유공자·의사상자·국군포로, 심한 장애인, 모범·유공납세자"},
]
# 공휴일 무료 개방에서 빠지는 주차장 — 명절 연휴에만 무료로 개방한다(시흥공영주차 포털 안내).
#   · 표준데이터 이름 그대로 적는다: 오이도·삼미시장·신천천·월곶(노상), 배다리 선착장(노외).
#     ‘오이도역’은 예외 대상이 아니므로 이름이 정확히 같은 것만 해당시킨다.
SIHEUNG_HOLIDAY_EXCEPT = ("오이도", "삼미시장", "신천천", "월곶", "배다리 선착장",
                          "조가비광장", "갯골생태공원")
SIHEUNG_HOLIDAY_NOTE = ("이 주차장은 공휴일 무료 개방 대상에서 빠져 명절 연휴에만 무료로 개방합니다"
                        " — 일요일·공휴일에도 요금이 붙을 수 있으니 현장 표지를 확인하세요")
SIHEUNG_CITY_HALL_NOTE = ("시흥시 등록 현황은 무료 개방으로 표시되어 있으나, 「시흥시청과 그 소속기관 등의 부설주차장 운영 조례」"
                          "(2026-01-01 시행)는 평일 08:00~20:00에 30분 500원·10분당 100원·1일 3,000원을 받을 수 있게 합니다")


def siheung_dong_of(text: str):
    """주소에서 시흥시 법정동을 뽑는다(‘은행동672-7’처럼 번지가 붙은 표기도 인정)."""
    t = re.sub(r"\s", "", text or "")
    for d in sorted(SIHEUNG_DONGS, key=len, reverse=True):
        if re.search(re.escape(d) + r"(?=$|\d|산\d|[^가-힣])", t):
            return d
    return None


def siheung_addr_jibun(addr: str) -> str:
    """지번주소 비교용 — 공백·‘경기도 시흥시’·괄호·‘일원/H’ 꼬리표를 빼고 동+번지로 맞춘다."""
    t = re.sub(r"\s", "", addr or "").replace("경기도시흥시", "")
    t = re.sub(r"\([^)]*\)", "", t)
    return re.sub(r"(일원|外?H|외\d+필지)$", "", t)


def siheung_name_key(s: str) -> str:
    """주차장 이름 비교용 키 — 괄호·공백·‘주차장/노외/공영’을 뺀다."""
    t = re.sub(r"['\"\s\[\]·,.ㆍ~-]", "", s or "")
    t = re.sub(r"\([^)]*\)", "", t)
    for w in ("주차장", "공영주차장", "노외", "공영"):
        t = t.replace(w, "")
    return t


def load_siheung_list() -> list:
    """시흥시 ‘주차시설현황’ 목록 스냅샷 → 주차장별 유형·동·급지·면수(교차 확인용)."""
    if not SIHEUNG_LIST_JSON.exists():
        return []
    raw = json.loads(SIHEUNG_LIST_JSON.read_text())
    return raw.get("rows", [])


def siheung_list_match(name: str, addr: str, pool: list):
    """표준데이터 한 행에 대응하는 시 현황표 행을 정한다(같은 지번 → 이름 키).

    ‘나눔 제27~47호’처럼 두 자료의 번호가 하나씩 어긋난 주차장이 있어, 이름보다 같은 지번을
    먼저 본다(조남동 745 · 28면 = 표준데이터 나눔제28호 ↔ 시 현황 나눔 제27호).
    """
    if not pool:
        return None
    jib = siheung_addr_jibun(addr)
    if jib:
        near = [r for r in pool if siheung_addr_jibun(r["addr"]) == jib]
        if len(near) == 1:
            return near[0]
    key = siheung_name_key(name)
    hit = [r for r in pool if key and siheung_name_key(r["name"]) == key]
    if len(hit) == 1:
        return hit[0]
    if hit:
        return hit[0]
    return None


def siheung_rows_dedupe(rows):
    """같은 주차장이 무료·유료 두 줄로 등록된 행을 하나로 줄인다.

    시흥시 표준데이터에는 같은 지번에 이름만 다른 줄이 2쌍 있고(조남동 664 · 정왕동 1622),
    시 현황표에는 유료 쪽 이름만 남아 있다. 유료(요금이 채워진) 줄을 남기고 무료 중복 줄을 뺀다.
    """
    kept, dropped = [], []
    for r in rows:
        jib = siheung_addr_jibun(r.get("소재지지번주소"))
        dup = next((k for k in kept if jib and siheung_addr_jibun(k.get("소재지지번주소")) == jib), None) if jib else None
        if dup is None:
            kept.append(r)
            continue
        a, b = dup, r
        paid_a = (a.get("요금정보") or "").strip() == "유료"
        paid_b = (b.get("요금정보") or "").strip() == "유료"
        if paid_b and not paid_a:
            kept[kept.index(a)] = b
            dropped.append({"name": a.get("주차장명"), "addr": a.get("소재지지번주소"),
                            "kept": b.get("주차장명"), "why": "같은 지번·무료 중복행"})
        elif not paid_a and not paid_b:
            # 둘 다 무료면 나중에 등록된 이름(시 현황표에 남아 있는 이름)을 남긴다.
            kept[kept.index(a)] = b
            dropped.append({"name": a.get("주차장명"), "addr": a.get("소재지지번주소"),
                            "kept": b.get("주차장명"), "why": "같은 지번·무료 중복행"})
        else:
            dropped.append({"name": b.get("주차장명"), "addr": b.get("소재지지번주소"),
                            "kept": a.get("주차장명"), "why": "같은 지번·무료 중복행"})
    return kept, dropped


def build_siheung():
    """시흥시 공영주차장을 표준데이터 + 시흥시 주차시설현황으로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 시흥시 범위를 벗어난 행은 제외(껍데기 행).
      · 시흥시는 자치구가 없어 구 대신 법정동으로 묶고, 시 페이지가 계산기·목록 페이지를 겸한다.
      · 노상(거리) 구간은 이름이 구간 설명이라 카드 대신 전용 표 페이지로 분리(list_mode='street').
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    요금은 조례 별표1의 노외·노상 1~3급지 요금표를 쓰고, 급지·면수는 시흥시 주차시설현황(2026-11-17 조회)과
    교차 확인한다. 표준데이터 등록값이 조례표와 다르면 품질 리포트 ‘등록값_차이’에 남기고 조례표를 적용한다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == SIHEUNG_PROVIDER]
    chosen, dropped = siheung_rows_dedupe(rows_city)
    city_list = load_siheung_list()
    lots, excluded = [], []
    card_no = street_no = 0
    fee_counts = Counter()
    grade_diff, space_diff, list_matched = [], [], 0

    for r in sorted(chosen, key=lambda r: (r.get("주차장명") or "")):
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
        elif lat is not None and not (SIHEUNG_BBOX[0] <= lat <= SIHEUNG_BBOX[1]
                                      and SIHEUNG_BBOX[2] <= lng <= SIHEUNG_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        ref = siheung_list_match(name, addr, city_list)
        if ref:
            list_matched += 1
        dong = siheung_dong_of(jibun) or siheung_dong_of(road)
        dong_src = "지번주소"
        if not dong:
            dong = siheung_dong_of(ref["addr"] if ref else "")
            dong_src = "시현황주소"
        if not dong:
            dong_src = "없음"
        gu = SIHEUNG_DISTRICTS[0][0]

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
            lot_id = f"sh-s{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"sh-{card_no:03d}"

        # 급지는 시 현황표 → 표준데이터 급지구분 → 2급지 순으로 정한다(무료 주차장은 급지가 없다).
        grade = (ref or {}).get("grade") or (std_grade if std_grade in (1, 2, 3) else None)
        if fee_raw == "유료" and grade is None:
            grade = 2
        if ref and ref.get("grade") and std_grade in (1, 2, 3) and ref["grade"] != std_grade:
            grade_diff.append(f"{name}: 표준데이터 {std_grade}급지 ↔ 시 현황 {ref['grade']}급지")
        if ref and ref.get("spaces") and ref["spaces"] != spaces:
            space_diff.append(f"{name}: 등록 {spaces}면 ↔ 시 현황 {ref['spaces']}면")

        category = "facility" if ptype == "부설" else ("street" if street else "off")
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
            "monthly": None, "monthly_night": None, "monthly_all": None,
            "pay": (r.get("결제방법") or "").strip(),
            "basis": None,
            "category": category if fee_raw == "유료" else None,
            "std": std_fee,
            "portal_free_now": False,
        }
        notice = None

        if fee["type"] == "유료":
            kind = "street" if street else "off"
            table = SIHEUNG_FEES[kind][grade]
            fee.update({
                "base_min": table["base_min"], "base_fee": table["base_fee"],
                "unit_min": table["unit_min"], "unit_fee": table["unit_fee"],
                "steps": [{"until": SIHEUNG_OVER_MIN, "unit_min": table["unit_min"],
                           "unit_fee": table["unit_fee"]},
                          {"until": None, "unit_min": table["unit_min"],
                           "unit_fee": table["over_fee"]}],
                "steps_label": f"2시간까지 {table['unit_fee']:,}원 · 2시간 초과 {table['over_fee']:,}원",
                "monthly": std_fee["monthly"] or table["month_day"],
                "monthly_night": table["month_night"],
                "daily_hours": 12,
            })
            if kind == "off":
                fee.update({"daily_fee": table["day"], "cap_src": "조례 1일 주차요금"})
            fee["basis"] = (f"「시흥시 주차장 설치 및 관리 조례」 별표1 {grade}급지"
                            f"({'노상' if street else '노외'})") if std_grade in (1, 2, 3) else \
                           f"「시흥시 주차장 설치 및 관리 조례」 별표1 {grade}급지"
            # 등록값(표준데이터)이 조례표와 다른 주차장 — 품질 리포트에 남긴다.
            if std_fee["base_fee"]:
                applied = (fee["base_min"], fee["base_fee"], fee["unit_min"], fee["unit_fee"])
                if (std_fee["base_min"], std_fee["base_fee"], std_fee["unit_min"],
                        std_fee["unit_fee"]) != applied:
                    fee["std_diff"] = (f"등록값 {std_fee['base_min'] or 0}분 {std_fee['base_fee'] or 0}원·"
                                       f"{std_fee['unit_min'] or 0}분당 {std_fee['unit_fee'] or 0}원 → 적용 "
                                       f"{applied[0]}분 {applied[1]}원·{applied[2]}분당 {applied[3]}원")
            fee_counts[f"{kind}{grade}"] += 1
            # 일요일·공휴일 무료 개방 — 공휴일 무료 개방에서 빠지는 주차장은 요금이 붙는다.
            if name not in SIHEUNG_HOLIDAY_EXCEPT:
                free_days["sun"] = True
            else:
                notice = SIHEUNG_HOLIDAY_NOTE
        if fee["type"] == "무료":
            free_days = {"sat": True, "sun": True}
            if all(win[k]["open"] and win[k]["24h"] for k in ("weekday", "sat", "sun")) or \
                    win["weekday"]["24h"]:
                for k in ("weekday", "sat", "sun"):
                    win[k] = {"open": True, "start": 0, "end": 1440, "24h": True,
                              "listed": True, "raw": ["00:00", "24:00"]}
                oper = {"weekday": True, "sat": True, "sun": True}
        if ptype == "부설" and name.startswith("시청"):
            notice = SIHEUNG_CITY_HALL_NOTE if not notice else notice + " / " + SIHEUNG_CITY_HALL_NOTE

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
            "road": None,
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip(),
            "note": note,
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": ref["name"] if ref else None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["base_fee"] if fee["base_fee"] else (fee["unit_fee"] or None),
            "city": "시흥시",
            "city_slug": "siheung",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"sh-{i:03d}" if l["list_mode"] == "card" else f"sh-s{i:03d}"

    quality = check_quality_siheung(rows_all, rows_city, lots, excluded, dropped, city_list,
                                    list_matched, grade_diff, space_diff)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(SIHEUNG_LIST_JSON).strftime("%Y-%m-%d %H:%M")
                            if SIHEUNG_LIST_JSON.exists() else None,
            "region": {"province": "경기도", "city": "시흥시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-14", "rows_total": len(rows_all),
                    "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("시흥시가 등록한 199행(제공기관명 '경기도 시흥시')을 읽었다. 노외 168행·노상 30행·"
                             "부설 1행이며, 같은 지번에 무료·유료로 두 번 등록된 2쌍은 유료 행만 남겼다"
                             "(quality.중복제거_행 참고)."),
                },
                {
                    "id": "siheung", "name": "시흥시 주차시설현황(공영주차장 요금표·현황 목록)",
                    "org": "시흥시청 교통행정과",
                    "url": SIHEUNG_PAGE_URL,
                    "file": SIHEUNG_LIST_JSON.name,
                    "sha256": sha256(SIHEUNG_LIST_JSON) if SIHEUNG_LIST_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": len(city_list),
                    "fetched_at": _snapshot_time(SIHEUNG_LIST_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if SIHEUNG_LIST_JSON.exists() else None,
                    "note": ("공영주차장 199곳(유료 노외 85·무료 노외 83·유료 노상 8·유료 부설 22·무료 노상 1)의 "
                             "급지·소재지·면수·면적 교차 확인용. 표준데이터와 급지·면수가 다른 곳은 quality에 남겼다."),
                },
                {
                    "id": "portal", "name": "시흥공영주차 포털 주차장 요금체계",
                    "org": "시흥도시공사",
                    "url": SIHEUNG_PORTAL_URL,
                    "file": SIHEUNG_PORTAL_TXT.name,
                    "sha256": sha256(SIHEUNG_PORTAL_TXT) if SIHEUNG_PORTAL_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": None,
                    "fetched_at": _snapshot_time(SIHEUNG_PORTAL_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if SIHEUNG_PORTAL_TXT.exists() else None,
                    "note": ("급지 구분 기준, 주·야간 시간 구분(상업지역 10~22시·그 밖 08~20시), "
                             "공휴일·평일 야간 무료 개방과 예외 7곳, 면제·감면 기준, 1구획 초과 차량 할증 확인용."),
                },
                {
                    "id": "ordinance", "name": "시흥시 주차장 설치 및 관리 조례 (별표1 공영주차장 주차요금)",
                    "org": "시흥시",
                    "url": SIHEUNG_ORDINANCE_URL,
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "2026-05-07 개정·시행(경기도시흥시조례 제2621호)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("노상·노외 1~3급지의 최초 30분·10분당·2시간 초과 10분당 요율, 1일 주차요금, "
                             "월 정기 주차요금 근거. 요금 감면은 제6조, 면제는 제5조의2."),
                },
                {
                    "id": "annex", "name": "시흥시청과 그 소속기관 등의 부설주차장 운영 조례",
                    "org": "시흥시",
                    "url": SIHEUNG_ANNEX_URL,
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "2025-10-02 공포·2026-01-01 시행(조례 제2530호)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("시청·소속기관 부설주차장의 운영시간(평일 08:00~20:00, 토요일·공휴일 제외)과 "
                             "요금(30분 500원·10분당 100원·1일 3,000원)·면제 기준 확인용."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in SIHEUNG_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "siheung_dual",
            "unit_min": 10,
            "over_min": SIHEUNG_OVER_MIN,
            "applies": "2026-05-07 개정 조례",
            "off": [{"grade": g, **t, "lots": quality["급지별"].get(g, 0)} for g, t in sorted(SIHEUNG_FEES["off"].items())],
            "street": [{"grade": g, **t} for g, t in sorted(SIHEUNG_FEES["street"].items())],
            "facility": SIHEUNG_ANNEX,
            "holiday_except": list(SIHEUNG_HOLIDAY_EXCEPT),
            "basis": ("「시흥시 주차장 설치 및 관리 조례」 별표1(2026-05-07 개정·시행) · 시흥시 주차시설현황 요금표 · "
                      "시흥공영주차 포털 주차장 요금체계(2026-11-17 확인)"),
        },
    }
    payload.update(CITY_META["시흥시"] | {
        "city": "시흥시",
        "weekend_free_pages": False,     # 주말 무료 개방 ‘페이지’는 만들지 않는다(공휴일 무료 개방은 카드·계산기에 반영)
        "discounts": SIHEUNG_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "siheung_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_siheung(std_all, rows, lots, excluded, dropped, city_list,
                          list_matched, grade_diff, space_diff):
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
        "원자료_시흥시행수": len(rows),
        "중복제거_행수": len(dropped),
        "중복제거_행": dropped,
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(Counter(l["gu"] for l in card)),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "요금갈래": dict(Counter(l["fee"]["category"] for l in lots if l["fee"]["category"])),
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots if l["fee"]["type"] == "유료")),
        "등록값_차이": [f'{l["name"]}: {l["fee"]["std_diff"]}' for l in lots if l["fee"].get("std_diff")],
        "시현황_목록수": len(city_list),
        "시현황_매칭": list_matched,
        "급지_차이": grade_diff,
        "면수_차이": space_diff,
        "평균_기본요금": round(sum(paid) / len(paid)) if paid else None,
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "공휴일_무료제외": [l["name"] for l in lots
                            if l["fee"]["type"] == "유료" and l["name"] in SIHEUNG_HOLIDAY_EXCEPT],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in mgmt.items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots}),
    }


# ---------------------------------------------------------------- 의정부시 (T-03 Phase 11)
UIJEONGBU_PROVIDER = "경기도 의정부시"
# 의정부시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고 그 아래 동 페이지를 둔다.
UIJEONGBU_DISTRICTS = [("의정부시", "uijeongbu")]
UIJEONGBU_BBOX = (37.67, 37.79, 126.97, 127.16)     # 의정부시 대략 경계(좌표 점검용)
# 의정부시 법정동(2026-11 기준 14개) — 표준데이터 지번주소에서 동을 뽑는 데 쓴다.
#   송산1~3동은 행정동이고, 법정동은 민락동·낙양동·고산동 등으로 나뉜다.
UIJEONGBU_DONGS = ("의정부동", "가능동", "신곡동", "용현동", "호원동", "장암동", "금오동",
                   "녹양동", "자금동", "흥선동", "민락동", "낙양동", "고산동", "산곡동")
UIJEONGBU_LIST_JSON = RAW / "uiuc.or.kr_공영주차장현황_20261117.json"
UIJEONGBU_PORTAL_TXT = RAW / "uiuc.or.kr_공영주차장_요금감면_20261117.txt"
UIJEONGBU_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2107023"
UIJEONGBU_ANNEX_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2111261"
UIJEONGBU_PAGE_URL = "https://www.uiuc.or.kr/businessInfo/trafficPage/public/list.do"
UIJEONGBU_LIST_URL = "https://www.uiuc.or.kr/businessInfo/trafficPage/public/list3.do"

# 의정부시 공영주차장 요금 — 「의정부시 주차장 설치 및 관리 조례」 제3조제1항(별표1, 시행 2026-01-09,
# 경기도의정부조례 제3674호)과 의정부도시공사 ‘공영주차장’ 요금 안내(2026-11-17 확인)를 그대로 옮겼다.
#   · 기본시간 없이 1회 주차 10분당 요금이 바로 붙는다(1급지 300원, 2급지 200원, 3급지 150원).
#   · 노외는 1일 주차권(12시간)이 상한이고, 노상은 1일 주차요금이 따로 있다.
#   · 월 정기권은 노외만 주간·야간·전일로 나뉜다(전일 = 1급지 104,000원).
UIJEONGBU_FEES = {
    "off": {
        1: {"unit": 300, "day": 9_000, "month_day": 70_000, "month_night": 60_000, "month_all": 104_000},
        2: {"unit": 200, "day": 5_000, "month_day": 40_000, "month_night": 30_000, "month_all": 56_000},
        3: {"unit": 150, "day": 3_000, "month_day": 20_000, "month_night": 20_000, "month_all": 32_000},
    },
    "street": {
        1: {"unit": 300, "day": 8_000, "month": 80_000},
        2: {"unit": 200, "day": 6_000, "month": 60_000},
        3: {"unit": 150, "day": 4_000, "month": 40_000},
    },
}
UIJEONGBU_DAY_HOURS = 12       # 노외 1일 주차권은 12시간 기준
# 「의정부시 공공시설 부설주차장 운영 조례」 제9조제1항(별표3) 요금 — 의정부도시공사 부설주차장 안내표.
UIJEONGBU_FACILITY = {
    "의정부시청": {"free_min": 30, "unit": 300, "day": 7_000, "month": None},
    "정보도서관": {"free_min": 60, "unit": 300, "day": 7_000, "month": None},
    "과학도서관": {"free_min": 60, "unit": 300, "day": 7_000, "month": 40_000},
    "낙양동 물사랑공원": {"free_min": 30, "unit": 300, "day": 7_000, "month": 56_000},
    "직동 근린공원": {"free_min": 180, "unit": 200, "day": 5_000, "month": 56_000},
    "추동근린공원": {"free_min": 180, "unit": 200, "day": 5_000, "month": None},
    "송산사지 근린공원": {"free_min": 180, "unit": 200, "day": 5_000, "month": None},
}
# 캠핑카 전용 구역은 조례 급지 요금이 아니라 표준데이터에 등록된 요금을 쓴다
#   (민락2지구·추동 캠핑카: 10분 200원·1일 5,000원·월 84,000원).
UIJEONGBU_CAMP_FEE = {"unit": 200, "day": 5_000, "month": 84_000}
# 「의정부시 주차장 설치 및 관리 조례」 제3조제1항 감면표와 의정부도시공사 안내(2026-11-17 확인).
#   · 국가유공자        : 최초 5시간 전액 면제, 5시간 초과분 50%
#   · 다자녀가정·전기차  : 최초 2시간 면제, 이후 50%(전기차는 충전시설이 있는 공영주차장)
#   · 장애인·경차·저공해·환승·우수자원봉사자·병역명문가·교육차량 : 50%
#   · 모범·유공·성실납세자 : 주차요금 면제(발행일부터 1년)
#   · 감면이 겹치면 감면율이 높은 하나만 적용한다.
UIJEONGBU_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·장애인 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경차(1,000cc 미만)·저공해·장애인(표지+복지카드)·환승(30분 이내 결제)·우수자원봉사자·병역명문가·교육차량"},
    {"label": "다자녀·전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "두 자녀 이상(막내 만 18세 이하)·전기자동차(충전시설 설치 주차장), 최초 2시간 면제"},
    {"label": "국가유공자 5시간 면제 후 50%", "rate": 0.5, "exempt_min": 300,
     "note": "국가유공자증서 소지자, 최초 5시간 전액 면제"},
    {"label": "성실납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "국세청 모범납세자·경기도 유공납세자·의정부시 성실납세자(발행일부터 1년)"},
]
UIJEONGBU_FACILITY_NOTE = ("이 주차장은 「의정부시 공공시설 부설주차장 운영 조례」 제8조에 따라 유료 운영시간(별표 2) "
                           "외의 시간을 무료로 개방합니다 — 카드의 예상요금은 유료 운영시간 기준이고, "
                           "야간·휴일 개방 여부는 시설 안내를 확인하세요")
UIJEONGBU_CAMP_NOTE = ("캠핑카 전용 구역은 표준데이터 등록요금(10분 200원·1일 5,000원·월 84,000원)이 적용됩니다"
                       " — 일반 구획 요금과 다를 수 있으니 현장 표지를 확인하세요")
UIJEONGBU_BIG_NOTE = ("대형자동차 전용 주차장입니다 — 조례 별표1의 ‘대형 기준 요금의 2배’"
                       "(10분 400원·1일 10,000원)를 적용했습니다")
UIJEONGBU_NEW_LOT_NOTE = ("도시공사 공영주차장 현황(2026년 9월 기준)에는 없고 표준데이터(기준일 2026-07-15)에만 "
                          "등록된 주차장입니다 — 운영 여부를 도시공사에 확인하세요")

# 표준데이터(제공기관 '경기도 의정부시') 행 ↔ 도시공사 공영주차장 현황(2026년 9월) 행 짝.
#   · 좌표·운영시간·전화·관리번호는 표준데이터에서, 이름·유형·급지·면수는 도시공사 현황에서 가져온다.
#   · 도시공사 현황은 면수가 구획 구성(일반+장애인+경차+여성+전기차+대형+캠핑카)의 합과 일치하고,
#     표준데이터의 면수는 같은 지번에서 다른 값을 담은 행이 있어(가능동 일대) 현황표 값을 쓴다.
UIJEONGBU_STD_MAP = {
    1: ["207-2-000011"], 2: ["207-2-000012"], 3: ["207-2-000008"], 4: ["207-2-000005"],
    5: ["207-2-000006"], 6: ["207-2-000007"], 7: ["207-2-000010"], 8: ["207-2-000003"],
    9: ["207-2-000002"], 10: ["207-2-000001"], 11: ["207-2-000009"], 12: ["207-2-000004"],
    13: ["207-2-000026"], 14: ["207-2-000021"], 15: ["207-2-000022"], 16: ["207-2-000023"],
    17: ["207-2-000024"], 18: ["207-2-000025"], 19: ["207-2-000029"], 20: ["207-2-000041"],
    21: ["207-2-000038"], 23: ["207-2-000027"], 24: ["207-2-000031"], 25: ["207-2-000047"],
    26: ["207-2-000046"], 27: ["207-2-000033"], 28: ["207-2-000013"], 29: ["207-2-000040"],
    30: ["207-2-000044"], 31: ["207-2-000020"], 32: ["207-2-000018"], 33: ["207-2-000019"],
    34: ["207-2-000037"], 35: ["207-2-000017"], 36: ["207-2-000015"], 37: ["207-2-000016"],
    38: ["207-2-000028"],
    39: ["207-2-000030"], 40: ["207-2-000039"], 41: ["207-2-000048"], 42: ["207-2-000014"],
    43: ["207-2-000045"], 44: ["207-2-000042"], 45: ["207-2-000032"], 46: ["207-2-000034"],
    47: ["207-2-000050", "207-2-000051", "207-2-000052"], 48: ["207-2-000049"], 49: ["207-2-000036"],
    50: ["207-2-000035"], 51: ["207-2-000053"], 52: ["207-2-000054"], 53: ["207-2-000055"],
    54: ["207-2-000056"], 55: ["207-2-000057"], 56: ["207-2-000058"], 57: ["207-2-000059"],
    58: ["207-2-000060"], 59: ["207-2-000061"], 60: ["207-2-000062"], 61: ["207-2-000063"],
    62: ["207-2-000064"], 63: ["207-2-000065"], 64: ["207-2-000066"], 65: ["207-2-000067"],
    66: ["207-2-000068"], 67: ["207-2-000069"], 68: ["207-2-000070"], 69: ["207-2-000071"],
    70: ["207-2-000072"],
}
# 표준데이터 좌표가 다른 주차장과 겹쳐 지도 핀이 엉뚱한 곳에 찍히는 행은 좌표를 비운다.
#   · 용현동 제1공영(도 34번): 표준데이터 좌표가 호원동 한주3차아파트 앞과 같은 값이다.
UIJEONGBU_COORD_DROP = {34}
# 표준데이터에 없는 주차장(부설 10곳·고산지구 제3·용현동 제1공영)의 좌표는 카카오맵 지오코딩으로 채웠다.
#   · 주소만으로 찍은 좌표라 주차장 입구와 수십 미터 다를 수 있다(지도 링크용).
UIJEONGBU_GEOCODE_JSON = RAW / "uiuc.or.kr_지오코딩_20261117.json"


def uijeongbu_dong_of(text: str):
    """주소에서 의정부시 법정동을 뽑는다(‘가능동678’·‘의정부동 30-38’ 같은 표기도 인정)."""
    t = re.sub(r"\s", "", text or "")
    for d in sorted(UIJEONGBU_DONGS, key=len, reverse=True):
        if re.search(re.escape(d) + r"(?=$|\d|[^가-힣])", t):
            return d
    return None


def load_uijeongbu_geocode() -> dict:
    """부설·신설 주차장 좌표(카카오맵 지오코딩) → {주차장명: (위도, 경도)}."""
    if not UIJEONGBU_GEOCODE_JSON.exists():
        return {}
    rows = json.loads(UIJEONGBU_GEOCODE_JSON.read_text()).get("rows", [])
    return {r["name"]: (r["lat"], r["lng"]) for r in rows if r.get("lat") and r.get("lng")}


def load_uijeongbu_list() -> list:
    """의정부도시공사 공영주차장 현황(2026년 9월) → 주차장별 유형·급지·면수·구획 구성."""
    if not UIJEONGBU_LIST_JSON.exists():
        return []
    return json.loads(UIJEONGBU_LIST_JSON.read_text()).get("rows", [])


def uijeongbu_facility_fee(name: str):
    """부설주차장 이름 → 부설주차장 운영 조례 요금(가장 긴 이름이 먼저 맞도록 정렬해 본다)."""
    for key in sorted(UIJEONGBU_FACILITY, key=len, reverse=True):
        if key in name:
            return UIJEONGBU_FACILITY[key]
    return None


def build_uijeongbu():
    """의정부시 공영주차장을 도시공사 현황(2026년 9월) + 표준데이터로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 의정부시 범위를 벗어난 행은 제외(껍데기 행).
      · 의정부시는 자치구가 없어 구 대신 법정동으로 묶고, 시 페이지가 계산기·목록 페이지를 겸한다.
      · 노상(거리) 구간은 도시공사 현황의 ‘노상’ 13구간을 표 페이지로 분리(list_mode='street').
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    요금은 조례 별표1의 노외·노상 1~3급지 요금표(10분 단위)를 쓰고, 부설은 부설주차장 운영 조례 요금을 쓴다.
    면수·급지·유형은 도시공사 현황표(2026년 9월)를 따르고, 표준데이터와 다른 곳은 품질 리포트에 남긴다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == UIJEONGBU_PROVIDER]
    std_by_no = {(r_["주차장관리번호"] or "").strip(): r_ for r_ in rows_city}
    city_list = load_uijeongbu_list()
    geocode = load_uijeongbu_geocode()
    lots, excluded = [], []
    card_no = street_no = 0
    used_std, matched = set(), 0
    grade_diff, space_diff, name_diff, fee_diff = [], [], [], []
    capa_bad = []

    def fee_base(kind, grade, free_min=0, unit=None, day=None, month=None, month_night=None,
                 month_all=None, daily_hours=None):
        return {
            "type": "유료", "raw_type": "유료", "mixed": False, "grade": grade if kind != "facility" else None,
            "std_grade": None,
            "base_min": free_min or 10, "base_fee": 0 if free_min else unit,
            "unit_min": 10, "unit_fee": unit, "steps": None,
            "free_min": free_min, "cap_fee": None, "cap_src": None,
            "daily_hours": daily_hours, "daily_fee": day,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": month, "monthly_night": month_night, "monthly_all": month_all,
            "pay": "", "basis": None, "category": None, "portal_free_now": False,
        }

    for ref in sorted(city_list, key=lambda x: x["no"]):
        name = (ref.get("name") or "").strip()
        ptype = ref.get("type") or "노외"
        grade = ref.get("grade")
        pay = ref.get("pay") or ""
        spaces = ref.get("spaces")
        std_ids = UIJEONGBU_STD_MAP.get(ref["no"], [])
        std = std_by_no.get(std_ids[0]) if std_ids else None
        for sid in std_ids:
            if sid in std_by_no:
                used_std.add(sid)
        if std:
            matched += 1
            if int(std.get("주차구획수") or 0) != spaces:
                space_diff.append(f"{name}: 표준데이터 {std.get('주차구획수')}면 ↔ 도시공사 {spaces}면")
            sg = to_int(std.get("급지구분"))
            if sg in (1, 2, 3) and grade and sg != grade:
                grade_diff.append(f"{name}: 표준데이터 {sg}급지 ↔ 도시공사 {grade}급지")
            if uij_name_key(std.get("주차장명")) != uij_name_key(name):
                name_diff.append(f"{name} ↔ 표준데이터 ‘{std.get('주차장명')}’")
        for sid in std_ids[1:]:
            extra = std_by_no.get(sid)
            if extra:
                space_diff.append(f"{name}: 표준데이터 ‘{extra.get('주차장명')}’ "
                                  f"{extra.get('주차구획수')}면이 같은 주차장으로 묶여 있음")

        # 주소·좌표 — 표준데이터가 있으면 그 주소를, 없으면 도시공사 현황 위치를 쓴다.
        jibun = (std.get("소재지지번주소") or "").strip() if std else ""
        road = (std.get("소재지도로명주소") or "").strip() if std else ""
        loc = (ref.get("loc") or "").strip()
        if not jibun and not road:
            addr_jibun = f"경기도 의정부시 {loc}" if loc else ""
            addr_road = ""
        else:
            addr_jibun, addr_road = jibun, road
        addr = addr_jibun or addr_road or loc

        lat = lng = None
        if std and ref["no"] not in UIJEONGBU_COORD_DROP:
            try:
                lat = float(std["위도"]) if (std.get("위도") or "").strip() else None
                lng = float(std["경도"]) if (std.get("경도") or "").strip() else None
            except ValueError:
                lat = lng = None
        if lat is None or lng is None:
            lat, lng = geocode.get(name, (None, None))

        # 껍데기 행 제외 — 이름·주소·구획수가 없으면 페이지를 만들지 않는다.
        reason = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (UIJEONGBU_BBOX[0] <= lat <= UIJEONGBU_BBOX[1]
                                      and UIJEONGBU_BBOX[2] <= lng <= UIJEONGBU_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = (uijeongbu_dong_of(jibun) or uijeongbu_dong_of(road) or uijeongbu_dong_of(loc)
                or next((d for d in UIJEONGBU_DONGS if name.startswith(d)), None))
        dong_src = "지번주소" if uijeongbu_dong_of(jibun) else (
            "도로명주소" if uijeongbu_dong_of(road) else
            ("도시공사위치" if uijeongbu_dong_of(loc) else
             ("주차장명" if name.startswith(tuple(UIJEONGBU_DONGS)) else "없음")))
        gu = UIJEONGBU_DISTRICTS[0][0]

        note = (std.get("특기사항") or "").strip() if std else ""
        if std:
            win, oper, closed_note = parse_schedule(std, note)
        else:
            win = {k: {"open": True, "start": 0, "end": 1440, "24h": True,
                       "listed": True, "raw": ["00:00", "24:00"]} for k in ("weekday", "sat", "sun")}
            oper, closed_note = {"weekday": True, "sat": True, "sun": True}, False
        free_days = parse_free_days(note)

        capa = ref.get("capa") or {}
        if capa and sum(capa.values()) != spaces:
            capa_bad.append(f"{name}({sum(capa.values())}면 ≠ {spaces}면)")
        capa_detail = {"disabled": capa.get("장애인") or 0, "compact": capa.get("경차") or 0,
                       "elec": capa.get("전기차") or 0, "woman": capa.get("여성") or 0}
        big = []
        if capa.get("대형차"):
            big.append(f"대형차 {capa['대형차']}면")
        if capa.get("캠핑카"):
            big.append(f"캠핑카 {capa['캠핑카']}면")
        if big:
            note = (note + " · " if note else "") + " · ".join(big)

        street = ptype == "노상"
        facility = ptype == "부설"
        category = "facility" if facility else ("street" if street else "off")
        if street:
            street_no += 1
            lot_id = f"uj-s{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"uj-{card_no:03d}"

        is_free = pay == "무료"
        fee = fee_base(category, grade)
        std_fee = {
            "base_min": to_int(std.get("주차기본시간")) if std else None,
            "base_fee": to_int(std.get("주차기본요금")) if std else None,
            "unit_min": to_int(std.get("추가단위시간")) if std else None,
            "unit_fee": to_int(std.get("추가단위요금")) if std else None,
            "day": to_int(std.get("1일주차권요금")) if std else None,
            "monthly": to_int(std.get("월정기권요금")) if std else None,
        }
        fee["std"] = std_fee
        notice = None
        if is_free:
            fee["type"] = fee["raw_type"] = "무료"
            fee["category"] = None
            free_days = {"sat": True, "sun": True}
        elif facility:
            fac = uijeongbu_facility_fee(name)
            if fac is None:
                fee["type"] = fee["raw_type"] = "미상"
                fee["category"] = None
                notice = "「의정부시 공공시설 부설주차장 운영 조례」 별표 3에 이 주차장의 요금이 없어 현장 확인이 필요합니다"
            else:
                fee.update(fee_base("facility", None, free_min=fac["free_min"], unit=fac["unit"],
                                    day=fac["day"], month=fac["month"], daily_hours=24))
                fee["category"] = "facility"
                fee["basis"] = "「의정부시 공공시설 부설주차장 운영 조례」 별표 3"
                notice = UIJEONGBU_FACILITY_NOTE
        elif street:
            table = UIJEONGBU_FEES["street"][grade]
            fee.update(fee_base("street", grade, unit=table["unit"], day=table["day"],
                                month=table["month"], daily_hours=24))
            fee["cap_src"] = "조례 1일 주차요금"
            fee["basis"] = f"「의정부시 주차장 설치 및 관리 조례」 별표1 노상 {grade}급지"
            if std_fee["base_fee"] and (std_fee["base_min"], std_fee["base_fee"]) != (10, table["unit"]):
                fee_diff.append(f"{name}: 등록 {std_fee['base_min']}분 {std_fee['base_fee']}원 "
                                f"→ 적용 10분 {table['unit']}원(조례 {grade}급지)")
        elif capa.get("대형차") and capa.get("대형차") == spaces:
            # 대형자동차 전용 주차장 — 조례 별표1의 ‘대형 기준 요금의 2배’를 적용한다
            #   (표준데이터 등록값도 10분 400원·1일 10,000원·월 112,000원으로 2급지의 2배다).
            table = UIJEONGBU_FEES["off"][grade]
            fee.update(fee_base("off", grade, unit=table["unit"] * 2, day=table["day"] * 2,
                                month=table["month_all"] * 2, month_night=table["month_night"] * 2,
                                month_all=table["month_all"] * 2, daily_hours=UIJEONGBU_DAY_HOURS))
            fee["basis"] = f"「의정부시 주차장 설치 및 관리 조례」 별표1 노외 {grade}급지(대형차 기준요금의 2배)"
            notice = UIJEONGBU_BIG_NOTE
        elif "캠핑카" in name:
            fee.update(fee_base("off", grade, unit=UIJEONGBU_CAMP_FEE["unit"], day=UIJEONGBU_CAMP_FEE["day"],
                                month=UIJEONGBU_CAMP_FEE["month"], month_all=UIJEONGBU_CAMP_FEE["month"],
                                daily_hours=UIJEONGBU_DAY_HOURS))
            fee["basis"] = "표준데이터 등록요금(캠핑카 전용)"
            notice = UIJEONGBU_CAMP_NOTE
        else:
            table = UIJEONGBU_FEES["off"][grade]
            fee.update(fee_base("off", grade, unit=table["unit"], day=table["day"],
                                month=table["month_all"], month_night=table["month_night"],
                                month_all=table["month_all"], daily_hours=UIJEONGBU_DAY_HOURS))
            fee["basis"] = f"「의정부시 주차장 설치 및 관리 조례」 별표1 노외 {grade}급지"
            if std_fee["base_fee"]:
                applied = (10, table["unit"])
                if (std_fee["base_min"], std_fee["base_fee"]) != applied:
                    fee_diff.append(f"{name}: 등록 {std_fee['base_min']}분 {std_fee['base_fee']}원 "
                                    f"→ 적용 10분 {table['unit']}원(조례 {grade}급지)")

        fee["pay"] = (std.get("결제방법") or "").strip() if std else ""

        lots.append({
            "id": lot_id,
            "mgmt_no": (std.get("주차장관리번호") or "").strip() if std else "",
            "src": "표준데이터" if std else "도시공사현황",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": gu,
            "dong": dong,
            "dong_src": dong_src,
            "kind": (std.get("주차장구분") or "").strip() if std else "공영",
            "ptype": ptype,
            "addr_jibun": addr_jibun,
            "addr_road": addr_road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
            "spaces": spaces,
            "tel": (std.get("전화번호") or "").strip() if std else "",
            "lat": lat, "lng": lng,
            "base_date": (std.get("데이터기준일자") or "").strip() if std else "2026-09 (도시공사 현황)",
            "manager": (std.get("관리기관명") or "").strip() if std else "의정부도시공사",
            "note": note,
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (std.get("장애인전용주차구역보유여부") or "").strip() if std else "",
            "capa_detail": capa_detail,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "의정부시",
            "city_slug": "uijeongbu",
        })

    # 표준데이터에만 있고 도시공사 현황(2026-09)에 없는 주차장 — 등록값 그대로 카드로 넣고 안내를 단다.
    for mgmt, std in sorted(std_by_no.items()):
        if mgmt in used_std:
            continue
        name = (std.get("주차장명") or "").strip()
        jibun = (std.get("소재지지번주소") or "").strip()
        road = (std.get("소재지도로명주소") or "").strip()
        spaces = to_int(std.get("주차구획수"))
        pay = (std.get("요금정보") or "").strip()
        if not (name and (jibun or road) and spaces):
            excluded.append({"name": name or "(이름 없음)", "reason": "이름·주소·구획수 중 없음"})
            continue
        try:
            lat = float(std["위도"]) if (std.get("위도") or "").strip() else None
            lng = float(std["경도"]) if (std.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if lat is not None and not (UIJEONGBU_BBOX[0] <= lat <= UIJEONGBU_BBOX[1]
                                    and UIJEONGBU_BBOX[2] <= lng <= UIJEONGBU_BBOX[3]):
            excluded.append({"name": name, "reason": "좌표 범위 이탈"})
            continue
        note = (std.get("특기사항") or "").strip()
        win, oper, closed_note = parse_schedule(std, note)
        grade = to_int(std.get("급지구분")) or 2
        fee = fee_base("off", grade)
        if pay == "무료":
            fee["type"] = fee["raw_type"] = "무료"
            free_days = {"sat": True, "sun": True}
        else:
            table = UIJEONGBU_FEES["off"][grade]
            fee.update(fee_base("off", grade, unit=table["unit"], day=table["day"],
                                month=table["month_all"], month_night=table["month_night"],
                                month_all=table["month_all"], daily_hours=UIJEONGBU_DAY_HOURS))
            fee["basis"] = f"「의정부시 주차장 설치 및 관리 조례」 별표1 노외 {grade}급지"
            free_days = parse_free_days(note)
        fee["pay"] = (std.get("결제방법") or "").strip()
        fee["std"] = {"base_min": to_int(std.get("주차기본시간")), "base_fee": to_int(std.get("주차기본요금")),
                      "unit_min": to_int(std.get("추가단위시간")), "unit_fee": to_int(std.get("추가단위요금")),
                      "day": to_int(std.get("1일주차권요금")), "monthly": to_int(std.get("월정기권요금"))}
        card_no += 1
        lots.append({
            "id": f"uj-{card_no:03d}", "mgmt_no": mgmt, "src": "표준데이터", "list_mode": "card",
            "name": name, "gu": UIJEONGBU_DISTRICTS[0][0],
            "dong": uijeongbu_dong_of(jibun) or uijeongbu_dong_of(road),
            "dong_src": "지번주소" if uijeongbu_dong_of(jibun) else "없음",
            "kind": (std.get("주차장구분") or "").strip(), "ptype": (std.get("주차장유형") or "노외").strip(),
            "addr_jibun": jibun, "addr_road": road, "road": None, "spaces": spaces,
            "tel": (std.get("전화번호") or "").strip(), "lat": lat, "lng": lng,
            "base_date": (std.get("데이터기준일자") or "").strip(),
            "manager": (std.get("관리기관명") or "").strip(), "note": note,
            "notice": UIJEONGBU_NEW_LOT_NOTE, "fee": fee, "oper": oper, "hours": win,
            "free_days": free_days, "free_window": parse_free_window(note),
            "closed_from_note": closed_note,
            "disabled_area": (std.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None, "portal_name": None, "realtime": None, "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "의정부시", "city_slug": "uijeongbu",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"uj-{i:03d}" if l["list_mode"] == "card" else f"uj-s{i:03d}"

    quality = check_quality_uijeongbu(rows_all, rows_city, lots, excluded, city_list,
                                      matched, grade_diff, space_diff, name_diff, fee_diff, capa_bad)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(UIJEONGBU_LIST_JSON).strftime("%Y-%m-%d %H:%M")
                            if UIJEONGBU_LIST_JSON.exists() else None,
            "region": {"province": "경기도", "city": "의정부시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-07-15",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("의정부시가 등록한 72행(제공기관명 '경기도 의정부시')을 읽었다. 모두 노외로 등록되어 "
                             "있으나 도시공사 현황과 맞춰 보면 노상 13구간이 섞여 있어, 유형은 도시공사 현황을 따랐다. "
                             "좌표·운영시간·전화·관리번호 출처로 썼다."),
                },
                {
                    "id": "uiuc", "name": "의정부도시공사 공영주차장 현황·요금 안내",
                    "org": "의정부도시공사 교통사업처",
                    "url": UIJEONGBU_LIST_URL,
                    "file": UIJEONGBU_LIST_JSON.name,
                    "sha256": sha256(UIJEONGBU_LIST_JSON) if UIJEONGBU_LIST_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026년 9월 기준", "rows_total": len(city_list),
                    "fetched_at": _snapshot_time(UIJEONGBU_LIST_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if UIJEONGBU_LIST_JSON.exists() else None,
                    "note": ("공영주차장 80곳(노외 67·노상 13, 그 가운데 부설 10) 5,649면의 유형·급지·면수와 "
                             "구획 구성(일반·장애인·경차·여성·전기차·대형차·캠핑카) 확인용. 이름·유형·급지·면수의 "
                             "기준으로 삼았다."),
                },
                {
                    "id": "portal", "name": "의정부도시공사 공영주차장 주차요금·감면 안내",
                    "org": "의정부도시공사 교통사업처",
                    "url": UIJEONGBU_PAGE_URL,
                    "file": UIJEONGBU_PORTAL_TXT.name,
                    "sha256": sha256(UIJEONGBU_PORTAL_TXT) if UIJEONGBU_PORTAL_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": None,
                    "fetched_at": _snapshot_time(UIJEONGBU_PORTAL_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if UIJEONGBU_PORTAL_TXT.exists() else None,
                    "note": ("급지 구분(1급지 상업지역·역세권·의정부1동 둔치, 2급지 주거지역, 3급지 그 밖), "
                             "노상·노외 1~3급지 요금표(10분당), 부설주차장 요금표, 감면 11종 확인용."),
                },
                {
                    "id": "geocode", "name": "주소 지오코딩(카카오맵)",
                    "org": "Kakao Map 지오코딩(maps geocode)",
                    "url": "https://map.kakao.com",
                    "file": UIJEONGBU_GEOCODE_JSON.name,
                    "sha256": sha256(UIJEONGBU_GEOCODE_JSON) if UIJEONGBU_GEOCODE_JSON.exists() else None,
                    "license": "지도 서비스 지오코딩 결과(참고용)",
                    "base_date": None, "rows_total": len(geocode),
                    "fetched_at": "2026-11-17 10:24 (KST)",
                    "note": ("표준데이터에 없는 부설주차장 10곳과 고산지구 제3공영·용현동 제1공영의 좌표를 "
                             "주소로 지오코딩해 채웠다. 주차장 입구와 수십 미터 다를 수 있다."),
                },
                {
                    "id": "ordinance", "name": "의정부시 주차장 설치 및 관리 조례 (제3조제1항·별표1)",
                    "org": "의정부시",
                    "url": UIJEONGBU_ORDINANCE_URL,
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "시행 2026-01-09 (경기도의정부시조례 제3674호)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("공영주차장 주차요금(노상·노외 1~3급지 10분당 요율, 1일 주차요금·1일 주차권, "
                             "월 정기권)과 요금 감면 근거. 도시공사 요금 안내로 교차 확인."),
                },
                {
                    "id": "annex", "name": "의정부시 공공시설 부설주차장 운영 조례 (제8조·제9조·별표2·별표3)",
                    "org": "의정부시",
                    "url": UIJEONGBU_ANNEX_URL,
                    "file": None, "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": "공포 2026-02-23 (조례 제3699호 일부개정)", "rows_total": None,
                    "fetched_at": "2026-11-17 (KST)",
                    "note": ("시청·도서관·공원 등 공공시설 부설주차장의 유료 운영시간(별표 2)과 요금(별표 3: "
                             "최초 30분~3시간 무료 뒤 10분당 300·200원, 1일 7,000·5,000원) 근거. 유료 운영시간 외에는 "
                             "무료로 개방한다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in UIJEONGBU_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "uijeongbu_grade",
            "unit_min": 10,
            "day_hours": UIJEONGBU_DAY_HOURS,
            "applies": "2026-01-09 시행 조례",
            "off": [{"grade": g, **t, "lots": 0} for g, t in sorted(UIJEONGBU_FEES["off"].items())],
            "street": [{"grade": g, **t} for g, t in sorted(UIJEONGBU_FEES["street"].items())],
            "facility": [{"name": k, **v} for k, v in UIJEONGBU_FACILITY.items()],
            "camp": UIJEONGBU_CAMP_FEE,
            "basis": ("「의정부시 주차장 설치 및 관리 조례」 별표1(2026-01-09 시행) · 「의정부시 공공시설 부설주차장 "
                      "운영 조례」 별표3 · 의정부도시공사 공영주차장 요금·감면 안내(2026-11-17 확인)"),
        },
    }
    for row in payload["fee_table"]["off"]:
        row["lots"] = quality["급지별"].get(row["grade"], 0)
    payload.update(CITY_META["의정부시"] | {
        "city": "의정부시",
        "weekend_free_pages": False,     # 주말 무료 개방 ‘페이지’는 만들지 않는다
        "discounts": UIJEONGBU_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "uijeongbu_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def uij_name_key(s: str) -> str:
    """주차장 이름 비교용 키 — 괄호·공백·‘주차장/공영/제/지하’와 숫자 표기 차이를 없앤다."""
    t = re.sub(r"\([^)]*\)", "", s or "")
    t = re.sub(r"[\s'\"\[\]·,.ㆍ~\-]", "", t)
    t = t.replace("제", "")
    for w in ("주차장", "공영주차장", "노외", "공영", "지하", "임시", "전용"):
        t = t.replace(w, "")
    return t


def check_quality_uijeongbu(std_all, rows, lots, excluded, city_list,
                            matched, grade_diff, space_diff, name_diff, fee_diff, capa_bad):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(f'{l["gu"]} {l["dong"] or "동 미상"}' for l in card)
    fee_types = Counter(l["fee"]["type"] for l in lots)
    paid = [l["fee"]["unit_fee"] for l in lots
            if l["fee"]["type"] == "유료" and l["fee"]["unit_fee"] and l["ptype"] != "부설"]
    mgmt = Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no"))
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_의정부시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "구별": dict(Counter(l["gu"] for l in card)),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(fee_types),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in lots
                               if l["fee"]["type"] == "유료" and l["fee"].get("grade"))),
        "도시공사_목록수": len(city_list),
        "도시공사_매칭": matched,
        "급지_차이": grade_diff,
        "면수_차이": space_diff,
        "이름_차이": name_diff,
        "등록값_차이": fee_diff,
        "구획구성_불일치": capa_bad,
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
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
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
        lines.append(f"- 원자료 {city} {q['원자료_행수']}행 중 껍데기 행 {q['제외_행수']}행 제외"
                     + (f" · 같은 지번 중복 {q['중복제거_행수']}행 제거" if q.get("중복제거_행수") else ""))
        if city in ("평택시", "남양주시", "시흥시", "의정부시"):
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
    ap.add_argument("--city", choices=["suwon", "seongnam", "yongin", "hwaseong", "anyang", "pyeongtaek", "bucheon", "goyang", "namyangju", "ansan", "siheung", "uijeongbu", "all"], default="all")
    args = ap.parse_args()

    want = (["수원시", "성남시", "용인시", "화성시", "안양시", "평택시", "부천시", "고양시", "남양주시", "안산시", "시흥시", "의정부시"] if args.city == "all" else \
            {"suwon": ["수원시"], "seongnam": ["성남시"], "yongin": ["용인시"],
             "hwaseong": ["화성시"], "anyang": ["안양시"], "pyeongtaek": ["평택시"],
             "bucheon": ["부천시"], "goyang": ["고양시"], "namyangju": ["남양주시"],
             "ansan": ["안산시"], "siheung": ["시흥시"], "uijeongbu": ["의정부시"]}[args.city])
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
    if "남양주시" in want:
        cities.append(build_namyangju())
    if "안산시" in want:
        cities.append(build_ansan())
    if "시흥시" in want:
        cities.append(build_siheung())
    if "의정부시" in want:
        cities.append(build_uijeongbu())

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
