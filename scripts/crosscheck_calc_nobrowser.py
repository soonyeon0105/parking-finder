#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""브라우저 없이 JS 계산 함수(app.js 의 priceFor)와 Python 규칙을 전수 비교한다.

crosscheck_calc.py 는 headless Chromium 의 DOM .price 텍스트를 읽는다. Chromium 을 설치할 수
없는 환경(플레이그라운드 다운로드 차단)에서는 이 스크립트로 같은 JS 함수를 JS 엔진(quickjs)에서
직접 호출해 동일한 조합을 대조한다.

  · 대상: site.json 의 카드 목록에 그리는 모든 주차장(수원 72 + 성남 98 + 용인 159 + 화성 78 + 안양 78 + 평택 75)
  · 조합: 요일 3 × 감면 버튼(도시별) × 시간 5
  · 추가: 서버가 그린 카드 가격(기본 상태)과 JS 계산도 대조

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
m = re.search(r"function priceFor\(lot, minutes, day, rate, exempt\) \{.*?\n  \}", app, re.S)
assert m, "priceFor 추출 실패"
ctx = quickjs.Context()
ctx.eval(m.group(0) + "\nthis.priceFor = priceFor;")

DAYS = ["weekday", "sat", "sun"]
MINUTES = [30, 60, 120, 240, 1440]


def js_price(lot, minutes, day, rate, exempt=0):
    payload = {"oper": lot["oper"], "free_days": lot["free_days"],
               "fee": {k: lot["fee"].get(k) for k in ("type", "base_min", "base_fee", "unit_min",
                                                      "unit_fee", "daily_hours", "daily_fee",
                                                      "steps", "bands", "free_min", "cap_fee", "deduct_min")}}
    ctx.eval(f"var LOT = {json.dumps(payload, ensure_ascii=False)};")
    r = ctx.eval(f"JSON.stringify(priceFor(LOT, {minutes}, {json.dumps(day)}, {rate}, {exempt}))")
    return json.loads(r)


def discounts_of(city):
    if city.get("discounts"):
        return [(d["rate"], d.get("exempt_min") or 0) for d in city["discounts"]]
    return [(0.0, 0), (0.5, 0), (0.8, 0)]


mismatch, total = [], 0
for city in DATA["cities"]:
    lots = [l for l in DATA["lots"]
            if l.get("city") == city["city"] and l.get("list_mode", "card") != "street"]
    for rate, exempt in discounts_of(city):
        for day in DAYS:
            for minutes in MINUTES:
                for lot in lots:
                    total += 1
                    a, b = price_for(lot, minutes, day, rate, exempt), js_price(lot, minutes, day, rate, exempt)
                    if a.get("state") != b.get("state") or a.get("amount") != b.get("amount") \
                            or bool(a.get("capped")) != bool(b.get("capped")) \
                            or bool(a.get("deducted")) != bool(b.get("deducted")) \
                            or bool(a.get("exempt")) != bool(b.get("exempt")):
                        mismatch.append((city["city"], lot["name"], day, rate, exempt, minutes, a, b))

# 서버가 그린 카드(기본 상태: 감면 없음)와 JS 계산도 대조
html_pages = cards_checked = 0
for pg in sorted((BASE / "dist").rglob("index.html")):
    html = pg.read_text()
    if 'id="lot-data"' not in html:
        continue
    html_pages += 1
    dm = re.search(r'id="lot-list" data-day="(\w+)" data-minutes="(\d+)"', html)
    day, minutes = (dm.group(1), int(dm.group(2))) if dm else ("weekday", 120)
    by_id = {l["id"]: l for l in DATA["lots"]}
    for lot_id, price in re.findall(r'data-lot="([^"]+)"[\s\S]*?<span class="price [a-z]+">([^<]+)</span>', html):
        lot = by_id.get(lot_id)
        if not lot:
            continue
        cards_checked += 1
        r = js_price(lot, minutes, day, 0)
        want = ("0원" if r["state"] == "free" else
                f"{r['amount']:,}원" if r["state"] == "paid" else
                "요금 정보 미상" if r["state"] == "unknown" else "휴무")
        if price.strip() != want:
            mismatch.append((str(pg.relative_to(BASE / "dist")), lot["name"], "static", price, want))

# 노상 페이지의 계산 표도 확인(카드가 아닌 구간이므로 price_for 로만 확인).
# 무료 구간은 감면 계산 대상이 아니므로 유료 구간만 본다.
street = [l for l in DATA["lots"] if l.get("list_mode") == "street"]
street_free = [l for l in street if l["fee"]["type"] == "무료"]
street_paid = [l for l in street if l["fee"]["type"] == "유료"]
street_bad = [l["name"] for l in street_paid
              if price_for(l, 120, "weekday", 0.5)["state"] != "paid"]
street_free_bad = [l["name"] for l in street_free
                   if price_for(l, 120, "weekday", 0.5)["state"] != "free"]

print(f"JS↔Python 비교 {total:,}건 · 서버카드 대조 {html_pages}페이지/{cards_checked:,}장 · "
      f"노상 구간 {len(street)}곳(무료 {len(street_free)}·유료 {len(street_paid)}) · "
      f"불일치 {len(mismatch) + len(street_bad) + len(street_free_bad)}건")
for x in mismatch[:10]:
    print("  ", x)
for x in street_bad[:5]:
    print("  노상 계산 불가:", x)
for x in street_free_bad[:5]:
    print("  노상 무료 계산 오류:", x)
sys.exit(1 if (mismatch or street_bad or street_free_bad) else 0)
