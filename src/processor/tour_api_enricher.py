import time

import pandas as pd
from tqdm import tqdm

from src.api.tour_api import get_tour_detail_intro, search_tour_keyword
from src.utils.file_utils import save_dataframe_csv, save_json

FINAL_CSV_PATH = "data/processed/final_discount_stores.csv"
FINAL_JSON_PATH = "data/processed/final_discount_stores.json"

TOUR_TARGET_CSV_PATH = "data/processed/tour_api_target_stores.csv"
TOUR_TARGET_JSON_PATH = "data/processed/tour_api_target_stores.json"

TARGET_COLUMNS = [
    "phone",
    "open_time",
    "close_time",
    "closed_day",
    "main_menu",
]


def is_empty(value) -> bool:
    """값이 비어있는지 확인하는 함수"""
    return pd.isna(value) or str(value).strip() == ""


def needs_tour_api_enrich(row) -> bool:
    """TourAPI 보강 대상인지 확인하는 함수"""
    return any(is_empty(row[column]) for column in TARGET_COLUMNS)


def extract_tour_api_target_stores() -> pd.DataFrame:
    """final 데이터에서 TourAPI 보강 대상만 추출하는 함수"""
    dataframe = pd.read_csv(FINAL_CSV_PATH)

    target_df = dataframe[dataframe.apply(needs_tour_api_enrich, axis=1)].copy()

    save_dataframe_csv(target_df, TOUR_TARGET_CSV_PATH)
    save_json(
        target_df.where(pd.notnull(target_df), None).to_dict(orient="records"),
        TOUR_TARGET_JSON_PATH,
    )

    print(f"[SUCCESS] TourAPI 보강 대상 추출 완료: {len(target_df)}건")
    return target_df


def guess_content_type_id(row) -> str:
    """업종 정보를 기반으로 TourAPI contentTypeId를 추정하는 함수"""
    text = f"{row.get('category', '')} {row.get('business_type', '')}"

    if any(keyword in text for keyword in ["숙박", "펜션", "모텔", "호텔", "민박"]):
        return "32"

    return "39"


def build_search_keyword(row) -> str:
    """TourAPI 검색 키워드 생성"""
    name = str(row.get("name", "")).strip()
    region = str(row.get("source_region", "")).strip()

    if region:
        return f"{name} {region}"

    return name


def enrich_tour_api_target_stores() -> pd.DataFrame:
    """추출된 대상 파일을 TourAPI로 보강한 뒤 final 파일에 다시 반영"""
    original_df = pd.read_csv(FINAL_CSV_PATH)

    try:
        target_df = pd.read_csv(TOUR_TARGET_CSV_PATH)
    except FileNotFoundError:
        target_df = extract_tour_api_target_stores()

    # 테스트용. 전체 돌릴 때는 삭제하거나 숫자 늘리기
    # target_df = target_df.head(20)

    print(f"[INFO] TourAPI 보강 실행 대상: {len(target_df)}건")

    for idx, row in tqdm(target_df.iterrows(), total=len(target_df)):
        content_type_id = guess_content_type_id(row)
        keyword = build_search_keyword(row)

        try:
            search_results = search_tour_keyword(keyword, content_type_id)

            if not search_results:
                print(f"[SKIP] TourAPI 검색 결과 없음: {keyword}")
                continue

            content_id = str(search_results[0].get("contentid", "")).strip()

            if not content_id:
                print(f"[SKIP] contentid 없음: {keyword}")
                continue

            detail_items = get_tour_detail_intro(content_id, content_type_id)

            if not detail_items:
                print(f"[SKIP] detailIntro2 결과 없음: {keyword}")
                continue

            detail = detail_items[0]
            updated_fields = []

            original_index = row.name

            if content_type_id == "39":
                updated_fields += apply_food_detail(
                    original_df, original_index, row, detail
                )
            elif content_type_id == "32":
                updated_fields += apply_lodging_detail(
                    original_df, original_index, row, detail
                )

            if updated_fields:
                print(f"[UPDATE] {row['name']} → {updated_fields}")
            else:
                print(f"[NO CHANGE] {row['name']}")

            time.sleep(0.3)

        except RuntimeError as error:
            print(f"[ERROR] {keyword} → {error}")
            continue

    save_dataframe_csv(original_df, FINAL_CSV_PATH)
    save_json(
        original_df.where(pd.notnull(original_df), None).to_dict(orient="records"),
        FINAL_JSON_PATH,
    )

    print(f"[SUCCESS] TourAPI 보강 결과 final 파일 반영 완료: {len(original_df)}건")
    return original_df


def apply_food_detail(dataframe, idx, row, detail) -> list:
    """음식점 상세정보를 기존 빈 컬럼에 반영"""
    updated_fields = []

    open_time = clean_html(detail.get("opentimefood", ""))
    closed_day = clean_html(detail.get("restdatefood", ""))
    first_menu = clean_html(detail.get("firstmenu", ""))
    treat_menu = clean_html(detail.get("treatmenu", ""))

    if is_empty(row["open_time"]) and open_time:
        dataframe.at[idx, "open_time"] = open_time
        updated_fields.append("open_time")

    if is_empty(row["closed_day"]) and closed_day:
        dataframe.at[idx, "closed_day"] = closed_day
        updated_fields.append("closed_day")

    menu = merge_menu(first_menu, treat_menu)

    if is_empty(row["main_menu"]) and menu:
        dataframe.at[idx, "main_menu"] = menu
        updated_fields.append("main_menu")

    return updated_fields


def apply_lodging_detail(dataframe, idx, row, detail) -> list:
    """숙박 상세정보를 기존 빈 컬럼에 반영"""
    updated_fields = []

    checkin_time = clean_html(detail.get("checkintime", ""))
    checkout_time = clean_html(detail.get("checkouttime", ""))

    if is_empty(row["open_time"]) and checkin_time:
        dataframe.at[idx, "open_time"] = checkin_time
        updated_fields.append("open_time")

    if is_empty(row["close_time"]) and checkout_time:
        dataframe.at[idx, "close_time"] = checkout_time
        updated_fields.append("close_time")

    return updated_fields


def merge_menu(first_menu: str, treat_menu: str) -> str:
    values = []

    if first_menu:
        values.append(first_menu)

    if treat_menu and treat_menu != first_menu:
        values.append(treat_menu)

    return " / ".join(values)


def clean_html(value: str) -> str:
    if not value:
        return ""

    import re

    value = str(value)
    value = value.replace("<br>", " ")
    value = value.replace("<br/>", " ")
    value = value.replace("<br />", " ")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def run_tour_target_extract_pipeline():
    """TourAPI 대상 추출만 실행"""
    return extract_tour_api_target_stores()


def run_tour_api_enrich_pipeline():
    """TourAPI 보강 실행"""
    return enrich_tour_api_target_stores()
