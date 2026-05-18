import time

import pandas as pd
from tqdm import tqdm

from src.crawler.naver_place_crawler import get_naver_place_info
from src.utils.file_utils import save_dataframe_csv, save_json

FINAL_CSV_PATH = "data/processed/final_discount_stores.csv"
FINAL_JSON_PATH = "data/processed/final_discount_stores.json"

NAVER_TARGET_CSV_PATH = "data/processed/naver_target_stores.csv"
NAVER_TARGET_JSON_PATH = "data/processed/naver_target_stores.json"

BATCH_SIZE = 5

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


def extract_naver_target_stores() -> pd.DataFrame:
    """final 데이터에서 네이버 보강 대상만 추출"""
    dataframe = pd.read_csv(FINAL_CSV_PATH)

    target_df = dataframe[dataframe.apply(needs_naver_enrich, axis=1)].copy()
    target_df["enrich_done"] = False
    target_df["enrich_status"] = ""
    target_df["enrich_error"] = ""

    save_dataframe_csv(target_df, NAVER_TARGET_CSV_PATH)
    save_json(
        target_df.where(pd.notnull(target_df), None).to_dict(orient="records"),
        NAVER_TARGET_JSON_PATH,
    )

    print(f"[SUCCESS] 네이버 보강 대상 추출 완료: {len(target_df)}건")
    return target_df


def prepare_target_dataframe(target_df: pd.DataFrame) -> pd.DataFrame:
    target_df = target_df.copy()

    if "enrich_done" not in target_df.columns:
        target_df["enrich_done"] = False

    if "enrich_status" not in target_df.columns:
        target_df["enrich_status"] = ""

    if "enrich_error" not in target_df.columns:
        target_df["enrich_error"] = ""

    target_df["enrich_done"] = target_df["enrich_done"].fillna(False).astype(bool)
    target_df["enrich_status"] = target_df["enrich_status"].astype(str)
    target_df["enrich_error"] = target_df["enrich_error"].astype(str)

    return target_df


def build_naver_query(row) -> str:
    """네이버 검색어 생성"""
    address = (
        row["road_address"] if not is_empty(row["road_address"]) else row["address"]
    )
    return f"{row['name']} {address}"


def enrich_with_naver(
    original_df: pd.DataFrame,
    target_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """naver_target_stores.csv 대상만 네이버로 보강 후 final 데이터에 반영"""
    original_df = original_df.copy()
    target_df = prepare_target_dataframe(target_df)

    pending_df = target_df[~target_df["enrich_done"]].head(BATCH_SIZE)

    print(f"[INFO] 네이버 크롤링 대상: {len(pending_df)}건")

    for original_index, row in tqdm(pending_df.iterrows(), total=len(pending_df)):
        query = build_naver_query(row)

        try:
            result = get_naver_place_info(query)

            if not result:
                print(f"[SKIP] 결과 없음: {query}")
                target_df.at[original_index, "enrich_done"] = True
                target_df.at[original_index, "enrich_status"] = "no_result"
                continue

            updated_fields = []

            for column in TARGET_COLUMNS:
                if is_empty(row[column]) and result.get(column):
                    original_df.at[original_index, column] = result[column]
                    target_df.at[original_index, column] = result[column]
                    updated_fields.append(column)

            target_df.at[original_index, "enrich_done"] = True

            if updated_fields:
                target_df.at[original_index, "enrich_status"] = "updated"
                print(f"[UPDATE] {row['name']} → {updated_fields}")
            else:
                target_df.at[original_index, "enrich_status"] = "no_change"
                print(f"[NO CHANGE] {row['name']}")

            time.sleep(3)

        except Exception as error:
            print(f"[ERROR] {query} → {error}")
            target_df.at[original_index, "enrich_status"] = "error"
            target_df.at[original_index, "enrich_error"] = str(error)
            continue

    return original_df, target_df


def run_naver_target_extract_pipeline():
    """네이버 보강 대상 추출만 실행"""
    return extract_naver_target_stores()


def run_naver_enrich_pipeline():
    """naver_target_stores.csv를 기준으로 네이버 크롤링 후 final 파일에 반영"""
    print("🟢 네이버 플레이스 정보 보강 시작")

    original_df = pd.read_csv(FINAL_CSV_PATH)

    try:
        target_df = pd.read_csv(NAVER_TARGET_CSV_PATH)
    except FileNotFoundError:
        target_df = extract_naver_target_stores()

    enriched, updated_target = enrich_with_naver(original_df, target_df)

    save_dataframe_csv(enriched, FINAL_CSV_PATH)
    save_json(
        enriched.where(pd.notnull(enriched), None).to_dict(orient="records"),
        FINAL_JSON_PATH,
    )

    save_dataframe_csv(updated_target, NAVER_TARGET_CSV_PATH)
    save_json(
        updated_target.where(pd.notnull(updated_target), None).to_dict(
            orient="records"
        ),
        NAVER_TARGET_JSON_PATH,
    )

    print(f"✅ 네이버 보강 완료: {len(enriched)}건")
    return enriched
