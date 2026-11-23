#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""브라우저 없이 JS 계산 함수(app.js 의 priceFor)와 Python 규칙을 전수 비교한다.

crosscheck_calc.py 는 headless Chromium 의 DOM .price 텍스트를 읽는다. Chromium 을 설치할 수
없는 환경(플레이그라운드 다운로드 차단)에서는 이 스크립트로 같은 JS 함수를 JS 엔진(quickjs)에서
직접 호출해 동일한 조합을 대조한다.

  · 대상: site.json 의 카드 목록에 그리는 모든 주차장
  · A상(기본): 요일 3 × 감면 버튼(도시별) × 시간 5 — 입차 시각 없음(예전 경로)
  · B상(입차): 입차 시각이 가격을 바꾸는 곳(유료 + 24시간 미만 운영 또는 무료 시간대)
    × 입차 시각 3(새벽·정오·심야) × 요일 3 × 시간 1 — Python/JS 일치 확인
  · 추가: 서버가 그린 카드 가격(기본 상태: 12:00 입차)과 JS 계산도 대조

사용법:  python3 scripts/crosscheck_calc_nobrowser.py
"""
import json
import re
import sys
from pathlib import Path

import quickjs

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
from build_site import price_for  # noqa: E402

DATA = json.loads((BASE / "data" / "site.json").read_text())
app = (BASE / "assets" / "app.js").read_text()


def extract_fn(src, name):
    """이름이 name인 최상위 function을 중괄호 짝을 세어 통째로 뽑는다."""
    m = re.search(r"function " + re.escape(name) + r"\(", src)
    assert m, f"{name} 추출 실패"
    i = src.index("{", m.start())
    depth, j = 0, i
    while j < len(src):
        ch = src[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():j + 1]
        j += 1
    raise AssertionError(f"{name} 닫는 중괄호를 찾지 못함")


ctx = quickjs.Context()
for _fn in ("overlapMinutes", "freeWindowOverlap", "chargeableMinutes", "priceFor"):
    ctx.eval(extract_fn(app, _fn))
ctx.eval("this.priceFor = priceFor;")

DAYS = ["weekday", "sat", "sun"]
MINUTES = [30, 60, 120, 240, 1440]
ENTRIES = [180, 720, 1320]  # 새벽 03:00 · 정오 12:00(기본값) · 심야 22:00


def js_price(lot, minutes, day, rate, exempt=0, entry=None):
    payload = {"oper": lot["oper"], "free_days": lot["free_days"],
               "ptype": lot.get("ptype"),
               "bus_only": bool(lot.get("bus_only")),
               "free_window": lot.get("free_window_min"),
               "hours": {k: {"open": lot["hours"][k]["open"], "start": lot["hours"][k]["start"],
                             "end": lot["hours"][k]["end"], "24h": lot["hours"][k]["24h"]}
                         for k in ("weekday", "sat", "sun")},
               "fee": {k: lot["fee"].get(k) for k in ("type", "base_min", "base_fee", "unit_min",
                                                      "unit_fee", "daily_hours", "daily_fee",
                                                      "steps", "bands", "free_min", "cap_fee", "deduct_min",
                                                      "flat_day")}}
    ctx.eval(f"var LOT = {json.dumps(payload, ensure_ascii=False)};")
    entry_js = "null" if entry is None else str(entry)
    r = ctx.eval(f"JSON.stringify(priceFor(LOT, {minutes}, {json.dumps(day)}, {rate}, {exempt}, {entry_js}))")
    return json.loads(r)


def discounts_of(city):
    if city.get("discounts"):
        return [(d["rate"], d.get("exempt_min") or 0) for d in city["discounts"]]
    return [(0.0, 0), (0.5, 0), (0.8, 0)]


def same(a, b):
    return (a.get("state") == b.get("state") and a.get("amount") == b.get("amount")
            and bool(a.get("capped")) == bool(b.get("capped"))
            and bool(a.get("deducted")) == bool(b.get("deducted"))
            and bool(a.get("exempt")) == bool(b.get("exempt"))
            and bool(a.get("free_window")) == bool(b.get("free_window"))
            and bool(a.get("outside_hours")) == bool(b.get("outside_hours")))


mismatch, total = [], 0
# A상 — 입차 시각 없는 예전 경로 전수
for city in DATA["cities"]:
    lots = [l for l in DATA["lots"]
            if l.get("city") == city["city"] and l.get("list_mode", "card") != "street"]
    for rate, exempt in discounts_of(city):
        for day in DAYS:
            for minutes in MINUTES:
                for lot in lots:
                    total += 1
                    a, b = price_for(lot, minutes, day, rate, exempt), js_price(lot, minutes, day, rate, exempt)
                    if not same(a, b):
                        mismatch.append((city["city"], lot["name"], day, rate, exempt, minutes, None, a, b))

# B상 — 입차 시각이 가격을 바꾸는 곳만
affected = []
for lot in DATA["lots"]:
    if lot.get("list_mode") == "street" or lot["fee"]["type"] != "유료":
        continue
    short_hours = any(not lot["hours"][d].get("24h") for d in DAYS)
    if short_hours or lot.get("free_window_min") or lot["fee"].get("flat_day"):
        affected.append(lot)
for lot in affected:
    for entry in ENTRIES:
        for day in DAYS:
            for rate, exempt in ((0.0, 0), (0.5, 0)):
                total += 1
                a, b = price_for(lot, 120, day, rate, exempt, entry), js_price(lot, 120, day, rate, exempt, entry)
                if not same(a, b):
                    mismatch.append((lot["city"], lot["name"], day, rate, exempt, 120, entry, a, b))

# 서버가 그린 카드(기본 상태: 12:00 입차, 감면 없음)와 JS 계산도 대조
html_pages = cards_checked = 0
for pg in sorted((BASE / "dist").rglob("index.html")):
    html = pg.read_text()
    if 'id="lot-data"' not in html:
        continue
    html_pages += 1
    dm = re.search(r'id="lot-list" data-day="(\w+)" data-minutes="(\d+)"(?: data-entry="(\d+)")?', html)
    day, minutes = (dm.group(1), int(dm.group(2))) if dm else ("weekday", 120)
    entry = int(dm.group(3)) if dm and dm.group(3) else 720
    by_id = {l["id"]: l for l in DATA["lots"]}
    for lot_id, price in re.findall(r'data-lot="([^"]+)"[\s\S]*?<span class="price [\w-]+">([^<]+)</span>', html):
        lot = by_id.get(lot_id)
        if not lot:
            continue
        cards_checked += 1
        r = js_price(lot, minutes, day, 0, entry=entry)
        want = ("0원" if r["state"] == "free" else
                f"{r['amount']:,}원" if r["state"] == "paid" else
                "요금 정보 미상" if r["state"] == "unknown" else
                "관광버스 전용" if r["state"] == "bus_only" else "휴무")
        if price.strip() != want:
            mismatch.append((str(pg.relative_to(BASE / "dist")), lot["name"], "static", price, want))

# 노상 페이지의 계산 표도 확인(카드가 아닌 구간이므로 price_for 로만 확인).
# 무료 구간은 감면 계산 대상이 아니므로 유료 구간만 본다.
street = [l for l in DATA["lots"] if l.get("list_mode") == "street"]
street_free = [l for l in street if l["fee"]["type"] == "무료"]
street_paid = [l for l in street if l["fee"]["type"] == "유료"]
# 평일에는 요금을 받지 않는 구간(과천시 북문노상주차장 — 평일 무료 개방·토요일·공휴일만 유료)은
#   평일 계산이 ‘휴무’로 나오는 것이 맞으므로 대조에서 뺀다.
# 최초 무료시간이 대조 시간(120분) 이상인 구간(가평군 가평읍 10구간 — 최초 2시간 무료)은
#   120분 계산이 ‘무료’로 나오는 것이 맞으므로 뺀다(데이터 오류 아님 — 검사 전제).
# 월정기 전용 노상(노원 은빛1-2단지 — 거주민 월 정기권 전용)은 시간제 요금이 없어
#   120분 계산이 ‘요금 정보 미상’으로 나오는 것이 맞으므로 뺀다(2026-11-23, 1차 출처 확인).
street_paid_wk = [l for l in street_paid if l["oper"].get("weekday")
                  and (l["fee"].get("free_min") or 0) < 120
                  and not l["fee"].get("monthly_only")]
street_bad = [l["name"] for l in street_paid_wk
              if price_for(l, 120, "weekday", 0.5)["state"] != "paid"]
street_free_bad = [l["name"] for l in street_free
                   if price_for(l, 120, "weekday", 0.5)["state"] != "free"]

print(f"JS↔Python 비교 {total:,}건(입차 대상 {len(affected):,}곳) · 서버카드 대조 {html_pages}페이지/{cards_checked:,}장 · "
      f"노상 구간 {len(street)}곳(무료 {len(street_free)}·유료 {len(street_paid)}) · "
      f"불일치 {len(mismatch) + len(street_bad) + len(street_free_bad)}건")
for x in mismatch[:10]:
    print("  ", x)
for x in street_bad[:5]:
    print("  노상 계산 불가:", x)
for x in street_free_bad[:5]:
    print("  노상 무료 계산 오류:", x)
sys.exit(1 if (mismatch or street_bad or street_free_bad) else 0)
