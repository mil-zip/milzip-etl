import argparse

import pandas as pd

from src.api.mma_narasarang_api import fetch_mma_narasarang_api
from src.api.yeongcheon_open_api import fetch_yeongcheon_open_api
from src.processor.kakao_enricher import enrich_discount_stores_with_kakao
from src.processor.naver_enricher import run_naver_enrich_pipeline
from src.processor.normalize_store import normalize_all_raw_csv
from src.processor.open_api_normalizer import (
    normalize_mma_narasarang_api,
    normalize_yeongcheon_open_api,
)
from src.utils.file_utils import save_dataframe_csv, save_json
from src.utils.logger import get_logger

logger = get_logger()


def run_file_data_pipeline():
    """수동 다운로드한 CSV 파일데이터를 정규화하는 함수"""
    logger.info("📂 CSV 파일데이터 정규화 시작")
    result = normalize_all_raw_csv()
    logger.info("✅ CSV 데이터 정규화 완료: %s건", len(result))
    return result


def run_open_api_pipeline():
    """OpenAPI 데이터를 수집하고 정규화하는 함수"""
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
        logger.critical("🚨 수집 가능한 OpenAPI 데이터 없음")
        raise RuntimeError("수집 가능한 OpenAPI 데이터가 없습니다.")

    logger.info("🔄 OpenAPI 데이터 병합 중...")
    merged = pd.concat(dataframes, ignore_index=True)

    logger.info("💾 OpenAPI 데이터 저장 중...")
    save_dataframe_csv(merged, "data/processed/open_api_discount_stores.csv")
    save_json(
        merged.where(pd.notnull(merged), None).to_dict(orient="records"),
        "data/processed/open_api_discount_stores.json",
    )

    logger.info("🎉 OpenAPI 데이터 정규화 완료: %s건", len(merged))
    return merged


def run_all_pipeline():
    """CSV 파일데이터와 OpenAPI 데이터를 모두 병합하는 함수"""
    logger.info("🚀 전체 데이터 파이프라인 실행")

    file_df = run_file_data_pipeline()
    api_df = run_open_api_pipeline()

    logger.info("🔄 전체 데이터 병합 중...")
    final_df = pd.concat([file_df, api_df], ignore_index=True)

    logger.info("💾 최종 데이터 저장 중...")
    save_dataframe_csv(final_df, "data/processed/final_discount_stores.csv")
    save_json(
        final_df.where(pd.notnull(final_df), None).to_dict(orient="records"),
        "data/processed/final_discount_stores.json",
    )

    logger.info("🎉 최종 데이터 통합 완료: %s건", len(final_df))
    return final_df


def run_enrich_pipeline():
    """카카오 로컬 API로 할인업소 위치 정보를 보강하는 함수"""
    logger.info("📍 카카오 위치 정보 보강 시작")
    result = enrich_discount_stores_with_kakao()
    logger.info("✅ 카카오 위치 정보 보강 완료: %s건", len(result))
    return result


def run_naver_pipeline():
    """네이버 플레이스 크롤링으로 할인업소 정보를 보강하는 함수"""
    logger.info("🟢 네이버 플레이스 정보 보강 시작")
    result = run_naver_enrich_pipeline()
    logger.info("✅ 네이버 플레이스 정보 보강 완료")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["file", "api", "all", "enrich", "naver"],
        default="file",
        help="실행할 데이터 파이프라인 선택",
    )

    args = parser.parse_args()

    if args.mode == "file":
        run_file_data_pipeline()
    elif args.mode == "api":
        run_open_api_pipeline()
    elif args.mode == "all":
        run_all_pipeline()
    elif args.mode == "enrich":
        run_enrich_pipeline()
    elif args.mode == "naver":
        run_naver_pipeline()


if __name__ == "__main__":
    main()
