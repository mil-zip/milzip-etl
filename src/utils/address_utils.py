import re


def normalize_korean_address(address):
    """카카오 검색 성공률을 높이기 위해 한국 주소 문자열을 정리하는 함수"""
    if not address:
        return ""

    address = str(address).strip()

    address = re.sub(r"\([^)]*\)", "", address)
    address = address.replace(")", "")
    address = address.replace("- ", "-")
    address = re.sub(r"\s+", " ", address)

    address = _split_sido(address)
    address = _split_sigungu(address)
    address = _split_eup_myeon_dong(address)
    address = _split_road_address(address)

    address = re.sub(r"(\d+)(층)", r"\1 \2", address)
    address = re.sub(r"(\d+)(호)", r"\1 \2", address)
    address = re.sub(r"\s+", " ", address)

    return address.strip()


def _split_sido(address):
    sido_patterns = [
        "서울특별시",
        "부산광역시",
        "대구광역시",
        "인천광역시",
        "광주광역시",
        "대전광역시",
        "울산광역시",
        "세종특별자치시",
        "경기도",
        "강원특별자치도",
        "충청북도",
        "충청남도",
        "전북특별자치도",
        "전라남도",
        "경상북도",
        "경상남도",
        "제주특별자치도",
    ]

    for sido in sido_patterns:
        address = address.replace(sido, f"{sido} ")

    return address


def _split_sigungu(address):
    address = re.sub(r"([가-힣]+시)\s*([가-힣]+구)", r"\1 \2", address)
    address = re.sub(r"([가-힣]+도)\s*([가-힣]+시)", r"\1 \2", address)
    address = re.sub(r"([가-힣]+도)\s*([가-힣]+군)", r"\1 \2", address)
    address = re.sub(r"([가-힣]+구)([가-힣0-9]+[로길])", r"\1 \2", address)
    address = re.sub(r"([가-힣]+시)([가-힣0-9]+[로길])", r"\1 \2", address)
    address = re.sub(r"([가-힣]+군)([가-힣0-9]+[로길])", r"\1 \2", address)

    return address


def _split_eup_myeon_dong(address):
    address = re.sub(r"([가-힣]+읍)([가-힣0-9]+[로길])", r"\1 \2", address)
    address = re.sub(r"([가-힣]+면)([가-힣0-9]+[로길])", r"\1 \2", address)
    address = re.sub(r"([가-힣]+동)([가-힣0-9]+[로길])", r"\1 \2", address)

    return address


def _split_road_address(address):
    address = re.sub(r"([가-힣0-9]+대로)(\d)", r"\1 \2", address)
    address = re.sub(r"([가-힣0-9]+로)(\d)", r"\1 \2", address)
    address = re.sub(r"([가-힣0-9]+길)(\d)", r"\1 \2", address)
    address = re.sub(r"(\d+)(번길)(\d+)", r"\1\2 \3", address)

    return address
