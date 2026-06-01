"""
integrated_final_discount_stores.csv의 image_urls 컬럼을 네이버 이미지 API로 채운다.

교차 검증 흐름:
  1. 네이버 지역 검색으로 name + address 검색
  2. 결과 place_name과 입력 name 유사도 확인 (0.6 이상이면 동일 장소 판단)
  3. 검증 통과 시 검증된 이름 + 주소로 이미지 검색 → 정확도 향상
  4. 검증 실패 시 원본 name + address로 이미지 검색 (fallback)

- 이미 image_urls가 있는 행은 건너뜀 (resumable)
- 100건마다 중간 저장
"""
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from src.api.naver_image_api import search_store_images
from src.api.naver_local_api import search_local
from src.utils.file_utils import save_dataframe_csv, save_json
from src.utils.logger import get_logger

logger = get_logger()

INTEGRATED_CSV = Path("data/processed/integrated_final_discount_stores.csv")
INTEGRATED_JSON = Path("data/processed/integrated_final_discount_stores.json")
SLEEP_SEC = 0.2
SIMILARITY_THRESHOLD = 0.6


def _clean_title(title: str) -> str:
    """네이버 지역 검색 결과의 HTML 태그 제거"""
    return re.sub(r"<[^>]+>", "", title).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _verify_and_get_query(name: str, address: str) -> Tuple[bool, str, str]:
    """
    네이버 지역 검색으로 장소 검증.
    Returns:
        (verified, search_name, search_address)
    """
    result = search_local(f"{name} {address}")
    if not result:
        return False, name, address

    place_name = _clean_title(result.get("title", ""))
    road_address = result.get("roadAddress", "")
    addr = result.get("address", "")
    verified_address = road_address or addr or address

    similarity = _similarity(name, place_name)
    verified = similarity >= SIMILARITY_THRESHOLD

    if verified:
        logger.debug("검증 성공 (%.2f): %s → %s", similarity, name, place_name)
        return True, place_name, verified_address
    else:
        logger.debug("검증 실패 (%.2f): %s ≠ %s → fallback", similarity, name, place_name)
        return False, name, address


def _has_images(value) -> bool:
    if pd.isna(value) or str(value).strip() in ("", "nan", "[]"):
        return False
    return True


def run_image_enrich_pipeline() -> pd.DataFrame:
    df = pd.read_csv(INTEGRATED_CSV)

    if "image_urls" not in df.columns:
        df["image_urls"] = None

    targets = df[~df["image_urls"].apply(_has_images)].index.tolist()
    logger.info("이미지 보강 대상: %d건 / 전체 %d건", len(targets), len(df))

    success = 0
    verified_count = 0
    skip = 0

    for i, idx in enumerate(targets):
        row = df.loc[idx]
        name = str(row.get("name", "")).strip()
        address = str(row.get("road_address") or row.get("address", "")).strip()
        category = str(row.get("category", "")).strip()

        if not name or address.lower() in ("nan", ""):
            skip += 1
            continue

        # 교차 검증 → 검증된 경우 정확한 이름/주소 사용
        verified, verified_name, verified_address = _verify_and_get_query(name, address)
        if verified:
            verified_count += 1

        time.sleep(SLEEP_SEC)

        # 이미지 검색 (카테고리 키워드 포함)
        urls = search_store_images(verified_name, verified_address, category)
        if urls:
            df.at[idx, "image_urls"] = json.dumps(urls, ensure_ascii=False)
            success += 1
        else:
            skip += 1

        if (i + 1) % 100 == 0:
            save_dataframe_csv(df, str(INTEGRATED_CSV))
            logger.info(
                "  진행: %d / %d (성공 %d, 검증통과 %d, 스킵 %d) → 중간저장",
                i + 1, len(targets), success, verified_count, skip,
            )

        time.sleep(SLEEP_SEC)

    save_dataframe_csv(df, str(INTEGRATED_CSV))
    save_json(
        df.where(pd.notnull(df), None).to_dict(orient="records"),
        str(INTEGRATED_JSON),
    )
    logger.info(
        "✅ 이미지 보강 완료: 성공 %d건 (검증통과 %d건), 스킵 %d건",
        success, verified_count, skip,
    )
    return df
