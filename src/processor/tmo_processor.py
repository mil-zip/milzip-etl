"""TMO 데이터 처리 및 좌표 보강

국방부 공공데이터(data/raw/tmo_raw.json)를 읽어
카카오 키워드 검색으로 위도/경도를 보강한 뒤 processed에 저장합니다.
"""
import json
import time
from pathlib import Path
from typing import Optional

from src.api.kakao_local_api import search_keyword
from src.utils.file_utils import save_dataframe_csv, save_json
from src.utils.logger import get_logger

logger = get_logger()

RAW_PATH = Path("data/raw/tmo_raw.json")
OUT_CSV = "data/processed/tmo_list.csv"
OUT_JSON = "data/processed/tmo_list.json"

# 동서울터미널처럼 역이 아닌 경우 별도 검색어 매핑
SEARCH_OVERRIDE = {
    "동서울": "동서울터미널",
    "연무대": "논산훈련소",
}


def _search_station(tmo_nm: str) -> Optional[dict]:
    """카카오 키워드 검색으로 역/터미널 좌표 조회"""
    query = SEARCH_OVERRIDE.get(tmo_nm, f"{tmo_nm}역")
    result = search_keyword(query)
    if result:
        docs = result.get("documents", [])
        if docs:
            return docs[0]
    return None


def run_tmo_pipeline() -> list[dict]:
    with open(RAW_PATH, encoding="utf-8") as f:
        raw_list = json.load(f)

    processed = []

    for item in raw_list:
        tmo_nm = item["tmo_nm"]
        phone = item["gnrltelno"] if item["gnrltelno"] != "없음" else None
        is_mobile = "출장형" in (item.get("etc") or "")

        result = _search_station(tmo_nm)
        latitude = float(result["y"]) if result else None
        longitude = float(result["x"]) if result else None
        address = result.get("address_name") or result.get("road_address_name") if result else None

        processed.append({
            "name": f"{tmo_nm} TMO",
            "phone": phone,
            "weekday_start_time": item["wkday_strtm"] or None,
            "weekday_end_time": item["wkday_endtm"] or None,
            "weekend_start_time": item["wkend_strtm"] or None,
            "weekend_end_time": item["wkend_endtm"] or None,
            "location_description": item["pstnexpln"],
            "note": item["etc"] or None,
            "is_mobile": is_mobile,
            "latitude": latitude,
            "longitude": longitude,
            "address": address,
        })

        status = "✅" if latitude else "⚠️ 좌표 없음"
        logger.info("[TMO] %s %s", tmo_nm, status)
        time.sleep(0.3)

    save_json(processed, OUT_JSON)

    import pandas as pd
    df = pd.DataFrame(processed)
    save_dataframe_csv(df, OUT_CSV)

    success = sum(1 for p in processed if p["latitude"])
    logger.info("✅ TMO 처리 완료: %d건 (좌표 확보 %d건)", len(processed), success)
    return processed
