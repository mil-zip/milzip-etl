import pandas as pd

from src.utils.address_utils import normalize_korean_address

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


def normalize_yeongcheon_open_api(raw_data):
    """영천시 OpenAPI 데이터를 공통 스키마로 변환하는 함수"""
    items = _extract_items(raw_data)
    rows = []

    for item in items:
        rows.append(
            {
                "name": _pick(item, ["storeNm"]),
                "category": "",
                "business_type": "",
                "address": normalize_korean_address(_pick(item, ["addr"])),
                "road_address": "",
                "phone": _pick(item, ["tel"]),
                "open_time": "",
                "close_time": "",
                "closed_day": "",
                "main_menu": "",
                "discount_info": "",
                "latitude": None,
                "longitude": None,
                "source": "yeongcheon_open_api",
                "source_region": "경상북도 영천시",
                "data_base_date": "",
            }
        )

    dataframe = pd.DataFrame(rows, columns=COMMON_COLUMNS)
    return _remove_empty_name_rows(dataframe)


def normalize_mma_narasarang_api(raw_data):
    """병무청 나라사랑가게 API 데이터를 공통 스키마로 변환하는 함수"""
    items = _extract_items(raw_data)
    rows = []

    for item in items:
        rows.append(
            {
                "name": _pick(item, ["udaeGgm"]),
                "category": _pick(item, ["gtcdNm"]),
                "business_type": "",
                "address": normalize_korean_address(_pick(item, ["juso"])),
                "road_address": "",
                "phone": _pick(item, ["udgigwanTelno"]),
                "open_time": "",
                "close_time": "",
                "closed_day": "",
                "main_menu": "",
                "discount_info": "",
                "latitude": None,
                "longitude": None,
                "source": "mma_narasarang_api",
                "source_region": "",
                "data_base_date": "",
            }
        )

    dataframe = pd.DataFrame(rows, columns=COMMON_COLUMNS)
    return _remove_empty_name_rows(dataframe)


def _extract_items(raw_data):
    """응답 데이터에서 item 목록을 추출하는 함수"""
    if isinstance(raw_data, list):
        return raw_data

    candidates = [
        raw_data.get("response", {}).get("body", {}).get("items", {}).get("item"),
        raw_data.get("body", {}).get("items", {}).get("item"),
        (
            raw_data.get("items", {}).get("item")
            if isinstance(raw_data.get("items"), dict)
            else None
        ),
        raw_data.get("items"),
        raw_data.get("data"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            return [candidate]

    return []


def _pick(item, keys):
    """여러 후보 키 중 존재하는 값을 반환하는 함수"""
    for key in keys:
        value = item.get(key)

        if value is not None and str(value).strip() != "":
            return str(value).strip()

    return ""


def _remove_empty_name_rows(dataframe):
    """업소명이 비어있는 행을 제거하는 함수"""
    return dataframe[dataframe["name"].astype(str).str.strip() != ""].reset_index(
        drop=True
    )
