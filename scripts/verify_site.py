#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
로컬 검증: dist/ 를 http.server 로 띄우고 headless Chromium(Playwright)으로
계산기 동작과 모바일/데스크톱 레이아웃을 확인하고 스크린샷을 남긴다.

결과: screenshots/*.png , scripts/verify_result.json (스크린샷 폴더는 PARKING_SHOTS_DIR 로 변경 가능)
"""
import json
import os
import threading
import functools
import http.server
import socketserver
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / "dist"
OUT = Path(os.environ.get("PARKING_SHOTS_DIR", BASE / "screenshots"))
PORT = 8791

OUT.mkdir(parents=True, exist_ok=True)
results = {"checks": [], "screenshots": [], "console_errors": []}


def check(name, ok, detail=""):
    results["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(("PASS " if ok else "FAIL ") + name + (" · " + str(detail) if detail else ""))


handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{PORT}"

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                              locale="ko-KR", is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.on("console", lambda m: results["console_errors"].append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: results["console_errors"].append(str(e)))

    # ---------------- 영통구 페이지 (모바일)
    page.goto(base + "/parking/gyeonggi/suwon-yeongtong/", wait_until="load")
    page.wait_for_function("document.getElementById('calc-summary') && "
                           "!document.getElementById('calc-summary').textContent.includes('계산 중')")
    check("영통구 페이지 로드", page.title().startswith("영통구"), page.title())
    check("h1 노출", "영통구 공영주차장" in page.inner_text("h1"), page.inner_text("h1"))

    first = page.inner_text("#lot-list .lot:first-child")
    check("목록 첫 카드 렌더", "영통구청" in first or "공영" in first, first.split("\n")[0])
    summary_weekday = page.inner_text("#calc-summary")
    check("계산 요약(평일 2시간)", "평일" in summary_weekday and "2시간" in summary_weekday, summary_weekday)

    # 2시간 평일 가격 (영통구청: 기본 30분 600원 + 10분 300원 -> 600 + ceil(90/10)*300 = 3300)
    price_2h = page.eval_on_selector(
        "#lot-list .lot[data-lot='std-3740000000'] .price", "el => el.textContent") \
        if page.query_selector("#lot-list .lot[data-lot='std-3740000000']") else None

    # -- 슬라이더 60분으로
    page.eval_on_selector("#time-slider", """el => { el.value = 60;
        el.dispatchEvent(new Event('input', {bubbles: true})); }""")
    page.wait_for_timeout(150)
    s60 = page.inner_text("#calc-summary")
    check("슬라이더 1시간 반영", "1시간" in s60, s60)

    # -- 경차 50% 감면
    before = [t.strip() for t in page.eval_on_selector_all("#lot-list .lot .price", "els => els.map(e=>e.textContent)")]
    page.click("#discount-group button[data-rate='0.5']")
    page.wait_for_timeout(150)
    after = [t.strip() for t in page.eval_on_selector_all("#lot-list .lot .price", "els => els.map(e=>e.textContent)")]
    check("감면 50% 선택 시 가격 변화", before != after, f"{before[:3]} → {after[:3]}")
    check("감면 버튼 pressed 상태", page.get_attribute("#discount-group button[data-rate='0.5']", "aria-pressed") == "true")

    # -- 일요일·공휴일 선택 → 무료 개방 최상단
    page.click("#day-group button[data-day='sun']")
    page.wait_for_timeout(200)
    top_card = page.inner_text("#lot-list .lot:first-child")
    top_name = top_card.split("\n")[0]
    top_price = page.inner_text("#lot-list .lot:first-child .price")
    check("일요일 선택 시 무료 개방 최상단", top_price == "0원" and "영통구청" in top_card,
          f"{top_name} / {top_price}")
    check("무료 배지 노출", page.is_visible("#lot-list .lot:first-child")
          and page.eval_on_selector("#lot-list .lot:first-child .badge.free", "el=>el.offsetParent!==null"))
    s_sun = page.inner_text("#calc-summary")
    check("일요일 요약 갱신", "일요일" in s_sun, s_sun)

    # 광고 슬롯 위치 (5번째·6번째 사이)
    order = page.eval_on_selector_all("#lot-list > *", "els => els.map(e => e.classList.contains('lot') ? 'lot' : 'ad')")
    check("광고 슬롯이 5번째 카드 뒤", order[:7] == ["lot"] * 5 + ["ad", "lot"], order[:8])

    # 가로 스크롤(레이아웃 깨짐) 확인
    overflow = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("모바일 가로 스크롤 없음", overflow <= 1, f"overflow={overflow}px")

    page.evaluate("window.scrollTo(0,0)")
    page.wait_for_timeout(150)
    page.screenshot(path=str(OUT / "01-mobile-yeongtong-top.png"))
    results["screenshots"].append("01-mobile-yeongtong-top.png")

    page.evaluate("window.scrollTo(0, 780)")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "02-mobile-yeongtong-list.png"))
    results["screenshots"].append("02-mobile-yeongtong-list.png")

    page.screenshot(path=str(OUT / "03-mobile-yeongtong-full.png"), full_page=True)
    results["screenshots"].append("03-mobile-yeongtong-full.png")

    # ---------------- 주말 무료 페이지
    page.goto(base + "/parking/gyeonggi/suwon-yeongtong/weekend-free/", wait_until="load")
    page.wait_for_timeout(300)
    body = page.inner_text("body")
    check("주말무료 페이지: 영통구청 포함", "영통구청" in body)
    check("주말무료 페이지: 무료 0원 표시", "0원" in body)
    page.screenshot(path=str(OUT / "04-mobile-weekend-free.png"))
    results["screenshots"].append("04-mobile-weekend-free.png")

    # ---------------- 시 허브
    page.goto(base + "/parking/gyeonggi/suwon/", wait_until="load")
    page.wait_for_timeout(200)
    check("시 허브: 구별 표", "구별 현황" in page.inner_text("body"))
    page.screenshot(path=str(OUT / "05-mobile-suwon-hub.png"))
    results["screenshots"].append("05-mobile-suwon-hub.png")

    # ---------------- 랜딩
    page.goto(base + "/", wait_until="load")
    page.wait_for_timeout(200)
    page.screenshot(path=str(OUT / "06-mobile-landing.png"))
    results["screenshots"].append("06-mobile-landing.png")

    # ---------------- 동 상세
    page.goto(base + "/parking/gyeonggi/suwon-yeongtong/maetan-dong/", wait_until="load")
    page.wait_for_timeout(200)
    check("동 상세 페이지", "매탄동 공영주차장" in page.inner_text("h1"), page.inner_text("h1"))
    page.screenshot(path=str(OUT / "07-mobile-maetan-dong.png"))
    results["screenshots"].append("07-mobile-maetan-dong.png")

    # ---------------- file:// 로 열어도 스타일·계산기가 동작하는지 (폰/PC에서 파일로 열 때)
    page.goto("file://" + str(DIST / "parking" / "gyeonggi" / "suwon-yeongtong" / "index.html"),
              wait_until="load")
    page.wait_for_timeout(400)
    bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
    check("file:// 에서 CSS 적용", bg not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)") or
          page.evaluate("getComputedStyle(document.querySelector('.calc')).borderRadius") != "0px", bg)
    check("file:// 에서 계산기 동작",
          "기준" in page.inner_text("#calc-summary"), page.inner_text("#calc-summary"))
    ctx.close()

    # ---------------- 데스크톱
    ctx2 = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
    page2 = ctx2.new_page()
    page2.on("pageerror", lambda e: results["console_errors"].append(str(e)))
    page2.goto(base + "/parking/gyeonggi/suwon-yeongtong/", wait_until="load")
    page2.wait_for_timeout(400)
    page2.screenshot(path=str(OUT / "08-desktop-yeongtong.png"))
    results["screenshots"].append("08-desktop-yeongtong.png")
    page2.evaluate("window.scrollTo(0, 700)")
    page2.wait_for_timeout(300)
    page2.screenshot(path=str(OUT / "09-desktop-yeongtong-list.png"))
    results["screenshots"].append("09-desktop-yeongtong-list.png")
    ov2 = page2.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check("데스크톱 가로 스크롤 없음", ov2 <= 1, f"overflow={ov2}px")
    ctx2.close()
    browser.close()

httpd.shutdown()

check("콘솔 오류 없음", not results["console_errors"], results["console_errors"][:3])
(BASE / "scripts" / "verify_result.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
fails = [c for c in results["checks"] if not c["ok"]]
print(f"\n{len(results['checks']) - len(fails)}/{len(results['checks'])} 통과")
sys.exit(1 if fails else 0)
