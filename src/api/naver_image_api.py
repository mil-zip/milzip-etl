from typing import List

import requests

from src.config.settings import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NAVER_IMAGE_SEARCH_URL = "https://openapi.naver.com/v1/search/image"
DEFAULT_DISPLAY = 5

# 카테고리별 검색 보조 키워드
CATEGORY_KEYWORDS = {
    "FOOD": "맛집",
    "CAFE": "카페",
    "LEISURE": "",
    "ACCOMMODATION": "숙박",
    "ETC": "",
}


def _short_address(address: str) -> str:
    """주소를 시/군/구 단위로 축약 (너무 상세하면 결과 없을 수 있음)
    예: '경기도 포천시 신북면 아트밸리로 42' → '경기도 포천시'
    """
    parts = address.strip().split()
    # 시/군/구 단위까지만 사용 (최대 2개 토큰)
    return " ".join(parts[:2]) if len(parts) >= 2 else address


def build_image_query(name: str, address: str, category: str = "") -> str:
    """이미지 검색 쿼리 구성: 가게명 + 시/구 + 카테고리 키워드"""
    short_addr = _short_address(address)
    keyword = CATEGORY_KEYWORDS.get(category.upper(), "맛집")
    parts = [name, short_addr, keyword]
    return " ".join(p for p in parts if p).strip()


def search_store_images(
    name: str,
    address: str,
    category: str = "",
    display: int = DEFAULT_DISPLAY,
) -> List[str]:
    """매장명 + 주소 + 카테고리 키워드로 네이버 이미지 검색"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 설정되지 않았습니다.")

    query = build_image_query(name, address, category)
    if not query:
        return []

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": display, "sort": "sim"}

    try:
        response = requests.get(
            NAVER_IMAGE_SEARCH_URL, headers=headers, params=params, timeout=10
        )
        if response.status_code != 200:
            return []

        items = response.json().get("items", [])
        return [item["thumbnail"] for item in items if item.get("thumbnail")]

    except requests.exceptions.RequestException:
        return []
