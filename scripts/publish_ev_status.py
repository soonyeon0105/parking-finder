#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EV 상태 본문을 Cloudflare D1(parking-ev-status)에 발행한다.

시간당 파이프라인의 마지막 단계 — refresh_ev_status.py --publish 가 부르고,
단독 실행하면 data/ev_stations.json 기준으로 본문을 만들어 발행한다.

  python3 scripts/publish_ev_status.py [--dry-run]

동작:
  · D1 files 표의 (path, hash)를 먼저 읽어, 본문 해시가 같은 항목은 건드리지
    않는다. 바뀐 항목만 INSERT OR REPLACE 로 갈아끼우고, 데이터에서 사라진
    지역은 표에서도 지운다.
  · 인증은 custom.cloudflare 커넥터와 같은 방식(dynamic_credentials 서로게이트)
    을 쓴다 — 토큰을 파일·명령행·로그에 남기지 않는다.
  · D1 쓰기는 시간당 수백 행 수준이라 무료 한도(일 100,000건)에 여유가 있다.
    Pages 배포·git 커밋은 일어나지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")

import ev_status  # noqa: E402

ACCOUNT_ID = "a6180480a03c05ea647b8b6b0356e21f"
DB_ID = "081acb52-91a7-46a8-9ba9-c553c80e1214"  # parking-ev-status (비밀 아님)
API = "https://api.cloudflare.com/client/v4"
KST = ZoneInfo("Asia/Seoul")
BATCH_MAX_ROWS = 10          # 한 번의 쿼리에 실을 행 수 (본문 합계도 함께 제한)
BATCH_MAX_BYTES = 200_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise RuntimeError("redirect refused, verify the endpoint")


def _query(sql: str, params: list | None = None) -> list:
    from dynamic_credentials import add_surrogate_to_request, read_json_response
    payload: dict = {"sql": sql}
    if params is not None:
        payload["params"] = params
    req = urllib.request.Request(
        f"{API}/accounts/{ACCOUNT_ID}/d1/database/{DB_ID}/query",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    add_surrogate_to_request(req, "custom.cloudflare",
                             allowed_hosts=["api.cloudflare.com"])
    try:
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=60) as r:
            data = read_json_response(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"D1 쿼리 실패 HTTP {e.code}: {e.read().decode()[:300]}")
    if not data.get("success"):
        raise SystemExit(f"D1 쿼리 실패: {data.get('errors')}")
    return data["result"][0].get("results", [])


def publish(payloads: dict, dry_run: bool = False) -> dict:
    """{key: 본문}을 D1에 반영한다. 반환: {changed, unchanged, deleted, bytes}."""
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    hashes = {k: hashlib.sha256(v.encode("utf-8")).hexdigest()
              for k, v in payloads.items()}
    existing = {row["path"]: row["hash"]
                for row in _query("SELECT path, hash FROM files")}
    changed = [k for k in payloads if existing.get(k) != hashes[k]]
    # files 표는 공용 창구다 — 항공권 키('flights-' 접두사)는 kmedicheck 쪽
    # 발행 스크립트 소유라, EV 발행이 지우면 안 된다 (2026-11-28 항공권 편입).
    deleted = [k for k in existing
               if k not in payloads and not k.startswith("flights-")]
    total_bytes = sum(len(payloads[k].encode("utf-8")) for k in changed)
    if dry_run:
        return {"changed": len(changed), "unchanged": len(payloads) - len(changed),
                "deleted": len(deleted), "bytes": total_bytes}
    batch: list[str] = []
    batch_params: list = []
    batch_bytes = 0

    def flush():
        nonlocal batch, batch_params, batch_bytes
        if not batch:
            return
        sql = ("INSERT OR REPLACE INTO files (path, body, hash, updated_at) VALUES "
               + ", ".join(batch))
        _query(sql, batch_params)
        batch, batch_params, batch_bytes = [], [], 0

    for k in changed:
        body = payloads[k]
        batch.append("(?, ?, ?, ?)")
        batch_params += [k, body, hashes[k], now]
        batch_bytes += len(body.encode("utf-8"))
        if len(batch) >= BATCH_MAX_ROWS or batch_bytes >= BATCH_MAX_BYTES:
            flush()
    flush()
    for k in deleted:
        _query("DELETE FROM files WHERE path = ?", [k])
    return {"changed": len(changed), "unchanged": len(payloads) - len(changed),
            "deleted": len(deleted), "bytes": total_bytes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 바뀔 항목만 센다")
    args = ap.parse_args()
    ev = json.loads((BASE / "data" / "ev_stations.json").read_text(encoding="utf-8"))
    payloads = ev_status.build_payloads(ev)
    stats = publish(payloads, dry_run=args.dry_run)
    total = sum(len(v.encode("utf-8")) for v in payloads.values())
    print(f"EV 상태 발행{' (dry-run)' if args.dry_run else ''}: 전체 {len(payloads)}개 본문 "
          f"{total / 1e6:.2f}MB · 바뀐 것 {stats['changed']}개({stats['bytes'] / 1e3:.0f}KB) · "
          f"그대로 {stats['unchanged']}개 · 삭제 {stats['deleted']}개")


if __name__ == "__main__":
    main()
