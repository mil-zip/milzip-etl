from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.utils.file_utils import (read_csv_with_encoding, save_dataframe_csv,
                                  save_json)

COMMON_COLUMNS = [
    "name",
    "category",
    "business_type",
    "address",
    "road_address",
    "phone",
    "open_time",
    "close_time",
    "closed_day",
    "main_menu",
    "discount_info",
    "latitude",
    "longitude",
    "source",
    "source_region",
    "data_base_date",
]

COLUMN_ALIASES = {
    "name": ["상호", "상호명", "업소명", "사업장명", "가맹점명", "업체명"],
    "category": ["업종", "업종명", "분류", "카테고리"],
    "business_type": ["업태", "업태명"],
    "address": ["주소", "사업장 주소", "소재지주소", "지번주소", "소재지"],
    "road_address": ["소재지도로명주소", "도로명주소", "도로명 주소"],
    "phone": ["전화번호", "연락처", "업소전화번호"],
    "open_time": ["영업시작시간", "영업 시작시간", "시작시간", "영업시간시작"],
    "close_time": ["영업종료시간", "영업 종료시간", "종료시간", "영업시간종료"],
    "closed_day": ["휴무", "휴무일", "휴일", "정기휴무"],
    "main_menu": ["주메뉴", "대표메뉴", "메뉴"],
    "discount_info": ["할인내용", "할인정보", "할인 정보", "혜택내용", "비고"],
    "latitude": ["위도", "lat", "LAT"],
    "longitude": ["경도", "lng", "LNG", "lon"],
    "data_base_date": ["데이터기준일", "데이터기준일자", "기준일자"],
}


def _find_column(dataframe: pd.DataFrame, candidates: list) -> Optional[str]:
    """후보 컬럼명 중 실제 DataFrame에 존재하는 컬럼을 찾는 함수"""
    normalized_columns = {str(column).strip(): column for column in dataframe.columns}

    for candidate in candidates:
        if candidate in normalized_columns:
            return normalized_columns[candidate]

    return None


def _get_value(row: pd.Series, column_name: Optional[str]) -> Any:
    """행에서 값을 안전하게 가져오는 함수"""
    if column_name is None:
        return ""

    value = row.get(column_name, "")

    if pd.isna(value):
        return ""

    return str(value).strip()


def _to_float(value: Any) -> Optional[float]:
    """값을 float 타입으로 변환하는 함수"""
    if value == "" or pd.isna(value):
        return None

    try:
        return float(value)
    except ValueError:
        return None


def normalize_discount_store_dataframe(
    dataframe: pd.DataFrame,
    source: str,
    source_region: str,
) -> pd.DataFrame:
    """할인업소 데이터를 공통 컬럼 구조로 정규화하는 함수"""
    column_map = {
        common_column: _find_column(dataframe, aliases)
        for common_column, aliases in COLUMN_ALIASES.items()
    }

    normalized_rows = []

    for _, row in dataframe.iterrows():
        normalized_rows.append(
            {
                "name": _get_value(row, column_map["name"]),
                "category": _get_value(row, column_map["category"]),
                "business_type": _get_value(row, column_map["business_type"]),
                "address": _get_value(row, column_map["address"]),
                "road_address": _get_value(row, column_map["road_address"]),
                "phone": _get_value(row, column_map["phone"]),
                "open_time": _get_value(row, column_map["open_time"]),
                "close_time": _get_value(row, column_map["close_time"]),
                "closed_day": _get_value(row, column_map["closed_day"]),
                "main_menu": _get_value(row, column_map["main_menu"]),
                "discount_info": _get_value(row, column_map["discount_info"]),
                "latitude": _to_float(_get_value(row, column_map["latitude"])),
                "longitude": _to_float(_get_value(row, column_map["longitude"])),
                "source": source,
                "source_region": source_region,
                "data_base_date": _get_value(row, column_map["data_base_date"]),
            }
        )

    return pd.DataFrame(normalized_rows, columns=COMMON_COLUMNS)


def normalize_all_raw_csv() -> pd.DataFrame:
    """raw CSV 파일들을 읽어 하나의 정규화 데이터로 병합하는 함수"""
    source_region_map = {
        "pocheon_file": "경기도 포천시",
        "paju_file": "경기도 파주시",
    }

    normalized_dataframes = []

    for source_id, source_region in source_region_map.items():
        file_path = Path(f"data/raw/{source_id}.csv")

        if not file_path.exists():
            print(f"[SKIP] raw CSV 없음: {file_path}")
            continue

        dataframe = read_csv_with_encoding(file_path)
        normalized = normalize_discount_store_dataframe(
            dataframe=dataframe,
            source=source_id,
            source_region=source_region,
        )
        normalized_dataframes.append(normalized)

    if not normalized_dataframes:
        raise FileNotFoundError("정규화할 raw CSV 파일이 없습니다.")

    merged = pd.concat(normalized_dataframes, ignore_index=True)
    merged = remove_empty_and_duplicate_stores(merged)

    save_dataframe_csv(merged, "data/processed/discount_stores.csv")
    save_json(
        merged.where(pd.notnull(merged), None).to_dict(orient="records"),
        "data/processed/discount_stores.json",
    )

    print(f"[SUCCESS] processed 데이터 저장 완료: {len(merged)}건")
    return merged


def remove_empty_and_duplicate_stores(dataframe: pd.DataFrame) -> pd.DataFrame:
    """빈 업소명 데이터와 중복 업소 데이터를 제거하는 함수"""
    dataframe = dataframe.copy()
    dataframe = dataframe[dataframe["name"].astype(str).str.strip() != ""]

    dataframe["duplicate_key"] = (
        dataframe["name"].astype(str).str.strip()
        + "_"
        + dataframe["address"].astype(str).str.strip()
        + "_"
        + dataframe["road_address"].astype(str).str.strip()
    )

    dataframe = dataframe.drop_duplicates(subset=["duplicate_key"])
    dataframe = dataframe.drop(columns=["duplicate_key"])

    return dataframe.reset_index(drop=True)
