#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
공영주차장 파인더 — 정적 사이트 생성기 (수원시 + 성남시 + 용인시 + 화성시)

data/site.json 을 읽어 dist/ 아래에 도시별로
  · 랜딩(도시 선택)
  · 시 허브
  · 구 허브 (계산기 + 목록)
  · 주말·공휴일 무료 개방 필터 (무료 개방 표기가 있는 도시만)
  · 행정동 상세 (노외 주차장 3곳 이상인 동만)
  · 노상(거리) 주차 구간 표 (노상 자료가 있는 도시만)
페이지를 만든다. 각 페이지에 BreadcrumbList · FAQPage · ItemList JSON-LD 를 넣는다.

사용법:  python3 scripts/build_site.py [--base https://example.com]
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import shutil
import statistics
from collections import Counter
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "data" / "site.json"
LEGACY_DATA_FILE = BASE / "data" / "suwon_parking.json"
DIST = BASE / "dist"
ASSETS = BASE / "assets"

SITE_NAME = "공영주차장 파인더"
SITE_BASE = "https://parking.9welfare.com"   # 배포 시 실제 도메인으로 바꾼다
BUILD_TS = ""
SNAPSHOT_TS = ""
SITE_CITIES: list[dict] = []                  # site.json 의 cities (nav 순서)

DONG_SLUG = {
    "고색동": "goseak-dong", "곡반정동": "gokbanjeong-dong", "권선동": "gwonseon-dong",
    "대황교동": "daehwanggyo-dong", "서둔동": "seodun-dong", "장지동": "jangji-dong",
    "탑동": "tap-dong",
    "매탄동": "maetan-dong", "신동": "sin-dong", "영통동": "yeongtong-dong",
    "원천동": "woncheon-dong", "이의동": "ui-dong", "하동": "ha-dong",
    "송죽동": "songjuk-dong", "영화동": "yeonghwa-dong", "율전동": "yuljeon-dong",
    "정자동": "jeongja-dong", "파장동": "pajang-dong", "하광교동": "hagwanggyo-dong",
    "고등동": "godeung-dong", "교동": "gyo-dong", "남수동": "namsu-dong",
    "매향동": "maehyang-dong", "신풍동": "sinpung-dong", "우만2동": "uman2-dong",
    "우만동": "uman-dong", "인계동": "ingye-dong", "장안동": "jangan-dong",
    "화서동": "hwaseo-dong",
}
GU_SLUG = {"영통구": "suwon-yeongtong", "권선구": "suwon-gwonseon",
           "팔달구": "suwon-paldal", "장안구": "suwon-jangan"}
GU_ORDER = ["영통구", "권선구", "팔달구", "장안구"]
CITY_SLUG = {"수원시": "suwon"}   # 시·군 슬러그 색인 (없으면 이름으로 자동 생성)
DAY_LABEL = {"weekday": "평일", "sat": "토요일", "sun": "일요일·공휴일"}

# 동 페이지를 만드는 최소 노외 주차장 수(도시별 값이 없을 때의 기본값).
# 새로 확장하는 도시는 빈 페이지를 막기 위해 3곳 미만 동을 구 페이지 표에만 싣는다.
DONG_PAGE_MIN_LOTS = 3
# 주소·이름·좌표로 동(읍·면)을 정하지 못한 주차장의 묶음 이름.
# 이 묶음은 구 페이지 표에만 싣고 절대 별도 페이지를 만들지 않는다(빈 페이지 방지).
UNKNOWN_DONG = "동 미상"
# 노상(거리) 주차 구간을 별도 표로 빼는 기준
STREET_MODE = "street"

# 도시별 화면 문구(데이터가 아니라 안내 문구). 없는 항목은 일반 문구로 대체한다.
CITY_UI = {
    "수원시": {
        "manager": "수원도시공사 031-695-0900",
        "manager_inquiry": "수원도시공사 주차관리팀(031-695-0900)",
        "merged_list": True,
        "district_short": True,
        "std_base_date": "2026-04-16",
        "realtime": True,
        "discount_note": ("수원시 조례(2025-01-01 시행) 기준입니다. 경차·저공해 2·3종·다자녀·임산부 등은 50%, "
                          "경증장애인·저공해 1종은 2시간 면제 후 50%, 중증장애인·국가유공자는 24시간 면제 후 50%, "
                          "모범·유공납세자는 100%이고, 감면은 한 가지만 적용됩니다(현장 확인)."),
        "free_example": "'영통구청'처럼 특기사항에 '일+공휴일 무료개방'이 적힌 주차장이 여기에 해당합니다. ",
        "calc_note": "차량 감면은 <b>수원시 조례(2025-01-01 시행)</b> 기준입니다. 경차·저공해 2·3종·다자녀·임산부 "
                     "50%, 경증장애인·저공해 1종 2시간 면제 후 50%, 중증장애인·국가유공자 24시간 면제 후 50%, "
                     "모범·유공납세자 100%이고 감면은 한 가지만 적용됩니다(현장 확인).",
        "daily_example": "24시간 7,000원",
    },
    "성남시": {
        "manager": "성남도시개발공사 공영주차장 안내",
        "manager_inquiry": "성남도시개발공사 공영주차장 안내(park.isdc.co.kr)",
        "merged_list": False,
        "district_short": False,
        "std_base_date": "2026-10-12",
        "realtime": False,
        "discount_note": ("성남시 조례 기준입니다. 경차·저공해·다자녀·임산부·만 65세 이상은 50%, "
                          "장애인은 1시간 면제 후 50%, 국가유공자는 12시간 면제 후 50%가 적용되고, "
                          "감면은 한 가지만 적용됩니다(현장 확인)."),
        "free_example": "",
        "calc_note": "차량 감면은 <b>성남시 조례 기준</b>입니다. 경차·저공해·다자녀·임산부·만 65세 이상 50%, "
                     "장애인 1시간 면제 후 50%, 국가유공자 12시간 면제 후 50%이고, 감면은 한 가지만 적용됩니다"
                     "(현장 확인).",
        "daily_example": "24시간 6,000원",
    },
    "용인시": {
        "manager": "용인도시공사 공영주차장 안내(park.yuc.co.kr) · 용인시 교통정책과",
        "manager_inquiry": "용인도시공사 공영주차장 안내(park.yuc.co.kr)",
        "merged_list": False,
        "district_short": False,
        "std_base_date": "2026-04-24",
        "realtime": False,
        "dong_unit_label": "동·읍·면",
        "discount_note": ("용인시 조례·용인도시공사 요금 안내(2026-11-16 확인) 기준입니다. 경차·2·3종 저공해·임산부는 50%, "
                          "다자녀는 2시간 무료 후 50%, 장애인은 6시간 면제 후 50%, 국가유공자는 100%이고, "
                          "감면이 겹치면 비율이 높은 하나만 적용됩니다(현장 확인)."),
        "free_example": "",
        "calc_note": "차량 감면은 <b>용인시 조례·용인도시공사 요금 안내</b> 기준입니다. 경차·2·3종 저공해·임산부 50%, "
                     "다자녀 2시간 무료 후 50%, 장애인 6시간 면제 후 50%, 국가유공자 100%이고 감면은 한 가지만 적용됩니다"
                     "(현장 확인).",
        "daily_example": "24시간 9,000원",
        "street_examples": "‘전대리’·‘용인성당 주변’",
        "street_fee_caveat": ("<li><b>용인시 요금표와 차이</b>: 용인시 공식 요금표는 최초 10분을 무료로 두지만 "
                              "표준데이터에는 이 무료 시간이 없어, 10분 이내 이용은 실제보다 높게 계산될 수 있습니다(현장 확인).</li>"),
    },
    "화성시": {
        "manager": "화성도시공사 주차운영부(031-8059-6538) · 화성시 교통지도과",
        "manager_inquiry": "화성도시공사 주차운영부(031-8059-6538)",
        "merged_list": False,
        "district_short": False,
        "std_base_date": "2026-10-20",
        "realtime": False,
        "dong_unit_label": "동·읍·면",
        "discount_note": ("화성시 조례(별표 4) 기준입니다. 경차(1,000cc 미만)·저공해·다자녀(2자녀 이상)·병역명문가·"
                          "우수자원봉사자·환승 등은 50%, 심하지 않은 장애는 2시간 면제 후 50%, "
                          "국가유공자·심한 장애·모범납세자는 100%이고, 감면은 한 가지만 적용됩니다(현장 확인)."),
        "free_example": "",
        "calc_note": "차량 감면은 <b>화성시 조례(별표 4)</b> 기준입니다. 경차·저공해·다자녀·병역명문가 등 50%, "
                     "심하지 않은 장애 2시간 면제 후 50%, 국가유공자·심한 장애·모범납세자 100%이고 "
                     "감면은 한 가지만 적용됩니다(현장 확인).",
        "daily_example": "1일 주차권 요금",
        "street_examples": "‘영천동 773’·‘개나리공원노상’",
        "street_fee_caveat": ("<li><b>요금표와 차이</b>: 특기사항에 ‘최초 1시간 30분 무료 후 10분당 300원’처럼 "
                              "현장 요금을 적은 구간이 있습니다. 표준데이터의 기본요금·추가요금만으로 계산하므로 "
                              "짧게 주차하면 예상요금이 실제보다 높을 수 있습니다(현장 확인).</li>"
                              "<li><b>거주자우선주차</b>: 이름에 ‘거주자우선주차’가 든 구간은 거주자 계약·공유 이용 요금이 "
                              "등록되어 있어 일반 이용 요금과 다를 수 있습니다(현장 확인).</li>"),
    },
}


def city_ui(city) -> dict:
    default = {"manager": "관리기관", "manager_inquiry": "관리기관", "merged_list": False,
               "merged_list": False, "district_short": False,
               "std_base_date": "", "realtime": False,
               "discount_note": "지자체 조례에 따라 감면율이 다릅니다. 현장 확인이 필요합니다.",
               "free_example": "", "calc_note": "차량 감면은 지자체 조례에 따라 다릅니다(현장 확인).",
               "daily_example": "1일 주차권 요금", "street_examples": "", "street_fee_caveat": ""}
    return {**default, **CITY_UI.get(city["city"] if city else "", {})}


def city_rows_total(city):
    """원자료에서 그 도시가 등록한 행 수(품질 리포트의 키 이름 차이를 흡수한다)."""
    q = city.get("quality") or {}
    for k in (f"원자료_{city['city']}행수", "원자료_행수"):
        if q.get(k) is not None:
            return q[k]
    return ""


def city_free_type_lots(city):
    """요금 구분이 '무료'인 주차장 수 — 주말에도 요금이 없다고 설명할 때 쓴다."""
    return city.get("quality", {}).get("요금구분", {}).get("무료", 0)


# ------------------------------------------------------- 자동 슬러그 (전국 확장)
# 국어의 로마자 표기법(문화체육관광부 고시)을 따르는 자동 슬러그 생성기.
#   · 이미 색인된 URL 은 GU_SLUG / DONG_SLUG / districts[].slug 매핑이 항상 우선하므로
#     수원시 39페이지 주소는 그대로 유지된다.
#   · 매핑에 없는 지역(다른 시·군·구·동)은 이름만으로 슬러그를 만들어 수동 딕셔너리 없이
#     같은 파이프라인에 편입할 수 있다.
#   · 음운 변화는 대표음(종성 ㄱ·ㄷ·ㅂ → k·t·p)과 ㄹ의 비음화·유음화만 반영한 간략 규칙이다.
CHO_ROM = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "",
           "j", "jj", "ch", "k", "t", "p", "h"]
JUNG_ROM = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe",
            "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
JONG_ROM = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p",
            "l", "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t"]
JONG_BIEUM = {1, 2, 3, 9, 24}      # ㄱ ㄲ ㄳ ㄺ ㅋ  → ㄹ 앞에서 [ŋ]
JONG_YUEUM = {4, 8}                # ㄴ ㄹ           → ㄹ 앞/뒤에서 [l]
CHO_N, CHO_R = 2, 5

ADMIN_SUFFIX = [("대로", "daero"), ("동", "dong"), ("읍", "eup"), ("면", "myeon"), ("리", "ri"),
                ("가", "ga"), ("길", "gil"), ("구", "gu"), ("시", "si"), ("군", "gun"), ("로", "ro"), ("도", "do")]


def romanize(text: str) -> str:
    """한글 문자열을 로마자로 옮긴다(한글 음절 단위, 음운 변화 일부 반영)."""
    chars = list(str(text or ""))
    out = []
    pending_cho = None          # 앞 음절의 영향으로 바뀐 다음 초성
    for i, ch in enumerate(chars):
        code = ord(ch)
        if not (0xAC00 <= code <= 0xD7A3):
            out.append(ch)
            pending_cho = None
            continue
        s = code - 0xAC00
        cho, jung, jong = s // 588, (s % 588) // 28, s % 28
        nxt = None
        if i + 1 < len(chars) and 0xAC00 <= ord(chars[i + 1]) <= 0xD7A3:
            nxt = (ord(chars[i + 1]) - 0xAC00) // 588

        jong_rom, cho_rom = JONG_ROM[jong], CHO_ROM[cho]
        if pending_cho is not None:
            cho_rom = pending_cho
        pending_cho = None
        if nxt == CHO_R:
            if jong in JONG_BIEUM:          # 백로 → baengno
                jong_rom, pending_cho = "ng", "n"
            elif jong in JONG_YUEUM:        # 신라 → silla
                jong_rom, pending_cho = "l", "l"
        out.append(cho_rom + JUNG_ROM[jung] + jong_rom)
    return "".join(out)


def base_slug(name: str) -> str:
    """행정 접미사를 분리해 소문자·하이픈 슬러그를 만든다. 예: 정자동 → jeongja-dong"""
    n = re.sub(r"\s+", "", str(name or ""))
    suffix = ""
    for tail, roman in ADMIN_SUFFIX:
        if n.endswith(tail) and len(n) - len(tail) >= 1:
            suffix, n = roman, n[: -len(tail)]
            break
    core = re.sub(r"[^a-z0-9]+", "-", romanize(n).lower()).strip("-")
    if not core:
        core = "x"
    return f"{core}-{suffix}" if suffix else core


def city_slug(city: str) -> str:
    """시·군 슬러그. 매핑이 없으면 이름으로 생성(성남시 → seongnam)."""
    if city in CITY_SLUG:
        return CITY_SLUG[city]
    core = base_slug(city)
    for suf in ("si", "gun", "gu"):
        if core.endswith("-" + suf):
            core = core[: -(len(suf) + 1)]
    return core or "region"


def gu_slug(gu: str, city: str = "수원시") -> str:
    """구 슬러그: 기존 매핑 우선, 없으면 시 슬러그 + 로마자(영통구 → suwon-yeongtong)."""
    if gu in GU_SLUG:
        return GU_SLUG[gu]
    core = base_slug(gu)
    for suf in ("gu", "gun", "si"):
        if core.endswith("-" + suf):
            core = core[: -(len(suf) + 1)]
    cs = city_slug(city)
    return f"{cs}-{core}" if core and core != cs else cs


def dong_slug(dong: str) -> str:
    """동 슬러그: 기존 매핑 우선, 없으면 로마자 자동 생성(정자동 → jeongja-dong)."""
    if dong in DONG_SLUG:
        return DONG_SLUG[dong]
    return base_slug(dong) or "etc"


def dong_slug_map(names) -> dict:
    """한 구 안에서 슬러그 충돌을 결정적으로 푸는 매핑(정렬 순서 고정)."""
    out, used = {}, set()
    for n in sorted(names):
        slug, k = dong_slug(n), 2
        while slug in used:
            slug = f"{dong_slug(n)}-{k}"
            k += 1
        used.add(slug)
        out[n] = slug
    return out


# ------------------------------------------------------------------ 경로
def city_path(city) -> str:
    return f"/parking/{city['province_slug']}/{city['slug']}/"


def district_path(city, d) -> str:
    return f"/parking/{city['province_slug']}/{d['slug']}/"


def street_path(city) -> str:
    return f"{city_path(city)}street-parking/"


# ------------------------------------------------------------------ utils
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def won(n) -> str:
    if n is None:
        return "—"
    return f"{int(round(n)):,}원"


def hhmm(m):
    if m is None:
        return ""
    h, mi = divmod(int(m), 60)
    return f"{h:02d}:{mi:02d}"


def price_for(lot, minutes=120, day="weekday", rate=0.0, exempt=0):
    """JS 계산기와 동일한 규칙 (서버 선계산용).

    exempt 는 조례상 '면제 시간'(분). exempt 이내 이용이면 0원(면제),
    넘으면 rate 만큼 감면한 금액을 낸다. 예: 성남 장애인 1시간 면제 후 50%.
    """
    if not lot["oper"].get(day):
        return {"state": "closed"}
    fee = lot["fee"]
    if fee["type"] == "무료" or (day != "weekday" and lot["free_days"].get(day)):
        return {"state": "free"}
    if exempt and minutes <= exempt:
        return {"state": "free", "exempt": True, "exempt_min": exempt}
    if fee["type"] != "유료" or not fee["base_min"] or fee["base_fee"] is None \
            or not fee["unit_min"] or fee["unit_fee"] is None:
        return {"state": "unknown"}
    if minutes <= fee["base_min"]:
        raw = fee["base_fee"]
    else:
        raw = fee["base_fee"] + math.ceil((minutes - fee["base_min"]) / fee["unit_min"]) * fee["unit_fee"]
    capped = False
    if fee["daily_fee"] and raw > fee["daily_fee"]:
        raw = fee["daily_fee"]
        capped = True
    return {"state": "paid", "amount": round(raw * (1 - rate)), "before": round(raw),
            "capped": capped, "discounted": rate > 0}


def hours_text(lot) -> str:
    hs = lot["hours"]
    all24 = all(hs[k]["open"] and hs[k]["24h"] for k in ("weekday", "sat", "sun"))
    if all24:
        return "24시간 운영(연중)"
    parts = []
    for k, label in (("weekday", "평일"), ("sat", "토"), ("sun", "일·공휴일")):
        h = hs[k]
        if not h["open"]:
            parts.append(f"{label} 휴무")
        elif h["24h"]:
            parts.append(f"{label} 24시간")
        else:
            parts.append(f"{label} {hhmm(h['start'])}~{hhmm(h['end'])}")
    return " · ".join(parts)


def fee_text(lot) -> str:
    f = lot["fee"]
    if f["type"] == "미상":
        return "요금 정보 없음 · 현장 확인"
    if f["type"] == "무료":
        return "무료"
    bits = [f"기본 {f['base_min']}분 {won(f['base_fee'])}"]
    if f["unit_min"] and f["unit_fee"] is not None:
        bits.append(f"추가 {f['unit_min']}분 {won(f['unit_fee'])}")
    if f["daily_fee"]:
        bits.append(f"1일권 {won(f['daily_fee'])}" + (f"({f['daily_hours']}시간)" if f["daily_hours"] else ""))
    if f["monthly"]:
        bits.append(f"월 {won(f['monthly'])}")
    return " · ".join(bits)


def addr_text(lot) -> str:
    a = lot["addr_jibun"] or lot["addr_road"]
    if a:
        return a
    dong = lot["dong"] or lot.get("city", "주소")
    return f"상세 주소 미제공 · {dong} 인근(지도 좌표 기준)"


def map_links(lot):
    name = lot["name"]
    lat, lng = lot["lat"], lot["lng"]
    city = lot.get("city", "")
    if lat and lng:
        kakao = f"https://map.kakao.com/link/map/{quote(name)},{lat},{lng}"
        naver = f"https://map.naver.com/p?c={lng},{lat},16"
    else:
        kakao = f"https://map.kakao.com/?q={quote(name + ' ' + city)}"
        naver = f"https://map.naver.com/p/search/{quote(name + ' ' + city)}"
    return kakao, naver


def free_note(lot):
    """무료 개방 관련 표기 문장."""
    if lot["fee"]["type"] == "무료":
        return "원자료상 요금 구분이 '무료'입니다."
    out = []
    if lot["free_days"].get("sun"):
        out.append("일요일·공휴일 무료 개방")
    if lot["free_days"].get("sat"):
        out.append("토요일 무료 개방")
    if out:
        return " · ".join(out) + " (원자료 특기사항 기준)"
    return None


def is_free_lot(lot) -> bool:
    return lot["fee"]["type"] == "무료" or lot["free_days"]["sat"] or lot["free_days"]["sun"]


def capa_note(lot) -> str:
    """구획수(표준데이터 등록면수)와 실시간 스냅샷 총면수가 다를 때의 짧은 설명.

    두 값은 기준이 다르다. 예: 매탄4지구는 구획 60면으로 등록됐지만
    스냅샷 합계는 58면이다. 두 숫자가 한 카드에 같이 나오면 모순처럼 보이므로
    차이를 숫자로 밝힌다.
    """
    rt = lot.get("realtime") or {}
    spaces, total = lot.get("spaces") or 0, rt.get("total") or 0
    if not (spaces and total) or spaces == total:
        return ""
    return f"등록 구획 {spaces:,}면과 {abs(total - spaces):,}면 차이"


def stats_for(lots):
    paid = [l["fee"]["base_fee"] for l in lots
            if l["fee"]["type"] == "유료" and l["fee"]["base_fee"]]
    return {
        "n": len(lots),
        "spaces": sum(l["spaces"] or 0 for l in lots),
        "free": len([l for l in lots if is_free_lot(l)]),
        "sun_free": len([l for l in lots if l["free_days"]["sun"] or l["fee"]["type"] == "무료"]),
        "sat_free": len([l for l in lots if l["free_days"]["sat"] or l["fee"]["type"] == "무료"]),
        "avg_base": round(sum(paid) / len(paid)) if paid else None,
        "unknown_fee": len([l for l in lots if l["fee"]["type"] == "미상"]),
        "closed_sat": len([l for l in lots if not l["oper"]["sat"]]),
        "closed_sun": len([l for l in lots if not l["oper"]["sun"]]),
        "live": len([l for l in lots if l.get("realtime")]),
        "capa_gap": len([l for l in lots if capa_note(l)]),
    }


# ------------------------------------------------------------------ jsonld
def jsonld_breadcrumb(items):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            dict([("@type", "ListItem"), ("position", i + 1), ("name", name)]
                 + ([("item", SITE_BASE + path if path else SITE_BASE + "/")] if path is not None else []))
            for i, (name, path) in enumerate(items)
        ],
    }


def jsonld_itemlist(lots, path):
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "공영주차장 목록",
        "numberOfItems": len(lots),
        "itemListOrder": "https://schema.org/ItemListOrderAscending",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1,
             "name": lot["name"],
             "url": f"{SITE_BASE}{path}#lot-{i + 1}"}
            for i, lot in enumerate(lots)
        ],
    }


def jsonld_faq(qa, path):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qa
        ],
    }


def script_jsonld(objs):
    return "\n".join(
        '<script type="application/ld+json">' + json.dumps(o, ensure_ascii=False) + "</script>"
        for o in objs if o
    )


# ------------------------------------------------------------------ layout
def nav_html(city, url, nav_active) -> str:
    """상단 지역 메뉴: 도시 허브 + (현재 도시의) 구 + 다른 도시들."""
    items = []
    for c in SITE_CITIES:
        here = bool(city) and c["city"] == city["city"]
        hub = city_path(c)
        if here:
            items.append((hub, f"{c['city']} 전체", nav_active == "city"))
            for d in c["districts"]:
                items.append((district_path(c, d), d["name"], nav_active == d["name"]))
        else:
            items.append((hub, f"{c['city']} 전체" if city else c["city"], False))
    # 도시 허브가 맨 앞에 오도록 정렬(현재 도시는 이미 앞)
    return ('<nav class="site-nav" aria-label="지역">'
            + "".join(f'<a href="{url(p)}"' + (" class=on" if on else "") + f">{esc(n)}</a>"
                      for p, n, on in items)
            + "</nav>")


def footer_sources(city, url) -> str:
    if not city:
        links = " · ".join(f'<a href="{url(city_path(c))}">{esc(c["city"])}</a>' for c in SITE_CITIES)
        return (f'    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 '
                f'<a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">'
                f'전국주차장정보표준데이터</a>를 결합해 만든 참고용 정보입니다. '
                f'실제 요금·운영시간은 현장에서 확인하세요.</p>\n'
                f'    <p>생성 시각 {esc(BUILD_TS)} · 페이지 내 잔여면수는 조회 시점 스냅샷입니다.</p>\n'
                f'    <p>{links} · <a href="{url("/sitemap.xml")}">사이트맵</a></p>\n')
    if city["city"] == "성남시":
        std_rows = city.get("quality", {}).get("원자료_성남시행수", "")
        return (f'    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 '
                f'<a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">'
                f'전국주차장정보표준데이터</a>(성남시 {std_rows}행, 기준일 '
                f'{esc(city_ui(city)["std_base_date"])})와 '
                f'<a href="https://park.isdc.co.kr/roadout/useinfo_fee3.do" rel="nofollow noopener" target="_blank">'
                f'성남도시개발공사 공영주차장 요금·감면 안내</a>를 기준으로 만든 참고용 정보입니다. '
                f'실제 요금·운영시간은 현장에서 확인하세요.</p>\n'
                f'    <p>생성 시각 {esc(BUILD_TS)} · 실시간 잔여면수는 연동하지 않았습니다.</p>\n'
                f'    <p><a href="{url(city_path(city))}">{esc(city["city"])} 전체 보기</a> · '
                f'<a href="{url("/sitemap.xml")}">사이트맵</a></p>\n')
    if city["city"] == "용인시":
        std_rows = city_rows_total(city)
        return (f'    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 '
                f'<a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">'
                f'전국주차장정보표준데이터</a>(용인시 {std_rows}행, 기준일 '
                f'{esc(city_ui(city)["std_base_date"])})와 '
                f'<a href="https://park.yuc.co.kr/views/parkinglot/fee/fee.html" rel="nofollow noopener" target="_blank">'
                f'용인시 공영주차장 주차장 요금 안내</a>(용인도시공사)를 기준으로 만든 참고용 정보입니다. '
                f'실제 요금·운영시간은 현장에서 확인하세요.</p>\n'
                f'    <p>생성 시각 {esc(BUILD_TS)} · 실시간 잔여면수는 연동하지 않았습니다.</p>\n'
                f'    <p><a href="{url(city_path(city))}">{esc(city["city"])} 전체 보기</a> · '
                f'<a href="{url("/sitemap.xml")}">사이트맵</a></p>\n')
    if city["city"] == "화성시":
        std_rows = city_rows_total(city)
        return (f'    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 '
                f'<a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">'
                f'전국주차장정보표준데이터</a>(화성시 {std_rows}행, 기준일 '
                f'{esc(city_ui(city)["std_base_date"])})와 '
                f'<a href="https://smartparking.hscity.go.kr/Main" rel="nofollow noopener" target="_blank">'
                f'화성시 통합주차포털</a>(화성도시공사 · 요금·감면 안내)을 기준으로 만든 참고용 정보입니다. '
                f'화성시는 2026-03-01 4개 구(만세·효행·병점·동탄) 체제로 바뀌었습니다. '
                f'실제 요금·운영시간은 현장에서 확인하세요.</p>\n'
                f'    <p>생성 시각 {esc(BUILD_TS)} · 실시간 잔여면수는 연동하지 않았습니다.</p>\n'
                f'    <p><a href="{url(city_path(city))}">{esc(city["city"])} 전체 보기</a> · '
                f'<a href="{url("/sitemap.xml")}">사이트맵</a></p>\n')
    if city["city"] != "수원시":
        # 새로 확장하는 시·군의 기본 문구 — 수원도시공사 자료를 언급하지 않는다.
        std_rows = city_rows_total(city)
        return (f'    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 '
                f'<a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">'
                f'전국주차장정보표준데이터</a>({esc(city["city"])} {std_rows}행, 기준일 '
                f'{esc(city_ui(city)["std_base_date"])})를 기준으로 만든 참고용 정보입니다. '
                f'실제 요금·운영시간은 현장에서 확인하세요.</p>\n'
                f'    <p>생성 시각 {esc(BUILD_TS)}</p>\n'
                f'    <p><a href="{url(city_path(city))}">{esc(city["city"])} 전체 보기</a> · '
                f'<a href="{url("/sitemap.xml")}">사이트맵</a></p>\n')
    return (f'    <p><strong>{SITE_NAME}</strong>는 공공데이터포털 '
            f'<a href="https://www.data.go.kr/data/15012896/standard.do" rel="nofollow noopener" target="_blank">'
            f'전국주차장정보표준데이터</a>(기준일 2026-04-16)와 '
            f'<a href="https://parking.suwonudc.co.kr/parking/parkingMap" rel="nofollow noopener" target="_blank">'
            f'수원도시공사 공영주차장 안내</a>,\n    '
            f'<a href="https://www.data.go.kr/data/15157772/fileData.do" rel="nofollow noopener" target="_blank">'
            f'경기도 수원시 공영노외주차장현황</a>(기준일 2026-08-01)을 결합해 만든 참고용 정보입니다. '
            f'실제 요금·운영시간은 현장에서 확인하세요.</p>\n'
            f'    <p>생성 시각 {esc(BUILD_TS)} · 페이지 내 잔여면수는 조회 시점 스냅샷입니다.</p>\n'
            f'    <p><a href="{url(city_path(city))}">{esc(city["city"])} 전체 보기</a> · '
            f'<a href="{url("/sitemap.xml")}">사이트맵</a></p>\n')


def layout(*, title, description, path, body, crumbs, jsonld, nav_active, city=None,
           extra_head="", absolute_links=False, robots="index,follow,max-image-preview:large",
           canonical=None):
    """공통 껍데기.

    absolute_links=True 이면 링크를 사이트 절대경로(/parking/...)로 쓴다. 404.html 처럼
    요청 주소가 그대로 유지되는 페이지는 상대경로가 어긋나므로 반드시 절대경로여야 한다.
    """
    canonical = SITE_BASE + path if canonical is None else canonical
    url = (lambda t: "/" + t.lstrip("/")) if absolute_links else (lambda t: rel(path, t))
    # canonical·og:url 은 색인하지 않는 페이지(404)에서는 비운다
    canonical_tag = f'<link rel="canonical" href="{canonical}">\n' if canonical else ""
    og_url_tag = f'<meta property="og:url" content="{canonical}">\n' if canonical else ""
    nav = nav_html(city, url, nav_active)
    crumb_html = '<nav aria-label="현재 위치"><ol class="crumbs">' + "".join(
        f'<li><a href="{url(p)}">{esc(n)}</a></li>' if p else f"<li>{esc(n)}</li>"
        for n, p in crumbs) + "</ol></nav>"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{canonical_tag}<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
{og_url_tag}<meta name="robots" content="{robots}">
<meta name="generator" content="parking-finder static builder">
{extra_head}
<link rel="stylesheet" href="{url('/assets/style.css')}">
{script_jsonld(jsonld)}
</head>
<body>
<header class="site-head">
  <div class="inner">
    <a class="brand" href="{url('/')}">
      <span class="dot">P</span>
      <span>{SITE_NAME}<small>공영주차장 요금·무료 개방 계산</small></span>
    </a>
    {nav}
  </div>
</header>
<main class="wrap">
{crumb_html}{body}
</main>
<footer class="site-foot">
  <div class="inner">
{footer_sources(city, url)}  </div>
</footer>
<script src="{url('/assets/app.js')}" defer></script>
</body>
</html>
"""


def rel_prefix(path: str) -> str:
    """현재 페이지 깊이에 맞는 상대 루트 접두어."""
    parts = [x for x in path.strip("/").split("/") if x]
    return "../" * len(parts)


def rel(path: str, target: str) -> str:
    """사이트 절대경로(/parking/...)를 현재 페이지 기준 상대경로로."""
    t = target.lstrip("/")
    return rel_prefix(path) + t if t else (rel_prefix(path) or "./")


# ------------------------------------------------------------------ pieces
def ad_slot(kind="inline"):
    return ('<div class="ad-slot" role="complementary" aria-label="광고">'
            '<span class="ad-label">Sponsored · 광고 영역(테스트)</span>'
            '<div class="ad-box"><span>Google AdSense 광고 자리</span>'
            '<span>모바일 320×100 / 데스크톱 728×90 · 실제 게재 시 이 자리표시자를 교체</span></div>'
            '</div>')


def park_label(city) -> str:
    """주차장 유형 표기 — 부설주차장이 있는 도시는 '노외·부설'로 적는다."""
    kinds = (city.get("quality") or {}).get("노외_부설") or {}
    return "노외·부설" if kinds.get("부설") else "노외"


def city_weekend_free_lots(city):
    """요금 구분은 유료지만 특기사항에 주말·공휴일 무료 개방이 적힌 카드 주차장 수."""
    return len([l for l in (city.get("_card_lots") or [])
                if l["fee"]["type"] != "무료" and (l["free_days"]["sat"] or l["free_days"]["sun"])])


def free_label(city) -> str:
    """통계 카드의 무료 항목 이름 — 요금 구분 '무료'가 있으면 그대로 '무료'로 적는다."""
    if city.get("weekend_free_pages") or city_weekend_free_lots(city):
        return "무료·주말무료"
    if city_free_type_lots(city):
        return "무료"
    return "무료 개방 표기"


def stat_cards(lots, *, extra_free_label=""):
    s = stats_for(lots)
    return f"""<div class="stats">
  <div class="stat"><span class="k">등록 주차장</span><span class="v">{s['n']}<small>곳</small></span></div>
  <div class="stat free"><span class="k">{esc(extra_free_label or '무료·주말무료')}</span><span class="v">{s['free']}<small>곳</small></span></div>
  <div class="stat"><span class="k">평균 기본요금</span><span class="v">{won(s['avg_base']) if s['avg_base'] else '—'}</span></div>
</div>"""


def default_discounts():
    """도시별 감면 설정이 없을 때의 공통 버튼(기존 수원시 화면과 동일)."""
    return [
        {"label": "일반 차량", "rate": 0.0, "exempt_min": 0, "note": ""},
        {"label": "경차·저공해·다자녀 50%", "rate": 0.5, "exempt_min": 0, "note": ""},
        {"label": "국가유공자·장애인 80%", "rate": 0.8, "exempt_min": 0, "note": ""},
    ]


def calculator(lots, default_day="weekday", default_minutes=120, path="", mode="district",
               discounts=None):
    s = stats_for(lots)
    day_btn = "".join(
        f'<button type="button" class="seg-btn" data-day="{k}" aria-pressed="{"true" if k == default_day else "false"}">'
        f'{DAY_LABEL[k]}'
        + (f"<small>{s['sat_free']}곳 무료</small>" if k == "sat" else "")
        + (f"<small>{s['sun_free']}곳 무료</small>" if k == "sun" else "")
        + "</button>"
        for k in ("weekday", "sat", "sun")
    )
    opts = discounts if discounts else default_discounts()
    disc_btn = "".join(
        f'<button type="button" class="seg-btn" data-rate="{o["rate"]}" data-exempt="{o.get("exempt_min") or 0}"'
        f' aria-pressed="{"true" if i == 0 else "false"}">{esc(o["label"])}'
        + (f'<small>{esc(o.get("note") or "")}</small>' if o.get("note") else "")
        + "</button>"
        for i, o in enumerate(opts)
    )
    cols = "cols-2" if len(opts) > 3 else "cols-3"
    return f"""<section class="calc" aria-labelledby="calc-title">
  <h2 id="calc-title">내 주차 조건으로 바로 계산</h2>
  <p class="hint">요일과 시간을 고르면 아래 목록의 예상 요금이 즉시 다시 계산되고 저렴한 순으로 정렬됩니다.</p>

  <div class="field">
    <span class="label">이용 요일</span>
    <div class="seg cols-3" id="day-group" role="group" aria-label="이용 요일">{day_btn}</div>
  </div>

  <div class="field">
    <div class="slider-row">
      <span class="label" style="margin:0">예상 주차 시간</span>
      <span class="time-value" id="time-label" aria-live="polite">2<span class="w">시간</span></span>
    </div>
    <input type="range" id="time-slider" min="30" max="1440" step="10" value="{default_minutes}"
           aria-label="예상 주차 시간(분)" aria-valuetext="2시간">
    <div class="ticks"><span>30분</span><span>6시간</span><span>12시간</span><span>24시간</span></div>
    <div class="chips">
      <button type="button" class="chip" data-minutes="30">30분</button>
      <button type="button" class="chip" data-minutes="60">1시간</button>
      <button type="button" class="chip" data-minutes="120">2시간</button>
      <button type="button" class="chip" data-minutes="240">4시간</button>
      <button type="button" class="chip" data-minutes="1440">하루</button>
    </div>
  </div>

  <div class="field">
    <span class="label">차량 감면(가정)</span>
    <div class="seg {cols}" id="discount-group" role="group" aria-label="차량 감면">{disc_btn}</div>
  </div>

  <div class="calc-result" id="calc-summary">계산 중…</div>
</section>"""


def lot_card(lot, idx, default_day="weekday", default_minutes=120):
    res = price_for(lot, default_minutes, default_day)
    if res["state"] == "free":
        # 요금 구분이 '무료'인 주차장은 요일과 관계없이 무료라 ‘선택한 요일’이라고 쓰지 않는다.
        free_note_text = ("요금 구분 ‘무료’" if lot["fee"]["type"] == "무료"
                          else "무료 개방 (선택한 요일)")
        price_html = (f'<span class="price free">0원</span>'
                      f'<span class="price-note">{esc(free_note_text)}</span>')
    elif res["state"] == "paid":
        extra = []
        if res["capped"]:
            extra.append("1일권 상한 적용")
        price_html = (f'<span class="price paid">{won(res["amount"])}</span>'
                      f'<span class="price-note">{esc(" · ".join(extra) or "기본요금·추가요금 기준")}</span>')
    elif res["state"] == "unknown":
        price_html = '<span class="price unknown">요금 정보 미상</span><span class="price-note">현장 확인 필요</span>'
    else:
        price_html = '<span class="price closed">휴무</span><span class="price-note">선택한 요일에 운영하지 않음</span>'

    badges = [f'<span class="badge kind">{esc(lot["kind"] or "공영")}</span>',
              f'<span class="badge">{esc(lot["ptype"] or "주차장")}</span>']
    if is_free_lot(lot):
        badges.append(f'<span class="badge free">{"무료" if lot["fee"]["type"] == "무료" else "무료개방"}</span>')
    if lot.get("realtime"):
        rt = lot["realtime"]
        badges.append(f'<span class="badge live">실시간 {rt["free"]}면</span>')
    if lot["fee"]["type"] == "미상":
        badges.append('<span class="badge unknown">요금 미확인</span>')

    addr_full = lot["addr_jibun"] or lot["addr_road"]
    show_dong = (bool(lot["dong"]) and lot["dong"] not in ("기타", UNKNOWN_DONG)
                 and (not addr_full or lot["dong"] not in addr_full))
    meta = [f'<li><b>구획</b> {lot["spaces"]:,}면</li>' if lot["spaces"] else "",
            f'<li><b>운영</b> {esc(hours_text(lot))}</li>',
            f'<li><b>동</b> {esc(lot["dong"])}' + ("(추정)" if lot.get("dong_src", "").startswith("좌표") else "") + '</li>' if show_dong else '']
    if lot["tel"]:
        meta.append(f'<li><b>전화</b> <a href="tel:{esc(lot["tel"])}">{esc(lot["tel"])}</a></li>')

    lines = [f'<p class="fee-line">요금: {esc(fee_text(lot))}</p>']
    if lot["fee"].get("pay"):
        lines.append(f'<p class="fee-line">결제: {esc(lot["fee"]["pay"])}</p>')
    if lot.get("realtime"):
        rt = lot["realtime"]
        gap = capa_note(lot)
        lines.append(f'<p class="fee-line">실시간 잔여 {rt["free"]}면 / {rt["total"]}면 · '
                     f'{esc(SNAPSHOT_TS)} 조회' + (f' · {esc(gap)}' if gap else '') + '</p>')
    fn = free_note(lot)
    if fn:
        lines.append(f'<p class="note-line">무료: {esc(fn)}</p>')
    note = lot["note"]
    if note and not (fn and "무료개방" in note.replace(" ", "")):
        lines.append(f'<p class="note-line">특기사항: {esc(note)}</p>')
    if lot.get("capa_detail"):
        cd = lot["capa_detail"]
        bits = [f'{k} {v}면' for k, v in (("장애인", cd.get("disabled")), ("경차", cd.get("compact")),
                                          ("전기차", cd.get("elec")), ("여성우선", cd.get("woman")),
                                          ("임산부", cd.get("pregnant"))) if v]
        if bits:
            lines.append(f'<p class="fee-line">구획 구성: {esc(" · ".join(bits))}</p>')
    lines.append(f'<p class="fee-line">자료 기준일: {esc(lot["base_date"])}</p>')

    kakao, naver = map_links(lot)
    return f"""<article class="card lot{' free' if res['state'] == 'free' else ''}" data-lot="{esc(lot['id'])}" id="lot-{idx}">
  <div class="lot-head">
    <h3>{esc(lot['name'])}</h3>
    <div class="badges">{''.join(badges)}</div>
  </div>
  <p class="addr">{esc(addr_text(lot))}</p>
  <ul class="meta">{''.join(m for m in meta if m)}</ul>
  <div class="price-row">{price_html}</div>
  {''.join(lines)}
  <div class="actions">
    <a class="btn solid" href="{esc(kakao)}" target="_blank" rel="nofollow noopener">카카오맵</a>
    <a class="btn" href="{esc(naver)}" target="_blank" rel="nofollow noopener">네이버지도</a>
  </div>
</article>"""


def lot_list(lots, path, default_day="weekday", with_ad=True, default_minutes=120):
    cards = []
    for i, lot in enumerate(lots, 1):
        cards.append(lot_card(lot, i, default_day))
        if with_ad and i == 5:
            cards.append(ad_slot())
    data = json.dumps([{
        "id": l["id"], "name": l["name"],
        "oper": l["oper"], "free_days": l["free_days"],
        "fee": {k: l["fee"][k] for k in ("type", "base_min", "base_fee", "unit_min", "unit_fee",
                                         "daily_hours", "daily_fee")},
    } for l in lots], ensure_ascii=False)
    return (f'<div class="list" id="lot-list" data-day="{default_day}" data-minutes="{default_minutes}">{"".join(cards)}</div>'
            f'<script type="application/json" id="lot-data">{data.replace("</", "<\\/")}</script>')


def faq_block(qa):
    items = "".join(
        f'<details class="faq"{" open" if i == 0 else ""}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'
        for i, (q, a) in enumerate(qa))
    return f'<h2>자주 묻는 질문</h2>{items}'


def two_h_price(lots, day="weekday"):
    """요일 기준 2시간 예상요금 목록(유료 계산 가능한 곳)."""
    return [price_for(l, 120, day)["amount"] for l in lots
            if price_for(l, 120, day)["state"] == "paid"]


def street_rows(street_lots, *, with_price=True, with_daily=None):
    """노상 구간 표 본문. 1일권 요금이 등록된 구간이 없으면(with_daily=None) 그 열을 빼다."""
    if with_daily is None:
        with_daily = any(l["fee"]["daily_fee"] for l in street_lots)
    rows = []
    for l in sorted(street_lots, key=lambda x: (x["gu"] or "", x.get("road") or "힣", x["name"])):
        road = l.get("road") or (f'{l["dong"]} 일대' if l.get("dong") else "지번 주소만 등록")
        p2 = price_for(l, 120, "weekday")
        amount = won(p2["amount"]) if p2["state"] == "paid" else ("무료" if p2["state"] == "free" else "현장 확인")
        addr = l["addr_jibun"] or l["addr_road"] or f'{l["name"]} {l.get("city", "")}'
        kurl = f"https://map.kakao.com/?q={quote(addr)}"
        rows.append(
            f'<tr><td><a href="{esc(kurl)}" target="_blank" rel="nofollow noopener">{esc(l["name"])}</a></td>'
            f'<td>{esc(l["gu"] or "-")}</td>'
            f'<td>{esc(road)}</td>'
            f'<td class="num">{l["spaces"]:,}</td>'
            + (f'<td class="num">{amount}</td>' if with_price else "")
            + (f'<td class="num">{won(l["fee"]["daily_fee"]) if l["fee"]["daily_fee"] else "-"}</td>'
               if with_daily else "") + "</tr>")
    head = ("<tr><th>구간</th><th>구</th><th>도로</th><th class=\"num\">구획</th>"
            + ("<th class=\"num\">평일 2시간</th>" if with_price else "")
            + ("<th class=\"num\">1일권</th>" if with_daily else "") + "</tr>")
    return f'<table class="data"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'


# ------------------------------------------------------------------ pages
def street_is_all_mixed(city) -> bool:
    """노상 구간이 모두 요금 구분 '혼합'(평일 운영시간만 유료)인 도시인지.

    성남시처럼 전 구간이 혼합이면 그에 맞는 설명을, 용인시처럼 무료·유료가 섞여 있으면
    등록값을 그대로 적는 설명을 쓴다.
    """
    st = city.get("_street_lots") or []
    return bool(st) and all(l["fee"].get("mixed") for l in st)


def district_dataset_lines(city, ui, gap_line) -> str:
    """구 페이지 ‘데이터 출처와 한계’ 목록 — 도시별로 실제 수집한 자료만 적는다."""
    q = city.get("quality") or {}
    if city["city"] == "수원시":
        return f"""    <li><b>요금·운영시간·구획수</b>: 공공데이터포털 전국주차장정보표준데이터(수원시 {q['원자료_수원시행수']}행, 기준일 2026-04-16)</li>
    <li><b>실시간 잔여면수·구획 구성</b>: 수원도시공사 공영주차장 안내 지도({esc(SNAPSHOT_TS)} 조회 스냅샷)</li>
    <li><b>구획수와 스냅샷 총면수</b>: 구획수는 표준데이터 <b>등록면수</b>, 잔여면수 옆 총면수는 안내 지도 <b>스냅샷 합계</b>입니다. {gap_line}</li>
    <li><b>주소·면수 보강</b>: 경기도 수원시 공영노외주차장현황(기준일 2026-08-01)</li>
    <li><b>요금 감면</b>: <a href="https://www.law.go.kr/LSW/ordinInfoP.do?ordinSeq=1985187" rel="nofollow noopener" target="_blank">수원시 주차장 조례</a>(2024-11-14 개정, 2025-01-01 시행)와 수원도시공사 요금 감면 안내(2026-11-16 확인)</li>
    <li>표준데이터에는 일요일 전용 운영시간 칸이 없어 <b>일요일은 공휴일 칸을 준용</b>했습니다.</li>
    <li>동 위치가 지번주소에 없는 주차장은 이름이나 좌표 최근접으로 추정했고, 카드에 ‘동 위치 추정’으로 표시했습니다.</li>"""
    if city["city"] == "성남시":
        return f"""    <li><b>요금·운영시간·구획수</b>: 공공데이터포털 전국주차장정보표준데이터(성남시 {q['원자료_성남시행수']}행 중 노외 {q['총_주차장']}곳, 기준일 {esc(ui['std_base_date'])})</li>
    <li><b>요금 감면</b>: 성남도시개발공사 공영주차장 요금·감면 안내(2026-11-16 확인)</li>
    <li>실시간 잔여면수는 연동하지 않았습니다. 카드의 구획수는 표준데이터 <b>등록면수</b>입니다.</li>
    <li>노상(거리) 주차 구간은 요금 구분이 ‘혼합’으로 등록되어 있어 카드가 아닌 표로 따로 정리했습니다.</li>
    <li>표준데이터에는 일요일 전용 운영시간 칸이 없어 <b>일요일은 공휴일 칸을 준용</b>했습니다.</li>
    <li>{city.get("dong_page_min_lots", DONG_PAGE_MIN_LOTS)}곳 미만인 동은 이 페이지의 ‘동별 주차장’ 표에만 싣고 별도 페이지를 만들지 않았습니다(빈 페이지 방지).</li>"""
    if city["city"] == "용인시":
        return f"""    <li><b>요금·운영시간·구획수</b>: 공공데이터포털 전국주차장정보표준데이터(용인시 {city_rows_total(city)}행 중 노외·부설 {q['총_주차장']}곳, 기준일 {esc(ui['std_base_date'])})</li>
    <li><b>요금 감면</b>: 용인도시공사 ‘용인시 공영주차장 주차장 요금 안내’의 감면할인 안내(2026-11-16 확인)</li>
    <li>실시간 잔여면수는 연동하지 않았습니다. 카드의 구획수는 표준데이터 <b>등록면수</b>입니다.</li>
    <li>용인시 요금표는 <b>최초 10분(청사·공원 부설은 최초 30분) 무료</b>를 두지만, 표준데이터의 기본요금·추가요금만으로 계산하므로 그보다 짧게 주차하면 예상요금이 실제보다 높게 나올 수 있습니다(현장 확인).</li>
    <li>부설주차장 일부는 특기사항에 ‘지하: 평일 06:00~20:00 운영’처럼 별도 운영시간이 적혀 있습니다. 카드는 등록된 운영요일·시간을 그대로 표시하고 특기사항을 함께 적었습니다(현장 확인).</li>
    <li>노상(거리) 주차 구간은 무료·유료가 섞여 있어 카드가 아닌 표로 따로 정리했습니다.</li>
    <li>표준데이터에는 일요일 전용 운영시간 칸이 없어 <b>일요일은 공휴일 칸을 준용</b>했습니다.</li>
    <li>{city.get("dong_page_min_lots", DONG_PAGE_MIN_LOTS)}곳 미만인 동·읍·면은 이 페이지의 표에만 싣고 별도 페이지를 만들지 않았습니다(빈 페이지 방지). 주소에 동이 없고 좌표로도 확인되지 않은 부설주차장은 ‘{UNKNOWN_DONG}’으로 묶었습니다.</li>"""
    if city["city"] == "화성시":
        return f"""    <li><b>요금·운영시간·구획수</b>: 공공데이터포털 전국주차장정보표준데이터(화성시 {city_rows_total(city)}행 중 노외 {q['총_주차장']}곳, 기준일 {esc(ui['std_base_date'])})</li>
    <li><b>요금 감면</b>: 「화성시 주차장 설치 및 관리 조례」 별표 4와 화성시 통합주차포털·화성도시공사 안내(2026-11-16 확인)</li>
    <li>화성시는 2026-03-01부터 만세·효행·병점·동탄 4개 구 체제입니다. 구·동 이름은 표준데이터 지번주소를 그대로 썼고, 동은 <b>법정동</b> 기준입니다(예: 동탄구 장지동).</li>
    <li>실시간 잔여면수는 연동하지 않았습니다. 카드의 구획수는 표준데이터 <b>등록면수</b>입니다.</li>
    <li>특기사항에 ‘최초 1시간 30분 무료 후 10분당 300원’처럼 현장 요금을 적은 주차장이 있습니다. 계산기는 기본요금·추가요금만 반영하므로 짧은 이용은 실제보다 높게 나올 수 있습니다(현장 확인).</li>
    <li>요금 필드가 비어 있는 주차장(예: 캠핑카 전용 임시주차장)은 0원이 아니라 <b>‘요금 정보 미상(현장 확인)’</b>으로 구분했습니다.</li>
    <li>노상(거리) 주차 구간은 이름이 구간·위치 설명이라 카드가 아닌 표로 따로 정리했습니다.</li>
    <li>표준데이터에는 일요일 전용 운영시간 칸이 없어 <b>일요일은 공휴일 칸을 준용</b>했습니다.</li>
    <li>{city.get("dong_page_min_lots", DONG_PAGE_MIN_LOTS)}곳 미만인 동·읍·면은 이 페이지의 표에만 싣고 별도 페이지를 만들지 않았습니다(빈 페이지 방지).</li>"""
    return f"""    <li><b>요금·운영시간·구획수</b>: 공공데이터포털 전국주차장정보표준데이터({esc(city['city'])} {city_rows_total(city)}행, 기준일 {esc(ui['std_base_date'])})</li>
    <li>실시간 잔여면수는 연동하지 않았습니다.</li>
    <li>표준데이터에는 일요일 전용 운영시간 칸이 없어 <b>일요일은 공휴일 칸을 준용</b>했습니다.</li>"""


def build_district(city, d, lots, site):
    gu = d["name"]
    path = district_path(city, d)
    s = stats_for(lots)
    ui = city_ui(city)
    lots_sorted = sorted(lots, key=lambda l: (
        0 if is_free_lot(l) else 1,
        l["fee"]["base_fee"] if l["fee"]["type"] == "유료" and l["fee"]["base_fee"] is not None else 9_999_999,
        l["name"]))

    dongs = {}
    for l in lots:
        dongs.setdefault(l["dong"] or UNKNOWN_DONG, []).append(l)
    dong_slugs = dong_slug_map(dongs)
    min_lots = city.get("dong_page_min_lots", DONG_PAGE_MIN_LOTS)
    dong_page_ok = {k: (k != UNKNOWN_DONG and len(v) >= min_lots) for k, v in dongs.items()}
    dong_rows = "".join(
        f'<tr><td>'
        + (f'<a href="{dong_slugs[k]}/">{esc(k)}</a>' if dong_page_ok[k] else esc(k))
        + f'</td><td class="num">{len(v)}</td><td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
        f'<td class="num">{sum(1 for x in v if is_free_lot(x))}</td></tr>'
        for k, v in sorted(dongs.items(), key=lambda kv: (kv[0] == UNKNOWN_DONG, -len(kv[1]))))

    # 구획수(등록면수) vs 스냅샷 총면수 차이 — 이 구에서 실제로 다른 곳만 예시로 든다
    gap = [l for l in lots if capa_note(l)]
    gap_line = (f"기준이 달라 {len(gap)}곳에서 숫자가 다르며(예: {esc(gap[0]['name'])} 구획 "
                f"{gap[0]['spaces']:,}면 ↔ 스냅샷 {gap[0]['realtime']['total']:,}면), 카드에 차이를 함께 적었습니다."
                if gap else "이 구 주차장은 두 값이 모두 일치합니다.")

    # 이 구의 노상 구간
    street = [l for l in city.get("_street_lots", []) if l["gu"] == gu]
    street_block = ""
    if street:
        st_free = len([l for l in street if l["fee"]["type"] == "무료"])
        st_paid = len([l for l in street if l["fee"]["type"] == "유료"])
        if street_is_all_mixed(city):
            intro = ("도로변에 설치된 유료 주차구간입니다. 요금 구분이 ‘혼합’으로 등록되어 있어 "
                     "<b>평일 운영시간에만 요금을 받고</b>, 토요일·일요일·공휴일은 운영시간이 등록되어 있지 않습니다.\n"
                     "무료 이용 가능 여부는 현장 표지를 확인하세요.")
        else:
            intro = (f"도로변에 설치된 공영 노상 주차구간입니다. 이 구 {len(street)}곳 가운데 "
                     f"<b>무료 {st_free}곳·유료 {st_paid}곳</b>이고, 무료 구간은 요일과 관계없이 요금이 없습니다. "
                     f"운영시간과 요금은 표의 등록값을 그대로 적었습니다.")
        street_block = f"""
<h2 style="margin-top:26px">{esc(gu)} 노상(거리) 주차 구간 {len(street)}곳</h2>
<p class="lede">{intro} 전체 {len(city.get("_street_lots", []))}구간은
<a href="{street_path(city)}">{esc(city['city'])} 노상주차장 요금 페이지</a>에 모아 두었습니다.</p>
{street_rows(street, with_price=True)}
"""
    free_in_gu = len([l for l in lots if l["fee"]["type"] == "무료"])
    free_weekend_in_gu = len([l for l in lots if l["fee"]["type"] != "무료"
                              and (l["free_days"]["sat"] or l["free_days"]["sun"])])
    weekend_link = (f"""
<h2>{esc(gu)} 주말·공휴일 무료 개방</h2>
<p class="lede">주말에 무료로 열리는 곳 {s['sun_free']}곳을 따로 모았습니다.
표기가 없는 주차장은 유료로 계산되니, 주말 방문 전에 확인하세요.</p>
<p><a class="btn solid" href="weekend-free/">주말·공휴일 무료 개방 주차장 보기 →</a></p>
""" if city.get("weekend_free_pages") else (
        f"""
<h2>{esc(gu)} 주말·공휴일 운영</h2>
<p class="lede">이 구 주차장 가운데 공공데이터에서 요금 구분이 <b>‘무료’</b>인 {free_in_gu}곳은 요일과 관계없이 무료입니다.
{(f"이 밖에 유료로 등록됐지만 특기사항에 ‘주말 및 공휴일 무료’가 적힌 곳이 {free_weekend_in_gu}곳 있습니다. " if free_weekend_in_gu else "")}그 밖의 유료 주차장은 주말에도 요금이 부과되고, 토요일 미운영 {s['closed_sat']}곳, 일요일·공휴일 미운영 {s['closed_sun']}곳입니다.
계산기의 요일을 ‘토요일’이나 ‘일요일·공휴일’로 바꾸면 그날 기준 예상요금으로 다시 정렬됩니다.</p>
""" if free_in_gu else f"""
<h2>{esc(gu)} 주말·공휴일 운영</h2>
<p class="lede">이 구 주차장은 공공데이터에 주말 무료 개방 표기가 없습니다.
토요일 미운영 {s['closed_sat']}곳, 일요일·공휴일 미운영 {s['closed_sun']}곳이며 나머지는 주말에도 요금이 부과됩니다.
계산기의 요일을 ‘토요일’이나 ‘일요일·공휴일’로 바꾸면 그날 기준 예상요금으로 다시 정렬됩니다.</p>
"""))

    dataset_lines = district_dataset_lines(city, ui, gap_line)
    daily_bullet = (f"1일 주차권 요금이 있으면 그 금액을 상한으로 적용합니다(예: {esc(ui['daily_example'])})."
                    if any(l["fee"]["daily_fee"] for l in lots) else
                    "이 구 주차장은 1일 주차권 요금이 등록되어 있지 않아, 상한 없이 기본요금·추가요금으로만 계산합니다.")

    qa = [
        (f"{gu} 공영주차장은 모두 몇 곳인가요?",
         (f"공공데이터포털 전국주차장정보표준데이터와 수원도시공사 안내 목록을 합쳐 {s['n']}곳이 등록되어 있습니다. "
          if ui["merged_list"] else
          f"공공데이터포털 전국주차장정보표준데이터에 등록된 {city['city']} {gu} {park_label(city)} 공영주차장은 {s['n']}곳입니다. ")
         + f"주차 구획은 총 {s['spaces']:,}면입니다."
         + (f" 이 밖에 노상(거리) 주차 구간 {len(street)}곳이 따로 등록되어 있습니다." if street else "")),
        (f"{gu}에서 일요일·공휴일에 무료로 주차할 수 있는 곳은?",
         ((f"요금 구분이 ‘무료’로 등록된 곳은 {free_in_gu}곳으로, 요일과 관계없이 무료입니다. "
           + (f"이 밖에 특기사항에 주말·공휴일 무료 개방이 적힌 곳이 {free_weekend_in_gu}곳 있습니다. "
              if free_weekend_in_gu else "")
           if (free_in_gu or free_weekend_in_gu) else
           f"자료에 무료 개방으로 표기된 곳은 {s['sun_free']}곳입니다. ")
          + (ui["free_example"] if s["sun_free"] else "")
          + f"표에 없는 주차장의 현장 무료 개방 여부는 관리기관({ui['manager']})에 확인하세요.")),
        (f"{gu} 공영주차장 2시간 요금은 얼마인가요?",
         (lambda prices: f"표준데이터 요금 기준 2시간 예상요금은 최저 {won(min(prices))}, "
                         f"중간값 {won(statistics.median(prices))}, 최고 {won(max(prices))}입니다. "
                         f"기본요금·추가단위요금을 그대로 계산한 값"
                         + ("이며 1일권 요금이 더 싸면 그 값으로 제한했습니다."
                            if any(l["fee"]["daily_fee"] for l in lots) else "입니다.")
          if prices else "요금 정보가 있는 주차장이 없어 계산할 수 없습니다.")(
             two_h_price(lots, "weekday"))),
        ("이 페이지의 요금·운영시간은 최신인가요?",
         f"요금·운영시간은 공공데이터포털 표준데이터(데이터 기준일 {ui['std_base_date']})를 그대로 반영했"
         + ("고, " if ui["realtime"] else "습니다. ")
         + (f"실시간 잔여면수는 {SNAPSHOT_TS} 조회 값입니다. " if ui["realtime"] else "")
         + "요금 개편이나 현장 정책(최초 N분 무료 등)으로 실제와 다를 수 있으니 방문 전에 관리기관에 확인하시기 바랍니다."),
    ]

    body = f"""
<h1>{esc(gu)} 공영주차장 {s['n']}곳 · 요금 계산과 무료 개방</h1>
<p class="lede">{esc(gu)} 공영주차장의 요금·운영시간·구획수를 공공데이터로 정리했습니다.
요일과 주차 시간을 고르면 예상 요금이 바로 계산되고, 무료로 개방되는 주차장이 맨 위로 올라옵니다.</p>
<p class="updated">자료 기준일 {esc(ui['std_base_date'])}{(' · 실시간 잔여면수 ' + esc(SNAPSHOT_TS) + ' 조회') if ui['realtime'] else ''}</p>
{stat_cards(lots, extra_free_label=free_label(city))}
{ad_slot()}
{calculator(lots, path=path, discounts=city.get("discounts"))}
<section class="note-box" style="margin-top:16px">
  <h2>요금 계산 방식</h2>
  <ul>
    <li>기본시간 이내는 기본요금, 초과분은 <b>추가단위시간마다 올림</b>해서 더합니다.</li>
    <li>{daily_bullet}</li>
    <li>{ui['calc_note']}</li>
    <li>요금 필드가 비어 있는 주차장은 0원으로 표시하지 않고 <b>‘요금 정보 미상(현장 확인)’</b>으로 구분합니다.</li>
  </ul>
</section>

<div class="toolbar">
  <h2>주차장 목록</h2>
  <span class="count">저렴한 순 자동 정렬 · 총 {s['n']}곳</span>
</div>
{lot_list(lots_sorted, path, with_ad=True)}

<h2>{esc(gu)} {esc(ui.get('dong_unit_label', '동'))}별 주차장</h2>
<table class="data">
  <thead><tr><th>동</th><th class="num">주차장</th><th class="num">구획</th><th class="num">무료</th></tr></thead>
  <tbody>{dong_rows}</tbody>
</table>
<p class="updated">동 이름을 누르면 해당 동의 주차장만 모아 볼 수 있습니다.{f' {min_lots}곳 미만인 동은 표에만 표시됩니다.' if min_lots > 1 else ''}{f' ‘{UNKNOWN_DONG}’은 주소에 동이 없고 좌표로도 확인되지 않은 곳으로, 이 페이지 목록에만 실었습니다.' if UNKNOWN_DONG in dongs else ''}</p>
{weekend_link}{street_block}
{faq_block(qa)}

<section class="note-box" style="margin-top:20px">
  <h2>데이터 출처와 한계</h2>
  <ul>
{dataset_lines}
  </ul>
</section>
"""
    crumbs = [("홈", "/"), ("경기도", None), (city["city"], city_path(city)),
              (f"{gu} 공영주차장", "")]
    return path, layout(
        title=f"{gu} 공영주차장 {s['n']}곳 요금·무료 개방 총정리 | {SITE_NAME}",
        description=f"{gu} 공영주차장 {s['n']}곳의 주차요금, 운영시간, 구획수, 주말·공휴일 무료 개방 정보를 "
                    f"공공데이터로 정리했습니다. 2시간 주차 예상요금과 무료 개방 여부를 바로 계산해 보세요.",
        path=path, body=body, crumbs=crumbs, nav_active=gu, city=city,
        jsonld=[jsonld_breadcrumb(crumbs),
                jsonld_itemlist(lots_sorted, path),
                jsonld_faq(qa, path)])


def build_weekend(city, d, lots, site):
    gu = d["name"]
    path = f"{district_path(city, d)}weekend-free/"
    ui = city_ui(city)
    free_lots = [l for l in lots if is_free_lot(l)]
    # 주말 대안: 일요일 기준 예상요금 낮은 순
    alt = sorted(
        [l for l in lots if price_for(l, 120, "sun")["state"] == "paid"],
        key=lambda l: price_for(l, 120, "sun")["amount"])[:8]
    s = stats_for(lots)

    qa = [
        (f"{gu}에서 주말에 무료로 주차할 수 있는 공영주차장은?",
         f"공식 자료에 무료 개방으로 표기된 곳은 {len(free_lots)}곳입니다. "
         + (", ".join(l["name"] for l in free_lots) + "입니다. " if free_lots else "")
         + "나머지 주차장은 토요일·일요일에도 요금이 부과되며, 현장 무료 개방 여부는 관리기관에 확인해야 합니다."),
        (f"{gu} 공영주차장 중 일요일에 문을 닫는 곳이 있나요?",
         f"일요일·공휴일 미운영으로 등록된 곳은 {s['closed_sun']}곳, 토요일 미운영은 {s['closed_sat']}곳입니다. "
         "토요일에 운영하지 않는 곳은 카드의 운영시간에 ‘토 휴무’로 표시됩니다."),
        ("무료 개방 표기가 없는 주차장은 주말에 얼마인가요?",
         cheapeast_sun_sentence(alt)),
    ]

    if free_lots:
        list_html = lot_list(sorted(free_lots, key=lambda l: l["name"]), path, default_day="sun")
    else:
        list_html = ('<div class="note-box">현재 자료에는 이 구에서 주말·공휴일 무료 개방으로 표기된 주차장이 없습니다. '
                     '아래는 주말 기준 예상요금이 낮은 대안 목록입니다.</div>')

    alt_rows = "".join(
        f'<tr><td><a href="../#lot-{i+1}">{esc(l["name"])}</a></td>'
        f'<td class="num">{won(price_for(l, 120, "sun")["amount"])}</td>'
        f'<td class="num">{l["spaces"] or "-"}</td></tr>'
        for i, l in enumerate(alt))

    body = f"""
<h1>{esc(gu)} 주말·공휴일 무료 개방 공영주차장</h1>
<p class="lede">토요일·일요일·공휴일에 <b>요금 없이</b> 이용할 수 있는 주차장만 모았습니다.
공공데이터 특기사항에 무료 개방이 적힌 곳만 넣었고, 표기가 없는 곳은 넣지 않았습니다.</p>
<p class="updated">자료 기준일 {esc(ui['std_base_date'])} · 총 {s['n']}곳 중 무료 개방 {len(free_lots)}곳</p>
{stat_cards(lots, extra_free_label='주말·공휴일 무료')}
{ad_slot()}
<h2>무료 개방 주차장 {len(free_lots)}곳</h2>
{list_html}

<section class="note-box" style="margin-top:18px">
  <h2>‘무료 개방’이 적게 표시되는 이유</h2>
  <ul>
    <li>{esc(city['city'])} 공영주차장은 주말·공휴일에도 요금을 받는 곳이 대부분입니다. 조례상 감면은 경차·저공해차, 임산부, 국가유공자·장애인 등 <b>차량·사유별</b>로 적용됩니다.</li>
    <li>표준데이터에서 ‘무료 개방’은 주차장별 특기사항 칸에만 적히기 때문에, 적혀 있지 않다고 해서 반드시 유료라는 뜻은 아닙니다.</li>
    <li>현장에서 무료로 개방하는지 확인하려면 {esc(ui['manager_inquiry'])}에 문의하세요.</li>
  </ul>
</section>

<h2>주말 대안: 예상요금이 낮은 곳</h2>
<p class="lede">무료 개방 표기가 없는 주차장 중 일요일 2시간 기준 예상요금이 낮은 순서입니다.</p>
<table class="data">
  <thead><tr><th>주차장</th><th class="num">일요일 2시간</th><th class="num">구획</th></tr></thead>
  <tbody>{alt_rows}</tbody>
</table>

{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), (city["city"], city_path(city)),
              (f"{gu} 공영주차장", district_path(city, d)), ("주말·공휴일 무료 개방", "")]
    return path, layout(
        title=f"{gu} 주말·공휴일 무료 개방 공영주차장 {len(free_lots)}곳 | {SITE_NAME}",
        description=f"{gu}에서 토요일·일요일·공휴일에 무료로 이용할 수 있는 공영주차장 목록과 "
                    f"주말 예상요금이 낮은 대안 주차장을 공공데이터 기준으로 정리했습니다.",
        path=path, body=body, crumbs=crumbs, nav_active=gu, city=city,
        jsonld=[jsonld_breadcrumb(crumbs),
                jsonld_itemlist(free_lots or alt, path),
                jsonld_faq(qa, path)])


def cheapeast_sun_sentence(alt):
    if not alt:
        return "일요일에도 요금 정보가 있는 주차장이 없습니다. 계산기의 요일을 ‘일요일·공휴일’로 바꾸면 목록이 다시 정렬됩니다."
    first = alt[0]
    return (f"일요일 2시간 기준 예상요금이 가장 낮은 곳은 {first['name']} "
            f"{won(price_for(first, 120, 'sun')['amount'])}입니다. "
            "계산기의 요일을 ‘일요일·공휴일’로 바꾸면 전체 목록이 그날 기준으로 다시 정렬됩니다.")


def build_dong(city, d, dong, lots, site, slug_override=None):
    gu = d["name"]
    dslug = slug_override or dong_slug(dong)
    path = f"{district_path(city, d)}{dslug}/"
    ui = city_ui(city)
    s = stats_for(lots)
    lots_sorted = sorted(lots, key=lambda l: (0 if is_free_lot(l) else 1,
                                              l["fee"]["base_fee"] or 9_999_999, l["name"]))
    qa = [
        (f"{gu} {dong} 공영주차장은 몇 곳인가요?",
         f"{dong}에 등록된 공영주차장은 {s['n']}곳, 주차 구획은 총 {s['spaces']:,}면입니다. "
         f"이 가운데 무료 또는 주말 무료 개방 표기가 있는 곳은 {s['free']}곳입니다."),
        (f"{dong}에서 2시간 주차하면 얼마인가요?",
         (lambda prices: f"표준데이터 요금 기준 2시간 예상요금은 {won(min(prices))}부터 {won(max(prices))}까지입니다."
          if prices else "요금 정보가 있는 주차장이 없습니다.")
         (two_h_price(lots))),
        ("야간이나 주말에도 운영하나요?",
         "주차장마다 운영시간이 다릅니다. 카드의 ‘운영’ 항목에 평일·토요일·일요일·공휴일 시간이 표시되고, "
         "24시간 운영하는 곳은 ‘24시간 운영(연중)’으로 표기했습니다."),
    ]
    body = f"""
<h1>{esc(gu)} {esc(dong)} 공영주차장 {s['n']}곳</h1>
<p class="lede">{esc(dong)}에 있는 공영주차장만 모았습니다. 요일·시간을 고르면 예상 요금이 바로 바뀝니다.</p>
<p class="updated">자료 기준일 {esc(ui['std_base_date'])}</p>
{stat_cards(lots, extra_free_label=free_label(city))}
{ad_slot()}
{calculator(lots, path=path, discounts=city.get("discounts"))}
<div class="toolbar"><h2>주차장 목록</h2><span class="count">총 {s['n']}곳</span></div>
{lot_list(lots_sorted, path)}
<p style="margin-top:16px"><a class="btn" href="../">← {esc(gu)} 전체 주차장 보기</a></p>
{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), (city["city"], city_path(city)),
              (f"{gu} 공영주차장", district_path(city, d)), (dong, "")]
    return path, layout(
        title=f"{gu} {dong} 공영주차장 {s['n']}곳 요금·운영시간 | {SITE_NAME}",
        description=f"{gu} {dong} 공영주차장 {s['n']}곳의 위치, 주차요금, 운영시간, 무료 개방 여부를 "
                    f"공공데이터로 정리했습니다. 예상 주차요금을 바로 계산해 보세요.",
        path=path, body=body, crumbs=crumbs, nav_active=gu, city=city,
        jsonld=[jsonld_breadcrumb(crumbs), jsonld_itemlist(lots_sorted, path), jsonld_faq(qa, path)])


def build_city(city, lots, site):
    path = city_path(city)
    ui = city_ui(city)
    s = stats_for(lots)
    street = city.get("_street_lots", [])
    rows = []
    for d in city["districts"]:
        gl = [l for l in lots if l["gu"] == d["name"]]
        gs = stats_for(gl)
        rows.append(f'<tr><td><a href="../{d["slug"]}/">{d["name"]}</a></td><td class="num">{gs["n"]}</td>'
                    f'<td class="num">{gs["spaces"]:,}</td><td class="num">{won(gs["avg_base"]) if gs["avg_base"] else "-"}</td>'
                    f'<td class="num">{gs["free"]}</td></tr>')
    free_type_n = len([l for l in lots if l["fee"]["type"] == "무료"])
    cheap = sorted([l for l in lots if l["fee"]["type"] == "유료" and l["fee"]["base_fee"] is not None],
                   key=lambda l: price_for(l, 120)["amount"])[:8]
    cheap_rows = "".join(
        f'<tr><td><a href="../{gu_slug(l["gu"], city["city"])}/#lot-{i+1}">{esc(l["name"])}</a></td>'
        f'<td>{esc(l["gu"] or "-")}</td><td class="num">{won(price_for(l, 120)["amount"])}</td>'
        f'<td class="num">{l["spaces"] or "-"}</td></tr>' for i, l in enumerate(cheap))
    street_block = ""
    if street:
        by_gu = {}
        for l in street:
            by_gu.setdefault(l["gu"] or "-", []).append(l)
        if street_is_all_mixed(city):
            street_rows_html = "".join(
                f'<tr><td>{esc(g)}</td><td class="num">{len(v)}</td>'
                f'<td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
                f'<td class="num">{won(next((x["fee"]["base_fee"] for x in v if x["fee"]["base_fee"]), None))}</td></tr>'
                for g, v in sorted(by_gu.items()))
            street_block = f"""
<h2>노상(거리) 주차 구간 {len(street)}곳</h2>
<p class="lede">도로변 유료 주차구간은 요금 구분이 ‘혼합’으로 등록되어 있어 평일 운영시간에만 요금을 받습니다.
구간별 요금과 위치는 <a href="{street_path(city)}">노상주차장 요금 페이지</a>에 정리했습니다.</p>
<table class="data">
  <thead><tr><th>구</th><th class="num">구간</th><th class="num">구획</th><th class="num">기본요금(30분)</th></tr></thead>
  <tbody>{street_rows_html}</tbody>
</table>
"""
        else:
            n_free = len([l for l in street if l["fee"]["type"] == "무료"])
            street_rows_html = "".join(
                f'<tr><td>{esc(g)}</td><td class="num">{len(v)}</td>'
                f'<td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
                f'<td class="num">{len([x for x in v if x["fee"]["type"] == "무료"])}</td>'
                f'<td class="num">{won(next((x["fee"]["base_fee"] for x in v if x["fee"]["base_fee"]), None))}</td></tr>'
                for g, v in sorted(by_gu.items()))
            street_block = f"""
<h2>노상(거리) 주차 구간 {len(street)}곳</h2>
<p class="lede">도로변 공영 주차구간은 무료 {n_free}곳과 유료 {len(street) - n_free}곳으로 나뉩니다.
무료 구간은 요일과 관계없이 요금이 없고, 구간별 요금과 위치는 <a href="{street_path(city)}">노상주차장 요금 페이지</a>에 정리했습니다.</p>
<table class="data">
  <thead><tr><th>구</th><th class="num">구간</th><th class="num">구획</th><th class="num">무료</th><th class="num">기본요금</th></tr></thead>
  <tbody>{street_rows_html}</tbody>
</table>
"""
    qa = [
        (f"{city['city']} 공영주차장은 모두 몇 곳인가요?",
         (f"공공데이터와 수원도시공사 안내 목록을 합쳐 {s['n']}곳, 주차 구획 {s['spaces']:,}면입니다. "
          if ui["merged_list"] else
          f"공공데이터포털 표준데이터에 등록된 {city['city']} {park_label(city)} 공영주차장은 {s['n']}곳, 주차 구획 {s['spaces']:,}면입니다. ")
         + (f"이 밖에 노상(거리) 주차 구간 {len(street)}곳이 따로 등록되어 있습니다. " if street else "")
         + (f"이 가운데 요금 구분이 ‘무료’인 곳은 {free_type_n}곳입니다." if free_type_n
            else f"이 가운데 무료·주말 무료 개방 표기가 있는 곳은 {s['free']}곳입니다.")),
        (f"{city['city']}에서 주말에 무료인 공영주차장은 어디인가요?",
         (f"공식 자료에 일요일·공휴일 무료 개방으로 표기된 곳은 {s['sun_free']}곳입니다. "
          "구별 ‘주말·공휴일 무료 개방’ 페이지에서 확인할 수 있습니다.")
         if city.get("weekend_free_pages") else
         ((f"공공데이터의 요금 구분이 ‘무료’인 공영주차장이 {free_type_n}곳으로, 이 곳들은 요일과 관계없이 무료입니다. "
           "유료로 등록된 주차장은 주말에도 요금이 부과되고, 노상 구간은 무료·유료가 섞여 있습니다. "
           f"현장 무료 개방 여부는 {ui['manager']}에 확인하세요.")
          if city_free_type_lots(city) else
          (f"공공데이터에는 {city['city']} 노외 공영주차장의 주말 무료 개방 표기가 없습니다. "
           "주말에도 요금이 부과되는 곳이 대부분이고, 노상 구간은 평일 운영시간 외에는 운영시간이 등록되어 있지 않습니다. "
           f"현장 무료 개방 여부는 {ui['manager']}에 확인하세요."))),
        ("평일 2시간 주차요금이 가장 싼 곳은?",
         (f"{cheap[0]['name']}({cheap[0]['gu']})이 {won(price_for(cheap[0], 120)['amount'])}으로 가장 낮습니다."
          if cheap else "요금 정보가 없습니다.")),
    ]
    body = f"""
<h1>{city['city']} 공영주차장 {s['n']}곳 · 요금과 무료 개방 한눈에</h1>
<p class="lede">{city['city']} {len(city['districts'])}개 구({'·'.join(d['name'][:-1] if ui['district_short'] and d['name'].endswith('구') else d['name'] for d in city['districts'])})의 공영주차장을 공공데이터로 정리했습니다.
구를 고르면 요금 계산기와 주차장 목록으로 이동합니다.</p>
<p class="updated">자료 기준일 {esc(ui['std_base_date'])}{(' · 실시간 잔여면수 ' + esc(SNAPSHOT_TS) + ' 조회') if ui['realtime'] else ''}</p>
{stat_cards(lots, extra_free_label=free_label(city))}
{ad_slot()}
<h2>구별 현황</h2>
<table class="data">
  <thead><tr><th>구</th><th class="num">주차장</th><th class="num">구획</th><th class="num">평균 기본요금</th><th class="num">무료</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table>

<h2>구별로 찾기</h2>
<div class="grid-2">
{''.join(f'''<a class="link-card" href="../{d["slug"]}/">
  <span class="t">{d["name"]} 공영주차장<span class="go">{stats_for([l for l in lots if l['gu'] == d['name']])['n']}곳 →</span></span>
  <span class="d">{'요금 계산기 · 주말 무료 개방 · 동별 목록' if city.get('weekend_free_pages') else '요금 계산기 · 동별 목록'}</span>
</a>''' for d in city['districts'])}
</div>
{street_block}
<h2>평일 2시간 기준 가장 저렴한 곳</h2>
<table class="data">
  <thead><tr><th>주차장</th><th>구</th><th class="num">2시간</th><th class="num">구획</th></tr></thead>
  <tbody>{cheap_rows}</tbody>
</table>
{ad_slot()}
{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), (f"{city['city']} 공영주차장", "")]
    return path, layout(
        title=f"{city['city']} 공영주차장 {s['n']}곳 요금·무료 개방 지도 | {SITE_NAME}",
        description=f"{city['city']} {len(city['districts'])}개 구 공영주차장 {s['n']}곳의 주차요금, 운영시간, 무료 개방 정보를 정리했습니다. "
                    f"구별 요금 계산기로 2시간·하루 주차비를 바로 확인하세요.",
        path=path, body=body, crumbs=crumbs, nav_active="city", city=city,
        jsonld=[jsonld_breadcrumb(crumbs), jsonld_itemlist(cheap, path), jsonld_faq(qa, path)])


def build_street(city, street, site):
    """노상(거리) 주차 구간 전용 페이지 — 구간 이름이 번호·설명이라 카드 대신 표로 정리한다.

    도시별 요금 구조가 다르므로 두 갈래로 나눈다.
      · 전 구간이 ‘혼합’(성남시): 평일 운영시간만 유료 — 기존 문구 유지
      · 무료·유료가 섞인 도시(용인시): 구간별 등록값을 그대로 적는다
    """
    if street_is_all_mixed(city):
        return _build_street_all_mixed(city, street, site)
    return _build_street_mixed(city, street, site)


def _build_street_all_mixed(city, street, site):
    """노상 구간이 모두 요금 구분 ‘혼합’인 도시(성남시) 전용 페이지."""
    path = street_path(city)
    ui = city_ui(city)
    total_spaces = sum(l["spaces"] or 0 for l in street)
    by_gu = {}
    by_road = {}
    for l in street:
        by_gu.setdefault(l["gu"] or "-", []).append(l)
        key = l.get("road") or (f'{l["dong"]} 일대' if l.get("dong") else "지번 주소만 등록")
        by_road.setdefault(key, []).append(l)
    # 대표 요금(가장 많은 조합)
    fee_key = Counter((l["fee"]["base_min"], l["fee"]["base_fee"], l["fee"]["unit_min"],
                       l["fee"]["unit_fee"], l["fee"]["daily_fee"]) for l in street)
    (bmin, bfee, umin, ufee, dfee), fee_n = fee_key.most_common(1)[0]
    sample = next(l for l in street
                  if (l["fee"]["base_min"], l["fee"]["base_fee"], l["fee"]["unit_min"],
                      l["fee"]["unit_fee"], l["fee"]["daily_fee"]) == (bmin, bfee, umin, ufee, dfee))
    example_rows = "".join(
        f'<tr><td>{label}</td><td class="num">{won(price_for(sample, m, "weekday")["amount"])}</td></tr>'
        for label, m in (("30분", 30), ("1시간", 60), ("2시간", 120), ("4시간", 240), ("9시간(1일권 기준)", 540)))
    gu_rows = "".join(
        f'<tr><td>{esc(g)}</td><td class="num">{len(v)}</td>'
        f'<td class="num">{sum(x["spaces"] or 0 for x in v):,}</td></tr>'
        for g, v in sorted(by_gu.items()))
    road_rows = "".join(
        f'<tr><td>{esc(r)}</td><td class="num">{len(v)}</td>'
        f'<td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
        f'<td class="num">{won(next((x["fee"]["base_fee"] for x in v if x["fee"]["base_fee"]), None))}</td></tr>'
        for r, v in sorted(by_road.items(), key=lambda kv: -len(kv[1])))
    pay_text = ((sample or (paid or street)[0])["fee"]["pay"] or "현장 확인")

    qa = [
        (f"{city['city']} 노상주차장은 몇 곳인가요?",
         f"공공데이터포털 표준데이터에 등록된 {city['city']} 공영 노상(거리) 주차 구간은 {len(street)}곳, "
         f"주차 구획은 총 {total_spaces:,}면입니다. "
         f"{'·'.join(sorted(by_gu))}에 있습니다."),
        ("노상주차장은 언제 돈을 내나요?",
         f"요금 구분이 ‘혼합’으로 등록되어 있어 평일 {hhmm(sample['hours']['weekday']['start'])}~{hhmm(sample['hours']['weekday']['end'])}에만 요금을 받습니다. "
         f"토요일·일요일·공휴일은 운영시간이 등록되어 있지 않습니다(무료 이용 가능 여부는 현장 표지 확인). "
         f"기본 {bmin}분 {won(bfee)}, 이후 {umin}분마다 {won(ufee)}, 1일권 {won(dfee)}입니다."),
        ("노상주차장 요금은 어떻게 계산하나요?",
         f"기본 {bmin}분 {won(bfee)}이고, 초과분은 {umin}분마다 {won(ufee)}씩 올림해서 더합니다. "
         f"1일권({sample['fee']['daily_hours']}시간) {won(dfee)}이 상한입니다. "
         f"예를 들어 2시간은 {won(price_for(sample, 120, 'weekday')['amount'])}, 4시간은 "
         f"{won(price_for(sample, 240, 'weekday')['amount'])}입니다."),
        ("월정기권도 있나요?",
         f"구간별로 월정기권 요금이 등록되어 있습니다(대부분 월 {won(next((l['fee']['monthly'] for l in street if l['fee']['monthly']), None))}). "
         f"월정기 신청·대기는 {ui['manager']}에서 받습니다."),
    ]
    body = f"""
<h1>{city['city']} 노상주차장 {len(street)}구간 · 요금과 운영시간</h1>
<p class="lede">도로변에 설치된 공영 노상(거리) 주차구간입니다. 구간 이름이 ‘중상32-75’처럼 도로변 번호로 등록되어 있어
카드 대신 도로별 표로 정리했습니다. 평일 운영시간과 요금, 1일권 상한을 한눈에 확인하세요.</p>
<p class="updated">자료 기준일 {esc(ui['std_base_date'])} · {len(street)}구간 {total_spaces:,}면</p>
<div class="stats">
  <div class="stat"><span class="k">노상 구간</span><span class="v">{len(street)}<small>곳</small></span></div>
  <div class="stat"><span class="k">총 구획</span><span class="v">{total_spaces:,}<small>면</small></span></div>
  <div class="stat"><span class="k">평일 기본요금</span><span class="v">{won(bfee)}</span></div>
</div>
{ad_slot()}

<section class="note-box" style="margin-top:16px">
  <h2>노상주차장 요금·운영시간</h2>
  <ul>
    <li><b>운영시간</b>: 평일 {hhmm(sample['hours']['weekday']['start'])}~{hhmm(sample['hours']['weekday']['end'])} (토요일·일요일·공휴일 운영시간 미등록)</li>
    <li><b>요금</b>: 기본 {bmin}분 {won(bfee)} · 이후 {umin}분마다 {won(ufee)} · 1일권({sample['fee']['daily_hours']}시간) {won(dfee)}</li>
    <li><b>요금 구분</b>: 표준데이터에 ‘혼합’으로 등록 — 운영시간에는 유료, 그 외 시간대는 운영시간이 비어 있습니다.</li>
    <li><b>감면</b>: {esc(ui['discount_note'])}</li>
    <li><b>결제</b>: {esc(sample['fee']['pay'] or '현장 확인')}</li>
  </ul>
</section>

<h2>예상 요금</h2>
<table class="data">
  <thead><tr><th>이용 시간</th><th class="num">평일 예상요금</th></tr></thead>
  <tbody>{example_rows}</tbody>
</table>
<p class="updated">{fee_n}개 구간이 위 요금표와 같습니다. 1일권 요금이 더 싸면 그 금액을 상한으로 적용합니다.</p>

<h2>구별 현황</h2>
<table class="data">
  <thead><tr><th>구</th><th class="num">구간</th><th class="num">구획</th></tr></thead>
  <tbody>{gu_rows}</tbody>
</table>

<h2>도로별 현황</h2>
<table class="data">
  <thead><tr><th>도로</th><th class="num">구간</th><th class="num">구획</th><th class="num">기본요금(30분)</th></tr></thead>
  <tbody>{road_rows}</tbody>
</table>

<h2>구간별 목록</h2>
{street_rows(street)}
<p class="updated">주차구획은 표준데이터 등록면수입니다. 위치는 도로명·지번주소 기준이며, 구간 이름을 누르면 지도에서 찾을 수 있습니다.</p>
{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), (city["city"], city_path(city)), ("노상주차장 요금", "")]
    return path, layout(
        title=f"{city['city']} 노상주차장 {len(street)}구간 요금·운영시간 총정리 | {SITE_NAME}",
        description=f"{city['city']} 공영 노상(거리) 주차구간 {len(street)}곳의 요금(기본 {bmin}분 {won(bfee)}, "
                    f"1일권 {won(dfee)})과 평일 운영시간, 구간별 위치·구획수를 공공데이터로 정리했습니다.",
        path=path, body=body, crumbs=crumbs, nav_active="city", city=city,
        jsonld=[jsonld_breadcrumb(crumbs), jsonld_itemlist(street, path), jsonld_faq(qa, path)])


def _build_street_mixed(city, street, site):
    """노상 구간이 무료·유료로 섞인 도시(용인시) 전용 페이지.

    등록값이 구간마다 달라(무료 48구간 · 유료 6구간) 한 요금표로 묶지 않고,
    구간별 표에 등록된 요금을 그대로 적는다.
    """
    path = street_path(city)
    ui = city_ui(city)
    total_spaces = sum(l["spaces"] or 0 for l in street)
    free = [l for l in street if l["fee"]["type"] == "무료"]
    paid = [l for l in street if l["fee"]["type"] == "유료"]
    by_gu, by_road = {}, {}
    for l in street:
        by_gu.setdefault(l["gu"] or "-", []).append(l)
        key = l.get("road") or (f'{l["dong"]} 일대' if l.get("dong") else "지번 주소만 등록")
        by_road.setdefault(key, []).append(l)

    sample, fee_n = None, 0
    if paid:
        fee_key = Counter((l["fee"]["base_min"], l["fee"]["base_fee"], l["fee"]["unit_min"],
                           l["fee"]["unit_fee"], l["fee"]["daily_fee"]) for l in paid)
        (bmin, bfee, umin, ufee, dfee), fee_n = fee_key.most_common(1)[0]
        sample = next(l for l in paid
                      if (l["fee"]["base_min"], l["fee"]["base_fee"], l["fee"]["unit_min"],
                          l["fee"]["unit_fee"], l["fee"]["daily_fee"]) == (bmin, bfee, umin, ufee, dfee))

    gu_rows = "".join(
        f'<tr><td>{esc(g)}</td><td class="num">{len(v)}</td>'
        f'<td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
        f'<td class="num">{len([x for x in v if x["fee"]["type"] == "무료"])}</td></tr>'
        for g, v in sorted(by_gu.items()))
    road_rows = "".join(
        f'<tr><td>{esc(r)}</td><td class="num">{len(v)}</td>'
        f'<td class="num">{sum(x["spaces"] or 0 for x in v):,}</td>'
        f'<td class="num">{len([x for x in v if x["fee"]["type"] == "무료"])}</td></tr>'
        for r, v in sorted(by_road.items(), key=lambda kv: -len(kv[1])))

    if sample:
        example_rows = "".join(
            f'<tr><td>{label}</td><td class="num">{won(price_for(sample, m, "weekday")["amount"])}</td></tr>'
            for label, m in (("10분", 10), ("30분", 30), ("1시간", 60), ("2시간", 120), ("4시간", 240)))
        daily_txt = (f"1일권({sample['fee']['daily_hours'] or ''}시간) {won(dfee)}" if dfee else "")
        fee_line = (f"기본 {bmin}분 {won(bfee)} · 이후 {umin}분마다 {won(ufee)}"
                    + (f" · 1일권 {won(dfee)}" if dfee else ""))
        fee_box = f"""
    <li><b>유료 구간 요금</b>: {fee_line} ({fee_n}개 구간이 같은 요금)</li>
    <li><b>무료 구간</b>: {len(free)}곳은 요금 구분이 ‘무료’로 등록되어 있어 요일과 관계없이 무료입니다.</li>
    {ui['street_fee_caveat']}"""
        price_block = f"""<h2>유료 구간 예상 요금</h2>
<table class="data">
  <thead><tr><th>이용 시간</th><th class="num">평일 예상요금</th></tr></thead>
  <tbody>{example_rows}</tbody>
</table>
<p class="updated">{fee_n}개 구간이 위 요금표와 같습니다.{" 1일권 요금이 더 싸면 그 금액을 상한으로 적용합니다." if dfee else ""}</p>"""
    else:
        fee_box = """
    <li><b>요금</b>: 모든 구간이 요금 구분 ‘무료’로 등록되어 있습니다.</li>"""
        price_block = ""

    pay_text = ((sample or (paid or street)[0])["fee"]["pay"] or "현장 확인")

    qa = [
        (f"{city['city']} 노상주차장은 몇 곳인가요?",
         f"공공데이터포털 표준데이터에 등록된 {city['city']} 공영 노상(거리) 주차 구간은 {len(street)}곳, "
         f"주차 구획은 총 {total_spaces:,}면입니다. {'·'.join(sorted(by_gu))}에 있습니다. "
         f"이 가운데 무료 구간이 {len(free)}곳, 유료 구간이 {len(paid)}곳입니다."),
        (f"{city['city']} 노상주차장은 언제 무료인가요?",
         f"요금 구분이 ‘무료’로 등록된 {len(free)}곳은 요일과 관계없이 요금이 없습니다. "
         + (f"유료 구간 {len(paid)}곳은 기본 {bmin}분 {won(bfee)}부터 요금이 붙습니다. " if sample else "")
         + "구간별 등록값은 아래 표에 그대로 적었으니 현장 표지와 함께 확인하세요."),
        ("유료 노상주차장 요금은 어떻게 계산하나요?",
         (f"기본 {bmin}분 {won(bfee)}이고, 초과분은 {umin}분마다 {won(ufee)}씩 올림해서 더합니다. "
          + (f"{daily_txt}이 상한입니다. " if daily_txt else "")
          + f"예를 들어 2시간은 {won(price_for(sample, 120, 'weekday')['amount'])}, 4시간은 "
          f"{won(price_for(sample, 240, 'weekday')['amount'])}입니다.")
         if sample else "이 도시 노상 구간은 모두 무료로 등록되어 있어 계산할 유료 요금이 없습니다."),
        ("월정기권도 있나요?",
         (f"유료 구간에는 월정기권 요금이 등록되어 있습니다(대표적으로 월 "
          f"{won(next((l['fee']['monthly'] for l in paid if l['fee']['monthly']), None))}). "
          f"신청·대기는 {ui['manager']}에서 받습니다.")
         if any(l["fee"]["monthly"] for l in paid) else
         f"월정기권 요금은 원자료에 등록되어 있지 않습니다. {ui['manager']}에 문의하세요."),
    ]

    body = f"""
<h1>{city['city']} 노상주차장 {len(street)}구간 · 무료 구간과 요금</h1>
<p class="lede">도로변에 설치된 공영 노상(거리) 주차구간입니다. 구간 이름이 {esc(ui['street_examples'] or '위치 설명')}처럼 위치 설명으로
등록되어 있어 카드 대신 도로별 표로 정리했습니다. 무료 {len(free)}곳과 유료 {len(paid)}곳을 구간별로 확인하세요.</p>
<p class="updated">자료 기준일 {esc(ui['std_base_date'])} · {len(street)}구간 {total_spaces:,}면</p>
<div class="stats">
  <div class="stat"><span class="k">노상 구간</span><span class="v">{len(street)}<small>곳</small></span></div>
  <div class="stat free"><span class="k">무료 구간</span><span class="v">{len(free)}<small>곳</small></span></div>
  <div class="stat"><span class="k">총 구획</span><span class="v">{total_spaces:,}<small>면</small></span></div>
</div>
{ad_slot()}

<section class="note-box" style="margin-top:16px">
  <h2>노상주차장 요금·운영시간</h2>
  <ul>{fee_box}
    <li><b>감면</b>: {esc(ui['discount_note'])}</li>
    <li><b>결제</b>: {esc(pay_text)}</li>
  </ul>
</section>

{price_block}

<h2>구별 현황</h2>
<table class="data">
  <thead><tr><th>구</th><th class="num">구간</th><th class="num">구획</th><th class="num">무료</th></tr></thead>
  <tbody>{gu_rows}</tbody>
</table>

<h2>도로별 현황</h2>
<table class="data">
  <thead><tr><th>도로·위치</th><th class="num">구간</th><th class="num">구획</th><th class="num">무료</th></tr></thead>
  <tbody>{road_rows}</tbody>
</table>

<h2>구간별 목록</h2>
{street_rows(street)}
<p class="updated">주차구획은 표준데이터 등록면수입니다. 위치는 도로명·지번주소 기준이며, 구간 이름을 누르면 지도에서 찾을 수 있습니다.</p>
{faq_block(qa)}
"""
    crumbs = [("홈", "/"), ("경기도", None), (city["city"], city_path(city)), ("노상주차장 요금", "")]
    return path, layout(
        title=f"{city['city']} 노상주차장 {len(street)}구간 · 무료 {len(free)}곳·요금 총정리 | {SITE_NAME}",
        description=f"{city['city']} 공영 노상(거리) 주차구간 {len(street)}곳 가운데 무료 {len(free)}곳과 "
                    f"유료 {len(paid)}곳의 요금·구간별 위치를 공공데이터로 정리했습니다." if not any(l["fee"]["daily_fee"] for l in paid) else
                    f"{city['city']} 공영 노상(거리) 주차구간 {len(street)}곳 가운데 무료 {len(free)}곳과 "
                    f"유료 {len(paid)}곳의 요금·1일권·구간별 위치를 공공데이터로 정리했습니다.",
        path=path, body=body, crumbs=crumbs, nav_active="city", city=city,
        jsonld=[jsonld_breadcrumb(crumbs), jsonld_itemlist(street, path), jsonld_faq(qa, path)])


def build_landing(site):
    path = "/"
    cards = []
    for city in site["cities"]:
        lots = city["_card_lots"]
        s = stats_for(lots)
        cards.append(f'''<a class="link-card" href="{city_path(city).lstrip("/")}">
  <span class="t">{city['city']}<span class="go">{s['n']}곳 →</span></span>
  <span class="d">주차요금 계산 · 구별 목록{' · 주말 무료 개방' if city.get('weekend_free_pages') else ' · 노상주차장 요금'}</span>
</a>''')
        for d in city["districts"]:
            dl = [l for l in lots if l["gu"] == d["name"]]
            cards.append(f'''<a class="link-card" href="{district_path(city, d).lstrip("/")}">
  <span class="t">{d['name']}<span class="go">{stats_for(dl)['n']}곳 →</span></span>
  <span class="d">{city['city']} · 주차요금 계산 · 동별 목록</span>
</a>''')
    total = sum(stats_for(c["_card_lots"])["n"] for c in site["cities"])
    total_spaces = sum(stats_for(c["_card_lots"])["spaces"] for c in site["cities"])
    city_names = "·".join(c["city"] for c in site["cities"])
    body = f"""
<h1>공영주차장 파인더 — {city_names}</h1>
<p class="lede">"여기 2시간 주차하면 얼마지?"를 바로 확인하는 페이지입니다.
공공데이터로 등록된 공영주차장 {total}곳(구획 {total_spaces:,}면)의 요금·운영시간·무료 개방 정보를 요일과 시간에 맞춰 계산합니다.</p>
<div class="stats">
  <div class="stat"><span class="k">등록 주차장</span><span class="v">{total}<small>곳</small></span></div>
  <div class="stat"><span class="k">지원 지역</span><span class="v">{len(site['cities'])}<small>개 시</small></span></div>
  <div class="stat"><span class="k">총 구획</span><span class="v">{total_spaces:,}<small>면</small></span></div>
</div>
{ad_slot()}
<h2>지역 선택</h2>
<div class="grid-2">{''.join(cards)}</div>
<h2>이런 걸 확인할 수 있어요</h2>
<div class="note-box">
  <ul>
    <li><b>요일별 무료 개방</b>: 평일·토요일·일요일·공휴일 중 언제 무료인지, 언제 문을 닫는지</li>
    <li><b>내 조건 요금</b>: 30분~24시간 슬라이더로 계산, 1일권 상한 자동 적용</li>
    <li><b>차량 감면</b>: 지자체 조례에 따른 감면 조건(수원·성남·용인·화성시 조례별 버튼, 면제 시간 포함)으로 계산</li>
    <li><b>실시간 잔여면수</b>: 수원도시공사 안내 지도 기준(조회 시점 스냅샷) · 등록 구획수와 스냅샷 총면수가 다른 곳은 차이를 함께 표시</li>
    <li><b>지도 연결</b>: 카카오맵·네이버지도로 바로 이동</li>
  </ul>
</div>
<h2>데이터</h2>
<p class="lede">공공데이터포털 전국주차장정보표준데이터를 기준으로 도시별 자료를 결합했습니다.
요금과 운영시간은 현장과 다를 수 있으니 방문 전에 확인하세요.</p>
<p>{' · '.join(f'<a class="btn" href="{city_path(c).lstrip("/")}">{c["city"]} 전체 주차장 보기</a>' for c in site["cities"])}</p>
"""
    return path, layout(
        title=f"{SITE_NAME} — {city_names} 공영주차장 요금·무료 개방 계산",
        description=f"{city_names} 공영주차장 요금을 요일·시간·감면 조건으로 바로 계산하고, "
                    "주말·공휴일 무료 개방 주차장과 실시간 잔여면수를 확인하세요.",
        path=path, body=body, crumbs=[("홈", "")], nav_active="", city=None, jsonld=[])


# ------------------------------------------------------------------ 404
def build_404(site):
    """없는 주소로 들어왔을 때 보여 줄 404 페이지 (dist/404.html).

    Cloudflare Pages 는 매칭되는 파일이 없으면 dist/404.html 을 그대로 돌려주고
    주소창의 경로는 바꾸지 않는다. 따라서 깊이를 알 수 없어 상대경로(../)를 쓸 수 없고,
    이 페이지 안의 링크·에셋은 모두 사이트 절대경로(/...)로 만든다.
    검색 결과에 남지 않도록 noindex 로 둔다.
    """
    body_parts = []
    for city in site["cities"]:
        lots = city["_card_lots"]
        s = stats_for(lots)
        cards = "".join(
            f'<a class="link-card" href="{district_path(city, d)}">\n'
            f'  <span class="t">{d["name"]}<span class="go">'
            f'{stats_for([l for l in lots if l["gu"] == d["name"]])["n"]}곳 →</span></span>\n'
            f'  <span class="d">주차요금 계산 · 동별 목록</span>\n</a>' for d in city["districts"])
        body_parts.append(f"""
<h2>{esc(city['city'])} 구별로 찾기</h2>
<div class="grid-2">{cards}</div>
<p class="updated">{esc(city['city'])} 공영주차장 {s['n']}곳 · 구획 {s['spaces']:,}면 · <a href="{city_path(city)}">{esc(city['city'])} 전체 보기</a></p>
""")
    body = f"""
<h1>페이지를 찾을 수 없습니다 (404)</h1>
<p class="lede">주소가 바뀌었거나 없는 경로입니다. 아래에서 원하는 주차장을 다시 찾아보세요.</p>
<p>
  <a class="btn solid" href="/">홈으로</a>
  {''.join(f'<a class="btn" href="{city_path(c)}">{esc(c["city"])} 주차장 목록</a>' for c in site["cities"])}
</p>
{''.join(body_parts)}
<h2>이런 걸 확인할 수 있어요</h2>
<div class="note-box">
  <ul>
    <li><b>내 조건 요금</b>: 요일·시간·감면을 고르면 30분~24시간 예상요금을 바로 계산</li>
    <li><b>주말·공휴일 무료 개방</b>: 언제 무료로 열리는지, 언제 문을 닫는지</li>
    <li><b>실시간 잔여면수</b>: 수원도시공사 안내 지도 {esc(SNAPSHOT_TS)} 조회 스냅샷 기준</li>
  </ul>
</div>
"""
    return layout(
        title=f"페이지를 찾을 수 없습니다 (404) | {SITE_NAME}",
        description="요청한 주소의 페이지가 없습니다. 공영주차장 파인더에서 공영주차장 요금과 무료 개방 정보를 확인하세요.",
        path="/404.html", body=body, crumbs=[("홈", "/")], nav_active="", city=None, jsonld=[],
        absolute_links=True, robots="noindex,follow", canonical="")


# ------------------------------------------------------------------ main
def load_site() -> dict:
    """data/site.json 을 읽고, 없으면 수원시 단독 파일을 같은 구조로 감싼다."""
    if DATA_FILE.exists():
        site = json.loads(DATA_FILE.read_text())
    else:
        suwon = json.loads(LEGACY_DATA_FILE.read_text())
        site = {"meta": {"generated_at": suwon["meta"]["generated_at"],
                         "snapshot_at": suwon["meta"].get("snapshot_at")},
                "cities": [suwon], "lots": suwon["lots"]}
    for c in site["cities"]:
        c.setdefault("weekend_free_pages", c["city"] == "수원시")
        c.setdefault("dong_page_min_lots", 1 if c["city"] == "수원시" else DONG_PAGE_MIN_LOTS)
        c.setdefault("discounts", None)
        c.setdefault("sources", [])
    return site


def main():
    global BUILD_TS, SITE_BASE, SNAPSHOT_TS, SITE_CITIES
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=SITE_BASE)
    args = ap.parse_args()
    SITE_BASE = args.base.rstrip("/")

    site = load_site()
    BUILD_TS = site["meta"]["generated_at"]
    SNAPSHOT_TS = site["meta"].get("snapshot_at") or BUILD_TS
    SITE_CITIES = site["cities"]
    for c in site["cities"]:
        city_lots = [l for l in site["lots"] if l.get("city") == c["city"]]
        for l in city_lots:
            l.setdefault("city", c["city"])
        c["_lots"] = city_lots
        c["_card_lots"] = [l for l in city_lots if l.get("list_mode", "card") != STREET_MODE]
        c["_street_lots"] = [l for l in city_lots if l.get("list_mode") == STREET_MODE]
        for l in c["_card_lots"]:
            if not l.get("dong"):
                l["dong"] = UNKNOWN_DONG

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "assets").mkdir(parents=True)
    for f in ("style.css", "app.js"):
        shutil.copy(ASSETS / f, DIST / "assets" / f)

    pages = [build_landing(site)]
    for city in site["cities"]:
        card_lots = city["_card_lots"]
        pages.append(build_city(city, card_lots, site))
        for d in city["districts"]:
            d_lots = [l for l in card_lots if l["gu"] == d["name"]]
            if not d_lots:
                continue
            pages.append(build_district(city, d, d_lots, site))
            if city.get("weekend_free_pages"):
                pages.append(build_weekend(city, d, d_lots, site))
            by_dong = {}
            for l in d_lots:
                by_dong.setdefault(l["dong"], []).append(l)
            slugs = dong_slug_map(by_dong)
            for dong, dl in sorted(by_dong.items()):
                if dong == UNKNOWN_DONG:
                    continue        # 주소·좌표로 확인되지 않은 묶음은 페이지를 만들지 않는다
                if len(dl) < city.get("dong_page_min_lots", DONG_PAGE_MIN_LOTS):
                    continue        # 빈 페이지·껍데기 페이지 방지
                pages.append(build_dong(city, d, dong, dl, site, slug_override=slugs[dong]))
        if city["_street_lots"]:
            pages.append(build_street(city, city["_street_lots"], site))

    for path, html_text in pages:
        out = DIST / path.strip("/") / "index.html" if path != "/" else DIST / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")

    # 없는 주소용 404 (사이트맵에는 넣지 않는다)
    (DIST / "404.html").write_text(build_404(site), encoding="utf-8")

    urls = "\n".join(
        f"  <url><loc>{SITE_BASE}{p}</loc><changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if p == '/' else ('0.9' if p.count('/') <= 4 else '0.7')}</priority></url>"
        for p, _ in pages)
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n')
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE}/sitemap.xml\n")

    print(f"생성 완료: {len(pages)}페이지 + 404.html · dist/")
    for p, _ in pages:
        print("  ", p)


if __name__ == "__main__":
    main()
