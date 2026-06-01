# Milzip ETL

군장병 혜택 매장 데이터를 수집·정제·적재하는 파이프라인입니다.

<br>

## ETL Process

### 1. Extract (데이터 수집)

- 공공데이터 및 외부 데이터 소스로부터 매장 정보 수집

- 지역, 업종, 혜택 정보 등 원천 데이터 확보

### 2. Transform (데이터 정제·변환)

- 중복 데이터 제거

- 주소 및 연락처 형식 표준화

- 위도·경도 보정

- 서비스 요구사항에 맞게 데이터 가공

### 3. Load (데이터 적재)

- 정제된 데이터를 데이터베이스에 저장

- 신규 데이터 추가 및 기존 데이터 업데이트

<br>


## 프로젝트 구조

| 폴더 | 역할 |
| --- | --- |
| `src/crawler/` | 웹 크롤링 |
| `src/api/` | 공공 API 호출 |
| `src/processor/` | 데이터 정제·보강 |
| `src/loader/` | DB 적재 |
| `src/utils/` | 공통 유틸 |
| `data/raw/` | 원본 데이터 |
| `data/processed/` | 가공 데이터 |

<br>


## 실행

```bash
source .venv/bin/activate
```

또는 직접 경로 지정:

```bash
.venv/bin/python3 -m src.main --mode <mode>
```

<br>


## 파이프라인

### STEP 1 — 공공데이터 수집 및 병합

```bash
.venv/bin/python3 -m src.main --mode file   # CSV 정규화 (포천, 파주, 홍천)
.venv/bin/python3 -m src.main --mode api    # 영천시 / 병무청 OpenAPI 수집
.venv/bin/python3 -m src.main --mode all    # 전체 병합 → final_discount_stores.csv
```

### STEP 2 — 지자체 사이트 크롤링

```bash
.venv/bin/python3 -m src.main --mode web-scrape                                # 전체
.venv/bin/python3 -m src.main --mode web-scrape --targets ddc ihc goyang inje  # 특정만
```

### STEP 3 — 통합 최종 파일 생성 (카카오 좌표 보강)

```bash
.venv/bin/python3 -m src.main --mode integrated-final
```

- `final` + 웹 크롤링 데이터 병합 후 카카오 API로 위도/경도 보강
- API 한도 초과 시 재실행하면 완료된 건 스킵하고 재개 (resumable)
- 한도: 300,000건/일, **UTC 00:00 (KST 09:00)** 초기화

### STEP 4 — 이미지 보강 (네이버 이미지 검색 API)

```bash
.venv/bin/python3 -m src.main --mode image-enrich
```

- 네이버 지역 검색으로 장소 교차 검증 후 이미지 검색
- 이미 `image_urls`가 있는 행은 스킵 (resumable)
- 한도: 25,000건/일, **KST 00:00** 초기화

### STEP 5 — 네이버 크롤링 보강 (선택)

```bash
.venv/bin/python3 -m src.main --mode naver-target  # 누락 데이터 추출
.venv/bin/python3 -m src.main --mode naver          # 크롤링 보강
```

추출 항목: `phone` `open_time` `close_time` `closed_day` `main_menu`

### STEP 6 — TourAPI 보강 (선택)

```bash
.venv/bin/python3 -m src.main --mode tour-target
.venv/bin/python3 -m src.main --mode tour
```

### STEP 7 — DB 적재

```bash
.venv/bin/python3 -m src.loader.store_loader
```

- `name + address` 기준 중복 스킵
- 기존 매장에 `image_urls`가 새로 생긴 경우 `store_images` 테이블 UPDATE
- 카테고리 자동 매핑 포함 (`src/utils/category_mapper.py`)

### STEP 8 — 임베딩 생성

```bash
.venv/bin/python3 -m src.main --mode embedding
```

- `embedding IS NULL`인 매장만 처리 (resumable)

<br>


## 데이터 출처

### 공공데이터포털 파일

| 지역 | 데이터셋 |
| --- | --- |
| 경기도 포천시 | data.go.kr/15106202 |
| 경기도 파주시 | data.go.kr/15126366 |
| 강원특별자치도 홍천군 | 공공데이터포털 CSV |

### 공공 OpenAPI

| 기관 | API명 | 환경변수 |
| --- | --- | --- |
| 병무청 | 나라사랑가게 OpenAPI | `MMA_NARASARANG_API_URL` |
| 경상북도 영천시 | 군장병 할인업소 OpenAPI | `YEONGCHEON_API_URL` |
| 한국관광공사 | TourAPI 관광지 상세정보 | `TOUR_API_BASE_URL` |

### 웹 크롤링

| 키 | 지역 |
| --- | --- |
| `ddc` | 경기도 동두천시 |
| `ihc` | 강원특별자치도 화천군 |
| `goyang` | 경기도 고양시 |
| `inje` | 강원특별자치도 인제군 |

### 보강 API

| 서비스 | 용도 | 한도 |
| --- | --- | --- |
| Kakao Local API | 주소 → 위도/경도, 도로명주소 | 300,000건/일 (UTC 00:00 초기화) |
| 네이버 지역 검색 API | 장소 교차 검증 | 25,000건/일 공유 |
| 네이버 이미지 검색 API | 매장 대표 이미지 수집 | 25,000건/일 (KST 00:00 초기화) |
| 네이버 플레이스 크롤링 | 전화번호, 영업시간, 메뉴 보강 | — |

<br>


## 카테고리 매핑

| ENUM | 업종 |
| --- | --- |
| `FOOD` | 일반음식점, 한식, 중식, 갈비, 치킨, 피자 등 |
| `CAFE` | 카페, 커피, 제과점, 베이커리, 휴게음식점 |
| `LEISURE` | PC방, 노래연습장, 당구, 볼링, 헬스 등 |
| `ACCOMMODATION` | 숙박, 모텔, 호텔, 펜션, 사우나, 목욕 |
| `ETC` | 이미용, 기타 |

<br>


## 출력 스키마

| 컬럼 | 설명 | 출처 |
| --- | --- | --- |
| `name` | 업소명 | 필수 |
| `category` | 업종 (ENUM) | 자동 매핑 |
| `address` | 지번주소 | 필수 |
| `road_address` | 도로명주소 | 카카오 보강 |
| `phone` | 전화번호 | 네이버 보강 |
| `open_time` / `close_time` | 영업시간 | 네이버 보강 |
| `closed_day` | 휴무일 | 네이버 보강 |
| `main_menu` | 대표메뉴 | 네이버 보강 |
| `discount_info` | 할인내용 (문자열) | 필수 |
| `discount_rate` | 할인율/금액 (숫자) | 비교·정렬용 |
| `latitude` / `longitude` | 위도/경도 | 카카오 보강 |
| `image_urls` | 이미지 URL 목록 (JSON 배열) | 네이버 이미지 보강 |
| `source` | 데이터 출처 코드 | |
| `source_region` | 수집 지역 | |
