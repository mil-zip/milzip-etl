import requests

from src.config.settings import DATA_GO_KR_SERVICE_KEY, YEONGCHEON_API_URL
from src.utils.api_utils import mask_sensitive_text


def fetch_yeongcheon_open_api(page_no=1, num_of_rows=100):
    """영천시 군장병 할인업소 OpenAPI 데이터를 수집하는 함수"""
    params = {
        "serviceKey": DATA_GO_KR_SERVICE_KEY,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "type": "json",
    }

    try:
        response = requests.get(YEONGCHEON_API_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        masked_error = mask_sensitive_text(str(error))
        raise RuntimeError(f"영천시 OpenAPI 요청 실패: {masked_error}")

    return response.json()
