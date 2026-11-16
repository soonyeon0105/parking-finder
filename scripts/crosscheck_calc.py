#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""화면(JS) 계산 결과와 서버(Python) 계산 규칙을 전수 교차검증한다(Chromium 필요).

브라우저가 없는 환경에서는 scripts/crosscheck_calc_nobrowser.py 를 쓴다(quickjs 로 같은 JS 함수 호출).
"""
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "dist"
sys.path.insert(0, str(BASE / "scripts"))
from build_site import price_for, district_path  # noqa: E402

DATA = json.loads((BASE / "data" / "site.json").read_text())
by_id = {l["id"]: l for l in DATA["lots"]}

PORT = 8797
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", PORT),
                               functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()

DAYS = ["weekday", "sat", "sun"]
MINUTES = [30, 60, 120, 240, 1440]
mismatch, total = [], 0


def discounts_of(city):
    if city.get("discounts"):
        return [(d["rate"], d.get("exempt_min") or 0) for d in city["discounts"]]
    return [(0.0, 0), (0.5, 0), (0.8, 0)]


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844}, locale="ko-KR")
    for city in DATA["cities"]:
        for d in city["districts"]:
            dist_lots = [l for l in DATA["lots"] if l.get("city") == city["city"]
                         and l["gu"] == d["name"] and l.get("list_mode", "card") != "street"]
            if not dist_lots:
                continue
            path = district_path(city, d).lstrip("/")
            pg.goto(f"http://127.0.0.1:{PORT}/{path}", wait_until="load")
            pg.wait_for_timeout(300)
            for day in DAYS:
                pg.click(f"#day-group button[data-day='{day}']")
                for rate, exempt in discounts_of(city):
                    pg.click(f"#discount-group button[data-rate='{rate}'][data-exempt='{exempt}']")
                    for minutes in MINUTES:
                        pg.eval_on_selector("#time-slider",
                                            "(el, v) => { el.value = v; el.dispatchEvent(new Event('input',{bubbles:true})); }",
                                            minutes)
                        pg.wait_for_timeout(30)
                        got = pg.eval_on_selector_all(
                            "#lot-list .lot",
                            "els => els.map(e => ({id: e.dataset.lot, price: e.querySelector('.price').textContent.trim(),"
                            " cls: e.querySelector('.price').className}))")
                        for g in got:
                            total += 1
                            lot = by_id[g["id"]]
                            want = price_for(lot, minutes, day, rate, exempt)
                            if want["state"] == "paid":
                                exp = f"{want['amount']:,}원"
                            elif want["state"] == "free":
                                exp = "0원"
                            elif want["state"] == "unknown":
                                exp = "요금 정보 미상"
                            else:
                                exp = "휴무"
                            if g["price"] != exp:
                                mismatch.append((city["city"], d["name"], lot["name"], day, rate, exempt,
                                                 minutes, g["price"], exp))
    b.close()
httpd.shutdown()

print(f"교차검증 {total:,}건 / 불일치 {len(mismatch)}건")
for m in mismatch[:15]:
    print("  ", m)
sys.exit(1 if mismatch else 0)
