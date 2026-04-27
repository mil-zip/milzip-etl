import time

import pandas as pd
from tqdm import tqdm

from src.crawler.naver_place_crawler import get_naver_place_info
from src.utils.file_utils import save_dataframe_csv, save_json

FINAL_CSV_PATH = "data/processed/final_discount_stores.csv"
FINAL_JSON_PATH = "data/processed/final_discount_stores.json"

TARGET_COLUMNS = [
    "phone",
    "open_time",
    "close_time",
    "closed_day",
    "main_menu",
]


def is_empty(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def needs_naver_enrich(row) -> bool:
    return any(is_empty(row[column]) for column in TARGET_COLUMNS)


def enrich_with_naver(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe = dataframe.copy()

    target_df = dataframe[dataframe.apply(needs_naver_enrich, axis=1)]

    # 테스트용. 전체 돌릴 때는 이 줄 삭제하거나 숫자 늘리기
    target_df = target_df.head(10)

    print(f"[INFO] 네이버 크롤링 대상: {len(target_df)}건")

    for idx in tqdm(target_df.index):
        row = dataframe.loc[idx]
        query = f"{row['name']} {row['address']}"

        try:
            result = get_naver_place_info(query)

            if not result:
                print(f"[SKIP] 결과 없음: {query}")
                continue

            updated_fields = []

            for column in TARGET_COLUMNS:
                if is_empty(row[column]) and result.get(column):
                    dataframe.at[idx, column] = result[column]
                    updated_fields.append(column)

            if updated_fields:
                print(f"[UPDATE] {row['name']} → {updated_fields}")
            else:
                print(f"[NO CHANGE] {row['name']}")

            time.sleep(3)

        except Exception as error:
            print(f"[ERROR] {query} → {error}")
            continue

    return dataframe


def run_naver_enrich_pipeline():
    print("🟢 네이버 플레이스 정보 보강 시작")

    df = pd.read_csv(FINAL_CSV_PATH)
    enriched = enrich_with_naver(df)

    save_dataframe_csv(enriched, FINAL_CSV_PATH)
    save_json(
        enriched.where(pd.notnull(enriched), None).to_dict(orient="records"),
        FINAL_JSON_PATH,
    )

    print(f"✅ 네이버 보강 완료: {len(enriched)}건")
    return enriched
