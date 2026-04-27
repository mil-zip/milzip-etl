import xml.etree.ElementTree as ET

import requests

from src.config.settings import DATA_GO_KR_SERVICE_KEY, MMA_NARASARANG_API_URL
from src.utils.api_utils import mask_sensitive_text


def fetch_mma_narasarang_api(page_no=1, num_of_rows=100):
    """병무청 나라사랑가게 OpenAPI XML 데이터를 수집하는 함수"""
    params = {
        "serviceKey": DATA_GO_KR_SERVICE_KEY,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
    }

    try:
        response = requests.get(MMA_NARASARANG_API_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        masked_error = mask_sensitive_text(str(error))
        raise RuntimeError(f"병무청 OpenAPI 요청 실패: {masked_error}")

    return _xml_to_dict_list(response.text)


def _xml_to_dict_list(xml_text):
    """XML 응답에서 item 목록을 dict 리스트로 변환하는 함수"""
    root = ET.fromstring(xml_text)
    items = []

    for item in root.findall(".//item"):
        row = {}
        for child in item:
            row[child.tag] = child.text or ""
        items.append(row)

    return items
