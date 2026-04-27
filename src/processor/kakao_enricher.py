import time

import pandas as pd

from src.api.kakao_local_api import search_address, search_keyword


def enrich_discount_stores_with_kakao():
    """카카오 API를 이용해 위경도 보강"""

    df = pd.read_csv("data/processed/final_discount_stores.csv")

    # 이미 좌표 있는 데이터는 스킵
    df = df[df["latitude"].isna() | df["longitude"].isna()].reset_index(drop=True)

    cache = {}
    results = []

    for i, row in df.iterrows():
        if i % 50 == 0:
            print(f"[INFO] 진행률: {i}/{len(df)}")

        address = str(row.get("address", "")).strip()
        name = str(row.get("name", "")).strip()

        try:
            result = _get_kakao_result(address, name, cache)

            if result:
                row["latitude"] = result.get("y")
                row["longitude"] = result.get("x")

        except RuntimeError:
            print("🚨 카카오 API limit 걸림 → 중단")
            break

        results.append(row)

        # rate limit
        time.sleep(0.4)

    enriched_df = pd.DataFrame(results)

    enriched_df.to_csv("data/processed/enriched_discount_stores.csv", index=False)

    return enriched_df


def _get_kakao_result(address, name, cache):
    """캐싱 + fallback 포함 카카오 검색"""

    if not address:
        return None

    key = f"{address}_{name}"

    # 캐싱
    if key in cache:
        return cache[key]

    # 주소 검색
    address_result = search_address(address)

    if address_result:
        documents = address_result.get("documents", [])
        if documents:
            cache[key] = documents[0]
            return documents[0]

    # 키워드 검색 fallback
    keyword_query = f"{address} {name}".strip()
    keyword_result = search_keyword(keyword_query)

    if keyword_result:
        documents = keyword_result.get("documents", [])
        if documents:
            cache[key] = documents[0]
            return documents[0]

    cache[key] = None
    return None
