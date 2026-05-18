from enum import Enum


class StoreCategory(str, Enum):
    FOOD = "FOOD"
    CAFE = "CAFE"
    LEISURE = "LEISURE"
    ACCOMMODATION = "ACCOMMODATION"
    ETC = "ETC"


_KEYWORD_MAP: list[tuple[StoreCategory, list[str]]] = [
    (
        StoreCategory.FOOD,
        [
            "일반음식점", "한식", "중식", "양식", "일식", "분식", "식당", "갈비", "삼겹살",
            "순대", "냉면", "국밥", "찌개", "탕", "구이", "치킨", "피자", "햄버거",
            "족발", "보쌈", "회", "초밥", "해산물", "곱창", "뼈", "닭", "오리",
            "부대찌개", "감자탕", "짜장", "짬뽕", "도시락", "뷔페", "음식",
        ],
    ),
    (
        StoreCategory.CAFE,
        [
            "카페", "커피", "제과", "제빵", "베이커리", "빵", "디저트", "케이크",
            "아이스크림", "음료", "휴게음식점", "티", "다원",
        ],
    ),
    (
        StoreCategory.LEISURE,
        [
            "pc방", "PC방", "노래", "당구", "볼링", "영화", "스크린", "게임",
            "스포츠", "수영", "헬스", "피트니스", "골프", "축구", "야구",
            "방탈출", "보드게임", "레저", "여가", "오락",
        ],
    ),
    (
        StoreCategory.ACCOMMODATION,
        [
            "숙박", "모텔", "호텔", "여관", "민박", "펜션", "캠핑", "게스트하우스",
            "리조트", "콘도", "사우나", "목욕",
        ],
    ),
]


def map_category(raw_category: str) -> StoreCategory:
    """한국어 업종 텍스트를 ENUM 카테고리로 변환"""
    if not raw_category:
        return StoreCategory.ETC

    text = raw_category.strip().lower()

    for category, keywords in _KEYWORD_MAP:
        if any(kw.lower() in text for kw in keywords):
            return category

    return StoreCategory.ETC
