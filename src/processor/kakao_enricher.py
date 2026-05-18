import time

import pandas as pd

from src.api.kakao_local_api import search_address, search_keyword
from src.utils.file_utils import save_dataframe_csv, save_json

FINAL_CSV_PATH = "data/processed/final_discount_stores.csv"
FINAL_JSON_PATH = "data/processed/final_discount_stores.json"

KAKAO_TARGET_CSV_PATH = "data/processed/kakao_target_stores.csv"
KAKAO_TARGET_JSON_PATH = "data/processed/kakao_target_stores.json"


def is_empty(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def needs_kakao_enrich(row) -> bool:
    return is_empty(row["latitude"]) or is_empty(row["longitude"])


def extract_kakao_target_stores() -> pd.DataFrame:
    """final 데이터에서 위도/경도가 비어있는 행만 추출"""
    dataframe = pd.read_csv(FINAL_CSV_PATH)

    target_df = dataframe[dataframe.apply(needs_kakao_enrich, axis=1)].copy()

    save_dataframe_csv(target_df, KAKAO_TARGET_CSV_PATH)
    save_json(
        target_df.where(pd.notnull(target_df), None).to_dict(orient="records"),
        KAKAO_TARGET_JSON_PATH,
    )

    print(f"[SUCCESS] 카카오 보강 대상 추출 완료: {len(target_df)}건")
    return target_df


def enrich_discount_stores_with_kakao():
    """카카오 API로 위도/경도가 비어있는 데이터만 보강 후 final 파일에 반영"""
    original_df = pd.read_csv(FINAL_CSV_PATH)

    try:
        target_df = pd.read_csv(KAKAO_TARGET_CSV_PATH)
    except FileNotFoundError:
        target_df = extract_kakao_target_stores()

    cache = {}

    print(f"[INFO] 카카오 보강 대상: {len(target_df)}건")

    for original_index, row in target_df.iterrows():
        if original_index % 50 == 0:
            print(f"[INFO] 진행률: {original_index}/{len(target_df)}")

        address = _pick_address(row)
        name = str(row.get("name", "")).strip()

        result = _get_kakao_result(address, name, cache)

        if result:
            original_df.at[original_index, "latitude"] = result.get("y")
            original_df.at[original_index, "longitude"] = result.get("x")

            road_address = _extract_road_address(result)
            if (
                is_empty(original_df.at[original_index, "road_address"])
                and road_address
            ):
                original_df.at[original_index, "road_address"] = road_address

            print(f"[UPDATE] {name} → latitude/longitude")
        else:
            print(f"[SKIP] 카카오 결과 없음: {name} {address}")

        time.sleep(0.4)

    save_dataframe_csv(original_df, FINAL_CSV_PATH)
    save_json(
        original_df.where(pd.notnull(original_df), None).to_dict(orient="records"),
        FINAL_JSON_PATH,
    )

    print(f"[SUCCESS] 카카오 보강 완료: {len(original_df)}건")
    return original_df


def _pick_address(row) -> str:
    """도로명주소가 있으면 우선 사용하고 없으면 지번주소 사용"""
    road_address = str(row.get("road_address", "")).strip()
    address = str(row.get("address", "")).strip()

    if road_address and road_address.lower() != "nan":
        return road_address

    if address and address.lower() != "nan":
        return address

    return ""


def _get_kakao_result(address, name, cache):
    """캐싱 + fallback 포함 카카오 검색"""
    if not address:
        return None

    key = f"{address}_{name}"

    if key in cache:
        return cache[key]

    address_result = search_address(address)

    if address_result:
        documents = address_result.get("documents", [])
        if documents:
            cache[key] = documents[0]
            return documents[0]

    keyword_query = f"{address} {name}".strip()
    keyword_result = search_keyword(keyword_query)

    if keyword_result:
        documents = keyword_result.get("documents", [])
        if documents:
            cache[key] = documents[0]
            return documents[0]

    cache[key] = None
    return None


def _extract_road_address(result) -> str:
    """카카오 응답에서 도로명주소 추출"""
    road_address = result.get("road_address", {})

    if isinstance(road_address, dict):
        return str(road_address.get("address_name", "")).strip()

    return str(result.get("road_address_name", "")).strip()
