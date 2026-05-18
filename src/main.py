import argparse

import pandas as pd

from src.crawler.web_scraper import scrape_all_sites
from src.api.kakao_local_api import search_address, search_keyword
from src.api.mma_narasarang_api import fetch_mma_narasarang_api
from src.api.yeongcheon_open_api import fetch_yeongcheon_open_api
from src.processor.kakao_enricher import (
    enrich_discount_stores_with_kakao,
    extract_kakao_target_stores,
)
from src.processor.naver_enricher import (
    run_naver_enrich_pipeline,
    run_naver_target_extract_pipeline,
)
from src.processor.normalize_store import normalize_all_raw_csv, _extract_discount_rate
from src.processor.open_api_normalizer import (
    normalize_mma_narasarang_api,
    normalize_yeongcheon_open_api,
)
from src.processor.tour_api_enricher import (
    run_tour_api_enrich_pipeline,
    run_tour_target_extract_pipeline,
)
from src.utils.file_utils import save_dataframe_csv, save_json
from src.utils.logger import get_logger

logger = get_logger()


# ==============================
# 1. CSV 정규화
# ==============================
def run_file_data_pipeline():
    logger.info("📂 CSV 파일데이터 정규화 시작")
    result = normalize_all_raw_csv()
    logger.info("✅ CSV 데이터 정규화 완료: %s건", len(result))
    return result


# ==============================
# 2. Open API
# ==============================
def run_open_api_pipeline():
    logger.info("🌐 OpenAPI 데이터 수집 시작")

    dataframes = []

    try:
        logger.info("➡️ 영천시 API 요청 중...")
        yeongcheon_raw = fetch_yeongcheon_open_api()
        yeongcheon_df = normalize_yeongcheon_open_api(yeongcheon_raw)
        dataframes.append(yeongcheon_df)
        logger.info("✅ 영천시 데이터 완료: %s건", len(yeongcheon_df))
    except RuntimeError as error:
        logger.error("❌ 영천시 API 실패: %s", error)

    try:
        logger.info("➡️ 병무청 API 요청 중...")
        mma_raw = fetch_mma_narasarang_api()
        mma_df = normalize_mma_narasarang_api(mma_raw)
        dataframes.append(mma_df)
        logger.info("✅ 병무청 데이터 완료: %s건", len(mma_df))
    except RuntimeError as error:
        logger.error("❌ 병무청 API 실패: %s", error)

    if not dataframes:
        raise RuntimeError("수집 가능한 OpenAPI 데이터가 없습니다.")

    merged = pd.concat(dataframes, ignore_index=True)

    save_dataframe_csv(merged, "data/processed/open_api_discount_stores.csv")
    save_json(
        merged.where(pd.notnull(merged), None).to_dict(orient="records"),
        "data/processed/open_api_discount_stores.json",
    )

    logger.info("🎉 OpenAPI 데이터 완료: %s건", len(merged))
    return merged


# ==============================
# 3. 전체 통합
# ==============================
def run_all_pipeline():
    logger.info("🚀 전체 데이터 파이프라인 실행")

    file_df = run_file_data_pipeline()
    api_df = run_open_api_pipeline()

    final_df = pd.concat([file_df, api_df], ignore_index=True)

    save_dataframe_csv(final_df, "data/processed/final_discount_stores.csv")
    save_json(
        final_df.where(pd.notnull(final_df), None).to_dict(orient="records"),
        "data/processed/final_discount_stores.json",
    )

    logger.info("🎉 최종 데이터 완료: %s건", len(final_df))
    return final_df


# ==============================
# 4. 카카오 (좌표)
# ==============================
def run_kakao_target_pipeline():
    logger.info("📄 카카오 보강 대상 추출 시작")
    result = extract_kakao_target_stores()
    logger.info("✅ 카카오 대상 추출 완료: %s건", len(result))
    return result


def run_enrich_pipeline():
    logger.info("📍 카카오 위치 정보 보강 시작")
    result = enrich_discount_stores_with_kakao()
    logger.info("✅ 카카오 보강 완료: %s건", len(result))
    return result


# ==============================
# 5. 네이버
# ==============================
def run_naver_target_pipeline():
    logger.info("📄 네이버 보강 대상 추출 시작")
    result = run_naver_target_extract_pipeline()
    logger.info("✅ 네이버 대상 추출 완료: %s건", len(result))
    return result


def run_naver_pipeline():
    logger.info("🟢 네이버 크롤링 시작")
    result = run_naver_enrich_pipeline()
    logger.info("✅ 네이버 보강 완료")
    return result


# ==============================
# 6. Tour API
# ==============================
def run_tour_target_pipeline():
    logger.info("📄 TourAPI 보강 대상 추출 시작")
    result = run_tour_target_extract_pipeline()
    logger.info("✅ TourAPI 대상 추출 완료: %s건", len(result))
    return result


def run_tour_pipeline():
    logger.info("🏛️ TourAPI 보강 시작")
    result = run_tour_api_enrich_pipeline()
    logger.info("✅ TourAPI 보강 완료: %s건", len(result))
    return result


INTEGRATED_FINAL_CSV = "data/processed/integrated_final_discount_stores.csv"
INTEGRATED_FINAL_JSON = "data/processed/integrated_final_discount_stores.json"

FINAL_COLUMNS = [
    "name", "category", "business_type", "address", "road_address",
    "phone", "open_time", "close_time", "closed_day", "main_menu",
    "discount_info", "discount_rate", "latitude", "longitude",
    "source", "source_region", "data_base_date",
]


def _is_empty(value) -> bool:
    return pd.isna(value) or str(value).strip() in ("", "nan", "None")


def _kakao_enrich_row(row, cache: dict) -> dict:
    """단일 행에 대해 카카오 API로 위도/경도 + 도로명주소 보강"""
    road = str(row.get("road_address", "")).strip()
    addr = str(row.get("address", "")).strip()
    query_addr = road if road and road.lower() != "nan" else addr
    name = str(row.get("name", "")).strip()

    if not query_addr:
        return {}

    cache_key = f"{query_addr}|{name}"
    if cache_key in cache:
        return cache[cache_key]

    result = None

    resp = search_address(query_addr)
    if resp:
        docs = resp.get("documents", [])
        if docs:
            result = docs[0]

    if not result:
        resp2 = search_keyword(f"{query_addr} {name}".strip())
        if resp2:
            docs2 = resp2.get("documents", [])
            if docs2:
                result = docs2[0]

    cache[cache_key] = result or {}
    return cache[cache_key]


# ==============================
# 7. 웹 크롤링
# ==============================
def run_web_scrape_pipeline(targets=None):
    logger.info("🕸️  웹 크롤링 시작 (대상: %s)", targets or "전체")
    df = scrape_all_sites(targets)
    save_dataframe_csv(df, "data/processed/web_scraped_discount_stores.csv")
    save_json(
        df.where(pd.notnull(df), None).to_dict(orient="records"),
        "data/processed/web_scraped_discount_stores.json",
    )
    logger.info("✅ 웹 크롤링 완료: %d건", len(df))
    return df


# ==============================
# 8. 통합 최종 (merge + Kakao 좌표 보강)
# ==============================
def _load_or_build_merged() -> pd.DataFrame:
    """통합 파일이 있으면 로드, 없으면 기존 final + 웹 크롤링 병합 후 반환"""
    import os

    if os.path.exists(INTEGRATED_FINAL_CSV):
        logger.info("📂 기존 통합 파일 로드: %s", INTEGRATED_FINAL_CSV)
        df = pd.read_csv(INTEGRATED_FINAL_CSV)
        if "discount_rate" not in df.columns:
            df["discount_rate"] = df["discount_info"].apply(_extract_discount_rate)
        for col in FINAL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df[FINAL_COLUMNS].reset_index(drop=True)

    logger.info("🔀 최초 병합 시작")
    existing_df = pd.read_csv("data/processed/final_discount_stores.csv")
    if "discount_rate" not in existing_df.columns:
        existing_df["discount_rate"] = existing_df["discount_info"].apply(_extract_discount_rate)

    web_df = pd.read_csv("data/processed/web_scraped_discount_stores.csv")

    for df in [existing_df, web_df]:
        for col in FINAL_COLUMNS:
            if col not in df.columns:
                df[col] = None

    merged = pd.concat(
        [existing_df[FINAL_COLUMNS], web_df[FINAL_COLUMNS]],
        ignore_index=True,
    )

    before = len(merged)
    merged["_dedup_key"] = (
        merged["name"].fillna("").str.strip()
        + "|"
        + merged["address"].fillna("").str.strip()
    )
    merged = merged.drop_duplicates(subset=["_dedup_key"]).drop(columns=["_dedup_key"])
    merged = merged[merged["name"].fillna("").str.strip() != ""].reset_index(drop=True)
    logger.info("📊 병합: %d건 → 중복 제거 후 %d건", before, len(merged))
    return merged


def run_integrated_final_pipeline():
    """기존 final + 웹 크롤링 데이터를 병합하고 누락된 위도경도를 카카오로 채워 진짜 최종 파일 생성.
    이미 통합 파일이 있으면 위도경도 없는 행만 보강해 재개(resumable)."""
    import time as _time

    merged = _load_or_build_merged()

    # 위도경도가 문자열로 저장된 경우 float 변환
    for col in ("latitude", "longitude"):
        merged[col] = pd.to_numeric(merged[col], errors="coerce")

    needs_enrich = merged.apply(
        lambda r: _is_empty(r["latitude"]) or _is_empty(r["longitude"]), axis=1
    )
    target_indices = merged[needs_enrich].index.tolist()
    logger.info("📍 카카오 보강 대상: %d건 / 전체 %d건", len(target_indices), len(merged))

    if not target_indices:
        logger.info("✅ 보강 대상 없음. 파일 저장만 수행합니다.")
    else:
        cache: dict = {}
        success = 0
        skip = 0

        for i, idx in enumerate(target_indices):
            row = merged.loc[idx]
            result = _kakao_enrich_row(row, cache)

            if result:
                merged.at[idx, "latitude"] = float(result.get("y", 0) or 0) or None
                merged.at[idx, "longitude"] = float(result.get("x", 0) or 0) or None

                road = result.get("road_address") or {}
                if isinstance(road, dict) and _is_empty(merged.at[idx, "road_address"]):
                    merged.at[idx, "road_address"] = road.get("address_name", "")

                success += 1
            else:
                skip += 1

            if (i + 1) % 100 == 0:
                # 중간 저장 (API limit 대비)
                save_dataframe_csv(merged, INTEGRATED_FINAL_CSV)
                logger.info("  진행: %d / %d (성공 %d, 스킵 %d) → 중간저장", i + 1, len(target_indices), success, skip)

            _time.sleep(0.4)

        logger.info("📍 카카오 보강 완료: 성공 %d건, 스킵 %d건", success, skip)

    save_dataframe_csv(merged, INTEGRATED_FINAL_CSV)
    save_json(
        merged.where(pd.notnull(merged), None).to_dict(orient="records"),
        INTEGRATED_FINAL_JSON,
    )

    lat_count = merged["latitude"].notna().sum()
    logger.info("✅ 진짜 최종 데이터 저장 완료: %d건 (위도경도 보유 %d건)", len(merged), lat_count)
    return merged


# ==============================
# CLI
# ==============================
def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=[
            "file",
            "api",
            "all",
            "kakao-target",
            "enrich",
            "naver-target",
            "naver",
            "tour-target",
            "tour",
            "web-scrape",
            "integrated-final",
        ],
        default="file",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        help="web-scrape 모드에서 크롤링할 사이트 (ddc ihc goyang inje)",
    )

    args = parser.parse_args()

    if args.mode == "file":
        run_file_data_pipeline()

    elif args.mode == "api":
        run_open_api_pipeline()

    elif args.mode == "all":
        run_all_pipeline()

    elif args.mode == "kakao-target":
        run_kakao_target_pipeline()

    elif args.mode == "enrich":
        run_enrich_pipeline()

    elif args.mode == "naver-target":
        run_naver_target_pipeline()

    elif args.mode == "naver":
        run_naver_pipeline()

    elif args.mode == "tour-target":
        run_tour_target_pipeline()

    elif args.mode == "tour":
        run_tour_pipeline()

    elif args.mode == "web-scrape":
        run_web_scrape_pipeline(args.targets)

    elif args.mode == "integrated-final":
        run_integrated_final_pipeline()


if __name__ == "__main__":
    main()
