# 공영주차장 파인더 — 수원시

공공데이터로 만든 **공영주차장 요금 계산 + 무료 개방 파인더**입니다.
수원시 4개 구 72곳을 정적 HTML 39페이지 + 404 페이지 + 인터랙티브 JavaScript 계산기로 제공하며,
서버·DB·외부 API 없이 동작합니다. 페이지 경로는 시·도 / 시·군 / 구 / 동 단위로 나뉘어 있어
다른 지자체를 같은 파이프라인에 그대로 추가할 수 있습니다.

- 랜딩: `dist/index.html`
- 수원시 허브: `dist/parking/gyeonggi/suwon/index.html`
- 구 허브(계산기): `dist/parking/gyeonggi/suwon-yeongtong/index.html` (권선·팔달·장안 동일 구조)
- 주말·공휴일 무료 개방: `dist/parking/gyeonggi/suwon-yeongtong/weekend-free/index.html`
- 행정동 상세: `dist/parking/gyeonggi/suwon-yeongtong/maetan-dong/index.html`
- 없는 주소(소프트 404 방지): `dist/404.html`

## 데이터 (모두 실제 공개 데이터)

| 구분 | 출처 | 수령 방법 | 수량 | 기준일 |
|---|---|---|---|---|
| 요금·운영시간·구획수·좌표 | 공공데이터포털 [전국주차장정보표준데이터](https://www.data.go.kr/data/15012896/standard.do) | 포털 '데이터 활용 > 그리드' CSV 다운로드 (로그인·인증키 불필요) | 전국 18,994행 중 수원시 **59행** | 2026-04-16 |
| 실시간 잔여면수·구획 구성 | [수원도시공사 공영주차장 안내 지도](https://parking.suwonudc.co.kr/parking/parkingMap) | 페이지에 내장된 주차장 목록 JSON 스냅샷 | **69곳** | 2026-11-16 19:11 조회 |
| 주소·면수 보강 | [경기도 수원시_공영노외주차장현황](https://www.data.go.kr/data/15157772/fileData.do) | 포털 파일데이터 다운로드 (로그인 불필요) | 112행 | 2026-08-01 |

원본은 `data/raw/`에 그대로 보관했고, `data/suwon_parking.json`의 `meta.sources`에 파일명·sha256·수령 시각·라이선스를 기록했습니다.

### 병합 결과 (`scripts/summary.md`)

- 최종 **72곳** (표준데이터 59 + 도시공사에만 있는 13곳), 총 구획 **11,743면**
- 구별: 영통 18 / 권선 14 / 팔달 24 / 장안 16
- 표준데이터 55곳에 실시간 잔여면수 연결(좌표 + 구획수 가중 매칭)
- 요금 유료 59곳, **요금 정보 미상 13곳**(0원으로 표시하지 않고 '현장 확인'으로 구분)
- 일요일·공휴일 무료 개방 표기 1곳(영통구청), 토요일 무료 0곳, 토요일 미운영 4곳

## 빌드

```bash
python3 scripts/prepare_data.py     # 원자료 정제·병합 → data/suwon_parking.json, scripts/summary.md
python3 scripts/build_site.py --base https://parking.9welfare.com   # dist/ 39페이지 + 404.html + sitemap.xml, robots.txt
python3 -m http.server 8000 --directory dist   # 확인용 (종료: Ctrl+C)
```

`--base`를 생략하면 기본값 `https://parking.9welfare.com`이 쓰입니다. canonical·Open Graph·JSON-LD·sitemap URL이
모두 이 값 기준으로 생성되므로, 다른 도메인에 배포할 때는 `--base https://내도메인`만 바꿔 다시 빌드하면 됩니다.

`dist/`는 상대경로로 만들어져 **파일을 그대로 열어도**(file://) 스타일과 계산기가 동작합니다.
유일한 예외가 `dist/404.html`입니다. 이 페이지는 주소창의 경로가 그대로 유지된 채 표시되므로
(Cloudflare Pages가 없는 주소에 이 파일을 돌려줌) 상대경로를 쓸 수 없어 링크·에셋을 사이트
절대경로(`/assets/...`, `/parking/...`)로 생성하고 `noindex`로 둡니다. 빌드할 때마다 자동 생성됩니다.

## 검증 스크립트

```bash
python3 scripts/qa_check.py        # JSON-LD 파싱·내부 링크 345건·404.html 절대링크/noindex·계산 규칙 표본·슬러그/canonical 검사
python3 scripts/verify_site.py     # headless Chromium: 클릭·정렬·뷰포트·file:// 검증 + 스크린샷
python3 scripts/crosscheck_calc.py # JS 계산 결과 vs Python 규칙 전수 교차검증(3,240건)
```

`verify_site.py`·`crosscheck_calc.py`는 Playwright(Chromium)가 필요합니다. 스크린샷은 기본으로
`screenshots/`에 저장되고 `PARKING_SHOTS_DIR=/원하는/경로`로 바꿀 수 있습니다.
검증 결과 요약은 `scripts/verify_result.json`에 남습니다.

현재 상태: qa_check 통과, crosscheck 3,240건 불일치 0건, verify_site 20/20 통과.

## 구현 규칙

- 요금: `기본시간 이하 = 기본요금`, 초과 시 `기본요금 + ceil((총시간-기본시간)/추가단위시간) × 추가단위요금`
- 1일 주차권 요금이 있으면 상한(Cap) 적용, 그다음 감면율 적용
- 요금 필드가 비어 있으면 0원이 아니라 **요금 정보 미상(현장 확인)**
- 무료 판정: `요금정보=무료` 이거나 특기사항의 '일+공휴일 무료개방' 같은 표기가 있는 요일
- 미운영(휴무)은 무료와 구분해 표시 (`운영요일`, `00:00~00:00` 처리)
- 일요일은 표준데이터에 전용 칸이 없어 **공휴일 칸을 준용**(페이지에 명시)

## 전국 확장: URL 슬러그는 자동 생성

URL은 `/{시·도}/{시·군}/{구}/{동}/` 구조이고, 구·동 이름의 영문 슬러그는 `scripts/build_site.py`가 만듭니다.

- **기존 주소는 고정**: 이미 공개된 수원시 29개 동·4개 구 슬러그는 `DONG_SLUG` / `GU_SLUG` /
  `data.suwon_parking.json`의 `districts[].slug` 매핑이 항상 우선하므로 한 글자도 바뀌지 않습니다.
  (예: `고색동 → goseak-dong`, `인계동 → ingye-dong`, `영통구 → suwon-yeongtong`)
- **새 지역은 자동**: 매핑에 없는 이름은 국어의 로마자 표기법(문화체육관광부 고시)에 따라 자동 생성합니다.
  행정 접미사는 하이픈으로 분리하고(`-dong`, `-eup`, `-myeon`, `-ri`, `-ga`, `-ro`, `-daero`, `-gil`, `-gu`, `-si`, `-gun`, `-do`),
  종성 대표음(ㄱ·ㄷ·ㅂ → k·t·p)과 ㄹ의 비음화·유음화(백로 → baengno, 신라 → silla)를 반영합니다.
  - `정자동 → jeongja-dong`, `판교동 → pangyo-dong`, `우만2동 → uman2-dong`, `경수대로 → gyeongsu-daero`
  - `분당구 → bundang-gu`, `성남시 → seongnam-si`, 시 슬러그는 접미사를 떼어 `seongnam`
  - 구 슬러그는 `시 슬러그 + 로마자` 형태로 `분당구 → seongnam-bundang`(수원시의 `suwon-yeongtong`과 같은 규칙)
- **충돌 방지**: 같은 구에서 로마자가 겹치면 이름 정렬 순서로 `-2`, `-3`을 붙여 결정적으로 분리합니다.
  (`dong_slug_map()` — 구 허브 표와 동 상세 페이지가 같은 결과를 쓰도록 한 곳에서 계산)
- 새 데이터를 넣을 때는 `data/*.json`에 `meta.region`·`districts[]`·`lots[].gu/dong`만 채우면 되고,
  `build_site.py`의 수동 딕셔너리를 고칠 필요가 없습니다. 표준데이터의 시·군 필터를 바꿔 `prepare_data.py`를
  재사용하면 다른 지자체도 같은 구조로 생성됩니다.
- `qa_check.py`가 기존 슬러그 불변·fallback 결과·충돌 해소·canonical 도메인을 함께 검사합니다.

## 구조

```
.
├── LICENSE                       # MIT (코드) · 데이터는 원자료 라이선스를 따름
├── assets/style.css, app.js      # 모바일 퍼스트 CSS · 계산기
├── data/raw/                     # 원본 3종(가공 없음)
├── data/suwon_parking.json       # 정제 결과(메타·72곳·품질 리포트)
├── scripts/prepare_data.py       # 정제·병합·품질 점검
├── scripts/build_site.py         # 정적 페이지 생성기(--base 로 도메인 지정, 슬러그 자동 생성)
├── scripts/summary.md|json       # 정제 요약(구·동·무료·정합성)
├── scripts/qa_check.py           # JSON-LD·링크·404·계산·슬러그 검사
├── scripts/verify_site.py        # 브라우저 검증(+스크린샷)
├── scripts/crosscheck_calc.py    # JS↔Python 계산 교차검증
└── dist/                         # 배포 산출물 39페이지 + 404.html
```

## 배포 (Cloudflare Pages)

- Build command: 없음(빈칸)
- Output directory: `dist`
- 빌드 산출물을 저장소에 함께 커밋해 두었으므로 별도 빌드 단계 없이 바로 배포됩니다.
  데이터를 갱신할 때만 로컬에서 `build_site.py --base https://parking.9welfare.com`을 다시 돌려 `dist/`를 커밋합니다.
- `dist/404.html`이 있으므로 없는 주소는 상태코드 404와 함께 이 페이지가 표시됩니다(소프트 404 방지).

## 라이선스

- 코드·생성 스크립트: [MIT](LICENSE) — Copyright (c) 2026 soonyeon0105 (공영주차장 파인더)
- 데이터: 원자료별 라이선스를 그대로 따릅니다. 표준데이터·공영노외주차장현황은 공공데이터포털 이용조건,
  수원도시공사 안내 지도는 공개 웹페이지 참고용입니다(`data/suwon_parking.json`의 `meta.sources[].license`).

## 알려진 한계

- 표준데이터 요금 필드는 기관 입력값이라 '최초 N분 무료' 같은 현장 정책이 빠져 있을 수 있습니다(원자료 기준일 표시).
- 실시간 잔여면수는 **조회 시점 스냅샷**입니다. 실시간 서비스로 만들려면 수원도시공사/경기도교통정보센터 API 연동과 주기적 재빌드가 필요합니다.
- **구획수와 스냅샷 총면수는 기준이 다릅니다.** 구획수는 표준데이터의 등록면수, 실시간 잔여면수 옆의 총면수는
  수원도시공사 안내 지도의 스냅샷 합계입니다. 17곳에서 두 값이 다르며(예: 매탄4지구 구획 60면 ↔ 스냅샷 58면,
  광교 1동 공영 구획 35면 ↔ 스냅샷 50면), 카드에 차이를 숫자로 함께 적고 구 페이지의 ‘데이터 출처와 한계’에도
  설명을 두었습니다(`scripts/qa_check.py`·`crosscheck_calc.py`는 이 표기와 무관하게 통과).
- 표준데이터의 주차장관리번호가 7쌍 중복되어 내부 식별자는 순번으로 대체했습니다(`scripts/summary.md` 참고).
- 실시간 목록에만 있는 13곳은 요금·운영시간이 없어 '요금 정보 미상'으로 표시하고, 주소가 없으면 '동 인근(좌표 기준)'으로 안내합니다.
- 로마자 자동 생성은 음운 변화(경음화·구개음화 등)를 모두 반영하지 않는 간략 규칙입니다. 특정 지역의 공식 표기가
  다르면 `DONG_SLUG` / `GU_SLUG`에 한 줄만 추가하면 그 이름부터 매핑이 우선 적용됩니다.

## 다음 단계(제안)

1. Cloudflare Pages(또는 GitHub Pages) 연결 후 `parking.9welfare.com` 도메인 연결
2. 애드센스 승인 후 플레이스홀더(광고 영역 2곳, 24px 여백 확보)에 실제 슬롯 삽입
3. 경기도교통정보센터·수원도시공사 API로 잔여면수 실시간화(스케줄러가 주기적으로 JSON 갱신 후 재빌드)
4. 다른 시·군으로 확장(표준데이터 시·군 필터만 추가하면 동일 파이프라인 재사용, 슬러그는 자동)
