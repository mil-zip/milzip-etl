from pathlib import Path

import pandas as pd
import requests

from src.api.discount_store_sources import DISCOUNT_STORE_SOURCES, PublicDataSource
from src.utils.file_utils import save_dataframe_csv, save_json


def fetch_csv_source(source: PublicDataSource) -> pd.DataFrame:
    if not source.csv_url:
        raise ValueError(f"{source.source_id}의 csv_url이 설정되지 않았습니다.")

    response = requests.get(source.csv_url, timeout=15)
    response.raise_for_status()

    raw_file_path = Path(f"data/raw/{source.source_id}.csv")
    raw_file_path.parent.mkdir(parents=True, exist_ok=True)
    raw_file_path.write_bytes(response.content)

    dataframe = pd.read_csv(raw_file_path, encoding="utf-8-sig")
    print(f"[SUCCESS] {source.name} CSV 수집 완료: {len(dataframe)}건")

    return dataframe


def fetch_json_source(source: PublicDataSource) -> dict:
    if not source.json_url:
        raise ValueError(f"{source.source_id}의 json_url이 설정되지 않았습니다.")

    response = requests.get(source.json_url, timeout=15)
    response.raise_for_status()

    data = response.json()
    save_json(data, f"data/raw/{source.source_id}.json")

    print(f"[SUCCESS] {source.name} JSON 수집 완료")
    return data


def fetch_all_csv_sources() -> dict[str, pd.DataFrame]:
    result = {}

    for source in DISCOUNT_STORE_SOURCES:
        if not source.csv_url:
            print(f"[SKIP] {source.name}: csv_url 미설정")
            continue

        result[source.source_id] = fetch_csv_source(source)

    return result


def save_manual_csv_to_raw(source_id: str, csv_path: str) -> pd.DataFrame:
    """
    공공데이터포털에서 CSV를 직접 다운로드한 뒤
    data/raw/에 표준 파일명으로 저장할 때 사용.
    """
    dataframe = pd.read_csv(csv_path, encoding="utf-8-sig")
    output_path = f"data/raw/{source_id}.csv"
    save_dataframe_csv(dataframe, output_path)

    print(f"[SUCCESS] 수동 CSV 저장 완료: {output_path}, {len(dataframe)}건")
    return dataframe
