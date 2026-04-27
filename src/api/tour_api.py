import requests

from src.config.settings import DATA_GO_KR_SERVICE_KEY, TOUR_API_BASE_URL
from src.utils.api_utils import mask_sensitive_text


def search_tour_keyword(keyword: str, content_type_id: str):
    """TourAPI 키워드 검색으로 contentid를 찾는 함수"""
    if not keyword:
        return []

    params = {
        "serviceKey": DATA_GO_KR_SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "milzip",
        "_type": "json",
        "numOfRows": 5,
        "pageNo": 1,
        "keyword": keyword,
        "contentTypeId": content_type_id,
    }

    return _request_tour_api("/searchKeyword2", params)


def get_tour_detail_intro(content_id: str, content_type_id: str):
    """TourAPI 상세 소개정보를 조회하는 함수"""
    params = {
        "serviceKey": DATA_GO_KR_SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "milzip",
        "_type": "json",
        "contentId": content_id,
        "contentTypeId": content_type_id,
    }

    return _request_tour_api("/detailIntro2", params)


def _request_tour_api(path: str, params: dict):
    """TourAPI 공통 요청 함수"""
    if not DATA_GO_KR_SERVICE_KEY:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY가 설정되지 않았습니다.")

    url = f"{TOUR_API_BASE_URL}{path}"

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as error:
        print(f"[WARN] TourAPI 요청 실패: {mask_sensitive_text(str(error))}")
        return []
    except ValueError:
        print("[WARN] TourAPI JSON 파싱 실패")
        return []

    return _extract_items(data)


def _extract_items(data):
    """TourAPI 응답에서 item 목록 추출"""
    if not isinstance(data, dict):
        return []

    response = data.get("response", {})
    if not isinstance(response, dict):
        return []

    body = response.get("body", {})
    if not isinstance(body, dict):
        return []

    items = body.get("items", {})
    if not isinstance(items, dict):
        return []

    item = items.get("item", [])

    if isinstance(item, list):
        return item

    if isinstance(item, dict):
        return [item]

    return []
