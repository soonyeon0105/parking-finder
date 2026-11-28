#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전기차 충전소 '상태 전용' 소형 데이터 생성 — 상태 JSON 분리 방식 (2026-11-28).

배경: 상태(충전 가능/충전 중/점검·운영중지/미확인 대수와 확인 시각)는 시간마다
바뀌는데, 예전에는 refresh_ev_status.py 가 build_ev.py 전체를 다시 돌려 정적
HTML·상세 JSON(57MB)·nearby 인덱스까지 전부 재생성했고, 그걸 git 으로 올리면
1회에 약 38.6MB 씩 저장소가 불어났다. 게다가 시간당 push 는 Pages 무료
플랜의 월 빌드 500회(시간당이면 월 약 720회)를 넘긴다.

그래서 상태를 정적 산출물·git 에서 완전히 분리한다:

  · 상태 본문은 이 모듈이 만들고, publish_ev_status.py 가 Cloudflare D1
    (parking-ev-status)의 files 표에 갈아끼운다. 시간당 쓰기는 행 수백 개
    수준이라 D1 무료 한도(일 쓰기 100,000건) 안에 충분히 든다. KV는 이
    계정 토큰에 권한이 없고 무료 쓰기 한도(일 1,000건)도 모자라 쓰지 않는다.
  · 응답은 Worker(parking-ev-status)가 D1에서 읽어 내보낸다 — Pages 배포는
    일어나지 않는다.
      GET {STATUS_BASE_URL}/ev-status-summary.json        → key 'summary'
      GET {STATUS_BASE_URL}/ev-status/{pslug}-{slug}.json → key '{pslug}-{slug}'
  · 지역 상태 본문: 충전소 id → [충전 가능, 충전 중, 점검·운영중지,
    상태 미확인, 확인 시각 인덱스]. 확인 시각 문자열은 본문 머리 "cfs"
    배열에 한 번만 싣고 충전소는 인덱스로 가리킨다.
  · 요약 본문: 지역별 [지금 충전 가능 있는 곳 수, 충전 가능 대수 합계] —
    시·도 페이지의 집계 표가 이 값만 읽어 화면에서 갈아끼운다.

읽는 쪽:
  · 지역 목록 페이지 — assets/ev-status.js 가 지역 본문을 읽어 카드의
    배지·요금 줄·첫 페이지 집계를 갈아끼운다(정적 HTML에는 빌드 시점 값이
    그대로 들어 있어 JS가 없거나 Worker가 죽어도 표시는 된다).
  · 충전소 상세 페이지 — Pages Function 이 상세 JSON 값 위에 상태 값을
    덮어써서 내보낸다.
  · 내 주변 페이지 — assets/ev-nearby.js 가 보여 줄 충전소가 속한 지역
    본문만 골라 읽어 행의 충전 가능 대수·확인 시각을 갈아끼운다.

표기는 종전대로 확인 시각('cf') 기준이며 '실시간'이라 쓰지 않는다.
"""
from __future__ import annotations

import json

# 상태 응답 Worker 주소 — assets/ev-status.js·assets/ev-nearby.js·
# functions/ev/[pslug]/[slug]/[id].js 도 같은 주소를 쓴다. 바꾸면 전부 함께.
STATUS_BASE_URL = "https://parking-ev-status.tearsstream3.workers.dev"


def status_at(ev: dict) -> str:
    """본문 머리에 실을 기준 시각 — 상태 확인이 가장 최근에 이뤄진 시각."""
    meta = ev.get("meta") or {}
    at = meta.get("cf_at") or ""
    if not at:
        at = (meta.get("st_collected") or "")[:16].replace("T", " ")
    return at


def region_key(region: dict) -> str:
    return f"{region['pslug']}-{region['slug']}"


def region_text(region: dict, at: str) -> str:
    """지역 상태 본문 — 충전소 한 곳을 한 줄로 쓴다(행 단위 비교·전송에 유리)."""
    cfs: list[str] = []
    cf_idx: dict[str, int] = {}
    lines = []
    for s in region["stations"]:
        cf = s.get("cf") or ""
        if cf not in cf_idx:
            cf_idx[cf] = len(cfs)
            cfs.append(cf)
        rec = json.dumps([s["a"], s["c"], s["dn"], s["un"], cf_idx[cf]],
                         separators=(",", ":"))
        lines.append(f"{json.dumps(s['id'])}:{rec}")
    head = json.dumps({"v": 1, "at": at, "cfs": cfs},
                      ensure_ascii=False, separators=(",", ":"))
    return head[:-1] + ',"st":{\n' + ",\n".join(lines) + "\n}}\n"


def summary_text(ev: dict, at: str) -> str:
    """지역별 집계 — [지금 충전 가능 있는 곳 수, 충전 가능 대수 합계]."""
    regions = {}
    for r in ev["regions"]:
        na = sum(1 for s in r["stations"] if s["a"])
        regions[region_key(r)] = [na, sum(s["a"] for s in r["stations"])]
    return json.dumps({"v": 1, "at": at, "r": regions},
                      ensure_ascii=False, separators=(",", ":")) + "\n"


def build_payloads(ev: dict) -> dict:
    """D1 files 표에 실을 {key: 본문} 전체. key는 'summary'와 지역 키."""
    at = status_at(ev)
    payloads = {"summary": summary_text(ev, at)}
    for r in ev["regions"]:
        payloads[region_key(r)] = region_text(r, at)
    return payloads
