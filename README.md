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


## 환경변수

`.env` 파일에 설정합니다.

| 변수 | 용도 | 필요 STEP |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 연결 | STEP 7, 8 |
| `KAKAO_REST_API_KEY` | 위도/경도 보강 | STEP 3 |
| `NAVER_CLIENT_ID` | 이미지·지역 검색 | STEP 4 |
| `NAVER_CLIENT_SECRET` | 이미지·지역 검색 | STEP 4 |
| `DATA_GO_KR_SERVICE_KEY` | 공공데이터 OpenAPI | STEP 1 |
| `MMA_NARASARANG_API_URL` | 병무청 나라사랑가게 API | STEP 1 |
| `YEONGCHEON_API_URL` | 영천시 할인업소 API | STEP 1 |
| `TOUR_API_BASE_URL` | 한국관광공사 TourAPI | STEP 6 |
| `OPENAI_API_KEY` | 임베딩 생성 | STEP 8 |
| `YOUTH_POLICY_API_KEY` | 온통청년 청년정책 API | 군인전용 혜택 |
| `KOBIS_API_KEY` | 박스오피스 API | 군인전용 혜택 |
| `S3_BUCKET` | AWS S3 버킷명 | S3 이미지 업로드 |
| `S3_REGION` | AWS 리전 | S3 이미지 업로드 |
| `S3_ACCESS_KEY` | AWS IAM Access Key | S3 이미지 업로드 |
| `S3_SECRET_KEY` | AWS IAM Secret Key | S3 이미지 업로드 |

<br>


## 매장 할인 파이프라인

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
export DATABASE_URL='postgresql+psycopg2://user:password@localhost:5432/milzip'

# 매장 할인 데이터
.venv/bin/python3 -m src.main --mode load

# 청년정책 데이터
.venv/bin/python3 -m src.main --mode load-youth-policy
```

- 매장: `name + address` 기준 중복 스킵, 카테고리 자동 매핑, 이미지 UPDATE
- 청년정책: `title + supervise_inst` 기준 중복 스킵 → `benefits` 테이블 (`SELF_DEVELOPMENT`)

### STEP 8 — 임베딩 생성

```bash
.venv/bin/python3 -m src.main --mode embedding
```

- `embedding IS NULL`인 매장만 처리 (resumable)
- 실행 전 pgvector 확장 및 `stores.embedding` 컬럼 필요 (Flyway V2 자동 처리)

<br>

## S3 이미지 마이그레이션

store_images 테이블의 외부 URL 이미지(네이버 이미지 API 수집)를 AWS S3로 업로드하고 DB URL을 교체합니다.

```bash
.venv/bin/python3 -m src.main --mode s3-upload
```

- `store_images.image_url`이 S3 URL이 아닌 행만 처리
- 이미지 다운로드 → S3 `store/` 경로에 업로드 → DB URL 교체
- 실패한 건은 스킵하고 계속 진행 (resumable)
- 실행 전 `S3_ACCESS_KEY`, `S3_SECRET_KEY` 환경변수 필수

<br>

## 군인 전용 혜택 데이터

### TMO 수집 (좌표 보강)

```bash
.venv/bin/python3 -m src.main --mode tmo
```

- `data/raw/tmo_raw.json` (국방부 공공데이터) 기반
- 카카오 키워드 검색으로 역/터미널 위도/경도 보강

### 주간 박스오피스 수집 (KOBIS)

```bash
.venv/bin/python3 -m src.main --mode boxoffice
```

- 영화진흥위원회 주간 박스오피스 상위 10편 수집
- 영화 상세정보(장르, 상영시간) + 네이버 이미지 검색으로 포스터 수집
- DB upsert: `weekly_boxoffice` 테이블

### 청년정책 수집 (온통청년)

```bash
# 수집
.venv/bin/python3 -m src.main --mode youth-policy

# DB 적재
.venv/bin/python3 -m src.main --mode load-youth-policy
```

- 온통청년 API에서 군인 관련 정책 필터링 수집
- 키워드: 군인, 군장병, 병사, 현역, 복무 등
- DB 적재: `benefits` 테이블 (`SELF_DEVELOPMENT`)

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
| 국방부 | TMO 운영 현황 | 파일 제공 (`data/raw/tmo_raw.json`) |
| 영화진흥위원회 | 주간 박스오피스 + 영화정보 | `KOBIS_API_KEY` |
| 온통청년 | 청년정책 (군인 필터) | `YOUTH_POLICY_API_KEY` |

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
| Kakao Local API | 주소 → 위도/경도, TMO 좌표 보강 | 300,000건/일 (UTC 00:00 초기화) |
| 네이버 지역 검색 API | 장소 교차 검증 | 25,000건/일 공유 |
| 네이버 이미지 검색 API | 매장/영화 포스터 이미지 수집 | 25,000건/일 (KST 00:00 초기화) |
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

### 매장 할인 (stores)

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

### TMO (tmo_list)

| 컬럼 | 설명 |
| --- | --- |
| `name` | TMO명 |
| `phone` | 전화번호 |
| `weekday_start_time` / `weekday_end_time` | 평일 운영시간 |
| `weekend_start_time` / `weekend_end_time` | 주말 운영시간 |
| `location_description` | 위치 설명 |
| `note` | 비고 |
| `is_mobile` | 출장형 여부 |
| `latitude` / `longitude` | 위도/경도 (카카오 보강) |
| `address` | 주소 |

### 박스오피스 (weekly_boxoffice)

| 컬럼 | 설명 |
| --- | --- |
| `rank` | 박스오피스 순위 |
| `movie_cd` | KOBIS 영화코드 |
| `title` | 영화명 |
| `open_date` | 개봉일 |
| `audience_count` | 누적 관객수 |
| `genre` | 장르 |
| `runtime_minutes` | 상영시간(분) |
| `poster_url` | 포스터 이미지 URL |
