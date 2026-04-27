import time

import requests

from src.config.settings import KAKAO_REST_API_KEY
from src.utils.api_utils import mask_sensitive_text

KAKAO_ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def search_address(address):
    """주소로 카카오 로컬 API를 검색하는 함수"""
    if not address:
        return None

    params = {"query": address}
    return _request_kakao_api(KAKAO_ADDRESS_SEARCH_URL, params)


def search_keyword(query):
    """키워드로 카카오 장소 검색 API를 검색하는 함수"""
    if not query:
        return None

    params = {
        "query": query,
        "size": 1,
    }
    return _request_kakao_api(KAKAO_KEYWORD_SEARCH_URL, params)


def _request_kakao_api(url, params):
    """카카오 API 공통 요청 함수"""
    if not KAKAO_REST_API_KEY:
        raise RuntimeError("KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    headers = {
        "Authorization": f"KakaoAK {KAKAO_REST_API_KEY}",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code != 200:
            error_body = _safe_json(response)

            if error_body.get("code") == -10:
                print("🚨 카카오 API limit → 해당 요청 skip")
                return None

            print("[WARN] 카카오 API 요청 실패")
            print(f"status: {response.status_code}")
            print(f"body: {mask_sensitive_text(response.text)}")
            print(f"url: {mask_sensitive_text(response.url)}")
            return None

        time.sleep(0.3)
        return response.json()

    except requests.exceptions.RequestException as error:
        print(f"[WARN] 카카오 API 요청 실패: {mask_sensitive_text(str(error))}")
        return None


def _safe_json(response):
    """응답 본문을 안전하게 JSON으로 변환하는 함수"""
    try:
        return response.json()
    except ValueError:
        return {}
