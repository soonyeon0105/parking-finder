#!/usr/bin/env python3
"""qa_check.py 단계별 실행 러너 — 주차장 #1073 EV 검수 (뮤즈 #1130 분할·재개 지시).

qa_check.py(6485줄, 단일 스크립트)를 배너(# ---) 기준 34개 단계로 나눠
단계 단위로 실행하고, 단계가 끝날 때마다 중간 결과(fails/warns)를
체크포인트 JSON에 저장한다. 중단되면 다음 단계부터 재개한다.
원본 qa_check.py는 건드리지 않는다 — exec으로 읽어 실행만 한다.

사용법:
  python3 qa_staged.py --list            # 단계 목록
  python3 qa_staged.py --stage N         # 단계 N 하나만 실행 (테스트용)
  python3 qa_staged.py --part A|B|C|D|E|F  # 파트 하나 실행 (단계별 체크포인트 저장)
  python3 qa_staged.py --next            # 다음 미완료 파트 하나 실행
  python3 qa_staged.py --report          # 전 단계 병합 + 최종 판정 출력
  python3 qa_staged.py --run-all         # 미완료 파트를 순서대로 전부 실행
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QA = HERE / "qa_check.py"
CKPT_DIR = Path(os.environ.get(
    "QA_CKPT_DIR",
    "/home/hatch/workspace/goals/arsen-mailbox-watch/hidden_files/qa-checkpoints-1073"))
CKPT_FILE = CKPT_DIR / "checkpoint.json"

# 파트: 연속 단계 범위. 파트 경계는 단계 간 의존성이 끊기는 곳이 아니라
# 실행 시간(환경 유지 시간 안에 들어가는 범위) 기준이다.
PARTS = {
    "A": (1, 3),    # JSON-LD, 내부 링크, 지도 링크 (무거운 I/O 파트)
    "B": (4, 10),   # 기본 구조, 404, 개인정보/GA4, 소유확인, 슬러그, 도시별 확장, EV 상세 생성물
    "C": (11, 11),  # 계산 규칙
    "D": (12, 22),  # 지역 T-03: 오산~연천
    "E": (23, 31),  # 지역 T-03: 서울~울산
    "F": (32, 34),  # 데이터 완전성 게이트, 지도 QA, EV 상세 실측
}

# 단계 프로세스에 주입하는 setup 코드 — qa_check.py 원문에서 가져온 정의만 복사.
# (각 단계가 앞 단계에서 계산한 값을 재사용하므로, 파트 시작 시 다시 계산한다.)
SETUP_COMMON = '''
pages = sorted(DIST.rglob("index.html"))
_ev_detail_urls = set()
for _jf in (DIST / "assets" / "ev-detail").glob("*.json"):
    try:
        _pack = json.loads(_jf.read_text())
    except (OSError, json.JSONDecodeError):
        continue
    for _st in _pack.get("stations", []):
        if _st.get("d"):
            _ev_detail_urls.add(f"/ev/{_pack['pslug']}/{_pack['slug']}/{_st['id']}/")
import html as html_lib
'''

SETUP_SLUG = '''
from build_site import (DONG_SLUG, GU_SLUG, UNKNOWN_DONG, base_slug,
                        dong_slug, dong_slug_map, gu_slug)
_redirects_txt = (DIST / "_redirects").read_text() if (DIST / "_redirects").exists() else ""
_STREET_IDS = {l["id"] for l in LOTS if l.get("list_mode") == "street"}
_STREET_NAMES = {l["id"]: l["name"] for l in LOTS if l.get("list_mode") == "street"}
_DETAIL_IDS = {l["id"] for l in LOTS
               if l["fee"]["type"] != "무료" and (l.get("spaces") or 0) >= 50}
_DETAIL_COUNT = Counter(l["city"] for l in LOTS if l["id"] in _DETAIL_IDS)
'''

SETUP_CALC = '''
from build_site import price_for, hours_text, fee_text
from build_site import price_for as _pf
def _leaked_nan(html: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z])None(?![A-Za-z])|(?<![A-Za-z])nan(?![A-Za-z])", html))
'''

SETUP_FOR_PART = {
    "A": SETUP_COMMON,
    # B: 단계 8·9가 build_site 이름(UNKNOWN_DONG 등)을 쓴다. 원래 파트 B 실행
    # 때는 단계 8 코드가 먼저 실행돼 이름이 생겼지만, 단계 9 단독 재실행 때는
    # 없어 NameError가 난다 — setup에 SLUG를 넣어 단독 실행도 되게 한다.
    "B": SETUP_COMMON + SETUP_SLUG,
    "C": SETUP_COMMON + SETUP_SLUG,
    "D": SETUP_COMMON + SETUP_SLUG + SETUP_CALC,
    "E": SETUP_COMMON + SETUP_SLUG + SETUP_CALC,
    "F": SETUP_COMMON,
}


def parse_stages():
    """qa_check.py를 preamble + 34개 단계 청크로 나눈다. 마지막 단계의 최종 판정 블록은 제외."""
    lines = QA.read_text().split("\n")
    banners = [i for i, l in enumerate(lines) if l.startswith("# ---")]
    bounds = [(0, banners[0])] + [
        (b, banners[k + 1] if k + 1 < len(banners) else len(lines))
        for k, b in enumerate(banners)
    ]
    preamble = "\n".join(lines[bounds[0][0]:bounds[0][1]])
    stages = []
    for si, (a, b) in enumerate(bounds[1:], start=1):
        chunk_lines = lines[a:b]
        # 마지막 단계: 최종 판정 블록(if fails: ... sys.exit) 제외 — --report에서만 실행
        if si == len(bounds) - 1:
            cut = None
            for j, l in enumerate(chunk_lines):
                if l.startswith("if fails:"):
                    cut = j
                    break
            if cut is not None:
                chunk_lines = chunk_lines[:cut]
        title = lines[a].lstrip("# -").strip()
        stages.append({"index": si, "title": title,
                       "lines": (a + 1, b), "code": "\n".join(chunk_lines)})
    return preamble, stages


def load_ckpt():
    if CKPT_FILE.exists():
        return json.loads(CKPT_FILE.read_text())
    return {"done": {}}


def save_ckpt(ckpt):
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CKPT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(ckpt, ensure_ascii=False, indent=1))
    tmp.replace(CKPT_FILE)


def run_stages(preamble, stages, wanted, setup_code, label):
    """wanted 단계들을 한 프로세스 네임스페이스에서 순서대로 exec, 단계마다 체크포인트 저장."""
    ckpt = load_ckpt()
    ns = {"__file__": str(QA), "__name__": "__main__"}
    print(f"[{label}] preamble 실행", flush=True)
    exec(compile(preamble, "qa_preamble", "exec"), ns)
    print(f"[{label}] setup 실행", flush=True)
    exec(compile(setup_code, "qa_setup", "exec"), ns)
    ns.setdefault("fails", [])
    ns.setdefault("warns", [])
    for st in stages:
        if st["index"] not in wanted:
            continue
        if str(st["index"]) in ckpt["done"]:
            print(f"[{label}] 단계 {st['index']} ({st['title']}) — 이미 완료, 건너뜀", flush=True)
            continue
        f0, w0 = len(ns["fails"]), len(ns["warns"])
        print(f"[{label}] 단계 {st['index']} 시작 ({st['title']}, {st['lines'][0]}-{st['lines'][1]}행)",
              flush=True)
        exec(compile(st["code"], f"qa_stage{st['index']}", "exec"), ns)
        ckpt["done"][str(st["index"])] = {
            "title": st["title"],
            "fails": ns["fails"][f0:],
            "warns": ns["warns"][w0:],
        }
        save_ckpt(ckpt)
        print(f"[{label}] 단계 {st['index']} 완료 — fails +{len(ns['fails']) - f0}건, "
              f"warns +{len(ns['warns']) - w0}건 (체크포인트 저장)", flush=True)
    return ckpt


def part_for_stage(n):
    for p, (a, b) in PARTS.items():
        if a <= n <= b:
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--stage", type=int)
    g.add_argument("--part")
    g.add_argument("--next", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--run-all", action="store_true")
    args = ap.parse_args()

    preamble, stages = parse_stages()

    if args.list:
        for st in stages:
            done = "완료" if str(st["index"]) in load_ckpt()["done"] else "미완료"
            print(f"{st['index']:2d}. [{done}] {st['title']} ({st['lines'][0]}-{st['lines'][1]}행)")
        return 0

    if args.report:
        ckpt = load_ckpt()
        missing = [st["index"] for st in stages if str(st["index"]) not in ckpt["done"]]
        if missing:
            print(f"미완료 단계 있음: {missing} — 판정은 전 단계 완료 후")
            return 2
        fails, warns = [], []
        for st in stages:
            d = ckpt["done"][str(st["index"])]
            fails += d["fails"]
            warns += d["warns"]
        print(f"전체 단계 완료: {len(stages)}개 단계")
        print(f"실패 {len(fails)}건 · 경고 {len(warns)}건")
        if fails:
            print(f"실패 {len(fails)}건")
            for f in fails[:20]:
                print(" -", f)
            return 1
        print("모두 통과: JSON-LD, 내부 링크, 404, 슬러그/canonical, 도시별 확장 규칙, "
              "계산 규칙, 데이터 완전성, 지도 QA, EV 상세 Functions 생성물")
        return 0

    if args.run_all:
        ckpt = load_ckpt()
        for p in ["A", "B", "C", "D", "E", "F"]:
            a, b = PARTS[p]
            if all(str(i) in ckpt["done"] for i in range(a, b + 1)):
                print(f"파트 {p} 이미 완료, 건너뜀", flush=True)
                continue
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "--part", p])
            if r.returncode != 0:
                print(f"파트 {p} 중단 (exit {r.returncode}) — 다음 실행 시 --next로 재개", flush=True)
                return r.returncode
            ckpt = load_ckpt()
        print("전 파트 완료 — python3 qa_staged.py --report 로 최종 판정", flush=True)
        return 0

    if args.next:
        ckpt = load_ckpt()
        for p in ["A", "B", "C", "D", "E", "F"]:
            a, b = PARTS[p]
            if not all(str(i) in ckpt["done"] for i in range(a, b + 1)):
                print(f"다음 미완료 파트: {p} (단계 {a}-{b})", flush=True)
                r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                    "--part", p])
                return r.returncode
        print("전 파트 완료 — python3 qa_staged.py --report 로 최종 판정", flush=True)
        return 0

    if args.stage is not None:
        p = part_for_stage(args.stage)
        run_stages(preamble, stages, {args.stage}, SETUP_FOR_PART[p], f"stage{args.stage}")
        return 0

    if args.part:
        p = args.part.upper()
        a, b = PARTS[p]
        run_stages(preamble, stages, set(range(a, b + 1)), SETUP_FOR_PART[p], f"part{p}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
