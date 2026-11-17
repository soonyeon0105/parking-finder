#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공영주차장 파인더 - 데이터 정제 스크립트 (수원시 + 성남시 + 용인시 + 화성시 + 안양시 + 평택시 + 부천시 + 고양시 + 남양주시 + 안산시 + 시흥시 + 의정부시 + 김포시 + 파주시 + 광주시 + 하남시 + 군포시 + 광명시 + 구리시 + 오산시 + 이천시 + 안성시 + 양주시)

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
     - 김포시 50행: 요금·운영시간·좌표 (노외 40 + 노상 10, 구 없이 3읍 3면·동)
     - 파주시 155행: 요금·운영시간·좌표 (노외 90 + 노상 65, 구 없이 4읍 9면·동지역)
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
  data/anseong_parking.json  안성시 단독 결과
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
    "김포시": {"slug": "gimpo", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "파주시": {"slug": "paju", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    # 광주시(경기도) — 광주광역시와 다른 도시다. 슬러그는 gwangju, 경로는 /parking/gyeonggi/gwangju/.
    "광주시": {"slug": "gwangju", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "하남시": {"slug": "hanam", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "군포시": {"slug": "gunpo", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "광명시": {"slug": "gwangmyeong", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "구리시": {"slug": "guri", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "오산시": {"slug": "osan", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "이천시": {"slug": "icheon", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "안성시": {"slug": "anseong", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "양주시": {"slug": "yangju", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "포천시": {"slug": "pocheon", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "의왕시": {"slug": "uiwang", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "여주시": {"slug": "yeoju", "province": "경기도", "province_slug": "gyeonggi",
             "dong_page_min_lots": 3},
    "동두천시": {"slug": "dongducheon", "province": "경기도", "province_slug": "gyeonggi",
              "dong_page_min_lots": 3},
    "과천시": {"slug": "gwacheon", "province": "경기도", "province_slug": "gyeonggi",
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


# ---------------------------------------------------------------- 김포시 (T-03 Phase 12)
GIMPO_PROVIDER = "경기도 김포시"
# 김포시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고 그 아래 읍·면·동 페이지를 둔다.
GIMPO_DISTRICTS = [("김포시", "gimpo")]
GIMPO_BBOX = (37.55, 37.75, 126.55, 126.87)     # 김포시 대략 경계(좌표 점검용)
# 김포시 법정동(동지역 9개 동)과 읍·면(3읍 3면) — 표준데이터 주소에서 지역을 뽑는 데 쓴다.
GIMPO_DONGS = ("운양동", "장기동", "구래동", "마산동", "사우동", "북변동", "풍무동",
               "감정동", "걸포동",
               "통진읍", "고촌읍", "양촌읍", "대곶면", "월곶면", "하성면")
# 지번주소에 읍·면 없이 리만 적힌 행(‘경기도 김포시 양곡리 1332’)을 읍·면으로 되돌린다.
GIMPO_RI_TO_EUP = {
    "양곡리": "양촌읍", "학운리": "양촌읍", "대포리": "양촌읍", "흥신리": "양촌읍",
    "진호리": "양촌읍", "누산리": "양촌읍", "마조리": "양촌읍", "구래리": "양촌읍",
    "신곡리": "고촌읍", "전호리": "고촌읍", "태리": "고촌읍", "향산리": "고촌읍",
    "풍곡리": "고촌읍", "유현리": "고촌읍", "하사리": "고촌읍",
    "마송리": "통진읍", "서암리": "통진읍", "도사리": "통진읍", "귀전리": "통진읍",
    "옹정리": "통진읍", "가현리": "통진읍", "동을산리": "통진읍", "고정리": "통진읍",
    "수찬리": "통진읍",
    "율생리": "대곶면", "대능리": "대곶면", "신안리": "대곶면", "초원지리": "대곶면",
    "거물대리": "대곶면", "오니산리": "대곶면", "대벽리": "대곶면", "송마리": "대곶면",
    "쇄정리": "대곶면", "석정리": "대곶면", "성지리": "대곶면", "약암리": "대곶면",
    "율마리": "대곶면",
    "군하리": "월곶면", "포내리": "월곶면", "갈산리": "월곶면", "고막리": "월곶면",
    "고양리": "월곶면", "성동리": "월곶면", "용강리": "월곶면", "조강리": "월곶면",
    "보구곶리": "월곶면",
    "석탄리": "하성면", "마곡리": "하성면", "후평리": "하성면", "가금리": "하성면",
    "시암리": "하성면", "양택리": "하성면", "원산리": "하성면", "전류리": "하성면",
    "봉성리": "하성면",
}

GIMPO_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2171011"
GIMPO_BLOG_URL = "https://blog.naver.com/gimpo2010/224252112942"
GIMPO_NEWS_URL = "https://www.gimpo.go.kr/news/selectBbsNttView.do?bbsNo=466&key=9377&nttNo=970481"
GIMPO_HASEONG_URL = "https://www.gimpo.go.kr/news/selectBbsNttView.do?bbsNo=466&key=9377&nttNo=988443"
GIMPO_GUCHON1_URL = "https://gimpo.go.kr/news/selectBbsNttView.do?bbsNo=466&key=9377&nttNo=954460"
GIMPO_UNYANG2_URL = "https://www.gimpo.go.kr/news/selectBbsNttView.do?bbsNo=466&key=9377&nttNo=960218"
GIMPO_H24_URL = "https://www.gimpo.go.kr/news/selectBbsNttView.do?bbsNo=466&key=9377&nttNo=716196"
GIMPO_PORTAL_URL = "https://its.gimpo.go.kr/parking_portal.view"
GIMPO_ANNEX_TXT = RAW / "gimpo.go.kr_주차장조례_별표1_20261117.txt"
GIMPO_FREE_TXT = RAW / "gimpo.go.kr_공영주차장_1시간무료_대상_20261117.txt"
GIMPO_PRESS_TXT = RAW / "gimpo.go.kr_보도자료_공영주차장_20261117.txt"
GIMPO_GUC_TXT = RAW / "guc.or.kr_공영주차장_상세안내_20261117.txt"

# 김포시 공영주차장 요금 — 「김포시 주차장 조례」 제5조제1항 별표1(시행 2026-09-28, 경기도김포시조례 제2322호).
#   · 기본 30분 600원(1급지)·300원(2급지) 뒤 30분을 넘기면 10분 단위로 300원·100원이 붙는다.
#   · 1일 주차요금이 상한이다(1급지 7,000원, 2급지 3,500원).
#   · 월 정기권은 노외 1급지 주·야간 80,000원 / 주간 60,000원 / 야간 50,000원,
#     노상 1급지 주간 60,000원만 있다.
#   · 급지: 1급지 = 통진읍·고촌읍·양촌읍·동지역, 2급지 = 그 밖의 지역(대곶·월곶·하성면).
GIMPO_FEES = {
    "off": {
        1: {"base_min": 30, "base_fee": 600, "unit_min": 10, "unit_fee": 300,
            "day": 7_000, "month_all": 80_000, "month_day": 60_000, "month_night": 50_000},
        2: {"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 100,
            "day": 3_500, "month_all": 50_000, "month_day": 35_000, "month_night": 25_000},
    },
    "street": {
        1: {"base_min": 30, "base_fee": 600, "unit_min": 10, "unit_fee": 300,
            "day": 7_000, "month_all": None, "month_day": 60_000, "month_night": None},
        2: {"base_min": 30, "base_fee": 300, "unit_min": 10, "unit_fee": 100,
            "day": 3_500, "month_all": None, "month_day": 35_000, "month_night": None},
    },
}
# 5일장 주차장(북변공영·통진·양곡1)의 정기권 — 시 공식 블로그 감면표(2026-04-14).
GIMPO_MARKET_MONTHLY = {"month_all": 50_000, "month_day": 40_000, "month_night": 30_000}
GIMPO_MARKET_LOTS = ("북변 공영주차장", "통진공영주차장", "양곡1 공영주차장")
# 1시간 무료(주차요금 1시간 감면) 정책 — 유료 노외 공영주차장 40개소, 2026-04-21~2027-04-30.
#   조례 별표1 4.파(지역경제·전통시장 활성화를 위해 주차요금을 1시간 범위에서 면제할 수 있다)에 근거한다.
GIMPO_FREE_HOUR_MIN = 60
GIMPO_FREE_HOUR_NOTE = ("최초 1시간 무료(김포시 ‘주차요금 1시간 감면’, 2027-04-30까지) · "
                        "00:00~09:00과 공휴일·설·추석 연휴에는 요금이 발생하지 않습니다")
GIMPO_STREET_FREE_NOTE = ("일요일·공휴일과 야간(19:00~익일 09:00)은 무료입니다"
                          "(「김포시 주차장 조례」 별표1 5.)")
# 24시간 운영이지만 00:00~09:00에는 요금이 발생하지 않는다(2023-02-01 24시간 운영 전환 보도자료).
GIMPO_NIGHT_FREE_NOTE = ("00:00~09:00에는 요금이 발생하지 않습니다 — 이 시간대에 걸쳐 주차하면 "
                         "카드의 예상요금(주차한 시간 전체 기준)보다 적게 나올 수 있습니다")
GIMPO_HOLIDAY_NOTE = "공휴일과 설·추석 연휴에는 모든 공영주차장을 무료로 개방합니다"
# 「김포시 주차장 조례」 별표1 4. 주차요금의 특례와 김포도시관리공사 감면 안내(2026-11-17 확인).
#   · 표에 적힌 ‘감면율이 높은 하나만’ 적용한다(별표1 8.).
GIMPO_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·임산부 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경차(1,000cc 미만)·저공해·임산부·병역명문가(김포시민)·65세 이상 김포시민·장기기증자"},
    {"label": "장애인·2자녀 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "장애인 표지+등록증(본인 탑승), 2자녀(경기아이플러스·경기도민), 최초 2시간 면제"},
    {"label": "우수자원봉사자 4시간 면제 후 50%", "rate": 0.5, "exempt_min": 240,
     "note": "경기도·김포시 우수자원봉사자증 소지자(본인 운전), 최초 4시간 면제"},
    {"label": "국가보훈대상자 24시간 면제 후 50%", "rate": 0.5, "exempt_min": 1440,
     "note": "국가보훈대상자 증서 소지자(본인 소유 승용차), 최초 24시간 면제(2026-09-28 개정)"},
    {"label": "3자녀·유공납세자·중소기업 100%", "rate": 1.0, "exempt_min": 0,
     "note": "3자녀 이상 경기도민·경기도 유공납세자(1년)·김포시 중소기업 차량(1년·2대)"},
]
# 표준데이터(기준일 2026-07-15)에 없는 주차장 — 김포시 보도자료·행정안전부 명절 개방 목록으로 채웠다.
#   · 좌표는 주소 지오코딩(카카오맵)·구글 장소로 채웠고, 주차장 입구와 수십 미터 다를 수 있다.
GIMPO_EXTRA = [
    {"name": "고촌1 공영주차장", "addr_jibun": "경기도 김포시 고촌읍 신곡리 1109",
     "addr_road": "경기도 김포시 고촌읍 신기신동로 87", "spaces": 31, "ptype": "노외",
     "lat": 37.6037916, "lng": 126.7731965, "tel": "031-996-6584",
     "note": "2025-11-15 무료 시범운영 뒤 2026-01-01부터 유료 정식운영(김포복지재단 인근)",
     "src": "시 보도자료·명절 무료개방 목록", "grade": 1, "free_hour": True},
    {"name": "운양2 공영주차장", "addr_jibun": "경기도 김포시 운양동 1338-5",
     "addr_road": "", "spaces": 20, "ptype": "노외",
     "lat": 37.6505303, "lng": 126.6915699, "tel": "031-996-6584",
     "note": "모담도서관 인근 · 2026-01-15 무료 시범운영 뒤 2026-02-01부터 유료 정식운영",
     "src": "시 보도자료·1시간 무료 대상 목록", "grade": 1, "free_hour": True},
    {"name": "하성공영주차장", "addr_jibun": "경기도 김포시 하성면 석탄리 530-15",
     "addr_road": "", "spaces": 63, "ptype": "노외",
     "lat": 37.7202321, "lng": 126.6343599, "tel": "031-996-6584",
     "note": "하성면행정복지센터 인근 하성교차로 · 2026-09-01 무료 시범운영 뒤 2026년 11월부터 유료",
     "src": "시 보도자료", "grade": 2, "free_hour": False,
     "notice": ("2026년 11월부터 유료로 전환했으나 요금표가 아직 공개되지 않아 요금을 계산하지 못합니다 "
                "— 김포도시관리공사(031-996-6584)에 확인하세요")},
]


def gimpo_dong_of(text: str):
    """주소에서 김포시 법정동·읍·면을 뽑는다(‘양곡리 1332’처럼 읍·면이 빠진 표기도 되돌린다).

    읍·면 이름은 뒤에 리 이름이 바로 붙어(‘고촌읍신곡리953-2’) 나오므로 느슨하게 찾고,
    동 이름은 다른 낱말 속에 우연히 들어가지 않도록 뒤를 본다.
    """
    t = re.sub(r"\s", "", text or "")
    for d in sorted(GIMPO_DONGS, key=len, reverse=True):
        if d.endswith(("읍", "면")):
            if re.search(re.escape(d) + r"(?=$|\d|[가-힣])", t):
                return d
        elif re.search(re.escape(d) + r"(?=$|\d|[^가-힣])", t):
            return d
    # 리만 적힌 주소 — 리 이름이 겹치지 않는 것만 되돌린다(신곡리·마조리·하사리는 둘 이상 읍·면에 있다).
    for ri in sorted(GIMPO_RI_TO_EUP, key=len, reverse=True):
        # ‘경기도김포시양곡리1332’처럼 앞 글자에 붙어도 찾되, 뒤에 다른 한글이 이어지면 다른 낱말로 본다.
        if re.search(re.escape(ri) + r"(?=$|\d|[^가-힣])", t):
            return GIMPO_RI_TO_EUP[ri]
    return None


def gimpo_name_key(s: str) -> str:
    """주차장 이름 비교용 키 — 띄어쓰기·괄호와 끝의 ‘주차장’만 없앤다.

    ‘고촌공영주차장’과 ‘고촌노상 주차장’처럼 다른 주차장이 같은 키가 되지 않도록,
    가운데에 있는 ‘공영·노상·노외’는 지우지 않는다.
    """
    t = re.sub(r"\([^)]*\)", "", s or "")
    t = re.sub(r"[\s'\"\[\]·,.ㆍ~\-]", "", t)
    for w in ("주차장",):
        if t.endswith(w):
            t = t[: -len(w)]
            break
    return t


def gimpo_fee(category: str, grade: int, *, free_hour: bool, monthly=None, daily_hours=24):
    """김포시 요금 구조 → 사이트 공통 fee 객체."""
    t = GIMPO_FEES[category][grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False, "grade": grade, "std_grade": None,
        "base_min": t["base_min"], "base_fee": t["base_fee"],
        "unit_min": t["unit_min"], "unit_fee": t["unit_fee"], "steps": None,
        "free_min": 10 if category == "street" else None,
        #   조례 별표1 3.라 ‘최초 10분 미만 정차 무료’ — 유료 노외는 1시간 무료(deduct_min)에 이미 포함된다.
        "deduct_min": GIMPO_FREE_HOUR_MIN if free_hour else None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": daily_hours, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": monthly if monthly is not None else t["month_all"],
        "monthly_day": t["month_day"], "monthly_night": t["month_night"],
        "monthly_all": t["month_all"],
        "pay": "", "basis": None, "category": None, "portal_free_now": False,
    }


def build_gimpo():
    """김포시 공영주차장을 표준데이터 + 시 보도자료 + 조례 별표1로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 김포시 범위를 벗어난 행은 제외(껍데기 행).
      · 김포시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 읍·면·동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 읍·면·동 페이지는 카드가 3곳 이상인 지역만 만든다.
    요금은 조례 별표1(1~2급지, 30분 기본 뒤 10분 단위)과 ‘최초 1시간 무료’ 정책(노외)을 적용하고,
    운영시간은 도시공사 안내(연중무휴 24시간, 00~09시 요금 없음)를 따른다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GIMPO_PROVIDER]
    lots, excluded, merged, hour_fixed, grade_fixed, fee_diff = [], [], [], [], [], []
    seen = {}
    card_no = street_no = 0

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        # 같은 주차장이 두 행으로 등록된 곳 — 이름이 같거나, 지번·유형·면수가 모두 같으면 한 곳으로 묶는다.
        jibun_key = re.sub(r"\s", "", jibun)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif gimpo_name_key(name) and ("이름", gimpo_name_key(name)) in seen:
            dup_key = ("이름", gimpo_name_key(name))
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and gimpo_name_key(name):
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", gimpo_name_key(name))] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (GIMPO_BBOX[0] <= lat <= GIMPO_BBOX[1]
                                      and GIMPO_BBOX[2] <= lng <= GIMPO_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = gimpo_dong_of(jibun) or gimpo_dong_of(road)
        dong_src = "지번주소" if gimpo_dong_of(jibun) else ("도로명주소" if gimpo_dong_of(road) else "없음")
        note = (r.get("특기사항") or "").strip()
        pay = (r.get("요금정보") or "").strip()
        std_grade = to_int(r.get("급지구분"))
        street = ptype == "노상"

        # 운영시간 — 노외는 도시공사 안내대로 연중무휴 24시간(00~09시 요금 없음)이다.
        #   표준데이터는 대부분 ‘평일+토요일’로만 적혀 있어 공휴일·일요일이 휴무로 보인다.
        std_win, _std_oper, _ = parse_schedule(r, note)
        if not street:
            win = {k: {"open": True, "start": 0, "end": 1440, "24h": True,
                       "listed": True, "raw": ["00:00", "24:00"]} for k in ("weekday", "sat", "sun")}
            oper = {"weekday": True, "sat": True, "sun": True}
            if not all(std_win[k]["open"] and std_win[k]["24h"] for k in ("weekday", "sat", "sun")):
                hour_fixed.append(f"{name}: 표준데이터 운영요일 {r.get('운영요일') or '—'} → 연중무휴 24시간")
            free_days = {"sat": False, "sun": False}
            closed_note = False
        else:
            win, oper, closed_note = parse_schedule(r, note)
            # 조례 별표1 5. — 노상주차장은 일요일·공휴일과 야간에 무료가 원칙이다.
            win["sun"] = {"open": True, "start": 0, "end": 1440, "24h": True,
                          "listed": True, "raw": ["00:00", "24:00"]}
            oper["sun"] = True
            free_days = {"sat": False, "sun": True}

        grade = std_grade if std_grade in (1, 2) else 1
        # 대곶공영주차장은 조례상 2급지(대곶면)지만 등록된 요금표가 1급지 요율이다 — 요금은 등록값을 따르고 사실을 남긴다.
        apply_grade = grade
        if (grade == 2 and (to_int(r.get("주차기본요금")) or 0) >= 600
                and (to_int(r.get("1일주차권요금")) or 0) >= 7_000):
            apply_grade = 1
            grade_fixed.append(f"{name}: 표준데이터 {grade}급지 ↔ 등록요금이 1급지 요율"
                               f"({r.get('주차기본시간')}분 {r.get('주차기본요금')}원·1일 {r.get('1일주차권요금')}원)")

        market = any(k.replace(" ", "") in name.replace(" ", "") for k in GIMPO_MARKET_LOTS)
        if street:
            street_no += 1
            lot_id = f"gp-s{street_no:03d}"
            fee = gimpo_fee("street", apply_grade, free_hour=False, daily_hours=24)
            fee["grade"] = apply_grade
            fee["basis"] = f"「김포시 주차장 조례」 별표1 노상 {apply_grade}급지"
            free_min_note = GIMPO_STREET_FREE_NOTE
        else:
            card_no += 1
            lot_id = f"gp-{card_no:03d}"
            if pay == "무료":
                fee = {"type": "무료", "raw_type": "무료", "mixed": False, "grade": apply_grade,
                       "std_grade": std_grade, "base_min": None, "base_fee": None, "unit_min": None,
                       "unit_fee": None, "steps": None, "free_min": None, "deduct_min": None,
                       "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
                       "prepaid_day": None, "prepaid_weekend": None, "monthly": None,
                       "monthly_day": None, "monthly_night": None, "monthly_all": None,
                       "pay": "", "basis": "요금 구분 ‘무료’", "category": None, "portal_free_now": False,
                       "std": None}
            else:
                monthly = GIMPO_MARKET_MONTHLY["month_all"] if market else None
                fee = gimpo_fee("off", apply_grade, free_hour=True, monthly=monthly)
                fee["basis"] = (f"「김포시 주차장 조례」 별표1 노외 {apply_grade}급지 · "
                                f"최초 1시간 무료(김포시 정책, 2027-04-30까지)")
                if market:
                    fee["monthly_day"] = GIMPO_MARKET_MONTHLY["month_day"]
                    fee["monthly_night"] = GIMPO_MARKET_MONTHLY["month_night"]
                    fee["monthly_all"] = GIMPO_MARKET_MONTHLY["month_all"]
                # 등록된 월정기권 금액이 조례와 다르면 그 값을 적는다(주간권·야간권만 파는 주차장).
                std_month = to_int(r.get("월정기권요금"))
                if std_month and not market:
                    if std_month == 60_000:
                        fee["monthly"] = 60_000
                    elif std_month == 50_000:
                        fee["monthly"] = 50_000
                    elif std_month == 80_000:
                        fee["monthly"] = 80_000
                    else:
                        fee["monthly"] = std_month
                        fee_diff.append(f"{name}: 등록 월정기권 {std_month:,}원")
                free_min_note = GIMPO_FREE_HOUR_NOTE if pay != "무료" else None
        fee["std_grade"] = std_grade
        fee["pay"] = (r.get("결제방법") or "").strip()
        fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                      "base_fee": to_int(r.get("주차기본요금")),
                      "unit_min": to_int(r.get("추가단위시간")),
                      "unit_fee": to_int(r.get("추가단위요금")),
                      "day": to_int(r.get("1일주차권요금")),
                      "monthly": to_int(r.get("월정기권요금"))}
        if pay != "무료" and fee["std"]["base_fee"]:
            want = GIMPO_FEES["off" if not street else "street"][apply_grade]
            if (fee["std"]["base_min"], fee["std"]["base_fee"]) != (want["base_min"], want["base_fee"]):
                fee_diff.append(f"{name}: 등록 {fee['std']['base_min']}분 {fee['std']['base_fee']}원 ↔ "
                                f"적용 {want['base_min']}분 {want['base_fee']}원({apply_grade}급지)")
        notice = None
        if pay != "무료" and not street and grade != apply_grade:
            notice = (f"조례상 대곶면은 2급지이나 이 주차장의 등록요금은 1급지 요율(30분 600원·10분 300원)입니다 "
                      f"— 현장 요금표를 확인하세요")
        lots.append({
            "id": lot_id,
            "mgmt_no": mgmt,
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "김포시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip() or "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
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
            "free_window": "00:00~09:00" if (not street and pay != "무료") else None,
            "free_hour_note": free_min_note,
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보호여부") or r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "김포시",
            "city_slug": "gimpo",
        })

    # 표준데이터에 없는 주차장(고촌1·운양2·하성) — 시 보도자료로 채운다.
    for ref in GIMPO_EXTRA:
        card_no += 1
        jibun, road = ref["addr_jibun"], ref["addr_road"]
        dong = gimpo_dong_of(jibun) or gimpo_dong_of(road)
        win = {k: {"open": True, "start": 0, "end": 1440, "24h": True,
                   "listed": True, "raw": ["00:00", "24:00"]} for k in ("weekday", "sat", "sun")}
        if ref.get("notice"):
            fee = {"type": "미상", "raw_type": "미상", "mixed": False, "grade": ref["grade"],
                   "std_grade": None, "base_min": None, "base_fee": None, "unit_min": None,
                   "unit_fee": None, "steps": None, "free_min": None, "deduct_min": None,
                   "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
                   "prepaid_day": None, "prepaid_weekend": None, "monthly": None,
                   "monthly_day": None, "monthly_night": None, "monthly_all": None,
                   "pay": "", "basis": "요금표 미공개(2026년 11월 유료 전환)", "category": None,
                   "portal_free_now": False, "std": None}
            free_min_note = "요금표가 공개되면 반영하겠습니다"
        else:
            fee = gimpo_fee("off", ref["grade"], free_hour=ref.get("free_hour", True))
            fee["basis"] = (f"「김포시 주차장 조례」 별표1 노외 {ref['grade']}급지 · "
                            f"최초 1시간 무료(김포시 정책, 2027-04-30까지)")
            free_min_note = GIMPO_FREE_HOUR_NOTE
        lots.append({
            "id": f"gp-{card_no:03d}", "mgmt_no": "", "src": ref["src"], "list_mode": "card",
            "name": ref["name"], "gu": "김포시", "dong": dong,
            "dong_src": "지번주소" if gimpo_dong_of(jibun) else "없음",
            "kind": "공영", "ptype": ref["ptype"],
            "addr_jibun": jibun, "addr_road": road, "road": None,
            "spaces": ref["spaces"], "tel": ref["tel"],
            "lat": ref["lat"], "lng": ref["lng"],
            "base_date": "2026-11 (시 보도자료)", "manager": "김포도시관리공사",
            "note": ref["note"], "notice": ref.get("notice"),
            "fee": fee, "oper": {"weekday": True, "sat": True, "sun": True}, "hours": win,
            "free_days": {"sat": False, "sun": False},
            "free_window": "00:00~09:00" if fee["type"] == "유료" else None,
            "free_hour_note": free_min_note, "closed_from_note": False,
            "disabled_area": "", "capa_detail": None, "portal_name": None, "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "김포시", "city_slug": "gimpo",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"gp-{i:03d}" if l["list_mode"] == "card" else f"gp-s{i:03d}"

    quality = check_quality_gimpo(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                  grade_fixed, fee_diff)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(GIMPO_FREE_TXT).strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "김포시"},
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
                    "note": ("김포시가 등록한 50행(제공기관명 '경기도 김포시', 노외 40·노상 10)을 읽었다. "
                             "이름·주소·운전시간·좌표·전화·관리번호와 등록요금 출처로 썼다."),
                },
                {
                    "id": "gimpo", "name": "김포시 공영주차장 1시간 무료 대상 40개소·요금 감면 표",
                    "org": "김포시(교통정책과 주차시설팀)",
                    "url": GIMPO_BLOG_URL,
                    "file": GIMPO_FREE_TXT.name,
                    "sha256": sha256(GIMPO_FREE_TXT) if GIMPO_FREE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-04-14 게시(2027-04-30까지 시행)",
                    "rows_total": 40,
                    "fetched_at": _snapshot_time(GIMPO_FREE_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if GIMPO_FREE_TXT.exists() else None,
                    "note": ("유료 노외 공영주차장 40개소 목록·도로명주소와 요금 감면표(경차·장애인·다자녀·"
                             "우수자원봉사자·5일장 정기권 등) 확인용. '최초 1시간 무료' 적용 근거."),
                },
                {
                    "id": "press", "name": "김포시 보도자료(공영주차장 운영·개장)",
                    "org": "김포시 교통정책과 주차시설팀",
                    "url": GIMPO_NEWS_URL,
                    "file": GIMPO_PRESS_TXT.name,
                    "sha256": sha256(GIMPO_PRESS_TXT) if GIMPO_PRESS_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2023-02-02 ~ 2026-09-01",
                    "rows_total": None,
                    "fetched_at": _snapshot_time(GIMPO_PRESS_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if GIMPO_PRESS_TXT.exists() else None,
                    "note": ("24시간 연중무휴 운영·00~09시 요금 없음·설·추석 연휴 무료 개방(2023-02-02), "
                             "고촌1(2025-11-14)·운양2(2026-01-16)·하성(2026-09-01) 개장, "
                             "1시간 감면 연장(2026-04-13) 확인용."),
                },
                {
                    "id": "guc", "name": "김포도시관리공사 공영주차장 상세 안내(공유누리)",
                    "org": "김포도시관리공사",
                    "url": "https://www.eshare.go.kr/UserPortal/Upv/UprResrcExpr/index.do?rsrc_no=EE03O5124780",
                    "file": GIMPO_GUC_TXT.name,
                    "sha256": sha256(GIMPO_GUC_TXT) if GIMPO_GUC_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": None, "rows_total": None,
                    "fetched_at": _snapshot_time(GIMPO_GUC_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if GIMPO_GUC_TXT.exists() else None,
                    "note": ("주차장별 주차면수(표준데이터와 일치)와 ‘연중무휴(단, 공휴일 및 00시~09시 주차요금 "
                             "제외)’·감면 안내 확인용. 김포 스마트 주차포털(parking.guc.or.kr)은 웹방화벽 "
                             "차단으로 목록을 읽지 못했다."),
                },
                {
                    "id": "ordinance", "name": "김포시 주차장 조례 (제5조제1항·별표1)",
                    "org": "김포시",
                    "url": GIMPO_ORDINANCE_URL,
                    "file": GIMPO_ANNEX_TXT.name,
                    "sha256": sha256(GIMPO_ANNEX_TXT) if GIMPO_ANNEX_TXT.exists() else None,
                    "license": "자치법규(공개)",
                    "base_date": "시행 2026-09-28 (경기도김포시조례 제2322호, 일부개정)",
                    "rows_total": None,
                    "fetched_at": _snapshot_time(GIMPO_ANNEX_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if GIMPO_ANNEX_TXT.exists() else None,
                    "note": ("공영주차장 주차요금표(노상·노외 1~2급지: 기본 30분 600·300원, 이후 10분당 "
                             "300·100원, 1일 7,000·3,500원, 월 정기권)와 요금 감면 특례 근거. 별표1 원문을 "
                             "그대로 옮겨 두었다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GIMPO_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "gimpo_grade",
            "unit_min": 10,
            "base_min": 30,
            "day_hours": 24,
            "free_hour_min": GIMPO_FREE_HOUR_MIN,
            "applies": "2026-09-28 시행 조례 · 1시간 무료는 2026-04-21~2027-04-30",
            "off": [{"grade": g, **t, "lots": 0} for g, t in sorted(GIMPO_FEES["off"].items())],
            "street": [{"grade": g, **t} for g, t in sorted(GIMPO_FEES["street"].items())],
            "market": GIMPO_MARKET_MONTHLY,
            "market_lots": list(GIMPO_MARKET_LOTS),
            "grade_targets": {"1": "통진읍·고촌읍·양촌읍·동지역", "2": "1급지를 제외한 김포시 지역"},
            "basis": ("「김포시 주차장 조례」 별표1(시행 2026-09-28) · 김포시 ‘공영주차장 1시간 무료’ "
                      "정책(2027-04-30까지) · 김포도시관리공사 공영주차장 안내(2026-11-17 확인)"),
        },
    }
    # 요금표의 ‘이 사이트 유료 주차장’ 칸은 노외 카드만 센다(노상은 따로 표를 그린다).
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["김포시"] | {
        "city": "김포시",
        "weekend_free_pages": False,     # 주말 무료 개방 ‘페이지’는 만들지 않는다
        "discounts": GIMPO_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "gimpo_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_gimpo(std_all, rows, lots, excluded, merged, hour_fixed, grade_fixed, fee_diff):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_김포시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"]["std_grade"] for l in paid if l["fee"].get("std_grade"))),
        "1시간무료_적용": len([l for l in paid if l["fee"].get("deduct_min")]),
        "운영시간_보정": hour_fixed,
        "급지_보정": grade_fixed,
        "등록값_차이": fee_diff,
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }



# ---------------------------------------------------------------- 파주시 (T-03 Phase 13)
PAJU_PROVIDER = "경기도 파주시"
# 파주시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고 그 아래 읍·면·동 페이지를 둔다.
PAJU_DISTRICTS = [("파주시", "paju")]
PAJU_BBOX = (37.68, 38.00, 126.66, 127.02)      # 파주시 대략 경계(좌표 점검용)
# 파주시 법정동(동지역)과 읍·면 — 표준데이터 주소에서 지역을 뽑는 데 쓴다.
#   (행정동 운정1~4동·금촌1~3동·교하동은 법정동 여러 개를 묶은 이름이라 주소에는 나오지 않는다.)
PAJU_DONGS = ("금촌동", "아동동", "야당동", "와동동", "목동동", "동패동", "다율동", "서패동",
              "신촌동", "문발동", "금릉동", "교하동",
              "문산읍", "조리읍", "법원읍", "파주읍",
              "월롱면", "탄현면", "광탄면", "파평면", "적성면", "군내면", "장단면",
              "진동면", "진서면")

PAJU_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2084279"
PAJU_PORTAL_URL = "https://parking.paju.go.kr/parkfeeinformation"
PAJU_PORTAL_HOME = "https://parking.paju.go.kr/"
PAJU_ANNEX_TXT = RAW / "paju_ordinance_20261008.txt"
PAJU_PORTAL_JSON = RAW / "parking.paju.go.kr_searchParkingList_20261117.json"
PAJU_FEE_TXT = RAW / "parking.paju.go.kr_주차요금안내_20261117.txt"

# 파주시 공영주차장 요금 — 「파주시 주차장 설치 및 관리 조례」 제3조제1항 별표1,
#   파주시 통합주차포털(파주파킹) ‘주차장 요금안내’ 표(2026-11-17 확인).
#   · 최초 30분 기본요금 뒤 30분을 넘기면 10분 단위로 붙는다(2025-01-01 개편).
#   · 1일 주차요금이 상한이다(1급지 9,000원 · 2급지 8,000원 · 3급지 7,000원).
#   · 월 정기권은 주간·야간·전일 세 가지다.
#   · 노상·노외가 같은 급지 요금표를 쓴다(포털 요금표에 구분이 없다).
PAJU_FEES = {
    1: {"base_min": 30, "base_fee": 600, "unit_min": 10, "unit_fee": 250, "day": 9_000,
        "month_day": 70_000, "month_night": 50_000, "month_all": 90_000},
    2: {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 200, "day": 8_000,
        "month_day": 60_000, "month_night": 40_000, "month_all": 80_000},
    3: {"base_min": 30, "base_fee": 400, "unit_min": 10, "unit_fee": 150, "day": 7_000,
        "month_day": 50_000, "month_night": 30_000, "month_all": 70_000},
}
# 관광지 주차장은 급지 요금이 아니라 종일 정액을 받는다(포털 요금안내 표).
PAJU_FLAT_DAY = 2_000
PAJU_TOURIST_URL_NOTE = "파주시 통합주차 포털 주차요금안내(관광지 주차장 종일 2,000원)"

# 유료 운영시간 밖과 주말·공휴일 무료 개방 — 파주시 통합주차포털 요금안내 표(2026-11-17).
PAJU_WEEKEND_FREE_NOTE = ("토요일·일요일·공휴일과 유료 운영시간 밖에는 요금이 발생하지 않습니다"
                          "(파주시 통합주차 포털)")
# 「파주시 주차장 설치 및 관리 조례」 제3조의3(주차요금의 감면 등) — 2026-11-17 확인.
#   · 100%     : 성실납세증 표지 차량(선정일부터 1년), 긴급자동차
#   · 2시간 면제 후 50% : 중증장애인, 국가유공자·상이자, 고엽제후유의증환자, 5·18부상자,
#                          병역명문가, 장기등·인체조직 기증 예우대상자, 의사상자 예우대상자
#                          (시에 주민등록이 있으면 전액 면제할 수 있다)
#   · 50%      : 경형자동차, 저공해·환경친화적 자동차, 모범자원봉사자, 경증장애인,
#                다자녀가정·경기 I-plus 카드, 임산부 탑승 차량, 1세 미만 자녀 양육 가정
#   · 감면이 겹치면 감면율이 높은 하나만 적용한다(제3조의3③).
PAJU_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·임산부·다자녀 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형자동차·저공해(환경친화적) 표지 차량·임산부 탑승 차량·다자녀가정(경기 I-plus 카드)"},
    {"label": "경증장애인·모범자원봉사자 50%", "rate": 0.5, "exempt_min": 0,
     "note": "장애의 정도가 심하지 않은 장애인(본인 운전·동승), 모범자원봉사자증 소지자 운전 차량"},
    {"label": "1세 미만 자녀 가정 50%", "rate": 0.5, "exempt_min": 0,
     "note": "출산 후 1년 이내 가정의 차량(2025-05-07 신설)"},
    {"label": "중증장애인·국가유공자 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "중증장애인·국가유공자·상이자·고엽제후유의증환자·5·18부상자·병역명문가·기증 예우대상자·의사상자(시 주민등록자는 면제)"},
    {"label": "성실납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "국세청장·경기도지사·시장이 교부한 성실납세증 표지 차량(1년)"},
]
# 포털 주차장 이름 → 표준데이터 주차장 이름. 노상·노외에 같은 이름(금촌2·금촌3·문산1·운정1)이
# 있어 유형(노외)까지 맞춰 찾는다.
PAJU_PORTAL_ALIAS = {
    "GTX-A 운정중앙역1 (환승)": "GTX-A 운정중앙역 1",
    "GTX-A 운정중앙역2 (환승_월정기)": "GTX-A 운정중앙역 2",
    "가람마을공원 (월정기)": "가람마을공원 공영주차장",
    "광탄경매시장": "광탄경매시장",
    "금촌2 (월정기)": "금촌2",
    "금촌2-17": "금촌2-17",
    "금촌3": "금촌3",
    "금촌로터리": "금촌로터리",
    "금촌역선로하부 (환승_월정기)": "금촌역 선로하부",
    "금촌통일시장1": "금촌통일시장",
    "문산1": "문산1",
    "문산자유시장": "문산자유시장",
    "봉일천 (월정기)": "봉일천 공영주차장",
    "산내마을2 (월정기)": "산내마을2",
    "야당역 (환승)": "야당역 환승",
    "운정1(월정기)": "운정1",
    "운정3 (월정기)": "운정3",
    "운정스타필드빌리지": "스타필드",
    "운정역 (환승_월정기)": "운정역환승주차장",
    "운정호수공원": "운정호수공원 공영주차장",
    "원앙길 (월정기)": "금촌 원앙길 공영주차장",
    "월롱역 (환승_월정기)": "월롱역 환승",
    "파주센트럴밸리 (월정기)": "파주센트럴벨리 공영주차장",
    "파주역 (환승_월정기)": "파주역 공영주차장",
}
# 포털에만 있고 표준데이터(기준일 2026-10-15)에 없는 주차장.
#   · 시청·시의회 청사 주차장과 감악산·마장호수·임진각 관광지 주차장은 포털이 유일한 공개 자료다.
#   · 좌표·면수·요금·운영시간은 포털 목록 스냅샷(2026-11-17)에서 그대로 옮겼다.
#   · 월롱임시공영주기장은 버스·대형차 주기장 성격이고, 놀이구름은 포털 요금안내 표에 없어 넣지 않았다.
PAJU_EXTRA_NAMES = ("시청주차장", "시의회주차장", "감악산 제3주차장", "감악산 제5주차장",
                    "마장호수 제1주차장", "임진각 주차장")
PAJU_EXTRA_NOTICE = {
    "시청주차장": "파주시청 청사 주차장입니다 — 민원인 무료시간은 안내데스크에 확인하세요",
    "시의회주차장": "파주시의회 청사 주차장입니다 — 방문 안내는 의회 사무국에 확인하세요",
    "감악산 제3주차장": "감악산 관광지 주차장 — 종일 2,000원, 연중무휴",
    "감악산 제5주차장": "감악산 힐링파크 인근 관광지 주차장 — 종일 2,000원, 연중무휴",
    "마장호수 제1주차장": "마장호수 출렁다리 관광지 주차장 — 종일 2,000원(08:00~18:00)",
    "임진각 주차장": "임진각 관광지 주차장 — 종일 2,000원(09:00~18:00)",
}


def paju_dong_of(text: str):
    """주소에서 파주시 법정동·읍·면을 뽑는다.

    ‘동패동 산 115-1’·‘(적성면,설마리)’처럼 지번 앞에 ‘산’이 붙거나 괄호·쉼표가 오므로,
    낱말 경계를 따지지 않고 이름이 들어 있는지로 찾는다(이름이 서로 겹치지 않는다).
    """
    t = re.sub(r"\s", "", text or "")
    for d in sorted(PAJU_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def paju_grade_from_fee(base_fee):
    return {600: 1, 500: 2, 400: 3}.get(base_fee or 0, 1)


def paju_hhmm(v):
    """포털의 ‘09:00’ 문자열 → 분. 00:00~00:00 은 24시간(운영 없음)으로 본다."""
    s = (v or "").strip()
    if not re.fullmatch(r"\d{2}:\d{2}", s):
        return None
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def paju_portal_hours(p):
    """포털 운영시간 → 사이트 hours/oper. 주말·공휴일은 ‘무료 개방’이라 24시간 연다."""
    s, e = paju_hhmm(p.get("WDAYS_START_TM")), paju_hhmm(p.get("WDAYS_END_TM"))
    full = ((p.get("ANYHOUR_RUN_YN") or "").strip() == "24시간운영함"
            or s is None or e is None or e <= s or (s == 0 and e >= 1439))
    win = {"weekday": {"open": True, "start": 0 if full else s, "end": 1440 if full else e,
                       "24h": full, "listed": True,
                       "raw": [p.get("WDAYS_START_TM") or "00:00", p.get("WDAYS_END_TM") or "24:00"]}}
    for k in ("sat", "sun"):
        win[k] = {"open": True, "start": 0, "end": 1440, "24h": True, "listed": True,
                  "raw": ["00:00", "24:00"]}
    return win, {"weekday": True, "sat": True, "sun": True}


def paju_fee_off(grade, portal=None, *, monthly_over=None):
    """파주시 요금 구조 → 사이트 공통 fee 객체(유료 노외).

    포털에 등록된 주차장별 기본시간·기본요금·간격·1일 상한·무료시간·정기권을 그대로 쓰고,
    포털에 없는 값은 조례 별표1의 급지 요금으로 채운다. 80분·90분·150분 기본시간은
    포털이 주차장별로 다르게 설정한 값이다(예: 시청 80분 1,000원·20분당 500원).
    """
    t = PAJU_FEES[grade]
    base_min, base_fee = t["base_min"], t["base_fee"]
    unit_min, unit_fee = t["unit_min"], t["unit_fee"]
    day, monthly = t["day"], t["month_all"]
    free_min = 10
    flat = False
    if portal:
        base_min = to_int(portal.get("DFLT_TM")) or base_min
        base_fee = to_int(portal.get("DFLT_AMT")) or base_fee
        unit_min = to_int(portal.get("INTVL_TM")) or unit_min
        uf = to_int(portal.get("INTVL_AMT"))
        if uf is not None:
            unit_fee = uf
        fm = to_int(portal.get("FREE_TM"))
        if fm is not None:
            free_min = fm
        day = to_int(portal.get("DAY_PARKING_AMT")) or day
        pt = to_int(portal.get("PERIOD_TICKET_AMT"))
        monthly = pt if pt else None
    if monthly_over is not None:
        monthly = monthly_over
    return {
        "type": "유료", "raw_type": "유료", "mixed": False, "grade": grade, "std_grade": None,
        "base_min": base_min, "base_fee": base_fee,
        "unit_min": unit_min, "unit_fee": unit_fee, "steps": None,
        # 포털의 ‘무료이용시간·회차시간’은 최초 N분을 빼고 계산하는 방식이다(김포시 1시간 무료와 같은 처리).
        "free_min": None,
        "deduct_min": free_min or None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": 24, "daily_fee": day,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": monthly,
        "monthly_day": t["month_day"], "monthly_night": t["month_night"], "monthly_all": monthly,
        "pay": "", "basis": None, "category": None, "portal_free_now": False,
        "flat_day": flat,
    }


def paju_fee_flat(portal):
    """관광지 주차장의 종일 정액(2,000원) 요금 객체."""
    day = to_int(portal.get("DAY_PARKING_AMT")) or PAJU_FLAT_DAY
    free_min = to_int(portal.get("FREE_TM")) or None
    return {
        # 관광지 주차장은 급지 요금이 아니라 종일 정액이라 급지를 두지 않는다.
        "type": "유료", "raw_type": "유료", "mixed": False, "grade": None, "std_grade": None,
        "base_min": 1440, "base_fee": day, "unit_min": 1440, "unit_fee": day, "steps": None,
        "free_min": None, "deduct_min": free_min,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": 24, "daily_fee": day,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "pay": "", "basis": None, "category": "tourist", "portal_free_now": False,
        "flat_day": True,
    }


def paju_free_fee():
    return {"type": "무료", "raw_type": "무료", "mixed": False, "grade": None, "std_grade": None,
            "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
            "steps": None, "free_min": None, "deduct_min": None, "cap_fee": None, "cap_src": None,
            "daily_hours": None, "daily_fee": None, "prepaid_day": None, "prepaid_weekend": None,
            "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
            "pay": "", "basis": "요금 구분 ‘무료’", "category": None, "portal_free_now": False,
            "std": None}


def load_paju_portal():
    """파주시 통합주차포털 주차장 목록 스냅샷 → {포털 이름: 항목}."""
    if not PAJU_PORTAL_JSON.exists():
        return {}
    return {(p.get("PARKING_NM") or "").strip(): p
            for p in json.loads(PAJU_PORTAL_JSON.read_text())["parkingList"]}


def build_paju():
    """파주시 공영주차장을 표준데이터 + 파주시 통합주차포털 + 조례 별표1로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 파주시 범위를 벗어난 행은 제외(껍데기 행).
      · 파주시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 읍·면·동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 읍·면·동 페이지는 카드가 3곳 이상인 지역만 만든다.
    요금은 조례 별표1(1~3급지, 30분 기본 뒤 10분 단위, 1일 상한)과 포털의 주차장별 설정
    (기본 80·90·150분, 최초 무료시간, 1일 상한, 월 정기권)을 적용하고, 운영시간은 포털의
    평일 운영시간과 ‘주말·공휴일 무료 개방’을 따른다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == PAJU_PROVIDER]
    portal = load_paju_portal()
    std_names = {(r.get("주차장명") or "").strip(): r for r in rows_city}
    portal_by_std = {}
    portal_unused = []
    for pname, ref in portal.items():
        target = PAJU_PORTAL_ALIAS.get(pname, pname)
        if target in std_names and (std_names[target].get("주차장유형") or "") != "노상":
            portal_by_std[target] = ref
        elif target in std_names:
            # 노상 구간(금촌 2·금촌 3·문산 1·운정 1)은 같은 이름의 노외 주차장과 다른 곳이다.
            portal_unused.append(pname)
        else:
            portal_unused.append(pname)

    lots, excluded, merged, hour_fixed, grade_fixed, fee_diff = [], [], [], [], [], []
    seen = {}
    card_no = street_no = 0

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        jibun_key = re.sub(r"\s", "", jibun)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif gimpo_name_key(name) and ("이름", gimpo_name_key(name), ptype, spaces) in seen:
            # 파주시는 ‘금촌 2’(노상)와 ‘금촌2’(노외)처럼 이름이 같은 다른 주차장이 있어
            # 이름만으로 묶지 않고 유형·면수까지 같을 때만 중복으로 본다.
            dup_key = ("이름", gimpo_name_key(name), ptype, spaces)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and gimpo_name_key(name):
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", gimpo_name_key(name), ptype, spaces)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (PAJU_BBOX[0] <= lat <= PAJU_BBOX[1]
                                      and PAJU_BBOX[2] <= lng <= PAJU_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = paju_dong_of(jibun) or paju_dong_of(road)
        dong_src = "지번주소" if paju_dong_of(jibun) else ("도로명주소" if paju_dong_of(road) else "없음")
        note = (r.get("특기사항") or "").strip()
        pay = (r.get("요금정보") or "").strip()
        std_grade = to_int(r.get("급지구분"))
        street = ptype == "노상"
        pref = portal_by_std.get(name)

        if street:
            win, oper, closed_note = parse_schedule(r, note)
            # 노상은 일요일 운영시간 칸이 없어 공휴일 칸(09:00~18:00)을 준용한다(원자료 한계, 화면에 적음).
            free_days = {"sat": False, "sun": False}
        elif pref:
            win, oper = paju_portal_hours(pref)
            # 포털 요금안내: 유료 노외는 토요일·일요일(공휴일) 무료 개방.
            free_days = {"sat": True, "sun": True}
        else:
            win, oper, closed_note = parse_schedule(r, note)
            free_days = {"sat": False, "sun": False}
        if not street:
            closed_note = False

        base_fee_reg = to_int(r.get("주차기본요금"))
        notice = None
        grade = (to_int(pref.get("GRADE")) if pref and to_int(pref.get("GRADE")) else None)
        if grade not in (1, 2, 3):
            grade = std_grade if std_grade in (1, 2, 3) else paju_grade_from_fee(base_fee_reg)
        if pref and grade != std_grade and std_grade in (1, 2, 3):
            grade_fixed.append(f"{name}: 표준데이터 {std_grade}급지 ↔ 포털 {grade}급지(포털 적용)")

        if street:
            street_no += 1
            lot_id = f"pj-s{street_no:03d}"
            if pay == "무료":
                fee = paju_free_fee()
                fee["grade"] = grade
            else:
                fee = paju_fee_off(grade, None, monthly_over=None)
                fee["monthly"] = None
                fee["monthly_all"] = None
                reg_day = to_int(r.get("1일주차권요금"))
                if reg_day:
                    fee["daily_fee"] = reg_day
                fee["free_min"] = None
                fee["deduct_min"] = None
                fee["basis"] = f"「파주시 주차장 설치 및 관리 조례」 별표1 노상 {grade}급지"
            free_min_note = None
        else:
            card_no += 1
            lot_id = f"pj-{card_no:03d}"
            if pay == "무료" and not pref:
                fee = paju_free_fee()
                fee["grade"] = grade
                free_min_note = None
            elif pref and (pref.get("PARKING_DIV_NM") == "관광"):
                fee = paju_fee_flat(pref)
                free_min_note = PAJU_WEEKEND_FREE_NOTE
            else:
                monthly_over = None
                if name == "시청주차장":
                    # 포털 정기권 10,000원은 청사 내부용으로 보이는 값이라 정기권을 적지 않는다.
                    monthly_over = None
                fee = paju_fee_off(grade, pref, monthly_over=monthly_over)
                if not pref:
                    # 포털에 없는 주차장은 월 정기권 판매 여부를 알 수 없어 비워 둔다.
                    fee["monthly"] = fee["monthly_all"] = None
                fee["basis"] = (f"「파주시 주차장 설치 및 관리 조례」 별표1 {grade}급지 · "
                                f"파주시 통합주차 포털 주차장별 요금(2026-11-17)")
                if name == "시청주차장":
                    fee["monthly"] = fee["monthly_all"] = None
                free_min_note = PAJU_WEEKEND_FREE_NOTE
                if pref and (pref.get("TRANS_YN") or "").strip() == "Y":
                    notice = ("환승주차장입니다 — 철도 이용 뒤 교통카드를 태그하면 환승요금(최초 30분 500원·"
                              "10분당 70원·1일 3,000원)이 적용됩니다(파주시 통합주차 포털 안내)")
                if not pref:
                    # 포털에 없는 유료 주차장 — 주말·공휴일 무료 개방 여부를 단정하지 않는다.
                    free_min_note = None
                    notice = ("파주시 통합주차 포털에 등록되지 않은 주차장입니다 — 주말·공휴일 무료 개방 "
                              "여부와 월 정기권은 파주시 주차관리과(031-940-4783)에 확인하세요")

        fee["std_grade"] = std_grade
        fee["pay"] = (r.get("결제방법") or "").strip()
        fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                      "base_fee": base_fee_reg,
                      "unit_min": to_int(r.get("추가단위시간")),
                      "unit_fee": to_int(r.get("추가단위요금")),
                      "day": to_int(r.get("1일주차권요금")),
                      "monthly": to_int(r.get("월정기권요금"))}
        if pay != "무료" and fee["std"]["base_fee"] and pref:
            std_pair = (fee["std"]["base_min"], fee["std"]["base_fee"])
            pr_pair = (to_int(pref.get("DFLT_TM")), to_int(pref.get("DFLT_AMT")))
            if std_pair != pr_pair:
                fee_diff.append(f"{name}: 등록 {std_pair[0]}분 {std_pair[1]}원 ↔ "
                                f"포털 {pr_pair[0]}분 {pr_pair[1]}원")
        if pay != "무료" and fee["std"]["base_fee"] and not pref:
            want = PAJU_FEES[grade]
            if (fee["std"]["base_min"], fee["std"]["base_fee"]) != (want["base_min"], want["base_fee"]):
                fee_diff.append(f"{name}: 등록 {fee['std']['base_min']}분 {fee['std']['base_fee']}원 ↔ "
                                f"적용 {want['base_min']}분 {want['base_fee']}원({grade}급지)")
        lots.append({
            "id": lot_id,
            "mgmt_no": mgmt,
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "파주시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip() or "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
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
            "free_window": None,
            "free_hour_note": free_min_note,
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": (pref or {}).get("PARKING_NM"),
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "파주시",
            "city_slug": "paju",
        })

    # 표준데이터에 없는 주차장(시청·시의회·감악산·마장호수·임진각) — 포털 목록으로 채운다.
    for pname in PAJU_EXTRA_NAMES:
        pref = portal.get(pname)
        if not pref:
            continue
        card_no += 1
        road = (pref.get("CELL_ADDR_LOAD") or pref.get("CELL_ADDR_JIBUN") or "").strip()
        dong = paju_dong_of(road)
        grade = to_int(pref.get("GRADE")) or 1
        tourist = (pref.get("PARKING_DIV_NM") == "관광")
        fee = paju_fee_flat(pref) if tourist else paju_fee_off(grade, pref)
        if pname == "시청주차장":
            fee["monthly"] = fee["monthly_all"] = None
        fee["basis"] = ("파주시 통합주차 포털 주차요금안내(관광지 종일 2,000원)" if tourist else
                        f"「파주시 주차장 설치 및 관리 조례」 별표1 {grade}급지 · "
                        f"파주시 통합주차 포털 주차장별 요금(2026-11-17)")
        fee["pay"] = (pref.get("PAY_METHOD") or "").strip()
        win, oper = paju_portal_hours(pref)
        if not tourist:
            win["sat"] = {"open": True, "start": 0, "end": 1440, "24h": True, "listed": True,
                          "raw": ["00:00", "24:00"]}
            win["sun"] = dict(win["sat"])
        try:
            lat = float(pref["LAT"]) if pref.get("LAT") else None
            lng = float(pref["LNG"]) if pref.get("LNG") else None
        except (TypeError, ValueError):
            lat = lng = None
        lots.append({
            "id": f"pj-{card_no:03d}", "mgmt_no": "", "src": "파주시 통합주차 포털",
            "list_mode": "card",
            "name": pname.replace(" (월정기)", ""), "gu": "파주시", "dong": dong,
            "dong_src": "도로명주소" if dong else "없음",
            "kind": "공영", "ptype": "노외",
            "addr_jibun": "", "addr_road": road, "road": None,
            "spaces": to_int(pref.get("CELL_CNT")),
            "tel": (pref.get("TEL_NO") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": "2026-11-17 (포털)",
            "manager": (pref.get("MNG_NM") or "").strip() or "파주시청",
            "note": "", "notice": PAJU_EXTRA_NOTICE.get(pname),
            "fee": fee, "oper": oper, "hours": win,
            # 관광지 주차장은 주말·공휴일에도 종일 2,000원을 받는다(포털 요금안내).
            "free_days": {"sat": False, "sun": False} if tourist else {"sat": True, "sun": True},
            "free_window": None,
            "free_hour_note": ("종일 2,000원 · 연중무휴 · 운영시간 밖은 무료로 개방합니다" if tourist
                               else PAJU_WEEKEND_FREE_NOTE),
            "closed_from_note": False,
            "disabled_area": "", "capa_detail": None,
            "portal_name": pname, "realtime": None, "udc_id": None,
            "price_key": fee["unit_fee"],
            "city": "파주시", "city_slug": "paju",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"pj-{i:03d}" if l["list_mode"] == "card" else f"pj-s{i:03d}"

    quality = check_quality_paju(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                 grade_fixed, fee_diff, portal, portal_by_std, portal_unused)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(PAJU_PORTAL_JSON).strftime("%Y-%m-%d %H:%M")
                           if PAJU_PORTAL_JSON.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "파주시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-15",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("파주시가 등록한 155행(제공기관명 '경기도 파주시', 노외 90·노상 65)을 읽었다. "
                             "이름·주소·운영시간·좌표·전화·관리번호와 등록요금 출처로 썼다."),
                },
                {
                    "id": "portal", "name": "파주시 통합주차 포털(파주파킹) 주차장 목록",
                    "org": "파주시·파주도시관광공사",
                    "url": "https://parking.paju.go.kr/api/parking/searchParkingList",
                    "file": PAJU_PORTAL_JSON.name,
                    "sha256": sha256(PAJU_PORTAL_JSON) if PAJU_PORTAL_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 조회",
                    "rows_total": len(portal), "rows_city": len(portal_by_std),
                    "fetched_at": _snapshot_time(PAJU_PORTAL_JSON).strftime("%Y-%m-%d %H:%M (KST)")
                                  if PAJU_PORTAL_JSON.exists() else None,
                    "note": ("유료 공영·관광 주차장 32곳의 급지(1~3급지)·기본시간·기본요금·10분/20분 "
                             "간격요금·1일 주차요금·최초 무료시간·월 정기권·평일 운영시간·좌표. "
                             "표준데이터 24곳과 이름으로 짝지었고, 시청·시의회·감악산·마장호수·임진각 6곳은 "
                             "포털에만 있어 포털 값으로 카드를 만들었다."),
                },
                {
                    "id": "fee", "name": "파주시 통합주차 포털 주차요금안내(급지별 요금 정책표)",
                    "org": "파주시(주차관리과)·파주도시관광공사",
                    "url": PAJU_PORTAL_URL,
                    "file": PAJU_FEE_TXT.name if PAJU_FEE_TXT.exists() else None,
                    "sha256": sha256(PAJU_FEE_TXT) if PAJU_FEE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": None,
                    "fetched_at": _snapshot_time(PAJU_FEE_TXT).strftime("%Y-%m-%d %H:%M (KST)")
                                  if PAJU_FEE_TXT.exists() else None,
                    "note": ("조례 제3조제1항 급지별 요금 정책표(1급지 30분 600원·10분당 250원·1일 9,000원, "
                             "2급지 500·200·8,000원, 3급지 400·150·7,000원, 월 정기권 주간·야간·전일)와 "
                             "주차장별 운영시간·무료이용시간·‘토·일·공휴일 무료 개방’ 확인용."),
                },
                {
                    "id": "ordinance", "name": "파주시 주차장 설치 및 관리 조례 (제3조·제3조의3)",
                    "org": "파주시",
                    "url": PAJU_ORDINANCE_URL,
                    "file": PAJU_ANNEX_TXT.name if PAJU_ANNEX_TXT.exists() else None,
                    "sha256": sha256(PAJU_ANNEX_TXT) if PAJU_ANNEX_TXT.exists() else None,
                    "license": "자치법규(공개)",
                    "base_date": "일부개정 2026-10-08 (조례 제2428호, 2027-01-01 시행)",
                    "rows_total": None,
                    "fetched_at": _sync_time(PAJU_ANNEX_TXT),
                    "note": ("주차요금(별표1)·감면 조항 원문. 중증장애인·국가유공자 등은 최초 2시간 면제 후 "
                             "50%, 경차·저공해·임산부·다자녀·경증장애인은 50%, 성실납세자는 1년 면제, "
                             "감면이 겹치면 감면율이 높은 하나만 적용(제3조의3). 2026-10-08 개정(제2428호)은 "
                             "2027-01-01 시행이라, 요금은 2026-11-17 현재 포털 게시값을 썼다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in PAJU_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "paju_grade",
            "unit_min": 10,
            "base_min": 30,
            "day_hours": 24,
            "applies": "2025-01-01 개편 요금 · 2026-11-17 포털 확인",
            "off": [{"grade": g, **t, "lots": 0} for g, t in sorted(PAJU_FEES.items())],
            "street": [{"grade": g, **t} for g, t in sorted(PAJU_FEES.items())],
            "tourist_day": PAJU_FLAT_DAY,
            "basis": ("「파주시 주차장 설치 및 관리 조례」 제3조제1항 별표1 · 파주시 통합주차 포털 "
                      "주차요금안내(2026-11-17 확인) · 주차장별 기본시간·무료시간은 포털 등록값"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["파주시"] | {
        "city": "파주시",
        "weekend_free_pages": False,
        "discounts": PAJU_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "paju_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def _sync_time(path: Path):
    """원자료 파일의 수집 시각(사이드카가 없으면 mtime)."""
    if path.exists():
        return _snapshot_time(path).strftime("%Y-%m-%d %H:%M (KST)")
    return None


def check_quality_paju(std_all, rows, lots, excluded, merged, hour_fixed, grade_fixed,
                       fee_diff, portal, portal_by_std, portal_unused):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    portal_only = [l["name"] for l in card if l.get("src") == "파주시 통합주차 포털"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_파주시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"]["std_grade"] for l in paid if l["fee"].get("std_grade"))),
        "포털_매칭": len(portal_by_std),
        "포털에만_있음": portal_only,
        "포털_미사용": [n for n in portal_unused if n not in PAJU_EXTRA_NAMES],
        "무료시간": dict(Counter(l["fee"].get("deduct_min") or l["fee"].get("free_min") for l in paid)),
        "운영시간_보정": hour_fixed,
        "급지_보정": grade_fixed,
        "등록값_차이": fee_diff,
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
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
        if q.get("민영_제외"):
            lines.append(f"- 공영 {q['원자료_양주시행수']}행만 실었고, 민영 주차장 {q['민영_제외']}행은 "
                         f"공영주차장 파인더라 제외")
        if city in ("평택시", "남양주시", "시흥시", "의정부시", "김포시", "파주시", "광주시", "하남시", "군포시", "광명시", "구리시", "오산시", "이천시", "안성시", "양주시", "포천시", "의왕시", "여주시", "동두천시", "과천시"):
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


# ---------------------------------------------------------------- 광주시 (T-03 Phase 14)
GWANGJU_PROVIDER = "경기도 광주시"
# 광주시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고 그 아래 읍·면·동 페이지를 둔다.
GWANGJU_DISTRICTS = [("광주시", "gwangju")]
GWANGJU_BBOX = (37.29, 37.50, 127.10, 127.45)   # 광주시 대략 경계(좌표 점검용)
# 광주시 법정동(동지역)과 읍·면 — 표준데이터 주소 세 번째 낱말이 지역 이름이다.
#   (행정동 경안동·송정동·광남동·탄벌동·신현동·능평동·오포1~2동은 법정동 여러 개를 묶은 이름이라
#    주소에는 법정동이 나온다. 오포읍은 2015년 폐지되어 법정동 문형동·매산동·양벌동 등으로 적힌다.)
GWANGJU_DONGS = ("경안동", "송정동", "역동", "유동", "직동", "신현동", "목동", "문형동",
                 "고산동", "장지동", "중대동", "매산동", "양벌동", "탄벌동", "삼동",
                 "쌍령동", "회덕동", "목현동", "갈평동", "능평동", "추자동", "태전동",
                 "초월읍", "곤지암읍", "퇴촌면", "남종면", "남한산성면", "도척면")

GWANGJU_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2111313"
GWANGJU_PORTAL_URL = "https://parking.gumc.or.kr/html/about/about_05"
GWANGJU_PORTAL_HOME = "https://parking.gumc.or.kr/html/main"
GWANGJU_PORTAL_LIST = "https://parking.gumc.or.kr/html/about/about_02"
GWANGJU_ANNEX1_TXT = RAW / "gwangju_ordinance_20260223_별표1.txt"
GWANGJU_ANNEX2_TXT = RAW / "gwangju_ordinance_20260223_별표2.txt"
GWANGJU_PORTAL_TXT = RAW / "parking.gumc.or.kr_요금안내_20261117.txt"
GWANGJU_ORDINANCE_NOTE = "시행 2026-02-23 (경기도광주시조례 제1757호, 일부개정)"

# 광주시 공영주차장 요금 — 「광주시 주차장 설치 및 관리 조례」 제5조제1항 별표1,
#   광주도시관리공사 통합주차관리 포털 ‘요금안내’(2026-11-17 확인).
#   · 최초 30분 기본요금 뒤 10분 단위로 붙는다(1급지 30분 800원·10분당 300원).
#   · 1일 주차요금이 상한이다(1급지 7,000원·2급지 5,000원).
#   · 월 정기권은 주·야간·주간·야간 세 가지다(1급지 70,000·50,000·40,000원).
#   · 노상·노외가 같은 급지 요금표를 쓴다(별표1·포털 요금표에 구분이 없다).
#   · 급지: 1급지 = 동지역, 2급지 = 1급지를 제외한 기타 지역 및 환승주차장.
GWANGJU_FEES = {
    1: {"base_min": 30, "base_fee": 800, "unit_min": 10, "unit_fee": 300, "day": 7_000,
        "month_day": 50_000, "month_night": 40_000, "month_all": 70_000},
    2: {"base_min": 30, "base_fee": 500, "unit_min": 10, "unit_fee": 200, "day": 5_000,
        "month_day": 40_000, "month_night": 20_000, "month_all": 50_000},
}
# 포털 요금표 ‘※ 최초 10분 미만(회차) 무료’ — 10분 이내에 나가면 요금이 없다.
GWANGJU_FREE_MIN = 10
# 정기권 할인(포털 ‘공영주차장 정기권 할인 요금표’, 조례 제6조) — 감면 대상 차량의 정기권 금액.
GWANGJU_MONTHLY_DISCOUNT = {
    "50": {1: {"month_all": 35_000, "month_day": 25_000, "month_night": 20_000},
           2: {"month_all": 25_000, "month_day": 20_000, "month_night": 10_000}},
    "60": {1: {"month_all": 28_000, "month_day": 20_000, "month_night": 16_000},
           2: {"month_all": 20_000, "month_day": 16_000, "month_night": 8_000}},
}
# 「광주시 주차장 설치 및 관리 조례」 제6조·별표2(2026-02-23 시행)와
#   광주도시관리공사 통합주차관리 포털 ‘공영주차장 요금 감면’(2026-11-17 확인).
#   · 표에 적힌 ‘감면율이 높은 하나만’ 적용한다(제6조②).
#   · 전기차는 조례 별표2가 ‘최초 1시간 면제 뒤 50%’, 포털은 ‘최초 2시간 면제 뒤 50%’로
#     안내가 달라, 계산은 조례(1시간)를 따르고 카드에 차이를 적는다.
GWANGJU_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·경증장애인 60%", "rate": 0.6, "exempt_min": 0,
     "note": "경형자동차, 장애의 정도가 심하지 않은 장애인의 자가운전 차량"},
    {"label": "저공해·임산부·다자녀 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "저공해자동차, 임산부 탑승 차량, 다자녀(경기아이플러스), 75세 이상 고령노인, 우수자원봉사자, 장기기증자, 병역명문가, 명예시민, 승용차요일제"},
    {"label": "전기차 1시간 면제 후 50%", "rate": 0.5, "exempt_min": 60,
     "note": "환경친화적 자동차 표지 부착 전기차 — 조례 별표2 기준(포털은 최초 2시간 면제로 안내)"},
    {"label": "국가유공자 4시간 면제 후 50%", "rate": 0.5, "exempt_min": 240,
     "note": "국가유공자·유족, 5·18민주유공자·유족(본인 소유 차량 직접 운전·동승)"},
    {"label": "중증장애인·성실납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "장애의 정도가 심한 장애인(자가운전·동승), 모범·유공·성실납세자 확인증 부착 차량(1년), 긴급·공무수행 차량"},
]
# 포털 ‘공영주차장 정보’가 유료로 안내하는 주차장 — 표준데이터(기준일 2026-04-17)는 무료로 등록했다.
#   · 두 자료가 어긋나므로 표준데이터의 무료 표기를 따르되 카드에 포털 안내를 함께 적는다.
GWANGJU_PORTAL_PAID_ONLY = {"곤지암역세권 공영주차장": "2급지", "경안동 (구) 약수터 공영주차장": "1급지"}
# 포털 급지 명단(2026-11-17) — 표준데이터 급지와 맞는지 확인하는 데 쓴다.
GWANGJU_PORTAL_GRADES = {
    1: ("경안동", "경안시장", "역동", "송정동 마을", "양벌동", "광주시호국보훈공원",
        "신현행정문화체육센터", "경안동 (구) 약수터"),
    2: ("곤지암배수펌프장", "상번천리", "광주역세권", "경안배수펌프장", "곤지암 제1",
        "곤지암역세권", "광주역 환승"),
}


def gwangju_dong_of(text: str):
    """주소에서 광주시 법정동·읍·면을 뽑는다.

    표준데이터 지번주소는 ‘경기도 광주시 {동·읍·면} {번지}’ 꼴이라 세 번째 낱말이 지역 이름이다.
    꼴이 다르면 법정동 목록에서 찾는다(이름이 서로 겹치지 않는다).
    """
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "광주시" and parts[2].endswith(("동", "읍", "면")):
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(GWANGJU_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def gwangju_fee(grade: int, *, daily_hours=24):
    """광주시 요금 구조 → 사이트 공통 fee 객체(유료)."""
    t = GWANGJU_FEES[grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False, "grade": grade, "std_grade": None,
        "base_min": t["base_min"], "base_fee": t["base_fee"],
        "unit_min": t["unit_min"], "unit_fee": t["unit_fee"], "steps": None,
        # 포털 ‘최초 10분 미만(회차) 무료’ — 10분 이내 출차는 0원, 그 뒤에는 기본요금부터 붙는다.
        "free_min": GWANGJU_FREE_MIN, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": daily_hours, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": t["month_all"],
        "monthly_day": t["month_day"], "monthly_night": t["month_night"], "monthly_all": t["month_all"],
        "pay": "", "basis": None, "category": None, "portal_free_now": False,
        "flat_day": False,
    }


def gwangju_free_fee():
    return {"type": "무료", "raw_type": "무료", "mixed": False, "grade": None, "std_grade": None,
            "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
            "steps": None, "free_min": None, "deduct_min": None, "cap_fee": None, "cap_src": None,
            "daily_hours": None, "daily_fee": None, "prepaid_day": None, "prepaid_weekend": None,
            "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
            "pay": "", "basis": "요금 구분 ‘무료’", "category": None, "portal_free_now": False,
            "std": None}


def build_gwangju():
    """광주시 공영주차장을 표준데이터 + 조례 별표1 + 광주도시관리공사 포털로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 광주시 범위를 벗어난 행은 제외(껍데기 행).
      · 광주시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 읍·면·동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 읍·면·동 페이지는 카드가 3곳 이상인 지역만 만든다.
    요금은 조례 별표1(1~2급지, 30분 기본 뒤 10분 단위, 1일 상한)과 포털의 ‘최초 10분 미만 무료’를 적용하고,
    운영시간은 표준데이터대로 24시간(연중)이다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GWANGJU_PROVIDER]
    lots, excluded, merged, hour_fixed, grade_fixed, fee_diff = [], [], [], [], [], []
    portal_paid_diff = []
    seen = {}
    card_no = street_no = 0

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        # 같은 주차장이 두 행으로 등록된 곳 — 지번·유형·면수가 같거나 이름·유형이 같으면 한 곳으로 묶는다.
        jibun_key = re.sub(r"\s", "", jibun)
        # 이름은 띄어쓰기만 지우고 괄호 숫자를 살린다 — ‘송정동 임시(1)’과 ‘송정동 임시(2)’는 다른 주차장이다.
        name_key = re.sub(r"\s+", "", name)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif name_key and ("이름", name_key, ptype) in seen:
            dup_key = ("이름", name_key, ptype)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and name_key:
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", name_key, ptype)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (GWANGJU_BBOX[0] <= lat <= GWANGJU_BBOX[1]
                                      and GWANGJU_BBOX[2] <= lng <= GWANGJU_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = gwangju_dong_of(jibun) or gwangju_dong_of(road)
        dong_src = "지번주소" if gwangju_dong_of(jibun) else ("도로명주소" if gwangju_dong_of(road) else "없음")
        note = (r.get("특기사항") or "").strip()
        pay = (r.get("요금정보") or "").strip()
        std_grade = to_int(r.get("급지구분"))
        street = ptype == "노상"

        win, oper, closed_note = parse_schedule(r, note)
        if not street:
            closed_note = False
        # 표준데이터가 24시간(00:00~23:59)으로 등록한 것을 그대로 쓰고, 24시간이 아니면 사실을 남긴다.
        if not all(win[k]["open"] and win[k]["24h"] for k in ("weekday", "sat", "sun")):
            hour_fixed.append(f"{name}: 표준데이터 운영시간 {r.get('운영요일') or '—'} "
                              f"{r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''}")

        base_fee_reg = to_int(r.get("주차기본요금"))
        grade = std_grade if std_grade in (1, 2) else ({800: 1, 500: 2}.get(base_fee_reg or 0, 1))
        if std_grade not in (1, 2) and base_fee_reg:
            grade_fixed.append(f"{name}: 표준데이터 급지 없음 → 등록 기본요금 {base_fee_reg:,}원으로 {grade}급지 판정")
        if grade == 2 and dong and not dong.endswith(("읍", "면")) and \
                name not in ("광주역세권 공영주차장", "경안배수펌프장 공영주차장"):
            grade_fixed.append(f"{name}: 동지역({dong})인데 2급지로 등록(조례 1급지 원칙, 시장이 조정 가능)")

        notice = None
        if name in GWANGJU_PORTAL_PAID_ONLY:
            portal_paid_diff.append(f"{name}: 표준데이터 무료 ↔ 포털 유료({GWANGJU_PORTAL_PAID_ONLY[name]})")
            notice = (f"광주도시관리공사 통합주차관리 포털은 이 주차장을 유료"
                      f"({GWANGJU_PORTAL_PAID_ONLY[name]})로 안내합니다 — 표준데이터(기준일 "
                      f"{r.get('데이터기준일자') or '2026-04-17'})는 무료로 등록되어 있어, 현장 요금 표지를 확인하세요")

        if street:
            street_no += 1
            lot_id = f"gj-s{street_no:03d}"
            if pay == "무료":
                fee = gwangju_free_fee()
                fee["grade"] = grade
            else:
                fee = gwangju_fee(grade)
                reg_day = to_int(r.get("1일주차권요금"))
                if reg_day:
                    fee["daily_fee"] = reg_day
                fee["basis"] = f"「광주시 주차장 설치 및 관리 조례」 별표1 노상 {grade}급지"
        else:
            card_no += 1
            lot_id = f"gj-{card_no:03d}"
            if pay == "무료":
                fee = gwangju_free_fee()
                fee["grade"] = grade
            else:
                fee = gwangju_fee(grade)
                fee["basis"] = (f"「광주시 주차장 설치 및 관리 조례」 별표1 노외 {grade}급지 · "
                                f"광주도시관리공사 통합주차관리 요금안내(2026-11-17)")
                std_month = to_int(r.get("월정기권요금"))
                if std_month and std_month != fee["monthly"]:
                    fee["monthly"] = std_month
                    fee_diff.append(f"{name}: 등록 월정기권 {std_month:,}원 ↔ 조례 "
                                    f"{GWANGJU_FEES[grade]['month_all']:,}원")

        fee["std_grade"] = std_grade
        fee["pay"] = (r.get("결제방법") or "").strip()
        fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                      "base_fee": base_fee_reg,
                      "unit_min": to_int(r.get("추가단위시간")),
                      "unit_fee": to_int(r.get("추가단위요금")),
                      "day": to_int(r.get("1일주차권요금")),
                      "monthly": to_int(r.get("월정기권요금"))}
        if pay != "무료" and fee["std"]["base_fee"]:
            want = GWANGJU_FEES[grade]
            if (fee["std"]["base_min"], fee["std"]["base_fee"]) != (want["base_min"], want["base_fee"]):
                fee_diff.append(f"{name}: 등록 {fee['std']['base_min']}분 {fee['std']['base_fee']}원 ↔ "
                                f"적용 {want['base_min']}분 {want['base_fee']}원({grade}급지)")
        lots.append({
            "id": lot_id,
            "mgmt_no": mgmt,
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "광주시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip() or "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
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
            "free_days": {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": ("최초 10분 미만(회차)은 무료입니다 — 24시간 운영, 요금은 10분 단위로 붙습니다"
                               if fee["type"] == "유료" else None),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "광주시",
            "city_slug": "gwangju",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"gj-{i:03d}" if l["list_mode"] == "card" else f"gj-s{i:03d}"

    quality = check_quality_gwangju(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                    grade_fixed, fee_diff, portal_paid_diff)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(GWANGJU_PORTAL_TXT).strftime("%Y-%m-%d %H:%M")
                           if GWANGJU_PORTAL_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "광주시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-17",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 광주시가 등록한 55행(노외 45·노상 10, 유료 12·무료 43)을 읽었다. "
                             "이름·주소·운영시간·좌표·전화·관리번호와 등록요금 출처로 썼다."),
                },
                {
                    "id": "portal", "name": "광주도시관리공사 통합주차관리 요금안내",
                    "org": "광주도시관리공사",
                    "url": GWANGJU_PORTAL_URL,
                    "file": GWANGJU_PORTAL_TXT.name if GWANGJU_PORTAL_TXT.exists() else None,
                    "sha256": sha256(GWANGJU_PORTAL_TXT) if GWANGJU_PORTAL_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": None,
                    "fetched_at": _sync_time(GWANGJU_PORTAL_TXT),
                    "note": ("1~2급지 요금표(30분 800·500원, 10분당 300·200원, 1일 7,000·5,000원, "
                             "월 정기권 주·야간·주간·야간), ‘최초 10분 미만(회차) 무료’, 급지별 주차장 명단, "
                             "정기권 할인(50·60%)과 요금 감면 표, 주차 할인권·거주자우선주차 요금 확인용. "
                             "같은 포털의 ‘공영주차장 정보’에서 유료 15곳·무료 39곳과 주차장별 면수·급지·24시간 운영을 "
                             "대조했다(경안배수펌프장 240면·2급지 일치)."),
                },
                {
                    "id": "ordinance", "name": "광주시 주차장 설치 및 관리 조례 (제5조·제6조, 별표1·별표2)",
                    "org": "광주시",
                    "url": GWANGJU_ORDINANCE_URL,
                    "file": GWANGJU_ANNEX1_TXT.name if GWANGJU_ANNEX1_TXT.exists() else None,
                    "sha256": sha256(GWANGJU_ANNEX1_TXT) if GWANGJU_ANNEX1_TXT.exists() else None,
                    "license": "자치법규(공개)",
                    "base_date": GWANGJU_ORDINANCE_NOTE,
                    "rows_total": None,
                    "fetched_at": _sync_time(GWANGJU_ANNEX1_TXT),
                    "note": ("공영주차장 주차요금표(별표1: 노상·노외 1~2급지, 최초 30분·10분당·1일 주차권·"
                             "월 정기권 주간·야간·주야간, 주간 4~10월 08:00~20:00·11~3월 09:00~19:30, "
                             "1급지 동지역·2급지 기타 지역 및 환승주차장)와 요금 감면(별표2: 긴급·공무수행·"
                             "중증장애인 면제, 경차·경증장애인 60%, 저공해·임산부·다자녀·75세 이상 50%, "
                             "국가유공자 4시간 면제 후 50%, 전기차 1시간 면제 후 50%) 원문."),
                },
                {
                    "id": "annex2", "name": "광주시 주차장 설치 및 관리 조례 [별표 2] 감면대상 및 감면기준",
                    "org": "광주시",
                    "url": GWANGJU_ORDINANCE_URL,
                    "file": GWANGJU_ANNEX2_TXT.name if GWANGJU_ANNEX2_TXT.exists() else None,
                    "sha256": sha256(GWANGJU_ANNEX2_TXT) if GWANGJU_ANNEX2_TXT.exists() else None,
                    "license": "자치법규(공개)",
                    "base_date": GWANGJU_ORDINANCE_NOTE,
                    "rows_total": None,
                    "fetched_at": _sync_time(GWANGJU_ANNEX2_TXT),
                    "note": ("감면 24개 항목의 감면율과 확인(증빙) 방법. 감면이 겹치면 감면율이 높은 하나만 "
                             "적용한다(제6조②)."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GWANGJU_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "gwangju_grade",
            "unit_min": 10,
            "base_min": 30,
            "day_hours": 24,
            "free_min": GWANGJU_FREE_MIN,
            "applies": GWANGJU_ORDINANCE_NOTE + " · 2026-11-17 포털 확인",
            "off": [{"grade": g, **t, "lots": 0} for g, t in sorted(GWANGJU_FEES.items())],
            "street": [{"grade": g, **t} for g, t in sorted(GWANGJU_FEES.items())],
            "monthly_discount": GWANGJU_MONTHLY_DISCOUNT,
            "grade_targets": {"1": "동지역", "2": "동지역 밖 읍·면과 환승주차장"},
            "grade_lots_1": ["경안동", "경안시장", "역동", "송정동 마을", "양벌동", "광주시호국보훈공원",
                             "신현행정문화체육센터", "경안동 (구) 약수터"],
            "grade_lots_2": ["곤지암배수펌프장", "상번천리", "광주역세권", "경안배수펌프장", "곤지암 제1",
                             "곤지암역세권", "광주역 환승"],
            "basis": ("「광주시 주차장 설치 및 관리 조례」 제5조제1항 별표1 · 광주도시관리공사 "
                      "통합주차관리 요금안내(2026-11-17 확인)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["광주시"] | {
        "city": "광주시",
        "weekend_free_pages": False,
        "discounts": GWANGJU_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "gwangju_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_gwangju(std_all, rows, lots, excluded, merged, hour_fixed, grade_fixed,
                          fee_diff, portal_paid_diff):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_광주시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"]["std_grade"] for l in paid if l["fee"].get("std_grade"))),
        "10분무료_적용": len([l for l in paid if l["fee"].get("free_min")]),
        "운영시간_보정": hour_fixed,
        "급지_보정": grade_fixed,
        "등록값_차이": fee_diff,
        "포털_유료_차이": portal_paid_diff,
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 하남시 (T-03 Phase 15)
HANAM_PROVIDER = "경기도 하남시"
# 하남시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 동 페이지를 둔다.
HANAM_DISTRICTS = [("하남시", "hanam")]
HANAM_BBOX = (37.47, 37.60, 127.13, 127.26)   # 하남시 대략 경계(좌표 점검용)
# 하남시 법정동 24개 — 표준데이터 지번주소 세 번째 낱말이 법정동이다.
#   (행정동 천현동·신장1·2동·덕풍1~3동·미사1~3동·감북동·감일동·위례동·춘궁동·초이동은
#    여러 법정동을 묶거나 한 법정동을 나눈 이름이라 주소에는 법정동이 적힌다.)
HANAM_DONGS = ("감북동", "감이동", "감일동", "광암동", "교산동", "당정동", "덕풍동", "망월동",
               "미사동", "배알미동", "상사창동", "상산곡동", "선동", "신장동", "창우동",
               "천현동", "초이동", "초일동", "춘궁동", "풍산동", "하사창동", "하산곡동",
               "학암동", "항동")

HANAM_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1844801"
HANAM_FEE_URL = "https://www.hanam.go.kr/www/contents.do?key=5561"
HANAM_LIST_URL = "https://www.hanam.go.kr/sotong/contents.do?key=11737"
HANAM_CORP_URL = "https://www.huic.co.kr/www/contents.do?key=147"
HANAM_DIRECT_URL = "https://www.huic.co.kr/www/contents.do?key=149"
HANAM_FEE_TXT = RAW / "hanam.go.kr_주차요금정보_20261117.txt"
HANAM_LIST_TXT = RAW / "hanam.go.kr_공영주차장현황_20261117.txt"
HANAM_CORP_TXT = RAW / "huic.co.kr_공영주차장현황_20261117.txt"
HANAM_DIRECT_TXT = RAW / "huic.co.kr_직영주차장_20261117.txt"
HANAM_GEOCODE_JSON = RAW / "huic.co.kr_지오코딩_20261117.json"
HANAM_ORDINANCE_NOTE = "시행 2023-08-04 (경기도하남시조례 제2192호, 일부개정)"

# 하남시 공영주차장 요금 — 「하남시 주차장 조례」 [별표 1] 공영주차장 주차요금표(제3조제1항 관련)와
#   하남시청 ‘주차요금 정보’(최종수정 2026-10-15) · 하남도시공사 공영주차장 요금표(2026-11-17 확인).
#   · 1~3급지, 최초 30분 기본요금 뒤 10분 단위로 붙는다(1급지 30분 800원·10분당 300원).
#   · 노상과 노외의 30분·10분 요율은 같지만 1일 주차권이 다르다(1급지 노상 5,000 ↔ 노외 7,000원).
#   · 월 정기권은 주간·야간·주야간 세 가지이고 급지마다 같다(1급지 50,000·40,000·70,000원).
#   · 주거지 전용(거주자우선주차) 구역은 주간 무료 개방, 야간 정기권 20,000원·전용 24시간 30,000원.
HANAM_FEES = {
    "노외": {
        1: {"base_fee": 800, "unit_fee": 300, "day": 7_000,
            "month_day": 50_000, "month_night": 40_000, "month_all": 70_000},
        2: {"base_fee": 600, "unit_fee": 200, "day": 6_000,
            "month_day": 40_000, "month_night": 30_000, "month_all": 50_000},
        3: {"base_fee": 400, "unit_fee": 100, "day": 4_000,
            "month_day": 30_000, "month_night": 20_000, "month_all": 40_000},
    },
    "노상": {
        1: {"base_fee": 800, "unit_fee": 300, "day": 5_000,
            "month_day": 50_000, "month_night": 40_000, "month_all": 70_000},
        2: {"base_fee": 600, "unit_fee": 200, "day": 4_000,
            "month_day": 40_000, "month_night": 30_000, "month_all": 50_000},
        3: {"base_fee": 400, "unit_fee": 100, "day": 3_000,
            "month_day": 30_000, "month_night": 20_000, "month_all": 40_000},
    },
}
HANAM_BASE_MIN = 30
HANAM_UNIT_MIN = 10
HANAM_RESIDENT_MONTHLY = {"month_day": 20_000, "month_night": 20_000, "month_all": 30_000}
HANAM_SEARCH_DAY = 2_000      # 검단산(현충탑 진입로) 노상 — 시간 요금 없이 전일 2,000원

# 하남시 ‘주차요금 정보’(2026-10-15)의 감면 표.
#   · 모범·유공·성실납세자는 면제(증서 발급일부터 1년), 경차(1,000cc 미만)·저공해는 50%,
#     부제운행 20%, 국가유공자·장애인·다자녀·5·18·병역명문가·장기기증자·다문화가족·우수기업은
#     최초 2시간 무료 뒤 50%, 환경친화적 자동차는 50%(당일 충전 영수증 제시 시 최초 2시간 면제).
HANAM_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해 50%", "rate": 0.5, "exempt_min": 0,
     "note": "배기량 1,000cc 미만 경형자동차, 수도권 대기환경 개선 특별법에 따른 저공해자동차 표지 부착 차량"},
    {"label": "부제운행 20%", "rate": 0.2, "exempt_min": 0, "note": "승용차부제 운행 차량"},
    {"label": "국가유공자·장애인 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "국가유공자 증서 소지자가 탑승한 차량, 장애인 등록증 소지자가 탑승한 차량, 다자녀가정우대카드(경기I-plus), 5·18민주유공자, 병역명문가, 장기등 기증자, 다문화가족, 우수기업 임직원 차량"},
    {"label": "전기차 50%", "rate": 0.5, "exempt_min": 0,
     "note": "환경친화적 자동차 표지 부착 차량 — 당일 충전하고 영수증을 제시하면 최초 2시간 면제(현장 확인)"},
    {"label": "모범·성실납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": "모범납세자·유공납세자·성실납세자 증서(스티커) 부착 차량 — 교부일부터 1년"},
]
# 하남도시공사 ‘공영주차장’ 현황(위탁 16곳)의 급지·면수 — 표준데이터와 대조해 카드에 차이를 적는다.
HANAM_CORP_LOTS = {
    "신장동 공영주차장": (1, 89),
    "덕풍공원 제1공영주차장": (3, 129),
    "덕풍공원 제2공영주차장": (3, 199),
    "덕풍공원 제3공영주차장": (3, 213),
    "덕풍어린이공원 공영주차장": (3, 47),
    "덕풍수리골 공영주차장": (2, 69),
    "하남덕풍 경기행복주택 공영주차장": (2, 98),
    "감일제1공영주차장": (1, 57),
    "감일제2공영주차장": (1, 41),
    "감일제3공영주차장": (1, 39),
    "천현동꿈나무공원 공영주차장": (3, 110),
    "덕풍스포츠센터 공영주차장": (1, 95),
    "덕풍소공원 공영주차장": (2, 18),
    "현충탑 진입로": (3, 95),
    "미사리대형차전용주차장": (3, 26),
    "초광산단로 공영주차장": (1, 21),
}
# 하남도시공사가 직접 운영하는 미사중앙 제1·2주차장 — 표준데이터(기준일 2026-04-16)에 없어
#   공사 ‘직영주차장’ 현황으로 카드를 만들었다(2023-12-01 판 표준데이터에는 있던 행이다).
HANAM_DIRECT_LOTS = [
    {"name": "미사중앙제1주차장", "jibun": "경기도 하남시 망월동 1086", "spaces": 48, "grade": 1,
     "tel": "031-791-9580"},
    {"name": "미사중앙제2주차장", "jibun": "경기도 하남시 망월동 1090", "spaces": 44, "grade": 1,
     "tel": "031-791-9580"},
]
# 주소로 법정동을 찾지 못한 행의 보정(공사 현황 ‘신장로 228번길 5 (덕풍동)’).
HANAM_DONG_OVERRIDE = {"덕풍수리골 공영주차장": ("덕풍동", "공사 현황 ‘신장로 228번길 5 (덕풍동)’")}
# 시간 주차요금 없이 정기권만 받는 주차장 — 0원이 아니라 ‘요금 미상(정기권 전용)’으로 둔다.
HANAM_TICKET_ONLY = {
    "덕풍스포츠센터 공영주차장": ("거주자·직장인 정기권 위주로 운영합니다 — 야간(18:00~익일 09:00) "
                                  "월 40,000원, 주말 주간 8일권 13,330원(하남도시공사 요금표). "
                                  "일반 시간 주차요금은 게시되어 있지 않아 현장 확인이 필요합니다"),
    "미사리대형차전용주차장": ("대형차 전용 주차장입니다 — 월 정기권 대형차 주간 90,000원·야간 60,000원·"
                                "주야간 120,000원(하남도시공사 요금표). 시간제 주차는 받지 않습니다"),
    "초광산단로 공영주차장": ("월 정기권(전용 24시간) 70,000원만 받고 시간제 주차요금은 게시되어 있지 않습니다"
                              "(하남도시공사 요금표). 현장 확인이 필요합니다"),
}


def hanam_dong_of(text: str):
    """주소에서 하남시 법정동을 뽑는다.

    표준데이터 지번주소는 ‘경기도 하남시 {법정동} {번지}’ 꼴이라 세 번째 낱말이 법정동이다.
    꼴이 다르면 법정동 목록에서 찾는다(이름이 서로 겹치지 않는다).
    """
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "하남시" and parts[2].endswith("동") and parts[2] in HANAM_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(HANAM_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def hanam_fee(kind: str, grade: int, *, daily_hours=24):
    """하남시 요금 구조 → 사이트 공통 fee 객체(유료). kind 는 ‘노외’·‘노상’."""
    t = HANAM_FEES[kind][grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False, "grade": grade, "std_grade": None,
        "base_min": HANAM_BASE_MIN, "base_fee": t["base_fee"],
        "unit_min": HANAM_UNIT_MIN, "unit_fee": t["unit_fee"], "steps": None,
        "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": daily_hours, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": t["month_all"],
        "monthly_day": t["month_day"], "monthly_night": t["month_night"], "monthly_all": t["month_all"],
        "pay": "", "basis": f"「하남시 주차장 조례」 [별표1] {kind} {grade}급지", "category": None,
        "portal_free_now": False, "flat_day": False, "ticket_only": False,
    }


def hanam_free_fee(**extra):
    fee = {"type": "무료", "raw_type": "무료", "mixed": False, "grade": None, "std_grade": None,
           "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
           "steps": None, "free_min": None, "deduct_min": None, "cap_fee": None, "cap_src": None,
           "daily_hours": None, "daily_fee": None, "prepaid_day": None, "prepaid_weekend": None,
           "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
           "pay": "", "basis": "요금 구분 ‘무료’", "category": None, "portal_free_now": False,
           "flat_day": False, "ticket_only": False, "std": None}
    fee.update(extra)
    return fee


def hanam_day_fee(day_fee: int):
    """시간 요금 없이 전일 정액만 받는 주차장(검단산 노상 2,000원)."""
    return {"type": "유료", "raw_type": "혼합", "mixed": True, "grade": 3, "std_grade": None,
            "base_min": 1440, "base_fee": day_fee, "unit_min": 1440, "unit_fee": day_fee,
            "steps": None, "free_min": None, "deduct_min": None,
            "cap_fee": None, "cap_src": "조례 1일 주차요금",
            "daily_hours": 24, "daily_fee": day_fee,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
            "pay": "", "basis": "하남도시공사 공영주차장 요금표(전일 2,000원)", "category": None,
            "portal_free_now": False, "flat_day": True, "ticket_only": False}


def hanam_ticket_fee(grade, kind, monthly=None, raw_type="혼합"):
    """정기권만 받는 주차장 → ‘요금 미상’(시간 주차요금 없음)."""
    return {"type": "미상", "raw_type": raw_type, "mixed": raw_type == "혼합", "grade": grade,
            "std_grade": None, "base_min": None, "base_fee": None, "unit_min": None,
            "unit_fee": None, "steps": None, "free_min": None, "deduct_min": None,
            "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None, "monthly": monthly,
            "monthly_day": None, "monthly_night": None, "monthly_all": None,
            "pay": "", "basis": f"정기권 전용 — {kind} {grade}급지", "category": None,
            "portal_free_now": False, "flat_day": False, "ticket_only": True}


def build_hanam():
    """하남시 공영주차장을 표준데이터 + 시 요금 정보 + 하남도시공사 현황으로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 하남시 범위를 벗어난 행은 제외(껍데기 행).
      · 하남시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다.
    요금은 조례 별표1(1~3급지, 30분 기본 뒤 10분 단위, 노상·노외 1일 주차권이 다름)을 적용하고,
    운영시간은 표준데이터대로 24시간(연중) 또는 09:00~18:00(주거지 전용·일부 노상)이다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == HANAM_PROVIDER]
    lots, excluded, merged, hour_fixed, grade_fixed, fee_diff, space_diff = [], [], [], [], [], [], []
    corp_missing = []
    seen = {}
    card_no = street_no = 0
    geocode = {g["name"]: (g["lat"], g["lng"]) for g in
               json.loads(HANAM_GEOCODE_JSON.read_text())["rows"]} if HANAM_GEOCODE_JSON.exists() else {}

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        # 같은 주차장이 두 행으로 등록된 곳 — 지번·유형·면수가 같거나 이름·유형이 같으면 한 곳으로 묶는다.
        jibun_key = re.sub(r"\s", "", jibun)
        name_key = re.sub(r"\s+", "", name)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif name_key and ("이름", name_key, ptype) in seen:
            dup_key = ("이름", name_key, ptype)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and name_key:
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", name_key, ptype)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (HANAM_BBOX[0] <= lat <= HANAM_BBOX[1]
                                      and HANAM_BBOX[2] <= lng <= HANAM_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = hanam_dong_of(jibun) or hanam_dong_of(road)
        dong_src = "지번주소" if hanam_dong_of(jibun) else ("도로명주소" if hanam_dong_of(road) else "없음")
        if not dong and name in HANAM_DONG_OVERRIDE:
            dong, why = HANAM_DONG_OVERRIDE[name]
            dong_src = f"보정({why})"
        note = (r.get("특기사항") or "").strip()
        pay = (r.get("요금정보") or "").strip()
        std_grade = to_int(r.get("급지구분"))
        street = ptype == "노상"

        win, oper, closed_note = parse_schedule(r, note)
        if street:
            closed_note = False
        # 표준데이터 운영시간을 그대로 쓰고, 24시간이 아니면 그 사실을 남긴다.
        if not all(win[k]["open"] and win[k]["24h"] for k in ("weekday", "sat", "sun")):
            hour_fixed.append(f"{name}: 표준데이터 운영시간 {r.get('운영요일') or '—'} "
                              f"{r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''}")

        base_fee_reg = to_int(r.get("주차기본요금"))
        grade = std_grade if std_grade in (1, 2, 3) else ({800: 1, 600: 2, 400: 3}.get(base_fee_reg or 0, 1))
        if std_grade not in (1, 2, 3):
            grade_fixed.append(f"{name}: 표준데이터 급지 없음 → 등록 기본요금 {base_fee_reg:,}원으로 {grade}급지 판정"
                               if base_fee_reg else f"{name}: 표준데이터 급지 없음 → 1급지로 두고 현장 확인")
        corp = HANAM_CORP_LOTS.get(name)
        if corp is None:
            corp_missing.append(name)
        else:
            if corp[0] != grade:
                grade_fixed.append(f"{name}: 표준데이터 {grade}급지 ↔ 공사 현황 {corp[0]}급지")
            if corp[1] != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 공사 현황 {corp[1]}면")

        kind = "노상" if street else "노외"
        # 요금 갈래: 무료 / 주거지 전용(주간 무료 개방) / 정기권 전용 / 일반 급지 요금.
        resident = pay == "혼합" and name not in HANAM_TICKET_ONLY
        if street:
            street_no += 1
            lot_id = f"hn-s{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"hn-{card_no:03d}"

        if name == "현충탑 진입로":
            # 검단산 노상 — 시간 요금 없이 전일 2,000원(공사 요금표).
            fee = hanam_day_fee(HANAM_SEARCH_DAY)
            fee["grade"] = grade
        elif name in HANAM_TICKET_ONLY:
            monthly = to_int(r.get("월정기권요금"))
            fee = hanam_ticket_fee(grade, kind, monthly=monthly, raw_type=pay or "혼합")
        elif resident:
            fee = hanam_free_fee(grade=grade, raw_type="혼합", mixed=True, category="resident",
                                 monthly=HANAM_RESIDENT_MONTHLY["month_all"],
                                 monthly_day=HANAM_RESIDENT_MONTHLY["month_day"],
                                 monthly_night=HANAM_RESIDENT_MONTHLY["month_night"],
                                 monthly_all=HANAM_RESIDENT_MONTHLY["month_all"],
                                 basis="주거지 전용(거주자우선주차) — 주간 무료 개방")
        elif pay == "무료":
            fee = hanam_free_fee()
            fee["grade"] = grade
        else:
            fee = hanam_fee(kind, grade)
            fee["basis"] = (f"「하남시 주차장 조례」 [별표1] {kind} {grade}급지 · "
                            f"하남시 주차요금 정보(2026-10-15)")
            reg_day = to_int(r.get("1일주차권요금"))
            if reg_day and reg_day != fee["daily_fee"]:
                fee_diff.append(f"{name}: 등록 1일 주차권 {reg_day:,}원 ↔ 조례 {kind} {grade}급지 "
                                f"{fee['daily_fee']:,}원")
        fee["std_grade"] = std_grade
        fee["pay"] = (r.get("결제방법") or "").strip()
        fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                      "base_fee": base_fee_reg,
                      "unit_min": to_int(r.get("추가단위시간")),
                      "unit_fee": to_int(r.get("추가단위요금")),
                      "day": to_int(r.get("1일주차권요금")),
                      "monthly": to_int(r.get("월정기권요금"))}
        if fee["type"] == "유료" and not fee.get("flat_day") and base_fee_reg:
            want = HANAM_FEES[kind][grade]
            if (fee["std"]["base_min"], base_fee_reg) != (HANAM_BASE_MIN, want["base_fee"]):
                fee_diff.append(f"{name}: 등록 {fee['std']['base_min']}분 {base_fee_reg:,}원 ↔ "
                                f"적용 {HANAM_BASE_MIN}분 {want['base_fee']:,}원({kind} {grade}급지)")

        # 주거지 전용 구역은 카드의 ‘무료’ 줄(build_site.free_note)에 안내를 적으므로 notice 는 두지 않는다.
        notice = None
        if name in HANAM_TICKET_ONLY:
            notice = HANAM_TICKET_ONLY[name]
        if name == "현충탑 진입로":
            notice = ("하남도시공사는 이 노상 구간을 ‘검단산 공영주차장’으로 안내합니다 — "
                      "시간 요금 없이 전일 2,000원입니다(2026-11-17 확인)")
        if name == "에코1단지 주변":
            notice = ("표준데이터(기준일 2026-04-16)는 유료(급지 2)로, 하남시 공영주차장 현황"
                      "(2024-06-10)은 급지 미지정·무료 운영으로 적고 있습니다 — 방문 전 현장 표지를 확인하세요")
        if corp and corp[1] != spaces:
            notice = ((notice + " · ") if notice else "") + \
                f"하남도시공사 현황은 {corp[1]}면으로 안내합니다(표준데이터 {spaces}면)"

        lots.append({
            "id": lot_id,
            "mgmt_no": mgmt,
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "하남시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip() or "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip() or "하남시",
            "note": note,
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": None,
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "하남시",
            "city_slug": "hanam",
        })

    # 표준데이터에 없는 하남도시공사 직영 2곳 — 공사 ‘직영주차장’ 현황·좌표(카카오맵 지오코딩).
    for d in HANAM_DIRECT_LOTS:
        lat, lng = geocode.get(d["name"], (None, None))
        win = {k: {"open": True, "start": 0, "end": 1440, "24h": True, "listed": True,
                   "raw": ["00:00", "24:00"]} for k in ("weekday", "sat", "sun")}
        fee = hanam_fee("노외", d["grade"])
        fee["basis"] = (f"「하남시 주차장 조례」 [별표1] 노외 {d['grade']}급지 · "
                        f"하남도시공사 직영주차장 요금표(2026-11-17)")
        fee["std"] = {"base_min": HANAM_BASE_MIN, "base_fee": fee["base_fee"],
                      "unit_min": HANAM_UNIT_MIN, "unit_fee": fee["unit_fee"],
                      "day": fee["daily_fee"], "monthly": None}
        lots.append({
            "id": "", "mgmt_no": "", "src": "하남도시공사 직영주차장 현황", "list_mode": "card",
            "name": d["name"], "gu": "하남시", "dong": hanam_dong_of(d["jibun"]) or "망월동",
            "dong_src": "지번주소", "kind": "공영", "ptype": "노외",
            "addr_jibun": d["jibun"], "addr_road": "", "road": None, "spaces": d["spaces"],
            "tel": d["tel"], "lat": lat, "lng": lng, "base_date": "2026-11-17 (공사 현황)",
            "manager": "하남도시공사", "note": "", "notice": None, "fee": fee,
            "oper": {k: True for k in ("weekday", "sat", "sun")}, "hours": win,
            "free_days": {"sat": False, "sun": False}, "free_window": None,
            "free_hour_note": None, "closed_from_note": False, "disabled_area": "",
            "capa_detail": None, "portal_name": None, "realtime": None, "udc_id": None,
            "price_key": fee["unit_fee"], "city": "하남시", "city_slug": "hanam",
        })

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"hn-{i:03d}" if l["list_mode"] == "card" else f"hn-s{i:03d}"

    quality = check_quality_hanam(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                  grade_fixed, fee_diff, space_diff, corp_missing)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(HANAM_CORP_TXT).strftime("%Y-%m-%d %H:%M")
                           if HANAM_CORP_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "하남시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-16",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 하남시가 등록한 35행(노외 18·노상 17)을 읽었다. 이름·주소·구획수·"
                             "급지·운영시간·좌표·전화·관리번호와 등록요금 출처로 썼다."),
                },
                {
                    "id": "fee", "name": "하남시 공영주차장 주차요금 정보(급지별 요금표·요금 감면)",
                    "org": "하남시 교통정책과 주차시설팀",
                    "url": HANAM_FEE_URL,
                    "file": HANAM_FEE_TXT.name if HANAM_FEE_TXT.exists() else None,
                    "sha256": sha256(HANAM_FEE_TXT) if HANAM_FEE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-10-15 최종수정",
                    "rows_total": None,
                    "fetched_at": _sync_time(HANAM_FEE_TXT),
                    "note": ("노상·노외 1~3급지 요금표(30분 800·600·400원, 10분당 300·200·100원, "
                             "1일 주차권 노상 5,000·4,000·3,000원 / 노외 7,000·6,000·4,000원, "
                             "월 정기권 주간·야간·주야간)와 주거지 전용 정기권(20,000·20,000·30,000원), "
                             "요금 감면 표(면제 1항목·감면 15항목) 확인용."),
                },
                {
                    "id": "corp", "name": "하남도시공사 공영주차장 현황·주차요금표",
                    "org": "하남도시공사",
                    "url": HANAM_CORP_URL,
                    "file": HANAM_CORP_TXT.name if HANAM_CORP_TXT.exists() else None,
                    "sha256": sha256(HANAM_CORP_TXT) if HANAM_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 16,
                    "fetched_at": _sync_time(HANAM_CORP_TXT),
                    "note": ("위탁 운영 공영주차장 16곳 1,281면의 유형·급지·면수와 주차장별 요금표"
                             "(덕풍공원·천현동꿈나무 400·100·4,000원, 수리골·행복주택·소공원 600·200·6,000원, "
                             "신장동·감일 800·300·7,000원, 검단산 노상 전일 2,000원, 초광산단로 전용 24시간 "
                             "70,000원, 덕풍스포츠 거주자 정기권) 확인용."),
                },
                {
                    "id": "direct", "name": "하남도시공사 직영주차장 현황·주차요금표",
                    "org": "하남도시공사",
                    "url": HANAM_DIRECT_URL,
                    "file": HANAM_DIRECT_TXT.name if HANAM_DIRECT_TXT.exists() else None,
                    "sha256": sha256(HANAM_DIRECT_TXT) if HANAM_DIRECT_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 2,
                    "fetched_at": _sync_time(HANAM_DIRECT_TXT),
                    "note": ("미사중앙제1(48면)·제2(44면)주차장 — 1급지 30분 800원·10분당 300원·"
                             "1일 7,000원. 표준데이터(기준일 2026-04-16)에 없는 두 곳이라 이 현황으로 카드를 만들었다."),
                },
                {
                    "id": "list", "name": "하남시 공영주차장 현황(주거지 전용 구역 포함)",
                    "org": "하남시",
                    "url": HANAM_LIST_URL,
                    "file": HANAM_LIST_TXT.name if HANAM_LIST_TXT.exists() else None,
                    "sha256": sha256(HANAM_LIST_TXT) if HANAM_LIST_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2024-06-10 최종수정",
                    "rows_total": None,
                    "fetched_at": _sync_time(HANAM_LIST_TXT),
                    "note": ("노외 13·노상 8·주거지 전용 13·부설 1(동부초교) 구성과 급지, "
                             "주거지 전용 구역의 ‘당일 18시~다음날 09시(주간무료개방)’ 운영 확인용."),
                },
                {
                    "id": "ordinance", "name": "하남시 주차장 조례 [별표 1] 공영주차장 주차요금표(제3조제1항 관련)",
                    "org": "하남시",
                    "url": HANAM_ORDINANCE_URL,
                    "file": None,
                    "sha256": None,
                    "license": "자치법규(공개)",
                    "base_date": HANAM_ORDINANCE_NOTE,
                    "rows_total": None,
                    "fetched_at": _sync_time(HANAM_FEE_TXT),
                    "note": ("요금표 원문은 국가법령정보센터의 별표 서식(HWP·PDF)으로만 게시되어 있어, "
                             "같은 별표를 그대로 옮겨 적은 하남시 ‘주차요금 정보’ 화면으로 값을 확인했다."),
                },
                {
                    "id": "geocode", "name": "주소 지오코딩(카카오맵)",
                    "org": "Kakao Map 지오코딩(maps geocode)",
                    "url": "https://map.kakao.com",
                    "file": HANAM_GEOCODE_JSON.name if HANAM_GEOCODE_JSON.exists() else None,
                    "sha256": sha256(HANAM_GEOCODE_JSON) if HANAM_GEOCODE_JSON.exists() else None,
                    "license": "지도 서비스 지오코딩 결과(참고용)",
                    "base_date": "2026-11-17",
                    "rows_total": len(HANAM_DIRECT_LOTS),
                    "fetched_at": _sync_time(HANAM_GEOCODE_JSON),
                    "note": "표준데이터에 없는 미사중앙 제1·2주차장의 좌표(망월동 1086·1090).",
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in HANAM_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "hanam_grade",
            "unit_min": HANAM_UNIT_MIN,
            "base_min": HANAM_BASE_MIN,
            "day_hours": 24,
            "applies": HANAM_ORDINANCE_NOTE + " · 2026-10-15 시 요금정보 확인",
            "off": [{"grade": g, **t, "lots": 0} for g, t in sorted(HANAM_FEES["노외"].items())],
            "street": [{"grade": g, **t} for g, t in sorted(HANAM_FEES["노상"].items())],
            "resident_monthly": HANAM_RESIDENT_MONTHLY,
            "basis": ("「하남시 주차장 조례」 [별표 1] 공영주차장 주차요금표(제3조제1항 관련, 시행 2023-08-04) · "
                      "하남시 주차요금 정보(2026-10-15 최종수정) · 하남도시공사 공영주차장 요금표"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["하남시"] | {
        "city": "하남시",
        "weekend_free_pages": False,
        "discounts": HANAM_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "hanam_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_hanam(std_all, rows, lots, excluded, merged, hour_fixed, grade_fixed,
                        fee_diff, space_diff, corp_missing):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_하남시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"]["std_grade"] for l in paid if l["fee"].get("std_grade"))),
        "운영시간_보정": hour_fixed,
        "급지_보정": grade_fixed,
        "등록값_차이": fee_diff,
        "면수_차이": space_diff,
        "공사_현황_없음": corp_missing,
        "주거지전용": [l["name"] for l in lots if (l["fee"].get("category") == "resident")],
        "정기권전용": [l["name"] for l in lots if l["fee"].get("ticket_only")],
        "포털추가": [l["name"] for l in lots if l["src"] != "표준데이터"],
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid
                                 if l["fee"].get("base_fee") and not l["fee"].get("flat_day"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")
                                        and not l["fee"].get("flat_day")]))),
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 군포시 (T-03 Phase 16)
GUNPO_PROVIDER = "경기도 군포시"
# 군포시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 동 페이지를 둔다.
GUNPO_DISTRICTS = [("군포시", "gunpo")]
GUNPO_BBOX = (37.28, 37.42, 126.85, 127.00)   # 군포시 대략 경계(좌표 점검용)
# 군포시 법정동 9개 — 표준데이터 지번주소의 세 번째 낱말이 법정동이다.
#   (행정동 군포1·2동, 산본1·2동, 금정동, 재궁동, 오금동, 수리동, 궁내동, 광정동, 대야동, 송부동은
#    여러 법정동을 묶은 이름이라 주소에는 법정동이 적힌다.)
GUNPO_DONGS = ("금정동", "당동", "당정동", "대야미동", "도마교동", "둔대동", "부곡동", "산본동", "속달동")

GUNPO_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1990477"
GUNPO_CORP_OUT_URL = "http://www.gunpocs.or.kr/fmcs/32"
GUNPO_CORP_ST_URL = "http://www.gunpocs.or.kr/fmcs/31"
GUNPO_CORP_ATT_URL = "http://www.gunpocs.or.kr/fmcs/721"
GUNPO_FAQ_URL = ("https://www.gunpouc.or.kr/fmcs/68?action=read"
                 "&action-value=d9feeea8c6a38d8804ffbb4034f43f3c")
GUNPO_CORP_TXT = RAW / "gunpocs.or.kr_노외주차장_20261117.txt"
GUNPO_ST_TXT = RAW / "gunpocs.or.kr_노상주차장_20261117.txt"
GUNPO_ATT_TXT = RAW / "gunpocs.or.kr_부설주차장_20261117.txt"
GUNPO_ORD_TXT = RAW / "gunpo.law.go.kr_주차장조례_20261117.txt"
GUNPO_ORD_A1 = RAW / "gunpo.law.go.kr_주차장조례_별표1_20261117.hwp"
GUNPO_ORD_A2 = RAW / "gunpo.law.go.kr_주차장조례_별표2_20261117.hwp"
GUNPO_ORDINANCE_NOTE = "시행 2025-01-01 (경기도군포시조례 제2236호, 2024-12-10 전부개정)"

# 군포시 공영주차장 요금 — 「군포시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금(제10조제1항 관련)을
#   rhwp 로 옮겨 읽고, 군포도시공사 공영주차장 안내(2026-11-17 확인)·‘2025년도 공영주차장 급지별 요금 변경
#   현황’(2025-01-01 시행)·‘주차요금 현황’(2025-04-01 기준)과 대조했다.
#   · 1~3급지 모두 <b>최초 15분 무료</b>, 최초 30분 기본요금 뒤 10분 단위로 붙는다.
#   · 1급지 30분 800원·10분당 400원·1일 최대 9,000원, 월 정기권 100,000원.
#   · 2급지 600·200·6,000원·월 70,000원, 3급지 300·200·4,000원·월 50,000원.
GUNPO_FEES = {
    1: {"base": 800, "unit": 400, "day": 9_000, "month": 100_000},
    2: {"base": 600, "unit": 200, "day": 6_000, "month": 70_000},
    3: {"base": 300, "unit": 200, "day": 4_000, "month": 50_000},
}
GUNPO_FREE_MIN = 15      # 최초 15분 무료(1~3급지 공통)
GUNPO_BASE_MIN = 30
GUNPO_UNIT_MIN = 10

# 특수관리대상·별도 요금 주차장 — 급지 요금표 대신 조례 [별표1]의 별도 표를 쓴다(10분 단위 누진).
#   · 중심1·2·3·중심지하: 최초 15분 무료, 30분 800원, 이후 10분당 400 → 1~2시간 600 → 2~3시간 1,000
#     → 3시간 이후 1,500원. 1시간 2,000·2시간 5,600·3시간 11,600·5시간 40분부터 1일 최대 35,000원.
#   · 산본로데오: 최초 1시간 무료, 이후 10분당 400원, 1일 최대 8,000원.
#   · 산본시장(노상)·산본시장제2·금산로1: 최초 30분 무료, 이후 10분당 400 → 1~2시간 600 → 2~3시간 900
#     → 3시간 이후 1,300원, 1일 최대 35,000원.
#   · 군포역환승: 최초 30분 무료, 이후 10분당 400원, 1일 최대 8,000원.
#   · 군포역1길(노상): 최초 30분 무료, 이후 10분당 400원, 1일 최대 없음.
#   1일 최대는 조례 별표1이 중심 90,000원·산본시장 57,000원으로 적혀 있으나, 공사 안내의 누적 요금표
#   (중심 5시간 40분부터 35,000원, 산본시장 6시간 20분부터 35,000원)를 운영 값으로 썼다.
GUNPO_SPECIAL = {
    "center": {"free_min": 15, "base_min": 30, "base": 800, "unit": 400,
               "tiers": (400, 600, 1_000, 1_500), "day": 35_000,
               "label": "중심 1·2·3·지하 누진"},
    "rodeo": {"free_min": 60, "base_min": 60, "base": 0, "unit": 400,
              "tiers": None, "day": 8_000, "label": "산본로데오 1시간 무료"},
    "transit": {"free_min": 30, "base_min": 30, "base": 0, "unit": 400,
                "tiers": None, "day": 8_000, "label": "군포역 환승"},
    "market": {"free_min": 30, "base_min": 30, "base": 0, "unit": 400,
               "tiers": (400, 600, 900, 1_300), "day": 35_000, "label": "산본시장 누진"},
    "station": {"free_min": 30, "base_min": 30, "base": 0, "unit": 400,
                "tiers": None, "day": None, "label": "군포역1길"},
}
GUNPO_SPECIAL_LOTS = {
    "중심1공영주차장": "center", "중심2공영주차장": "center",
    "중심3공영주차장": "center", "중심지하공영주차장": "center",
    "산본로데오공영주차장": "rodeo",
    "군포역환승공영주차장": "transit",
    "산본시장공영주차장": "market", "산본시장제2공영주차장": "market",
    "금산로1공영주차장": "market",
    "군포역1길공영주차장": "station",
}

# 군포도시공사 공영주차장 현황(2026-11-17 조회) — 급지·면수·운영시간을 표준데이터와 대조하고,
#   표준데이터가 80행 모두 00:00~23:59로만 등록해 둔 운영시간을 공사 안내 값으로 바로잡는 데 쓴다.
#   표준데이터 이름 → (공사 이름, 급지(특수는 None), 면수, (평일, 토요일, 일요일) 운영시간)
GUNPO_CORP = {
    "중심지하공영주차장": ("중심지하", None, 179, ("24H", "24H", "24H")),
    "중심1공영주차장": ("중심1", None, 39, ("24H", "24H", "24H")),
    "중심2공영주차장": ("중심2", None, 39, ("24H", "24H", "24H")),
    "중심3공영주차장": ("중심3", None, 18, ("24H", "24H", "24H")),
    "행복공영주차장": ("행복1", 1, 59, ("24H", "24H", "24H")),
    "산본천공영주차장": ("산본천", 1, 76, ("08:00~24:00", "08:00~24:00", "08:00~24:00")),
    "바위백이공영주차장": ("바위백이(지하)", 1, 28, ("08:00~24:00", "08:00~24:00", "08:00~24:00")),
    "철쭉공원공영주차장": ("철쭉공원", 2, 260,
                          ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "송죽공영주차장": ("송죽", 2, 232, ("07:00~23:00", "07:00~23:00", "07:00~23:00")),
    "당동2공영주차장": ("당동2", 2, 206, ("08:00~24:00", "08:00~24:00", "08:00~24:00")),
    "당동4공영주차장": ("당동4", 2, 17, ("무료개방", "무료개방", "무료개방")),
    "문화공영주차장": ("문화", 1, 74, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "안금정공영주차장": ("안금정", 2, 44, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "군포역환승공영주차장": ("군포역환승", None, 74,
                            ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "청명1길공영주차장": ("청명1길", 2, 50, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "당동1공영주차장": ("당동1", 2, 82, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "당정역광장공영주차장": ("당정역광장", 1, 43,
                            ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "당정1공영주차장": ("당정1", 2, 76, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "당정2공영주차장": ("당정2", 3, 237, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "대야6공영주차장": ("대야6", 2, 31, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "금정제일공영주차장": ("금정제일", 2, 115, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "군포고가교밑2공영주차장": ("군포고가교밑2", 2, 30,
                               ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "당정12공영주차장": ("당정12", 2, 30, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "당동3공영주차장": ("당동3", 2, 80, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "고랑치기공영주차장": ("고랑치기", 2, 166, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "평화공영주차장": ("평화", 2, 17, ("월정기", "월정기", "월정기")),
    "당정노외공영주차장": ("당정노외", 2, 44, ("월정기", "월정기", "월정기")),
    "당정3공영주차장": ("당정3", 2, 40, ("월정기", "월정기", "월정기")),
    "당정7공영주차장": ("당정7", 2, 17, ("월정기", "월정기", "월정기")),
    "당정8공영주차장": ("당정8", 2, 34, ("월정기", "월정기", "월정기")),
    "당정9공영주차장": ("당정9", 2, 28, ("월정기", "월정기", "월정기")),
    "군포고가교밑3공영주차장": ("군포고가교밑3", 2, 33, ("월정기", "월정기", "월정기")),
    "당정10공영주차장": ("당정10", 2, 69, ("월정기", "월정기", "월정기")),
    "당정11공영주차장": ("당정11", 2, 28, ("월정기", "월정기", "월정기")),
    "금정역제1공영주차장": ("금정역제1", 1, 202, ("24H", "24H", "24H")),
    "산본시장제2공영주차장": ("산본시장제2", None, 23,
                             ("08:00~20:00", "08:00~20:00", "08:00~20:00")),
    "산본로데오공영주차장": ("산본로데오", None, 285, ("24H", "24H", "24H")),
    "반월호수공영주차장": ("반월호수", 2, 120, ("무료개방", "무료개방", "무료개방")),
    "당말공원공영주차장": ("당말공원", 1, 49, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    "산본시장제1공영주차장": ("산본시장제1", None, 40, ("월정기", "월정기", "월정기")),
    "대야제5공영주차장": ("대야5", 2, 49, ("08:00~24:00", "08:00~24:00", "10:00~22:00")),
    # 노상(거리) 구간 6곳 — 평일 09:00~18:00(토요일 10:00~18:00)에만 요금을 받는다.
    "군포역1길공영주차장": ("군포역1길", None, 20,
                           ("09:00~18:00", "10:00~18:00", "무료개방")),
    "산본시장공영주차장": ("산본시장", None, 100,
                          ("09:00~18:00", "10:00~18:00", "무료개방")),
    "금산로1공영주차장": ("금산로1", None, 14,
                         ("09:00~18:00", "10:00~18:00", "무료개방")),
    "금산로2공영주차장": ("금산로2", 1, 48, ("무료개방", "무료개방", "무료개방")),
    "동백길공영주차장": ("동백길", 2, 31, ("월정기", "월정기", "월정기")),
    "군포고가교밑1공영주차장": ("군포고가교밑1", 2, 15,
                               ("09:00~18:00", "무료개방", "무료개방")),
}
# 군포도시공사가 게시하지 않은(군포시청이 관리하는) 소규모 무료 주차장 — 표준데이터 등록값을 그대로 쓴다.
GUNPO_CITY_ONLY = ("대야제1공영주차장", "대야제2공영주차장", "대야제3공영주차장",
                   "대야제4공영주차장", "당정4공영주차장", "당정5공영주차장",
                   "당정대영지구공영주차장", "번영공영주차장", "당말공영주차장")

# 시간 주차요금 없이 월 정기권만 받는 주차장(공사 현황 ‘월정기 전용’) — 0원이 아니라 ‘요금 미상’으로 둔다.
GUNPO_TICKET_ONLY = ("산본시장제1공영주차장", "군포고가교밑3공영주차장", "당정10공영주차장",
                     "당정11공영주차장", "당정9공영주차장", "당정8공영주차장",
                     "당정7공영주차장", "당정3공영주차장", "당정노외공영주차장",
                     "평화공영주차장", "동백길공영주차장")

# 주소로 법정동을 찾지 못한 행의 보정 — 도로명주소만 등록된 4행(공사 현황·도로명주소 기준).
GUNPO_DONG_OVERRIDE = {
    "농심로72번길 노상": ("당정동", "농심로는 당정동 도로(당정7·8 농심로 7·8)"),
    "당말공원공영주차장": ("당동", "공사 현황 ‘당동 779’, 당말공영주차장 당동 869"),
    "반월호수공영주차장": ("둔대동", "반월호수 공원 둔대동 354-3·호수로 92"),
    "첨단산업단지 노상": ("부곡동", "군포첨단산업1로는 부곡동(부곡동 1234 일대)"),
}
# 표준데이터가 24시간으로 등록했지만 공사 안내는 다른 시간인 주차장(노상 4곳·실제 요금 부과 시간).
GUNPO_PAID_WINDOW = ("군포역1길공영주차장", "산본시장공영주차장", "금산로1공영주차장",
                     "군포고가교밑1공영주차장", "산본시장제2공영주차장")

# 군포시 ‘공영주차장 주차요금 감면기준’(조례 [별표 2], 제10조제2항) — 시간주차는 1회 주차요금 기준,
#   일일권·월 정기권은 별도 감면율(30%·50%)이다.
#   · 전액면제: 긴급자동차, 공무수행차량, 외교사절, 군포2동 행정복지센터 민원(문화 30분),
#     군포역 환승·군포역1길 민원 확인증 1시간.
#   · 1회 주차요금 최초 2시간 면제 후 50%: 국가유공자·유족, 고엽제, 5·18, 중증장애인, 성실·모범납세자(1년),
#     의사상자, 다자녀(경기I-plus), 한부모, 당일 헌혈자.
#   · 1회 50%: 경형자동차, 환경친화적 자동차(전기차는 최초 2시간 전액면제), 도시철도 환승,
#     경증장애인, 저공해자동차, 경로우대(65세 이상), 병역명문가, 우수기업, 우수자원봉사자.
GUNPO_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·전기차 50%", "rate": 0.5, "exempt_min": 0,
     "note": "「자동차관리법 시행규칙」 별표1 경형자동차(1,000cc 미만), 환경친화적 자동차 — 전기차는 최초 2시간 전액 면제"},
    {"label": "경로·병역명문가 50%", "rate": 0.5, "exempt_min": 0,
     "note": "만 65세 이상 경로우대 자가운전 차량, 병역명문가증 제시 차량, 도시철도 환승 차량, 경증장애인·저공해자동차"},
    {"label": "유공자·장애인 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "국가유공자·유족, 고엽제후유의증, 5·18 부상자, 장애 정도가 심한 장애인, 성실·모범납세자(교부일부터 1년), "
             "의사상자, 다자녀가정(경기I-plus), 한부모가족, 당일 헌혈자"},
    {"label": "긴급·공무 차량 면제", "rate": 1.0, "exempt_min": 0,
     "note": "긴급자동차, 국가·지방자치단체 공무수행차량, 외교사절 및 수행자"},
]


def gunpo_dong_of(text: str):
    """주소에서 군포시 법정동을 뽑는다.

    표준데이터 지번주소는 ‘경기도 군포시 {법정동} {번지}’ 꼴이라 세 번째 낱말이 법정동이다.
    꼴이 다르면 법정동 목록에서 찾는다(이름이 서로 겹치지 않는다).
    """
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "군포시" and parts[2] in GUNPO_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(GUNPO_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def gunpo_win(spec):
    """공사 안내 운영시간 문자열 → 사이트 공통 hours 객체.

    "24H"·"무료개방"은 24시간 운영으로, "월정기"는 시간 운영 없이 정기권만 받는 것으로 둔다.
    """
    win = {}
    for key, txt in zip(("weekday", "sat", "sun"), spec):
        if txt in ("24H", "무료개방", "월정기"):
            win[key] = {"open": True, "start": 0, "end": 1440, "24h": True,
                        "listed": True, "raw": ["00:00", "24:00"]}
        else:
            m = re.match(r"(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})", txt)
            s = int(m.group(1)) * 60 + int(m.group(2))
            e = int(m.group(3)) * 60 + int(m.group(4))
            win[key] = {"open": True, "start": s, "end": e, "24h": False,
                        "listed": True, "raw": [f"{s // 60:02d}:{s % 60:02d}",
                                                f"{e // 60:02d}:{e % 60:02d}"]}
    return win


def gunpo_fee(grade: int):
    """군포시 급지 요금 → 사이트 공통 fee 객체(유료). 최초 15분 무료·30분 기본·10분 단위."""
    t = GUNPO_FEES[grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False, "grade": grade, "std_grade": None,
        "base_min": GUNPO_BASE_MIN, "base_fee": t["base"],
        "unit_min": GUNPO_UNIT_MIN, "unit_fee": t["unit"],
        "steps": None, "free_min": GUNPO_FREE_MIN, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": None, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "pay": "", "basis": f"「군포시 주차장 설치 및 관리 조례」 [별표1] {grade}급지",
        "category": None, "portal_free_now": False, "flat_day": False, "ticket_only": False,
    }


def gunpo_special_fee(kind: str):
    """특수관리대상·별도 요금 주차장(중심·산본로데오·산본시장·군포역환승·군포역1길)의 누진 요금."""
    t = GUNPO_SPECIAL[kind]
    steps = None
    if t["tiers"]:
        steps = [{"until": b, "unit_min": GUNPO_UNIT_MIN, "unit_fee": f}
                 for b, f in zip((60, 120, 180, None), t["tiers"])]
    fee = {
        "type": "유료", "raw_type": "혼합", "mixed": True, "grade": None, "std_grade": None,
        "base_min": t["base_min"], "base_fee": t["base"],
        "unit_min": GUNPO_UNIT_MIN, "unit_fee": t["unit"],
        "steps": steps, "free_min": t["free_min"], "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": None, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "pay": "", "basis": f"「군포시 주차장 설치 및 관리 조례」 [별표1] 별도 요금({t['label']})",
        "category": None, "portal_free_now": False, "flat_day": False, "ticket_only": False,
    }
    if steps:
        fee["steps_label"] = t["label"]
    return fee


def gunpo_free_fee(**extra):
    fee = {"type": "무료", "raw_type": "무료", "mixed": False, "grade": None, "std_grade": None,
           "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
           "steps": None, "free_min": None, "deduct_min": None, "cap_fee": None, "cap_src": None,
           "daily_hours": None, "daily_fee": None, "prepaid_day": None, "prepaid_weekend": None,
           "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
           "pay": "", "basis": "요금 구분 ‘무료’", "category": None, "portal_free_now": False,
           "flat_day": False, "ticket_only": False, "std": None}
    fee.update(extra)
    return fee


def gunpo_ticket_fee(monthly=None, raw_type="유료"):
    """월 정기권만 받는 주차장 → ‘요금 미상’(시간 주차요금 없음)."""
    return {"type": "미상", "raw_type": raw_type, "mixed": False, "grade": None,
            "std_grade": None, "base_min": None, "base_fee": None, "unit_min": None,
            "unit_fee": None, "steps": None, "free_min": None, "deduct_min": None,
            "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None, "monthly": monthly,
            "monthly_day": None, "monthly_night": None, "monthly_all": None,
            "pay": "", "basis": "월 정기권 전용(시간 주차요금 미게시)", "category": None,
            "portal_free_now": False, "flat_day": False, "ticket_only": True, "std": None}


GUNPO_WINDOW_DAYS = {"평일": "평일", "토": "토요일", "일": "일요일", "주말": "주말",
                     "토·일": "토·일요일", "평일·토": "평일·토요일",
                     "평일·주말": "평일·주말", "평일·토·일": "평일·토·일요일"}


def gunpo_free_info(note: str):
    """특기사항에서 무료 시간대·무료 개방 요일을 읽는다.

    표준데이터 특기사항은 ‘평일·토(00:01~07:59 무료)+일(22:01~09:59 무료)’처럼 시간대 무료와
    ‘일요일 무료개방’·‘토일 무료개방’ 같은 종일 무료를 함께 적는다. 종일 무료만 free_days 로 두고,
    시간대 무료는 free_hour_note 문장으로 옮긴다(계산기는 입차 시각을 모르므로 입차~출차 길이로만 계산).
    """
    txt = (note or "").replace("09:60", "09:59")      # 표준데이터 오타(군산로1 ‘토 18:01~09:60’)
    days = {"sat": False, "sun": False}
    if re.search(r"(토일|토·일|주말)\s*무료개방", txt):
        days["sat"] = days["sun"] = True
    elif re.search(r"토요일\s*무료개방", txt):
        days["sat"] = True
    if re.search(r"(일요일|일)\s*무료개방", txt):
        days["sun"] = True
    windows = []
    for dm, s, e in re.findall(r"([가-힣·]+)\((\d{1,2}:\d{2})~(\d{1,2}:\d{2})\s*무료\)", txt):
        windows.append(f"{GUNPO_WINDOW_DAYS.get(dm, dm)} {s}~{e}")
    return days, windows


def build_gunpo():
    """군포시 공영주차장을 표준데이터 + 군포도시공사 현황 + 조례 별표로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 군포시 범위를 벗어난 행은 제외(껍데기 행).
      · 군포시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다.
    요금은 조례 별표1(1~3급지 최초 15분 무료·30분 기본·10분 단위, 특수관리대상은 별도 누진표)을 적용하고,
    운영시간은 표준데이터가 80행 모두 00:00~23:59로만 등록해 두어 군포도시공사 현황의 값으로 바로잡았다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GUNPO_PROVIDER]
    lots, excluded, merged, hour_fixed, grade_fixed, fee_diff, space_diff = [], [], [], [], [], [], []
    corp_missing, note_fixed, ticket_diff = [], [], []
    seen = {}
    card_no = street_no = 0

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        # 같은 주차장이 두 행으로 등록된 곳 — 이름·유형이 같으면 한 곳으로 묶는다.
        jibun_key = re.sub(r"\s", "", jibun)
        name_key = re.sub(r"\s+", "", name)
        dup_key = None
        if jibun_key and (("지번", jibun_key, ptype, spaces)) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif name_key and ("이름", name_key, ptype) in seen:
            dup_key = ("이름", name_key, ptype)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and name_key:
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", name_key, ptype)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (GUNPO_BBOX[0] <= lat <= GUNPO_BBOX[1]
                                     and GUNPO_BBOX[2] <= lng <= GUNPO_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = gunpo_dong_of(jibun) or gunpo_dong_of(road)
        dong_src = "지번주소" if gunpo_dong_of(jibun) else ("도로명주소" if gunpo_dong_of(road) else "없음")
        if not dong and name in GUNPO_DONG_OVERRIDE:
            dong, why = GUNPO_DONG_OVERRIDE[name]
            dong_src = f"보정({why})"
        note = (r.get("특기사항") or "").strip()
        pay = (r.get("요금정보") or "").strip()
        std_grade = to_int(r.get("급지구분"))
        street = ptype == "노상"

        win, oper, closed_note = parse_schedule(r, note)
        if street:
            closed_note = False
        # 표준데이터는 80행 모두 평일·토요일·공휴일 00:00~23:59라, 공사 현황의 운영시간으로 바로잡는다.
        corp = GUNPO_CORP.get(name)
        if corp:
            want = gunpo_win(corp[3])
            if any(win[k]["start"] != want[k]["start"] or win[k]["end"] != want[k]["end"]
                   for k in ("weekday", "sat", "sun")):
                hour_fixed.append(
                    f"{name}: 표준데이터 00:00~23:59 → 공사 안내 "
                    f"평일 {corp[3][0]}·토 {corp[3][1]}·일 {corp[3][2]}")
            win = want
            oper = {k: True for k in ("weekday", "sat", "sun")}
        elif not all(win[k]["open"] and win[k]["24h"] for k in ("weekday", "sat", "sun")):
            hour_fixed.append(f"{name}: 표준데이터 운영시간 {r.get('운영요일') or '—'} "
                              f"{r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''}")

        free_days, free_windows = gunpo_free_info(note)

        base_fee_reg = to_int(r.get("주차기본요금"))
        if name in GUNPO_SPECIAL_LOTS:
            grade = None
        elif std_grade in (1, 2, 3):
            grade = std_grade
        else:
            # 급지 ‘기타’(특수관리대상·무료) — 공사 현황의 급지가 있으면 그것을 쓴다.
            grade = corp[1] if corp else None
            if grade and pay != "무료":
                grade_fixed.append(f"{name}: 표준데이터 급지 ‘기타’ → 공사 현황 {grade}급지")
        if corp and corp[1] is not None and grade is not None and corp[1] != grade:
            grade_fixed.append(f"{name}: 표준데이터 {grade}급지 ↔ 공사 현황 {corp[1]}급지")
        if corp is None:
            corp_missing.append(name)
        elif corp[2] != spaces:
            space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 공사 현황 {corp[2]}면")

        kind = "노상" if street else "노외"
        if street:
            street_no += 1
            lot_id = f"gpo-s{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"gpo-{card_no:03d}"

        monthly = to_int(r.get("월정기권요금"))
        if name in GUNPO_TICKET_ONLY:
            fee = gunpo_ticket_fee(monthly=monthly, raw_type=pay or "유료")
        elif name in GUNPO_SPECIAL_LOTS:
            fee = gunpo_special_fee(GUNPO_SPECIAL_LOTS[name])
            fee["monthly"] = monthly or None
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")), "base_fee": base_fee_reg,
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": to_int(r.get("1일주차권요금")), "monthly": monthly}
        elif pay == "무료":
            fee = gunpo_free_fee()
        elif grade in GUNPO_FEES:
            fee = gunpo_fee(grade)
            fee["monthly"] = monthly or None
            fee["monthly_all"] = monthly or None
            # 1일 주차권을 운영하지 않는 곳(산본천·바위백이)은 상한 없이 계산한다.
            if name in ("산본천공영주차장", "바위백이공영주차장"):
                fee["daily_fee"] = None
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")), "base_fee": base_fee_reg,
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": to_int(r.get("1일주차권요금")), "monthly": monthly}
            reg_day = to_int(r.get("1일주차권요금"))
            if reg_day and fee["daily_fee"] and reg_day != fee["daily_fee"]:
                fee_diff.append(f"{name}: 등록 1일 주차권 {reg_day:,}원 ↔ 조례 {grade}급지 "
                                f"{fee['daily_fee'] or 0:,}원")
        else:
            fee = gunpo_ticket_fee(monthly=monthly or None, raw_type=pay or "유료")
        if name not in GUNPO_SPECIAL_LOTS:
            fee["std_grade"] = std_grade
        fee["pay"] = (r.get("결제방법") or "").strip()

        notice = None
        if name in ("산본천공영주차장", "바위백이공영주차장"):
            notice = ("1일 주차권을 운영하지 않습니다(군포도시공사 안내) — 24시간을 세우면 시간 요금 "
                      "합계가 그대로 청구됩니다")
        if name in GUNPO_SPECIAL_LOTS:
            special_note = {
                "center": ("특수관리대상(중심상가) — 1시간 2,000원·2시간 5,600원·3시간 11,600원, "
                           "3시간 뒤에는 10분당 1,500원이고 5시간 40분부터 1일 최대 35,000원입니다"),
                "rodeo": ("특수관리대상 — 최초 1시간 무료, 이후 10분당 400원, 1일 최대 8,000원입니다"
                          "(표준데이터에는 기본 60분 0원·10분당 400원으로 등록)"),
                "transit": "특수관리대상 환승주차장 — 최초 30분 무료, 이후 10분당 400원, 1일 최대 8,000원입니다",
                "market": ("특수관리대상 — 최초 30분 무료, 이후 10분당 400원(1~2시간 600원·2~3시간 900원·"
                           "3시간 뒤 1,300원)이고 6시간 20분부터 1일 최대 35,000원입니다"),
                "station": "특수관리대상 — 최초 30분 무료, 이후 10분당 400원이고 1일 최대 요금은 없습니다",
            }[GUNPO_SPECIAL_LOTS[name]]
            notice = special_note
            if name == "산본시장제2공영주차장":
                notice += (" · 표준데이터에는 10분당 1,300원·1일 요금 없음으로만 등록되어 있습니다"
                           "(조례 별표1은 산본시장과 같은 별도 표로 1일 최대 57,000원)")
            if name in ("산본시장공영주차장", "금산로1공영주차장", "군포역1길공영주차장"):
                notice += " · 평일 09:00~18:00(토요일 10:00~18:00)에만 요금을 받고, 일요일은 무료 개방입니다"
        if name == "산본시장제1공영주차장":
            notice = ("월 정기권 전용 주차장입니다 — 시간 주차요금은 게시되어 있지 않고, "
                      f"월 정기권은 {monthly:,}원입니다" if monthly else
                      "월 정기권 전용 주차장입니다 — 시간 주차요금은 게시되어 있지 않습니다")
        if name in GUNPO_TICKET_ONLY and name != "산본시장제1공영주차장":
            notice = ("공사 현황에 ‘월정기 전용’으로 안내되는 주차장입니다 — 시간 주차요금은 게시되어 있지 않고, "
                      f"월 정기권은 {monthly:,}원입니다" if monthly else
                      "공사 현황에 ‘월정기 전용’으로 안내되는 주차장입니다 — 시간 주차요금은 게시되어 있지 않습니다")
        if name in ("당동4공영주차장", "반월호수공영주차장"):
            notice = ("군포도시공사가 ‘무료개방’으로 안내하는 주차장입니다(공사 현황 급지 2급지, "
                      "요금 구분 ‘무료’)")
        if name == "금산로2공영주차장":
            notice = ("공사 현황은 1급지·‘무료개방’으로, 표준데이터는 급지 ‘기타’·‘무료’로 등록하고 "
                      "있습니다 — 두 자료 모두 무료라 요금은 없습니다")
        if name in GUNPO_PAID_WINDOW and notice is None:
            notice = ("평일 09:00~18:00(토요일 10:00~18:00)에만 요금을 받고, 그 밖의 시간과 일요일은 "
                      "무료입니다")
        if corp is None and name in GUNPO_CITY_ONLY:
            notice = ("군포시청이 관리하는 소규모 무료 주차장입니다 — 군포도시공사 공영주차장 현황(41곳)에는 "
                      "없고 표준데이터에만 등록되어 있습니다")
        if corp and corp[2] != spaces:
            notice = ((notice + " · ") if notice else "") + \
                f"군포도시공사 현황은 {corp[2]}면으로 안내합니다(표준데이터 {spaces}면)"
        if "09:60" in (r.get("특기사항") or ""):
            note_fixed.append(f"{name}: 특기사항 ‘토(18:01~09:60 무료)’ → 09:59로 읽음(표준데이터 오타)")

        lots.append({
            "id": lot_id,
            "mgmt_no": mgmt,
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "군포시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip() or "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
            "spaces": spaces,
            "tel": (r.get("전화번호") or "").strip(),
            "lat": lat, "lng": lng,
            "base_date": (r.get("데이터기준일자") or "").strip(),
            "manager": (r.get("관리기관명") or "").strip() or "군포시",
            "note": note,
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days,
            "free_window": (free_windows[0].split(" ", 1)[1] if free_windows else None),
            "free_hour_note": ((" · ".join(free_windows) + "에는 요금이 발생하지 않습니다(등록 특기사항 기준)")
                               if free_windows else None),
            "closed_from_note": closed_note,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip(),
            "capa_detail": None,
            "portal_name": corp[0] if corp else None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "군포시",
            "city_slug": "gunpo",
        })

    # 일부러 0원으로 두지 않는 값 — 월정기 전용 주차장의 ‘1일 주차권 없음’을 품질 리포트에 남긴다.
    for l in lots:
        if l["fee"].get("ticket_only") and not l["fee"].get("monthly"):
            ticket_diff.append(l["name"])

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"gpo-{i:03d}" if l["list_mode"] == "card" else f"gpo-s{i:03d}"

    quality = check_quality_gunpo(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                  grade_fixed, fee_diff, space_diff, corp_missing,
                                  note_fixed, ticket_diff)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(GUNPO_CORP_TXT).strftime("%Y-%m-%d %H:%M")
                           if GUNPO_CORP_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "군포시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-16",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 군포시가 등록한 80행(노외 50·노상 30)을 읽었다. 이름·주소·구획수·"
                             "급지·운영시간·좌표·전화·관리번호·특기사항(무료 시간대)과 등록요금 출처로 썼다."),
                },
                {
                    "id": "ordinance", "name": "군포시 주차장 설치 및 관리 조례 [별표 1] 공영주차장 주차요금·[별표 2] 감면기준",
                    "org": "군포시(차량관리과)",
                    "url": GUNPO_ORDINANCE_URL,
                    "file": f"{GUNPO_ORD_A1.name} · {GUNPO_ORD_A2.name}",
                    "sha256": sha256(GUNPO_ORD_A1) if GUNPO_ORD_A1.exists() else None,
                    "license": "자치법규(공개)",
                    "base_date": GUNPO_ORDINANCE_NOTE,
                    "rows_total": None,
                    "fetched_at": _sync_time(GUNPO_ORD_A1),
                    "note": ("1~3급지 최초 15분 무료·최초 30분 800·600·300원·10분당 400·200·200원·"
                             "1일 최대 9,000·6,000·4,000원, 월 정기권 100,000·70,000·50,000원과 "
                             "중심1·2·3·지하·산본로데오·산본시장·군포역환승·군포역1길의 별도(누진) 요금표를 "
                             "별표 HWP로 받아 rhwp로 옮겨 읽었다. 감면은 [별표 2](전액면제·2시간 면제 후 "
                             "50%·50%·기타 20%)를 썼다."),
                },
                {
                    "id": "corp", "name": "군포도시공사 공영주차장 노외주차장 현황·주차요금",
                    "org": "군포도시공사 교통관리부 주차관리팀(031-390-7684)",
                    "url": GUNPO_CORP_OUT_URL,
                    "file": GUNPO_CORP_TXT.name if GUNPO_CORP_TXT.exists() else None,
                    "sha256": sha256(GUNPO_CORP_TXT) if GUNPO_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 41,
                    "fetched_at": _sync_time(GUNPO_CORP_TXT),
                    "note": ("노외 41곳 3,363면의 급지(1~3급지·특수관리대상)·면수·평일·토요일·일요일 "
                             "운영시간과 요금표(1급지 800·400·9,000원, 2급지 600·200·6,000원, 3급지 "
                             "300·200·4,000원, 중심·산본로데오·군포역환승 별도표) 확인용."),
                },
                {
                    "id": "corp_st", "name": "군포도시공사 공영주차장 노상주차장 현황·주차요금",
                    "org": "군포도시공사 교통관리부 주차관리팀(031-390-7684)",
                    "url": GUNPO_CORP_ST_URL,
                    "file": GUNPO_ST_TXT.name if GUNPO_ST_TXT.exists() else None,
                    "sha256": sha256(GUNPO_ST_TXT) if GUNPO_ST_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 6,
                    "fetched_at": _sync_time(GUNPO_ST_TXT),
                    "note": ("노상 6곳 228면(군포역1길·산본시장·금산로1·금산로2·동백길·군포고가교밑1)의 "
                             "급지·면수와 운영시간(평일 09:00~18:00·토요일 10:00~18:00·일요일 무료개방), "
                             "산본시장·금산로1의 누진 요금표(1시간 1,200·2시간 4,800·3시간 10,200원, "
                             "1일 최대 35,000원) 확인용."),
                },
                {
                    "id": "corp_att", "name": "군포도시공사 부설주차장 현황(시청부설)",
                    "org": "군포도시공사 교통관리부 주차관리팀(031-390-7684)",
                    "url": GUNPO_CORP_ATT_URL,
                    "file": GUNPO_ATT_TXT.name if GUNPO_ATT_TXT.exists() else None,
                    "sha256": sha256(GUNPO_ATT_TXT) if GUNPO_ATT_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 1,
                    "fetched_at": _sync_time(GUNPO_ATT_TXT),
                    "note": ("시청부설주차장 1곳 159면(급지 없음, 24시간 무인화, 1시간 이내 출차 면제·"
                             "1시간 초과 10분당 300원·1일(최대 4시간) 6,000원) — 공영주차장 목록과 요금 기준이 "
                             "달라 카드로 만들지 않고 페이지에 안내했다."),
                },
                {
                    "id": "faq", "name": "군포도시공사 ‘공영주차장 주차요금 현황’(2025-04-01 기준)",
                    "org": "군포도시공사",
                    "url": GUNPO_FAQ_URL,
                    "file": None, "sha256": None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2025-04-01 기준",
                    "rows_total": None,
                    "fetched_at": _sync_time(GUNPO_CORP_TXT),
                    "note": ("1급지 800·400·9,000원 / 2급지 600·200·6,000원 / 3급지 300·200·4,000원과 "
                             "중심 1일 최대 35,000원·산본로데오 8,000원을 확인했다(조례 별표1의 중심 "
                             "90,000원·산본시장 57,000원은 2025년 개정 전 값으로 보아 운영 값을 따랐다)."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GUNPO_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "gunpo_special",
            "unit_min": GUNPO_UNIT_MIN,
            "base_min": GUNPO_BASE_MIN,
            "free_min": GUNPO_FREE_MIN,
            "applies": GUNPO_ORDINANCE_NOTE + " · 2025-01-01 요금 적용",
            "off": [{"grade": g, **t, "lots": 0} for g, t in sorted(GUNPO_FEES.items())],
            "special": [
                {"key": "center", "name": "중심1·2·3·중심지하",
                 "free_min": 15, "base": 800, "tiers": "400 → 600 → 1,000 → 1,500",
                 "day": 35_000, "note": "1시간 2,000·2시간 5,600·3시간 11,600원 · 월 정기권 없음"},
                {"key": "rodeo", "name": "산본로데오",
                 "free_min": 60, "base": 0, "tiers": "1시간 무료 뒤 400",
                 "day": 8_000, "note": "285면·24시간 · 월 정기권 90,000원"},
                {"key": "market", "name": "산본시장(노상)·산본시장제2·금산로1",
                 "free_min": 30, "base": 0, "tiers": "400 → 600 → 900 → 1,300",
                 "day": 35_000, "note": "1시간 1,200·2시간 4,800·3시간 10,200원 · 산본시장제1 정기권 80,000원"},
                {"key": "transit", "name": "군포역환승",
                 "free_min": 30, "base": 0, "tiers": "400",
                 "day": 8_000, "note": "74면 · 월 정기권 80,000원"},
                {"key": "station", "name": "군포역1길(노상)",
                 "free_min": 30, "base": 0, "tiers": "400",
                 "day": None, "note": "1일 최대 없음(20면)"},
            ],
            "corp": {"out": 41, "out_spaces": 3363, "st": 6, "st_spaces": 228, "att": 1, "att_spaces": 159},
            "basis": ("「군포시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금"
                      f"({GUNPO_ORDINANCE_NOTE}) · 군포도시공사 공영주차장 요금 안내(2026-11-17 확인)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["군포시"] | {
        "city": "군포시",
        "weekend_free_pages": False,
        "discounts": GUNPO_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "gunpo_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_gunpo(std_all, rows, lots, excluded, merged, hour_fixed, grade_fixed,
                        fee_diff, space_diff, corp_missing, note_fixed, ticket_diff):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_군포시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "특수관리대상": [l["name"] for l in lots if l["name"] in GUNPO_SPECIAL_LOTS],
        "운영시간_보정": hour_fixed,
        "급지_보정": grade_fixed,
        "등록값_차이": fee_diff,
        "면수_차이": space_diff,
        "공사_현황_없음": corp_missing,
        "특기사항_보정": note_fixed,
        "정기권_금액없음": ticket_diff,
        "야간무료_표기": [l["name"] for l in lots if l["free_hour_note"]],
        "정기권전용": [l["name"] for l in lots if l["fee"].get("ticket_only")],
        "포털추가": [l["name"] for l in lots if l["src"] != "표준데이터"],
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid
                                 if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }



# ---------------------------------------------------------------- 광명시 (T-03 Phase 17)
GM_PROVIDER = "경기도 광명시"
# 광명시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
GM_DISTRICTS = [("광명시", "gwangmyeong")]
GM_BBOX = (37.41, 37.51, 126.83, 126.93)   # 광명시 대략 경계(좌표 점검용)
# 광명시 법정동 9개 — 표준데이터 지번주소의 세 번째 낱말이 법정동이다.
#   (행정동 광명1~7동·철산1~4동·하안1~4동·소하1~2동·일직동·학온동은 여러 법정동을 묶은 이름이라
#    주소에는 법정동이 적힌다. ‘학원동’은 시 홈페이지 요금표의 표기이고 조례·주소의 이름은 학온동이다.)
GM_DONGS = ("광명동", "철산동", "하안동", "소하동", "일직동", "학온동", "노온사동", "가학동", "옥길동")

GM_ORDINANCE_URL = "https://www.law.go.kr/LSW/ordinInfoP.do?chrClsCd=010202&gubun=ELIS&ordinSeq=2162053"
GM_CITY_URL = "https://www.gm.go.kr/pt/ns/gi/czfacility/PTMN207/PTGI0042.jsp"
GM_CORP_FACIL_URL = "https://gmuc.co.kr/user/conn/parkFacil.do"
GM_CORP_PUBLIC_URL = "https://www.gmuc.co.kr/user/conn/parkPublic.do"
GM_CORP_PRICE_URL = "https://www.gmuc.co.kr/user/conn/parkPrice.do"
GM_CORP_TERMS_URL = "https://www.gmuc.co.kr/user/conn/parkTerms.do"
GM_CITY_TXT = RAW / "gm.go.kr_공영주차장_20261117.txt"
GM_FACIL_TXT = RAW / "gmuc.co.kr_공영주차장현황_20261117.txt"
GM_PUBLIC_TXT = RAW / "gmuc.co.kr_공영주차장안내_20261117.txt"
GM_PRICE_TXT = RAW / "gmuc.co.kr_이용요금_20261117.txt"
GM_TERMS_TXT = RAW / "gmuc.co.kr_이용약관_20261117.txt"
GM_ORD_TXT = RAW / "gwangmyeong.law.go.kr_주차장조례_20261117.txt"
GM_ORDINANCE_NOTE = "시행 2026-08-14 (경기도광명시조례 제3407호, 2026-08-14 일부개정)"

# 광명시 공영주차장 요금 — 「광명시 주차장 설치 및 관리 조례」 [별표 1]의 값으로, 광명시청 공영주차장
#   요금표(2026-11-17 확인)와 광명도시공사 이용요금(parkPrice)·요금 안내(parking2)에서 같은 값을 확인했다.
#   · 1급지(2급지 이외의 광명시 전지역): 최초 30분 800원 → 30분 초과 10분당 300원 →
#     <b>2시간 초과 10분당 400원</b>. 노외 1일 주차권 13,000원, 월 정기권 주간 75,000·야간 45,000원.
#   · 2급지(옥길동·학온동): 30분 500원 → 10분당 200원 → 2시간 초과 10분당 300원,
#     1일 8,000원, 월 정기권 주간 50,000·야간 30,000원.
#   · 거주지 전용(목감로 거주자우선): 30분 800원 → 10분당 300원 → 2시간 초과 10분당 400원,
#     1일 5,000원, 월 정기권 20,000원(주간·야간)·전일 40,000원.
#   · 전통시장(광명동 전통시장 지하): 30분 800원 → 10분당 300원 → 2시간 초과 10분당 500원,
#     1일 한도 없음. 시 홈페이지는 1일 주차권·월정기권을 시행하지 않는다고 적고,
#     광명도시공사는 야간(21시~익일 9시) 정기권 45,000원을 게시한다(카드에 함께 적음).
#   2023-11-10 조례 일부개정 전에는 30분 600원·10분당 200원·1일 7,500원이었고, 시 홈페이지의
#   ‘2급지 250원’ 표는 그 이전 값이 화면에 남은 것이다 — 도시공사·표준데이터(2026-04-17) 값이 최신이다.
GM_FEES = {
    1: {"base": 800, "unit": 300, "unit_after2h": 400, "day": 13_000,
        "month_day": 75_000, "month_night": 45_000, "month_all": 120_000},
    2: {"base": 500, "unit": 200, "unit_after2h": 300, "day": 8_000,
        "month_day": 50_000, "month_night": 30_000, "month_all": None},
}
GM_RESIDENT = {"base": 800, "unit": 300, "unit_after2h": 400, "day": 5_000,
               "month_day": 20_000, "month_night": 20_000, "month_all": 40_000}
GM_MARKET = {"base": 800, "unit": 300, "unit_after2h": 500, "day": None, "month_night": 45_000}
GM_GRADE_DONGS = ("옥길동", "학온동")     # 2급지
GM_BASE_MIN = 30
GM_UNIT_MIN = 10
GM_STEP_UNTIL = 120                      # 2시간 초과분부터 요율이 올라간다

# 광명시청 ‘공영주차장 현황’(2026-11-17 조회) — 노외 21곳·노상 10곳 31개소 2,373면.
#   표준데이터 이름 → (시 홈페이지 이름, 면수, 노상/노외, 유료/무료)
GM_CITY = {
    "뜨락": ("뜨락", 11, "노외", "유료"),
    "광삼로 뜨락": ("광산로 뜨락", 4, "노외", "무료"),
    "광명사거리": ("광명4동 광명사거리", 30, "노외", "유료"),
    "광명5동 한진1길": ("광명5동 한진1길", 4, "노외", "유료"),
    "광명새마을시장유료": ("광명5동 새마을시장 유료", 39, "노외", "유료"),
    "광북": ("광북", 170, "노외", "유료"),
    "광명시청 철산동지하": ("광명시청 철산동지하", 367, "노외", "유료"),
    "밤일부락 소형": ("밤일부락 소형", 8, "노외", "유료"),
    "개운어린이공원": ("개운어린이공원", 46, "노외", "유료"),
    "소하동 제1": ("소하 제1", 27, "노외", "무료"),
    "소하동 제3": ("소하 제3", 85, "노외", "유료"),
    "소하동 제4": ("소하 제4", 52, "노외", "유료"),
    "광명동굴 제3": ("광명동굴 제3", 168, "노외", "유료"),
    "철산상업지역 노외": ("철산상업지역 노외", 18, "노외", "유료"),
    "삼각주마을 제1": ("삼각주마을 제1", 48, "노외", "유료"),
    "삼각주마을 제2": ("삼각주마을 제2", 16, "노외", "유료"),
    "삼각주마을 제3": ("삼각주마을 제3", 22, "노외", "유료"),
    "광명동초등학교 지하": ("광명동초등학교 지하", 104, "노외", "유료"),
    "광명동(전통시장) 지하": ("광명동(전통시장) 지하", 176, "노외", "유료"),
    # 노상 10구간
    "철산동 등기소 주변": ("철산동 등기소 주변", 55, "노상", "유료"),
    "철산동 중앙로변": ("철산동 철산로변", 78, "노상", "유료"),
    "철산동 상업지역 제1": ("철산동 상업지역 제1", 124, "노상", "유료"),
    "철산동 상업지역 제2": ("철산동 상업지역 제2", 67, "노상", "유료"),
    "자동차경매장 주변": ("자동차매장 주변", 25, "노상", "유료"),
    "하안동 상업지역 제1": ("하안동 상업지역 제1", 91, "노상", "유료"),
    "하안동 상업지역 제2": ("하안동 상업지역 제2", 103, "노상", "유료"),
    "목감천 거주자우선": ("목감로 거주자우선", 121, "노상", "유료"),
    "범안로 임시": ("범안로 임시", 22, "노상", "유료"),
}
# 광명도시공사 운영현황(2026-11-17 조회) — 표준데이터에 없는 소하 제1·3·4노외의 면수가 다르고,
#   노상 8구간의 면수가 시 홈페이지와 1~2면씩 다르다. 값은 참고로만 두고 등록면수(표준데이터·
#   시 홈페이지)를 쓴다 — 차이는 카드에 적는다.
GM_CORP_SPACES = {
    "광명동(전통시장) 지하": 176, "광명동초등학교 지하": 104, "개운어린이공원": 46,
    "철산상업지역 노외": 18, "삼각주마을 제1": 48, "삼각주마을 제2": 16,
    "삼각주마을 제3": 22, "광명시청 철산동지하": 367, "광북": 170, "광명동굴 제3": 168,
    "소하동 제1": 73, "소하동 제3": 93, "소하동 제4": 52,
    "철산동 등기소 주변": 54, "철산동 중앙로변": 77, "철산동 상업지역 제1": 124,
    "철산동 상업지역 제2": 67, "하안동 상업지역 제1": 91, "하안동 상업지역 제2": 103,
    "자동차경매장 주변": 25, "범안로 임시": 22,
}
# 표준데이터에 없고 시 홈페이지·도시공사 안내에만 있는 주차장 — 주소·면수·운영방법·운영시간이
#   모두 공개된 곳만 넣는다(이름만 있는 행은 넣지 않는다). 좌표는 원자료에 없어 지도는 주소 검색으로 건다.
GM_EXTRA = [
    {"name": "안현철골", "jibun": "경기도 광명시 하안동 577-1", "road": "",
     "spaces": 192, "dong": "하안동", "ptype": "노외", "pay": "유료",
     "spec": ("24H", "24H", "24H"), "tel": "02-2610-7390",
     "src": "광명시 공영주차장 현황",
     "notice": "광명시 공영주차장 현황(노외 21곳)에만 등록되어 있고 표준데이터·도시공사 운영현황에는 "
               "없습니다 — 192면 규모의 건물식(철골) 주차장입니다"},
    {"name": "광명6동 노외", "jibun": "경기도 광명시 광명동 748-5", "road": "",
     "spaces": 75, "dong": "광명동", "ptype": "노외", "pay": "유료",
     "spec": ("24H", "24H", "24H"), "tel": "02-2680-6499",
     "src": "광명시 공영주차장 현황",
     "notice": "광명시 공영주차장 현황에만 등록되어 있고 표준데이터에는 없습니다 — 75면 규모입니다"},
    {"name": "광명6동 소형", "jibun": "경기도 광명시 광명동 390-6", "road": "",
     "spaces": 25, "dong": "광명동", "ptype": "노상", "pay": "무료",
     "spec": ("24H", "24H", "24H"), "tel": "02-2680-6499",
     "src": "광명시 공영주차장 현황",
     "notice": "광명시 공영주차장 현황에 ‘무료’로 등록된 소형 노상 주차장입니다(표준데이터 미등록)"},
    {"name": "새빛공원", "jibun": "경기도 광명시 일직동 424", "road": "",
     "spaces": 52, "dong": "일직동", "ptype": "노외", "pay": "유료",
     "spec": ("09:00~18:00", "09:00~18:00", "09:00~18:00"), "tel": "02-2610-7390",
     "src": "광명도시공사 공영주차장 현황",
     "notice": "광명도시공사 운영현황(일직동)에만 있는 주차장입니다 — 평일 09:00~18:00 유료, "
               "주말·공휴일은 무료 개방(도시공사 안내)이고 1일 주차권은 13,000원입니다"},
]
GM_EXTRA_FREE_DAYS = ("새빛공원",)     # 주말·공휴일 무료 개방

# 시간 주차요금 없이 월 정기권만 등록된 주차장 — 0원이 아니라 ‘요금 정보 미상(정기권 전용)’으로 둔다.
#   (광명시청·행정복지센터가 관리하는 소형 주차장으로, 표준데이터에 월정기권 금액만 있다.)
GM_TICKET_ONLY = ("뜨락", "광명5동 한진1길", "밤일부락 소형")

# 노상에서 주말·공휴일에 요금을 받지 않는 구간(광명시 홈페이지 ‘주말, 공휴일 무료’).
#   철산동 상업지역 제1·2는 ‘명절 무료’만이라 주말에도 요금을 받는다.
GM_STREET_WEEKEND_FREE = ("철산동 등기소 주변", "철산동 중앙로변", "자동차경매장 주변",
                          "하안동 상업지역 제1", "하안동 상업지역 제2", "범안로 임시")
GM_STREET_HOLIDAY_ONLY = ("철산동 상업지역 제1", "철산동 상업지역 제2")

# 광명시 ‘공영주차장 할인대상’(조례 제6조제4항·시 홈페이지·광명도시공사 할인 안내) —
#   · 면제: 긴급자동차, 납세자 관련 차량용 증명표지 부착 차량(모범납세자)
#   · 2시간 무료 후 50%: 국가유공자·상이자, 고엽제후유의증, 5·18민주유공자 부상자, 장애인,
#     3자녀 이상(막내 만15세 이하), 전기·수소·태양광 자동차
#   · 50%: 경형자동차(경차), 장기 등 기증자·기증등록자, 저공해자동차, 우수자원봉사자,
#     병역명문가, 2자녀 이상(막내 만15세 이하)
#   · 그 밖에 승용차 부제·함께타기 20%, 전통시장 주차권 30분 감면
GM_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해 50%", "rate": 0.5, "exempt_min": 0,
     "note": "「자동차관리법」에 따른 경형자동차, 저공해자동차 표지부착차량, 장기 등 기증자·기증등록자, "
             "우수자원봉사자증 소지자, 병역명문가증 제시자, 2자녀 이상 가정(막내 만15세 이하)"},
    {"label": "유공자·장애인 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "국가유공자·상이자, 고엽제후유의증 환자, 5·18민주유공자 부상자, 등록 장애인, "
             "3자녀 이상 가정, 전기·수소·태양광 자동차 — 최초 2시간 면제 뒤 50%"},
    {"label": "긴급·납세자 차량 면제", "rate": 1.0, "exempt_min": 0,
     "note": "긴급자동차, 납세자 관련 차량용 증명표지 부착 차량(모범납세자)"},
]


def gm_dong_of(text: str):
    """주소에서 광명시 법정동을 뽑는다 — ‘경기도 광명시 {법정동} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "광명시" and parts[2] in GM_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(GM_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def gm_win(spec):
    """도시공사·시 안내 운영시간 문자열 → 사이트 공통 hours 객체."""
    win = {}
    for key, txt in zip(("weekday", "sat", "sun"), spec):
        if txt in ("24H", "무료개방"):
            win[key] = {"open": True, "start": 0, "end": 1440, "24h": True,
                        "listed": True, "raw": ["00:00", "24:00"]}
        else:
            m = re.match(r"(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})", txt)
            s = int(m.group(1)) * 60 + int(m.group(2))
            e = int(m.group(3)) * 60 + int(m.group(4))
            win[key] = {"open": True, "start": s, "end": e, "24h": False,
                        "listed": True, "raw": [f"{s // 60:02d}:{s % 60:02d}",
                                                f"{e // 60:02d}:{e % 60:02d}"]}
    return win


def gm_steps(t):
    """30분 기본요금 뒤 10분 단위, 2시간을 넘으면 요율이 올라가는 2단계 요금."""
    return [{"until": GM_STEP_UNTIL, "unit_min": GM_UNIT_MIN, "unit_fee": t["unit"]},
            {"until": None, "unit_min": GM_UNIT_MIN, "unit_fee": t["unit_after2h"]}]


def gm_fee(kind: str, street: bool, monthly=None):
    """광명시 공영주차장 요금 → 사이트 공통 fee 객체.

    kind: ‘1급지’·‘2급지’·‘전통시장’·‘거주지’
    노상에는 1일 주차권이 없다(광명도시공사 요금표 ‘일 최대 요금(노외 한정)’).
    """
    if kind == "전통시장":
        t, label, day = GM_MARKET, "별표1 전통시장", None
    elif kind == "거주지":
        t, label, day = GM_RESIDENT, "별표1 거주지 전용", GM_RESIDENT["day"]
    else:
        t = GM_FEES[1 if kind == "1급지" else 2]
        label, day = f"별표1 {kind}", (None if street else t["day"])
    fee = {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": (1 if kind == "1급지" else 2 if kind == "2급지" else None),
        "std_grade": None,
        "base_min": GM_BASE_MIN, "base_fee": t["base"],
        "unit_min": GM_UNIT_MIN, "unit_fee": t["unit"],
        "steps": gm_steps(t), "steps_label": "2시간 초과 10분당 {}".format(
            won_kr(t["unit_after2h"])),
        "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": None, "daily_fee": day,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": monthly, "monthly_day": t.get("month_day"),
        "monthly_night": t.get("month_night"), "monthly_all": t.get("month_all"),
        "pay": "", "basis": f"「광명시 주차장 설치 및 관리 조례」 {label}",
        "category": None, "portal_free_now": False, "flat_day": False, "ticket_only": False,
    }
    if monthly and not fee["monthly_all"]:
        fee["monthly_all"] = monthly
    return fee


def won_kr(n):
    return f"{n:,}원"


def gm_free_fee(**extra):
    fee = {"type": "무료", "raw_type": "무료", "mixed": False, "grade": None, "std_grade": None,
           "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
           "steps": None, "free_min": None, "deduct_min": None, "cap_fee": None, "cap_src": None,
           "daily_hours": None, "daily_fee": None, "prepaid_day": None, "prepaid_weekend": None,
           "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
           "pay": "", "basis": "요금 구분 ‘무료’", "category": None, "portal_free_now": False,
           "flat_day": False, "ticket_only": False, "std": None}
    fee.update(extra)
    return fee


def gm_ticket_fee(monthly=None, raw_type="유료", basis="월 정기권 전용(시간 주차요금 미게시)"):
    return {"type": "미상", "raw_type": raw_type, "mixed": False, "grade": None,
            "std_grade": None, "base_min": None, "base_fee": None, "unit_min": None,
            "unit_fee": None, "steps": None, "free_min": None, "deduct_min": None,
            "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
            "prepaid_day": None, "prepaid_weekend": None, "monthly": monthly,
            "monthly_day": None, "monthly_night": None, "monthly_all": None,
            "pay": "", "basis": basis, "category": None,
            "portal_free_now": False, "flat_day": False, "ticket_only": True, "std": None}


def build_gwangmyeong():
    """광명시 공영주차장을 표준데이터 + 광명시 공영주차장 현황 + 광명도시공사 안내 + 조례 별표1로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 광명시 범위를 벗어난 행은 제외(껍데기 행).
      · 광명시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다.
    요금은 조례 별표1(1·2급지·거주지 전용·전통시장)을 적용하고, 운영시간은 표준데이터의 등록값을
    쓰되 주말·공휴일 무료 개방과 노상 요금 시간을 시·도시공사 안내로 보정했다(노외는 24시간 연중무휴).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GM_PROVIDER]
    lots, excluded, merged, hour_fixed, space_diff, note_fixed = [], [], [], [], [], []
    corp_missing, ticket_diff, city_only = [], [], []
    seen = {}
    card_no = street_no = 0

    def add_lot(name, jibun, road, ptype, spaces, dong, pay, win, oper, fee, r=None,
                src="표준데이터", notice=None, tel="", mgmt="", lat=None, lng=None,
                base_date="", free_days=None, free_note=None):
        nonlocal card_no, street_no
        street = ptype == "노상"
        if street:
            street_no += 1
            lot_id = f"gmy-s{street_no:03d}"
        else:
            card_no += 1
            lot_id = f"gmy-{card_no:03d}"
        fee["pay"] = (r.get("결제방법") or "").strip() if r else ""
        lots.append({
            "id": lot_id,
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": src,
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "광명시",
            "dong": dong,
            "dong_src": "지번주소" if r and gm_dong_of((r.get("소재지지번주소") or "")) else
                        ("도로명주소" if r and gm_dong_of((r.get("소재지도로명주소") or "")) else
                         ("시 홈페이지 주소" if src != "표준데이터" else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": (re.match(r"^([가-힣0-9]+(?:대로|로|길))", name).group(1)
                     if street and re.match(r"^([가-힣0-9]+(?:대로|로|길))", name) else None),
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "광명시",
            "note": (r.get("특기사항") or "").strip() if r else "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "광명시",
            "city_slug": "gwangmyeong",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        jibun_key = re.sub(r"\s", "", jibun)
        name_key = re.sub(r"\s+", "", name)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif name_key and ("이름", name_key, ptype) in seen:
            dup_key = ("이름", name_key, ptype)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and name_key:
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", name_key, ptype)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (GM_BBOX[0] <= lat <= GM_BBOX[1]
                                     and GM_BBOX[2] <= lng <= GM_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = gm_dong_of(jibun) or gm_dong_of(road)
        pay = (r.get("요금정보") or "").strip()
        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        free_days = {"sat": False, "sun": False}
        free_note = None

        # 노상은 시·도시공사 안내의 요금 부과 시간(평일 10:00~19:00)과 주말·공휴일 무료 개방을 쓴다.
        if street and name in GM_STREET_WEEKEND_FREE:
            want = gm_win(("10:00~19:00", "10:00~19:00", "10:00~19:00"))
            if any(win[k]["start"] != want[k]["start"] or win[k]["end"] != want[k]["end"]
                   for k in ("weekday", "sat", "sun")):
                hour_fixed.append(
                    f"{name}: 표준데이터 토·공휴일 휴무(00:00~00:00) → 시 안내 평일 10:00~19:00 · "
                    f"주말·공휴일 무료 개방")
            win = want
            oper = {k: True for k in ("weekday", "sat", "sun")}
            free_days = {"sat": True, "sun": True}
            free_note = "토요일·일요일·공휴일에는 요금을 받지 않습니다(광명시 홈페이지 안내)"
        elif street and name in GM_STREET_HOLIDAY_ONLY:
            want = gm_win(("10:00~19:00", "10:00~19:00", "10:00~19:00"))
            win, oper = want, {k: True for k in ("weekday", "sat", "sun")}
            hour_fixed.append(f"{name}: 토·공휴일 휴무(00:00~00:00) → 시 안내 10:00~19:00(명절 연휴만 무료)")
            free_note = "평일·토요일·일요일에 요금을 받고, 명절 연휴에만 무료입니다(광명시 홈페이지 안내)"
        elif street and name == "목감천 거주자우선":
            want = gm_win(("24H", "24H", "24H"))
            win, oper = want, {k: True for k in ("weekday", "sat", "sun")}
            hour_fixed.append(f"{name}: 거주자우선주차장 — 24시간 연중무휴(도시공사 이용약관)")

        if name in GM_TICKET_ONLY:
            monthly = to_int(r.get("월정기권요금"))
            fee = gm_ticket_fee(monthly=monthly, raw_type=pay or "유료",
                                basis="월 정기권 전용(시간 주차요금 미게시)")
            ticket_diff.append(f"{name}: 월 정기권 {monthly:,}원만 등록" if monthly else name)
        elif name == "목감천 거주자우선":
            fee = gm_fee("거주지", street=True, monthly=to_int(r.get("월정기권요금")))
        elif pay == "무료":
            fee = gm_free_fee()
        elif name == "광명동(전통시장) 지하":
            fee = gm_fee("전통시장", street=street)
        else:
            grade = "2급지" if dong in GM_GRADE_DONGS else "1급지"
            fee = gm_fee(grade, street=street, monthly=to_int(r.get("월정기권요금")))
        fee["std_grade"] = to_int(r.get("급지구분"))
        fee["std"] = {"base_min": to_int(r.get("주차기본시간")), "base_fee": to_int(r.get("주차기본요금")),
                      "unit_min": to_int(r.get("추가단위시간")),
                      "unit_fee": to_int(r.get("추가단위요금")),
                      "day": to_int(r.get("1일주차권요금")), "monthly": to_int(r.get("월정기권요금"))}

        notice = None
        if name == "광명동(전통시장) 지하":
            notice = ("전통시장 공영주차장 — 2시간이 지나면 10분당 500원이고 1일 한도 금액이 없습니다"
                      "(표준데이터 특기사항은 400원으로 등록되어 있으나 시·도시공사 요금표의 500원을 썼습니다). "
                      "시 홈페이지는 1일 주차권·월정기권을 시행하지 않는다고 적고, 광명도시공사는 "
                      "야간(21:00~익일 09:00) 정기권 45,000원을 게시합니다(현장 확인)")
        elif name == "목감천 거주자우선":
            notice = ("거주자우선주차장입니다 — 배정 차량은 월 정기권(전일 40,000원·주간/야간 20,000원)을 "
                      "내고, 비배정 차량은 ‘모두의 주차장’ 앱 공유주차로만 30분당 800원·1회 5,000원까지 "
                      "이용할 수 있습니다(도시공사 이용약관). 계산기의 시간 요금은 조례 별표1의 "
                      "‘거주지 전용’(30분 800원·10분당 300원·1일 5,000원)입니다")
        elif name in GM_TICKET_ONLY:
            m = to_int(r.get("월정기권요금"))
            notice = ("시간 주차요금 없이 월 정기권만 등록된 주차장입니다 — "
                      + (f"월 정기권은 {m:,}원입니다" if m else "월 정기권 금액은 게시되어 있지 않습니다"))
        elif name in ("광삼로 뜨락", "소하동 제1"):
            notice = ("광명시 공영주차장 현황·표준데이터 모두 요금 구분이 ‘무료’인 주차장입니다"
                      if name == "광삼로 뜨락" else
                      "광명시 공영주차장 현황·표준데이터 모두 ‘무료’로 등록된 주차장입니다"
                      "(도시공사 ‘그 외 주차장’ 표에는 유료로 적혀 있어 현장 확인이 필요합니다)")
        elif name == "광명사거리":
            notice = "09:00~01:00(자정 넘김) 운영으로 등록되어 있어 화면에는 09:00~24:00으로 적었습니다"
        elif street and name in GM_STREET_HOLIDAY_ONLY:
            notice = "명절 연휴에만 무료이고 평일·토요일·일요일에는 10:00~19:00 요금을 받습니다"
        elif street:
            notice = "평일 10:00~19:00에만 요금을 받고, 주말·공휴일은 무료로 개방합니다(광명시 홈페이지)"

        if name in GM_CITY:
            city_name, city_spaces, city_type, city_pay = GM_CITY[name]
            if city_spaces != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 시 홈페이지 {city_spaces}면")
                notice = ((notice + " · ") if notice else "") + \
                    f"광명시 공영주차장 현황은 {city_spaces}면으로 안내합니다(표준데이터 {spaces}면)"
            if city_pay == "무료" and pay != "무료":
                note_fixed.append(f"{name}: 표준데이터 ‘{pay}’ ↔ 시 홈페이지 ‘무료’")
        if name in GM_CORP_SPACES and GM_CORP_SPACES[name] != spaces:
            space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 도시공사 {GM_CORP_SPACES[name]}면")
            notice = ((notice + " · ") if notice else "") + \
                f"광명도시공사는 {GM_CORP_SPACES[name]}면으로 안내합니다"
        if name not in GM_CORP_SPACES and name not in ("뜨락", "광삼로 뜨락", "광명사거리",
                                                      "광명새마을시장유료", "광명5동 한진1길",
                                                      "밤일부락 소형", "소하동 제1"):
            corp_missing.append(name)

        add_lot(name, jibun, road, ptype, spaces, dong, pay, win, oper, fee, r=r,
                notice=notice, tel=(r.get("전화번호") or "").strip(),
                mgmt=(r.get("관리기관명") or "").strip() or "광명시",
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    # 표준데이터에 없고 시 홈페이지·도시공사 안내에만 있는 주차장
    for e in GM_EXTRA:
        win = gm_win(e["spec"])
        oper = {k: True for k in ("weekday", "sat", "sun")}
        free_days = {"sat": False, "sun": False}
        free_note = None
        if e["name"] in GM_EXTRA_FREE_DAYS:
            free_days = {"sat": True, "sun": True}
            free_note = "토요일·일요일·공휴일은 무료로 개방합니다(광명도시공사 안내)"
        if e["pay"] == "무료":
            fee = gm_free_fee()
        else:
            fee = gm_fee("2급지" if e["dong"] in GM_GRADE_DONGS else "1급지",
                         street=(e["ptype"] == "노상"))
        city_only.append(e["name"])
        add_lot(e["name"], e["jibun"], e["road"], e["ptype"], e["spaces"], e["dong"], e["pay"],
                win, oper, fee, src=e["src"], notice=e["notice"], tel=e["tel"],
                mgmt="광명시", base_date="2026-11-17", free_days=free_days, free_note=free_note)

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"gmy-{i:03d}" if l["list_mode"] == "card" else f"gmy-s{i:03d}"

    quality = check_quality_gwangmyeong(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                        space_diff, note_fixed, ticket_diff, corp_missing,
                                        city_only)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(GM_CITY_TXT).strftime("%Y-%m-%d %H:%M")
                           if GM_CITY_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "광명시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-17",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 광명시가 등록한 28행(노외 19·노상 9)을 읽었다. 이름·주소·구획수·"
                             "운영요일·운영시간·좌표·전화·관리번호·결제방법·특기사항과 등록요금 출처로 썼다."),
                },
                {
                    "id": "ordinance", "name": "광명시 주차장 설치 및 관리 조례 [별표 1] 공영주차장 주차요금",
                    "org": "광명시(대중교통과)",
                    "url": GM_ORDINANCE_URL,
                    "file": GM_ORD_TXT.name,
                    "sha256": sha256(GM_ORD_TXT) if GM_ORD_TXT.exists() else None,
                    "license": "자치법규(공개)",
                    "base_date": GM_ORDINANCE_NOTE,
                    "rows_total": None,
                    "fetched_at": _sync_time(GM_ORD_TXT),
                    "note": ("1급지 최초 30분 800원·10분당 300원(2시간 초과 400원)·1일 13,000원·"
                             "월 정기권 주간 75,000원·야간 45,000원, 2급지(옥길동·학온동) 500·200·300원·"
                             "1일 8,000원, 거주지 전용 800·300·400원·1일 5,000원, 전통시장 2시간 초과 "
                             "10분당 500원(1일 한도 없음)을 확인했다. 조문 일부만 받아 옮겼고, 별표 금액은 "
                             "광명시 공영주차장 요금표·광명도시공사 이용요금의 같은 표로 대조했다."),
                },
                {
                    "id": "city", "name": "광명시 공영주차장 현황·요금표·할인대상·운영시간",
                    "org": "광명시 대중교통과 주차시설팀(02-2680-6499)",
                    "url": GM_CITY_URL,
                    "file": GM_CITY_TXT.name if GM_CITY_TXT.exists() else None,
                    "sha256": sha256(GM_CITY_TXT) if GM_CITY_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 31,
                    "fetched_at": _sync_time(GM_CITY_TXT),
                    "note": ("노외 21곳·노상 10곳 31개소 2,373면의 이름·위치·면수·유료/무료, 요금표"
                             "(1급지·2급지·거주지 전용), 할인대상, 노상 운영시간(10:00~19:00·주말·공휴일 "
                             "무료) 확인용."),
                },
                {
                    "id": "corp", "name": "광명도시공사 공영주차장 운영현황·공영주차장 안내",
                    "org": "광명도시공사 주차관리팀(02-2610-7390)",
                    "url": GM_CORP_FACIL_URL,
                    "file": f"{GM_FACIL_TXT.name} · {GM_PUBLIC_TXT.name}",
                    "sha256": sha256(GM_FACIL_TXT) if GM_FACIL_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": 25,
                    "fetched_at": _sync_time(GM_FACIL_TXT),
                    "note": ("노외 11곳·노상 8곳·거주자 1곳·부설 5곳의 면수와 운영시간(24시간 연중무휴, "
                             "새빛공원 평일 09:00~18시·주말 무료), 운영방법(시간/월정기), 소하 제1·3·4 "
                             "노외의 면수 확인용. 실시간 잔여면수는 게시되어 있지 않다."),
                },
                {
                    "id": "price", "name": "광명도시공사 공영주차장 이용요금·할인 안내",
                    "org": "광명도시공사",
                    "url": GM_CORP_PRICE_URL,
                    "file": GM_PRICE_TXT.name if GM_PRICE_TXT.exists() else None,
                    "sha256": sha256(GM_PRICE_TXT) if GM_PRICE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": None,
                    "fetched_at": _sync_time(GM_PRICE_TXT),
                    "note": ("시간주차 800·300·400원과 일 최대 13,000원(노외 한정, 철산 상업지역은 상한 "
                             "없음), 전통시장 2시간 초과 500원, 월정기권(전일 120,000·주간 75,000·야간 "
                             "45,000원, 광명동굴 제3 80,000원, 개운어린이공원 70,000원, 목감로 거주자 "
                             "40,000원)과 시간주차·월정기권 할인표 확인용."),
                },
                {
                    "id": "terms", "name": "광명도시공사 공영주차장 이용약관",
                    "org": "광명도시공사",
                    "url": GM_CORP_TERMS_URL,
                    "file": GM_TERMS_TXT.name if GM_TERMS_TXT.exists() else None,
                    "sha256": sha256(GM_TERMS_TXT) if GM_TERMS_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)",
                    "base_date": "2026-11-17 확인",
                    "rows_total": None,
                    "fetched_at": _sync_time(GM_TERMS_TXT),
                    "note": ("노상 8구간의 평일 10:00~19:00·주말·공휴일 휴무, 노외 24시간 연중무휴, "
                             "월정기주차 운영 주차장과 주간(08:00~19:00)·야간(19:00~익일 08:00) 시간, "
                             "거주자우선 공유주차 30분 800원·1회 5,000원 확인용."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GM_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "gwangmyeong_steps",
            "unit_min": GM_UNIT_MIN,
            "base_min": GM_BASE_MIN,
            "free_min": 0,
            "applies": GM_ORDINANCE_NOTE + " · 2023-11-10 요금 적용",
            "off": [
                {"grade": 1, "base": 800, "unit": 300, "after": 400, "day": 13_000,
                 "month_day": 75_000, "month_night": 45_000, "month_all": 120_000,
                 "where": "2급지 이외의 광명시 전지역", "lots": 0},
                {"grade": 2, "base": 500, "unit": 200, "after": 300, "day": 8_000,
                 "month_day": 50_000, "month_night": 30_000, "month_all": None,
                 "where": "옥길동·학온동", "lots": 0},
            ],
            "special": [
                {"name": "광명동(전통시장) 지하", "base": 800, "unit": 300, "after": 500,
                 "day": None, "note": "2시간 초과 10분당 500원 · 일 한도 없음 · 야간 정기권 45,000원"},
                {"name": "목감로 거주자우선(거주지 전용)", "base": 800, "unit": 300, "after": 400,
                 "day": 5_000, "note": "월 정기권 주간·야간 20,000원 · 전일 40,000원 · 공유주차 30분 800원"},
            ],
            "corp": {"out": 11, "st": 8, "resident": 1, "att": 5, "city": 31},
            "basis": ("「광명시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금"
                      f"({GM_ORDINANCE_NOTE}) · 광명시 공영주차장 요금표 · 광명도시공사 이용요금(2026-11-17 확인)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["광명시"] | {
        "city": "광명시",
        "weekend_free_pages": False,
        "discounts": GM_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "gwangmyeong_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_gwangmyeong(std_all, rows, lots, excluded, merged, hour_fixed,
                              space_diff, note_fixed, ticket_diff, corp_missing, city_only):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_광명시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "특기사항_보정": note_fixed,
        "정기권_금액없음": ticket_diff,
        "공사_현황_없음": corp_missing,
        "시_홈페이지에만": city_only,
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }



# ---------------------------------------------------------------- 구리시 (T-03 Phase 18)
GR_PROVIDER = "경기도 구리시"
# 구리시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
GR_DISTRICTS = [("구리시", "guri")]
GR_BBOX = (37.54, 37.64, 127.09, 127.18)   # 구리시 대략 경계(좌표 점검용)
# 구리시 법정동 9개 — 표준데이터 지번주소의 세 번째 낱말이 법정동이다.
#   (행정동 교문1·2동, 수택1·2·3동, 인창동, 동구동, 갈매동은 여러 법정동을 묶은 이름이라
#    주소에는 법정동이 적힌다. 이 사이트의 카드 9곳은 수택동 6·인창동 2·교문동 1이다.)
GR_DONGS = ("교문동", "수택동", "인창동", "동구동", "갈매동", "아천동", "사노동", "토평동", "학동")

GR_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?chrClsCd=010202"
                    "&gubun=ELIS&ordinSeq=1864905")
GR_CITY_NOOE_URL = "https://www.guri.go.kr/www/contents.do?key=707"
GR_CITY_STREET_URL = "https://www.guri.go.kr/www/contents.do?key=706"
GR_CITY_DISCOUNT_URL = "https://www.guri.go.kr/www/contents.do?key=708"
GR_CITY_SHARE_URL = "https://www.guri.go.kr/www/contents.do?key=6896"
GR_NOOE_TXT = RAW / "guri.go.kr_노외주차장_20261117.txt"
GR_STREET_TXT = RAW / "guri.go.kr_노상주차장_20261117.txt"
GR_DISC_TXT = RAW / "guri.go.kr_주차요금감면_20261117.txt"
GR_SHARE_TXT = RAW / "guri.go.kr_공유주차장_20261117.txt"
GR_ORD_TXT = RAW / "guri.law.go.kr_주차장조례_20261117.txt"
GR_ORDINANCE_NOTE = ("시행 2023-10-16 · 경기도구리시조례 제2161호"
                     "(국가법령정보센터) · 최신 공포본 2026-04-06")

# 구리시 공영주차장 요금 — 「구리시 주차장 조례」 [별표 1] 공영주차장 주차요금표
#   (국가법령정보센터 별표/서식에서 펼쳐 읽음)의 값이다. 구리시 홈페이지 노외·노상 주차장
#   요금표(최종수정 2026-10-30)와 표준데이터 등록값이 같은 숫자다 — 세 자료로 대조했다.
#   · 노상 1급지 30분 700원 → 10분당 300원, 1일 주차권 9,000원(적용 10시간), 월 정기권 없음
#   · 노상 2급지 30분 500원 → 10분당 200원, 1일 주차권 6,000원
#   · 노외 1급지 30분 600원 → 10분당 200원, 1일 주차권 8,000원, 월 정기권 70,000원
#   · 노외 2급지 30분 500원 → 10분당 200원, 1일 주차권 6,000원, 월 정기권 50,000원
#   · 노외 3급지 30분 400원 → 10분당 100원, 1일 주차권 5,000원, 월 정기권 40,000원
#   · 거주자전용(조례 별표1): 월 정기권 전일 30,000원 · 주간 20,000원 · 야간 20,000원
#   별표 비고: 1급지=상업지역·준주거지역·인창유수지 주차장, 2급지=일반주거지역,
#   3급지=그 밖의 지역·옥밭굴 지하주차장. 노외는 ‘1일 단위 시간당 주차요금의 합계액이
#   1일 주차요금을 초과할 수 없다’(조례 제5조①·별표 비고1) — 1일 주차권이 시간요금의 상한이다.
GR_FEES = {
    "노상": {1: {"base": 700, "unit": 300, "day": 9_000, "month": None},
             2: {"base": 500, "unit": 200, "day": 6_000, "month": None}},
    "노외": {1: {"base": 600, "unit": 200, "day": 8_000, "month": 70_000},
             2: {"base": 500, "unit": 200, "day": 6_000, "month": 50_000},
             3: {"base": 400, "unit": 100, "day": 5_000, "month": 40_000}},
}
GR_BASE_MIN = 30
GR_UNIT_MIN = 10

# 노상 구간의 도로명 — 시 홈페이지 ‘노상주차장’ 위치 표기(표준데이터 이름은 ‘제N공영노상주차장’뿐).
GR_ROADS = {
    "제1공영노상주차장": "검배로",
    "제2공영노상주차장": "안골로",
    "제6공영노상주차장": "동구릉로85번길",
    "제7공영노상주차장": "장자대로86번길",
    "제9공영노상주차장": "수택천로",
    "제10공영노상주차장": "건원대로34번길",
}
# 요일·공휴일에 요금을 받지 않는 노외 주차장 — 시 홈페이지 ‘제4~제7공영 → 월~토요일
#   유료(06:00~22:00) / 일요일, 공휴일 무료’. 표준데이터는 공휴일 칸을 00:00~00:00(미운영)으로
#   두었고, 구리시 안내는 ‘무료 개방’이라 그 값으로 바로잡았다.
GR_NOOE_SUN_FREE = ("제4공영노외주차장", "제5공영노외주차장", "제6공영노외주차장")
# 노상 6구간 — 평일 09:00~19:00, 토요일 09:00~17:00에만 요금을 받고 일요일·공휴일은 무료다.
GR_STREET_HOURS = ("09:00~19:00", "09:00~17:00", "09:00~19:00")
# 시 홈페이지와 표준데이터의 면수가 다른 곳 — 표준데이터 등록면수를 쓰고 카드에 적는다.
#   제5공영노외 249면(표준데이터) ↔ 217면(시 홈페이지·언론 보도), 제9공영노상 15면 ↔ 14면.
GR_SPACE_DIFF = {"제5공영노외주차장": 217, "제9공영노상주차장": 14}

# 구리시 ‘주차요금의 경감 및 면제대상’(조례 제6조, 최종수정 2026-10-30) —
#   · 면제: 긴급차량, 공무수행차량, 외교사절 일행, 유공납세증(1년), 투표확인증(2천원 범위 1회),
#     국가유공자·다자녀 가정 차량은 1회 주차 48시간(노외 한정), 노상 5분 이내 주차
#   · 50% + 1일 1회 3시간 면제: 등록장애인, 고엽제후유의증, 5·18민주화운동 부상자,
#     국가유공자(노상은 50%만)
#   · 50% + 1일 1회 2시간 면제: 환경친화적 자동차(전기·수소 등), 다자녀 가정(노상)
#   · 50%: 경형자동차, 저공해자동차, 장기기증자·등록자, 우수자원봉사자(연 100시간 이상),
#     병역명문가, 효행 부양자, 의사자 유족·의상자, 구리시 시민대상 수상자
#   · 20%: 승용차 요일제 참여차량
#   감면사유가 둘 이상이면 감면율이 높은 하나만 적용하고 100원 미만은 절사한다.
GR_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·장기기증 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형자동차(「자동차관리법」), 저공해 표시 스티커 부착 차량, 장기기증자·장기기증 등록자, "
             "우수자원봉사자(연 100시간 이상), 병역명문가 예우대상자·가족, 효행 부양자(세대주), "
             "의사자 유족·의상자 및 가족, 구리시 시민대상 수상자"},
    {"label": "장애인·유공자 3시간 면제 후 50%", "rate": 0.5, "exempt_min": 180,
     "note": "등록장애인 운전·동반 차량, 고엽제후유의증 환자 비사업용 차량, 5·18민주화운동 부상자 "
             "운전·동반 차량, 국가유공자 증서 제시자 탑승 차량 — 1일 1회 3시간까지 전액 면제 뒤 50%"},
    {"label": "환경친화적 자동차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "「구리시 환경친화적 자동차의 보급 및 이용활성화를 위한 지원 조례」에 따른 전기·수소 등 "
             "환경친화적 자동차 — 1일 1회 2시간까지 전액 면제 뒤 50%(노외는 다자녀 가정도 48시간 면제)"},
    {"label": "승용차 요일제 20%", "rate": 0.2, "exempt_min": 0,
     "note": "10인승 이하 비영업용 승용·승합차로 요일제 전자태그를 붙이고 운휴일을 지킨 차량"},
    {"label": "긴급·공무·유공납세 차량 면제", "rate": 1.0, "exempt_min": 0,
     "note": "긴급차량, 국가·지방자치단체 공무수행차량(관용), 외교사절 및 수행자 차량, "
             "유공납세증 스티커 부착 차량(교부일부터 1년), 투표확인증 제출 차량(2천원 범위 1회)"},
]


def gr_dong_of(text: str):
    """주소에서 구리시 법정동을 뽑는다 — ‘경기도 구리시 {법정동} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "구리시" and parts[2] in GR_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(GR_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def gr_win(spec):
    """시 홈페이지 운영시간 문자열(‘09:00~19:00’) → 사이트 공통 hours 객체."""
    win = {}
    for key, txt in zip(("weekday", "sat", "sun"), spec):
        if txt in ("24H", "무료개방"):
            win[key] = {"open": True, "start": 0, "end": 1440, "24h": True,
                        "listed": True, "raw": ["00:00", "24:00"]}
        else:
            m = re.match(r"(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})", txt)
            s = int(m.group(1)) * 60 + int(m.group(2))
            e = int(m.group(3)) * 60 + int(m.group(4))
            win[key] = {"open": True, "start": s, "end": e, "24h": False,
                        "listed": True, "raw": [f"{s // 60:02d}:{s % 60:02d}",
                                                f"{e // 60:02d}:{e % 60:02d}"]}
    return win


def gr_fee(grade: int, street: bool, daily=None, daily_hours=None, monthly=None):
    """구리시 공영주차장 요금 → 사이트 공통 fee 객체.

    조례 별표1은 노상·노외의 기본요금이 다르고(노상 1급지 700원·노외 1급지 600원),
    노외만 월 정기권을 받는다. 두 시간 단위는 30분 기본 + 10분 단위로 같다.
    """
    kind = "노상" if street else "노외"
    t = GR_FEES[kind][grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "std_grade": None,
        "base_min": GR_BASE_MIN, "base_fee": t["base"],
        "unit_min": GR_UNIT_MIN, "unit_fee": t["unit"],
        "steps": None, "steps_label": None,
        "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None,
        "daily_hours": daily_hours, "daily_fee": daily or t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": monthly or (None if street else t["month"]),
        "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "pay": "", "basis": f"「구리시 주차장 조례」 별표1 {kind} {grade}급지",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def build_guri():
    """구리시 공영주차장을 표준데이터 + 구리시 홈페이지 요금표·감면안내 + 조례 별표1로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 구리시 범위를 벗어난 행은 제외(껍데기 행).
      · 구리시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다(구리시는 수택동 6곳뿐).
    요금은 조례 별표1의 노상·노외 1~3급지 요금을 적용하고, 운영시간은 표준데이터 등록값을 쓰되
    일요일·공휴일 무료 개방을 시 홈페이지 안내로 보정했다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GR_PROVIDER]
    lots, excluded, merged, hour_fixed, space_diff, note_fixed = [], [], [], [], [], []
    ticket_diff, disc_note = [], []
    seen = {}
    card_no = street_no = 0

    def add_lot(name, jibun, road, ptype, spaces, dong, pay, win, oper, fee, r=None,
                src="표준데이터", notice=None, tel="", mgmt="", lat=None, lng=None,
                base_date="", free_days=None, free_note=None, detail_road=None):
        nonlocal card_no, street_no
        street = ptype == "노상"
        fee["pay"] = (r.get("결제방법") or "").strip() if r else ""
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": src,
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "구리시",
            "dong": dong,
            "dong_src": "지번주소" if r and gr_dong_of((r.get("소재지지번주소") or "")) else
                        ("도로명주소" if r and gr_dong_of((r.get("소재지도로명주소") or "")) else
                         ("시 홈페이지 주소" if src != "표준데이터" else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": detail_road,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "구리도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "구리시",
            "city_slug": "guri",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        jibun_key = re.sub(r"\s", "", jibun)
        name_key = re.sub(r"\s+", "", name)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif name_key and ("이름", name_key, ptype) in seen:
            dup_key = ("이름", name_key, ptype)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and name_key:
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", name_key, ptype)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (GR_BBOX[0] <= lat <= GR_BBOX[1]
                                     and GR_BBOX[2] <= lng <= GR_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = gr_dong_of(jibun) or gr_dong_of(road)
        street = ptype == "노상"
        note_raw = (r.get("특기사항") or "")
        win, oper, _closed = parse_schedule(r, note_raw)
        free_days = {"sat": False, "sun": False}
        free_note = None
        notice = None

        if street:
            # 노상은 평일 09:00~19:00 · 토요일 09:00~17:00에만 요금을 받고 일요일·공휴일은 무료다.
            want = gr_win(GR_STREET_HOURS)
            if any(win[k]["start"] != want[k]["start"] or win[k]["end"] != want[k]["end"]
                   for k in ("weekday", "sat")):
                hour_fixed.append(
                    f"{name}: 표준데이터 {win['weekday']['raw'][0]}~{win['weekday']['raw'][1]} · "
                    f"토 {win['sat']['raw'][0]}~{win['sat']['raw'][1]} → 시 안내 평일 09:00~19:00 · "
                    f"토요일 09:00~17:00")
            if not oper["sun"]:
                hour_fixed.append(f"{name}: 표준데이터 공휴일 미운영(00:00~00:00) → "
                                  f"시 안내 일요일·공휴일 무료 개방")
            win = want
            oper = {k: True for k in ("weekday", "sat", "sun")}
            free_days = {"sat": False, "sun": True}
            free_note = None
            notice = ("평일 09:00~19:00과 토요일 09:00~17:00에만 요금을 받고, 일요일·공휴일은 "
                      "무료로 개방합니다(구리시 홈페이지). 조례 제12조는 동절기 09:00~19:00·"
                      "하절기 08:00~20:00으로 적고 있어 계절에 따라 1시간 앞뒤로 달라질 수 있습니다")
        elif name in GR_NOOE_SUN_FREE:
            win["sun"] = (gr_win(("06:00~22:00",))["weekday"]
                          | {"raw": ["06:00", "22:00"]})
            oper["sun"] = True
            free_days = {"sat": False, "sun": True}
            free_note = None
            hour_fixed.append(f"{name}: 표준데이터 공휴일 미운영(00:00~00:00) → "
                              f"시 안내 일요일·공휴일 무료 개방")
            notice = ("월요일~토요일 06:00~22:00에 요금을 받고, 일요일·공휴일은 무료로 "
                      "개방합니다(구리시 홈페이지)")

        grade = to_int(r.get("급지구분"))
        if not grade:
            grade = 1
        daily = to_int(r.get("1일주차권요금"))
        daily_hours = to_int(r.get("1일주차권요금적용시간"))
        monthly = to_int(r.get("월정기권요금"))
        fee = gr_fee(grade, street=street, daily=daily, daily_hours=daily_hours,
                     monthly=monthly)
        fee["std_grade"] = to_int(r.get("급지구분"))
        fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                      "base_fee": to_int(r.get("주차기본요금")),
                      "unit_min": to_int(r.get("추가단위시간")),
                      "unit_fee": to_int(r.get("추가단위요금")),
                      "day": daily, "monthly": monthly}

        # 등록요금이 조례 별표1과 다르면 그 사실을 남긴다(값은 조례를 쓴다).
        tbl = GR_FEES["노상" if street else "노외"].get(grade, {})
        if tbl and (tbl["base"] != fee["std"]["base_fee"] or tbl["unit"] != fee["std"]["unit_fee"]):
            notice = ((notice + " · ") if notice else "") + \
                (f"표준데이터 등록요금은 30분 {fee['std']['base_fee']}원·10분당 "
                 f"{fee['std']['unit_fee']}원입니다")
        if monthly and not street and tbl.get("month") and monthly != tbl["month"]:
            ticket_diff.append(f"{name}: 월 정기권 {monthly:,}원(조례 별표1 {tbl['month']:,}원)")

        if name in GR_SPACE_DIFF and GR_SPACE_DIFF[name] != spaces:
            space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 시 홈페이지 {GR_SPACE_DIFF[name]}면")
            notice = ((notice + " · ") if notice else "") + \
                f"구리시 홈페이지는 {GR_SPACE_DIFF[name]}면으로 안내합니다(표준데이터 {spaces}면)"
        if name == "제6공영노외주차장":
            notice = ((notice + " · ") if notice else "") + \
                ("인창유수지 위 주차장이라 여름철 자연재난 대책기간(2025년 6월 1일~9월 30일)에는 "
                 "운영을 멈춘 적이 있습니다 — 장마철 이용 전 구리도시공사(031-550-3766)에 확인하세요")
        note_fixed.append(f"{name}: 표준데이터 특기사항이 15행 모두 같은 감면 안내문이라 "
                          f"카드 대신 시 페이지 감면표로 옮김")

        add_lot(name, jibun, road, ptype, spaces, dong, (r.get("요금정보") or "").strip(),
                win, oper, fee, r=r, notice=notice,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=(r.get("관리기관명") or "").strip() or "구리도시공사",
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note,
                detail_road=GR_ROADS.get(name))

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"gri-{i:03d}" if l["list_mode"] == "card" else f"gri-s{i:03d}"

    quality = check_quality_guri(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                 space_diff, note_fixed, ticket_diff)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(GR_NOOE_TXT).strftime("%Y-%m-%d %H:%M")
                           if GR_NOOE_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "구리시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-13",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 구리시가 등록한 15행(노외 9·노상 6)을 읽었다. 이름·주소·구획수·"
                             "급지·운영요일·운영시간·좌표·전화·관리번호·결제방법과 등록요금 출처로 썼다."),
                },
                {
                    "id": "ordinance", "name": "구리시 주차장 조례 [별표 1] 공영주차장 주차요금표",
                    "org": "구리시(자동차관리과 031-550-2705)", "url": GR_ORDINANCE_URL,
                    "file": GR_ORD_TXT.name,
                    "sha256": sha256(GR_ORD_TXT) if GR_ORD_TXT.exists() else None,
                    "license": "자치법규(공개)", "base_date": GR_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(GR_ORD_TXT),
                    "note": ("노상 1급지 700·300·9,000원 / 2급지 500·200·6,000원, 노외 1급지 "
                             "600·200·8,000·월 70,000원 / 2급지 500·200·6,000·50,000원 / 3급지 "
                             "400·100·5,000·40,000원, 거주자전용 월 30,000원(주간·야간 20,000원)을 "
                             "별표/서식 화면에서 확인했다. 급지 기준(1급지 상업·준주거지역·인창유수지, "
                             "2급지 일반주거지역, 3급지 그 밖의 지역·옥밭굴 지하)과 ‘노외 시간요금은 "
                             "1일 주차요금을 넘지 않는다’는 비고도 함께 읽었다."),
                },
                {
                    "id": "city_nooe", "name": "구리시 노외주차장 현황·요금표",
                    "org": "구리시 자동차관리과(031-550-2795)", "url": GR_CITY_NOOE_URL,
                    "file": GR_NOOE_TXT.name if GR_NOOE_TXT.exists() else None,
                    "sha256": sha256(GR_NOOE_TXT) if GR_NOOE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "2026-10-30 최종수정",
                    "rows_total": 9, "fetched_at": _sync_time(GR_NOOE_TXT),
                    "note": ("노외 9곳 1,486면의 위치·면수·급지·요금(기본 30분·10분당·1일 주차권·"
                             "월 정기권)과 운영시간(제1·2·3·8·9공영 24시간 연중무휴, 제4~7공영 "
                             "월~토 06:00~22:00·일요일·공휴일 무료) 확인용."),
                },
                {
                    "id": "city_street", "name": "구리시 노상주차장 현황·요금표",
                    "org": "구리시 자동차관리과(031-550-2795)", "url": GR_CITY_STREET_URL,
                    "file": GR_STREET_TXT.name if GR_STREET_TXT.exists() else None,
                    "sha256": sha256(GR_STREET_TXT) if GR_STREET_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "2026-10-30 최종수정",
                    "rows_total": 6, "fetched_at": _sync_time(GR_STREET_TXT),
                    "note": ("노상 6구간 144면의 위치(도로명)·면수·급지·요금(1급지 700·300·"
                             "9,000원, 2급지 500·200·6,000원)과 요금 부과 시간(평일 09:00~19:00, "
                             "토요일 09:00~17:00, 일요일·공휴일 무료) 확인용. 제9공영은 시 14면·"
                             "표준데이터 15면으로 1면 차이가 있다."),
                },
                {
                    "id": "discount", "name": "구리시 주차요금의 경감 및 면제대상",
                    "org": "구리시 자동차관리과(031-550-2795)", "url": GR_CITY_DISCOUNT_URL,
                    "file": GR_DISC_TXT.name if GR_DISC_TXT.exists() else None,
                    "sha256": sha256(GR_DISC_TXT) if GR_DISC_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "2026-10-30 최종수정",
                    "rows_total": None, "fetched_at": _sync_time(GR_DISC_TXT),
                    "note": ("조례 제6조의 면제(긴급·공무·유공납세·국가유공자 48시간·다자녀 48시간·"
                             "노상 5분)와 경감(장애인·유공자 3시간 면제 후 50%, 환경친화적 자동차 "
                             "2시간 면제 후 50%, 경차·저공해·다자녀·병역명문가 등 50%, 요일제 20%) "
                             "확인용."),
                },
                {
                    "id": "share", "name": "구리시 공유주차장 운영현황",
                    "org": "구리시 자동차관리과(031-550-2932)", "url": GR_CITY_SHARE_URL,
                    "file": GR_SHARE_TXT.name if GR_SHARE_TXT.exists() else None,
                    "sha256": sha256(GR_SHARE_TXT) if GR_SHARE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "2026-10-30 최종수정",
                    "rows_total": 19, "fetched_at": _sync_time(GR_SHARE_TXT),
                    "note": ("공공기관·학교·종교시설 부설주차장을 시간대를 정해 무료로 여는 "
                             "공유주차장 19개소 2,251면(시청 597면·수택3동 173면·체육관 232면·"
                             "구리유통종합시장 924면 등) 확인용 — 공영주차장 요금표 대상이 아니라 "
                             "카드로 만들지 않고 자주 묻는 질문에 안내했다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GR_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "guri_grade",
            "unit_min": GR_UNIT_MIN,
            "base_min": GR_BASE_MIN,
            "free_min": 0,
            "applies": GR_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "base": 600, "unit": 200, "day": 8_000, "month": 70_000,
                 "where": "상업지역·준주거지역·인창유수지", "lots": 0},
                {"grade": 2, "base": 500, "unit": 200, "day": 6_000, "month": 50_000,
                 "where": "일반주거지역", "lots": 0},
                {"grade": 3, "base": 400, "unit": 100, "day": 5_000, "month": 40_000,
                 "where": "그 밖의 지역·옥밭굴 지하", "lots": 0},
            ],
            "street": [
                {"grade": 1, "base": 700, "unit": 300, "day": 9_000, "month": None},
                {"grade": 2, "base": 500, "unit": 200, "day": 6_000, "month": None},
            ],
            "corp": {"out": 9, "out_spaces": 1_518, "st": 6, "st_spaces": 145,
                     "share": 19, "share_spaces": 2_251,
                     "city_out_spaces": 1_486, "city_st_spaces": 144},
            "basis": ("「구리시 주차장 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({GR_ORDINANCE_NOTE}) · 구리시 노외·노상주차장 요금표(2026-10-30) · "
                      "표준데이터 등록값(2026-10-13) 대조"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["구리시"] | {
        "city": "구리시",
        "weekend_free_pages": False,
        "discounts": GR_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "guri_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_guri(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                       note_fixed, ticket_diff):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_구리시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "특기사항_보정": note_fixed,
        "정기권_금액없음": ticket_diff,
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 오산시 (T-03 Phase 19)
OS_PROVIDER = "경기도 오산시"
# 오산시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
OS_DISTRICTS = [("오산시", "osan")]
OS_BBOX = (37.10, 37.22, 126.98, 127.11)   # 오산시 대략 경계(좌표 점검용)
# 오산시 법정동 24개 — 표준데이터 지번주소의 세 번째 낱말이 법정동이다.
#   (행정동 중앙·대원1·2·남촌·신장1·2·세마·초평동은 여러 법정동을 묶은 이름이라 주소에는 법정동이 적힌다.)
OS_DONGS = ("가수동", "가장동", "갈곶동", "고현동", "궐동", "금암동", "내삼미동", "누읍동",
            "두곡동", "벌음동", "부산동", "서동", "서랑동", "세교동", "수청동", "양산동",
            "오산동", "외삼미동", "원동", "은계동", "지곶동", "청학동", "청호동", "탑동")

OS_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2127813"
                    "&gubun=ELIS&conDatGubunCd=1")
OS_CITY_FEE_URL = "https://www.osan.go.kr/depart/contents.do?mId=0304020000"
OS_CITY_MAP_URL = "https://www.osan.go.kr/depart/contents.do?mId=0304010000"
OS_PORTAL_FEE_URL = "https://parking.osuc.or.kr/park/fee"
OS_PORTAL_LIST_URL = "https://parking.osuc.or.kr/park/introduction"
OS_ORD_TXT = RAW / "osan.law.go.kr_주차장조례_20261117.txt"
OS_CITY_FEE_TXT = RAW / "osan.go.kr_공영주차장_요금표_20261117.txt"
OS_CITY_MAP_TXT = RAW / "osan.go.kr_공영주차장_위치안내_20261117.txt"
OS_PORTAL_FEE_TXT = RAW / "parking.osuc.or.kr_공영주차장_요금안내_20261117.txt"
OS_PORTAL_LIST_TXT = RAW / "parking.osuc.or.kr_공영주차장_현황_20261117.txt"
OS_ORDINANCE_NOTE = ("시행 2026-05-06 · 경기도오산시조례 제2363호"
                     "(국가법령정보센터) · 별표1 개정 2025-05-22")
OS_UNIT_MIN = 10

# 오산시 공영주차장 요금 — 「오산시 주차장 조례」 [별표 1] 공영주차장 주차요금표
#   (별표 개정 2025-05-22, 조례 시행 2026-05-06. 별표/서식 화면에서 펼쳐 읽음)의 값이다.
#   오산도시공사 주차포털(parking.osuc.or.kr/park/fee)의 주차장별 무료시간·10분당 요금·
#   12시간권·월 정기권과 표준데이터 등록값이 같은 숫자다 — 세 자료로 대조했다.
#   · 노외 1급지(상업지역): 최초 1시간 무료 → 10분당 250원, 12시간 주차권 6,000원,
#     월 야간권(19:00~익일 09:00) 40,000원, 월 정기권 80,000원
#   · 노외 2급지(주거·공업지역, 그 밖의 지역): 최초 1시간 무료 → 10분당 200원,
#     12시간 주차권 4,000원, 월 야간권 30,000원, 월 정기권 60,000원
#   · 노상 1급지: 최초 1시간 무료 → 2시간까지 10분당 200원 → 2시간 초과 10분당 400원,
#     12시간 주차권 10,000원 / 노상 2급지: 100원 → 200원, 12시간 주차권 5,000원
#   · 별도 표: 오색시장 제1·2(1시간 30분 무료 → 3시간까지 200원 → 300원),
#     오산천(2시간 무료 → 300원), 독산성입구(동문)(2시간 무료 → 200원, 12시간권 4,000원)
#   · 환승주차장은 노외 1급지 요금에서 환승 목적 차량 60% 경감을 적용해 10분당 100원,
#     12시간까지 최대 2,400원, 월 정기권 40,000원(50% 감면)이다.
#   · 거주자전용은 월 30,000원(주간·야간 20,000원)이다(이 사이트 카드 대상 아님).
OS_GRADE_FEES = {
    "노외": {1: {"free": 60, "unit": 250, "ticket": 6_000, "night": 40_000, "month": 80_000},
             2: {"free": 60, "unit": 200, "ticket": 4_000, "night": 30_000, "month": 60_000}},
    "노상": {1: {"free": 60, "steps": ((120, 200), (None, 400)), "ticket": 10_000},
             2: {"free": 60, "steps": ((120, 100), (None, 200)), "ticket": 5_000}},
}

# 주차장별 실제 적용 요금 — 오산도시공사 주차포털(2026-11-17)의 주차장별 값과 조례 별표1.
#   무료시간(free)·10분당 요금(unit)·12시간 주차권(ticket)·월 정기권(month_*)을 그대로 적었고,
#   별표1의 별도 표를 쓰는 곳은 steps(누진)로 적었다. 포털이 ‘해당없음’으로 안내한 12시간권은
#   ticket 을 None 으로 두었다(별표1과 다르면 quality['12시간권_차이']에 남긴다).
OS_RATES = {
    "운암공영주차장": {"grade": 1, "free": 60, "unit": 250, "ticket": 6_000,
                  "month": 80_000, "month_day": 50_000, "month_night": 40_000, "month_label": "종일"},
    "궐동 공영주차장": {"grade": 2, "free": 60, "unit": 200, "ticket": 4_000,
                   "month": 60_000, "month_label": "종일"},
    "궐동 제3공영주차장": {"grade": 1, "free": 60, "unit": 250, "ticket": 6_000,
                    "month": 80_000, "month_label": "종일"},
    "어울림(복개천)공영주차장": {"grade": 1, "free": 60, "unit": 250, "ticket": 6_000,
                        "month": 80_000, "month_night": 40_000, "month_label": "종일"},
    "오산역제2환승주차장": {"grade": 1, "free": 60, "unit": 100, "ticket": 2_400,
                    "month": 40_000, "month_label": "종일", "transfer": True},
    "세마역 환승주차장": {"grade": 1, "free": 60, "unit": 100, "ticket": 2_400,
                  "month": 40_000, "month_label": "종일", "transfer": True},
    "오산대역 환승주차장": {"grade": 1, "free": 60, "unit": 100, "ticket": 2_400,
                   "month": 40_000, "month_label": "종일", "transfer": True},
    "오색시장 주차장": {"grade": None, "free": 90, "unit": 200,
                  "steps": ((180, 200), (None, 300)), "ticket": None},
    "오산 오색시장 제2공영주차장": {"grade": None, "free": 90, "unit": 200,
                           "steps": ((180, 200), (None, 300)), "ticket": None,
                           "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "문화의거리 제2공영주차장": {"grade": 1, "free": 60, "unit": 250, "ticket": 6_000,
                       "month": 40_000, "month_night": 40_000, "month_label": "야간"},
    "삼미공영주차장": {"grade": None, "free": 120, "unit": 300, "ticket": 4_000,
                 "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "은계동 공영주차장": {"grade": 2, "free": 120, "unit": 200, "ticket": 4_000,
                   "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "오산천공영주차장": {"grade": None, "free": 120, "unit": 300, "ticket": 4_000,
                  "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "수청동 공영주차장": {"grade": 2, "free": 60, "unit": 200, "ticket": 4_000,
                   "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "양산동 공영주차장(양산도서관 옆)": {"grade": 2, "free": 60, "unit": 200, "ticket": 4_000,
                              "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "청학동 공영주차장": {"grade": 2, "free": 60, "unit": 200, "ticket": 4_000,
                   "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "대원동 공영주차장": {"grade": 2, "free": 60, "unit": 200, "ticket": None},
    "독산성입구(동문) 공영주차장": {"grade": None, "free": 120, "unit": 200, "ticket": None,
                          "month": 60_000, "month_night": 30_000, "month_label": "종일"},
    "운암2 노상주차장": {"grade": 2, "free": 60, "unit": 100, "street": True,
                  "steps": ((120, 100), (None, 200)), "ticket": None},
}

# 오산도시공사 주차포털 ‘주차장 현황’(2026-11-17)의 면수 — 유료 공영주차장만 있다.
#   (부설주차장 6곳은 공영 요금표 대상이 아니라 이 사이트 카드로 만들지 않는다.)
OS_PORTAL_SPACES = {
    "운암공영주차장": 586, "궐동 공영주차장": 229, "어울림(복개천)공영주차장": 165,
    "오산역제2환승주차장": 133, "세마역 환승주차장": 70, "오산대역 환승주차장": 99,
    "오색시장 주차장": 100, "오산 오색시장 제2공영주차장": 177,
    "문화의거리 제2공영주차장": 40, "삼미공영주차장": 116, "은계동 공영주차장": 117,
    "오산천공영주차장": 142, "수청동 공영주차장": 55, "양산동 공영주차장(양산도서관 옆)": 62,
    "청학동 공영주차장": 45, "대원동 공영주차장": 32, "궐동 제3공영주차장": 113,
    "독산성입구(동문) 공영주차장": 81, "운암2 노상주차장": 16,
}
# 포털의 부설주차장 6곳 — 요금표 대상이 아니라 자주 묻는 질문에만 적는다.
OS_FACILITIES = (("오산시청", 546, "최초 1시간 무료, 이후 10분당 300원, 1일(24시간) 최대 9,000원"),
                 ("오색문화체육센터", 187, "최초 2시간 무료, 이후 10분당 300원"),
                 ("오산스포츠센터", 345, "최초 2시간 무료, 이후 10분당 300원"),
                 ("그린케어숲공원", 83, "최초 2시간 무료, 이후 10분당 300원(16인승 이상 2배)"),
                 ("세교복지타운", 149, "최초 2시간 무료, 이후 10분당 300원"),
                 ("은빛개울공원 제2", 30, "최초 2시간 무료, 이후 10분당 300원"))

# 오산시 ‘주차요금의 감면’(조례 제10조, 주차포털 감면표 2026-11-17) —
#   · 면제(1회 12시간까지): 긴급자동차, 공무수행차량, 외교사절 일행, 국가보훈대상자 자가운전,
#     모범·유공납세자(1년), 장애 정도가 심한 장애인 탑승 차량, 국경일·기념일 행사 참여자,
#     당일 투표 마친 선거인
#   · 60% 경감: 장애 정도가 심하지 않은 장애인 자가운전, 경형자동차, 환승주차장
#   · 50%: 10부제 함께 타기, 저공해차, 다자녀, 우수자원봉사자, 통장 직무수행,
#     환경친화적 자동차(전기차는 1일 1회 2시간 면제), 장기·인체조직 기증자, 병역명문가
#   · 정기권: 면제 대상 70%, 경감 대상 50% 경감. 감면이 겹치면 높은 하나만, 100원 미만 절사.
OS_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·경증장애인·환승 60%", "rate": 0.6, "exempt_min": 0,
     "note": "경형자동차(1,000cc 미만), 장애 정도가 심하지 않은 장애인 자가운전, 환승주차장 이용"},
    {"label": "저공해·다자녀·기증자 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "저공해차, 다자녀가정, 장기·인체조직 기증자, 병역명문가, 우수자원봉사자, "
             "통장 직무수행, 환경친화적 자동차, 10부제 함께 타기"},
    {"label": "전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "환경친화적 자동차 중 전기자동차 — 1일 1회 2시간까지 면제 뒤 50%"},
    {"label": "중증장애인·유공자 12시간 면제 후 60%", "rate": 0.6, "exempt_min": 720,
     "note": "장애 정도가 심한 장애인 탑승 차량, 국가보훈대상자 자가운전, 모범·유공납세자(1년) "
             "— 1회 12시간까지 면제(이후 60% 경감)"},
    {"label": "긴급·공무 차량 면제(12시간 한도)", "rate": 1.0, "exempt_min": 720,
     "note": "긴급자동차, 국가·지방자치단체 공무수행 자동차, 외교사절 수행자 차량 "
             "— 1회 12시간까지 면제"},
]


def os_dong_of(text: str):
    """주소에서 오산시 법정동을 뽑는다 — ‘경기도 오산시 {법정동} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "오산시" and parts[2] in OS_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(OS_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def os_win(spans):
    """시 홈페이지·주차포털 운영시간 → 사이트 공통 hours 객체(요일 셋 모두 같은 값).

    spans 는 (평일, 토요일, 일·공휴일) 문자열. ‘24H’는 24시간, ‘09:00~23:00’은 그 구간이다.
    """
    win = {}
    for key, txt in zip(("weekday", "sat", "sun"), spans):
        if txt == "24H":
            win[key] = {"open": True, "start": 0, "end": 1440, "24h": True,
                        "listed": True, "raw": ["00:00", "24:00"]}
        else:
            m = re.match(r"(\d{1,2}):(\d{2})~(\d{1,2}):(\d{2})", txt)
            s = int(m.group(1)) * 60 + int(m.group(2))
            e = int(m.group(3)) * 60 + int(m.group(4))
            win[key] = {"open": True, "start": s, "end": e, "24h": False,
                        "listed": True, "raw": [f"{s // 60:02d}:{s % 60:02d}",
                                                f"{e // 60:02d}:{e % 60:02d}"]}
    return win


def os_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def os_fee(rate: dict, std=None, monthly=None):
    """오산시 공영주차장 요금 → 사이트 공통 fee 객체.

    별표1은 기본요금 없이 ‘최초 1시간(또는 2시간·1시간 30분) 무료’ 뒤 10분 단위 요금이 붙는다.
    free_min 과 base_min 을 같은 값으로 두고 base_fee 를 0으로 두면 계산기가 ‘최초 N분 무료 ·
    이후 10분마다 X원’으로 계산한다(평택시 90분 무료와 같은 방식). 12시간 주차권은 선불로
    사는 1일권이라 시간 요금의 상한으로 둔다.
    """
    free = rate["free"]
    steps = ([{"until": u, "unit_min": OS_UNIT_MIN, "unit_fee": f} for u, f in rate["steps"]]
             if rate.get("steps") else None)
    ticket = rate.get("ticket")
    fee = {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": rate.get("grade"), "std_grade": None,
        "base_min": free, "base_fee": 0,
        "unit_min": OS_UNIT_MIN, "unit_fee": rate["unit"],
        "steps": steps,
        "steps_label": ("3시간 초과 10분당 300원" if rate.get("steps") == ((180, 200), (None, 300))
                        else "2시간 초과 10분당 200원" if rate.get("steps") == ((120, 100), (None, 200))
                        else None),
        "free_min": free, "deduct_min": None,
        "cap_fee": None,
        "cap_src": ("12시간 한도" if rate.get("transfer") else
                    "12시간권(선불)" if ticket else None),
        "daily_hours": 12 if ticket else None,
        "daily_fee": ticket,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": monthly if monthly is not None else rate.get("month"),
        "monthly_day": rate.get("month_day"), "monthly_night": rate.get("month_night"),
        "monthly_all": rate.get("month"),
        "monthly_label": rate.get("month_label"),
        "pay": "", "basis": None,
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": std,
    }
    if rate.get("transfer"):
        fee["basis"] = (f"「오산시 주차장 조례」 별표1 노외 1급지 · 환승주차장 60% 경감"
                        f"({rate['unit']}원/10분)")
    elif rate.get("street"):
        fee["basis"] = f"「오산시 주차장 조례」 별표1 노상 {rate['grade']}급지"
    elif rate.get("grade"):
        fee["basis"] = f"「오산시 주차장 조례」 별표1 노외 {rate['grade']}급지"
    else:
        fee["basis"] = "「오산시 주차장 조례」 별표1 별도 요금표"
    return fee


def build_osan():
    """오산시 공영주차장을 표준데이터 + 오산시 누리집 요금표 + 오산도시공사 주차포털로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 오산시 범위를 벗어난 행은 제외(껍데기 행).
      · 오산시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 표준데이터에 등록된 44행은 모두 주차장유형이 ‘노외’지만, 그중 ‘운암2 노상주차장’은
        주차포털이 노상(09:00~23:00)으로 안내하고 요금도 별표1 노상 2급지라 노상 카드로 만든다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다(오산동·원동·궐동·수청동·청학동·세교동·내삼미동).
    요금은 오산도시공사 주차포털의 주차장별 값(조례 별표1과 같은 숫자)을 쓰고, 운영시간은
    유료 노외 24시간·운암2 노상 09:00~23:00으로 적었다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == OS_PROVIDER]
    lots, excluded, merged, hour_fixed, space_diff, note_fixed = [], [], [], [], [], []
    ticket_diff, city_fee_diff, unknown_rate = [], [], []
    seen = {}
    card_no = street_no = 0

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                src="표준데이터", notice=None, tel="", mgmt="", lat=None, lng=None,
                base_date="", free_days=None, free_note=None, list_mode="card"):
        nonlocal card_no, street_no
        fee["pay"] = (r.get("결제방법") or "").strip() if r else ""
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": src,
            "list_mode": list_mode,
            "name": name,
            "gu": "오산시",
            "dong": dong,
            "dong_src": "지번주소" if r and os_dong_of((r.get("소재지지번주소") or "")) else
                        ("도로명주소" if r and os_dong_of((r.get("소재지도로명주소") or "")) else
                         ("시 홈페이지 주소" if src != "표준데이터" else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "오산도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "오산시",
            "city_slug": "osan",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        jibun_key = re.sub(r"\s", "", jibun)
        name_key = re.sub(r"\s+", "", name)
        dup_key = None
        if jibun_key and ("지번", jibun_key, ptype, spaces) in seen:
            dup_key = ("지번", jibun_key, ptype, spaces)
        elif name_key and ("이름", name_key, ptype) in seen:
            dup_key = ("이름", name_key, ptype)
        if dup_key:
            merged.append(f"{seen[dup_key]}({mgmt}) ↔ {name}({mgmt}) — 같은 주차장으로 묶음")
            continue
        if jibun_key and name_key:
            seen[("지번", jibun_key, ptype, spaces)] = name
            seen[("이름", name_key, ptype)] = name

        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (OS_BBOX[0] <= lat <= OS_BBOX[1]
                                     and OS_BBOX[2] <= lng <= OS_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = os_dong_of(jibun) or os_dong_of(road)
        rate = OS_RATES.get(name)
        note_raw = (r.get("특기사항") or "")
        win, oper, _closed = parse_schedule(r, note_raw)
        notice = None
        free_days = {"sat": False, "sun": False}
        free_note = None
        daily_h = to_int(r.get("1일주차권요금적용시간"))
        daily = to_int(r.get("1일주차권요금"))
        monthly_std = to_int(r.get("월정기권요금"))

        # 운영시간 — 유료 노외는 24시간 연중무휴, 운암2 노상은 09:00~23:00(주차포털·별표1 비고3).
        if rate is None:
            # 무료 임시공영주차장 — 표준데이터 등록값(00:00~23:59, 평일+토+공휴일)을 그대로 쓴다.
            win = os_win(("00:00~23:59", "00:00~23:59", "00:00~23:59"))
            oper = {k: True for k in ("weekday", "sat", "sun")}
        elif rate.get("street"):
            want = os_win(("09:00~23:00",) * 3)
            if (win["weekday"]["start"], win["weekday"]["end"]) != (want["weekday"]["start"],
                                                                  want["weekday"]["end"]):
                hour_fixed.append(f"{name}: 표준데이터 {win['weekday']['raw'][0]}~"
                                  f"{win['weekday']['raw'][1]} → 노상 운영시간 09:00~23:00")
            win, oper = want, {k: True for k in ("weekday", "sat", "sun")}
        else:
            if not all(win[k]["24h"] for k in ("weekday", "sat", "sun")) or \
                    not all(oper[k] for k in ("weekday", "sat", "sun")):
                hour_fixed.append(f"{name}: 표준데이터 {win['weekday']['raw'][0]}~"
                                  f"{win['weekday']['raw'][1]} → 유료 노외 24시간 연중무휴")
            win = os_win(("24H",) * 3)
            oper = {k: True for k in ("weekday", "sat", "sun")}

        if rate is None:
            fee = os_free_fee()
            if (r.get("요금정보") or "").strip() == "유료":
                notice = "표준데이터는 유료로 등록했지만 이 사이트는 요금을 찾지 못했습니다 — 현장 확인"
                unknown_rate.append(name)
        else:
            fee = os_fee(rate, monthly=rate.get("month"))
            fee["std_grade"] = to_int(r.get("급지구분"))
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                          "base_fee": to_int(r.get("주차기본요금")),
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily, "day_hours": daily_h, "monthly": monthly_std}
            # 표준데이터 등록값과 실제 적용값이 다른 부분을 남긴다(값은 포털·별표1을 쓴다).
            if daily is not None and rate.get("ticket") is not None and daily != rate["ticket"]:
                ticket_diff.append(f"{name}: 표준데이터 1일 주차권 {daily:,}원"
                                   f"(적용 12시간권 {rate['ticket']:,}원)")
            elif daily is None and rate.get("ticket"):
                ticket_diff.append(f"{name}: 표준데이터에 1일 주차권 없음"
                                   f"(적용 12시간권 {rate['ticket']:,}원)")
            elif daily is None and rate.get("ticket") is None and name in (
                    "오색시장 주차장", "운암2 노상주차장"):
                ticket_diff.append(f"{name}: 주차포털은 12시간 주차권 해당없음"
                                   f"(조례 별표1에는 {'5,000' if rate.get('street') else '4,000'}원권)")

        # 주차포털과 표준데이터의 면수가 다른 곳 — 표준데이터 등록면수를 쓰고 카드에 적는다.
        portal_spaces = OS_PORTAL_SPACES.get(name)
        if portal_spaces and portal_spaces != spaces:
            space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 주차포털 {portal_spaces}면")
            notice = ((notice + " · ") if notice else "") + \
                (f"오산도시공사 주차포털은 {portal_spaces}면으로 안내합니다"
                 f"(표준데이터 {spaces}면)")

        # 주차장별 안내 — 요금 구조와 현장 사정을 카드에 적는다.
        extra = []
        if rate and rate.get("transfer"):
            extra.append("환승주차장은 도시철도 환승 목적 차량에 60% 경감을 적용해 10분당 100원이고, "
                         "12시간까지 최대 2,400원·월 정기권 40,000원(50% 감면)입니다. "
                         "환승하지 않은 차량은 노외 1급지 요금(10분당 250원)이 적용됩니다")
        if rate and rate.get("steps") and not rate.get("street"):
            extra.append("오색시장 제1·2 공영주차장은 조례 별표1의 별도 요금표를 씁니다 — 최초 1시간 30분 "
                         "무료, 3시간까지 10분당 200원, 3시간을 넘기면 300원입니다")
            if name == "오색시장 주차장":
                extra.append("조례 별표1은 두 곳 모두 월 야간권 30,000원·월 정기권 60,000원을 두고 있지만, "
                             "주차포털은 이 곳(제1)의 정기권을 ‘해당없음’으로, 제2만 종일 60,000원·야간 "
                             "30,000원으로 안내합니다")
        if name in ("은계동 공영주차장", "삼미공영주차장"):
            extra.append("조례 별표1 비고는 이 두 주차장 이용객에게 처음 180분까지 무료로 적용할 수 있게 "
                         "하고, 주차포털은 최초 2시간(120분) 무료로 안내합니다")
        if name == "삼미공영주차장":
            extra.append("캐러반·캠핑카 전용 61면이 있고, 캠핑카·카라반은 노외 1급지 월 정기권 80,000원을 "
                         "적용합니다(감면 제외). 시 홈페이지는 내삼미동 454-4, 표준데이터·주차포털은 "
                         "내삼미동 702-3으로 적습니다")
        if name == "오산역 임시공영주차장":
            extra.append("오산역 제1 환승 공영주차장(오산동 625-1, 216면)이 공사 중이어서 그 자리에 "
                         "임시로 운영하는 무료 주차장입니다(오산도시공사 주차포털)")
        if name == "운암2 노상주차장":
            extra.append("도로변 노상주차장(16면)으로 09:00~23:00에만 운영합니다. 조례 별표1 노상 2급지 "
                         "요금(최초 1시간 무료·2시간까지 10분당 100원·2시간 초과 200원)을 적용하고, "
                         "주차포털도 같은 값입니다")
            extra.append("조례 별표1 노상 2급지에는 12시간 주차권 5,000원이 있으나 주차포털은 해당없음으로 "
                         "안내해 1일권 없이 계산합니다")
        if name == "독산성입구(동문) 공영주차장":
            extra.append("조례 별표1에는 12시간 주차권 4,000원이 있으나 주차포털은 해당없음으로 안내해 "
                         "1일권 없이 계산합니다")
        if name == "대원동 공영주차장":
            extra.append("12시간 주차권과 월 정기권은 운영하지 않습니다(주차포털)")
        if name == "문화의거리 제2공영주차장":
            extra.append("월 정기권은 야간권(19:00~익일 09:00) 40,000원만 운영합니다(주차포털)")
        if name == "궐동 공영주차장":
            extra.append("표준데이터 급지구분은 1급지로 등록되어 있지만, 실제 적용 요금은 2급지"
                         "(10분당 200원·월 60,000원)입니다(주차포털·별표1 비고4: 1급지=상업지역)")
        if name in ("청학동 공영주차장", "수청동 공영주차장", "양산동 공영주차장(양산도서관 옆)",
                    "대원동 공영주차장"):
            extra.append("표준데이터 급지구분은 1급지로 등록되어 있지만, 실제 적용 요금은 2급지"
                         "(10분당 200원)입니다(주차포털)")
        if extra:
            notice = " · ".join(([notice] if notice else []) + extra)

        if rate is None:
            note_fixed.append(f"{name}: 요금 구분 ‘무료’ — 요일과 관계없이 무료")
        add_lot(name, jibun, road, "노상" if (rate and rate.get("street")) else
                ("노외" if ptype != "노상" else ptype), spaces, dong, win, oper, fee, r=r,
                notice=notice, tel=(r.get("전화번호") or "").strip(),
                mgmt=(r.get("관리기관명") or "").strip() or "오산도시공사",
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    # 오산시 누리집 요금표(급지별)는 30분 기본요금으로 적혀 있어 조례 별표1과 다르다 — 한 번만 남긴다.
    city_fee_diff.append("노외: 시 누리집 ‘처음 30분 1급지 500원·2급지 300원’ ↔ 조례 별표1·주차포털 "
                         "‘최초 1시간 무료 + 10분당 1급지 250원·2급지 200원’")
    city_fee_diff.append("노상: 시 누리집 ‘2시간까지 10분당 200원(1급지)·100원(2급지)’ ↔ 조례 별표1 "
                         "‘최초 1시간 무료 + 2시간까지 200·100원, 2시간 초과 400·200원’")

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"osn-{i:03d}" if l["list_mode"] == "card" else f"osn-s{i:03d}"

    quality = check_quality_osan(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                 space_diff, note_fixed, ticket_diff, city_fee_diff, unknown_rate)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(OS_PORTAL_LIST_TXT).strftime("%Y-%m-%d %H:%M")
                           if OS_PORTAL_LIST_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "오산시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-13",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 오산시가 등록한 44행(모두 노외)을 읽었다. 이름·주소·구획수·"
                             "급지·운영요일·운영시간·좌표·전화·관리번호·결제방법과 등록요금 출처로 썼다."),
                },
                {
                    "id": "ordinance", "name": "오산시 주차장 조례 [별표 1] 공영주차장 주차요금표",
                    "org": "오산시(교통정책과 031-8036-7729)", "url": OS_ORDINANCE_URL,
                    "file": OS_ORD_TXT.name,
                    "sha256": sha256(OS_ORD_TXT) if OS_ORD_TXT.exists() else None,
                    "license": "자치법규(공개)", "base_date": OS_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(OS_ORD_TXT),
                    "note": ("노외 1급지 최초 1시간 무료 + 10분당 250원·12시간 주차권 6,000원·월 야간권 "
                             "40,000원·월 정기권 80,000원, 2급지 200원·4,000·30,000·60,000원, 노상 1급지 "
                             "2시간까지 200원·초과 400원·12시간권 10,000원, 2급지 100·200·5,000원, "
                             "오색시장 제1·2(1시간 30분 무료·200→300원), 오산천(2시간 무료·300원), "
                             "독산성입구(동문)(2시간 무료·200원)을 별표/서식 화면에서 확인했다. "
                             "급지(1급지 상업지역, 2급지 주거·공업지역·그 밖), 노상 운영시간 "
                             "09:00~23:00, 환승주차장은 노외 1급지 요금, 은계동·삼미 180분 무료 규정도 "
                             "함께 읽었다."),
                },
                {
                    "id": "city_fee", "name": "오산시 공영주차장 주차요금표",
                    "org": "오산시 누리집", "url": OS_CITY_FEE_URL,
                    "file": OS_CITY_FEE_TXT.name if OS_CITY_FEE_TXT.exists() else None,
                    "sha256": sha256(OS_CITY_FEE_TXT) if OS_CITY_FEE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": None, "fetched_at": _sync_time(OS_CITY_FEE_TXT),
                    "note": ("급지별 요금표(노상 2시간까지 200·100원, 2시간 초과 400·200원, 노외 "
                             "30분 500·300원, 10분당 250·200원, 1일 6,000·4,000원, 월 80,000·60,000원)를 "
                             "읽었다. 이 표에는 ‘최초 1시간 무료’가 빠져 있어 조례 별표1·주차포털과 "
                             "다르고, 값은 조례 별표1을 썼다(품질 리포트 ‘시_요금표_차이’)."),
                },
                {
                    "id": "portal_fee", "name": "오산도시공사 주차포털 공영주차장 요금안내",
                    "org": "오산도시공사(031-371-1830)", "url": OS_PORTAL_FEE_URL,
                    "file": OS_PORTAL_FEE_TXT.name if OS_PORTAL_FEE_TXT.exists() else None,
                    "sha256": sha256(OS_PORTAL_FEE_TXT) if OS_PORTAL_FEE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 26, "fetched_at": _sync_time(OS_PORTAL_FEE_TXT),
                    "note": ("주차장별 무료시간(1시간·2시간·1시간 30분)·10분당 요금·12시간권(선불)·"
                             "월 정기권(종일·주간·야간)과 감면표(100%·60%·50%)·12시간권 선불 규정"
                             "(입차 4시간 내 구매, 12시간 경과 후 시간제)·정기권 환불 규정을 확인했다."),
                },
                {
                    "id": "portal_list", "name": "오산도시공사 주차포털 주차장 현황·운영시간",
                    "org": "오산도시공사(031-371-1830)", "url": OS_PORTAL_LIST_URL,
                    "file": OS_PORTAL_LIST_TXT.name if OS_PORTAL_LIST_TXT.exists() else None,
                    "sha256": sha256(OS_PORTAL_LIST_TXT) if OS_PORTAL_LIST_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 26, "fetched_at": _sync_time(OS_PORTAL_LIST_TXT),
                    "note": ("유료 공영주차장 19곳(노외 18·노상 1)과 부설주차장 6곳의 면수·운영시간"
                             "(24시간 유료운영, 노상 09:00~23:00)·명절연휴 무료개방, 오산역 제1 환승 "
                             "공영주차장의 공사중 표기를 확인했다. 면수는 표준데이터와 "
                             f"{len(space_diff)}곳이 다르다."),
                },
                {
                    "id": "city_map", "name": "오산시 누리집 공영주차장 위치안내",
                    "org": "오산시 누리집", "url": OS_CITY_MAP_URL,
                    "file": OS_CITY_MAP_TXT.name if OS_CITY_MAP_TXT.exists() else None,
                    "sha256": sha256(OS_CITY_MAP_TXT) if OS_CITY_MAP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 18, "fetched_at": _sync_time(OS_CITY_MAP_TXT),
                    "note": ("시가 안내하는 유료 공영주차장 18곳의 명칭·주소를 확인했다(무료 임시공영 "
                             "25곳은 들어 있지 않다). 삼미 공영주차장은 시 안내가 내삼미동 454-4, "
                             "표준데이터·주차포털은 내삼미동 702-3으로 적는다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in OS_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "osan_free_hour",
            "unit_min": OS_UNIT_MIN,
            "free_min": 60,
            "applies": OS_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "상업지역", "free": 60, "unit": 250, "ticket": 6_000,
                 "night": 40_000, "month": 80_000, "lots": 0},
                {"grade": 2, "where": "주거지역·공업지역·그 밖의 지역", "free": 60, "unit": 200,
                 "ticket": 4_000, "night": 30_000, "month": 60_000, "lots": 0},
            ],
            "street": [
                {"grade": 1, "free": 60, "unit2": 200, "unit_over": 400, "ticket": 10_000},
                {"grade": 2, "free": 60, "unit2": 100, "unit_over": 200, "ticket": 5_000},
            ],
            "special": [
                {"name": "오색시장 제1", "free": 90, "tiers": "3시간까지 10분당 200원 → 3시간 초과 300원",
                 "ticket": None, "month": None, "night": None},
                {"name": "오색시장 제2", "free": 90, "tiers": "3시간까지 10분당 200원 → 3시간 초과 300원",
                 "ticket": None, "month": 60_000, "night": 30_000},
                {"name": "오산천", "free": 120, "tiers": "2시간 초과 10분당 300원",
                 "ticket": 4_000, "month": 60_000, "night": 30_000},
                {"name": "독산성입구(동문)", "free": 120, "tiers": "2시간 초과 10분당 200원",
                 "ticket": None, "month": 60_000, "night": 30_000},
                {"name": "환승 3곳(오산역 제2·세마역·오산대역)", "free": 60,
                 "tiers": "10분당 100원(환승 60% 경감, 12시간까지 최대 2,400원)",
                 "ticket": None, "month": 40_000, "night": None},
            ],
            "lots": [
                {"name": l["name"], "dong": l["dong"], "grade": l["fee"].get("grade"),
                 "free": l["fee"].get("free_min"), "unit": l["fee"].get("unit_fee"),
                 "ticket": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly"),
                 "month_label": l["fee"].get("monthly_label")}
                for l in lots if l["fee"]["type"] == "유료"],
            "corp": {"out": len([l for l in lots if l["fee"]["type"] == "유료" and l["ptype"] == "노외"]),
                     "st": len([l for l in lots if l["ptype"] == "노상"]),
                     "st_spaces": sum(l["spaces"] or 0 for l in lots if l["ptype"] == "노상"),
                     "free": len([l for l in lots if l["fee"]["type"] == "무료"]),
                     "free_spaces": sum(l["spaces"] or 0 for l in lots if l["fee"]["type"] == "무료"),
                     "portal_sum": 3_702,
                     "fac": len(OS_FACILITIES),
                     "fac_spaces": sum(f[1] for f in OS_FACILITIES)},
            "basis": ("「오산시 주차장 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({OS_ORDINANCE_NOTE}) · 오산도시공사 주차포털 요금안내(2026-11-17) · "
                      "표준데이터 등록값(2026-10-13) 대조"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["오산시"] | {
        "city": "오산시",
        "weekend_free_pages": False,
        "discounts": OS_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "osan_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_osan(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                       note_fixed, ticket_diff, city_fee_diff, unknown_rate):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_오산시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "특기사항_보정": note_fixed,
        "12시간권_차이": ticket_diff,
        "정기권_차이": [f"{l['name']}: 주차포털은 정기권 해당없음"
                     f"(조례 별표1 월 야간권 30,000·월 정기권 60,000원)"
                     for l in lots if l["name"] == "오색시장 주차장" and not l["fee"].get("monthly")],
        "시_요금표_차이": city_fee_diff,
        "요금_미상_유료행": unknown_rate,
        "무료시간_출처": "「오산시 주차장 조례」 별표1(개정 2025-05-22) · 오산도시공사 주차포털",
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "평균_기본요금": 0,
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 이천시 (T-03 Phase 20)
IC_PROVIDER = "경기도 이천시"
# 이천시는 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
IC_DISTRICTS = [("이천시", "icheon")]
IC_BBOX = (37.09, 37.36, 127.30, 127.64)   # 이천시 대략 경계(좌표 점검용)
# 이천시 법정 동·읍·면 — 표준데이터 지번주소의 세 번째 낱말이 지역 이름이다.
#   (행정동 증포동은 중리동·증일동·안흥동 등 여러 법정동을 묶은 이름이라 주소에는 법정동이 적힌다.)
IC_DONGS = ("관고동", "대월면", "마장면", "모가면", "부발읍", "사음동", "송정동", "신둔면",
            "안흥동", "증일동", "중리동", "창전동", "장호원읍", "백사면", "호명면")

IC_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2040013"
                    "&gubun=ELIS&conDatGubunCd=1")
IC_PORTAL_FEE_URL = "https://parking.2000fmc.or.kr/parkfeeinformation"
IC_PORTAL_DISC_URL = "https://parking.2000fmc.or.kr/parkfeereduction"
IC_FAQ_URL = "https://2000fmc.or.kr/ic-kr/bbs/i-79/list.do"
IC_NOTICE_URL = "https://parking.2000fmc.or.kr/noticeview?atclId=6029"
IC_ORD_TXT = RAW / "icheon.law.go.kr_주차장조례_20261117.txt"
IC_ORD_HWP = RAW / "icheon.law.go.kr_주차장조례_별표1_20261117.hwp"
IC_PORTAL_FEE_TXT = RAW / "parking.2000fmc.or.kr_공영주차장_요금안내_20261117.txt"
IC_PORTAL_DISC_TXT = RAW / "parking.2000fmc.or.kr_공영주차장_감면안내_20261117.txt"
IC_FAQ_TXT = RAW / "2000fmc.or.kr_공영주차장_자주묻는질문_20261117.txt"
IC_NOTICE_TXT = RAW / "parking.2000fmc.or.kr_남천상가_보수공사안내_20261117.txt"
IC_ORDINANCE_NOTE = ("공포 2025-05-16 · 경기도이천시조례 제2224호(일부개정) · "
                     "별표1 〈개정 2025.5.16.〉")
IC_BASE_MIN = 30
IC_UNIT_MIN = 10

# 이천시 공영주차장 요금 — 「이천시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금표
#   (공포 2025-05-16, 경기도이천시조례 제2224호. 별표/서식 HWP에서 표를 읽음)의 값이다.
#   이천스마트주차포털(parking.2000fmc.or.kr/parkfeeinformation)의 주차장별 무료시간·요금과
#   표준데이터 등록값이 같은 숫자다 — 세 자료로 대조했다.
#   · 노상 1급지: 최초 30분 600원 → 10분당 250원, 1일 최대 7,000원, 월 정기권 없음
#   · 노외 1급지: 최초 30분 600원 → 10분당 250원, 1일 최대 7,000원,
#     월 정기권 주간 60,000·야간 36,000·주야간 70,000원
#   · 노외 2급지: 최초 30분 500원 → 10분당 200원, 1일 최대 5,000원,
#     월 정기권 주간 50,000·야간 30,000·주야간 60,000원
#   · 노외 3급지: 최초 30분 400원 → 10분당 150원, 1일 최대 4,000원,
#     월 정기권 주간 30,000·야간 20,000·주야간 40,000원
#   · 별표 비고: 주차장에 입차 후 10분까지는 무료 회차할 수 있다.
#   · 별표 6라: 1급지 상업지역, 2급지 주거·공업·녹지지역, 3급지 도시지역 외 지역.
#     표준데이터가 4급지로 등록한 곳은 무료 주차장뿐이라 요금표 급지(1~3급지)와 겹치지 않는다.
IC_FEES = {
    "노상": {1: {"base": 600, "unit": 250, "day": 7_000, "month": None},
             2: {"base": 500, "unit": 200, "day": 5_500, "month": (50_000, 30_000, None)},
             3: {"base": 400, "unit": 150, "day": 4_500, "month": (40_000, 24_000, None)}},
    "노외": {1: {"base": 600, "unit": 250, "day": 7_000, "month": (60_000, 36_000, 70_000)},
             2: {"base": 500, "unit": 200, "day": 5_000, "month": (50_000, 30_000, 60_000)},
             3: {"base": 400, "unit": 150, "day": 4_000, "month": (30_000, 20_000, 40_000)}},
}

# 주차장별 실제 적용 무료시간 — 이천스마트주차포털 이용안내(2026-11-17)의 값.
#   표준데이터에는 무료시간이 등록되어 있지 않아(free_min 없음) 포털 값을 fee.free_min 으로 넣는다.
#   나머지 유료 주차장은 최초 30분이 기본요금이고, 입차 후 10분은 무료 회차(별표 비고)다.
IC_FREE_MIN = {
    "창전동 임시 공영주차장": 30, "남천상가주차장": 30, "공설운동장공영주차장": 30,
    "마장택지지구 공영주차장1": 60, "마장택지지구 공영주차장2": 60,
    "서희청소년문화센터공영주차장": 120, "택시쉼터공영주차장": 60,
}

# 월 정기권 운영 주차장 — 포털 자주묻는 질문(2026-06-16): 북샛말·택시쉼터·서희청소년문화센터·
#   공설운동장·사동리 5곳만 운영하고 그 밖의 주차장은 미운영이다. 조례 별표1에는 급지별
#   정기권이 있으므로, 정기권 미운영 주차장은 정기권을 비워 두고 차이를 품질 리포트에 남긴다.
IC_MONTHLY_LOTS = ("북샛말공영주차장", "택시쉼터공영주차장", "서희청소년문화센터공영주차장",
                   "공설운동장공영주차장", "사동리 제1공영주차장")

# 포털 ‘공단 운영 시설’의 면수(FAQ, 2026-06-16 게시) — 표준데이터 등록면수와 다른 곳을 적는다.
#   공설운동장 464면(표준데이터 466면), 북샛말 176면(표준데이터 177면) — 등록면수를 쓰고 카드에 적는다.
IC_SPACE_DIFF = {"공설운동장공영주차장": 464, "북샛말공영주차장": 176,
                 "중리천로공영주차장": 33}

# 이천시시설관리공단이 운영하는 유료 노외 10곳·노상 유인 31구간 이외의 무료 주차장은 시가
#   직접 운영한다(관리기관명 ‘경기도 이천시청’, 전화 031-644-2333).
IC_CORP = "이천시시설관리공단"

# 이천시 ‘주차요금의 감면’(조례 별표1 세부사항 바목, 주차포털 감면안내 2026-11-17) —
#   이중감면은 하지 않고, 감면은 납부(출차) 시 대상임을 증명한 경우에 한다.
IC_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·다자녀 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "경형자동차(1,000cc 미만), 저공해자동차 표지 부착 차량, 2자녀 이상 다자녀, "
             "임산부, 65세 이상 경로우대자 본인 운전, 자원봉사활동 차량, 병역명문가, "
             "기초수급자·차상위계층 자가운전, 장애정도가 심하지 않은 장애인"},
    {"label": "저공해1종·우수자원봉사자 1시간 면제 후 50%", "rate": 0.5, "exempt_min": 60,
     "note": "제1종 저공해자동차(전기·수소·태양광), 경기도·이천시 우수자원봉사자 — "
             "최초 1시간 면제 뒤 50%"},
    {"label": "중증장애인 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "장애정도가 심한 장애인 본인 운전·동승(대리운전 포함) 차량 — "
             "최초 2시간 면제 뒤 50%"},
    {"label": "국가유공자 등 4시간 면제 후 50%", "rate": 0.5, "exempt_min": 240,
     "note": "국가유공자·유족, 참전유공자, 고엽제후유의증환자, 5·18민주화운동부상자, "
             "의사상자(유족증 포함) — 최초 4시간 면제 뒤 50%"},
    {"label": "승용차 요일제 30%", "rate": 0.3, "exempt_min": 0,
     "note": "승용차 요일제 및 함께 타기 표지부착 차량(1일 주차권·월 정기권은 감면 없음)"},
    {"label": "긴급·공무·명예시민 등 100% 면제", "rate": 1.0, "exempt_min": 0,
     "note": "긴급자동차(노상에 한함), 교통약자이동지원센터·장애인심부름센터·콜승합차 차량, "
             "군부대 관용차량, 명예시민증·이천인증 소지자 본인 운전·동승 차량, "
             "모범·유공·성실납세자 인증 차량(유효기간), 국가·지방자치단체 공무수행 자동차, "
             "65세 이상 국가보훈대상자 자가운전 차량"},
]


def ic_dong_of(text: str):
    """주소에서 이천시 법정동·읍·면을 뽑는다 — ‘경기도 이천시 {동·읍·면} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "이천시" and parts[2] in IC_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(IC_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def ic_fee(kind: str, grade: int, free_min=None):
    """이천시 공영주차장 요금 → 사이트 공통 fee 객체.

    별표1은 최초 30분 기본요금 + 30분 초과 시 10분마다 요금이다. 주차포털이
    최초 무료시간(30분·1시간·2시간)을 안내하는 곳은 free_min 으로 넣어 계산기가
    그 시간까지 0원으로 계산한다(입차 후 10분 무료 회차는 별표 비고).
    """
    t = IC_FEES[kind][grade]
    month = t["month"]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "std_grade": None,
        "base_min": IC_BASE_MIN, "base_fee": t["base"],
        "unit_min": IC_UNIT_MIN, "unit_fee": t["unit"],
        "steps": None, "steps_label": None,
        "free_min": free_min, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 1일 주차요금",
        "daily_hours": None, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": month[2] if kind == "노외" else None,
        "monthly_day": month[0] if month else None,
        "monthly_night": month[1] if month else None,
        "monthly_all": month[2] if month else None,
        "monthly_label": "주야간" if kind == "노외" else None,
        "pay": "", "basis": f"「이천시 주차장 설치 및 관리 조례」 별표1 {kind} {grade}급지",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def ic_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def _ic_strip_num(name: str) -> str:
    """노상 구간 이름 앞의 구간 번호(‘1-1 ’)를 떼어 낸다."""
    return re.sub(r"^\d+-\d+\s+", "", name or "").strip()


def _ic_rank(r: dict):
    """같은 주차장이 두 번 등록된 행 가운데 어느 쪽을 쓸지 정한다.

    표준데이터가 같은 주차장을 두 세트로 등록했다 — 구간 번호가 붙은 이름에
    운영시간 10:00~19:00·무료시간 없이, 번호 없는 이름에 09:00~18:00·1일권 적용
    5시간으로. 요금은 두 세트가 같으므로 무료시간·운영시간이 등록된 쪽을 쓴다.
    """
    return (0 if re.match(r"^\d+-\d+ ", r["주차장명"]) else 1,
            0 if r["요금정보"] == "혼합" else 1,
            0 if r["평일운영시작시각"] == "09:00" else 1)


def build_icheon():
    """이천시 공영주차장을 표준데이터 + 이천시 주차장 조례 별표1 + 이천스마트주차포털로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 이천시 범위를 벗어난 행은 제외(껍데기 행).
      · 이천시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다.
      · 표준데이터는 같은 주차장을 두 세트로 등록했다(구간 번호 붙은 이름 10:00~19:00 / 번호 없는
        이름 09:00~18:00) — 같은 관리번호·주소·요금이면 한 카드로 묶는다.
    요금은 조례 별표1의 급지 요금을 적용하고, 무료시간은 이천스마트주차포털 이용안내의
    주차장별 값(표준데이터에는 무료시간이 없다)을 넣는다. 운영시간은 표준데이터 등록값을 쓴다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == IC_PROVIDER]
    lots, excluded, merged, hour_fixed, space_diff, note_fixed = [], [], [], [], [], []
    ticket_diff, disc_note = [], []
    card_no = street_no = 0

    # --- 중복 등록 정리: 같은 관리번호에 주차장유형·이름(번호 제외)까지 같은 행은 하나로 묶는다.
    buckets = defaultdict(list)
    for r in rows_city:
        buckets[(re.sub(r"\s", "", r["주차장관리번호"]), r["주차장유형"],
                 _ic_strip_num(r["주차장명"]))].append(r)
    rows_one = []
    for _k, grp in buckets.items():
        grp = sorted(grp, key=_ic_rank)
        rows_one.append(grp[0])
        if len(grp) > 1:
            merged.append(f"{grp[0]['주차장명']}({grp[0]['주차장관리번호']}) ← "
                          f"{' / '.join(r['주차장명'] for r in grp[1:])} — 같은 주차장 두 세트 등록")
    # --- 주소+구획수가 같으면 다른 관리번호라도 같은 주차장이다(설봉공원입구 무료/유료 등).
    final_rows, seen_addr, seen_nm = [], {}, {}
    for r in sorted(rows_one, key=_ic_rank):
        key_a = (r["주차장유형"], re.sub(r"\s", "", r["소재지지번주소"] or ""), r["주차구획수"])
        key_b = (r["주차장유형"], re.sub(r"\s", "", r["소재지지번주소"] or ""),
                 _ic_strip_num(r["주차장명"]))
        prev = seen_addr.get(key_a) or seen_nm.get(key_b)
        if prev is not None:
            merged.append(f"{prev['주차장명']}({prev['주차장관리번호']}) ↔ "
                          f"{r['주차장명']}({r['주차장관리번호']}) — 같은 주소·구획, 유료 등록값을 씀")
            continue
        seen_addr[key_a] = r
        seen_nm[key_b] = r
        final_rows.append(r)

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                src="표준데이터", notice=None, tel="", mgmt="", lat=None, lng=None,
                base_date="", free_days=None, free_note=None, detail_road=None):
        nonlocal card_no, street_no
        street = ptype == "노상"
        fee["pay"] = (r.get("결제방법") or "").strip() if r else ""
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": src,
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "이천시",
            "dong": dong,
            "dong_src": "지번주소" if r and ic_dong_of((r.get("소재지지번주소") or "")) else
                        ("도로명주소" if r and ic_dong_of((r.get("소재지도로명주소") or "")) else "없음"),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": detail_road,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or IC_CORP,
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "이천시",
            "city_slug": "icheon",
        })

    for r in final_rows:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        mgmt = (r.get("주차장관리번호") or "").strip()
        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (IC_BBOX[0] <= lat <= IC_BBOX[1]
                                      and IC_BBOX[2] <= lng <= IC_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = ic_dong_of(jibun) or ic_dong_of(road)
        street = ptype == "노상"
        paid = (r.get("요금정보") or "").strip() == "혼합"
        note_raw = (r.get("특기사항") or "")
        win, oper, _closed = parse_schedule(r, note_raw)
        free_days = {"sat": False, "sun": False}
        free_note = None
        notice = None

        # 운영요일·시간 — 표준데이터는 유료 노상을 평일만(토·공휴일 00:00~00:00 미운영)으로
        #   등록했지만, 주차포털은 ‘토·일요일 및 공휴일 무료운영’이라 무료 개방으로 바로잡는다.
        if paid and street:
            if not oper["sat"] or not oper["sun"]:
                hour_fixed.append(f"{name}: 표준데이터 토·공휴일 미운영(00:00~00:00) → "
                                  f"주차포털 안내 토·일요일·공휴일 무료 개방")
            oper = {k: True for k in ("weekday", "sat", "sun")}
            free_days = {"sat": True, "sun": True}
            # 터미널(8-2)만 주말에도 24시간 유료다(주차포털) — 요일 무료 표기를 되돌린다.
            if name == "8-2 터미널공영":
                free_days = {"sat": False, "sun": False}

        if paid:
            grade = to_int(r.get("급지구분")) or 1
            grade = min(grade, 3)     # 요금표는 1~3급지다(4급지 등록 행은 모두 무료 주차장)
            kind = "노상" if street else "노외"
            fee = ic_fee(kind, grade)
            fee["std_grade"] = to_int(r.get("급지구분"))
            daily = to_int(r.get("1일주차권요금"))
            monthly_std = to_int(r.get("월정기권요금"))
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                          "base_fee": to_int(r.get("주차기본요금")),
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily, "monthly": monthly_std}
            # 표준데이터 등록값과 별표1이 같은지 점검해 다른 부분을 남긴다.
            tbl = IC_FEES[kind][grade]
            if (fee["std"]["base_fee"], fee["std"]["unit_fee"]) != (tbl["base"], tbl["unit"]):
                notice = ((notice + " · ") if notice else "") + \
                    (f"표준데이터 등록요금은 기본 {fee['std']['base_min']}분 "
                     f"{fee['std']['base_fee']}원·10분당 {fee['std']['unit_fee']}원입니다 — "
                     f"이 사이트는 조례 별표1 {grade}급지 요금을 적용합니다")
            # 무료시간 — 표준데이터에는 없고 주차포털 이용안내에만 있다.
            #   ‘최초 N분 무료 → 이후 10분당 요금’이므로 그 시간을 뺀 요금으로 계산하는
            #   deduct_min 방식(김포시 1시간 무료와 같은 처리)을 쓴다.
            free_min = IC_FREE_MIN.get(name)
            if free_min:
                fee["free_min"] = free_min
                fee["deduct_min"] = free_min
                note_fixed.append(f"{name}: 주차포털 안내 최초 {free_min}분 무료"
                                  f"(표준데이터 무료시간 미등록)")
            # 월 정기권 — 별표1에는 급지별로 있지만 공단은 5곳에서만 운영한다.
            if name not in IC_MONTHLY_LOTS:
                if fee["monthly"] or fee["monthly_day"] or fee["monthly_night"]:
                    ticket_diff.append(
                        f"{name}: 조례 별표1 월 정기권(주야간 {tbl['month'][2]:,}원)이 있으나 "
                        f"공단 FAQ는 이 주차장의 월 정기권을 미운영이라 안내해 비웠다")
                fee["monthly"] = fee["monthly_day"] = fee["monthly_night"] = fee["monthly_all"] = None
                fee["monthly_label"] = None
            elif monthly_std and monthly_std != fee["monthly"]:
                ticket_diff.append(f"{name}: 표준데이터 월 정기권 {monthly_std:,}원"
                                   f"(별표1 주야간 {fee['monthly']:,}원)")
        else:
            fee = ic_free_fee()

        # 주차장별 안내 — 요금 구조와 현장 사정을 카드에 적는다.
        extra = []
        if name == "8-2 터미널공영":
            extra.append("터미널 앞 노상주차장(8-2)만 토요일·일요일·공휴일에도 24시간 유료로 "
                         "운영합니다(주차포털). 나머지 유료 노상 구간은 평일 09:00~18:00에만 "
                         "요금을 받고 주말·공휴일은 무료입니다")
            free_days = {"sat": False, "sun": False}
            hour_fixed.append(f"{name}: 표준데이터 공휴일 미운영(00:00~00:00) → "
                              f"주차포털 안내 24시간 유료 운영")
        if name in ("공설운동장공영주차장", "북샛말공영주차장", "서희청소년문화센터공영주차장",
                    "택시쉼터공영주차장", "사동리 제1공영주차장"):
            extra.append("월 정기권을 운영하는 5개 주차장 가운데 한 곳입니다 — "
                         "이천시스마트주차포털(parking.2000fmc.or.kr)에서 신청합니다(공단 FAQ)")
        if name == "남천상가주차장":
            extra.append("지하 2층 보수공사로 2026-11-23~12-14에 지하 2층 전면 폐쇄 "
                         "(11-23~12-4는 출입·주차 불가)가 예정되어 있습니다(주차포털 공지, "
                         "공사 일정은 현장 여건에 따라 변경될 수 있습니다)")
        if name in ("마장택지지구 공영주차장1", "마장택지지구 공영주차장2"):
            extra.append("기본요금이 최초 60분 500원으로 등록되어 있어(표준데이터·포털 요금표) "
                         "1시간까지 500원이고, 이후 10분당 200원입니다. 주차포털 안내 표는 "
                         "‘최초 1시간 무료’로 적습니다 — 이 사이트는 등록요금으로 계산합니다")
            fee["free_min"] = None
            fee["deduct_min"] = None
            fee["base_min"] = 60
        if name in IC_SPACE_DIFF and IC_SPACE_DIFF[name] != spaces:
            space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 공단 FAQ {IC_SPACE_DIFF[name]}면")
            notice = ((notice + " · ") if notice else "") + \
                f"이천시시설관리공단 안내는 {IC_SPACE_DIFF[name]}면입니다(표준데이터 {spaces}면)"
        if extra:
            notice = " · ".join(([notice] if notice else []) + extra)

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=notice, tel=(r.get("전화번호") or "").strip(),
                mgmt=(r.get("관리기관명") or "").strip() or IC_CORP,
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"ich-{i:03d}" if l["list_mode"] == "card" else f"ich-s{i:03d}"

    quality = check_quality_icheon(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                   space_diff, note_fixed, ticket_diff)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(IC_PORTAL_FEE_TXT).strftime("%Y-%m-%d %H:%M")
                           if IC_PORTAL_FEE_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "이천시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-13",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 19:07 (KST)",
                    "note": ("경기도 이천시가 등록한 115행(노상 82·노외 33)을 읽었다. 이름·주소·구획수·"
                             "급지·운영요일·운영시간·좌표·전화·관리번호·결제방법과 등록요금 출처로 썼다. "
                             "같은 주차장이 두 세트로 등록된 행(구간 번호 붙은 이름 10:00~19:00 / "
                             "번호 없는 이름 09:00~18:00)과 다른 관리번호의 같은 주소 행을 묶었다."),
                },
                {
                    "id": "ordinance", "name": "이천시 주차장 설치 및 관리 조례 [별표 1] 공영주차장 주차요금표",
                    "org": "이천시(교통정책과) · 이천시시설관리공단 주차사업팀(031-635-2070)",
                    "url": IC_ORDINANCE_URL,
                    "file": IC_ORD_TXT.name,
                    "sha256": sha256(IC_ORD_TXT) if IC_ORD_TXT.exists() else None,
                    "license": "자치법규(공개)", "base_date": IC_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(IC_ORD_TXT),
                    "note": ("노상 1급지 최초 30분 600원·10분당 250원·1일 최대 7,000원(정기권 없음), "
                             "노외 1급지 600·250·7,000원·월 정기권 주야간 70,000원, 2급지 500·200·"
                             "5,000원·60,000원, 3급지 400·150·4,000원·40,000원을 별표/서식 HWP에서 "
                             "읽었다. 입차 후 10분 무료 회차, 급지(1급지 상업지역·2급지 주거·공업·"
                             "녹지지역·3급지 도시지역 외), 감면(중증장애인 2시간·유공자 4시간 면제 후 "
                             "50% 등), 정기권 주간 08:00~20:00·야간 18:30~익일 08:00도 함께 읽었다."),
                },
                {
                    "id": "portal_fee", "name": "이천스마트주차포털 주차장 이용안내(주차요금·운영시간)",
                    "org": "이천시시설관리공단 주차사업팀(031-635-2070)", "url": IC_PORTAL_FEE_URL,
                    "file": IC_PORTAL_FEE_TXT.name if IC_PORTAL_FEE_TXT.exists() else None,
                    "sha256": sha256(IC_PORTAL_FEE_TXT) if IC_PORTAL_FEE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": None, "fetched_at": _sync_time(IC_PORTAL_FEE_TXT),
                    "note": ("주차장별 최초 무료시간(창전동 임시·남천상가 30분, 공설운동장 30분, "
                             "마장 1·2·택시쉼터 1시간, 서희청소년문화센터 2시간)과 노상 유료 구간의 "
                             "평일 09:00~18:00 유료·주말 무료 운영, 터미널(8-2)만 24시간 유료인 "
                             "것을 확인했다. 1일 최대요금은 노상 1급지 7,000원·노외 2급지 5,000원·"
                             "3급지 4,000원이다."),
                },
                {
                    "id": "portal_disc", "name": "이천스마트주차포털 주차요금 감면안내",
                    "org": "이천시시설관리공단 주차사업팀(031-635-2070)", "url": IC_PORTAL_DISC_URL,
                    "file": IC_PORTAL_DISC_TXT.name if IC_PORTAL_DISC_TXT.exists() else None,
                    "sha256": sha256(IC_PORTAL_DISC_TXT) if IC_PORTAL_DISC_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": None, "fetched_at": _sync_time(IC_PORTAL_DISC_TXT),
                    "note": ("100% 감면(긴급자동차·명예시민증·모범납세자 등), 중증장애인 2시간 면제 "
                             "후 50%, 국가유공자·참전유공자·고엽제·5·18부상자·의사상자 4시간 면제 "
                             "후 50%, 우수자원봉사자·1종 저공해 1시간 면제 후 50%, 경차·다자녀·"
                             "임산부·경로우대 등 50%, 요일제 30%, 투표확인증 2,000원 감면을 "
                             "확인했다. 이중감면은 하지 않는다."),
                },
                {
                    "id": "portal_faq", "name": "이천시시설관리공단 자주묻는 질문(요금·운영시간·월정기권)",
                    "org": "이천시시설관리공단 주차사업팀(031-635-2070)", "url": IC_FAQ_URL,
                    "file": IC_FAQ_TXT.name if IC_FAQ_TXT.exists() else None,
                    "sha256": sha256(IC_FAQ_TXT) if IC_FAQ_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "게시 2026-06-16",
                    "rows_total": None, "fetched_at": _sync_time(IC_FAQ_TXT),
                    "note": ("공단 운영 노상 유인 31구간·노외 10개소와 급지별 배정(1급지 노상 "
                             "전구간·중리천로·남천상가·창전동 임시, 2급지 북샛말·서희청소년·"
                             "공설운동장·마장 1·2·사동리, 3급지 택시쉼터), 월 정기권 운영 5곳"
                             "(북샛말·택시쉼터·서희청소년·공설운동장·사동리)과 감면표를 확인했다."),
                },
                {
                    "id": "portal_notice", "name": "이천스마트주차포털 공지 — 남천상가 지하 2층 보수공사 안내",
                    "org": "이천시시설관리공단 주차사업팀(031-635-2070)", "url": IC_NOTICE_URL,
                    "file": IC_NOTICE_TXT.name if IC_NOTICE_TXT.exists() else None,
                    "sha256": sha256(IC_NOTICE_TXT) if IC_NOTICE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": None, "fetched_at": _sync_time(IC_NOTICE_TXT),
                    "note": ("남천상가 공영주차장 지하 2층 보수공사(2026-11-23~12-14, 11-23~12-4 "
                             "지하 2층 전면 폐쇄)를 확인해 카드에 적었다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in IC_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "icheon_grade",
            "unit_min": IC_UNIT_MIN,
            "base_min": IC_BASE_MIN,
            "applies": IC_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "상업지역", "base": 600, "unit": 250, "day": 7_000,
                 "month": 70_000, "lots": 0},
                {"grade": 2, "where": "주거지역·공업지역·녹지지역", "base": 500, "unit": 200,
                 "day": 5_000, "month": 60_000, "lots": 0},
                {"grade": 3, "where": "도시지역 외 지역", "base": 400, "unit": 150,
                 "day": 4_000, "month": 40_000, "lots": 0},
            ],
            "street": [
                {"grade": 1, "base": 600, "unit": 250, "day": 7_000},
            ],
            "special": [
                {"name": "창전동 임시·남천상가(노외 1급지)", "free": 30,
                 "tiers": "30분 무료 → 10분당 250원", "day": 7_000, "month": None},
                {"name": "공설운동장(노외 2급지)", "free": 30,
                 "tiers": "30분 무료 → 10분당 200원", "day": 5_000, "month": 60_000},
                {"name": "마장 제1·2(노외 2급지)", "free": 60,
                 "tiers": "1시간 무료 → 10분당 200원", "day": 5_000, "month": None},
                {"name": "서희청소년문화센터(노외 2급지)", "free": 120,
                 "tiers": "2시간 무료 → 10분당 200원", "day": 5_000, "month": 60_000},
                {"name": "택시쉼터(노외 3급지)", "free": 60,
                 "tiers": "1시간 무료 → 10분당 150원", "day": 4_000, "month": 40_000},
            ],
            "lots": [
                {"name": l["name"], "dong": l["dong"], "grade": l["fee"].get("grade"),
                 "free": l["fee"].get("free_min"), "unit": l["fee"].get("unit_fee"),
                 "day": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "corp": {"out": len([l for l in lots if l["fee"]["type"] == "유료" and l["ptype"] == "노외"]),
                     "st": len([l for l in lots if l["ptype"] == "노상" and l["fee"]["type"] == "유료"]),
                     "st_spaces": sum(l["spaces"] or 0 for l in lots
                                      if l["ptype"] == "노상" and l["fee"]["type"] == "유료"),
                     "free": len([l for l in lots if l["fee"]["type"] == "무료"]),
                     "free_spaces": sum(l["spaces"] or 0 for l in lots if l["fee"]["type"] == "무료"),
                     "corp_total": "노상 유인 31구간·노외 10개소 2,137면(공단 FAQ)"},
            "basis": ("「이천시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({IC_ORDINANCE_NOTE}) · 이천스마트주차포털 주차장 이용안내(2026-11-17) · "
                      "표준데이터 등록값(2026-10-13) 대조"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["이천시"] | {
        "city": "이천시",
        "weekend_free_pages": False,
        "discounts": IC_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "icheon_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_icheon(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                         note_fixed, ticket_diff):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_이천시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "특기사항_보정": note_fixed,
        "정기권_차이": ticket_diff,
        "감면_출처": "「이천시 주차장 설치 및 관리 조례」 별표1 세부사항 바목 · "
                    "이천스마트주차포털 감면안내",
        "무료시간_출처": "이천스마트주차포털 주차장 이용안내(표준데이터 무료시간 미등록)",
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 안성시 (T-03 Phase 21)
AS_PROVIDER = "경기도 안성시"
# 안성시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
AS_DISTRICTS = [("안성시", "anseong")]
AS_BBOX = (36.85, 37.17, 127.05, 127.58)   # 안성시 대략 경계(좌표 점검용)
# 안성시 법정동·읍·면 — 표준데이터 지번주소의 세 번째 낱말이 지역 이름이다(‘경기도 안성시 공도읍 승두리’).
AS_DONGS = ("공도읍", "미양면", "대덕면", "양성면", "원곡면", "고삼면", "보개면", "금광면",
            "서운면", "일죽면", "죽산면", "삼죽면",
            "가사동", "계동", "구포동", "금산동", "낙원동", "당왕동", "도기동", "동본동",
            "명륜동", "봉남동", "봉산동", "서인동", "석정동", "숭인동", "아양동", "연지동",
            "영동", "옥산동", "옥천동", "인지동", "중리동", "창전동", "현수동")

AS_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2115243"
                    "&gubun=ELIS&conDatGubunCd=1")
AS_CITY_OUT_URL = "https://www.anseong.go.kr/depart/contents.do?mId=0302060100"
AS_CITY_ST_URL = "https://www.anseong.go.kr/depart/contents.do?mId=0302060200"
AS_CORP_URL = "https://www.asimc.or.kr/portal/contents.do?mid=0104181600"
AS_CORP_FEE_URL = "https://www.asimc.or.kr/portal/contents.do?mid=0104181700"
AS_CORP_CSV_URL = "https://www.data.go.kr/data/15156880/fileData.do"
AS_NEWS_URL = "http://www.asns.co.kr/news/articleView.html?idxno=11974"
AS_ORD_HWP = RAW / "anseong.law.go.kr_주차장조례_별표1_20261117.hwp"
AS_ORD_TXT = RAW / "anseong.law.go.kr_주차장조례_별표1_20261117.txt"
AS_CITY_OUT_TXT = RAW / "anseong.go.kr_공영주차장_노외_현황_20261117.txt"
AS_CITY_ST_TXT = RAW / "anseong.go.kr_공영주차장_노상_현황_20261117.txt"
AS_CORP_TXT = RAW / "asimc.or.kr_공영주차장_소개_20261117.txt"
AS_CORP_FEE_TXT = RAW / "asimc.or.kr_주차장_이용요금_20261117.txt"
AS_CORP_CSV_TXT = RAW / "data.go.kr_안성시시설관리공단_안성공영주차장정보_20261117.txt"
AS_NEWS_TXT = RAW / "asns.co.kr_안성맞춤2구간_노상_유료운영_20261117.txt"
AS_NEWS_FEE_URL = "http://www.joongang.tv/news/articleView.html?idxno=130621"
AS_NEWS_FEE_TXT = RAW / "joongang.tv_안성시_주차요금_개정_20250521_20261117.txt"
AS_ORDINANCE_NOTE = "공포 2026-03-13 · 경기도안성시조례 제2217호(일부개정) · 별표1 〈개정 2025.4.18.〉"
AS_BASE_MIN = 30
AS_UNIT_MIN = 30
AS_FREE_MIN = 30

# 안성시 공영주차장 요금 — 「안성시 주차장 설치 및 관리조례」 [별표 1] 공영주차장 주차요금표
#   (공포 2026-03-13, 경기도안성시조례 제2217호. 별표/서식 HWP에서 표를 읽음)의 값이다.
#   · 30분 미만은 무료(비고3) — 그 뒤 30분 단위로 요금이 붙는다.
#   · 노외 1급지: 2시간까지 30분당 500원 → 2시간 초과 30분당 2,000원,
#     1일 주차권 10,000원, 월 정기권 100,000원
#   · 노외 2급지: 200 · 1,000 · 6,000 · 60,000원 / 3급지: 200 · 1,000 · 5,000 · 40,000원
#   · 노상 1급지: 500 · 2,000 · 8,000 · 80,000원 / 2급지: 200 · 1,000 · 4,000원(정기권 없음)
#   · 급지(비고2): 1급지 동·읍의 도시계획 지역, 2급지 1급지 외의 지역, 3급지 공업지역 또는
#     공업지역에 접한 지역. 안성시시설관리공단 홈페이지는 같은 표를 1급지(동·읍 단위)·
#     2급지(면 단위)·3급지(공업지역)로 안내해 별표와 같은 값을 보인다.
#   · 비고4: 사전 약정 없는 요금이 1일 주차권을 넘으면 1일 주차권을, 1일 주차권 합계가
#     월 정기권을 넘으면 월 정기권을 단위요금으로 한다 — 계산기는 1일 주차권을 상한으로 쓴다.
AS_FEES = {
    "노상": {1: {"tier1": 500, "tier2": 2_000, "day": 8_000, "month": 80_000},
             2: {"tier1": 200, "tier2": 1_000, "day": 4_000, "month": None}},
    "노외": {1: {"tier1": 500, "tier2": 2_000, "day": 10_000, "month": 100_000},
             2: {"tier1": 200, "tier2": 1_000, "day": 6_000, "month": 60_000},
             3: {"tier1": 200, "tier2": 1_000, "day": 5_000, "month": 40_000}},
}

# 안성시시설관리공단이 위탁받아 운영하는 13곳(노외 12·노상 1) — 모두 카드결제 전용 유료 주차장이다
#   (공단 ‘공영주차장 소개’ 운영현황, 2026-11-17 조회). 이름은 표준데이터 등록명에 맞춰 찾는다.
AS_CORP_LOTS = {
    "석정동공영주차장(건축물식)": ("석정동 공영주차장", 1),
    "금산동 공영주차장": ("금산동 공영주차장", 1),
    "공도저류지 공영주차장": ("공도저류지 공영주차장", 1),
    "동본동공영주차장(건축물식)": ("동본동 공영주차장", 1),
    "서인동공영주차장(건축물식)": ("서인동 공영주차장", 1),
    "대덕 내리 공영주차장": ("대덕면 내리 공영주차장", 2),
    "아양지구 제2공영주차장": ("아양지구 제2공영주차장", 1),
    "안성맞춤대로2구간": ("안성맞춤2구간 노상공영주차장", 1),
}

# 공단이 운영하지만 표준데이터에 등록되지 않은 노외 5곳 — 공단 공영주차장 소개·공공데이터포털
#   파일데이터(안성시시설관리공단_안성공영주차장정보, 12행, 2026-06-10)의 값으로 채운다.
#   (지번, 도로명, 면수, 급지, 1일 주차권) — 좌표는 원자료에 없어 지도는 이름·주소 검색으로 연다.
AS_EXTRA = (
    ("안성맞춤공감센터 공영주차장", "경기도 안성시 낙원동 68-1", "경기도 안성시 장기로 107",
     "낙원동", 67, 1),
    ("아양지구 제3공영주차장", "경기도 안성시 옥산동 596", "", "옥산동", 65, 1),
    ("대덕면 광덕 공영주차장", "경기도 안성시 대덕면 내리 322-12", "", "대덕면", 49, 2),
    ("원곡면 공영주차장", "경기도 안성시 원곡면 외가천리 208", "", "원곡면", 86, 2),
    ("안성 제2산업단지 공영주차장", "경기도 안성시 미양면 계륵리 80-13", "", "미양면", 288, 3),
)

# 표준데이터·공단 안내의 면수 차이(표준, 공단, 시 홈페이지) — 카드에 차이를 적는다.
AS_SPACE_DIFF = {
    "석정동공영주차장(건축물식)": (54, 47, 53),
    "금산동 공영주차장": (19, 18, 18),
    "공도저류지 공영주차장": (201, 199, None),
    "동본동공영주차장(건축물식)": (87, 70, 76),
    "서인동공영주차장(건축물식)": (74, 68, 74),
    "대덕 내리 공영주차장": (48, 38, None),
}

# 시 홈페이지 노상주차장 현황(2026-11-17)과 표준데이터의 이름·면수 차이 — 품질 리포트에 남긴다.
AS_STREET_DIFF = (
    "혜산로 노상주차장(시 홈페이지, 44면) ↔ 아양로(표준데이터, 아양동 384, 44면) — 같은 구간으로 보임",
    "명륜천 주차장(시 홈페이지, 68면, 장안면옥~보룡약국)은 표준데이터에 없음",
    "안성맞춤대로1구간 22면(표준) ↔ 19면(시) · 안성맞춤대로2구간 19면(표준) ↔ 23면(시) · "
    "비룡로 27면(표준) ↔ 19면(시) · 고수1로 35면(표준) ↔ 32면(시)",
)

# 안성시 ‘주차요금의 감면’(조례 제3조의2, 시 홈페이지 주차요금 면제표, 공단 이용요금 안내) —
#   둘 이상의 감면사유에 해당하면 감면율이 높은 하나만 적용하고, 증명서를 제시해야 한다.
AS_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차 60%", "rate": 0.6, "exempt_min": 0,
     "note": "경형자동차(배기량 1,000cc 미만) — 조례 제3조의2④"},
    {"label": "경증장애인·저공해차 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": "장애 정도가 심하지 않은 장애인, 저공해자동차 표지 부착 차량(전기차는 최초 2시간 "
             "전액 면제 가능), 우수자원봉사자(경기도·안성시), 병역명문가 예우대상자와 가족, "
             "두 자녀 이상 가정 경기아이플러스카드 소지자"},
    {"label": "중증장애인·국가유공자 등 1시간 면제 후 50%", "rate": 0.5, "exempt_min": 60,
     "note": "장애 정도가 심한 장애인, 국가유공자·상이자, 고엽제후유증환자, 5·18민주유공자 — "
             "본인 소유 차량을 직접 운전·동승한 경우 최초 1시간 면제, 그 뒤 50%"},
    {"label": "차량부제·함께 타기 30%", "rate": 0.3, "exempt_min": 0,
     "note": "자가용 승용차로 차량부제 운행·함께 타기 참여 스티커를 부착한 차량"},
    {"label": "긴급·모범납세자 등 100% 면제", "rate": 1.0, "exempt_min": 0,
     "note": "긴급자동차, 모범납세자·경기도 유공납세자·성실납세자 주차스티커 부착 차량"
             "(스티커 유효기간에 한정)"},
]


def as_dong_of(text: str):
    """주소에서 안성시 법정동·읍·면을 뽑는다 — ‘경기도 안성시 {동·읍·면} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "안성시" and parts[2] in AS_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(AS_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def as_fee(kind: str, grade: int, pay: str = ""):
    """안성시 공영주차장 요금 → 사이트 공통 fee 객체.

    별표1은 ‘30분 미만 무료 → 2시간까지 30분당 500원(2급지 200원) → 2시간 초과 30분당
    2,000원(1,000원)’ 구조다. 시간대 누진은 steps 로 적고, 무료 30분은 그 시간을 뺀
    시간으로 계산하는 deduct_min 으로 넣는다(김포·이천과 같은 처리). 1일 주차권은 상한.
    """
    t = AS_FEES[kind][grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "std_grade": None,
        "base_min": AS_BASE_MIN, "base_fee": t["tier1"],
        "unit_min": AS_UNIT_MIN, "unit_fee": t["tier2"],
        "steps": [{"until": 120, "unit_min": AS_UNIT_MIN, "unit_fee": t["tier1"]},
                  {"until": None, "unit_min": AS_UNIT_MIN, "unit_fee": t["tier2"]}],
        "steps_label": f"2시간까지 30분당 {t['tier1']:,}원",
        "free_min": AS_FREE_MIN, "deduct_min": AS_FREE_MIN,
        "cap_fee": None, "cap_src": "조례 별표1 1일 주차권(비고4)",
        "daily_hours": None, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": t["month"], "monthly_day": None, "monthly_night": None,
        "monthly_all": t["month"], "monthly_label": None,
        "pay": pay, "basis": f"「안성시 주차장 설치 및 관리조례」 별표1 {kind} {grade}급지",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def as_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def build_anseong():
    """안성시 공영주차장을 표준데이터 + 안성시 주차장 조례 별표1 + 안성시시설관리공단 안내로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 안성시 범위를 벗어난 행은 제외(껍데기 행).
      · 안성시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동·읍·면만 만든다.
    요금은 조례 별표1의 급지 요금을 적용하고, 30분 미만 무료(비고3)를 deduct_min 으로 넣는다.
    운영시간은 표준데이터 등록값을 쓰고, 공단이 2026-09-01부터 유료로 바꾼 안성맞춤2구간
    노상주차장만 평일 09:00~18:00·주말·공휴일 무료로 바로잡는다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == AS_PROVIDER]
    lots, excluded, merged = [], [], []
    hour_fixed, space_diff, note_fixed, reclassified = [], [], [], []
    card_no = street_no = 0

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                src="표준데이터", notice=None, tel="", mgmt="", lat=None, lng=None,
                base_date="", free_days=None, free_note=None, detail_road=None,
                kind="공영"):
        nonlocal card_no, street_no
        street = ptype == "노상"
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": src,
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "안성시",
            "dong": dong,
            "dong_src": "지번주소" if r and as_dong_of((r.get("소재지지번주소") or "")) else
                        ("도로명주소" if r and as_dong_of((r.get("소재지도로명주소") or "")) else
                         ("공단 안내" if (not r and dong) else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else kind,
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": detail_road,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "안성시시설관리공단",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "안성시",
            "city_slug": "anseong",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is not None and not (AS_BBOX[0] <= lat <= AS_BBOX[1]
                                      and AS_BBOX[2] <= lng <= AS_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = as_dong_of(jibun) or as_dong_of(road)
        street = ptype == "노상"
        corp = AS_CORP_LOTS.get(name)
        paid = (r.get("요금정보") or "").strip() in ("유료", "혼합")
        if corp and not paid:
            # 표준데이터가 ‘무료’로 등록한 아양지구 제2·안성맞춤2구간을 공단 운영(유료)에 맞춘다.
            paid = True
            reclassified.append(
                (f"{name}: 표준데이터 요금정보 ‘{(r.get('요금정보') or '').strip() or '무료'}’ ↔ "
                 f"안성시시설관리공단이 카드결제 전용 유료로 운영({corp[0]}) — 유료로 바로잡음"))
        note_raw = (r.get("특기사항") or "")
        win, oper, _closed = parse_schedule(r, note_raw)
        free_days = {"sat": False, "sun": False}
        free_note = None
        notice = None
        extra = []

        # 안성맞춤2구간 노상주차장은 2026-09-01부터 공단이 유료 운영 — 평일 09:00~18:00,
        #   토요일·일요일·공휴일 무료, 카드결제만 받는다(공단 홈페이지·안성뉴스 2026-08-26).
        if name == "안성맞춤대로2구간":
            win["weekday"] = {"open": True, "start": 9 * 60, "end": 18 * 60, "24h": False,
                              "listed": True, "raw": ["09:00", "18:00"]}
            win["sat"] = {"open": True, "start": 9 * 60, "end": 18 * 60, "24h": False,
                          "listed": True, "raw": ["09:00", "18:00"]}
            win["sun"] = dict(win["sat"])
            oper = {"weekday": True, "sat": True, "sun": True}
            free_days = {"sat": True, "sun": True}
            hour_fixed.append(
                f"{name}: 표준데이터 24시간·무료 등록 → 공단 안내 2026-09-01부터 유료"
                f"(평일 09:00~18:00, 토·일·공휴일 무료, 카드결제)")
            extra.append(
                "안성시시설관리공단이 2026-09-01부터 유료로 운영합니다 — 평일 09:00~18:00에만 "
                "요금을 받고 토요일·일요일·공휴일은 무료이며, 현금 없이 카드로만 결제합니다"
                "(공단 홈페이지·안성뉴스 2026-08-26). 공단은 이 구간을 ‘안성맞춤2구간 "
                "노상공영주차장’으로 안내합니다")
        elif paid and street:
            extra.append(
                "조례 별표1 비고5는 노상주차장 운영시간을 하절기(4~10월) 08:00~20:00·"
                "동절기(11~3월) 09:00~19:00으로 정하고, 시장이 주차수요·주민편익을 위해 "
                "주차장별로 조정할 수 있습니다 — 표준데이터에는 24시간으로 등록되어 있어 "
                "현장 안내를 확인하세요")

        if paid:
            kind = "노상" if street else "노외"
            grade = to_int(r.get("급지구분")) or 1
            grade = min(max(grade, 1), 3)     # 요금표는 1~3급지다
            fee = as_fee(kind, grade, pay=(r.get("결제방법") or "").strip())
            if corp:
                fee["grade"] = corp[1]
                grade = corp[1]
                # 공단이 운영하는 13곳은 카드결제 전용이다(공단 운영현황) — 표준데이터 등록값과 다르다.
                if fee["pay"] != "신용카드":
                    if fee["pay"]:
                        note_fixed.append(f"{name}: 표준데이터 결제방법 ‘{fee['pay']}’ ↔ "
                                          f"공단 안내 카드결제 전용")
                    fee["pay"] = "신용카드"
            fee["std_grade"] = to_int(r.get("급지구분"))
            daily = to_int(r.get("1일주차권요금"))
            monthly_std = to_int(r.get("월정기권요금"))
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                          "base_fee": to_int(r.get("주차기본요금")),
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily, "monthly": monthly_std}
            tbl = AS_FEES[kind][grade]
            if fee["std"]["base_fee"] and fee["std"]["unit_fee"] and \
                    (fee["std"]["base_fee"], fee["std"]["unit_fee"]) != (tbl["tier1"], tbl["tier2"]):
                notice = ((notice + " · ") if notice else "") + \
                    (f"표준데이터 등록요금은 기본 {fee['std']['base_min']}분 "
                     f"{fee['std']['base_fee']:,}원·{fee['std']['unit_min']}분당 "
                     f"{fee['std']['unit_fee']:,}원입니다 — 이 사이트는 조례 별표1 "
                     f"{grade}급지 요금(2시간까지 30분당 {tbl['tier1']:,}원, 2시간 초과 30분당 "
                     f"{tbl['tier2']:,}원)을 적용합니다")
            if daily and daily != tbl["day"]:
                note_fixed.append(f"{name}: 표준데이터 1일 주차권 {daily:,}원 ↔ 별표1 "
                                  f"{kind} {grade}급지 {tbl['day']:,}원")
            if monthly_std and monthly_std != (tbl["month"] or 0):
                note_fixed.append(f"{name}: 표준데이터 월 정기권 {monthly_std:,}원 ↔ 별표1 "
                                  f"{kind} {grade}급지 {tbl['month'] or 0:,}원")
        else:
            fee = as_free_fee()

        sp = AS_SPACE_DIFF.get(name)
        if sp and sp[0] != sp[1]:
            space_diff.append(f"{name}: 표준데이터 {sp[0]}면 ↔ 공단 {sp[1]}면"
                              + (f" ↔ 시 홈페이지 {sp[2]}면" if sp[2] else ""))
            extra.append(f"안성시시설관리공단 안내는 {sp[1]}면입니다(표준데이터 등록 {sp[0]}면"
                         + (f", 시 홈페이지 {sp[2]}면" if sp[2] else "") + ")")
        if extra:
            notice = " · ".join(([notice] if notice else []) + extra)

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=notice, tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "안성시시설관리공단"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    # 공단이 운영하지만 표준데이터에 없는 노외 5곳 — 공단 자료로 채운다.
    for name, jibun, road, dong, spaces, grade in AS_EXTRA:
        kind = "노외"
        fee = as_fee(kind, grade, pay="신용카드")
        win = {k: {"open": True, "start": 0, "end": 24 * 60, "24h": True, "listed": True,
                   "raw": ["00:00", "23:59"]} for k in ("weekday", "sat", "sun")}
        notice = ("안성시시설관리공단이 운영하는 주차장으로 표준데이터에는 등록되어 있지 않습니다"
                  " — 공단 공영주차장 소개와 공공데이터포털 ‘안성시시설관리공단_안성공영주차장정보’"
                  "(12행, 2026-06-10)의 급지·면수·요금입니다. 원자료에 좌표가 없어 지도는 "
                  "이름·주소 검색으로 엽니다")
        if name == "안성맞춤공감센터 공영주차장":
            notice += " · 면수는 부설주차장을 포함한 값입니다(일반62·장애인2·전기차2·임산부1)"
        add_lot(name, jibun, road, kind, spaces, dong, win,
                {"weekday": True, "sat": True, "sun": True}, fee, src="안성시시설관리공단",
                notice=notice, tel="031-677-6262", mgmt="안성시시설관리공단", lat=None, lng=None,
                base_date="2026-06-10")

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"aseo-{i:03d}" if l["list_mode"] == "card" else f"aseo-s{i:03d}"

    quality = check_quality_anseong(rows_all, rows_city, lots, excluded, merged, hour_fixed,
                                    space_diff, note_fixed, reclassified)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(AS_ORD_TXT).strftime("%Y-%m-%d %H:%M")
                           if AS_ORD_TXT.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "안성시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-15",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-17 16:05 (KST)",
                    "note": ("경기도 안성시가 등록한 52행(노외 35·노상 17)을 읽었다. 이름·주소·"
                             "구획수·급지·운영요일·운영시간·좌표·전화·관리번호·결제방법과 등록요금 "
                             "출처로 썼다. 같은 관리번호·이름 중복은 없었고, 같은 지번에 둘 이상 "
                             "등록된 노상 구간(남파로 1·2구간, 중앙로·장기로 2구간)은 이름·면수가 "
                             "달라 그대로 두었다."),
                },
                {
                    "id": "ordinance",
                    "name": "안성시 주차장 설치 및 관리조례 [별표 1] 공영주차장 주차요금표",
                    "org": "안성시(교통정책과, 031-678-2812) · 안성시시설관리공단 공영주차팀(031-677-6262)",
                    "url": AS_ORDINANCE_URL,
                    "file": AS_ORD_TXT.name,
                    "sha256": sha256(AS_ORD_TXT) if AS_ORD_TXT.exists() else None,
                    "license": "자치법규(공개)", "base_date": AS_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(AS_ORD_TXT),
                    "note": ("노외 1급지 2시간까지 30분당 500원·2시간 초과 30분당 2,000원·1일 "
                             "10,000원·월 정기권 100,000원, 2급지 200·1,000·6,000·60,000원, "
                             "3급지 200·1,000·5,000·40,000원, 노상 1급지 500·2,000·8,000·"
                             "80,000원, 노상 2급지 200·1,000·4,000원(정기권 없음)을 별표/서식 "
                             "HWP에서 읽었다. 30분 미만 무료(비고3), 1일·월 주차권을 단위요금으로 "
                             "하는 상한(비고4), 노상 운영시간 하절기 08:00~20:00·동절기 "
                             "09:00~19:00(비고5), 전통시장 인근 노상의 30분 미만 무료·일요일 "
                             "무료 운영(비고6)도 함께 읽었다."),
                },
                {
                    "id": "news_fee", "name": "중앙신문 — 안성시, 공영주차장 무료시간 30분으로 확대·요금 체계 조정(2025.4.21 시행)",
                    "org": "중앙신문(2025-04-09 보도)", "url": AS_NEWS_FEE_URL,
                    "file": AS_NEWS_FEE_TXT.name if AS_NEWS_FEE_TXT.exists() else None,
                    "sha256": sha256(AS_NEWS_FEE_TXT) if AS_NEWS_FEE_TXT.exists() else None,
                    "license": "언론 보도(참고용)", "base_date": "2025-04-09",
                    "rows_total": None, "fetched_at": _sync_time(AS_NEWS_FEE_TXT),
                    "note": ("무료 주차시간을 10분에서 30분으로 넓히고, 2시간까지 30분당 500원·2시간 초과 "
                             "30분당 2,000원으로 올리며 월 정기권을 60,000원에서 100,000원으로 인상한 "
                             "개정안을 2025-04-21부터 적용한다는 것을 확인했다(대상 14개소 유료 "
                             "노상·노외). 별표1 〈개정 2025.4.18.〉과 같은 내용이다."),
                },
                {
                    "id": "corp_intro", "name": "안성시시설관리공단 공영주차장 소개(운영현황·주차장 현황)",
                    "org": "안성시시설관리공단(031-672-1234)", "url": AS_CORP_URL,
                    "file": AS_CORP_TXT.name if AS_CORP_TXT.exists() else None,
                    "sha256": sha256(AS_CORP_TXT) if AS_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 13, "fetched_at": _sync_time(AS_CORP_TXT),
                    "note": ("공단이 안성시에서 위탁받아 운영하는 공영주차장 13곳(노외 12·노상 1, "
                             "1,053면)의 이름·주소·급지·면수를 확인했다 — 노외는 24시간, 노상"
                             "(안성맞춤2구간, 서인동 121, 19면)은 평일 09:00~18:00·주말·공휴일 "
                             "무료이고 모두 카드결제 전용이다."),
                },
                {
                    "id": "corp_fee", "name": "안성시시설관리공단 주차장 이용요금·주차장 주요감면 안내",
                    "org": "안성시시설관리공단(031-672-1234)", "url": AS_CORP_FEE_URL,
                    "file": AS_CORP_FEE_TXT.name if AS_CORP_FEE_TXT.exists() else None,
                    "sha256": sha256(AS_CORP_FEE_TXT) if AS_CORP_FEE_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": None, "fetched_at": _sync_time(AS_CORP_FEE_TXT),
                    "note": ("1급지(동·읍 단위) 30분 미만 무료·2시간까지 500원·2시간 초과 "
                             "2,000원·1일 10,000원·월 100,000원, 2급지(면 단위) 200·1,000·"
                             "6,000·60,000원, 3급지(공업지역) 200·1,000·5,000·40,000원과 감면표"
                             "(100%·1시간 면제 후 50%·60%·50%·30%)를 조례 제3조의2와 대조했다."),
                },
                {
                    "id": "corp_csv", "name": "안성시시설관리공단_안성공영주차장정보(공공데이터포털 15156880)",
                    "org": "안성시시설관리공단 기획예산팀(070-8856-2339)",
                    "url": AS_CORP_CSV_URL,
                    "file": AS_CORP_CSV_TXT.name if AS_CORP_CSV_TXT.exists() else None,
                    "sha256": sha256(AS_CORP_CSV_TXT) if AS_CORP_CSV_TXT.exists() else None,
                    "license": "이용허락범위 제한 없음", "base_date": "2026-06-10",
                    "rows_total": 12, "fetched_at": _sync_time(AS_CORP_CSV_TXT),
                    "note": ("공단이 운영하는 노외 12곳의 급지·주차면수·운영시간·요금정보·기본 "
                             "무료시간(30분 미만)·추가단위(30분)·1일 주차요금·결제방법을 확인해 "
                             "표준데이터에 없는 5곳(안성맞춤공감센터·아양지구 제3·대덕면 광덕·"
                             "원곡면·안성 제2산업단지)을 채웠다."),
                },
                {
                    "id": "city_out", "name": "안성시청 공영주차장 현황(노외)·주차요금 안내",
                    "org": "안성시청 교통정책과(031-678-2815)",
                    "url": AS_CITY_OUT_URL,
                    "file": AS_CITY_OUT_TXT.name if AS_CITY_OUT_TXT.exists() else None,
                    "sha256": sha256(AS_CITY_OUT_TXT) if AS_CITY_OUT_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 27, "fetched_at": _sync_time(AS_CITY_OUT_TXT),
                    "note": ("노외 공영주차장 27곳의 면수(계·주차대수·장애인·경차)·전기차 "
                             "충전시설과 급지별 요금·감면표를 확인했다. 면수가 표준데이터와 다른 "
                             "곳은 카드에 함께 적었다."),
                },
                {
                    "id": "city_street", "name": "안성시청 공영주차장 현황(노상)",
                    "org": "안성시청 교통정책과(031-678-2815)",
                    "url": AS_CITY_ST_URL,
                    "file": AS_CITY_ST_TXT.name if AS_CITY_ST_TXT.exists() else None,
                    "sha256": sha256(AS_CITY_ST_TXT) if AS_CITY_ST_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 17, "fetched_at": _sync_time(AS_CITY_ST_TXT),
                    "note": ("노상 공영주차장 17곳의 위치와 면수를 확인해 표준데이터와 대조했다 — "
                             "혜산로(44면)는 표준데이터의 아양로로 보이고, 명륜천 주차장(68면)은 "
                             "표준데이터에 없다. 안성맞춤대로1·2구간과 비룡로·고수1로는 면수가 다르다."),
                },
                {
                    "id": "news_paid", "name": "안성뉴스 — 안성맞춤2구간 노상공영주차장, 9월 1일부터 유료 운영",
                    "org": "안성뉴스(2026-08-26 보도)", "url": AS_NEWS_URL,
                    "file": AS_NEWS_TXT.name if AS_NEWS_TXT.exists() else None,
                    "sha256": sha256(AS_NEWS_TXT) if AS_NEWS_TXT.exists() else None,
                    "license": "언론 보도(참고용)", "base_date": "2026-08-26",
                    "rows_total": None, "fetched_at": _sync_time(AS_NEWS_TXT),
                    "note": ("안성맞춤2구간 노상공영주차장(서인동 121)이 2026-09-01부터 유료로 "
                             "바뀌어 평일 09:00~18:00 운영하고 주말·공휴일은 무료, 카드결제만 "
                             "받는다는 것을 확인했다 — 표준데이터는 아직 무료·24시간으로 등록."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in AS_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "anseong_grade",
            "unit_min": AS_UNIT_MIN,
            "base_min": AS_BASE_MIN,
            "free_min": AS_FREE_MIN,
            "applies": AS_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "동·읍의 도시계획 지역", "tier1": 500, "tier2": 2_000,
                 "day": 10_000, "month": 100_000, "lots": 0},
                {"grade": 2, "where": "1급지 외의 지역(면)", "tier1": 200, "tier2": 1_000,
                 "day": 6_000, "month": 60_000, "lots": 0},
                {"grade": 3, "where": "공업지역 또는 공업지역에 접한 지역", "tier1": 200,
                 "tier2": 1_000, "day": 5_000, "month": 40_000, "lots": 0},
            ],
            "street": [
                {"grade": 1, "tier1": 500, "tier2": 2_000, "day": 8_000, "month": 80_000},
                {"grade": 2, "tier1": 200, "tier2": 1_000, "day": 4_000, "month": None},
            ],
            "lots": [
                {"name": l["name"], "dong": l["dong"], "grade": l["fee"].get("grade"),
                 "free": l["fee"].get("free_min"), "unit": l["fee"].get("unit_fee"),
                 "day": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "corp": {
                "out": len([l for l in lots if l["fee"]["type"] == "유료" and l["ptype"] == "노외"]),
                "st": len([l for l in lots if l["ptype"] == "노상" and l["fee"]["type"] == "유료"]),
                "st_spaces": sum(l["spaces"] or 0 for l in lots
                                 if l["ptype"] == "노상" and l["fee"]["type"] == "유료"),
                "free": len([l for l in lots if l["fee"]["type"] == "무료"]),
                "free_spaces": sum(l["spaces"] or 0 for l in lots if l["fee"]["type"] == "무료"),
                "corp_total": "공영주차장 13개소 1,053면(노외 12·노상 1, 공단 운영현황)",
            },
            "basis": ("「안성시 주차장 설치 및 관리조례」 [별표 1] 공영주차장 주차요금표"
                      f"({AS_ORDINANCE_NOTE}) · 안성시시설관리공단 주차장 이용요금 안내"
                      "(2026-11-17) · 표준데이터 등록값(2026-10-15) 대조"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["안성시"] | {
        "city": "안성시",
        "weekend_free_pages": False,
        "discounts": AS_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "anseong_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_anseong(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                          note_fixed, reclassified):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_안성시행수": len(rows),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "특기사항_보정": note_fixed,
        "요금구분_보정": reclassified,
        "노상_자료차이": list(AS_STREET_DIFF),
        "감면_출처": "「안성시 주차장 설치 및 관리조례」 제3조의2 · 안성시청 주차요금 면제표 · "
                    "안성시시설관리공단 주차장 이용요금 안내",
        "무료시간_출처": "조례 별표1 비고3(주차시간 30분 미만 무료)",
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }

# ---------------------------------------------------------------- 양주시 (T-03 Phase 22)
YJ_PROVIDER = "경기도 양주시"
# 양주시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
YJ_DISTRICTS = [("양주시", "yangju")]
YJ_BBOX = (37.68, 37.97, 126.88, 127.16)   # 양주시 대략 경계(좌표 점검용)
# 양주시 법정동·읍·면 — 표준데이터 지번주소의 세 번째 낱말이 지역 이름이다(‘경기도 양주시 덕정동 350-272’).
#   행정동(양주1·2동, 회천1~4동)은 법정동 여러 개를 묶은 이름이라 주소에는 법정동이 나온다.
YJ_DONGS = ("백석읍", "광적면", "은현면", "남면", "장흥면",
            "유양동", "어둔동", "남방동", "마전동", "산북동",
            "덕정동", "고암동", "봉양동", "회정동", "회암동", "회남동", "율정동", "옥정동",
            "광사동", "고읍동", "만송동", "덕계동", "고읍리")

YJ_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2108757"
                    "&gubun=ELIS&conDatGubunCd=1")
YJ_CORP_URL = "https://www.yjuc.or.kr/sub/content.asp?cIdx=22"
YJ_PORTAL_URL = "https://parking.yjuc.or.kr/parking/list.do"
YJ_PORTAL_AMT_URL = "https://parking.yjuc.or.kr/parking/parkingAmt.do"
YJ_NEWS_URL = "https://www.shinailbo.co.kr/news/articleView.html?idxno=5018586"
YJ_ORD_TXT = RAW / "yangju.law.go.kr_주차장조례_20261117.txt"
YJ_ORD_ANNEX_TXT = RAW / "yangju.law.go.kr_주차장조례_별표1_20261117.txt"
YJ_ORD_ANNEX_HWP = RAW / "yangju.law.go.kr_주차장조례_별표1_20261117.hwp"
YJ_CORP_TXT = RAW / "yjuc.or.kr_공영주차장_20261117.txt"
YJ_PORTAL_JSON = RAW / "parking.yjuc.or.kr_searchParkingList_20261117.json"
YJ_NEWS_TXT = RAW / "shinailbo.co.kr_양주덕정역공영주차장_유료전환_20261117.txt"
YJ_ORDINANCE_NOTE = ("공포 2026-02-02 · 경기도양주시조례 제1498호(일부개정) · "
                     "별표1 〈개정 2021.8.2.〉")
YJ_BASE_MIN = 30
YJ_UNIT_MIN = 10
YJ_FREE_MIN = 10

# 양주시 공영주차장 요금 — 「양주시 주차장 조례」 [별표 1] 공영주차장 주차요금표
#   (공포 2026-02-02, 경기도양주시조례 제1498호. 별표1 〈개정 2021.8.2.〉 HWP에서 표를 읽음).
#   · 1급지: 최초 30분 이내 기본요금 600원 → 10분당 200원, 1일 주차권(선납) 7,000원, 월 정기권(선납) 60,000원
#   · 2급지: 300원 → 10분당 100원, 1일 3,000원, 월 40,000원
#   · 거주자 전용 주차구획: 주간(09:00~19:00) 20,000원 · 야간(19:00~익일 09:00) 20,000원 · 전일 30,000원
#   · 최초 30분 미만은 기본요금, 다만 입차 후 최초 10분까지는 무료(별표1 아래 단서)
#   · 비고2: 운영시간 주간 08:00~20:00 · 야간 20:00~익일 08:00(시장이 조정 가능)
#   · 비고3: 야간·주말·공휴일 주차요금은 무료 — 무료운영 시간에 주차수요가 많으면 유료로 운영할 수 있다
#   · 비고4: 1급지 = 국도·지방도·시도로부터 500미터 이내, 2급지 = 그 밖의 지역
#   · 비고7: 16~36인승 승합·2.5~5톤 화물은 기준요금의 2배, 36인승 이상·5톤 이상은 3배
YJ_FEES = {
    1: {"base": 600, "unit": 200, "day": 7_000, "month": 60_000},
    2: {"base": 300, "unit": 100, "day": 3_000, "month": 40_000},
}
# 장흥관광지 공영주차장(제1·2·7 등)은 급지 요금이 아니라 당일 정액이다 —
#   경차 1,000원 · 소·중형 2,000원 · 대형 3,000원, 무인정산기 카드결제만(현금 불가).
YJ_FLAT_DAY = 2_000
YJ_FLAT_SHORT = 1_000
YJ_FLAT_LONG = 3_000
YJ_FLAT_LOTS = ("장흥관광지 제1주차장(하천변)", "장흥관광지 제2주차장(장흥관광지)",
                "장흥관광지 제3주차장(효편의점)", "장흥관광지 제4주차장(선비촌)",
                "장흥관광지 제5주차장(아시나요)", "장흥관광지(노상)")

# 표준데이터 주차장명 → 양주도시공사 통합주차포털(parking.yjuc.or.kr) 주차장명.
#   포털 ‘주차장검색’ 목록(2026-11-17 조회, 24곳 — 공영 18·부설 6)과 이름을 맞춘다.
YJ_PORTAL_NAMES = {
    "고읍저류지 공영주차장": "고읍저류지",
    "광적 공영주차장": "광적(타워)",
    "덕계공원 공영주차장": "덕계공원주차타워",
    "덕계역(1) 공영주차장": "덕계역(1)",
    "덕계역(2) 공영주차장": "덕계역(2)",
    "덕계역(3) 공영주차장": "덕계역(3)",
    "덕정역 공영주차장": "덕정역",
    "화물자동차 공영주차장": "덕정화물자동차",
    "옥정(2) 공영주차장": "옥정(2)",
    "옥정(3) 공영주차장": "옥정(3)",
    "마장호수 공영주차장": "마장호수편의시설",
    "기산저수지(1) 공영주차장": "기산저수지(1)",
    "기산저수지(2) 공영주차장": "기산저수지(2)",
    "장흥관광지 제1주차장(하천변)": "장흥관광지(1)",
    "장흥관광지 제2주차장(장흥관광지)": "장흥관광지(2)",
    "장흥관광지 제4주차장(선비촌)": "장흥관광지(7)",
    "광적가납 공영주차장": "광적가납",
}

# 양주도시공사 ‘공영주차장’ 안내(2026.10.31. 기준)의 주차면수 — 포털·표준데이터와 다른 곳이 있다.
#   (이름: 공단 홈페이지 면수) 화물자동차 92면은 화물 66면 + 일반 26면이다.
YJ_CORP_SPACES = {
    "마장호수 공영주차장": 149, "광적 공영주차장": 74, "덕정주공상가 공영주차장": 31,
    "화물자동차 공영주차장": 92, "광적가납 공영주차장": 31, "고읍저류지 공영주차장": 145,
    "덕계공원 공영주차장": 145, "옥정(2) 공영주차장": 34, "옥정(3) 공영주차장": 25,
    "덕계역(1) 공영주차장": 88, "덕계역(2) 공영주차장": 57, "덕계역(3) 공영주차장": 77,
    "덕정역 공영주차장": 68, "장흥관광지 제1주차장(하천변)": 40,
    "장흥관광지 제2주차장(장흥관광지)": 106, "장흥관광지 제4주차장(선비촌)": 40,
    "기산저수지(1) 공영주차장": 45, "기산저수지(2) 공영주차장": 77,
}

# 양주시 ‘주차요금의 감면’(조례 제7조)과 양주도시공사의 주요 할인안내(2026.10.31. 기준) —
#   둘 이상 해당하면 감면율이 높은 하나만 적용하고, 감면대상 차량은 증빙서류를 낸 때부터 적용한다.
YJ_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·장애인·다자녀 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": ("경형자동차, 저공해자동차 표지 부착차량, 환경친화적 자동차, 장애인 자가운전·동승 차량, "
              "경기 I-Plus 카드 등 다자녀증명 제시자, 승용차요일제 표지 차량(참여 요일 제외), "
              "양주시 장기등 기증 예우대상자, 양주시민대상 수상자(수상일부터 2년), "
              "병역명문가증 소지자, 임산부·미취학아동 동승 차량, "
              "환승주차장(덕계역1·2·3·덕정역)에서 30분 이내 철도 환승 차량")},
    {"label": "전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": ("전기자동차 충전시설이 설치된 공영주차장을 이용하는 전기자동차 — 최초 2시간 면제, "
              "이후 발생요금 50% 감면(충전시설이 없는 주차장은 50%만 감면)")},
    {"label": "국가유공자 등 4시간 면제 후 50%", "rate": 0.5, "exempt_min": 240,
     "note": ("국가유공자·유족·가족, 5·18민주화운동 관련자·유족, 고엽제후유증환자·고엽제후유의증환자·"
              "고엽제후유증 2세환자가 자가운전하는 차량(상이자 동승 포함) — 최초 4시간 면제, "
              "4시간 초과분 50% 감면")},
    {"label": "긴급·선거참여·모범납세자 100%", "rate": 1.0, "exempt_min": 0,
     "note": ("긴급자동차, 투표 당일 1회 선거참여자(투표참여 확인증), 공무수행 중인 관용차량, "
              "국세청장·경기도지사·시장이 교부한 모범·유공·성실납세자 표지 부착 차량(유효기간 내)")},
]


def yj_dong_of(text: str):
    """주소에서 양주시 법정동·읍·면을 뽑는다 — ‘경기도 양주시 {동·읍·면} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "양주시" and parts[2] in YJ_DONGS:
        return parts[2]
    t = re.sub(r"\s", "", text or "")
    for d in sorted(YJ_DONGS, key=len, reverse=True):
        if d in t:
            return d
    return None


def yj_fee(grade: int = 1, pay: str = "", *, monthly=None):
    """양주시 공영주차장 시간 요금 → 사이트 공통 fee 객체(유료, 1일 주차권이 상한).

    별표1은 ‘최초 30분 이내 기본요금 600원(1급지) → 10분당 200원’이고, 입차 후 최초 10분은
    무료다(별표1 단서). 그래서 free_min=10, base 30분 600원, 10분 단위 200원으로 넣는다.
    """
    t = YJ_FEES[grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "std_grade": None,
        "base_min": YJ_BASE_MIN, "base_fee": t["base"],
        "unit_min": YJ_UNIT_MIN, "unit_fee": t["unit"],
        "steps": None, "steps_label": None,
        "free_min": YJ_FREE_MIN, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 별표1 1일 주차권(선납)",
        "daily_hours": 24, "daily_fee": t["day"],
        "prepaid_day": t["day"], "prepaid_weekend": None,
        "monthly": t["month"] if monthly is None else monthly,
        "monthly_day": None, "monthly_night": None,
        "monthly_all": t["month"] if monthly is None else monthly, "monthly_label": None,
        "pay": pay,
        "basis": f"「양주시 주차장 조례」 별표1 {grade}급지 · 양주도시공사 요금안내",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def yj_flat_fee(pay: str = "신용카드"):
    """장흥관광지 공영주차장의 당일 정액(소·중형 2,000원) 요금 객체."""
    return {
        # 급지 요금이 아니라 당일 정액이라 급지를 두지 않는다.
        "type": "유료", "raw_type": "혼합", "mixed": True,
        "grade": None, "std_grade": None,
        "base_min": 1440, "base_fee": YJ_FLAT_DAY,
        "unit_min": 1440, "unit_fee": YJ_FLAT_DAY, "steps": None,
        "free_min": None, "deduct_min": YJ_FREE_MIN,
        "cap_fee": None, "cap_src": "양주도시공사 장흥관광지 요금(당일)",
        "daily_hours": 24, "daily_fee": YJ_FLAT_DAY,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": pay,
        "basis": "양주도시공사 장흥관광지 공영주차장 요금(경차 1,000·소·중형 2,000·대형 3,000원)",
        "category": "tourist", "portal_free_now": False, "flat_day": True,
        "ticket_only": False, "std": None,
    }


def yj_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def load_yangju_portal():
    """양주도시공사 통합주차포털 주차장 목록 스냅샷 → {포털 이름: 항목}."""
    if not YJ_PORTAL_JSON.exists():
        return {}
    raw = json.loads(YJ_PORTAL_JSON.read_text())
    out = {}
    for d in raw.get("parkingList") or []:
        name = (d.get("PARKING_NM") or "").strip()
        if name:
            out[name] = d
    return out


def yj_window(start, end):
    """포털의 ‘시작~종료’ 문자열 → hours 셀.

    포털은 요금을 받지 않는 요일에 00:00~00:00 을 넣는다. 그 값은 ‘그날은 요금을 받지
    않는다(무료 개방)’는 뜻이라, 부르는 쪽에서 free_days 로 따로 표시한다.
    """
    s, e = parse_hm(start), parse_hm(end)
    if s is None or e is None or (s == 0 and e == 0):
        return None
    if s == 0 and e == 23 * 60 + 59:
        return {"open": True, "start": 0, "end": 24 * 60, "24h": True, "listed": True,
                "raw": ["00:00", "24:00"]}
    return {"open": True, "start": s, "end": e, "24h": False, "listed": True,
            "raw": [fmt_time(start), fmt_time(end)]}


def build_yangju():
    """양주시 공영주차장을 표준데이터 + 양주시 주차장 조례 별표1 + 양주도시공사 자료로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 양주시 범위를 벗어난 행은 제외(껍데기 행).
      · 이 사이트는 공영주차장 파인더라 민영 주차장(40행, 상가·건물·코레일네트웍스 등)은 넣지 않는다.
      · 양주시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동·읍·면만 만든다.
    요금은 조례 별표1(1급지 30분 600원·10분당 200원·1일 7,000원·월 60,000원, 최초 10분 무료)을
    쓰고, 운영시간은 양주도시공사 통합주차포털의 주차장별 시간으로 바로잡는다(표준데이터는 모두
    09:00~23:59 로만 등록). 포털이 요금을 받지 않는 요일(00:00~00:00)은 조례 별표1 비고3
    (야간·주말·공휴일 무료)에 따라 무료 개방으로 표시한다.
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == YJ_PROVIDER]
    portal = load_yangju_portal()
    lots, excluded, merged, private = [], [], [], []
    hour_fixed, space_diff, note_fixed, reclassified, month_diff = [], [], [], [], []
    portal_used = set()

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                src="표준데이터", notice=None, tel="", mgmt="", lat=None, lng=None,
                base_date="", free_days=None, free_note=None, kind="공영"):
        street = ptype == "노상"
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": src,
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "양주시",
            "dong": dong,
            "dong_src": "지번주소" if r and yj_dong_of((r.get("소재지지번주소") or "")) else
                        ("도로명주소" if r and yj_dong_of((r.get("소재지도로명주소") or "")) else
                         ("공단 안내" if (not r and dong) else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else kind,
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "양주도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" and not fee.get("flat_day") else None,
            "city": "양주시",
            "city_slug": "yangju",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        gubun = (r.get("주차장구분") or "").strip()
        if gubun == "민영":
            # 공영주차장 파인더라 민영 주차장은 넣지 않는다(건물·상가·코레일네트웍스 등 40곳).
            private.append({"name": name or "(이름 없음)", "reason": "민영 주차장(공영 아님)"})
            continue
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not (YJ_BBOX[0] <= lat <= YJ_BBOX[1] and YJ_BBOX[2] <= lng <= YJ_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = yj_dong_of(jibun) or yj_dong_of(road)
        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        free_days = {"sat": False, "sun": False}
        notice_bits = []
        pay = (r.get("결제방법") or "").strip()
        fee_type = (r.get("요금정보") or "").strip()

        # 장흥관광지 공영주차장 — 급지 요금이 아니라 당일 정액(2,000원)이다.
        if name in YJ_FLAT_LOTS:
            fee = yj_flat_fee(pay="신용카드")
            portal_name = YJ_PORTAL_NAMES.get(name)
            p = portal.get(portal_name) if portal_name else None
            if p:
                portal_used.add(portal_name)
                wk = yj_window(p.get("WDAYS_START_TM"), p.get("WDAYS_END_TM"))
                we = yj_window(p.get("WEND_START_TM"), p.get("WEND_END_TM"))
                he = yj_window(p.get("HEND_START_TM"), p.get("HEND_END_TM"))
                if wk:
                    win = {"weekday": wk, "sat": we or dict(wk), "sun": he or dict(wk)}
                    oper = {"weekday": True, "sat": True, "sun": True}
                    hour_fixed.append(f"{name}: 표준데이터 09:00~23:59 → 포털 운영시간 "
                                      f"{wk['raw'][0]}~{wk['raw'][1]}(토·일·공휴일 포함)")
            notice_bits.append(
                "양주도시공사가 운영하는 장흥관광지 공영주차장입니다 — 급지 요금이 아니라 "
                f"당일 정액이고, 경차 {YJ_FLAT_SHORT:,}원·소·중형차 {YJ_FLAT_DAY:,}원·"
                f"대형차(2.5톤 이상 화물·16인승 이상 승합) {YJ_FLAT_LONG:,}원입니다. "
                "무인정산기 카드결제만 되고 현금은 받지 않습니다")
            if name in ("장흥관광지 제3주차장(효편의점)", "장흥관광지 제5주차장(아시나요)"):
                notice_bits.append(
                    "양주도시공사 홈페이지는 장흥관광지 제1·2·7 공영주차장만 따로 안내하고, "
                    "표준데이터에는 제1~5주차장과 노상 구간이 등록되어 있습니다 — 같은 관광지 "
                    "주차장으로 보아 당일 정액을 적용했습니다")
        else:
            paid = fee_type in ("유료", "혼합")
            grade = to_int(r.get("급지구분")) or 1
            grade = min(max(grade, 1), 2)     # 조례 별표1은 1·2급지다
            portal_name = YJ_PORTAL_NAMES.get(name)
            p = portal.get(portal_name) if portal_name else None
            if p and not paid and (to_int(p.get("DFLT_AMT")) or 0) > 0:
                # 표준데이터가 ‘무료’로 등록한 덕정역 공영주차장을 공단·포털(유료 운영)에 맞춘다.
                paid = True
                reclassified.append(
                    f"{name}: 표준데이터 요금정보 ‘{fee_type or '무료'}’ ↔ 양주도시공사가 "
                    f"2026-05-04부터 유료로 운영(포털 요금 10분 무료·30분 600원·1일 7,000원) — 유료로 바로잡음")
                notice_bits.append(
                    "2025년 10월부터 무료로 시범 운영하다 2026년 5월 4일부터 평일 주간에만 "
                    "유료로 전환했습니다 — 평일 08:00~20:00에만 요금을 받고 야간·주말·공휴일은 "
                    "무료로 개방하며, 덕정역 환승객은 50% 할인이 자동 적용됩니다"
                    "(양주도시공사 공지 2026-04-29·신아일보 2026-05-07). 표준데이터에는 아직 무료로 등록")
            if paid:
                monthly = YJ_FEES[grade]["month"]
                fee = yj_fee(grade, pay=pay, monthly=monthly)
                fee["std_grade"] = to_int(r.get("급지구분"))
                daily_std = to_int(r.get("1일주차권요금"))
                month_std = to_int(r.get("월정기권요금"))
                fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                              "base_fee": to_int(r.get("주차기본요금")),
                              "unit_min": to_int(r.get("추가단위시간")),
                              "unit_fee": to_int(r.get("추가단위요금")),
                              "day": daily_std, "monthly": month_std}
                if daily_std and daily_std != YJ_FEES[grade]["day"]:
                    note_fixed.append(f"{name}: 표준데이터 1일 주차권 {daily_std:,}원 ↔ "
                                      f"별표1 {grade}급지 {YJ_FEES[grade]['day']:,}원")
                if p and month_std and not to_int(p.get("PERIOD_TICKET_AMT")):
                    # 포털에 정기권 판매가 없는 주차장 — 조례 요금은 있으나 운영하지 않는다.
                    month_diff.append(f"{name}: 표준데이터 월 정기권 {month_std or 0:,}원 ↔ "
                                      f"포털 정기권 판매 없음(공단 안내 정기권 시행 주차장 아님)")
            else:
                fee = yj_free_fee()

            if p:
                portal_used.add(portal_name)
                wk = yj_window(p.get("WDAYS_START_TM"), p.get("WDAYS_END_TM"))
                we = yj_window(p.get("WEND_START_TM"), p.get("WEND_END_TM"))
                he = yj_window(p.get("HEND_START_TM"), p.get("HEND_END_TM"))
                if wk:
                    # 포털은 요금을 받지 않는 요일에 00:00~00:00 을 넣는다 — 무료 개방.
                    sat_free = we is None
                    sun_free = he is None
                    win = {"weekday": wk,
                           "sat": (we or {"open": True, "start": 0, "end": 24 * 60, "24h": True,
                                          "listed": True, "raw": ["00:00", "24:00"]}),
                           "sun": (he or dict(we or {"open": True, "start": 0, "end": 24 * 60,
                                                    "24h": True, "listed": True,
                                                    "raw": ["00:00", "24:00"]}))}
                    oper = {"weekday": True, "sat": True, "sun": True}
                    free_days = {"sat": sat_free, "sun": sun_free}
                    hour_fixed.append(
                        f"{name}: 표준데이터 09:00~23:59 → 포털 평일 "
                        f"{wk['raw'][0]}~{wk['raw'][1]}"
                        + ("" if sat_free else f" · 토 {we['raw'][0]}~{we['raw'][1]}")
                        + ("" if sun_free else f" · 공휴일 {he['raw'][0]}~{he['raw'][1]}"))
                if paid and fee["type"] == "유료":
                    when = ("평일 " + f"{wk['raw'][0]}~{wk['raw'][1]}" if wk else "평일 주간")
                    if free_days["sat"] or free_days["sun"]:
                        free_note = ("야간과 토요일·일요일·공휴일은 무료로 개방합니다 — "
                                     f"{when}에만 요금을 받습니다(조례 별표1 비고2·3)")
                    else:
                        free_note = ("야간은 무료로 개방합니다 — "
                                     f"{when}과 주말·공휴일에는 요금을 받습니다(조례 별표1 비고2·3)")
            elif paid:
                free_note = ("야간(20:00~08:00)과 토요일·일요일·공휴일은 무료로 개방합니다 — "
                             "주간(08:00~20:00)에만 요금을 받습니다(조례 별표1 비고2·3)")
            else:
                free_note = None

            if not paid:
                free_days = {"sat": False, "sun": False}

        sp = YJ_CORP_SPACES.get(name)
        psp = to_int(p.get("CELL_CNT")) if p else None
        if (sp and sp != spaces) or (psp and psp != spaces):
            diff = f"{name}: 표준데이터 {spaces}면"
            if psp and psp != spaces:
                diff += f" ↔ 포털 {psp}면"
            if sp and sp != spaces and sp != psp:
                diff += f" ↔ 공단 {sp}면"
            space_diff.append(diff)
            bits = [f"표준데이터 등록면수 {spaces}면"]
            if psp and psp != spaces:
                bits.append(f"포털 {psp}면")
            if sp and sp != spaces:
                bits.append(f"양주도시공사 안내 {sp}면")
            notice_bits.append("면수는 자료마다 다릅니다 — " + " · ".join(bits)
                               + " (이 사이트는 등록면수를 씁니다)")
        if name == "화물자동차 공영주차장":
            notice_bits.append("양주도시공사 안내의 92면은 화물 66면과 일반 26면을 합한 값이고, "
                               "표준데이터에는 일반면 26면만 등록되어 있습니다")
        if name == "광적가납 공영주차장":
            notice_bits.append("양주도시공사가 화물·승합·건설기계 정기권 주차장으로 운영합니다"
                               "(24시간, 정기권은 통합예약서비스에서 신청)")
        if name == "고읍(4) 공영주차장":
            notice_bits.append("같은 부지(광사동 711)의 46면은 카라반·캠핑트레일러 전용 "
                               "‘고읍 캠핑카’ 정기권 구역으로 양주도시공사가 운영합니다")
        if name == "덕정 교각(1) 임시 공영주차장":
            notice_bits.append("양주시청 교각(마전동 93-1) 부설주차장과 같은 곳으로 보이며, "
                               "양주도시공사는 08:00~18:00 운영으로 안내합니다")
        if street:
            notice_bits.append("노상주차장은 조례 별표1 1급지 요금(30분 600원·10분당 200원·"
                               "1일 7,000원)을 적용할 수 있고, 표준데이터에는 요금 구분이 "
                               f"‘{fee_type or '무료'}’로 등록되어 있습니다")
        if name == "덕정주공상가 공영주차장":
            notice_bits.append("양주도시공사 홈페이지는 31면·운영시간 없음(24시간 개방)으로 "
                               "안내합니다")

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=" · ".join(notice_bits) or None,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "양주도시공사"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    unused = sorted(set(portal) - portal_used)

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"yj-{i:03d}" if l["list_mode"] == "card" else f"yj-s{i:03d}"

    quality = check_quality_yangju(rows_all, rows_city, lots, excluded, merged, private,
                                   hour_fixed, space_diff, note_fixed, reclassified,
                                   month_diff, unused)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": _snapshot_time(YJ_PORTAL_JSON).strftime("%Y-%m-%d %H:%M")
                           if YJ_PORTAL_JSON.exists() else NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "양주시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-15",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-17 16:05 (KST)",
                    "note": ("경기도 양주시가 등록한 89행(노외 78·노상 11)을 읽었다. 이 가운데 "
                             "민영 40행(상가·건물·코레일네트웍스 등)은 공영주차장 파인더라 싣지 않고, "
                             "공영 49행(노외 38·노상 11)을 이름·주소·구획수·급지·운영요일·좌표·전화·"
                             "관리번호·결제방법 출처로 썼다. 운영시간은 모든 행이 09:00~23:59 로만 "
                             "등록되어 있어 양주도시공사 포털의 주차장별 시간으로 바로잡았다."),
                },
                {
                    "id": "ordinance",
                    "name": "양주시 주차장 조례 [별표 1] 공영주차장 주차요금표",
                    "org": "양주시청 차량관리과(031-8082-6623) · 양주도시공사 통합주차관제센터(031-828-9796~8)",
                    "url": YJ_ORDINANCE_URL,
                    "file": YJ_ORD_ANNEX_TXT.name if YJ_ORD_ANNEX_TXT.exists() else YJ_ORD_TXT.name,
                    "sha256": (sha256(YJ_ORD_ANNEX_TXT) if YJ_ORD_ANNEX_TXT.exists()
                               else sha256(YJ_ORD_TXT) if YJ_ORD_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": YJ_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(YJ_ORD_TXT),
                    "note": ("국가법령정보센터 별표/서식 HWP(yangju.law.go.kr_주차장조례_별표1_20261117.hwp)에서 "
                             "표를 읽어 정리본(txt)을 두었다. 1급지 최초 30분 이내 600원·10분당 200원·1일 주차권(선납) 7,000원·"
                             "월 정기권(선납) 60,000원, 2급지 300·100·3,000·40,000원, 거주자 전용 "
                             "주차구획 주간·야간 20,000원·전일 30,000원을 별표/서식 HWP에서 읽었다. "
                             "같은 별표가 ‘최초 30분 미만은 기본요금, 다만 입차 후 최초 10분까지는 "
                             "무료’, 운영시간 주간 08:00~20:00·야간 20:00~익일 08:00(비고2), "
                             "‘야간·주말·공휴일 요금은 무료’(비고3), 1급지(국도·지방도·시도 500m "
                             "이내)·2급지 구분(비고4), 차량 크기별 2배·3배(비고7)를 정하고 있다."),
                },
                {
                    "id": "corp", "name": "양주도시공사 공영주차장 시설·이용안내(요금안내·주요 할인안내)",
                    "org": "양주도시공사 통합주차관제센터(031-828-9796~8)",
                    "url": YJ_CORP_URL,
                    "file": YJ_CORP_TXT.name if YJ_CORP_TXT.exists() else None,
                    "sha256": sha256(YJ_CORP_TXT) if YJ_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "2026-10-31 기준",
                    "rows_total": 19, "fetched_at": _sync_time(YJ_CORP_TXT),
                    "note": ("공영주차장 19곳(노외 18·노상 1)과 부설주차장 5곳의 평일·주말 운영시간과 "
                             "면수를 확인했다 — 공영주차장 요금은 최초 10분 무료·10분초과 30분이내 "
                             "600원·30분초과 10분당 200원·일일권(선납) 7,000원·월정기권(선납) "
                             "60,000원이고, 장흥관광지 1·2·7은 당일 경차 1,000·소·중형 2,000·"
                             "대형 3,000원(카드결제만)이다. 할인은 국가유공자 등 4시간 면제 뒤 "
                             "50%, 전기차 2시간 면제 뒤 50%, 경차·저공해·장애인·다자녀 등 50%, "
                             "긴급·선거참여 무료로 안내한다."),
                },
                {
                    "id": "portal", "name": "양주도시공사 통합주차포털 주차장 목록(주차장검색)",
                    "org": "양주도시공사 통합주차관제센터(031-828-9797~8)",
                    "url": YJ_PORTAL_URL,
                    "file": YJ_PORTAL_JSON.name if YJ_PORTAL_JSON.exists() else None,
                    "sha256": sha256(YJ_PORTAL_JSON) if YJ_PORTAL_JSON.exists() else None,
                    "license": "공공기관 공개 웹페이지(참고용)", "base_date": "조회 2026-11-17",
                    "rows_total": 24, "fetched_at": _sync_time(YJ_PORTAL_JSON),
                    "note": ("공영 18곳·부설 6곳의 급지·면수·요금(무료시간 10분·기본 30분 600원·"
                             "추가 10분 200원·일 최대 7,000원·월 60,000원)·평일/토요일/공휴일 "
                             "운영시간을 주차장별로 읽어 표준데이터의 24시간·09:00~23:59 등록을 "
                             "바로잡았다. 요금을 받지 않는 요일은 00:00~00:00 으로 등록되어 있어 "
                             "조례 별표1 비고3에 따라 무료 개방으로 표시했다."),
                },
                {
                    "id": "news", "name": "신아일보 — 양주, 덕정역 공영주차장 유료 전환 운영",
                    "org": "신아일보(2026-05-07 보도)", "url": YJ_NEWS_URL,
                    "file": YJ_NEWS_TXT.name if YJ_NEWS_TXT.exists() else None,
                    "sha256": sha256(YJ_NEWS_TXT) if YJ_NEWS_TXT.exists() else None,
                    "license": "언론 보도(참고용)", "base_date": "2026-05-07",
                    "rows_total": None, "fetched_at": _sync_time(YJ_NEWS_TXT),
                    "note": ("덕정역 공영주차장(68면)이 2026-05-04부터 평일 08:00~20:00에만 "
                             "유료로 운영되고 야간·주말·공휴일은 무료로 개방한다는 것을 확인했다 — "
                             "최초 30분 600원·이후 10분당 200원·1일 7,000원, 덕정역 환승 50% 할인은 "
                             "정산 때 자동 차감. 표준데이터는 아직 무료로 등록되어 있다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in YJ_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "yangju_grade",
            "unit_min": YJ_UNIT_MIN,
            "base_min": YJ_BASE_MIN,
            "free_min": YJ_FREE_MIN,
            "applies": YJ_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "국도·지방도·시도로부터 500m 이내", "base": 600, "unit": 200,
                 "day": 7_000, "month": 60_000, "lots": 0},
                {"grade": 2, "where": "1급지 이외의 지역", "base": 300, "unit": 100,
                 "day": 3_000, "month": 40_000, "lots": 0},
            ],
            "resident": {"day": 20_000, "night": 20_000, "all": 30_000,
                         "day_hours": "09:00~19:00", "night_hours": "19:00~익일 09:00"},
            "flat": {"amount": YJ_FLAT_DAY, "short": YJ_FLAT_SHORT, "long": YJ_FLAT_LONG,
                     "lots": [l["name"] for l in lots if l["fee"].get("flat_day")]},
            "lots": [
                {"name": l["name"], "dong": l["dong"], "grade": l["fee"].get("grade"),
                 "free": l["fee"].get("free_min"), "day": l["fee"].get("daily_fee"),
                 "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "corp": {
                "paid_out": len([l for l in lots if l["fee"]["type"] == "유료"
                                 and l["ptype"] == "노외" and not l["fee"].get("flat_day")]),
                "flat": len([l for l in lots if l["fee"].get("flat_day")]),
                "free": len([l for l in lots if l["fee"]["type"] == "무료"]),
                "free_spaces": sum(l["spaces"] or 0 for l in lots if l["fee"]["type"] == "무료"),
                "corp_total": ("공영주차장 19곳(노외 18·노상 1)과 부설주차장 5곳"
                               "(공단 안내 2026.10.31. 기준)"),
            },
            "basis": ("「양주시 주차장 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({YJ_ORDINANCE_NOTE}) · 양주도시공사 요금안내(2026-10-31) · "
                      "통합주차포털 주차장별 요금(2026-11-17 조회)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["양주시"] | {
        "city": "양주시",
        "weekend_free_pages": False,
        "discounts": YJ_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "yangju_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_yangju(std_all, rows, lots, excluded, merged, private, hour_fixed, space_diff,
                         note_fixed, reclassified, month_diff, unused):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_양주시행수": len([r for r in rows if (r.get("주차장구분") or "").strip() == "공영"]),
        "원자료_전체행수": len(rows),
        "민영_제외": len(private),
        "민영_행": private,
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"].split("(")[0] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in lots
                                     if l["fee"].get("std_grade"))),
        "당일정액": [l["name"] for l in lots if l["fee"].get("flat_day")],
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "특기사항_보정": note_fixed,
        "요금구분_보정": reclassified,
        "정기권_차이": month_diff,
        "포털_미사용": unused,
        "감면_출처": "「양주시 주차장 조례」 제7조 · 양주도시공사 주요 할인안내(2026-10-31)",
        "무료시간_출처": "조례 별표1 단서(입차 후 최초 10분 무료)",
        "주말무료_출처": "조례 별표1 비고3(야간·주말·공휴일 요금 무료) · 포털 요일별 운영시간",
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len([l for l in lots if l["fee"]["type"] == "무료"]),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 포천시 (T-03 Phase 23)
PH_PROVIDER = "경기도 포천시"
# 포천시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
PH_DISTRICTS = [("포천시", "pocheon")]
PH_BBOX = (37.70, 38.25, 127.05, 127.50)   # 포천시 대략 경계(좌표 점검용)
# 포천시 법정동·읍·면 — 주소의 ‘경기도 포천시 ○○동|○○읍|○○면 번지’ 세 번째 낱말을 쓴다.
#   포천시는 1읍(소흘읍) 11면(군내·내촌·가산·신북·창수·영중·일동·이동·영북·관인·화현)과
#   포천동·선단동 2개 행정동(법정동 신읍동·선단동 등)으로 이루어진다.
PH_UNIT_SUFFIX = ("읍", "면", "동")
# 표준데이터에 실제로 주소가 올라온 지역(품질 리포트의 동별 집계와 같은 값이 된다).

PH_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2095709"
                    "&gubun=ELIS&conDatGubunCd=1")
PH_CORP_URL = "https://www.pcuc.kr/contents/99"
PH_MONTH_URL = "https://www.pcuc.kr/contents/101"
PH_CITY_URL = "https://www.pocheon.go.kr/www/contents.do?key=4280"
PH_NEWS_URL = "https://www.kihoilbo.co.kr/news/articleView.html?idxno=1122252"
PH_ORD_ANNEX1_TXT = RAW / "pocheon.law.go.kr_주차장조례_별표1_20261117.txt"
PH_ORD_ANNEX1_HWP = RAW / "pocheon.law.go.kr_주차장조례_별표1_20261117.hwp"
PH_ORD_ANNEX2_TXT = RAW / "pocheon.law.go.kr_주차장조례_별표2_20261117.txt"
PH_ORD_ANNEX2_HWP = RAW / "pocheon.law.go.kr_주차장조례_별표2_20261117.hwp"
PH_CORP_TXT = RAW / "pcuc.kr_공영주차장_20261117.txt"
PH_MONTH_TXT = RAW / "pcuc.kr_월정기주차권_20261117.txt"
PH_CITY_TXT = RAW / "pocheon.go.kr_교통주차시설_20261117.txt"
PH_NEWS_TXT = RAW / "kihoilbo.co.kr_포천공영주차장_요금정상화_20261117.txt"
PH_ORDINANCE_NOTE = ("시행 2025-12-22 · 경기도포천시조례 제1827호(일부개정) · "
                     "별표1 〈개정 2025.11.20.〉")
PH_BASE_MIN = 5
PH_UNIT_MIN = 10
PH_FREE_MIN = 5

# 포천시 공영주차장 요금 — 「포천시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 요금표
#   (시행 2025-12-22, 경기도포천시조례 제1827호. 별표/서식 HWP에서 표를 읽음).
#   · 노상: 1급지 10분당 200원·1일 주차요금(선납) 7,000원·월 정기권(선납) 70,000원
#           2급지 100원·4,000원·40,000원
#   · 노외: 1급지 10분당 200원·1일 주차권 7,000원·월 정기권(선납) 40,000원
#           2급지 100원·4,000원·30,000원
#   · 노상·노외 모두 ‘최초 5분’은 무료(병합 셀), 5분이 지나면 10분 단위로 요금이 붙는다.
#   · 비고3: 09:00~18:00이 주간, 나머지는 야간. 비고4: 1급지 = 도시지역 중 주거·상업·공업지역,
#     2급지 = 그 밖의 지역. 비고5: 토·일요일·공휴일과 야간은 무료 원칙(수요가 많은 곳은 유료 가능).
#     비고6: 점심시간(11:30~13:30) 동안 유료 노상주차장 무료.
#     비고7: 중형 승합·화물 2배, 대형 승합·화물·건설기계 3배.
PH_FEES = {
    (1, "노상"): {"unit": 200, "day": 7_000, "month": 70_000},
    (1, "노외"): {"unit": 200, "day": 7_000, "month": 40_000},
    (2, "노상"): {"unit": 100, "day": 4_000, "month": 40_000},
    (2, "노외"): {"unit": 100, "day": 4_000, "month": 30_000},
}
# 포천도시공사가 요금을 받는 시간 — 두 요금안내 표 모두 ‘운영시간 09:00~18:00,
#   운영시간 외 무료 개방, 토·일·법정공휴일 무료 개방’이다.
PH_PAID_START = 9 * 60
PH_PAID_END = 18 * 60
PH_LUNCH_FREE = (11 * 60 + 30, 13 * 60 + 30)   # 유료 노상주차장 점심시간 무료(별표1 비고6)
# 포천도시공사가 따로 안내하는 주차장별 면수(2026-11-17 조회) — 표준데이터와 다른 곳이 있다.
PH_CORP_SPACES = {
    "송우로 제1주차장": 108, "송우로 제2주차장": 58, "송우로 제3주차장": 27,
}
# 포천도시공사 노상주차장 안내의 구간·면수(2026-11-17 조회) — 표준데이터는 지역별로 묶어 등록했다.
#   신읍동은 행정동 포천동의 법정동이라 포천동 구간(237면·15구간)으로 잇는다.
PH_CORP_STREET = {
    "소흘읍": (117, 5, "소흘읍"), "일동면": (130, 5, "일동면"), "신읍동": (237, 15, "포천동"),
}
# 표준데이터가 ‘무료’로 등록했지만 포천도시공사가 유료로 운영하는 주차장.
#   2025-01-01부터 코로나19 한시 감면을 끝내고 정상 요금을 받는다(기호일보 2024-12-04 보도,
#   포천도시공사 노외주차장 요금안내) — 시청사 부설·송우로 제1·2·3·소흘읍·포천동·일동면.
PH_RECLASSIFIED = {"송우로 제3주차장"}

# 포천시 주차요금 감면 — 「포천시 주차장 설치 및 관리 조례」 [별표 2](제3조제3항 관련).
#   감면은 중복 적용하지 않고(제3조③), 증빙서류를 낸 때부터 적용한다.
PH_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "경차·저공해·경로우대·병역명문가 50%", "rate": 0.5, "exempt_min": 60,
     "note": ("장애인등록증·복지카드 소지자, 전기차 등(본인 소유 비사업용 자동차 직접 운전), "
              "경형자동차(1,000cc 미만), 저공해자동차표지 부착 차량, 만 70세 이상 경로우대, "
              "포천시 우수자원봉사자증 소지차량, 병역명문가 예우대상자 차량, 투표확인증 소지자"
              "(투표 당일 1회) — 최초 1시간 면제, 1시간 초과분 50% 감면")},
    {"label": "다자녀 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": ("「포천시 인구정책 추진 및 지원에 관한 조례」에 따른 다자녀가정이 모바일 앱카드·"
              "경기i-PLUS카드를 제시하거나 경기도 내 거주 다자녀가정 증명서를 제시하는 경우 — "
              "최초 2시간 면제, 2시간 초과분 50% 감면")},
    {"label": "국가유공자 등 4시간 면제 후 50%", "rate": 0.5, "exempt_min": 240,
     "note": ("국가유공자·독립유공자·참전유공자·고엽제후유의증 등 환자·5·18민주유공자·"
              "특수임무유공자·의사상자·국군포로(억류지출신 포로가족·등록포로) — 최초 4시간 면제, "
              "4시간 초과분 50% 감면")},
    {"label": "긴급·관용·임산부·성실납세자 등 100%", "rate": 1.0, "exempt_min": 0,
     "note": ("국가·지방자치단체 공무수행(관용) 자동차와 외교사절 차량, 긴급자동차, 성실납세증 "
              "표지 부착 차량(1년), 임산부가 운전하거나 동승한 차량, 이·통장·새마을지도자·"
              "적십자봉사자·주민자치(회) 위원, 설날·추석 연휴 기간")},
]


def ph_dong_of(text: str):
    """주소에서 포천시 법정동·읍·면을 뽑는다 — ‘경기도 포천시 {읍·면·동} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "포천시":
        cand = parts[2]
        if cand.endswith("읍") or cand.endswith("면") or cand.endswith("동"):
            if not cand.endswith(("로동", "가동")):
                return cand
    return None


def ph_fee(ptype: str = "노외", grade: int = 1, pay: str = "", *,
           monthly=None, daily=0, month_std=0):
    """포천시 공영주차장 시간 요금 → 사이트 공통 fee 객체(유료, 1일 주차요금이 상한).

    별표1은 ‘최초 5분 무료 → 5분이 지나면 10분당 200원(1급지)’이다. 그래서 free_min=5,
    base 5분 0원, 10분 단위 200원으로 넣는다(5분까지 0원, 6~15분 200원, 16~25분 400원).
    """
    t = PH_FEES[(grade, ptype)]
    month = t["month"] if monthly is None else monthly
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "std_grade": None,
        "base_min": PH_BASE_MIN, "base_fee": 0,
        "unit_min": PH_UNIT_MIN, "unit_fee": t["unit"],
        "steps": None, "steps_label": None,
        "free_min": PH_FREE_MIN, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 별표1 1일 주차요금(선납)",
        "daily_hours": None, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": month, "monthly_day": None, "monthly_night": None,
        "monthly_all": month, "monthly_label": None,
        "pay": pay,
        "basis": (f"「포천시 주차장 설치 및 관리 조례」 별표1 {grade}급지 {ptype} "
                  f"(최초 {PH_FREE_MIN}분 무료 · {PH_UNIT_MIN}분당 {t['unit']:,}원 · "
                  f"1일 {t['day']:,}원)"),
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def ph_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def ph_hm(m: int) -> str:
    """분 단위 값 → ‘09:00’ 꼴 표기."""
    h, mi = divmod(int(m), 60)
    return f"{h:02d}:{mi:02d}"


def ph_window(start=PH_PAID_START, end=PH_PAID_END):
    """요금을 받는 시간(09:00~18:00)을 hours 셀 모양으로 만든다."""
    return {"open": True, "start": start, "end": end, "24h": False, "listed": True,
            "raw": [ph_hm(start), ph_hm(end)]}


def build_pocheon():
    """포천시 공영주차장을 표준데이터 + 포천시 조례 별표1·2 + 포천도시공사 자료로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 포천시 범위를 벗어난 행은 제외(껍데기 행).
      · 표준데이터 82행은 모두 공영(민영 등록 없음)이라 민영 제외는 일어나지 않는다.
      · 포천시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동·읍·면만 만든다.
    요금은 조례 별표1(최초 5분 무료 → 10분당 200원, 1일 7,000원, 월 노상 70,000원·노외 40,000원)을
    쓰고, 운영시간은 포천도시공사 요금안내의 ‘09:00~18:00, 운영시간 외 무료 개방, 토·일·법정공휴일
    무료 개방’으로 정리한다(표준데이터는 유료 행도 00:00~23:59로 등록되어 있다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == PH_PROVIDER]
    lots, excluded, merged = [], [], []
    hour_fixed, space_diff, note_fixed, reclassified, month_diff = [], [], [], [], []
    lunch_street, five_day = [], []

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                notice=None, tel="", mgmt="", lat=None, lng=None, base_date="",
                free_days=None, free_note=None):
        street = ptype == "노상"
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "포천시",
            "dong": dong,
            "dong_src": ("지번주소" if r and ph_dong_of((r.get("소재지지번주소") or "")) else
                         ("도로명주소" if r and ph_dong_of((r.get("소재지도로명주소") or "")) else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "포천도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": fee["unit_fee"] if fee["type"] == "유료" else None,
            "city": "포천시",
            "city_slug": "pocheon",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        gubun = (r.get("주차장구분") or "").strip()
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if gubun == "민영":
            # 포천시는 표준데이터에 민영 등록이 없지만, 다른 도시와 같은 규칙을 둔다.
            excluded.append({"name": name or "(이름 없음)", "reason": "민영 주차장(공영 아님)"})
            continue
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not (PH_BBOX[0] <= lat <= PH_BBOX[1] and PH_BBOX[2] <= lng <= PH_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = ph_dong_of(jibun) or ph_dong_of(road)
        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        pay = (r.get("결제방법") or "").strip()
        fee_type = (r.get("요금정보") or "").strip()
        grade = to_int(r.get("급지구분")) or 1
        grade = min(max(grade, 1), 2)     # 조례 별표1은 1·2급지다
        notice_bits = []
        free_days = {"sat": False, "sun": False}
        free_note = None

        paid = fee_type in ("유료", "혼합") or name in PH_RECLASSIFIED
        if fee_type not in ("유료", "혼합") and name in PH_RECLASSIFIED:
            reclassified.append(
                f"{name}: 표준데이터 요금정보 ‘{fee_type or '무료'}’ ↔ 포천도시공사가 2025-01-01부터 "
                f"정상 요금으로 운영(노외 5분 무료·10분당 200원·1일 7,000원·월 40,000원) — 유료로 바로잡음")

        if paid:
            fee = ph_fee(ptype, grade, pay=pay)
            # 1일 주차요금·월 정기권은 조례 별표1 값이다. 표준데이터는 이 두 칸이 어긋나 있다
            #   (적용시간 칸에 7,000, 1일 주차권 칸에 70,000, 월정기권 칸은 비어 있음).
            daily_std = to_int(r.get("1일주차권요금")) or 0
            month_std = to_int(r.get("월정기권요금")) or 0
            applied_std = (r.get("1일주차권요금적용시간") or "").strip()
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                          "base_fee": to_int(r.get("주차기본요금")),
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily_std, "monthly": month_std}
            want_day, want_month = PH_FEES[(grade, ptype)]["day"], PH_FEES[(grade, ptype)]["month"]
            if (applied_std or daily_std or month_std) and \
                    (applied_std or daily_std != want_day or month_std != want_month):
                note_fixed.append(
                    f"{name}: 표준데이터 1일주차권요금적용시간 ‘{applied_std}’·1일주차권요금 "
                    f"{daily_std:,}원·월정기권요금 {month_std:,}원 ↔ 조례 별표1 {grade}급지 {ptype} "
                    f"1일 {want_day:,}원·월 {want_month:,}원(칸이 어긋나 있음)")
                month_diff.append(f"{name}: 표준데이터 월정기권 {month_std or 0:,}원 ↔ 별표1 "
                                  f"{ptype} {grade}급지 {want_month:,}원")
            # 요금은 09:00~18:00에만 받고 그 밖의 시간과 토·일·공휴일은 무료 개방이다.
            win = {"weekday": ph_window(), "sat": ph_window(), "sun": ph_window()}
            oper = {"weekday": True, "sat": True, "sun": True}
            free_days = {"sat": True, "sun": True}
            hour_fixed.append(
                f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~"
                f"{r.get('평일운영종료시각') or ''}({r.get('운영요일') or '평일'}) → 포천도시공사 "
                f"요금안내 09:00~18:00(운영시간 외·토·일·공휴일 무료 개방)")
            free_note = ("평일 09:00~18:00에만 요금을 받고, 18:00~익일 09:00과 토요일·일요일·"
                         "공휴일은 무료로 개방합니다(조례 별표1 비고3·5, 포천도시공사 요금안내)")
            if street:
                free_note += (f" · 점심시간({ph_hm(PH_LUNCH_FREE[0])}~"
                              f"{ph_hm(PH_LUNCH_FREE[1])})에는 무료입니다(비고6)")
                lunch_street.append(name)
            notice_bits.append(
                f"「포천시 주차장 설치 및 관리 조례」 별표1 {grade}급지 {ptype} 요금입니다 — "
                f"최초 {PH_FREE_MIN}분 무료, 그 뒤 {PH_UNIT_MIN}분당 "
                f"{PH_FEES[(grade, ptype)]['unit']:,}원, 1일 주차요금(선납) "
                f"{PH_FEES[(grade, ptype)]['day']:,}원, 월 정기권(선납) "
                f"{PH_FEES[(grade, ptype)]['month']:,}원")
            if (r.get("부제시행구분") or "").strip() == "5부제":
                five_day.append(name)
                notice_bits.append("승용차 5부제를 시행하는 구간입니다")
            if name in PH_RECLASSIFIED:
                notice_bits.append(
                    "포천도시공사가 2025년 1월 1일부터 코로나19 한시 감면을 끝내고 정상 요금을 "
                    "받습니다 — 공공데이터 표준데이터에는 아직 ‘무료’로 등록되어 있습니다")
            if name in PH_CORP_SPACES and PH_CORP_SPACES[name] != spaces:
                notice_bits.append(
                    f"표준데이터 등록면수는 {spaces}면이고, 포천도시공사 안내는 "
                    f"{PH_CORP_SPACES[name]}면입니다")
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 포천도시공사 "
                                  f"{PH_CORP_SPACES[name]}면")
        else:
            fee = ph_free_fee()
            free_days = {"sat": False, "sun": False}
            # 무료 주차장은 표준데이터의 운영시간을 그대로 쓴다(대부분 24시간).
            if name in PH_CORP_SPACES and PH_CORP_SPACES[name] != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 포천도시공사 "
                                  f"{PH_CORP_SPACES[name]}면")

        if street and dong in PH_CORP_STREET and paid:
            corp_spaces, corp_seg, corp_area = PH_CORP_STREET[dong]
            here = (f"{corp_area}(법정동 {dong})" if corp_area != dong else corp_area)
            notice_bits.append(
                f"포천도시공사는 {here} 노상주차장을 {corp_seg}개 구간 {corp_spaces}면으로 "
                f"나누어 안내합니다(‘{corp_area}1’~‘{corp_area}{corp_seg}’) — 표준데이터는 이 구간을 "
                f"한 줄로 묶어 등록했습니다")

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=" · ".join(notice_bits) or None,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "포천도시공사"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"ph-{i:03d}" if l["list_mode"] == "card" else f"ph-s{i:03d}"

    quality = check_quality_pocheon(rows_all, rows_city, lots, excluded, merged,
                                    hour_fixed, space_diff, note_fixed, reclassified,
                                    month_diff, lunch_street, five_day)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "포천시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-20",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-17 16:05 (KST)",
                    "note": ("경기도 포천시가 등록한 82행(노외 66·노상 16)을 읽었다. 모두 주차장구분이 "
                             "‘공영’이라 민영 주차장은 없다(공영주차장 파인더라 민영은 싣지 않는 규칙은 "
                             "그대로 두었다). 요금 구분은 유료 14행(노외 2·노상 12)과 무료 68행이지만, "
                             "노외 ‘송우로 제3주차장’은 포천도시공사가 2025-01-01부터 유료로 운영해 "
                             "유료로 바로잡았다. 주차구획수가 비어 있는 8행(용정산업단지 제1쌈지·"
                             "가채리 벚꽃길·구읍공원·탄동리·도평리 쌈지·양문리·감암리 파라뷰·"
                             "내촌면 내리)은 껍데기 행이라 제외했다."),
                },
                {
                    "id": "ordinance",
                    "name": "포천시 주차장 설치 및 관리 조례 [별표 1] 공영주차장 요금표 · [별표 2] 주차요금의 감면",
                    "org": "포천시청 교통행정과 · 포천도시공사 공공시설팀 주차관리(031-540-6305)",
                    "url": PH_ORDINANCE_URL,
                    "file": PH_ORD_ANNEX1_HWP.name if PH_ORD_ANNEX1_HWP.exists() else PH_ORD_ANNEX1_TXT.name,
                    "sha256": (sha256(PH_ORD_ANNEX1_HWP) if PH_ORD_ANNEX1_HWP.exists()
                               else sha256(PH_ORD_ANNEX1_TXT) if PH_ORD_ANNEX1_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": PH_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(PH_ORD_ANNEX1_TXT),
                    "note": ("국가법령정보센터 별표/서식 HWP를 내려받아 표 셀을 읽어 정리본(txt)을 "
                             "두었다. 노상 1급지 10분당 200원·1일 주차요금(선납) 7,000원·월 정기권"
                             "(선납) 70,000원, 노외 1급지 200·7,000·40,000원, 2급지 100·4,000·40,000원"
                             "(노외 30,000원)이고, 노상·노외 모두 ‘최초 5분’이 무료다(병합 셀). "
                             "비고3은 09:00~18:00을 주간, 비고5는 토·일·공휴일·야간 무료 원칙, "
                             "비고6은 점심시간(11:30~13:30) 유료 노상주차장 무료, 비고7은 차량 크기별 "
                             "2배·3배를 정한다. 별표2는 전액 면제·일부 면제(2시간)·50% 감면(4시간·"
                             "2시간·1시간 면제 뒤)·40%·30% 감면을 정한다."),
                },
                {
                    "id": "corp", "name": "포천도시공사 공영주차장 안내(노상주차장·노외주차장·감면 대상)",
                    "org": "포천도시공사 공공시설팀 주차관리(031-540-6305)",
                    "url": PH_CORP_URL,
                    "file": PH_CORP_TXT.name if PH_CORP_TXT.exists() else None,
                    "sha256": sha256(PH_CORP_TXT) if PH_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 25, "fetched_at": _sync_time(PH_CORP_TXT),
                    "note": ("노상주차장은 소흘읍·일동면·포천동 세 지역 25개 구간 484면, 노외주차장은 "
                             "송우로 제1·2·3 세 곳(108·58·27면)이다. 요금은 노상·노외 모두 5분 무료·"
                             "5분 이후 10분당 200원·선납 1일 7,000원이고, 월 정기권은 노상 70,000원·"
                             "노외 40,000원이다. 두 표 모두 ‘운영시간 09:00~18:00(운영시간 외 무료 "
                             "개방)’, ‘토·일·법정공휴일 무료 개방’을 적고 있어 요금 부과 시간과 "
                             "무료 개방을 이 값으로 정리했다. 감면은 조례 별표2를 그대로 싣고 "
                             "중복 시 감면율이 높은 하나만 적용한다고 안내한다."),
                },
                {
                    "id": "month", "name": "포천도시공사 월정기 주차권 안내(노외주차장)",
                    "org": "포천도시공사 공공시설팀 주차관리(031-540-6305~7)",
                    "url": PH_MONTH_URL,
                    "file": PH_MONTH_TXT.name if PH_MONTH_TXT.exists() else None,
                    "sha256": sha256(PH_MONTH_TXT) if PH_MONTH_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 3, "fetched_at": _sync_time(PH_MONTH_TXT),
                    "note": ("노외 3곳의 월 정기권이 모두 40,000원이고 신청 가능 면수는 98면(송우로 "
                             "제1 55·제2 29·제3 14)이다. 매월 25일(휴일이면 전날) 09:00부터 온라인 "
                             "선착순 접수하고 카드로만 결제하며, 경차·저공해·장애인·국가유공자·"
                             "다자녀는 50% 감면(20,000원)이다. 노상 월 정기권은 공사가 따로 안내하지 "
                             "않아 조례 별표1(70,000원)을 그대로 적었다."),
                },
                {
                    "id": "city", "name": "포천시 대표 누리집 — 교통/주차시설(명절 공영주차장 무료 개방)",
                    "org": "포천시청", "url": PH_CITY_URL,
                    "file": PH_CITY_TXT.name if PH_CITY_TXT.exists() else None,
                    "sha256": sha256(PH_CITY_TXT) if PH_CITY_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "2026-09-23~27",
                    "rows_total": 14, "fetched_at": _sync_time(PH_CITY_TXT),
                    "note": ("2026년 추석 연휴(9.23~9.27)에 무료로 개방한 공영주차장 14곳과 면수를 "
                             "확인해, 어느 주차장이 평소 유료인지 가려냈다 — 신읍동 8구간, 소흘읍 "
                             "5곳(송우로 제1·2·3 포함), 일동면 1구간이다. 표준데이터가 ‘무료’로 "
                             "등록한 송우로 제3공영주차장도 이 목록에 있어 유료 운영을 뒷받침한다."),
                },
                {
                    "id": "news", "name": "기호일보 — 포천도시공사 공영주차장 요금감면 전면 폐지 및 정상화 운영",
                    "org": "기호일보(2024-12-04 보도)", "url": PH_NEWS_URL,
                    "file": PH_NEWS_TXT.name if PH_NEWS_TXT.exists() else None,
                    "sha256": sha256(PH_NEWS_TXT) if PH_NEWS_TXT.exists() else None,
                    "license": "언론 보도(참고용)", "base_date": "2024-12-04",
                    "rows_total": None, "fetched_at": _sync_time(PH_NEWS_TXT),
                    "note": ("코로나19 한시 감면을 2024-12-31자로 끝내고 2025-01-01부터 정상 요금을 "
                             "받는다고 보도했다 — 대상은 시청사 부설, 송우로 제1·2·3공영주차장, "
                             "소흘읍·포천동·일동면 공영주차장이고, ‘입차 후 5분 무료, 10분당 "
                             "200원’이라고 적고 있다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in PH_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "pocheon_grade",
            "unit_min": PH_UNIT_MIN,
            "base_min": PH_BASE_MIN,
            "free_min": PH_FREE_MIN,
            "applies": PH_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "도시지역 중 주거지역·상업지역·공업지역",
                 "unit": 200, "day_st": 7_000, "day_out": 7_000,
                 "month_st": 70_000, "month_out": 40_000, "lots": 0},
                {"grade": 2, "where": "1급지 외의 지역",
                 "unit": 100, "day_st": 4_000, "day_out": 4_000,
                 "month_st": 40_000, "month_out": 30_000, "lots": 0},
            ],
            "paid_window": {"start": "09:00", "end": "18:00",
                            "free": "운영시간 외·토요일·일요일·공휴일 무료 개방"},
            "lunch_free": {"start": "11:30", "end": "13:30", "target": "유료 노상주차장"},
            "corp": {
                "street": {"lots": 25, "spaces": 484, "areas": "소흘읍 5·일동면 5·포천동 15"},
                "out": {"lots": 3, "spaces": 193, "names": "송우로 제1·2·3"},
                "month_out_spaces": 98,
                "paid": len([l for l in lots if l["fee"]["type"] == "유료"]),
                "free": len([l for l in lots if l["fee"]["type"] == "무료"]),
                "free_spaces": sum(l["spaces"] or 0 for l in lots if l["fee"]["type"] == "무료"),
            },
            "lots": [
                {"name": l["name"], "dong": l["dong"], "ptype": l["ptype"],
                 "grade": l["fee"].get("grade"), "free": l["fee"].get("free_min"),
                 "unit": l["fee"].get("unit_fee"), "day": l["fee"].get("daily_fee"),
                 "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "basis": ("「포천시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 요금표"
                      f"({PH_ORDINANCE_NOTE}) · 포천도시공사 공영주차장 요금안내(2026-11-17 확인)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["포천시"] | {
        "city": "포천시",
        "weekend_free_pages": False,
        "discounts": PH_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "pocheon_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_pocheon(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                          note_fixed, reclassified, month_diff, lunch_street, five_day):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    free = [l for l in lots if l["fee"]["type"] == "무료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_포천시행수": len([r for r in rows if (r.get("주차장구분") or "").strip() == "공영"]),
        "원자료_전체행수": len(rows),
        "민영_제외": len([e for e in excluded if "민영" in e["reason"]]),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in paid
                                     if l["fee"].get("std_grade"))),
        "유료_노상": len([l for l in paid if l["ptype"] == "노상"]),
        "유료_노외": len([l for l in paid if l["ptype"] == "노외"]),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "등록값_차이": note_fixed,
        "요금구분_보정": reclassified,
        "정기권_차이": month_diff,
        "점심시간_무료_노상": lunch_street,
        "5부제": five_day,
        "감면_출처": "「포천시 주차장 설치 및 관리 조례」 별표2(제3조제3항) · 포천도시공사 감면 대상",
        "무료시간_출처": "조례 별표1 공영주차장 요금표(최초 5분 무료)",
        "주말무료_출처": ("조례 별표1 비고5(토·일요일·공휴일·야간 무료 원칙) · "
                          "포천도시공사 요금안내(토·일·법정공휴일 무료 개방)"),
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len(free),
        "무료_구획수": sum(l["spaces"] or 0 for l in free),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 의왕시 (T-03 Phase 24)
UW_PROVIDER = "경기도 의왕시"
# 의왕시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
UW_DISTRICTS = [("의왕시", "uiwang")]
UW_BBOX = (37.28, 37.44, 126.92, 127.06)   # 의왕시 대략 경계(좌표 점검용)
# 의왕시 법정동 — 주소의 ‘경기도 의왕시 ○○동 번지’ 세 번째 낱말을 쓴다.
#   의왕시는 읍·면이 없고 12개 법정동(고천·이·왕곡·오전·학의·내손·포일·청계·이동·삼·월암·초평)으로
#   이루어지며, 행정동은 고천동·부곡동·오전동·내손1동·내손2동·청계동 6개다.
UW_UNIT_SUFFIX = ("동",)
# 표준데이터에 실제로 주소가 올라온 지역(품질 리포트의 동별 집계와 같은 값이 된다).

UW_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2153459"
                    "&gubun=ELIS&conDatGubunCd=1")
UW_CORP_URL = "https://www.uuc.or.kr/base/contents/view?contentsNo=26&menuLevel=3&menuNo=45"
UW_DISC_URL = "https://www.uuc.or.kr/base/contents/view?contentsNo=131&menuLevel=3&menuNo=127"
UW_NEWS_URL = "https://siminilbo.co.kr/news/newsview.php?ncode=1160274638630509"
UW_SYS_URL = "https://parking.uiwang.go.kr/"
UW_ORD_ANNEX1_HWP = RAW / "uiwang.law.go.kr_주차장조례_별표1_20261117.hwpx"
UW_ORD_ANNEX1_TXT = RAW / "uiwang.law.go.kr_주차장조례_별표1_20261117.txt"
UW_ORD_ANNEX2_HWP = RAW / "uiwang.law.go.kr_주차장조례_별표2_20261117.hwpx"
UW_ORD_ANNEX2_TXT = RAW / "uiwang.law.go.kr_주차장조례_별표2_20261117.txt"
UW_CORP_TXT = RAW / "uuc.or.kr_공영주차장_요금안내_20261117.txt"
UW_DISC_TXT = RAW / "uuc.or.kr_감면안내_20261117.txt"
UW_NEWS_TXT = RAW / "siminilbo.co.kr_고천문화공원_공영주차장_개시_20261117.txt"
UW_SYS_TXT = RAW / "uiwang.go.kr_통합주차정보시스템_중단_20261117.txt"
UW_ORDINANCE_NOTE = ("시행 2026-05-07 · 경기도의왕시조례 제2336호(일부개정) · "
                     "별표1·별표2 〈개정 2025.9.30.〉")
UW_BASE_MIN = 30
UW_UNIT_MIN = 10
UW_FREE_MIN = 10

# 의왕시 공영주차장 요금 — 「의왕시 주차장설치 및 관리 조례」 [별표 1] 공영주차장 주차요금표
#   (시행 2026-05-07, 경기도의왕시조례 제2336호 · 별표1 〈개정 2025.9.30.〉, 별표/서식 HWPX에서 표를 읽음).
#   · 노상: 1급지 최초 30분 800원·이후 10분당 300원·1일 주차권 8,000원·월 정기권(전일) 85,000원
#           2급지 600·200·6,000·50,000원 / 3급지 500·200·5,000·40,000원
#   · 노외: 노상과 같은 1회 요금에 월 정기권(야간)을 더 둔다 — 1급지 60,000·2급지 45,000·3급지 35,000원
#   · 거주자 전용 주차구획: 주간(07:00~19:00) 25,000·야간(19:00~익일 07:00) 20,000·전일 35,000원
#   · 행락지 주차장: 1시간 이내 1,000 / 1시간 초과 3시간 이내 2,000 / 3시간 초과 6시간 이내 3,000 /
#     6시간 초과 9시간 이내 4,000 / 9시간 초과(1일 주차권) 5,000원, 월 정기권 전일 45,000·야간 40,000원
#   · 비고2: 주간은 평일 09:00~20:00, 토·일·공휴일 09:00~18:00이고 나머지는 야간. 일요일·공휴일은
#     무료가 원칙이나 노외주차장·행락지 주차장은 야간·일요일·공휴일에도 요금을 받을 수 있다.
#   · 비고3: 상업지역 1급지, 공업·주거지역 2급지, 개발제한구역 포함 자연녹지지역 3급지.
#   · 비고5: 15~25인승·2.5~5톤 2배, 25인승 초과·5톤 초과 3배(행락지 관광 목적 버스는 전액 면제).
#   · 비고6: 1일 1회 주차요금이 1일 주차권보다 많으면 1일 주차권 요금으로 징수.
#   · 비고7: 행락지 주차장 = 백운호수제방·왕송호수·청계산·왕송호수공원·무민공원·백운호수공원 제1·제2.
UW_FEES = {
    (1, "노상"): {"base": 800, "unit": 300, "day": 8_000, "month": 85_000, "night": None},
    (2, "노상"): {"base": 600, "unit": 200, "day": 6_000, "month": 50_000, "night": None},
    (3, "노상"): {"base": 500, "unit": 200, "day": 5_000, "month": 40_000, "night": None},
    (1, "노외"): {"base": 800, "unit": 300, "day": 8_000, "month": 85_000, "night": 60_000},
    (2, "노외"): {"base": 600, "unit": 200, "day": 6_000, "month": 50_000, "night": 45_000},
    (3, "노외"): {"base": 500, "unit": 200, "day": 5_000, "month": 40_000, "night": 35_000},
}
# 행락지 주차장의 구간 요금 — 총 주차시간이 속한 구간의 금액을 받는다(누진이 아니라 구간 합계).
UW_PARK_BANDS = [
    {"until": 60, "amount": 1_000},      # 1시간 이내
    {"until": 180, "amount": 2_000},     # 1시간 초과 3시간 이내
    {"until": 360, "amount": 3_000},     # 3시간 초과 6시간 이내
    {"until": 540, "amount": 4_000},     # 6시간 초과 9시간 이내
    {"until": None, "amount": 5_000},    # 9시간 초과(1일 주차권)
]
UW_PARK_MONTH = 45_000
UW_PARK_NIGHT = 40_000

# 의왕도시공사가 요금을 받는 시간과 무료 개방 — 요금안내 표의 각주(2026-11-17 조회).
#   · 내손주차빌딩(표준데이터 이름 ‘내손체육공원 주차빌딩’)·의왕역·고천주민센터·백운커뮤니티 주차타워·
#     서울외곽순환하부: ‘무료개방 : 야간 20:00~익일 08:00, 주말, 공휴일’
#   · 청계산: ‘무료개방: 주말, 공휴일’ / 유료 노상(왕곡천복개·오전천복개): 휴무일 ‘토·일요일,
#     공휴일(무료운영)’
#   · 그 밖의 유료 주차장은 무료 개방 각주가 없어 24시간 같은 요금을 받는다(조례 비고2가 노외·행락지
#     주차장의 야간·일요일·공휴일 요금 부과를 허용한다).
UW_FREE_OPEN = {
    "내손체육공원 주차빌딩": {"night": (20 * 60, 8 * 60), "weekend": True},
    "의왕역 공영주차장": {"night": (20 * 60, 8 * 60), "weekend": True},
    "고천주민센터 공영주차장": {"night": (20 * 60, 8 * 60), "weekend": True},
    "백운커뮤니티센터 주차타워": {"night": (20 * 60, 8 * 60), "weekend": True},
    "서울외곽순환고속도로하부": {"night": (20 * 60, 8 * 60), "weekend": True},
    "청계산 공영주차장": {"night": None, "weekend": True},
    "왕곡천복개주차장": {"night": None, "weekend": True},
    "오전천복개1": {"night": None, "weekend": True},
}
# 의왕도시공사 요금안내가 적은 급지 — 표준데이터의 급지구분과 대조한다(모두 같다).
UW_CORP_GRADE = {
    "고천주민센터 공영주차장": 1, "계원대학로 제2 공영주차장": 1,
    "서울외곽순환고속도로하부": 1, "왕곡천복개주차장": 1,
    "내손체육공원 주차빌딩": 2, "내손 제1공영주차장": 2, "내손 제2공영주차장": 2,
    "내손 제3공영주차장": 2, "내손 제4공영주차장": 2, "갈미어린이공원 공영주차장": 2,
    "의왕역 공영주차장": 2, "고천지구 공영주차장": 2, "백운커뮤니티센터 주차타워": 2,
    "오전천복개1": 2, "고천문화공원 공영주차장": 2,
    "산빛근린공원 공영주차장": 3, "왕송고가하부 공영주차장": 3,
}
# 의왕도시공사가 ‘(화물차 전용)’으로만 안내하는 주차장 — 급지가 없어 조례 별표1의 급지 요금을
#   적용할 수 없다. 표준데이터에 등록된 값(60분 1,000원·120분마다 1,000원·1일 5,000원·
#   월 45,000원)을 그대로 쓴다(공사는 화물차 월 정기·차고지 요금만 안내한다).
UW_SPECIAL = {
    "백운호수교각 공영주차장": {"label": "화물차 전용", "base_min": 60, "base_fee": 1_000,
                             "unit_min": 120, "unit_fee": 1_000, "day": 5_000, "month": 45_000},
}
# 의왕도시공사 요금안내가 적은 주차장별 면수 가운데 표준데이터와 다른 곳.
UW_CORP_SPACES = {
    "고천지구 공영주차장": 99,          # 표준 85면
    "서울외곽순환고속도로하부": 66,     # 표준 70면
    "고천주민센터 공영주차장": 85,      # 표준 86면
}
# 표준데이터 이름 → 의왕도시공사 요금안내의 주차장 이름(카드에 함께 적는다).
UW_CORP_NAME = {
    "내손체육공원 주차빌딩": "내손주차빌딩",
    "서울외곽순환고속도로하부": "서울외곽순환하부주차장",
    "백운호수교각 공영주차장": "백운교각주차장",
    "백운호수제방 공영주차장": "백운제방주차장",
    "왕곡천복개주차장": "왕곡천복개 공영주차장",
    "오전천복개1": "오전천복개 공영주차장",
    "의왕역 공영주차장": "의왕역공영주차장",
    "내손 제1공영주차장": "내손제1공영주차장",
    "내손 제2공영주차장": "내손제2공영주차장",
    "내손 제3공영주차장": "내손제3공영주차장",
    "내손 제4공영주차장": "내손제4공영주차장",
    "갈미어린이공원 공영주차장": "갈미어린이공원 공영주차장",
    "산빛근린공원 공영주차장": "산빛근린공원 공영주차장",
    "백운커뮤니티센터 주차타워": "백운커뮤니티 주차타워",
    "계원대학로 제2 공영주차장": "계원대학로 제2공영주차장",
    "청계산 공영주차장": "청계산공영주차장",
}
# 조례 별표1 비고7이 정한 행락지 주차장.
UW_PARK_LOTS = {
    "백운호수제방 공영주차장", "왕송호수 공영주차장", "청계산 공영주차장",
    "왕송호수공원 공영주차장", "무민공원 공영주차장",
    "백운호수제1공영주차장", "백운호수제2공영주차장",
}
# 표준데이터가 ‘무료’로 등록했지만 지금은 요금을 받는 주차장.
#   · 고천문화공원: 2026-04-01 정식 운영, 4월 한 달 무료 시범 운영 뒤 5월부터 유료 전환(시민일보
#     2026-03-30). 의왕도시공사 요금안내는 2급지(30분 600원·10분당 200원·1일 6,000원·월 50,000원).
#   · 백운호수공원 제1·2: 조례 별표1 비고7이 행락지 주차장으로 지정하고, 현장 안내판도 행락지
#     요금(1시간 1,000원~9시간 초과 5,000원)을 적고 있다. 의왕도시공사 감면안내도 행락지 목록에
#     ‘백운호수 공원1·2’를 넣었다.
UW_RECLASSIFIED = {
    "고천문화공원 공영주차장": "2급지",
    "백운호수제1공영주차장": "행락지",
    "백운호수제2공영주차장": "행락지",
}
# 월 정기권 — 조례 별표1의 금액과 의왕도시공사 요금안내의 신청 조건.
UW_MONTHLY = {
    "내손체육공원 주차빌딩": (50_000, "내손주차빌딩 — 정기주차(주·야간) 50,000원"),
    "내손 제1공영주차장": (50_000, "정기권 50,000원, 타지역 시민도 신청할 수 있습니다"),
    "내손 제2공영주차장": (50_000, "정기권 50,000원, 의왕시민만 6개월 단위 추첨제"),
    "내손 제3공영주차장": (50_000, "정기권 50,000원, 의왕시민(주변에서 상가를 운영하는 타지역 시민 포함)"),
    "내손 제4공영주차장": (None, "정기권을 받지 않습니다"),
    "갈미어린이공원 공영주차장": (50_000, "정기권 50,000원, 의왕시민만 신청할 수 있습니다"),
    "산빛근린공원 공영주차장": (None, "정기권을 받지 않습니다"),
    "왕송고가하부 공영주차장": (None, "정기권을 받지 않습니다"),
    "계원대학로 제2 공영주차장": (None, "정기권을 받지 않습니다"),
    "의왕역 공영주차장": (None, "정기권을 받지 않습니다"),
    "고천주민센터 공영주차장": (None, "정기권을 받지 않습니다"),
    "백운커뮤니티센터 주차타워": (50_000, "정기권 50,000원, 의왕시민만 신청할 수 있습니다"),
    "고천지구 공영주차장": (50_000, "정기권 50,000원, 타지역 시민도 신청할 수 있습니다"),
    "고천문화공원 공영주차장": (50_000, "정기권 50,000원, 의왕시민이 이용할 수 있습니다"),
    "왕송호수 공영주차장": (45_000, "행락지 주차장 월 정기권 45,000원, 타지역 시민도 신청할 수 있습니다"),
    "왕송호수공원 공영주차장": (45_000, "행락지 주차장 월 정기권 45,000원(승용차만, 화물 불가)"),
    "백운호수제방 공영주차장": (45_000, "행락지 주차장 월 정기권 45,000원 — 승용차 정기권은 상황실 문의, "
                                        "버스·캠핑카·버스운전원 승용차는 1년 단위 추첨제"),
    "청계산 공영주차장": (None, "정기권을 받지 않습니다"),
    "백운호수교각 공영주차장": (45_000, "화물차 전용 주차장 — 1년 단위 추첨제, 화물차 월 정기주차 "
                                        "소형(1톤 이하) 45,000·중형 90,000·대형 135,000원"),
    "서울외곽순환고속도로하부": (None, "정기권을 받지 않습니다"),
    "왕곡천복개주차장": (85_000, "노상 1급지 월 정기권 85,000원(조례 별표1)"),
    "오전천복개1": (50_000, "노상 2급지 월 정기권 50,000원(조례 별표1)"),
}

# 의왕시 주차요금 감면 — 「의왕시 주차장설치 및 관리 조례」 [별표 2](제5조제1항 관련)와
#   의왕도시공사 ‘감면안내’(2026-11-17 확인). 감면은 중복 적용하지 않고(공통사항 1) 증빙서류를
#   낸 때부터 적용한다.
UW_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "장애인·국가유공자 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": ("「장애인복지법」 제2조에 따른 장애인이 직접 운전 또는 탑승하고 장애인 자동차 표지를 "
              "부착한 자동차, 「국가유공자 등 예우 및 지원에 관한 법률」 제4조에 따른 국가유공자 및 "
              "그 유족, 고엽제후유의증 등 대상자 및 그 유족, 5·18민주유공자 및 그 유족, "
              "「의왕시 기업활동 촉진 및 투자유치 지원 조례」에 따른 우수기업 대표자 — "
              "1일 1회 주차에 한해 최초 2시간 면제, 2시간 초과분 50% 감면")},
    {"label": "경차·다자녀·경로우대 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": ("경형자동차(1,000cc 미만), 기초생활수급자 소유 차량, 한부모 가족 차량, 18세 이하 자녀가 "
              "있는 다자녀 가정, 「의왕시 병역명문가 예우에 관한 조례」에 따른 예우 대상자, 만 65세 이상 "
              "경로우대(1회 주차), 전통시장 이용자(1회 2시간 이내), 우수자원봉사자(1회 2시간 이내), "
              "임산부 자동차 표지 발급 차량, 장기복무 제대군인, 저공해 2·3종 표지 부착 차량 — 50% 감면")},
    {"label": "저공해 1종·플러그인하이브리드 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": ("「대기환경보전법」에 따른 저공해 자동차 가운데 제1종 저공해 자동차 표지 부착 차량과 "
              "플러그인하이브리드 차량 — 최초 2시간 무료, 초과분 50% 감면")},
    {"label": "환승 경차 60%", "rate": 0.6, "exempt_min": 0,
     "note": "환승을 목적으로 환승주차장에 주차하는 경차 — 환승목적 증명서류 제시자"},
    {"label": "의왕시 거주자 행락지 30%", "rate": 0.3, "exempt_min": 0,
     "note": ("의왕시 거주자가 행락지 주차장(백운호수·청계산·왕송호수·자연학습공원·무민공원·"
              "백운호수공원 제1·2 등)을 이용하는 경우 1회 주차에 한해 30% 감면 — 거주지 증명서 제시. "
              "왕송호수·왕송호수공원 주차장을 야영장·레저시설 이용을 위해 주차한 경우와 주거지역·"
              "녹지지역 노외주차장 반경 50m 이내 거주 주민(정기권)도 30%입니다")},
    {"label": "요일제 운행 20%", "rate": 0.2, "exempt_min": 0,
     "note": ("승용차 부제(요일제 등) 운행차량과 자가용 함께 타기 참여 차량 — 지방자치단체장의 "
              "확인필증을 부착한 자동차, 20% 감면")},
    {"label": "긴급·관용·유공납세자 등 100%", "rate": 1.0, "exempt_min": 0,
     "note": ("긴급자동차, 국가·지방자치단체 공무수행(관용) 자동차, 외교사절 및 그 수행자의 공무수행 "
              "(관용) 자동차, 모범·유공납세자 인증표지 부착 차량 1대(교부일로부터 1년), "
              "공공청사 부설주차장 민원인(1시간)·위원회 참석위원·문화강좌 수강생(3시간) — 면제")},
]


def uw_dong_of(text: str):
    """주소에서 의왕시 법정동을 뽑는다 — ‘경기도 의왕시 {동} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "의왕시":
        cand = parts[2]
        if cand.endswith("동") and not cand.endswith(("로동", "가동")):
            return cand
    return None


def uw_fee(ptype: str = "노외", grade: int = 1, pay: str = "", *,
           monthly=None, month_note="", park=False):
    """의왕시 공영주차장 요금 → 사이트 공통 fee 객체.

    급지 요금은 ‘최초 30분 기본요금 + 이후 10분당’ 구조이고, 조례 별표2 제1호 마목이
    ‘10분 미만 이용차량’을 전액 면제하므로 free_min=10을 둔다(10분까지 0원, 11~30분 기본요금).
    행락지 주차장은 시간 구간별 금액(bands)이라 base 1시간 1,000원을 두고 bands가 계산을 맡는다.
    """
    if park:
        return {
            "type": "유료", "raw_type": "유료", "mixed": False,
            "grade": None, "grade_label": "행락지", "std_grade": "행락지",
            "base_min": 60, "base_fee": 1_000,
            "unit_min": 60, "unit_fee": 1_000,
            "bands": [dict(b) for b in UW_PARK_BANDS],
            "steps": None, "steps_label": None,
            "free_min": UW_FREE_MIN, "deduct_min": None,
            "cap_fee": None, "cap_src": "조례 별표1 행락지 1일 주차권",
            "daily_hours": None, "daily_fee": 5_000,
            "prepaid_day": None, "prepaid_weekend": None,
            "monthly": UW_PARK_MONTH if monthly is None else monthly,
            "monthly_day": None, "monthly_night": UW_PARK_NIGHT,
            "monthly_all": UW_PARK_MONTH if monthly is None else monthly,
            "monthly_label": "행락지 정기권",
            "pay": pay,
            "basis": ("「의왕시 주차장설치 및 관리 조례」 별표1 행락지 주차장(1시간 이내 1,000원 · "
                      "3시간 이내 2,000원 · 6시간 이내 3,000원 · 9시간 이내 4,000원 · "
                      "9시간 초과 5,000원)"),
            "category": None, "portal_free_now": False, "flat_day": False,
            "ticket_only": False, "std": None,
        }
    t = UW_FEES[(grade, ptype)]
    month = t["month"] if monthly is None else monthly
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "grade_label": None, "std_grade": None,
        "base_min": UW_BASE_MIN, "base_fee": t["base"],
        "unit_min": UW_UNIT_MIN, "unit_fee": t["unit"],
        "bands": None, "steps": None, "steps_label": None,
        "free_min": UW_FREE_MIN, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 별표1 1일 주차권",
        "daily_hours": None, "daily_fee": t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": month, "monthly_day": None, "monthly_night": t["night"],
        "monthly_all": month, "monthly_label": month_note or None,
        "pay": pay,
        "basis": (f"「의왕시 주차장설치 및 관리 조례」 별표1 {grade}급지 {ptype} "
                  f"(최초 {UW_BASE_MIN}분 {t['base']:,}원 · 이후 {UW_UNIT_MIN}분당 {t['unit']:,}원 · "
                  f"1일 {t['day']:,}원)"),
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def uw_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "grade_label": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "bands": None, "steps": None, "steps_label": None,
        "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def uw_hm(m: int) -> str:
    h, mi = divmod(int(m), 60)
    return f"{h:02d}:{mi:02d}"


def uw_window(start, end):
    return {"open": True, "start": start, "end": end, "24h": False, "listed": True,
            "raw": [uw_hm(start), uw_hm(end)]}


def build_uiwang():
    """의왕시 공영주차장을 표준데이터 + 의왕시 조례 별표1·2 + 의왕도시공사 요금안내로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 의왕시 범위를 벗어난 행은 제외(껍데기 행).
      · 표준데이터 55행은 모두 공영(민영 등록 없음)이라 민영 제외는 일어나지 않는다.
      · 의왕시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동만 만든다.
    요금은 조례 별표1(급지별 30분 기본·10분당 요율, 행락지 구간 요금)을 쓰고, 무료 개방은
    의왕도시공사 요금안내 각주(야간 20:00~08:00·주말·공휴일)를 따른다(표준데이터는 유료 행도
    00:00~23:59로 등록되어 있다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == UW_PROVIDER]
    lots, excluded, merged = [], [], []
    hour_fixed, space_diff, note_fixed, reclassified, month_diff = [], [], [], [], []
    night_free, weekend_free, grade_from_corp, park_from_rule, std_grade_diff = [], [], [], [], []

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                notice=None, tel="", mgmt="", lat=None, lng=None, base_date="",
                free_days=None, free_note=None):
        street = ptype == "노상"
        lots.append({
            "id": "",
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "의왕시",
            "dong": dong,
            "dong_src": ("지번주소" if r and uw_dong_of((r.get("소재지지번주소") or "")) else
                         ("도로명주소" if r and uw_dong_of((r.get("소재지도로명주소") or "")) else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "의왕도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": (fee["base_fee"] if fee["type"] == "유료" else None),
            "city": "의왕시",
            "city_slug": "uiwang",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        gubun = (r.get("주차장구분") or "").strip()
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if gubun == "민영":
            excluded.append({"name": name or "(이름 없음)", "reason": "민영 주차장(공영 아님)"})
            continue
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not (UW_BBOX[0] <= lat <= UW_BBOX[1] and UW_BBOX[2] <= lng <= UW_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = uw_dong_of(jibun) or uw_dong_of(road)
        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        pay = (r.get("결제방법") or "").strip()
        fee_type = (r.get("요금정보") or "").strip()
        std_grade = (r.get("급지구분") or "").strip()
        grade = to_int(std_grade)
        if grade:
            grade = min(max(grade, 1), 3)
        notice_bits = []
        free_days = {"sat": False, "sun": False}
        free_note = None
        monthly, month_note = UW_MONTHLY.get(name, (None, ""))
        corp_name = UW_CORP_NAME.get(name)

        paid = fee_type in ("유료", "혼합") or name in UW_RECLASSIFIED
        park = name in UW_PARK_LOTS
        if fee_type not in ("유료", "혼합") and name in UW_RECLASSIFIED:
            want = UW_RECLASSIFIED[name]
            reclassified.append(
                f"{name}: 표준데이터 요금정보 ‘{fee_type or '무료'}’ ↔ 지금은 {want} 요금을 받는 "
                f"주차장 — 유료로 바로잡음")
            if name == "고천문화공원 공영주차장":
                notice_bits.append(
                    "2026년 4월 1일 정식 운영을 시작해 4월 한 달은 무료로 시범 운영하고 "
                    "5월부터 유료로 전환했습니다(시민일보 2026-03-30) — 공공데이터 표준데이터에는 "
                    "아직 ‘무료’로 등록되어 있습니다")
                grade = 2
            else:
                notice_bits.append(
                    "조례 별표1 비고7이 행락지 주차장으로 지정한 곳입니다 — 현장 안내판도 1시간 "
                    "1,000원~9시간 초과 5,000원의 행락지 요금을 적고 있고, 공공데이터 표준데이터에는 "
                    "아직 ‘무료’로 등록되어 있습니다")
                park_from_rule.append(name)
        if park and fee_type in ("유료", "혼합"):
            park_from_rule.append(name)
        special = UW_SPECIAL.get(name)
        if paid and not park and not special:
            if not grade:
                grade = 2      # 급지가 비어 있는 유료 행(고천문화공원)은 2급지로 본다
                std_grade_diff.append(f"{name}: 표준데이터 급지구분 ‘{std_grade or '없음'}’ ↔ "
                                      f"의왕도시공사 요금안내 2급지")
            corp_grade = UW_CORP_GRADE.get(name)
            if corp_grade and corp_grade != grade:
                grade_from_corp.append(
                    f"{name}: 표준데이터 {grade}급지 ↔ 의왕도시공사 요금안내 {corp_grade}급지 — "
                    f"공사 안내를 따름")
                grade = corp_grade

        if paid and special:
            fee = uw_free_fee()
            fee.update({
                "type": "유료", "raw_type": "유료",
                "grade": None, "grade_label": special["label"], "std_grade": std_grade or None,
                "base_min": special["base_min"], "base_fee": special["base_fee"],
                "unit_min": special["unit_min"], "unit_fee": special["unit_fee"],
                "free_min": UW_FREE_MIN, "daily_fee": special["day"],
                "monthly": monthly if monthly is not None else special["month"],
                "monthly_all": monthly if monthly is not None else special["month"],
                "monthly_label": None, "pay": pay,
                "cap_src": "표준데이터 1일 주차권",
                "basis": ("표준데이터 등록 요금(60분 1,000원 · 이후 120분마다 1,000원 · "
                          "1일 5,000원 · 월 45,000원)"),
                "std": {"base_min": to_int(r.get("주차기본시간")),
                        "base_fee": to_int(r.get("주차기본요금")),
                        "unit_min": to_int(r.get("추가단위시간")),
                        "unit_fee": to_int(r.get("추가단위요금")),
                        "day": to_int(r.get("1일주차권요금")),
                        "monthly": to_int(r.get("월정기권요금"))},
            })
            notice_bits.append(
                "화물차 전용 주차장이라 일반 승용차는 이용할 수 없습니다 — 의왕도시공사는 화물차 "
                "월 정기·차고지 요금만 안내하고, 위 시간 요금은 표준데이터 등록값입니다")
            if month_note:
                notice_bits.append(month_note)
        elif paid:
            fee = uw_fee(ptype, grade or 2, pay=pay, monthly=monthly, park=park)
            if name in UW_MONTHLY and UW_MONTHLY[name][0] is None:
                # 정기권을 받지 않는 주차장 — 조례의 월 정기권 금액을 카드에 띄우지 않는다.
                fee["monthly"] = fee["monthly_all"] = fee["monthly_night"] = None
                fee["monthly_label"] = None
            month_txt = f", 월 정기권 {fee['monthly']:,}원" if fee["monthly"] else ""
            daily_std = to_int(r.get("1일주차권요금")) or 0
            month_std = to_int(r.get("월정기권요금")) or 0
            applied_std = (r.get("1일주차권요금적용시간") or "").strip()
            fee["std"] = {"base_min": to_int(r.get("주차기본시간")),
                          "base_fee": to_int(r.get("주차기본요금")),
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily_std, "monthly": month_std}
            want_day = 5_000 if park else UW_FEES[(grade or 2, ptype)]["day"]
            want_month = (UW_PARK_MONTH if park else UW_FEES[(grade or 2, ptype)]["month"])
            if daily_std and daily_std != want_day:
                note_fixed.append(
                    f"{name}: 표준데이터 1일주차권요금 {daily_std:,}원 ↔ 조례 별표1 "
                    f"{'행락지' if park else f'{grade}급지 {ptype}'} 1일 {want_day:,}원")
            if month_std and want_month and month_std != want_month:
                month_diff.append(f"{name}: 표준데이터 월정기권 {month_std:,}원 ↔ 조례 별표1 "
                                  f"{'행락지' if park else f'{ptype} {grade}급지'} {want_month:,}원")
            # 무료 개방(야간·주말·공휴일) — 의왕도시공사 요금안내 각주
            fo = UW_FREE_OPEN.get(name)
            if fo:
                if fo.get("weekend"):
                    free_days = {"sat": True, "sun": True}
                    weekend_free.append(name)
                bits = []
                night = fo.get("night")
                if night:
                    s, e = night
                    # 요금을 받는 시간은 무료 개방의 반대편(08:00~20:00)이다 — 운영일은 그대로 연다.
                    win = {"weekday": uw_window(e, s), "sat": uw_window(e, s), "sun": uw_window(e, s)}
                    night_free.append(name)
                    bits.append(f"야간 {uw_hm(s)}~익일 {uw_hm(e)}")
                if fo.get("weekend"):
                    bits.append("토요일·일요일·공휴일")
                oper = {"weekday": True, "sat": True, "sun": True}
                free_note = ("의왕도시공사 요금안내: " + "·".join(bits) + "은 무료로 개방합니다")
                if night:
                    free_note += f" — 요금은 {uw_hm(night[1])}~{uw_hm(night[0])}에만 받습니다"
                free_note += (". 계산기는 머문 시간만으로 계산해 무료 시간을 빼지 않으니, 실제 "
                              "정산은 현장 안내를 확인하세요.")
                hour_fixed.append(
                    f"{name}: 표준데이터 평일 {r.get('평일운영시작시각') or ''}~"
                    f"{r.get('평일운영종료시각') or ''} → 의왕도시공사 요금안내의 무료 개방"
                    f"({'·'.join(bits)})을 반영")
            notice_bits.append(
                f"「의왕시 주차장설치 및 관리 조례」 별표1 "
                + ("행락지 주차장 요금입니다 — 1시간 이내 1,000원, 1시간 초과 3시간 이내 "
                   "2,000원, 3~6시간 3,000원, 6~9시간 4,000원, 9시간 초과(1일 주차권) 5,000원"
                   if park else
                   f"{grade}급지 {ptype} 요금입니다 — 최초 30분 {fee['base_fee']:,}원, 이후 "
                   f"10분당 {fee['unit_fee']:,}원, 1일 주차권 {fee['daily_fee']:,}원")
                + month_txt
                + ". 조례 별표2로 10분 미만 이용은 무료입니다")
            if month_note:
                notice_bits.append(month_note)
            if name in UW_CORP_SPACES and UW_CORP_SPACES[name] != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 의왕도시공사 "
                                  f"{UW_CORP_SPACES[name]}면")
                notice_bits.append(
                    f"표준데이터 등록면수는 {spaces}면이고, 의왕도시공사 안내는 "
                    f"{UW_CORP_SPACES[name]}면입니다")
        else:
            fee = uw_free_fee()
            if name in UW_CORP_SPACES and UW_CORP_SPACES[name] != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 의왕도시공사 "
                                  f"{UW_CORP_SPACES[name]}면")

        # 무료로 개방하는 요일은 운영 칸을 열어 둔다 — 표준데이터가 유료 노상의 공휴일을
        #   00:00~00:00(휴무)으로 등록한 곳(왕곡천복개·오전천복개)이 ‘휴무’로 보이지 않게 한다.
        for _k in ("sat", "sun"):
            if free_days.get(_k) and not win[_k]["open"]:
                win[_k] = dict(win["weekday"], open=True, listed=True)
        if corp_name and corp_name != name:
            notice_bits.append(f"의왕도시공사 요금안내에는 ‘{corp_name}’이라는 이름으로 적혀 있습니다")
        if name == "왕송호수공원 공영주차장":
            notice_bits.append("화물차·버스는 평일만 주차할 수 있습니다(주말 주차 불가)")
        if name == "의왕역 공영주차장":
            notice_bits.append(
                "공사 요금안내에 ‘야간주차 시간은 22:00부터 익일 08:00까지’와 ‘무료개방: 야간 "
                "20:00~익일 08:00’이 함께 적혀 있어 야간 기준이 서로 다릅니다 — 이 사이트는 "
                "20:00부터 무료로 계산합니다(현장 확인 권장)")

        if street and name in ("왕곡천복개주차장", "오전천복개1"):
            notice_bits.append("유료 노상주차장은 토요일·일요일·공휴일에 무료로 운영합니다"
                               "(의왕도시공사 요금안내 휴무일란)")

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=" · ".join(b for b in notice_bits if b) or None,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "의왕도시공사"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    # 결제 방법 — 의왕도시공사는 모든 주차장에서 신용카드·후불교통신용카드만 받는다(현금 결제 불가).
    #   표준데이터가 ‘현금’으로 등록한 유료 노상 2곳(왕곡천복개·서울외곽순환하부)을 바로잡는다.
    pay_fixed = []
    for l in lots:
        if l["fee"]["type"] != "유료":
            continue
        if (l["fee"].get("pay") or "") != "신용카드":
            pay_fixed.append(f"{l['name']}: 표준데이터 결제방법 ‘{l['fee'].get('pay') or '없음'}’ ↔ "
                             f"의왕도시공사 ‘신용카드·후불교통신용카드만(현금 결제 불가)’")
            l["fee"]["pay"] = "신용카드"

    # 이름이 같은 노상 구간(표준데이터가 같은 이름으로 두 줄 등록한 ‘이면도로 주차장’ 2곳)은
    #   지번을 덧붙여 구분한다.
    dup_names = {k for k, v in Counter(l["name"] for l in lots).items() if v > 1}
    for l in lots:
        if l["name"] in dup_names:
            jibun = (l["addr_jibun"] or "").split()
            if jibun:
                l["name"] = f"{l['name']}({jibun[-1]})"

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"uw-{i:03d}" if l["list_mode"] == "card" else f"uw-s{i:03d}"

    quality = check_quality_uiwang(rows_all, rows_city, lots, excluded, merged,
                                   hour_fixed, space_diff, note_fixed, reclassified,
                                   month_diff, night_free, weekend_free, grade_from_corp,
                                   park_from_rule, std_grade_diff, pay_fixed)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "의왕시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-04-23",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 22:03 (KST)",
                    "note": ("경기도 의왕시가 등록한 55행(노외 27·노상 28)을 읽었다. 모두 주차장구분이 "
                             "‘공영’이라 민영 주차장은 없다. 요금 구분은 유료 22행(노외 19·노상 3)과 "
                             "무료 33행이지만, 고천문화공원(2026-05 유료 전환)과 백운호수공원 "
                             "제1·2(조례 별표1 비고7 행락지)는 유료로 바로잡았다. 주차구획수가 비어 "
                             "있거나 좌표가 빠진 껍데기 행은 없어 55행을 모두 실었다."),
                },
                {
                    "id": "ordinance",
                    "name": ("의왕시 주차장설치 및 관리 조례 [별표 1] 공영주차장 주차요금표 · "
                             "[별표 2] 공영주차장 주차요금 감면기준"),
                    "org": "의왕시청 교통정책과(031-345-3311) · 의왕도시공사 통합관제실(031-8086-7440)",
                    "url": UW_ORDINANCE_URL,
                    "file": UW_ORD_ANNEX1_HWP.name if UW_ORD_ANNEX1_HWP.exists() else UW_ORD_ANNEX1_TXT.name,
                    "sha256": (sha256(UW_ORD_ANNEX1_HWP) if UW_ORD_ANNEX1_HWP.exists()
                               else sha256(UW_ORD_ANNEX1_TXT) if UW_ORD_ANNEX1_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": UW_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(UW_ORD_ANNEX1_TXT),
                    "note": ("국가법령정보센터 별표/서식 HWPX를 내려받아 표 셀을 읽어 정리본(txt)을 "
                             "두었다. 노상 1급지 최초 30분 800원·이후 10분당 300원·1일 주차권 "
                             "8,000원·월 정기권 85,000원(2급지 600·200·6,000·50,000원, 3급지 "
                             "500·200·5,000·40,000원)이고, 노외는 같은 1회 요금에 야간 정기권 "
                             "(1급지 60,000·2급지 45,000·3급지 35,000원)을 더 둔다. 행락지 주차장은 "
                             "1시간 이내 1,000 / 3시간 이내 2,000 / 6시간 이내 3,000 / 9시간 이내 "
                             "4,000 / 9시간 초과 5,000원, 월 정기권 45,000(야간 40,000)원이다. "
                             "별표2는 전액면제(긴급·관용·유공납세자·10분 미만 이용), 50% 감면"
                             "(장애인·국가유공자 등은 2시간 면제 뒤), 30% 감면(의왕시 거주자 행락지), "
                             "20% 감면(요일제)을 정한다."),
                },
                {
                    "id": "corp", "name": "의왕도시공사 공영주차장 요금안내(직영·위탁주차장, 노상주차장, 무료공영주차장)",
                    "org": "의왕도시공사 통합관제실(031-8086-7440)",
                    "url": UW_CORP_URL,
                    "file": UW_CORP_TXT.name if UW_CORP_TXT.exists() else None,
                    "sha256": sha256(UW_CORP_TXT) if UW_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 23, "fetched_at": _sync_time(UW_CORP_TXT),
                    "note": ("직영·위탁주차장 23곳(노외·부설)과 노상주차장 2곳, 동별 무료 노상주차장을 "
                             "급지·면수·요금·정기권·무료개방과 함께 싣고 있다. 급지는 1급지(고천주민센터·"
                             "계원대학로 제2·서울외곽순환하부·왕곡천복개), 2급지(내손 1~4·내손주차빌딩·"
                             "갈미·의왕역·고천지구·고천문화공원·백운커뮤니티·오전천복개), 3급지"
                             "(산빛근린·왕송고가하부), 행락지(백운제방·왕송호수·왕송호수공원·청계산·"
                             "무민공원)로 나뉜다. 유료 주차장 가운데 내손주차빌딩·의왕역·고천주민센터·"
                             "백운커뮤니티 주차타워·서울외곽순환하부는 ‘야간 20:00~익일 08:00·주말·"
                             "공휴일 무료 개방’, 청계산은 ‘주말·공휴일 무료 개방’을 적고, 노상 "
                             "왕곡천복개·오전천복개는 휴무일란에 ‘토·일요일, 공휴일(무료운영)’이라고 "
                             "적는다. 백운호수공원 제1·2와 내손공용청사는 이 목록에 없다."),
                },
                {
                    "id": "disc", "name": "의왕도시공사 교통시설 감면안내",
                    "org": "의왕도시공사 통합관제실(031-8086-7440)",
                    "url": UW_DISC_URL,
                    "file": UW_DISC_TXT.name if UW_DISC_TXT.exists() else None,
                    "sha256": sha256(UW_DISC_TXT) if UW_DISC_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 22, "fetched_at": _sync_time(UW_DISC_TXT),
                    "note": ("감면대상·증빙서류·할인율을 표로 정리해 두었다. 조례 별표2와 같은 내용이며, "
                             "행락지 목록을 ‘백운호수, 청계산, 왕송호수, 자연학습공원, 무민공원, "
                             "백운호수 공원1·2 등’으로 적어 백운호수공원 제1·2가 행락지 주차장임을 "
                             "뒷받침한다. 환승 경차 60%, 저공해 1종·플러그인하이브리드 2시간 면제 뒤 "
                             "50%, 의왕시 거주자 행락지 30%를 함께 적고 있다."),
                },
                {
                    "id": "news", "name": "시민일보 — 의왕시, 고천문화공원 공영주차장 운영 개시",
                    "org": "시민일보(2026-03-30 보도)", "url": UW_NEWS_URL,
                    "file": UW_NEWS_TXT.name if UW_NEWS_TXT.exists() else None,
                    "sha256": sha256(UW_NEWS_TXT) if UW_NEWS_TXT.exists() else None,
                    "license": "언론 보도(참고용)", "base_date": "2026-03-30",
                    "rows_total": None, "fetched_at": _sync_time(UW_NEWS_TXT),
                    "note": ("고천문화공원 공영주차장(100면, 문화공원로 27)을 2026-04-01 정식 운영하고 "
                             "4월 한 달 무료 시범 운영 뒤 5월부터 유료로 전환한다고 보도했다 — "
                             "표준데이터가 ‘무료’로 남아 있는 이유를 설명한다."),
                },
                {
                    "id": "sys", "name": "의왕시 통합주차정보시스템(서비스 일시 중단 안내)",
                    "org": "의왕시 교통정책과", "url": UW_SYS_URL,
                    "file": UW_SYS_TXT.name if UW_SYS_TXT.exists() else None,
                    "sha256": sha256(UW_SYS_TXT) if UW_SYS_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지", "base_date": "조회 2026-11-17",
                    "rows_total": None, "fetched_at": _sync_time(UW_SYS_TXT),
                    "note": ("2026-11-17 조회 시 실시간 주차정보 대신 ‘주차정보 서비스 일시 중단 안내’ "
                             "페이지만 열려, 실시간 잔여면수는 연동하지 않았다(realtime: false)."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in UW_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "uiwang_grade",
            "base_min": UW_BASE_MIN,
            "unit_min": UW_UNIT_MIN,
            "free_min": UW_FREE_MIN,
            "applies": UW_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "상업지역", "base": 800, "unit": 300, "day": 8_000,
                 "month": 85_000, "night": 60_000, "lots": 0},
                {"grade": 2, "where": "공업지역·주거지역", "base": 600, "unit": 200, "day": 6_000,
                 "month": 50_000, "night": 45_000, "lots": 0},
                {"grade": 3, "where": "개발제한구역을 포함한 자연녹지지역", "base": 500, "unit": 200,
                 "day": 5_000, "month": 40_000, "night": 35_000, "lots": 0},
            ],
            "street": [
                {"grade": 1, "base": 800, "unit": 300, "day": 8_000, "month": 85_000, "night": None},
                {"grade": 2, "base": 600, "unit": 200, "day": 6_000, "month": 50_000, "night": None},
                {"grade": 3, "base": 500, "unit": 200, "day": 5_000, "month": 40_000, "night": None},
            ],
            "park": {"bands": [dict(b) for b in UW_PARK_BANDS], "month": UW_PARK_MONTH,
                     "night": UW_PARK_NIGHT, "free_min": UW_FREE_MIN,
                     "lots": len([l for l in lots if l["fee"].get("grade_label") == "행락지"])},
            "paid_window": {"weekday": "09:00~20:00", "weekend": "09:00~18:00",
                            "free": "일요일·공휴일 무료 원칙(노외·행락지는 요금 부과 가능)"},
            "corp": {
                "paid": len([l for l in lots if l["fee"]["type"] == "유료"]),
                "free": len([l for l in lots if l["fee"]["type"] == "무료"]),
                "free_spaces": sum(l["spaces"] or 0 for l in lots if l["fee"]["type"] == "무료"),
                "night_free": len(night_free),
                "weekend_free": len(weekend_free),
            },
            "lots": [
                {"name": l["name"], "dong": l["dong"], "ptype": l["ptype"],
                 "grade": l["fee"].get("grade"), "grade_label": l["fee"].get("grade_label"),
                 "free": l["fee"].get("free_min"), "base": l["fee"].get("base_fee"),
                 "base_min": l["fee"].get("base_min"),
                 "unit": l["fee"].get("unit_fee"), "unit_min": l["fee"].get("unit_min"),
                 "day": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "basis": ("「의왕시 주차장설치 및 관리 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({UW_ORDINANCE_NOTE}) · 의왕도시공사 공영주차장 요금안내(2026-11-17 확인)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["의왕시"] | {
        "city": "의왕시",
        "weekend_free_pages": False,
        "discounts": UW_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "uiwang_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_uiwang(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                         note_fixed, reclassified, month_diff, night_free, weekend_free,
                         grade_from_corp, park_from_rule, std_grade_diff, pay_fixed):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    free = [l for l in lots if l["fee"]["type"] == "무료"]
    park = [l for l in lots if l["fee"].get("grade_label") == "행락지"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_의왕시행수": len([r for r in rows if (r.get("주차장구분") or "").strip() == "공영"]),
        "원자료_전체행수": len(rows),
        "민영_제외": len([e for e in excluded if "민영" in e["reason"]]),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "행락지_주차장": [l["name"] for l in park],
        "행락지_출처": ("「의왕시 주차장설치 및 관리 조례」 별표1 비고7 · 의왕도시공사 감면안내"
                        "(행락지 목록에 백운호수 공원1·2 포함)"),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in paid
                                     if l["fee"].get("std_grade"))),
        "유료_노상": len([l for l in paid if l["ptype"] == "노상"]),
        "유료_노외": len([l for l in paid if l["ptype"] == "노외"]),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "등록값_차이": note_fixed,
        "요금구분_보정": reclassified,
        "정기권_차이": month_diff,
        "야간무료_주차장": night_free,
        "주말무료_주차장": weekend_free,
        "급지_보정": grade_from_corp,
        "결제_보정": pay_fixed,
        "급지_없음_보정": std_grade_diff,
        "행락지_지정": park_from_rule,
        "감면_출처": "「의왕시 주차장설치 및 관리 조례」 별표2(제5조제1항) · 의왕도시공사 감면안내",
        "무료시간_출처": "조례 별표2 제1호 마목(10분 미만 공영주차장 이용차량 전액 면제)",
        "주말무료_출처": ("의왕도시공사 요금안내 각주(내손주차빌딩·의왕역·고천주민센터·백운커뮤니티 "
                          "주차타워·서울외곽순환하부 ‘야간 20:00~익일 08:00, 주말, 공휴일’ / 청계산 "
                          "‘주말, 공휴일’ / 노상 왕곡천복개·오전천복개 휴무일 ‘토·일요일, 공휴일"
                          "(무료운영)’·조례 별표1 비고2"),
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len(free),
        "무료_구획수": sum(l["spaces"] or 0 for l in free),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- main
# ---------------------------------------------------------------- 여주시 (T-03 Phase 25)
YEOJU_PROVIDER = "경기도 여주시"
# 여주시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
YEOJU_DISTRICTS = [("여주시", "yeoju")]
YEOJU_BBOX = (37.10, 37.50, 127.40, 127.80)   # 여주시 대략 경계(좌표 점검용)
# 여주시 법정동·읍·면 — 주소의 ‘경기도 여주시 ○○동|○○읍|○○면 번지’ 세 번째 낱말을 쓴다.
#   여주시는 1읍(가남읍) 8면(점동·세종대왕·흥천·금사·산북·대신·북내·강천)과
#   여흥동·중앙동·오학동 3개 행정동(법정동 홍문동·창동·상동·하동·현암동·오학동 등)으로 이루어진다.
YEOJU_UNIT_SUFFIX = ("읍", "면", "동")

YEOJU_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2049793"
                    "&gubun=ELIS&conDatGubunCd=1")
YEOJU_HALL_ORD_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1997205"
                   "&gubun=ELIS&conDatGubunCd=0")
YEOJU_CORP_URL = "https://yeojuuc.or.kr/sub1/parking/public.do"
YEOJU_HALL_URL = "https://yeojuuc.or.kr/sub1/parking/cityhall.do"
YEOJU_ORD_HWP = RAW / "yeoju.law.go.kr_주차장조례_20261117.hwp"
YEOJU_ORD_TXT = RAW / "yeoju.law.go.kr_주차장조례_별표5_20261117.txt"
YEOJU_HALL_HWP = RAW / "yeoju.law.go.kr_공공청사부설주차장조례_20261117.hwp"
YEOJU_HALL_TXT = RAW / "yeoju.law.go.kr_공공청사부설주차장조례_별표1_20261117.txt"
YEOJU_CORP_TXT = RAW / "yeojuuc.or.kr_공영주차장_20261117.txt"
YEOJU_HALLP_TXT = RAW / "yeojuuc.or.kr_시청부설주차장_20261117.txt"
YEOJU_ORDINANCE_NOTE = ("시행 2025-06-30 · 경기도여주시조례 제1434호(일부개정) · "
                     "별표5·별표6 〈개정 2025.6.30.〉")
YEOJU_HALL_NOTE = ("시행 2024-12-18 · 경기도여주시조례 제1399호(일부개정) · "
                "별표1 〈개정 2024.12.18.〉")
YEOJU_BASE_MIN = 60
YEOJU_UNIT_MIN = 10
YEOJU_FREE_MIN = 60

# 여주시 공영주차장 요금 — 「여주시 주차장 조례」 [별표 5] 공영주차장 주차요금표
#   (시행 2025-06-30, 경기도여주시조례 제1434호 · 별표5〈개정 2025.6.30.〉, 조례 HWP의 표를 읽음).
#   · 1급지: 최초 60분 이내 무료 → 60분 초과 시 10분마다 200원 · 1일 주차요금 6,000원 ·
#     월 정기 주차요금 60,000원
#   · 2급지: 최초 60분 이내 무료 → 10분마다 100원 · 1일 3,000원 · 월 40,000원
#   · 비고1: 여주한글시장 공영주차장과 노상주차장(시청삼거리~홍문현대교차로 구간)만 1일·월 요금을
#     빼고 1구획당 요금기준(60분 무료·10분당 200원)만 적용한다.
#   · 비고2: 1급지 = 동 및 읍지역 도시계획구역, 2급지 = 1급지 이외의 지역 — 여주 유료 주차장은
#     모두 동·읍 지역이라 전부 1급지다.
#   · 비고5: 최초 60분 이하 무료, 60분 초과분 계산에서 10분 미만은 10분으로 본다.
#   · 비고6: 1일 주차요금·월 정기요금이 시간 요금의 상한이 된다.
#   · 제9조(징수시간): 평일 10:00~19:00, 토요일 10:00~15:00, 일요일·공휴일 무료.
YEOJU_FEES = {
    1: {"unit": 200, "day": 6_000, "month": 60_000},
    2: {"unit": 100, "day": 3_000, "month": 40_000},
}
# 「여주시 공공청사 부설주차장 관리 운영 조례」 [별표 1](시행 2024-12-18, 제1399호) — 시청부설주차장
#   최초 40분까지 무료 → 40분 초과 1시간 이내 500원 → 1시간 초과 시 10분마다 300원.
#   유료 운영시간은 평일 09:00~18:30이고, 1일·월 주차권은 두지 않는다(제3조의2).
YEOJU_HALL_FEE = {"free_min": 40, "base_min": 60, "base_fee": 500, "unit_min": 10, "unit_fee": 300}
# 요금을 받는 시간 — 여주도시공사 공영주차장 안내의 ‘유료 운영시간’(2026-11-17 조회).
#   · 한글·창동·여흥동 노외주차장: 월~일 08:00~19:00 (휴무: 공휴일)
#   · 하동·하동제일시장·가남읍1·가남읍2: 월~금 10:00~19:00 (휴무: 토·일, 공휴일)
#   · 노상주차장: 월~금 10:00~19:00 (휴무: 토·일, 공휴일)
#   공사 표의 ‘휴무’는 요금을 받지 않는 날이라는 뜻이라 무료 개방으로 옮겼다(조례 제9조 3호도
#   일요일·공휴일을 무료로 정한다). 공사 표는 공휴일 칸이 따로 없어 일요일과 함께 무료로 둔다.
YEOJU_HOURS_A = {"한글시장 주차장", "창동공영주차장(주차타워)", "여흥동 공영주차장"}
YEOJU_HOURS_B = {"하동 공영주차장", "하동제일시장", "가남읍 1공영주차장", "가남읍 2공영주차장"}
YEOJU_HOURS_WEEKDAY = {"시민회관공영주차장"}      # 표준데이터 평일 10:00~19:00 · 토·공휴일 휴무
YEOJU_HALL_NAME = "시청부설주차장"
# 표준데이터가 ‘무료’로 등록했지만 여주도시공사가 유료로 운영하는 주차장.
#   공사 안내의 유료 운영시간 표에 ‘하동, 하동제일주차장, 가남읍1, 가남읍2: 월~금 10:00~19:00’이
#   들어 있고, 이용요금도 같은 표(60분 무료·10분당 200원·1일 6,000원)를 쓴다.
YEOJU_RECLASSIFIED = {"가남읍 1공영주차장", "가남읍 2공영주차장"}
# 1일·월 주차요금을 받지 않는 주차장(조례 별표5 비고1) — 한글시장 공영주차장과 세종로 노상 구간
#   (시청삼거리~홍문현대교차로)이다. 공사 안내도 ‘한글시장주차장 및 노상주차장(시청삼거리~홍문현대교차로)
#   1일 주차권 폐지’라고 적는다.
YEOJU_NO_DAY_TICKET_STREET = "세종로("
# 여주도시공사가 따로 안내하는 주차장별 면수(2026-11-17 조회) — 표준데이터와 다른 곳이 있다.
YEOJU_CORP_SPACES = {
    "한글시장 주차장": 173,          # 표준 184면
    "창동공영주차장(주차타워)": 193,  # 표준 209면
    "여흥동 공영주차장": 415,        # 표준 423면
    "하동 공영주차장": 53,           # 표준 56면
    "하동제일시장": 262,             # 표준 119면
    "가남읍 1공영주차장": 70,        # 표준 71면
    "가남읍 2공영주차장": 47,        # 표준 48면
    "시청부설주차장": 83,            # 표준 93면
}
# 표준데이터 이름 → 여주도시공사 안내의 주차장 이름(카드에 함께 적는다).
YEOJU_CORP_NAME = {
    "한글시장 주차장": "한글시장주차장",
    "창동공영주차장(주차타워)": "창동타워주차장",
    "여흥동 공영주차장": "여흥동공영주차장",
    "하동 공영주차장": "하동공영주차장",
    "하동제일시장": "하동제일시장주차장",
    "가남읍 1공영주차장": "가남읍1주차장",
    "가남읍 2공영주차장": "가남읍2주차장",
}
# 여주도시공사 노상주차장 안내의 구간·면수(2026-11-17 조회) — 표준데이터는 세종로를 11개 구간으로,
#   공사는 좌·우 10개 구간으로 나누고 강변·청심로 2개 구간을 더한다(경찰서·여흥동주민센터는 미운영).
YEOJU_CORP_STREET = {"세종로": (10, 142), "강변로": (1, 80), "청심로": (2, 32)}
#   여흥로(여흥동사무소~여흥초교 후문) 구간은 공사 안내의 ‘여흥동주민센터 13면(미운영)’과 같은 곳으로 보여
#   구간 안내를 붙이지 않았다(표준데이터에만 유료 구간으로 등록).

# 여주시 주차요금 감면 — 「여주시 주차장 조례」 [별표 6](제6조제1항 관련)과 여주도시공사 감면안내.
#   22개 항목을 계산기에서 고를 수 있는 갈래로 묶었다. 감면은 중복 적용하지 않고 비율이 높은
#   하나만 적용하며, 감면 대상자는 면제시간을 넘긴 시간의 요금을 계산할 때 ‘최초 60분 무료’를
#   적용하지 않는다(조례 제6조④, 2025.6.30. 신설).
YEOJU_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "국가유공자 6시간 면제 후 50%", "rate": 0.5, "exempt_min": 360,
     "note": ("국가유공자 증서 소지자가 본인 자동차를 직접 운전하거나 장애 정도가 심해 동승하고 "
              "타인에게 대리운전을 맡긴 경우(수권유족 포함) — 1일 1회 6시간 면제 뒤 50%")},
    {"label": "장애인(심한)·5·18·고엽제·참전 등 3시간 면제 후 50%", "rate": 0.5, "exempt_min": 180,
     "note": ("장애 정도가 심한 장애인, 5·18민주화운동부상자, 고엽제후유의증 환자, 참전유공자, "
              "만 75세 이상 여주시 거주 고령노인(본인 운전), 새마을지도자·새마을부녀지도자, "
              "이장·통장, 대한노인회 여주시지회장·분회장·마을별 노인회장, 장기기증자·기증희망자와 "
              "법정 유가족 1인, 임산부 — 3시간 면제 뒤 50%")},
    {"label": "경차·저공해·다자녀·병역명문가 등 50%", "rate": 0.5, "exempt_min": 0,
     "note": ("경형자동차(1,000cc 미만), 환경친화적 자동차(전기차 제외), 저공해자동차 표지 부착 차량, "
              "2자녀(막내 만 18세 이하) 이상 다자녀세대, 부양세대 등록 차량, 병역명문가 차량, "
              "장애 정도가 심하지 않은 장애인 — 50%")},
    {"label": "전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "환경친화적 자동차 가운데 전기차 — 최초 2시간 면제 뒤 50%(별표6 제15호)"},
    {"label": "전통시장 상인·고객 2시간 면제", "rate": 0.0, "exempt_min": 120,
     "note": ("「전통시장 및 상점가 육성을 위한 특별법」 제19조제1항에 따른 주차장에서 상인·고객이 "
              "주차하는 경우 — 2시간 면제(영수증 등 구입 증빙 제시). 한글시장·하동제일시장 카드 참고")},
    {"label": "자가용 부제·함께타기 20%", "rate": 0.2, "exempt_min": 0,
     "note": "국가·자치단체장이 발행한 자가용 부제 및 함께타기 표지부착 차량 — 20% 감면"},
    {"label": "긴급·성실납세자 등 100%", "rate": 1.0, "exempt_min": 0,
     "note": ("긴급자동차, 성실납세자·유공납세자 인증서 교부일부터 1년(표지·인증서 부착 차량) — 면제. "
              "시청부설주차장은 민원업무·의정활동·청사 유지보수 방문 차량도 해당 부서 확인으로 면제")},
]


def _yeoju_fix_unit(unit: str):
    """주소의 지역 이름을 바로잡는다 — 표준데이터가 ‘가납읍’으로 잘못 적은 행이 있다(가남읍)."""
    if unit == "가납읍":
        return "가남읍"
    return unit


def yeoju_dong_of(text: str, fixes=None):
    """주소에서 여주시 법정동·읍·면을 뽑는다 — ‘경기도 여주시 {동|읍|면} {번지}’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "여주시":
        cand = parts[2]
        if cand.endswith(YEOJU_UNIT_SUFFIX) and not cand.endswith(("로동", "가동")):
            fixed = _yeoju_fix_unit(cand)
            if fixes is not None and fixed != cand:
                fixes.append(f"{text}: 주소의 ‘{cand}’을 ‘{fixed}’으로 바로잡음"
                             f"(가남읍 태평리 일대 — 같은 읍의 다른 주차장 주소와 대조)")
            return fixed
    return None


def yeoju_fee(grade: int = 1, pay: str = "", *, no_day_ticket: bool = False, basis_extra: str = ""):
    """여주시 공영주차장 요금 → 사이트 공통 fee 객체.

    별표5는 ‘최초 60분 무료 → 60분 초과 시 10분마다 200원’이므로 기본요금 0원·무료 60분·
    10분당 200원으로 넣는다(60분까지 0원, 61~70분 200원, 90분 600원).
    """
    t = YEOJU_FEES[grade]
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": grade, "grade_label": None, "std_grade": None,
        "base_min": YEOJU_BASE_MIN, "base_fee": 0,
        "unit_min": YEOJU_UNIT_MIN, "unit_fee": t["unit"],
        "steps": None, "steps_label": None,
        "free_min": YEOJU_FREE_MIN, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 별표5 1일 주차요금",
        "daily_hours": None,
        "daily_fee": None if no_day_ticket else t["day"],
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None if no_day_ticket else t["month"],
        "monthly_day": None, "monthly_night": None,
        "monthly_all": None if no_day_ticket else t["month"], "monthly_label": None,
        "pay": pay,
        "basis": (f"「여주시 주차장 조례」 별표5 {grade}급지(최초 {YEOJU_FREE_MIN}분 무료 · "
                  f"{YEOJU_UNIT_MIN}분당 {t['unit']:,}원"
                  + ("" if no_day_ticket else f" · 1일 {t['day']:,}원 · 월 {t['month']:,}원")
                  + f"){basis_extra}"),
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def yeoju_hall_fee(pay: str = ""):
    """시청부설주차장 요금 — 공공청사 부설주차장 조례 별표1(40분 무료 → 1시간 500원 → 10분당 300원)."""
    f = YEOJU_HALL_FEE
    return {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": None, "grade_label": "청사 부설", "std_grade": None,
        "base_min": f["base_min"], "base_fee": f["base_fee"],
        "unit_min": f["unit_min"], "unit_fee": f["unit_fee"],
        "steps": None, "steps_label": None,
        "free_min": f["free_min"], "deduct_min": None,
        "cap_fee": None, "cap_src": None,
        "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None,
        "monthly_all": None, "monthly_label": None,
        "pay": pay,
        "basis": ("「여주시 공공청사 부설주차장 관리 운영 조례」 별표1(최초 40분 무료 · "
                  "40분 초과 1시간 이내 500원 · 1시간 초과 10분당 300원)"),
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def yeoju_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "grade_label": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def yeoju_hm(m: int) -> str:
    h, mi = divmod(int(m), 60)
    return f"{h:02d}:{mi:02d}"


def yeoju_window(start, end):
    return {"open": True, "start": start, "end": end, "24h": False, "listed": True,
            "raw": [yeoju_hm(start), yeoju_hm(end)]}


def build_yeoju():
    """여주시 공영주차장을 표준데이터 + 여주시 조례 별표5·6 + 여주도시공사 안내로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 여주시 범위를 벗어난 행은 제외(껍데기 행).
      · 표준데이터 40행은 모두 공영(민영 등록 없음)이라 민영 제외는 일어나지 않는다.
      · 여주시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동·읍·면 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 동·읍·면만 만든다.
    요금은 조례 별표5(최초 60분 무료 → 10분당 200원, 1일 6,000원, 월 60,000원)를 쓰고,
    운영시간은 여주도시공사 ‘유료 운영시간’으로 정리한다(표준데이터는 유료 행도 00:00~23:59로
    등록되어 있다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == YEOJU_PROVIDER]
    lots, excluded, merged = [], [], []
    hour_fixed, space_diff, note_fixed, reclassified, month_diff = [], [], [], [], []
    addr_fixed, dup_mgmt, no_ticket, hall_note = [], [], [], []

    # 같은 지번에 무료·유료로 두 번 등록된 행은 유료 행만 남긴다(시흥시와 같은 규칙).
    by_jibun = defaultdict(list)
    for r in rows_city:
        key = re.sub(r"\s+", "", (r.get("소재지지번주소") or ""))
        if key:
            by_jibun[key].append(r)
    drop = set()
    for key, rows in by_jibun.items():
        paid_rows = [r for r in rows if (r.get("요금정보") or "").strip() in ("유료", "혼합")]
        free_rows = [r for r in rows if (r.get("요금정보") or "").strip() == "무료"]
        if paid_rows and free_rows and len(rows) == len(paid_rows) + len(free_rows):
            for r in free_rows:
                drop.add(id(r))
                merged.append({
                    "kept": (paid_rows[0].get("주차장명") or "").strip(),
                    "dropped": (r.get("주차장명") or "").strip(),
                    "reason": (f"같은 지번({(r.get('소재지지번주소') or '').strip()})에 유료·무료로 두 번 등록 — "
                               f"유료로 운영하는 ‘{(paid_rows[0].get('주차장명') or '').strip()}’만 실었다"),
                })

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                notice=None, tel="", mgmt="", lat=None, lng=None, base_date="",
                free_days=None, free_note=None):
        street = ptype == "노상"
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "여주시",
            "dong": dong,
            "dong_src": ("지번주소" if r and yeoju_dong_of((r.get("소재지지번주소") or "")) else
                         ("도로명주소" if r and yeoju_dong_of((r.get("소재지도로명주소") or "")) else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "여주도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": (fee["free_min"] if fee["type"] == "유료" else None),
            "city": "여주시",
            "city_slug": "yeoju",
        })

    for r in rows_city:
        if id(r) in drop:
            continue
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        gubun = (r.get("주차장구분") or "").strip()
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if gubun == "민영":
            excluded.append({"name": name or "(이름 없음)", "reason": "민영 주차장(공영 아님)"})
            continue
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not (YEOJU_BBOX[0] <= lat <= YEOJU_BBOX[1] and YEOJU_BBOX[2] <= lng <= YEOJU_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        if "가납읍" in jibun:
            jibun = jibun.replace("가납읍", "가남읍")
            if not any("가납읍" in x for x in addr_fixed):
                addr_fixed.append(f"{name}: 지번주소의 ‘가납읍’을 ‘가남읍’으로 바로잡음"
                                  f"(가남읍 태평리 일대 — 같은 읍의 다른 주차장 주소와 대조)")
        dong = yeoju_dong_of(jibun, addr_fixed) or yeoju_dong_of(road, addr_fixed)
        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        pay = (r.get("결제방법") or "").strip()
        fee_type = (r.get("요금정보") or "").strip()
        std_grade = (r.get("급지구분") or "").strip()
        grade = to_int(std_grade) or 1
        grade = min(max(grade, 1), 2)
        notice_bits = []
        free_days = {"sat": False, "sun": False}
        free_note = None
        is_hall = name == YEOJU_HALL_NAME
        corp_name = YEOJU_CORP_NAME.get(name)

        paid = fee_type in ("유료", "혼합") or name in YEOJU_RECLASSIFIED
        if fee_type not in ("유료", "혼합") and name in YEOJU_RECLASSIFIED:
            reclassified.append(
                f"{name}: 표준데이터 요금정보 ‘{fee_type or '무료'}’ ↔ 여주도시공사가 유료로 운영"
                f"(유료 운영시간 표에 10:00~19:00, 이용요금 60분 무료·10분당 200원·1일 6,000원) — 유료로 바로잡음")
            notice_bits.append(
                "공공데이터 표준데이터에는 ‘무료’로 등록되어 있지만, 여주도시공사가 "
                "월~금 10:00~19:00 유료로 운영합니다(60분 무료·10분당 200원·1일 6,000원)")

        if paid and is_hall:
            fee = yeoju_hall_fee(pay)
            win = {"weekday": yeoju_window(9 * 60, 18 * 60 + 30),
                   "sat": yeoju_window(9 * 60, 18 * 60 + 30),
                   "sun": yeoju_window(9 * 60, 18 * 60 + 30)}
            oper = {"weekday": True, "sat": True, "sun": True}
            free_days = {"sat": True, "sun": True}
            free_note = ("토요일·일요일·공휴일은 청사 휴무일로 무료(개방하지 않음)입니다 — "
                         "유료 운영시간은 평일 09:00~18:30입니다")
            hour_fixed.append(
                f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                f"공공청사 부설주차장 조례 제3조의2 평일 09:00~18:30")
            notice_bits.append(
                "「여주시 공공청사 부설주차장 관리 운영 조례」 별표1 요금입니다 — 최초 40분까지 무료, "
                "40분 초과 1시간 이내 500원, 1시간 초과 시 10분마다 300원(1일·월 주차권 없음)")
            notice_bits.append(
                "민원업무·의정활동·청사 유지보수 등 업무로 방문한 차량은 해당 부서 확인으로 면제됩니다"
                "(별표2 제2~4호)")
            hall_note.append(name)
        elif paid:
            no_day_ticket = (name == "한글시장 주차장" or (street and name.startswith(YEOJU_NO_DAY_TICKET_STREET)))
            fee = yeoju_fee(grade, pay=pay, no_day_ticket=no_day_ticket)
            if no_day_ticket:
                no_ticket.append(name)
                notice_bits.append(
                    "조례 별표5 비고1에 따라 이 주차장은 1일 주차요금과 월 정기 주차요금을 받지 않고 "
                    "1구획당 요금기준(60분 무료·10분당 200원)만 적용합니다 — 여주도시공사도 "
                    "‘1일 주차권 폐지’를 안내 합니다")
            daily_std = to_int(r.get("1일주차권요금")) or 0
            month_std = to_int(r.get("월정기권요금")) or 0
            base_min_std = to_int(r.get("주차기본시간"))
            base_fee_std = to_int(r.get("주차기본요금"))
            fee["std"] = {"base_min": base_min_std, "base_fee": base_fee_std,
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily_std, "monthly": month_std}
            want = YEOJU_FEES[grade]
            if fee_type in ("유료", "혼합") and (
                    (base_min_std, base_fee_std) != (YEOJU_BASE_MIN, 0) or
                    (to_int(r.get("추가단위요금")) or 0) != want["unit"]):
                note_fixed.append(
                    f"{name}: 표준데이터 기본 {base_min_std or '-'}분 {base_fee_std or 0:,}원·"
                    f"추가 {to_int(r.get('추가단위시간')) or '-'}분 "
                    f"{to_int(r.get('추가단위요금')) or 0:,}원 ↔ 조례 별표5 {grade}급지 "
                    f"최초 {YEOJU_BASE_MIN}분 무료·{YEOJU_UNIT_MIN}분당 {want['unit']:,}원"
                    f"(2025-06-30 개정 전 등록값)")
            if not no_day_ticket and month_std and month_std != want["month"]:
                month_diff.append(f"{name}: 표준데이터 월정기권 {month_std:,}원 ↔ 별표5 "
                                  f"{grade}급지 {want['month']:,}원")
            if not no_day_ticket and daily_std and daily_std != want["day"]:
                note_fixed.append(f"{name}: 표준데이터 1일주차권요금 {daily_std:,}원 ↔ 별표5 "
                                  f"{grade}급지 1일 {want['day']:,}원")
            # 요금을 받는 시간 — 여주도시공사 유료 운영시간 표
            if name in YEOJU_HOURS_A:
                win = {"weekday": yeoju_window(8 * 60, 19 * 60),
                       "sat": yeoju_window(8 * 60, 19 * 60),
                       "sun": yeoju_window(8 * 60, 19 * 60)}
                oper = {"weekday": True, "sat": True, "sun": True}
                free_days = {"sat": False, "sun": True}
                free_note = ("여주도시공사 안내: 월~일 08:00~19:00에 요금을 받고, 공휴일은 휴무(무료)입니다. "
                             "조례 제9조 3호는 일요일·공휴일을 무료로 정하고 있어 일요일·공휴일은 무료로 계산합니다"
                             " — 일요일은 현장 안내를 확인하세요")
                hour_fixed.append(
                    f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                    f"여주도시공사 월~일 08:00~19:00(공휴일 휴무)")
            else:
                start, end = (9 * 60, 18 * 60 + 30) if is_hall else (10 * 60, 19 * 60)
                win = {"weekday": yeoju_window(start, end),
                       "sat": yeoju_window(start, end),
                       "sun": yeoju_window(start, end)}
                oper = {"weekday": True, "sat": True, "sun": True}
                free_days = {"sat": True, "sun": True}
                if name in YEOJU_HOURS_B:
                    free_note = ("여주도시공사 안내: 하동·하동제일시장·가남읍1·가남읍2는 월~금 "
                                 "10:00~19:00에만 요금을 받고 토요일·일요일·공휴일은 휴무(무료)입니다")
                elif name in YEOJU_HOURS_WEEKDAY:
                    free_note = ("여주도시공사 유료 주차장 목록에는 없고 표준데이터에만 평일 "
                                 "10:00~19:00 유료로 등록되어 있습니다 — 토요일·일요일·공휴일은 "
                                 "요금을 받지 않습니다(현장 확인 권장)")
                else:
                    free_note = ("여주도시공사 안내: 노상주차장은 월~금 10:00~19:00에만 요금을 받고 "
                                 "토요일·일요일·공휴일은 휴무(무료)입니다")
                hour_fixed.append(
                    f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                    f"여주도시공사 월~금 10:00~19:00(토·일·공휴일 휴무)")
            notice_bits.append(
                f"「여주시 주차장 조례」 별표5 {grade}급지 요금입니다 — 최초 {YEOJU_FREE_MIN}분 무료, "
                f"60분이 지나면 {YEOJU_UNIT_MIN}분마다 {want['unit']:,}원"
                + ("" if no_day_ticket else f", 1일 주차요금 {want['day']:,}원, 월 정기 {want['month']:,}원"))
            if (r.get("특기사항") or "").strip():
                notice_bits.append((r.get("특기사항") or "").strip().replace("50퍼센트", "50%"))
            if name in YEOJU_CORP_SPACES and YEOJU_CORP_SPACES[name] != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 여주도시공사 {YEOJU_CORP_SPACES[name]}면")
                notice_bits.append(
                    f"표준데이터 등록면수는 {spaces}면이고, 여주도시공사 안내는 "
                    f"{YEOJU_CORP_SPACES[name]}면입니다")
            if name == "시민회관공영주차장":
                notice_bits.append(
                    "여주도시공사 공영주차장 안내의 유료 주차장 8곳에는 들어 있지 않고, 표준데이터에만 "
                    "유료(평일 10:00~19:00)로 등록되어 있습니다 — 현장 확인 권장")
        else:
            fee = yeoju_free_fee()
            # 무료 주차장은 표준데이터의 운영시간을 그대로 쓴다(대부분 24시간).

        if street and paid:
            corp = YEOJU_CORP_STREET.get((name or "").split("(")[0])
            if corp:
                segs, seg_spaces = corp
                notice_bits.append(
                    f"여주도시공사는 이 도로의 노상주차장을 {segs}개 구간 {seg_spaces}면으로 안내합니다"
                    f"(표준데이터는 구간을 도로별로 나누어 등록)")
        if corp_name and corp_name != name:
            notice_bits.append(f"여주도시공사 안내에는 ‘{corp_name}’으로 적혀 있습니다")

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=" · ".join(b for b in notice_bits if b) or None,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "여주도시공사"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    # 관리번호가 같은 행이 둘(현암동·오학동 공영주차장이 237-2-000018) — 이름이 달라 그대로 두고 기록만 한다.
    for no, cnt in Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no")).items():
        if cnt > 1:
            names = "·".join(l["name"] for l in lots if l.get("mgmt_no") == no)
            dup_mgmt.append(f"관리번호 {no}가 {names} 두 곳에 같은 값으로 등록되어 있습니다(이름·주소·좌표가 달라 그대로 실음)")

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"yju-{i:03d}" if l["list_mode"] == "card" else f"yju-s{i:03d}"

    quality = check_quality_yeoju(rows_all, rows_city, lots, excluded, merged,
                                  hour_fixed, space_diff, note_fixed, reclassified,
                                  month_diff, addr_fixed, dup_mgmt, no_ticket)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "여주시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-13",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 22:03 (KST)",
                    "note": ("경기도 여주시가 등록한 40행(노외 23·노상 16·부설 1)을 읽었다. 모두 주차장구분이 "
                             "‘공영’이라 민영 주차장은 없다. 요금 구분은 유료 23행(노외 6·노상 16·부설 1)과 "
                             "무료 17행이지만, 표준데이터가 ‘무료’로 등록한 가남읍 1·2공영주차장은 "
                             "여주도시공사가 유료로 운영해 유료로 바로잡았다. 또 상동 357에 같은 지번으로 "
                             "무료(보건소옆무료주차장)·유료(여흥동 공영주차장) 두 번 등록된 1행은 유료 행만 "
                             "남겼다. 주차구획수가 비어 있는 껍데기 행은 없었다."),
                },
                {
                    "id": "ordinance",
                    "name": ("여주시 주차장 조례 [별표 5] 공영주차장 주차요금표 · "
                             "[별표 6] 주차요금 감면대상 및 비율"),
                    "org": "여주시청 교통과(031-887-3357) · 여주도시공사 공영주차장(031-880-4031~2)",
                    "url": YEOJU_ORDINANCE_URL,
                    "file": YEOJU_ORD_HWP.name if YEOJU_ORD_HWP.exists() else YEOJU_ORD_TXT.name,
                    "sha256": (sha256(YEOJU_ORD_HWP) if YEOJU_ORD_HWP.exists()
                               else sha256(YEOJU_ORD_TXT) if YEOJU_ORD_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": YEOJU_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(YEOJU_ORD_TXT),
                    "note": ("국가법령정보센터 자치법규 HWP를 내려받아 표 셀을 읽어 정리본(txt)을 두었다. "
                             "1급지 최초 60분 무료·60분 초과 시 10분마다 200원·1일 주차요금 6,000원·"
                             "월 정기 60,000원, 2급지 100·3,000·40,000원이고, 비고1은 여주한글시장 "
                             "공영주차장과 노상(시청삼거리~홍문현대교차로)에 1일·월 요금을 적용하지 "
                             "않는다. 비고5는 최초 60분 이하 무료·10분 미만은 10분으로, 비고6은 1일·월 "
                             "요금을 상한으로 정한다. 제9조는 평일 10:00~19:00·토요일 10:00~15:00·"
                             "일요일·공휴일 무료를 징수시간으로 정한다. 별표6은 22개 감면 항목이다."),
                },
                {
                    "id": "hall", "name": ("여주시 공공청사 부설주차장 관리 운영 조례 "
                                           "[별표 1] 주차장 주차요금표 · [별표 2] 감면"),
                    "org": "여주시청 총무과(031-887-2610)",
                    "url": YEOJU_HALL_ORD_URL,
                    "file": YEOJU_HALL_HWP.name if YEOJU_HALL_HWP.exists() else YEOJU_HALL_TXT.name,
                    "sha256": (sha256(YEOJU_HALL_HWP) if YEOJU_HALL_HWP.exists()
                               else sha256(YEOJU_HALL_TXT) if YEOJU_HALL_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": YEOJU_HALL_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(YEOJU_HALL_TXT),
                    "note": ("시청부설주차장에 적용하는 별도 조례다. 최초 40분까지 무료, 40분 초과 1시간 "
                             "이내 500원, 1시간 초과 시 10분마다 300원이고(단위시간 미만은 10분으로), "
                             "유료 운영시간은 평일 09:00~18:30이다. 별표2는 민원업무·의정활동·청사 "
                             "유지보수 방문 차량의 면제를 포함해 24개 항목을 정한다."),
                },
                {
                    "id": "corp", "name": "여주도시공사 공영주차장 안내(주차장 소개·유료 운영시간·이용요금·감면)",
                    "org": "여주도시공사 공영주차장(031-880-4031~2)",
                    "url": YEOJU_CORP_URL,
                    "file": YEOJU_CORP_TXT.name if YEOJU_CORP_TXT.exists() else None,
                    "sha256": sha256(YEOJU_CORP_TXT) if YEOJU_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 22, "fetched_at": _sync_time(YEOJU_CORP_TXT),
                    "note": ("노상주차장 14개 구간(경찰서·여흥동주민센터 2곳은 미운영)과 노외주차장 8곳의 "
                             "면수, 유료 운영시간(한글·창동·여흥동 월~일 08:00~19:00, 하동·하동제일·"
                             "가남읍1·2 월~금 10:00~19:00, 노상 월~금 10:00~19:00, 공휴일 휴무), 이용요금"
                             "(최초 60분 무료·10분마다 200원·1일 6,000원)과 ‘한글시장 및 노상(시청삼거리~"
                             "홍문현대교차로) 1일 주차권 폐지’를 적고 있다. 감면은 조례 별표6과 같은 22개 "
                             "항목이다."),
                },
                {
                    "id": "hallp", "name": "여주도시공사 시청부설주차장 안내(이용시간·이용요금·면수)",
                    "org": "여주도시공사 공영주차장(031-880-4031~2)",
                    "url": YEOJU_HALL_URL,
                    "file": YEOJU_HALLP_TXT.name if YEOJU_HALLP_TXT.exists() else None,
                    "sha256": sha256(YEOJU_HALLP_TXT) if YEOJU_HALLP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 1, "fetched_at": _sync_time(YEOJU_HALLP_TXT),
                    "note": ("시청부설주차장은 월~금 09:00~18:30(토·일·공휴일 휴무), 최초 40분 무료·"
                             "40분 초과 1시간 이내 500원·1시간 초과 10분마다 300원, 82면(일반 63·장애인 5·"
                             "임산부·어르신 2·경차 7·버스 1·전기차 4)이다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in YEOJU_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "yeoju_grade",
            "base_min": YEOJU_BASE_MIN,
            "unit_min": YEOJU_UNIT_MIN,
            "free_min": YEOJU_FREE_MIN,
            "applies": YEOJU_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "동 및 읍지역 도시계획구역", "unit": 200, "day": 6_000,
                 "month": 60_000, "lots": 0},
                {"grade": 2, "where": "1급지 이외의 지역", "unit": 100, "day": 3_000,
                 "month": 40_000, "lots": 0},
            ],
            "hall": {"name": YEOJU_HALL_NAME, "free_min": YEOJU_HALL_FEE["free_min"],
                     "base_fee": YEOJU_HALL_FEE["base_fee"], "unit_fee": YEOJU_HALL_FEE["unit_fee"],
                     "window": "평일 09:00~18:30", "spaces": 93, "applies": YEOJU_HALL_NOTE},
            "windows": [
                {"group": "한글시장·창동타워·여흥동 공영", "hours": "월~일 08:00~19:00",
                 "free": "공휴일 휴무(무료)"},
                {"group": "하동·하동제일시장·가남읍1·가남읍2", "hours": "월~금 10:00~19:00",
                 "free": "토·일·공휴일 휴무(무료)"},
                {"group": "노상주차장", "hours": "월~금 10:00~19:00",
                 "free": "토·일·공휴일 휴무(무료)"},
                {"group": "시청부설주차장", "hours": "평일 09:00~18:30",
                 "free": "토·일·공휴일 휴무(무료)"},
            ],
            "no_ticket": sorted(no_ticket),
            "corp": {
                "paid_out": len([l for l in lots if l["list_mode"] == "card"
                                 and l["fee"]["type"] == "유료"]),
                "free_out": len([l for l in lots if l["list_mode"] == "card"
                                 and l["fee"]["type"] == "무료"]),
                "street": len([l for l in lots if l["list_mode"] == "street"]),
            },
            "lots": [
                {"name": l["name"], "dong": l["dong"], "ptype": l["ptype"],
                 "grade": l["fee"].get("grade") or l["fee"].get("grade_label"),
                 "free": l["fee"].get("free_min"), "unit": l["fee"].get("unit_fee"),
                 "base": l["fee"].get("base_fee"),
                 "day": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "basis": ("「여주시 주차장 조례」 [별표 5] 공영주차장 주차요금표"
                      f"({YEOJU_ORDINANCE_NOTE}) · 「여주시 공공청사 부설주차장 관리 운영 조례」 [별표 1]"
                      f"({YEOJU_HALL_NOTE}) · 여주도시공사 공영주차장 안내(2026-11-17 확인)"),
        },
    }
    card_paid = Counter(l["fee"]["grade"] for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade"))
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload.update(CITY_META["여주시"] | {
        "city": "여주시",
        "weekend_free_pages": False,
        "discounts": YEOJU_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "yeoju_parking.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_yeoju(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                        note_fixed, reclassified, month_diff, addr_fixed, dup_mgmt, no_ticket):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    free = [l for l in lots if l["fee"]["type"] == "무료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_여주시행수": len([r for r in rows if (r.get("주차장구분") or "").strip() == "공영"]),
        "원자료_전체행수": len(rows),
        "민영_제외": len([e for e in excluded if "민영" in e["reason"]]),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in paid
                                     if l["fee"].get("std_grade"))),
        "유료_노상": len([l for l in paid if l["ptype"] == "노상"]),
        "유료_노외": len([l for l in paid if l["ptype"] == "노외"]),
        "유료_부설": len([l for l in paid if l["ptype"] == "부설"]),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "등록값_차이": note_fixed,
        "요금구분_보정": reclassified,
        "정기권_차이": month_diff,
        "주소_보정": addr_fixed,
        "관리번호_중복": dup_mgmt,
        "1일권_없음": no_ticket,
        "감면_출처": ("「여주시 주차장 조례」 별표6(제6조제1항) · 여주도시공사 감면안내 · "
                      "「여주시 공공청사 부설주차장 관리 운영 조례」 별표2(청사 부설)"),
        "무료시간_출처": "조례 별표5 공영주차장 주차요금표(최초 60분 이내 무료) · 청사 부설주차장 조례 별표1(최초 40분)",
        "주말무료_출처": ("여주도시공사 유료 운영시간(휴무: 공휴일 / 토·일·공휴일) · "
                          "조례 제9조 3호(일요일·공휴일 무료)"),
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len(free),
        "무료_구획수": sum(l["spaces"] or 0 for l in free),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 동두천시 (T-03 Phase 26)
DDC_PROVIDER = "경기도 동두천시"
# 동두천시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
DDC_DISTRICTS = [("동두천시", "dongducheon")]
DDC_BBOX = (37.82, 37.99, 126.96, 127.20)   # 동두천시 대략 경계(좌표 점검용)
# 동두천시 법정동 — 주소의 ‘경기도 동두천시 ○○동 번지’ 세 번째 낱말을 쓴다.
#   행정동은 8개(생연1·2동, 중앙동, 보산동, 불현동, 송내동, 소요동, 상패동)이고,
#   법정동은 생연동·송내동·지행동·동두천동·보산동·탑동동·상패동·광암동 등이다.
DDC_UNIT_SUFFIX = ("동",)

DDC_ORDINANCE_URL = ("https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=2127619"
                     "&gubun=ELIS&conDatGubunCd=1")
DDC_CORP_URL = "https://www.ddcsiseol.or.kr/main/content/view/MN02040000.do"
DDC_CITY_URL = "https://www.ddc.go.kr/ddc/contents.do?key=242"
DDC_ORD_HWP = RAW / "ddc.law.go.kr_주차장조례_별표1_20261117.hwp"
DDC_ORD_TXT = RAW / "ddc.law.go.kr_주차장조례_별표1_20261117.txt"
DDC_CORP_TXT = RAW / "ddcsiseol.or.kr_공영주차장_20261117.txt"
DDC_CITY_TXT = RAW / "ddc.go.kr_공영주차장_20261117.txt"
DDC_ORDINANCE_NOTE = ("시행 2026-05-06 · 경기도동두천시조례 제2628호(일부개정) · "
                      "별표1〈개정 2025.11.18.〉")
DDC_BASE_MIN = 30
DDC_UNIT_MIN = 10
DDC_FREE_MIN = 10          # 별표1 ※ ‘입차 후 최초 10분까지는 무료’
DDC_2H_FREE_MIN = 120      # 별표1 ‘2시간 무료 주차 허용 노외주차장’

# 동두천시 공영주차장 요금 — 「동두천시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금표
#   (시행 2026-05-06, 경기도동두천시조례 제2628호 · 별표1〈개정 2025.11.18.〉, 조례 HWP의 표를 읽음).
#   · 노상 1급지: 최초 30분 700원 · 30분 초과 10분마다 300원 · 2시간 초과 15분마다 700원 (1일·월 없음)
#   · 노상 2급지: 최초 30분 500원 · 10분마다 200원 · 2시간 초과 15분마다 500원
#   · 노외 1급지: 최초 30분 600원 · 30분 초과 10분마다 200원 · 1일 6,000원 · 월 50,000원
#   · 노외 2급지: 최초 30분 500원 · 30분 초과 10분마다 200원 · 1일 4,000원 · 월 40,000원
#   · 2시간 무료 주차 허용 노외주차장(2급지에 한함): 최초 2시간 무료 · 이후 10분마다 400원,
#     1일·월 요금은 2급지 값(4,000원·40,000원)
#   · 대형자동차 공영주차장: 소형 30분 500원·10분당 200원·1일 4,000원·월 40,000원,
#     중형·대형 30분 600원·10분당 200원·1일 8,000원·월 100,000원
#   · 비고 2: 노상 3~10월 08:00~20:00·11~2월 09:00~19:00, 노외 주간 09:00~20:00·야간 20:00~익일 09:00
#   · 비고 3: 1급지 = 상업지역 중 교통혼잡역세권(지행역 주변), 2급지 = 1급지를 제외한 상업·준주거·주거지역
#   · 비고 5: 주차시간 10분 미만은 10분으로 본다.
#   · ※ 입차 후 최초 10분까지는 무료(회차 차량 고려)
DDC_FEES = {
    1: {"base": 600, "unit": 200, "day": 6_000, "month": 50_000},
    2: {"base": 500, "unit": 200, "day": 4_000, "month": 40_000},
}
DDC_FEE_2H = {"free_min": 120, "unit": 400, "day": 4_000, "month": 40_000}
DDC_BIG = {
    "소형": {"base": 500, "unit": 200, "day": 4_000, "month": 40_000},
    "중형·대형": {"base": 600, "unit": 200, "day": 8_000, "month": 100_000},
}
# 유료 주차장 요금 갈래 — 동두천시 시설관리공단 ‘(유료) 노외주차장 현황’(2026-11-17 조회)과
#   표준데이터의 기본·추가 요금이 같은 곳만 골라 배정했다.
DDC_GRADE1 = {"송내1주차장", "송내4주차장"}            # 1급지(지행역 주변) 30분 600원
DDC_2H_LOTS = {                                        # 2시간 무료 뒤 10분당 400원
    "큰시장 공영주차장", "중앙동 공영주차장", "송내2주차장", "송내3주차장",
    "송내지구 공영주차장", "미2사단 보산동 공영주차장", "생연로일원 공영주차장",
    "동두천중앙역세권", "5060청춘로드 주차장",
}
DDC_BIG_LOTS = {"대형자동차 공영주차장(소형)": "소형", "대형자동차 공영주차장(대형)": "중형·대형"}
# 요금을 받는 시간 — 공단 ‘(유료) 노외주차장 현황’의 운영시간(2026-11-17 조회)
DDC_HOURS_DAY = {"송내1주차장", "송내4주차장"}          # 09:00~22:00 (월~일)
DDC_HOURS_BIG = {"대형자동차 공영주차장(소형)", "대형자동차 공영주차장(대형)"}   # 08:00~21:00 (월~토)
#   나머지 유료 주차장은 09:00~20:00 (월~토)이고, 일요일·공휴일은 요금을 받지 않는다.
#   공단 표의 운영시간은 ‘요금을 받는 시간’이라 그 밖의 시간(야간 20:00~익일 09:00)은
#   요금을 받지 않는다(조례 별표1 비고2의 주간·야간 구분).
# 공단이 정기권을 판매하는 7곳(송내4·송내지구·중앙동·상패동 대형·보산동·생연로 일원·중앙역세권)의
#   월 정기요금. 나머지 유료 주차장은 공단 정기권 판매 대상이 아니라 월 요금을 비운다.
DDC_MONTHLY = {
    "송내4주차장": 50_000, "송내지구 공영주차장": 40_000, "중앙동 공영주차장": 40_000,
    "대형자동차 공영주차장(대형)": 100_000, "미2사단 보산동 공영주차장": 40_000,
    "생연로일원 공영주차장": 40_000, "동두천중앙역세권": 40_000,
}
# 표준데이터가 ‘무료’로 등록했지만 공단이 유료로 운영하는 주차장(2시간 무료 뒤 10분당 400원).
DDC_RECLASSIFIED = {"송내3주차장"}
# 공단 안내와 표준데이터가 다른 면수 — 등록면수를 쓰고 카드에 차이를 적는다.
DDC_CORP_SPACES = {"송내3주차장": 14, "대형자동차 공영주차장(소형)": 44, "대형자동차 공영주차장(대형)": 136}
# 공단 안내의 위치(지번) — 표준데이터 지번과 다른 곳.
DDC_CORP_ADDR = {
    "미2사단 보산동 공영주차장": "경기도 동두천시 보산동 441-3",
    "대형자동차 공영주차장(대형)": "경기도 동두천시 상패동 370",
    "대형자동차 공영주차장(소형)": "경기도 동두천시 상패동 370",
}
# 표준데이터에만 유료로 등록되어 있고 공단 유료 노외주차장 11곳 목록에는 없는 곳.
DDC_NOT_IN_CORP = {"5060청춘로드 주차장"}

# 동두천시 주차요금 감면 — 「동두천시 주차장 설치 및 관리 조례」 제7조(주차요금의 감면).
#   면제: 긴급자동차, 국가유공자·유족, 고엽제후유증·후유의증환자와 2세, 5·18민주화운동 부상자,
#         시장이 필요하다고 인정하는 공공행사·공무수행·공휴일 이용차량·성실모범납세필증 차량.
#   경감 50%: 장애인, 경형자동차, 저공해자동차, 다자녀(미성년 2자녀 이상),
#         요일제·임산부·자원봉사자·장기기증 등 시책 참여 차량, 병역명문가, 장기복무 제대군인.
#   전기자동차: 2시간 무료 뒤 50%.
#   원도심·재래시장 활성화를 위해 시장이 필요하다고 인정하면 공영주차장 2시간 이내 무료주차 허용.
DDC_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "국가유공자·유족·고엽제·5·18부상자 면제", "rate": 1.0, "exempt_min": 0,
     "note": ("국가유공자 증서, 고엽제후유증·후유의증 환자·2세 증명서, 5·18민주유공자증을 "
              "소지한 사람의 자가운전차량 및 동승차량 — 면제(제7조 제1항 제1호 나~라목)")},
    {"label": "긴급·공무수행·공휴일·성실납세자 면제", "rate": 1.0, "exempt_min": 0,
     "note": ("긴급자동차, 공무수행 차량, 공휴일 이용차량, 시가 주최·후원하는 공공 목적 행사 차량, "
              "성실모범납세필증 부착 차량 — 면제(제7조 제1항 제1호 가목·마목)")},
    {"label": "장애인 50%", "rate": 0.5, "exempt_min": 0,
     "note": "장애인등록증을 소지한 장애인의 자가운전차량 및 동승차량 — 50%"},
    {"label": "경차 50%", "rate": 0.5, "exempt_min": 0,
     "note": "「자동차관리법」 제3조에 따른 경형자동차 — 50%"},
    {"label": "저공해차 50%", "rate": 0.5, "exempt_min": 0,
     "note": "저공해자동차 표지부착차량 — 50%(전기자동차는 따로 2시간 무료 뒤 50%)"},
    {"label": "다자녀(미성년 2자녀 이상) 50%", "rate": 0.5, "exempt_min": 0,
     "note": "자동차 소유주가 다자녀(미성년 2자녀 이상) 가구임을 증명하는 자동차 — 50%"},
    {"label": "요일제·임산부·자원봉사·장기기증 50%", "rate": 0.5, "exempt_min": 0,
     "note": ("시장이 실시하는 시책 참여 차량 — 요일제 스티커 부착차량, 모자보건수첩 등 임산부 증빙 제시차량, "
              "경기도·시 우수 자원봉사자증 제시차량, 장기 및 인체조직 기증 등록증 제시차량 — 50%")},
    {"label": "병역명문가·장기복무 제대군인 50%", "rate": 0.5, "exempt_min": 0,
     "note": ("병역명문가증과 주소가 기입된 신분증을 제시하는 사람의 차량, 장기복무 제대군인으로서 "
              "국가보훈등록증을 증명하는 차량 — 50%(2025-11-18 신설)")},
    {"label": "전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "「자동차관리법」 제10조에 따른 전기자동차 — 최초 2시간 무료 뒤 50%(제7조 제1항 제2호 바목)"},
]


def ddc_dong_of(text: str):
    """주소에서 동두천시 법정동을 뽑는다 — ‘경기도 동두천시 ○○동 번지’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "동두천시":
        cand = parts[2]
        if cand.endswith(DDC_UNIT_SUFFIX) and not cand.endswith(("로동", "가동")):
            return cand
    return None


def ddc_hm(m: int) -> str:
    h, mi = divmod(int(m), 60)
    return f"{h:02d}:{mi:02d}"


def ddc_window(start, end):
    return {"open": True, "start": start, "end": end, "24h": False, "listed": True,
            "raw": [ddc_hm(start), ddc_hm(end)]}


def ddc_fee(*, grade: int = 2, two_hour: bool = False, big: str = None, pay: str = "",
            monthly=None):
    """동두천시 공영주차장 요금 → 사이트 공통 fee 객체.

    별표1은 ‘최초 30분 기본요금 → 30분 초과 10분마다 200원’이고, 입차 후 최초 10분은 무료다.
    2시간 무료 주차 허용 노외주차장은 최초 120분 무료 뒤 10분당 400원(1일·월은 2급지 값)이라
    기본요금 0원·무료 120분으로 넣는다(120분까지 0원, 130분 400원, 150분 1,200원).
    """
    common = {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": None, "grade_label": None, "std_grade": None,
        "steps": None, "steps_label": None, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 별표1 1일 주차요금",
        "daily_hours": None, "prepaid_day": None, "prepaid_weekend": None,
        "monthly_day": None, "monthly_night": None, "monthly_all": monthly, "monthly_label": None,
        "pay": pay, "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }
    if big:
        t = DDC_BIG[big]
        return {**common,
                "grade_label": f"대형자동차 {big}",
                "base_min": DDC_BASE_MIN, "base_fee": t["base"],
                "unit_min": DDC_UNIT_MIN, "unit_fee": t["unit"],
                "free_min": DDC_FREE_MIN,
                "daily_fee": t["day"], "monthly": monthly,
                "basis": (f"「동두천시 주차장 설치 및 관리 조례」 별표1 대형자동차 공영주차장 "
                          f"{big}(최초 30분 {t['base']:,}원 · 30분 초과 {DDC_UNIT_MIN}분당 "
                          f"{t['unit']:,}원 · 1일 {t['day']:,}원"
                          + (f" · 월 {monthly:,}원" if monthly else "") + ")")}
    if two_hour:
        t = DDC_FEE_2H
        return {**common,
                "grade": 2,
                "base_min": DDC_FEE_2H["free_min"], "base_fee": 0,
                "unit_min": DDC_UNIT_MIN, "unit_fee": t["unit"],
                "free_min": DDC_FEE_2H["free_min"],
                "daily_fee": t["day"], "monthly": monthly,
                "basis": (f"「동두천시 주차장 설치 및 관리 조례」 별표1 2시간 무료 주차 허용 "
                          f"노외주차장(2급지 한정 · 최초 {DDC_2H_FREE_MIN}분 무료 · 이후 "
                          f"{DDC_UNIT_MIN}분당 {t['unit']:,}원 · 1일 {t['day']:,}원"
                          + (f" · 월 {monthly:,}원" if monthly else "") + ")")}
    t = DDC_FEES[grade]
    return {**common,
            "grade": grade,
            "base_min": DDC_BASE_MIN, "base_fee": t["base"],
            "unit_min": DDC_UNIT_MIN, "unit_fee": t["unit"],
            "free_min": DDC_FREE_MIN,
            "daily_fee": t["day"], "monthly": monthly,
            "basis": (f"「동두천시 주차장 설치 및 관리 조례」 별표1 노외 {grade}급지"
                      f"(최초 30분 {t['base']:,}원 · 30분 초과 {DDC_UNIT_MIN}분당 {t['unit']:,}원 · "
                      f"1일 {t['day']:,}원" + (f" · 월 {monthly:,}원" if monthly else "") + ")")}


def ddc_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "grade_label": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def build_dongducheon():
    """동두천시 공영주차장을 표준데이터 + 동두천시 조례 별표1 + 시설관리공단 안내로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 동두천시 범위를 벗어난 행은 제외(껍데기 행).
      · 표준데이터 64행은 모두 공영(민영 등록 없음)이라 민영 제외는 일어나지 않는다.
      · 동두천시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    요금은 조례 별표1을 쓰고, 유료 주차장의 요금 갈래·운영시간은 공단 ‘(유료) 노외주차장 현황’으로
    대조한다(표준데이터는 유료 행도 기본·추가 요금만 등록되어 있고 운영시간이 24시간으로 되어 있다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == DDC_PROVIDER]
    lots, excluded, merged = [], [], []
    hour_fixed, space_diff, note_fixed, reclassified, month_diff = [], [], [], [], []
    addr_fixed, dup_mgmt, no_ticket, big_note = [], [], [], []

    def add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=None,
                notice=None, tel="", mgmt="", lat=None, lng=None, base_date="",
                free_days=None, free_note=None):
        street = ptype == "노상"
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "동두천시",
            "dong": dong,
            "dong_src": ("지번주소" if r and ddc_dong_of((r.get("소재지지번주소") or "")) else
                         ("도로명주소" if r and ddc_dong_of((r.get("소재지도로명주소") or "")) else "없음")),
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "동두천시 시설관리공단",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": (fee["free_min"] if fee["type"] == "유료" else None),
            "city": "동두천시",
            "city_slug": "dongducheon",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        gubun = (r.get("주차장구분") or "").strip()
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if gubun == "민영":
            excluded.append({"name": name or "(이름 없음)", "reason": "민영 주차장(공영 아님)"})
            continue
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not (DDC_BBOX[0] <= lat <= DDC_BBOX[1] and DDC_BBOX[2] <= lng <= DDC_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = ddc_dong_of(jibun) or ddc_dong_of(road)
        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        pay = (r.get("결제방법") or "").strip()
        fee_type = (r.get("요금정보") or "").strip()
        std_grade = (r.get("급지구분") or "").strip()
        notice_bits = []
        free_days = {"sat": False, "sun": False}
        free_note = None
        is_big = name in DDC_BIG_LOTS
        is_2h = name in DDC_2H_LOTS

        paid = fee_type in ("유료", "혼합") or name in DDC_RECLASSIFIED
        if fee_type not in ("유료", "혼합") and name in DDC_RECLASSIFIED:
            reclassified.append(
                f"{name}: 표준데이터 요금정보 ‘{fee_type or '무료'}’ ↔ 동두천시 시설관리공단이 유료로 운영"
                f"(유료 노외주차장 현황 5번, 14면·09:00~20:00 월~토·2시간 무료·2시간 초과 10분당 400원"
                f"·1일 4,000원) — 유료로 바로잡음")
            notice_bits.append(
                "공공데이터 표준데이터에는 ‘무료’로 등록되어 있지만, 동두천시 시설관리공단이 "
                "유료(09:00~20:00 월~토, 2시간 무료·2시간 초과 10분당 400원·1일 4,000원)로 운영합니다")

        if paid:
            if is_big:
                big = DDC_BIG_LOTS[name]
                fee = ddc_fee(big=big, pay=pay, monthly=DDC_MONTHLY.get(name))
                big_note.append(name)
                notice_bits.append(
                    "「동두천시 주차장 설치 및 관리 조례」 별표1 대형자동차 공영주차장 요금입니다 — "
                    f"최초 30분 {DDC_BIG[big]['base']:,}원, 30분 초과 10분마다 200원"
                    + (f", 1일 {DDC_BIG[big]['day']:,}원" if big == "중형·대형" else ""))
            elif is_2h:
                fee = ddc_fee(two_hour=True, pay=pay, monthly=DDC_MONTHLY.get(name))
                notice_bits.append(
                    "조례 별표1의 ‘2시간 무료 주차 허용 노외주차장’(2급지에 한함) 요금입니다 — "
                    "최초 2시간 무료, 2시간이 지나면 10분마다 400원, 1일 주차요금 4,000원")
            else:
                grade = 1 if name in DDC_GRADE1 else 2
                fee = ddc_fee(grade=grade, pay=pay, monthly=DDC_MONTHLY.get(name))
                notice_bits.append(
                    f"「동두천시 주차장 설치 및 관리 조례」 별표1 노외 {grade}급지 요금입니다 — "
                    f"최초 30분 {DDC_FEES[grade]['base']:,}원, 30분 초과 10분마다 200원, "
                    f"1일 주차요금 {DDC_FEES[grade]['day']:,}원"
                    + (f", 월 정기 {DDC_FEES[grade]['month']:,}원" if DDC_MONTHLY.get(name) else ""))
            fee["std_grade"] = std_grade or None
            daily_std = to_int(r.get("1일주차권요금")) or 0
            month_std = to_int(r.get("월정기권요금")) or 0
            base_min_std = to_int(r.get("주차기본시간"))
            base_fee_std = to_int(r.get("주차기본요금"))
            fee["std"] = {"base_min": base_min_std, "base_fee": base_fee_std,
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily_std, "monthly": month_std}
            # 표준데이터 등록값과 조례 별표1이 다르면 기록한다.
            std_tuple = (base_min_std, base_fee_std, to_int(r.get("추가단위요금")) or 0)
            want_tuple = ((DDC_FEE_2H["free_min"], 0, 400) if is_2h
                          else (DDC_BASE_MIN, DDC_BIG[DDC_BIG_LOTS[name]]["base"] if is_big
                                else DDC_FEES[1 if name in DDC_GRADE1 else 2]["base"], 200))
            if std_tuple != want_tuple:
                note_fixed.append(
                    f"{name}: 표준데이터 기본 {base_min_std or '-'}분 {base_fee_std or 0:,}원·"
                    f"추가 {to_int(r.get('추가단위시간')) or '-'}분 {to_int(r.get('추가단위요금')) or 0:,}원 "
                    f"↔ 조례 별표1 {want_tuple[0]}분 {want_tuple[1]:,}원·10분당 {want_tuple[2]:,}원")
            if is_2h and std_grade and std_grade != "2":
                note_fixed.append(f"{name}: 표준데이터 급지 {std_grade} ↔ 2시간 무료 요금제는 2급지 한정"
                                  f"(별표1) — 공단 요금이 2시간 무료·10분당 400원이라 2급지로 실음")
            if not DDC_MONTHLY.get(name) and month_std:
                month_diff.append(f"{name}: 표준데이터 월정기권 {month_std:,}원 ↔ 공단 정기권 판매 7곳에 없음")
            # 요금을 받는 시간 — 공단 운영시간대로 정리한다.
            if name in DDC_HOURS_DAY:
                win = {"weekday": ddc_window(9 * 60, 22 * 60),
                       "sat": ddc_window(9 * 60, 22 * 60),
                       "sun": ddc_window(9 * 60, 22 * 60)}
                oper = {"weekday": True, "sat": True, "sun": True}
                free_days = {"sat": False, "sun": True}
                hour_fixed.append(
                    f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                    f"공단 09:00~22:00(월~일)·일요일·공휴일 무료")
            elif is_big:
                win = {"weekday": ddc_window(8 * 60, 21 * 60),
                       "sat": ddc_window(8 * 60, 21 * 60),
                       "sun": ddc_window(8 * 60, 21 * 60)}
                oper = {"weekday": True, "sat": True, "sun": True}
                free_days = {"sat": False, "sun": True}
                hour_fixed.append(
                    f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                    f"공단 08:00~21:00(월~토)·일요일·공휴일 무료")
            else:
                win = {"weekday": ddc_window(9 * 60, 20 * 60),
                       "sat": ddc_window(9 * 60, 20 * 60),
                       "sun": ddc_window(9 * 60, 20 * 60)}
                oper = {"weekday": True, "sat": True, "sun": True}
                free_days = {"sat": False, "sun": True}
                hour_fixed.append(
                    f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                    f"공단 09:00~20:00(월~토)·일요일·공휴일 무료")
            night_from = "22:00" if name in DDC_HOURS_DAY else ("21:00" if is_big else "20:00")
            notice_bits.append(
                f"입차 후 최초 10분은 무료입니다(조례 별표1 ※). {night_from} 이후 야간과 일요일·공휴일은 "
                "요금을 받지 않습니다(조례 별표1 비고2의 주간·야간 구분, 제7조 제1항 제1호 마목 "
                "‘공휴일 이용차량’ 면제)")
            if name in DDC_HOURS_DAY:
                notice_bits.append(
                    "공단 운영시간은 월~일 09:00~22:00이라 일요일도 여는 주차장입니다 — 일요일 요금은 "
                    "현장 안내를 확인하세요(동두천시는 일요일·공휴일 무료로 안내해 왔습니다)")
            if not DDC_MONTHLY.get(name) and name != "송내1주차장":
                notice_bits.append(
                    "조례 별표1의 월 정기요금은 있지만, 동두천시 시설관리공단이 정기권을 판매하는 "
                    "7곳(송내4·송내지구·중앙동·상패동 대형·보산동·생연로 일원·중앙역세권)에는 들지 않습니다")
            if name in DDC_CORP_SPACES and DDC_CORP_SPACES[name] != spaces:
                space_diff.append(f"{name}: 표준데이터 {spaces}면 ↔ 공단 {DDC_CORP_SPACES[name]}면")
                notice_bits.append(
                    f"표준데이터 등록면수는 {spaces}면이고, 공단 안내는 {DDC_CORP_SPACES[name]}면입니다")
            if name in DDC_CORP_ADDR:
                notice_bits.append(f"공단 안내 위치는 {DDC_CORP_ADDR[name]}입니다")
            if name in DDC_NOT_IN_CORP:
                notice_bits.append(
                    "공단 ‘(유료) 노외주차장 현황’ 11곳에는 없고 표준데이터에만 유료(2시간 무료·"
                    "10분당 400원·1일 4,000원)로 등록되어 있습니다 — 현장 확인 권장")
            if name == "송내1주차장":
                notice_bits.append(
                    "공단 정기권 판매 대상은 아니고, 일 주차요금만 받습니다"
                    "(조례 1급지 월 정기요금 50,000원은 송내4에 적용)")
            if is_big:
                notice_bits.append(
                    "표준데이터는 이 주차장을 대형·소형 두 행(136면·48면)으로 나누어 등록했고, "
                    "공단은 184면(대형 136·소형 44) 한 곳으로 안내합니다")
            if name == "미2사단 보산동 공영주차장":
                notice_bits.append(
                    "공단은 ‘출차 전 무인정산기 결제, 2시간 무료 외 모든 감면·면제 대상 해당’을 안내합니다")
        else:
            fee = ddc_free_fee()
            # 무료 주차장은 표준데이터의 운영시간을 그대로 쓴다(대부분 24시간).
            if street:
                notice_bits.append(
                    "동두천시가 노상주차장을 무료로 운영합니다(동두천시 홈페이지 ‘노상주차장(무료)’ 26개소 "
                    "816면·공단 전체 현황 25개소 825면). 조례 별표1에는 노상 1급지 700원·2급지 500원 "
                    "기준이 있으나 현재 요금을 받지 않습니다")

        spec = (r.get("특기사항") or "").strip()
        if spec:
            spec = spec.replace("50퍼센트", "50%")
            spec = re.sub(r"\s*\+\s*", " · ", spec)
            notice_bits.append(f"표준데이터 특기사항: {spec}")

        add_lot(name, jibun, road, ptype, spaces, dong, win, oper, fee, r=r,
                notice=" · ".join(b for b in notice_bits if b) or None,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "동두천시 시설관리공단"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note)

    for no, cnt in Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no")).items():
        if cnt > 1:
            names = "·".join(l["name"] for l in lots if l.get("mgmt_no") == no)
            dup_mgmt.append(f"관리번호 {no}가 {names} 두 곳에 같은 값으로 등록되어 있습니다")

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"ddc-{i:03d}" if l["list_mode"] == "card" else f"ddc-s{i:03d}"

    quality = check_quality_dongducheon(rows_all, rows_city, lots, excluded, merged,
                                        hour_fixed, space_diff, note_fixed, reclassified,
                                        month_diff, addr_fixed, dup_mgmt, no_ticket)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "동두천시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-23",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 22:03 (KST)",
                    "note": ("경기도 동두천시가 등록한 64행(노외 39·노상 25)을 읽었다. 모두 주차장구분이 "
                             "‘공영’이라 민영 주차장은 없다. 요금 구분은 유료 12행(모두 노외)과 무료 52행"
                             "(노외 27·노상 25)인데, 표준데이터가 ‘무료’로 등록한 송내3 공영주차장은 "
                             "시설관리공단이 유료로 운영해 유료로 바로잡았다. 노외 39곳의 등록면수 합계 "
                             "1,599면은 공단 전체 현황의 노외 1,599면과 같고, 노상 25구간 812면은 시 "
                             "홈페이지 26개소 816면과 1곳(동두천중앙역 3번출구 4면)만큼 다르다. "
                             "주차구획수가 비어 있는 껍데기 행은 없었다."),
                },
                {
                    "id": "ordinance",
                    "name": "동두천시 주차장 설치 및 관리 조례 [별표 1] 공영주차장 주차요금표 · 제7조 감면",
                    "org": "동두천시청 교통행정과(031-860-2293)",
                    "url": DDC_ORDINANCE_URL,
                    "file": DDC_ORD_HWP.name if DDC_ORD_HWP.exists() else DDC_ORD_TXT.name,
                    "sha256": (sha256(DDC_ORD_HWP) if DDC_ORD_HWP.exists()
                               else sha256(DDC_ORD_TXT) if DDC_ORD_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": DDC_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(DDC_ORD_TXT),
                    "note": ("국가법령정보센터 자치법규 별표 HWP를 내려받아 표 셀과 비고를 읽어 정리본(txt)을 "
                             "두었다. 노외 1급지 최초 30분 600원·10분당 200원·1일 6,000원·월 50,000원, "
                             "2급지 500·200·4,000·40,000원, 2시간 무료 주차 허용 노외(2급지 한정)는 "
                             "최초 2시간 무료 뒤 10분당 400원, 대형자동차는 소형 500·200·4,000·40,000원, "
                             "중형·대형 600·200·8,000·100,000원이다. ※ 입차 후 최초 10분 무료, 비고2 "
                             "운영시간(노외 주간 09:00~20:00), 비고3 급지(1급지 지행역 주변 상업지역), "
                             "비고5 10분 미만 10분 계산. 제7조는 면제 4종과 50% 경감 8종, 전기차 "
                             "2시간 무료 뒤 50%, 재래시장 2시간 무료 허용을 정한다."),
                },
                {
                    "id": "corp", "name": "동두천시 시설관리공단 공영주차장 현황·정기권 안내",
                    "org": "동두천시 시설관리공단 시설관리팀(031-865-6004)",
                    "url": DDC_CORP_URL,
                    "file": DDC_CORP_TXT.name if DDC_CORP_TXT.exists() else None,
                    "sha256": sha256(DDC_CORP_TXT) if DDC_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 12, "fetched_at": _sync_time(DDC_CORP_TXT),
                    "note": ("전체 공영주차장 64개소 2,934면(환승 2·106면, 노상 25·825면, 노외 36·1,599면 "
                             "가운데 유료 11·893면, 무료 25·706면)과 유료 노외주차장 12행(시청 부설 포함)의 "
                             "면수·운영시간·요금을 적고 있다. 2시간 무료 주차장은 09:00~20:00 월~토, "
                             "송내1·4는 09:00~22:00 월~일, 상패동 대형자동차는 08:00~21:00 월~토, "
                             "시청 부설은 08:00~18:00 월~금이다. 정기권은 7곳(송내4 50,000원·송내지구·"
                             "중앙동·보산동·생연로 일원·중앙역세권 40,000원·상패동 대형 100,000원)에서만 "
                             "판매한다."),
                },
                {
                    "id": "city", "name": "동두천시 홈페이지 공영주차장 안내(노상·무료 노외·기타 관리부서)",
                    "org": "동두천시 교통행정과(031-860-2293)",
                    "url": DDC_CITY_URL,
                    "file": DDC_CITY_TXT.name if DDC_CITY_TXT.exists() else None,
                    "sha256": sha256(DDC_CITY_TXT) if DDC_CITY_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 82, "fetched_at": _sync_time(DDC_CITY_TXT),
                    "note": ("공영주차장 총 82개소 3,768면(노상 26·816면, 유료 노외 11·708면, 무료 노외 23·716면, "
                             "기타 부서 22·1,525면)을 안내한다. 노상주차장은 모두 무료이고, 무료 노외주차장 "
                             "목록에 동두천역 환승주차장(68면)이 들어 있다. 시청 부설주차장(방죽로 23)은 "
                             "기타 부서 주차장(349면)으로 표기되며 공단이 199면을 유료로 운영한다 — "
                             "표준데이터에는 없어 카드로 만들지 않고 자주 묻는 질문에 안내했다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in DDC_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "dongducheon_grade",
            "base_min": DDC_BASE_MIN,
            "unit_min": DDC_UNIT_MIN,
            "free_min": DDC_FREE_MIN,
            "applies": DDC_ORDINANCE_NOTE,
            "off": [
                {"grade": 1, "where": "상업지역 중 교통혼잡역세권(지행역 주변)",
                 "base": 600, "unit": 200, "day": 6_000, "month": 50_000, "lots": 0},
                {"grade": 2, "where": "그 밖의 상업·준주거·주거지역",
                 "base": 500, "unit": 200, "day": 4_000, "month": 40_000, "lots": 0},
            ],
            "two_hour": {"where": "2급지에 한함", "free_min": DDC_2H_FREE_MIN,
                         "unit": DDC_FEE_2H["unit"], "day": DDC_FEE_2H["day"],
                         "month": DDC_FEE_2H["month"], "lots": 0},
            "big": [
                {"kind": "소형", "base": 500, "unit": 200, "day": 4_000, "month": 40_000, "lots": 0},
                {"kind": "중형·대형", "base": 600, "unit": 200, "day": 8_000, "month": 100_000, "lots": 0},
            ],
            "street": [
                {"grade": 1, "base": 700, "unit": 300, "after": 700},
                {"grade": 2, "base": 500, "unit": 200, "after": 500},
            ],
            "windows": [
                {"group": "송내1·송내4 공영(1급지)", "hours": "월~일 09:00~22:00",
                 "free": "일요일·공휴일 무료"},
                {"group": "2시간 무료 주차장(2급지)", "hours": "월~토 09:00~20:00",
                 "free": "일요일·공휴일 무료 · 야간(20:00~09:00) 무료"},
                {"group": "상패동 대형자동차 공영주차장", "hours": "월~토 08:00~21:00",
                 "free": "일요일·공휴일 무료 · 야간 무료"},
                {"group": "동두천시청 부설주차장(공단)", "hours": "월~금 08:00~18:00",
                 "free": "토·일·공휴일 무료"},
            ],
            "monthly_sold": sorted(DDC_MONTHLY),
            "corp": {
                "paid_out": len([l for l in lots if l["list_mode"] == "card"
                                 and l["fee"]["type"] == "유료"]),
                "free_out": len([l for l in lots if l["list_mode"] == "card"
                                 and l["fee"]["type"] == "무료"]),
                "street": len([l for l in lots if l["list_mode"] == "street"]),
            },
            "lots": [
                {"name": l["name"], "dong": l["dong"], "ptype": l["ptype"],
                 "grade": l["fee"].get("grade") or l["fee"].get("grade_label"),
                 "free": l["fee"].get("free_min"), "unit": l["fee"].get("unit_fee"),
                 "base": l["fee"].get("base_fee"),
                 "day": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "basis": ("「동두천시 주차장 설치 및 관리 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({DDC_ORDINANCE_NOTE}) · 제7조 주차요금의 감면 · 동두천시 시설관리공단 "
                      "공영주차장 현황(2026-11-17 확인)"),
        },
    }
    # 급지 요금표의 ‘이 사이트 유료 주차장’은 그 급지의 기본 요금을 쓰는 곳만 센다 —
    #   2시간 무료 주차 허용 노외주차장은 따로 표를 두므로 여기서 빼고 센다.
    card_paid = Counter(l["fee"].get("grade") for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
                        and l["fee"].get("grade") and l["fee"].get("free_min") != DDC_2H_FREE_MIN)
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    two_h = [l for l in lots if l["list_mode"] == "card" and l["fee"]["type"] == "유료"
             and l["fee"].get("free_min") == DDC_2H_FREE_MIN]
    payload["fee_table"]["two_hour"]["lots"] = len(two_h)
    for row in payload["fee_table"]["big"]:
        row["lots"] = len([l for l in lots if l["list_mode"] == "card"
                           and l["fee"].get("grade_label") == f"대형자동차 {row['kind']}"])
    payload.update(CITY_META["동두천시"] | {
        "city": "동두천시",
        "weekend_free_pages": False,
        "discounts": DDC_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "dongducheon_parking.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_dongducheon(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                              note_fixed, reclassified, month_diff, addr_fixed, dup_mgmt, no_ticket):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    free = [l for l in lots if l["fee"]["type"] == "무료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_동두천시행수": len([r for r in rows if (r.get("주차장구분") or "").strip() == "공영"]),
        "원자료_전체행수": len(rows),
        "민영_제외": len([e for e in excluded if "민영" in e["reason"]]),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in paid
                                     if l["fee"].get("std_grade"))),
        "유료_노상": len([l for l in paid if l["ptype"] == "노상"]),
        "유료_노외": len([l for l in paid if l["ptype"] == "노외"]),
        "유료_부설": len([l for l in paid if l["ptype"] == "부설"]),
        "2시간무료": len([l for l in paid if l["fee"].get("free_min") == DDC_2H_FREE_MIN]),
        "대형자동차": len([l for l in paid if (l["fee"].get("grade_label") or "").startswith("대형자동차")]),
        "정기권_판매": sorted(l["name"] for l in paid if l["fee"].get("monthly")),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "등록값_차이": note_fixed,
        "요금구분_보정": reclassified,
        "정기권_차이": month_diff,
        "주소_보정": addr_fixed,
        "관리번호_중복": dup_mgmt,
        "1일권_없음": no_ticket,
        "감면_출처": "「동두천시 주차장 설치 및 관리 조례」 제7조(주차요금의 감면) · 동두천시 시설관리공단 감면안내",
        "무료시간_출처": "조례 별표1 ※(입차 후 최초 10분 무료) · 2시간 무료 주차 허용 노외주차장(최초 2시간)",
        "주말무료_출처": ("동두천시 시설관리공단 유료 운영시간(월~토 / 송내1·4 월~일) · "
                          "조례 제7조 제1항 제1호 마목(공휴일 이용차량 면제)"),
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len(free),
        "무료_구획수": sum(l["spaces"] or 0 for l in free),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


# ---------------------------------------------------------------- 과천시 (T-03 Phase 27)
GC_PROVIDER = "경기도 과천시"
# 과천시도 자치구가 없다 — 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
GC_DISTRICTS = [("과천시", "gwacheon")]
GC_BBOX = (37.40, 37.48, 126.97, 127.05)   # 과천시 대략 경계(좌표 점검용)
# 과천시 법정동 — 주소의 ‘경기도 과천시 ○○동 번지’ 세 번째 낱말을 쓴다.
#   행정동은 6개(중앙동·별양동·부림동·문원동·과천동·갈현동)이고, 법정동도 같은 이름을 쓴다.
GC_UNIT_SUFFIX = ("동",)

GC_ORDINANCE_URL = "https://law.go.kr/LSW/ordinInfoP.do?ordinSeq=2007623"
GC_CORP_URL = "https://www.gcuc.or.kr/parking/second_menu.do?action=현황"
GC_CORP_FEE_URL = "https://www.gcuc.or.kr/parking/second_menu.do?action=요금안내"
GC_CORP_HOURS_URL = "https://www.gcuc.or.kr/fmcs/225"
GC_CITY_FEE_URL = "https://www.gccity.go.kr/dept/contents.do?mId=0407010000"
GC_CITY_URL = "https://www.gccity.go.kr/dept/contents.do?mId=0407020000"
GC_ORD1 = RAW / "law.go.kr_주차장조례_별표1_20261117.hwpx"
GC_ORD1_TXT = RAW / "law.go.kr_주차장조례_별표1_20261117.txt"
GC_ORD6 = RAW / "law.go.kr_주차장조례_별표6_20261117.hwpx"
GC_ORD6_TXT = RAW / "law.go.kr_주차장조례_별표6_20261117.txt"
GC_CORP_TXT = RAW / "gcuc.or.kr_공영주차장현황_20261117.txt"
GC_CORP_FEE_TXT = RAW / "gcuc.or.kr_공영주차장_요금안내_20261117.txt"
GC_CORP_HOURS_TXT = RAW / "gcuc.or.kr_공영주차장_시설운영시간_20261117.txt"
GC_CITY_FEE_TXT = RAW / "gccity.go.kr_공영주차장_주차요금표_20261117.txt"
GC_CITY_TXT = RAW / "gccity.go.kr_공영주차장_현황_20261117.txt"
GC_ORDINANCE_NOTE = ("시행 2025-01-01 · 경기도과천시조례 제2081호(일부개정) · "
                     "별표1 공영주차장 주차요금표 · 별표6 감면·추가 요금표")
GC_UNIT_MIN = 5            # 1구획 5분당 요금(별표1)
GC_FREE_MIN = 5            # 별표1 비고9 — 최초 입차 후 5분 이내 출차 시 무료
GC_CLOSE_MIN = 19 * 60     # 별표1 비고3 적용시간 09:00~19:00

# 과천시 공영주차장 요금 — 「과천시 주차장 조례」 [별표 1] 공영주차장 주차요금표
#   (시행 2025-01-01, 경기도과천시조례 제2081호, 별표1 HWPX의 표와 비고를 읽음).
#   · 1급지: 1구획 5분당 300원 · 1일 상한 28,000원 · 월 정기 110,000원(경마공원 주변은 1+4급지 합산)
#   · 2급지: 250원 · 24,000원 · 150,000원   (일반상업지역, 주차빌딩 포함)
#   · 3급지: 150원 · 14,000원 · 70,000원    (관악산길 주차장)
#   · 4급지: 100원 · 7,000원 · 50,000원     (경마장 주변 경마일 제외, 이면도로 노상)
#   · 5급지: 관내주민 70원·7,000원·35,000원 / 관내사업자·종사자·법인 150원·14,000원·70,000원
#            / 관외주민 300원·28,000원·120,000원
#   · 비고3: 징수일 — 경마장 주변(경마일) 및 관악산길 주차장을 제외하고 법정 공휴일은 무료,
#            적용시간 09:00~19:00
#   · 비고4: 급지 구분(가. 1급지 경마장 주변(경마일) 나. 2급지 일반상업지역(주차빌딩 포함)
#            다. 3급지 관악산길 라. 4급지 경마장 주변(경마일 제외)·이면도로 노상
#            마. 5급지 중앙동 소공원, 그 외 1~4급지에 해당하지 않는 노상·노외)
#   · 비고9: 5분 단위 산정, 5분 이하 주차시간은 5분으로 본다. 다만 최초 입차 후 5분 이내 출차 시 무료
#   · 비고10: 월 정기 주차권은 총 주차면수의 50% 범위에서 발행   · 비고11: 10원 미만 절사
GC_FEES = {
    1: {"unit": 300, "day": 28_000, "month": 110_000, "where": "경마장 주변(경마일)"},
    2: {"unit": 250, "day": 24_000, "month": 150_000, "where": "일반상업지역(주차빌딩 포함)"},
    3: {"unit": 150, "day": 14_000, "month": 70_000, "where": "관악산길 주차장"},
    4: {"unit": 100, "day": 7_000, "month": 50_000, "where": "경마장 주변(경마일 제외)·이면도로 노상"},
}
GC_G5 = {
    "관내주민": {"unit": 70, "day": 7_000, "month": 35_000},
    "관내사업자·종사자·법인": {"unit": 150, "day": 14_000, "month": 70_000},
    "관외주민": {"unit": 300, "day": 28_000, "month": 120_000},
}
GC_G5_NOTE = ("가운데 관내주민 5분당 70원·1일 7,000원·월 35,000원, 관내사업자·종사자·법인 "
              "등록차량 5분당 150원·1일 14,000원·월 70,000원입니다(주민등록증·사업자등록증 등 증빙 제시).")
# 과천도시공사 홈페이지 ‘공영주차장 > 현황’(2026-11-17 조회)의 주차장별 급지·면수·유형·비고.
#   표준데이터와 급지가 같고, 면수와 유형이 다른 곳은 카드에 차이를 적는다.
GC_CORP_SPACES = {
    "우리은행 옆": 18, "제일쇼핑 앞": 15, "새서울쇼핑 앞": 15, "이마트 앞": 16,
    "2단지(은혜와진리교회) 앞": 10, "우체국 앞": 7, "벽산상가 앞": 8, "렉스타운 앞": 39,
    "그레이스호텔 앞": 19, "골든타워 앞": 7, "주차빌딩": 81, "코오롱 앞(기계식)": 47,
    "동성빌딩 주변": 31, "소방서 뒤": 22, "중앙빌딩": 15, "중앙동 소공원 주차장": 33,
    "관악산길": 96, "교보빌딩 앞(상이군경회)": 41, "국민은행 앞(상이군경회)": 44,
    "힐스테이트 과천청사역 앞": 37, "과천지구대 맞은편": 6,
    "광창교(5주차장 선바위역)": 54, "북문노상주차장": 45,
    "궁말마을 입구(경마공원역)": 172, "광창교 앞(삼부골)": 152,
    "한내1": 9, "한내2": 7, "한내3": 19, "뒷골5": 17, "뒷골6": 34, "뒷골7": 55,
    "찬우물1": 9, "찬우물2": 11, "찬우물3": 22, "죽바위2-2": 11, "문원공원마을 어린이집": 48,
    "광창1": 48, "광창2": 7, "광창3": 8, "광창5": 15, "문원청계마을": 180,
}
GC_CORP_MERGED = {
    "농협(경찰서옆) 앞": ("농협(KT)", 32, "KT(전화국) 앞"),
    "우면산간(2,3주차장)": ("우면산간(2주차장)", 296, "우면산간(4 주차장)"),
}
# 공단이 ‘월정기 전용’으로 안내하는 주차장 — 시간 주차요금을 받지 않을 수 있다.
GC_TICKET_ONLY = {"한내1", "한내2", "광창2", "광창3"}
# 경마장 주변 — 급지가 경마일에 따라 달라진다(별표1 비고4 가목·라목).
GC_RACE_DAY_LOTS = {"궁말마을 입구(경마공원역)", "광창교 앞(삼부골)"}
GC_GRADE1_LOTS = {"우면산간(2,3주차장)", "우면산간(4 주차장)", "광창교(5주차장 선바위역)",
                  "북문노상주차장"}
# 요금을 받지 않는 날 — 공단 시설운영시간(2026-11-17)의 ‘휴무일’과 별표1 비고3.
# 관악산길은 연중무휴(별표1 비고3의 징수일 예외) — 요일과 관계없이 요금을 받는다.
GC_ALWAYS_PAID = {"관악산길"}
# 표준데이터 지번주소가 비어 도로명주소만 있는 노상 3구간 — 공단 현황의 지번이 중앙동 40-14다.
GC_DONG_FIX = {"중앙빌딩": "중앙동", "소방서 뒤": "중앙동", "동성빌딩 주변": "중앙동"}
# 공단 현황의 지역 묶음 — 노상 표의 ‘도로·위치’ 열에 쓴다.
GC_ROAD_GROUP = {
    "별양동 상업지역": {"우리은행 옆", "제일쇼핑 앞", "새서울쇼핑 앞", "이마트 앞",
                        "2단지(은혜와진리교회) 앞", "우체국 앞", "벽산상가 앞", "골든타워 앞"},
    "중앙동 상업지역": {"동성빌딩 주변", "소방서 뒤", "중앙빌딩", "농협(경찰서옆) 앞",
                        "KT(전화국) 앞", "과천지구대 맞은편"},
    "관악산길": {"관악산길"},
    "경마장 주변": {"우면산간(2,3주차장)", "우면산간(4 주차장)", "광창교(5주차장 선바위역)",
                    "북문노상주차장", "광창교 앞(삼부골)", "궁말마을 입구(경마공원역)"},
}
GC_GENERIC_NAME = "공영노외주차장"

# 과천시 주차요금 감면 — 「과천시 주차장 조례」 제3조제1항 [별표 6] 공영주차장 주차요금 감면·추가요금표.
#   전액 감면: 장애 정도가 심한 장애인(운전·동승), 국가유공자(제4조제1항 제4·6·10·12·15호 및 제73조),
#             고엽제후유증·후유의증 환자, 5·18민주화 부상자, 독립유공자(유족), 과천시 공무수행(관용) 차량
#   50% 감면: 장애 정도가 심하지 않은 장애인(일 2시간까지 전액 면제), 1,000cc 미만 경형자동차,
#             저공해·친환경 자동차 표지 부착 차량(전기차 충전 시 2시간까지 면제), 65세 이상 운전자
#             (일 2시간까지 전액 면제), 18세 이하 자녀 1명 포함 2명 이상 다자녀 가정, 장기등 기증자 본인,
#             병역명문가증 제시 차량, 국가유공자 유족증 제시 차량
#   20% 감면: 승용차 부제·요일제·자가용 함께 타기 참여차량, 장기등 인체조직 기증희망 등록자 본인
#   기타: 유공납세자 인증 차량 1년간 면제, 화물하역구간 화물자동차 20분까지 면제,
#         공공시설 방문 확인증 발급 차량 30분까지 면제, 우수자원봉사자 2시간까지 면제
#   ※ 2종류 이상 해당하면 면제율이 높은 하나만 적용. 경마장 주변(경마일)에는 감면을 적용하지 않는다
#     (상위 법령에 의한 면제는 적용). 증빙서류를 제시해야 한다.
GC_DISCOUNTS = [
    {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
    {"label": "장애인(심한)·국가유공자·5·18·독립유공자 면제", "rate": 1.0, "exempt_min": 0,
     "note": ("장애의 정도가 심한 장애인이 운전하거나 동승한 차량, 국가유공자(제4조제1항 "
              "제4·6·10·12·15호 및 제73조), 고엽제후유증·후유의증 환자, 5·18민주화 부상자, "
              "독립유공자(유족), 과천시 공무수행(관용) 차량 — 전액 감면")},
    {"label": "유공납세자·화물하역·공공시설 방문 면제", "rate": 1.0, "exempt_min": 0,
     "note": ("유공납세자 인증 차량(1년), 화물하역구간 화물자동차(20분까지), 동주민센터·경찰서·"
              "소방서·도서관 방문 확인증 발급 차량(30분까지), 우수자원봉사자(2시간까지)")},
    {"label": "장애인(경증) 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "장애의 정도가 심하지 않은 장애인이 운전하거나 동승한 차량 — 일 2시간까지 전액 면제 뒤 50%"},
    {"label": "65세 이상 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "65세 이상 운전자 — 일 2시간까지 전액 면제 뒤 50%"},
    {"label": "전기차 2시간 면제 후 50%", "rate": 0.5, "exempt_min": 120,
     "note": "전기자동차 충전 시 2시간까지 면제, 그 뒤 50%(저공해·친환경 표지 차량)"},
    {"label": "경차·저공해·다자녀·장기기증·병역명문가·유족 50%", "rate": 0.5, "exempt_min": 0,
     "note": ("1,000cc 미만 경형자동차, 저공해·친환경 표지 차량, 18세 이하 자녀 1명을 포함한 "
              "2명 이상 다자녀 가정, 장기등 기증자 본인, 병역명문가증·국가유공자 유족증 제시 차량 — 50%")},
    {"label": "승용차 부제·요일제·함께타기 20%", "rate": 0.2, "exempt_min": 0,
     "note": "승용차 부제·요일제 운행·자가용 함께 타기 참여차량, 장기등 인체조직 기증희망 등록자 — 20%"},
]


def gc_dong_of(text: str):
    """주소에서 과천시 법정동을 뽑는다 — ‘경기도 과천시 ○○동 번지’ 꼴."""
    parts = (text or "").split()
    if len(parts) >= 3 and parts[1] == "과천시":
        cand = parts[2]
        if cand.endswith(GC_UNIT_SUFFIX) and not cand.endswith(("로동", "가동")):
            return cand
    return None


def gc_window(start, end):
    h1, m1 = divmod(int(start), 60)
    h2, m2 = divmod(int(end), 60)
    return {"open": True, "start": start, "end": end, "24h": False, "listed": True,
            "raw": [f"{h1:02d}:{m1:02d}", f"{h2:02d}:{m2:02d}"]}


def gc_fee(*, grade: int = None, g5: str = "관외주민", monthly=None, pay="",
           ticket_only: bool = False):
    """과천시 공영주차장 요금 → 사이트 공통 fee 객체.

    별표1은 1구획 5분당 요금이고 1일 상한요금이 시간 요금의 상한이다. 최초 입차 후 5분 이내
    출차하면 무료이므로 free_min=5로 넣는다(6분 이상이면 5분 단위로 올림).
    """
    common = {
        "type": "유료", "raw_type": "유료", "mixed": False,
        "grade": None, "grade_label": None, "std_grade": None,
        "steps": None, "steps_label": None, "deduct_min": None,
        "cap_fee": None, "cap_src": "조례 별표1 1일 상한요금",
        "daily_hours": None, "prepaid_day": None, "prepaid_weekend": None,
        "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": pay, "category": None, "portal_free_now": False,
        "flat_day": False, "ticket_only": ticket_only, "std": None,
    }
    if grade in GC_FEES:
        t = GC_FEES[grade]
        return {**common,
                "grade": grade, "grade_label": f"{grade}급지",
                "base_min": GC_UNIT_MIN, "base_fee": t["unit"],
                "unit_min": GC_UNIT_MIN, "unit_fee": t["unit"],
                "free_min": GC_FREE_MIN,
                "daily_fee": t["day"], "monthly": monthly,
                "basis": (f"「과천시 주차장 조례」 별표1 {grade}급지({t['where']}) — "
                          f"1구획 5분당 {t['unit']:,}원 · 1일 상한 {t['day']:,}원"
                          + (f" · 월 정기 {monthly:,}원" if monthly else ""))}
    t = GC_G5[g5]
    return {**common,
            "grade": 5, "grade_label": f"5급지 {g5}",
            "base_min": GC_UNIT_MIN, "base_fee": t["unit"],
            "unit_min": GC_UNIT_MIN, "unit_fee": t["unit"],
            "free_min": GC_FREE_MIN,
            "daily_fee": t["day"], "monthly": monthly,
            "monthly_label": f"{g5} 월 정기",
            "basis": (f"「과천시 주차장 조례」 별표1 5급지 {g5} — "
                      f"1구획 5분당 {t['unit']:,}원 · 1일 상한 {t['day']:,}원"
                      + (f" · 월 정기 {monthly:,}원" if monthly else ""))}


def gc_free_fee():
    """요금 구분 ‘무료’ 주차장의 사이트 공통 fee 객체."""
    return {
        "type": "무료", "raw_type": "무료", "mixed": False,
        "grade": None, "grade_label": None, "std_grade": None,
        "base_min": None, "base_fee": None, "unit_min": None, "unit_fee": None,
        "steps": None, "steps_label": None, "free_min": None, "deduct_min": None,
        "cap_fee": None, "cap_src": None, "daily_hours": None, "daily_fee": None,
        "prepaid_day": None, "prepaid_weekend": None,
        "monthly": None, "monthly_day": None, "monthly_night": None, "monthly_all": None,
        "monthly_label": None, "pay": "", "basis": "요금 구분 ‘무료’",
        "category": None, "portal_free_now": False, "flat_day": False,
        "ticket_only": False, "std": None,
    }


def build_gwacheon():
    """과천시 공영주차장을 표준데이터 + 과천시 주차장 조례 별표1·별표6 + 과천도시공사 현황으로 추출한다.

    다른 도시와 같은 품질 기준을 쓴다.
      · 이름·주소·구획수 중 하나라도 없거나 좌표가 과천시 범위를 벗어난 행은 제외(껍데기 행).
      · 표준데이터 101행은 모두 공영(민영 등록 없음)이라 민영 제외는 일어나지 않는다.
      · 과천시는 자치구가 없어 시 페이지가 계산기·목록 페이지를 겸하고, 그 아래 법정동 페이지를 둔다.
      · 노상(거리) 구간은 표 페이지로 분리(list_mode='street')하고 카드 목록에는 넣지 않는다.
      · 동 페이지는 카드가 3곳 이상인 법정동만 만든다.
    요금은 조례 별표1을 쓰고, 급지·면수·운영시간은 과천도시공사 공영주차장 현황으로 대조한다
    (표준데이터는 유료 행도 급지와 5분당 요금만 등록되어 있어 운영시간이 24시간으로 되어 있다).
    """
    rows_all = read_csv_kr(STD_CSV)
    rows_city = [r for r in rows_all if (r.get("제공기관명") or "").strip() == GC_PROVIDER]
    lots, excluded, merged = [], [], []
    hour_fixed, space_diff, note_fixed, reclassified, month_diff = [], [], [], [], []
    addr_fixed, dup_mgmt, no_ticket, name_fixed = [], [], [], []

    def add_lot(name, jibun, road, ptype, spaces, dong, dong_src, win, oper, fee, r=None,
                notice=None, tel="", mgmt="", lat=None, lng=None, base_date="",
                free_days=None, free_note=None, road_group=None):
        street = ptype == "노상"
        lots.append({
            "id": "",     # 정렬 뒤에 다시 매긴다
            "mgmt_no": (r.get("주차장관리번호") or "").strip() if r else "",
            "src": "표준데이터",
            "list_mode": "street" if street else "card",
            "name": name,
            "gu": "과천시",
            "dong": dong,
            "dong_src": dong_src,
            "kind": (r.get("주차장구분") or "").strip() if r else "공영",
            "ptype": ptype,
            "addr_jibun": jibun,
            "addr_road": road,
            "road": road_group if street else None,
            "spaces": spaces,
            "tel": tel,
            "lat": lat, "lng": lng,
            "base_date": base_date,
            "manager": mgmt or "과천도시공사",
            "note": "",
            "notice": notice,
            "fee": fee,
            "oper": oper,
            "hours": win,
            "free_days": free_days or {"sat": False, "sun": False},
            "free_window": None,
            "free_hour_note": free_note,
            "closed_from_note": False,
            "disabled_area": (r.get("장애인전용주차구역보유여부") or "").strip() if r else "",
            "capa_detail": None,
            "portal_name": None,
            "realtime": None,
            "udc_id": None,
            "price_key": (fee["free_min"] if fee["type"] == "유료" else None),
            "city": "과천시",
            "city_slug": "gwacheon",
        })

    for r in rows_city:
        name = (r.get("주차장명") or "").strip()
        jibun = (r.get("소재지지번주소") or "").strip()
        road = (r.get("소재지도로명주소") or "").strip()
        ptype = (r.get("주차장유형") or "").strip() or "노외"
        spaces = to_int(r.get("주차구획수"))
        addr = jibun or road
        gubun = (r.get("주차장구분") or "").strip()
        reason = None
        try:
            lat = float(r["위도"]) if (r.get("위도") or "").strip() else None
            lng = float(r["경도"]) if (r.get("경도") or "").strip() else None
        except ValueError:
            lat = lng = None
        if gubun == "민영":
            excluded.append({"name": name or "(이름 없음)", "reason": "민영 주차장(공영 아님)"})
            continue
        if not name:
            reason = "주차장명 없음"
        elif not addr:
            reason = "주소 없음"
        elif not spaces:
            reason = "주차구획수 없음"
        elif lat is None or lng is None:
            reason = "좌표 없음"
        elif not (GC_BBOX[0] <= lat <= GC_BBOX[1] and GC_BBOX[2] <= lng <= GC_BBOX[3]):
            reason = "좌표 범위 이탈"
        if reason:
            excluded.append({"name": name or "(이름 없음)", "reason": reason})
            continue

        dong = gc_dong_of(jibun) or gc_dong_of(road) or GC_DONG_FIX.get(name)
        dong_src = ("지번주소" if gc_dong_of(jibun) else
                    ("도로명주소" if gc_dong_of(road) else
                     ("공단현황" if name in GC_DONG_FIX else "없음")))
        # 표준데이터에 개별 이름 없이 ‘공영노외주차장’으로만 등록된 소규모 주차장 —
        #   주소의 지번을 붙여 구분한다(이름이 같아 카드가 뒤섞이는 것을 막는다).
        registered_name = name
        if name == GC_GENERIC_NAME:
            tail = " ".join(jibun.split()[2:]) or (road or "").strip()
            name = f"{GC_GENERIC_NAME}({tail})"
            name_fixed.append(f"{jibun}: ‘{GC_GENERIC_NAME}’ → ‘{name}’")

        street = ptype == "노상"
        win, oper, _closed = parse_schedule(r, (r.get("특기사항") or ""))
        pay = (r.get("결제방법") or "").strip()
        fee_type = (r.get("요금정보") or "").strip()
        std_grade = (r.get("급지구분") or "").strip()
        notice_bits = []
        free_days = {"sat": False, "sun": False}
        free_note = None
        paid = fee_type in ("유료", "혼합")
        grade = to_int(std_grade)
        road_group = next((g for g, names in GC_ROAD_GROUP.items() if name in names), None)

        if paid:
            if name in GC_GRADE1_LOTS:
                g = 1
            elif grade == 5:
                g = None
            elif grade in GC_FEES:
                g = grade
            else:
                g = 2
            g5 = None
            if g is None:
                # 5급지는 관내주민·관내사업자·관외주민 세 갈래다 — 표준데이터에 등록된 5분당
                # 요금(70·150·300원)으로 어느 갈래인지 고른다(죽바위2-2·과천지구대 맞은편은 관내주민).
                std_unit = to_int(r.get("추가단위요금")) or 0
                g5 = next((who for who, t in GC_G5.items() if t["unit"] == std_unit), "관외주민")
            monthly = to_int(r.get("월정기권요금")) or (
                GC_G5[g5]["month"] if g5 else GC_FEES[g]["month"])
            fee = gc_fee(grade=g, g5=g5, monthly=monthly, pay=pay,
                         ticket_only=name in GC_TICKET_ONLY)
            fee["std_grade"] = std_grade or None
            daily_std = to_int(r.get("1일주차권요금")) or 0
            month_std = to_int(r.get("월정기권요금")) or 0
            base_min_std = to_int(r.get("주차기본시간"))
            base_fee_std = to_int(r.get("주차기본요금"))
            fee["std"] = {"base_min": base_min_std, "base_fee": base_fee_std,
                          "unit_min": to_int(r.get("추가단위시간")),
                          "unit_fee": to_int(r.get("추가단위요금")),
                          "day": daily_std, "monthly": month_std}
            std_tuple = (base_min_std, base_fee_std, to_int(r.get("추가단위요금")) or 0)
            want_tuple = (GC_UNIT_MIN, fee["base_fee"], fee["unit_fee"])
            if std_tuple != want_tuple:
                note_fixed.append(
                    f"{name}: 표준데이터 기본 {base_min_std or '-'}분 {base_fee_std or 0:,}원·"
                    f"추가 {to_int(r.get('추가단위시간')) or '-'}분 {to_int(r.get('추가단위요금')) or 0:,}원 "
                    f"↔ 조례 별표1 {GC_UNIT_MIN}분 {fee['base_fee']:,}원·{GC_UNIT_MIN}분당 {fee['unit_fee']:,}원")
            if daily_std and daily_std != fee["daily_fee"]:
                note_fixed.append(f"{name}: 표준데이터 1일 {daily_std:,}원 ↔ 별표1 {fee['daily_fee']:,}원")
            if month_std and month_std != (fee["monthly"] or 0):
                month_diff.append(f"{name}: 표준데이터 월정기 {month_std:,}원 ↔ 적용 {fee['monthly'] or 0:,}원")

            # 급지 안내 — 별표1 비고4의 구역 설명을 카드에 적는다.
            if g:
                notice_bits.append(
                    f"「과천시 주차장 조례」 별표1 {g}급지({GC_FEES[g]['where']}) 요금입니다 — "
                    f"1구획 5분당 {GC_FEES[g]['unit']:,}원, 1일 상한 {GC_FEES[g]['day']:,}원, "
                    f"월 정기 {GC_FEES[g]['month']:,}원")
            else:
                if g5 == "관외주민":
                    notice_bits.append(
                        f"별표1 5급지 관외주민 요금(5분당 {GC_G5[g5]['unit']:,}원·1일 상한 "
                        f"{GC_G5[g5]['day']:,}원·월 정기 {GC_G5[g5]['month']:,}원)으로 계산합니다. " + GC_G5_NOTE)
                else:
                    notice_bits.append(
                        f"별표1 5급지 {g5} 요금입니다 — 5분당 {GC_G5[g5]['unit']:,}원, 1일 상한 "
                        f"{GC_G5[g5]['day']:,}원, 월 정기 {GC_G5[g5]['month']:,}원"
                        + ("(표준데이터에 관내주민 요금으로 등록되어 있습니다)"
                           if g5 == "관내주민" else "")
                        + ". 관외주민은 5분당 300원·1일 28,000원·월 120,000원입니다")
            if name in GC_RACE_DAY_LOTS:
                notice_bits.append(
                    "경마일에는 1급지 요금(5분당 300원·1일 28,000원)이 적용됩니다 — 표준데이터 특기사항 "
                    "‘평일 4급지+경마일 1급지’, 조례 별표1 비고4 가목·라목")
            if name in ("우면산간(2,3주차장)", "우면산간(4 주차장)", "광창교(5주차장 선바위역)"):
                notice_bits.append(
                    "조례 별표1 비고4 가목의 1급지(경마장 주변·경마일) 요금입니다. 경마일이 아닌 날은 "
                    "같은 비고 라목의 4급지(5분당 100원·1일 7,000원) 요금이 적용되므로, 경마일이 아닌 "
                    "날의 요금은 현장 안내를 확인하세요")
            notice_bits.append(
                "최초 입차 후 5분 이내 출차하면 무료이고, 5분이 지나면 5분 단위로 올림해 계산합니다"
                "(별표1 비고9·비고11 — 10원 미만 절사)")
            # 요금을 받는 시간 — 별표1 비고3(09:00~19:00)과 공단 시설운영시간(2026-11-17 조회)
            if name == "북문노상주차장":
                win = {"weekday": {"open": False, "start": 0, "end": 0, "24h": False,
                                   "listed": False, "raw": ["-", "-"]},
                       "sat": gc_window(9 * 60, GC_CLOSE_MIN),
                       "sun": gc_window(9 * 60, GC_CLOSE_MIN)}
                oper = {"weekday": False, "sat": True, "sun": True}
                free_days = {"sat": False, "sun": True}
                hour_fixed.append(
                    f"{name}: 표준데이터 평일 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                    "공단 안내 토요일·공휴일 09:00~19:00(평일 무료 개방)")
                notice_bits.append(
                    "평일에는 요금을 받지 않고(무료 개방), 토요일·공휴일에만 1급지 요금을 받습니다"
                    "(표준데이터 특기사항 ‘평일 무료+주말 1급지’·운영요일 ‘토요일+공휴일’). 계산기는 "
                    "평일을 휴무로 표시하니, 평일 이용은 현장 안내를 확인하세요")
            else:
                win = {"weekday": gc_window(9 * 60, GC_CLOSE_MIN),
                       "sat": gc_window(9 * 60, GC_CLOSE_MIN),
                       "sun": gc_window(9 * 60, GC_CLOSE_MIN)}
                oper = {"weekday": True, "sat": True, "sun": True}
                if name in GC_ALWAYS_PAID:
                    free_days = {"sat": False, "sun": False}
                    notice_bits.append(
                        "관악산길 주차장은 연중무휴로 별표1 비고3의 공휴일 무료 예외에 들어 "
                        "일요일·공휴일에도 09:00~19:00 요금을 받습니다(공단 현황 ‘연중무휴’)")
                else:
                    free_days = {"sat": False, "sun": True}
                    notice_bits.append(
                        "요금을 받는 시간은 09:00~19:00이고, 일요일·공휴일은 무료입니다"
                        "(별표1 비고3 ‘경마장 주변(경마일) 및 관악산길 주차장을 제외하고 법정 공휴일은 무료’, "
                        "공단 시설운영시간)")
                if (parse_hm(r.get("평일운영시작시각")), parse_hm(r.get("평일운영종료시각"))) != (9 * 60, GC_CLOSE_MIN):
                    hour_fixed.append(
                        f"{name}: 표준데이터 {r.get('평일운영시작시각') or ''}~{r.get('평일운영종료시각') or ''} → "
                        "별표1 비고3·공단 시설운영시간 09:00~19:00")
            if r.get("월정기권요금") and name in GC_TICKET_ONLY:
                notice_bits.append(
                    "공단은 이 주차장을 ‘월정기 전용’으로 안내합니다 — 시간 주차요금은 받지 않을 수 있으니 "
                    "현장에서 확인하세요(표준데이터에는 5분당 요금이 등록되어 있습니다)")
            if name == "중앙동 소공원 주차장":
                notice_bits.append(
                    "평일 07:30~09:00에는 입출차가 제한됩니다(공단 시설운영시간). 월 정기권은 일부만 판매합니다")
            if name == "코오롱 앞(기계식)":
                notice_bits.append(
                    "기계식 주차장이라 운영시간(09:00~19:00) 밖에는 입출차가 되지 않습니다"
                    "(공단 현황 ‘시간외 입출차 불가’)")
            if name in ("교보빌딩 앞(상이군경회)", "국민은행 앞(상이군경회)"):
                notice_bits.append("상이군경회가 위탁 운영하는 주차장입니다(공단 현황)")
            if name == "문원청계마을":
                notice_bits.append(
                    "같은 지번(문원동 150-8)에 과천시가 등록한 무료 ‘공영노외주차장(문원동 150-8)’ "
                    "42면이 따로 있습니다(표준데이터 두 행) — 서로 다른 주차면으로 보고 둘 다 실었습니다")
            if name == "문원공원마을 어린이집":
                notice_bits.append(
                    "공단 현황에는 급지가 적혀 있지 않고(급지 ‘-’), 표준데이터는 5급지로 등록했습니다 — "
                    "요금은 5급지 관외주민 기준으로 계산합니다")
        else:
            fee = gc_free_fee()
            if street:
                notice_bits.append(
                    "과천시가 노상주차장을 무료로 등록했습니다(조례 별표1에는 노상·노외 같은 급지 "
                    "요금표가 있습니다)")
            if name.startswith(GC_GENERIC_NAME + "("):
                notice_bits.append(
                    "공공데이터 표준데이터에 개별 이름 없이 ‘공영노외주차장’으로만 등록된 주차장입니다 — "
                    "주소의 지번을 붙여 구분했습니다")
            if registered_name == "나대지주차장(市)":
                notice_bits.append("나대지를 임시 공영주차장으로 쓰는 곳입니다(표준데이터 등록 이름 그대로)")
            if registered_name.startswith("한계주자창"):
                notice_bits.append("표준데이터 표기가 ‘한계주자창(남태령지구)’입니다(‘주차장’의 오기로 보입니다)")
            if registered_name == "문원동 버스차고지":
                notice_bits.append("버스 차고지 부지에 마련된 공영주차장입니다(공휴일 운영시간 없음)")

        spec = (r.get("특기사항") or "").strip()
        if spec:
            spec = spec.replace("50퍼센트", "50%")
            spec = re.sub(r"\s*\+\s*", " · ", spec)
            notice_bits.append(f"표준데이터 특기사항: {spec}")

        add_lot(name, jibun, road, ptype, spaces, dong, dong_src, win, oper, fee, r=r,
                notice=" · ".join(b for b in notice_bits if b) or None,
                tel=(r.get("전화번호") or "").strip(),
                mgmt=((r.get("관리기관명") or "").strip() or "과천도시공사"),
                lat=lat, lng=lng, base_date=(r.get("데이터기준일자") or "").strip(),
                free_days=free_days, free_note=free_note, road_group=road_group)

    # 공단 현황과 면수가 다른 곳 — 등록면수를 쓰고 카드에 차이를 적는다.
    by_name = {l["name"]: l for l in lots}
    for name, corp_spaces in GC_CORP_SPACES.items():
        lot = by_name.get(name)
        if not lot or lot["spaces"] == corp_spaces:
            continue
        space_diff.append(f"{name}: 표준데이터 {lot['spaces']}면 ↔ 공단 {corp_spaces}면")
        extra = (f"과천도시공사 공영주차장 현황의 면수는 {corp_spaces}면입니다(표준데이터 등록면수 "
                 f"{lot['spaces']}면과 다릅니다)")
        lot["notice"] = " · ".join(x for x in [lot.get("notice"), extra] if x)
    for name, (corp_name, total, other) in GC_CORP_MERGED.items():
        lot = by_name.get(name)
        other_lot = by_name.get(other)
        if not lot:
            continue
        have = (lot["spaces"] or 0) + ((other_lot["spaces"] or 0) if other_lot else 0)
        if have == total:
            extra = (f"공단은 {corp_name} {total}면으로 안내합니다(표준데이터는 "
                     + ("두 행 " if other_lot else "한 행 ")
                     + f"{have}면" + (f" — {name} {lot['spaces']}면 + {other} "
                                      f"{other_lot['spaces']}면" if other_lot else "") + ")")
            lot["notice"] = " · ".join(x for x in [lot.get("notice"), extra] if x)

    for no, cnt in Counter(l.get("mgmt_no") for l in lots if l.get("mgmt_no")).items():
        if cnt > 1:
            names = "·".join(l["name"] for l in lots if l.get("mgmt_no") == no)
            dup_mgmt.append(f"관리번호 {no}가 {names} 두 곳에 같은 값으로 등록되어 있습니다")

    lots.sort(key=lambda l: (l["list_mode"] != "card", l["dong"] or "힣", l["name"]))
    for i, l in enumerate(lots, 1):
        l["id"] = f"gc-{i:03d}" if l["list_mode"] == "card" else f"gc-s{i:03d}"

    quality = check_quality_gwacheon(rows_all, rows_city, lots, excluded, merged,
                                     hour_fixed, space_diff, note_fixed, reclassified,
                                     month_diff, addr_fixed, dup_mgmt, no_ticket, name_fixed)
    payload = {
        "meta": {
            "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "generated_at_iso": NOW.isoformat(timespec="seconds"),
            "snapshot_at": NOW.strftime("%Y-%m-%d %H:%M"),
            "region": {"province": "경기도", "city": "과천시"},
            "sources": [
                {
                    "id": "std", "name": "전국주차장정보표준데이터",
                    "org": "행정안전부·지방자치단체",
                    "url": "https://www.data.go.kr/data/15012896/standard.do",
                    "file": STD_CSV.name, "sha256": sha256(STD_CSV),
                    "license": "이용허락범위 안내(공공누리 유형별 표기)",
                    "base_date": "2026-10-23",
                    "rows_total": len(rows_all), "rows_city": len(rows_city),
                    "fetched_at": "2026-11-16 22:03 (KST)",
                    "note": ("경기도 과천시가 등록한 101행(노외 80·노상 21)을 읽었다. 모두 주차장구분이 "
                             "‘공영’이라 민영 주차장은 없다. 요금 구분은 유료 46행(노외 25·노상 21)과 "
                             "무료 55행(모두 노외)인데, 유료 노외 25행의 급지는 2급지 8·5급지 17이고 "
                             "노상 21행은 1급지 4·2급지 13·3급지 1·4급지 2·5급지 1이다. 노외 80행 가운데 "
                             "31행은 개별 이름 없이 ‘공영노외주차장’으로만 등록되어 있어 주소의 지번을 "
                             "붙여 구분했다. 주차구획수가 비어 있는 껍데기 행은 없었다."),
                },
                {
                    "id": "ordinance",
                    "name": "「과천시 주차장 조례」 [별표 1] 공영주차장 주차요금표 · [별표 6] 감면·추가 요금표",
                    "org": "과천시청 건설도시국 교통과(02-3677-2899 · 02-3677-2897)",
                    "url": GC_ORDINANCE_URL,
                    "file": GC_ORD1.name if GC_ORD1.exists() else GC_ORD1_TXT.name,
                    "sha256": (sha256(GC_ORD1) if GC_ORD1.exists()
                               else sha256(GC_ORD1_TXT) if GC_ORD1_TXT.exists() else None),
                    "license": "자치법규(공개)", "base_date": GC_ORDINANCE_NOTE,
                    "rows_total": None, "fetched_at": _sync_time(GC_ORD1_TXT),
                    "note": ("국가법령정보센터 자치법규 별표 HWPX를 내려받아 표 셀과 비고를 읽어 정리본(txt)을 "
                             "두었다. 1구획 5분당 1급지 300원·2급지 250원·3급지 150원·4급지 100원, 5급지는 "
                             "관내주민 70원·관내사업자·종사자·법인 150원·관외주민 300원이고, 1일 상한요금은 "
                             "급지별 28,000·24,000·14,000·7,000원(5급지 7,000·14,000·28,000원), 월 정기권은 "
                             "110,000(※)·150,000·70,000·50,000원(5급지 35,000·70,000·120,000원)이다. 비고3은 "
                             "징수일(경마장 주변(경마일)·관악산길 제외 법정 공휴일 무료)과 적용시간 "
                             "09:00~19:00, 비고4는 급지(1급지 경마장 주변 경마일, 2급지 일반상업지역, 3급지 "
                             "관악산길, 4급지 경마장 주변 경마일 제외·이면도로 노상, 5급지 중앙동 소공원과 "
                             "그 밖의 노상·노외), 비고9는 5분 단위 산정과 최초 입차 후 5분 이내 출차 무료, "
                             "비고10은 월 정기권 50% 범위다. 별표6은 전액 감면 6종, 50% 감면 8종(장애인·65세 "
                             "이상은 일 2시간 전액 면제), 20% 감면 2종, 기타 4종을 정한다."),
                },
                {
                    "id": "corp", "name": "과천도시공사 공영주차장 현황·요금안내·시설운영시간",
                    "org": "과천도시공사 주차관리부(02-504-7300 · parking@gcuc.or.kr)",
                    "url": GC_CORP_URL,
                    "file": GC_CORP_TXT.name if GC_CORP_TXT.exists() else None,
                    "sha256": sha256(GC_CORP_TXT) if GC_CORP_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 44, "fetched_at": _sync_time(GC_CORP_TXT),
                    "note": ("공영주차장 44곳(노외·노상)을 지역 묶음(별양동·중앙동 상업지역, 경마장 주변, "
                             "기타지역)으로 나누어 주차장명·주소·면수·유형·급지·비고를 적고, 운영시간 "
                             "09:00~19:00과 ‘경마장 주변(경마일) 및 관악산길 주차장을 제외하고 법정 공휴일은 "
                             "무료’를 안내한다. 경마장 주변 북문노외(1주차장) 398면은 운영종료(2025.10.)로 "
                             "적혀 있고, 한내1·2와 광창2·3은 ‘월정기 전용’, 코오롱 앞(기계식)은 ‘시간외 입출차 "
                             "불가’, 교보빌딩·국민은행 앞은 ‘상이군경회 위탁’이다. 요금안내는 별표1 요금표와 "
                             "함께 5분 이하 5분 산정·최초 입차 후 5분 이내 출차 무료, 운영종료 2시간 이내 "
                             "주차 차량의 사전주차요금 징수를 적는다. 시설운영시간은 주차장별 평일·주말 "
                             "09:00~19:00과 휴무일(중앙동·별양동 상업지역과 우체국 앞·별양동 기계식은 일요일, "
                             "관악산길·찬우물·중앙동 소공원은 없음)을 적는다."),
                },
                {
                    "id": "city", "name": "과천시 홈페이지 공영주차장 주차요금표·현황",
                    "org": "과천시 교통과(02-3677-2897)",
                    "url": GC_CITY_URL,
                    "file": GC_CITY_TXT.name if GC_CITY_TXT.exists() else None,
                    "sha256": sha256(GC_CITY_TXT) if GC_CITY_TXT.exists() else None,
                    "license": "공공기관 공개 웹페이지(공공누리 제1유형)", "base_date": "조회 2026-11-17",
                    "rows_total": 33, "fetched_at": _sync_time(GC_CITY_TXT),
                    "note": ("주차요금표는 과천도시공사 요금안내와 같은 별표1 값이고, 급지 설명도 같다. "
                             "현황 표는 유료운영 공영주차장의 총계를 2,092면(일반 2,035·장애 31·다자녀 "
                             "임산부 13·경차 7)으로 적지만 화면에 올라온 항목(별양동 165 + 상이군경회 61 + "
                             "중앙동·관악산길 188 + 경마장 1,117 + 뒷골 104)을 더하면 1,635면이라, 찬우물·"
                             "한내·광창·문원동 주차장은 표에 빠져 있다. 그래서 면수·급지는 공단 현황과 "
                             "표준데이터로 대조했다."),
                },
            ],
        },
        "districts": [{"name": g, "slug": s} for g, s in GC_DISTRICTS],
        "lots": lots,
        "quality": quality,
        "fee_table": {
            "style": "gwacheon_grade",
            "unit_min": GC_UNIT_MIN,
            "free_min": GC_FREE_MIN,
            "applies": GC_ORDINANCE_NOTE,
            "off": [
                {"grade": g, "where": GC_FEES[g]["where"], "unit": GC_FEES[g]["unit"],
                 "day": GC_FEES[g]["day"], "month": GC_FEES[g]["month"], "lots": 0}
                for g in (1, 2, 3, 4)],
            "g5": [
                {"who": who, "unit": t["unit"], "day": t["day"], "month": t["month"], "lots": 0}
                for who, t in GC_G5.items()],
            "windows": [
                {"group": "상업지역·경마장 주변 유료 주차장(노상·노외)",
                 "hours": "월~일 09:00~19:00", "free": "일요일·공휴일 무료"},
                {"group": "관악산길 주차장(3급지)",
                 "hours": "연중무휴 09:00~19:00", "free": "공휴일에도 요금을 받음(별표1 비고3 예외)"},
                {"group": "북문노상주차장",
                 "hours": "토요일·공휴일 09:00~19:00", "free": "평일 무료 개방"},
                {"group": "월정기 전용(한내1·2, 광창2·3)",
                 "hours": "공단 안내 참조", "free": "시간 주차요금은 받지 않을 수 있음"},
            ],
            "monthly_note": ("월 정기 주차권은 총 주차면수의 50% 범위에서 발행하며(별표1 비고10), "
                             "경마공원 주변은 경마일·비경마일을 합산해 1급지와 4급지 금액을 더해 계산합니다(※)."),
            "corp": {
                "paid_out": len([l for l in lots if l["list_mode"] == "card"
                                 and l["fee"]["type"] == "유료"]),
                "free_out": len([l for l in lots if l["list_mode"] == "card"
                                 and l["fee"]["type"] == "무료"]),
                "street": len([l for l in lots if l["list_mode"] == "street"]),
            },
            "lots": [
                {"name": l["name"], "dong": l["dong"], "ptype": l["ptype"],
                 "grade": l["fee"].get("grade") or l["fee"].get("grade_label"),
                 "free": l["fee"].get("free_min"), "unit": l["fee"].get("unit_fee"),
                 "base": l["fee"].get("base_fee"),
                 "day": l["fee"].get("daily_fee"), "month": l["fee"].get("monthly")}
                for l in lots if l["fee"]["type"] == "유료"],
            "basis": ("「과천시 주차장 조례」 [별표 1] 공영주차장 주차요금표"
                      f"({GC_ORDINANCE_NOTE}) · [별표 6] 감면·추가 요금표 · "
                      "과천도시공사 공영주차장 현황·요금안내·시설운영시간(2026-11-17 확인)"),
        },
    }
    # 급지 요금표의 ‘이 사이트 유료 주차장’은 카드로 실은 곳만 센다(노상은 노상 페이지에서 센다).
    card_paid = Counter(l["fee"].get("grade") for l in lots
                        if l["list_mode"] == "card" and l["fee"]["type"] == "유료")
    for row in payload["fee_table"]["off"]:
        row["lots"] = card_paid.get(row["grade"], 0)
    payload["fee_table"]["g5"][list(GC_G5).index("관외주민")]["lots"] = card_paid.get(5, 0)
    payload.update(CITY_META["과천시"] | {
        "city": "과천시",
        "weekend_free_pages": False,
        "discounts": GC_DISCOUNTS,
        "realtime": False,
    })
    (DATA / "gwacheon_parking.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1))
    return payload


def check_quality_gwacheon(std_all, rows, lots, excluded, merged, hour_fixed, space_diff,
                           note_fixed, reclassified, month_diff, addr_fixed, dup_mgmt,
                           no_ticket, name_fixed=None):
    card = [l for l in lots if l["list_mode"] == "card"]
    street = [l for l in lots if l["list_mode"] == "street"]
    by_dong = Counter(l["dong"] or "동 미상" for l in card)
    paid = [l for l in lots if l["fee"]["type"] == "유료"]
    free = [l for l in lots if l["fee"]["type"] == "무료"]
    return {
        "generated_at": NOW.strftime("%Y-%m-%d %H:%M"),
        "원자료_전국행수": len(std_all),
        "원자료_행수": len(rows),
        "원자료_과천시행수": len([r for r in rows if (r.get("주차장구분") or "").strip() == "공영"]),
        "원자료_전체행수": len(rows),
        "민영_제외": len([e for e in excluded if "민영" in e["reason"]]),
        "제외_행수": len(excluded),
        "제외_행": excluded,
        "중복제거_행수": len(merged),
        "중복제거_행": merged,
        "총_주차장": len(card),
        "노외_부설": dict(Counter(l["ptype"] for l in card)),
        "노상_구간": len(street),
        "총_구획수": sum(l["spaces"] or 0 for l in card),
        "노상_구획수": sum(l["spaces"] or 0 for l in street),
        "동별": dict(sorted(by_dong.items(), key=lambda kv: (-kv[1], kv[0]))),
        "동수": len({l["dong"] for l in card if l["dong"]}),
        "동_미상": [l["name"] for l in card if not l["dong"]],
        "동_근거": dict(Counter(l["dong_src"] for l in card)),
        "요금구분": dict(Counter(l["fee"]["type"] for l in lots)),
        "요금_미상": [l["name"] for l in lots if l["fee"]["type"] == "미상"],
        "급지별": dict(Counter(l["fee"]["grade"] for l in paid if l["fee"].get("grade"))),
        "표준데이터_급지": dict(Counter(l["fee"].get("std_grade") for l in paid
                                     if l["fee"].get("std_grade"))),
        "유료_노상": len([l for l in paid if l["ptype"] == "노상"]),
        "유료_노외": len([l for l in paid if l["ptype"] == "노외"]),
        "유료_부설": len([l for l in paid if l["ptype"] == "부설"]),
        "5급지_관외": len([l for l in paid if l["fee"].get("grade") == 5
                          and l["fee"].get("monthly_label") == "관외주민 월 정기"]),
        "정기권_판매": sorted(l["name"] for l in paid if l["fee"].get("monthly")),
        "운영시간_보정": hour_fixed,
        "면수_차이": space_diff,
        "등록값_차이": note_fixed,
        "요금구분_보정": reclassified,
        "정기권_차이": month_diff,
        "주소_보정": addr_fixed,
        "관리번호_중복": dup_mgmt,
        "1일권_없음": no_ticket,
        "이름_보정": name_fixed or [],
        "감면_출처": ("「과천시 주차장 조례」 [별표 6] 공영주차장 주차요금 감면·추가 요금표 · "
                     "과천도시공사 요금감면대상 안내"),
        "무료시간_출처": "별표1 비고9(5분 단위 산정, 최초 입차 후 5분 이내 출차 시 무료)",
        "주말무료_출처": ("별표1 비고3(경마장 주변(경마일)·관악산길 제외 법정 공휴일 무료) · "
                          "과천도시공사 시설운영시간(중앙동·별양동 상업지역과 우체국 앞 휴무일 일요일)"),
        "일요일_무료표기": [l["name"] for l in lots if l["free_days"].get("sun")],
        "무료개방_표기": [l["name"] for l in lots
                          if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])],
        "무료_요금구분": len(free),
        "무료_구획수": sum(l["spaces"] or 0 for l in free),
        "평균_기본요금": round(sum(l["fee"]["base_fee"] for l in paid if l["fee"].get("base_fee"))
                          / max(1, len([l for l in paid if l["fee"].get("base_fee")]))),
        "토요일_미운영": len([l for l in lots if not l["oper"]["sat"]]),
        "일공휴일_미운영": len([l for l in lots if not l["oper"]["sun"]]),
        "좌표_없음": [l["name"] for l in lots if l["lat"] is None or l["lng"] is None],
        "주소_없음": [l["name"] for l in lots if not (l["addr_jibun"] or l["addr_road"])],
        "이름중복": [k for k, v in Counter(l["name"] for l in lots).items() if v > 1],
        "관리번호중복": [k for k, v in Counter(l.get("mgmt_no") for l in lots
                                              if l.get("mgmt_no")).items() if v > 1],
        "전화번호_없음": len([l for l in lots if not l["tel"]]),
        "데이터기준일": sorted({l["base_date"] for l in lots if l["base_date"]}),
    }


def main():
    ap = argparse.ArgumentParser(description="공영주차장 파인더 데이터 정제")
    ap.add_argument("--city", choices=["suwon", "seongnam", "yongin", "hwaseong", "anyang", "pyeongtaek", "bucheon", "goyang", "namyangju", "ansan", "siheung", "uijeongbu", "gimpo", "paju", "gwangju", "hanam", "gunpo", "gwangmyeong", "guri", "osan", "icheon", "anseong", "yangju", "pocheon", "uiwang", "yeoju", "dongducheon", "gwacheon", "all"], default="all")
    args = ap.parse_args()

    want = (["수원시", "성남시", "용인시", "화성시", "안양시", "평택시", "부천시", "고양시", "남양주시", "안산시", "시흥시", "의정부시", "김포시", "파주시", "광주시", "하남시", "군포시", "광명시", "구리시", "오산시", "이천시", "안성시", "양주시", "포천시", "의왕시", "여주시", "동두천시", "과천시"] if args.city == "all" else \
            {"suwon": ["수원시"], "seongnam": ["성남시"], "yongin": ["용인시"],
             "hwaseong": ["화성시"], "anyang": ["안양시"], "pyeongtaek": ["평택시"],
             "bucheon": ["부천시"], "goyang": ["고양시"], "namyangju": ["남양주시"],
             "ansan": ["안산시"], "siheung": ["시흥시"], "uijeongbu": ["의정부시"],
             "gimpo": ["김포시"], "paju": ["파주시"], "gwangju": ["광주시"],
             "hanam": ["하남시"], "gunpo": ["군포시"],
             "gwangmyeong": ["광명시"], "guri": ["구리시"], "osan": ["오산시"],
             "icheon": ["이천시"], "anseong": ["안성시"],
             "yangju": ["양주시"], "pocheon": ["포천시"], "uiwang": ["의왕시"],
             "yeoju": ["여주시"],
             "dongducheon": ["동두천시"],
             "gwacheon": ["과천시"]}[args.city])
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
    if "김포시" in want:
        cities.append(build_gimpo())
    if "파주시" in want:
        cities.append(build_paju())
    if "광주시" in want:
        cities.append(build_gwangju())
    if "하남시" in want:
        cities.append(build_hanam())
    if "군포시" in want:
        cities.append(build_gunpo())
    if "광명시" in want:
        cities.append(build_gwangmyeong())
    if "구리시" in want:
        cities.append(build_guri())
    if "오산시" in want:
        cities.append(build_osan())
    if "이천시" in want:
        cities.append(build_icheon())
    if "안성시" in want:
        cities.append(build_anseong())
    if "양주시" in want:
        cities.append(build_yangju())
    if "포천시" in want:
        cities.append(build_pocheon())
    if "의왕시" in want:
        cities.append(build_uiwang())
    if "여주시" in want:
        cities.append(build_yeoju())
    if "동두천시" in want:
        cities.append(build_dongducheon())
    if "과천시" in want:
        cities.append(build_gwacheon())

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
