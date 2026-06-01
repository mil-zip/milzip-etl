from typing import Optional
import requests

from src.config.settings import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NAVER_LOCAL_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"


def search_local(query: str) -> Optional[dict]:
    """네이버 지역 검색 API로 장소 검색 후 첫 번째 결과 반환"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return None

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": 1, "sort": "comment"}

    try:
        response = requests.get(
            NAVER_LOCAL_SEARCH_URL, headers=headers, params=params, timeout=10
        )
        if response.status_code != 200:
            return None

        items = response.json().get("items", [])
        return items[0] if items else None

    except requests.exceptions.RequestException:
        return None
