import re
import ssl
import time
import urllib.parse
import urllib.request
from typing import List, Optional

import pandas as pd
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

logger = get_logger()

_SSL_UNVERIFIED = ssl.create_default_context()
_SSL_UNVERIFIED.check_hostname = False
_SSL_UNVERIFIED.verify_mode = ssl.CERT_NONE


def _fetch(url: str, method: str = "GET", data: Optional[dict] = None, ssl_context=None) -> str:
    encoded = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(
        url,
        data=encoded,
        method=method,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, context=ssl_context, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")


_PROVINCE_PREFIXES = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충청", "전라", "전북", "경상", "제주", "특별자치",
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _full_address(address: str, source_region: str) -> str:
    """주소에 시/도 정보가 없으면 source_region을 앞에 붙여 완전한 주소로 만든다."""
    addr = _clean(address)
    if not addr:
        return addr
    if any(addr.startswith(p) for p in _PROVINCE_PREFIXES):
        return addr
    return f"{source_region} {addr}"


def _extract_discount_rate(discount_info: str) -> Optional[float]:
    """할인내용 문자열에서 숫자 비율(%) 또는 금액(원)을 추출"""
    if not discount_info:
        return None
    pct = re.search(r"(\d+(?:\.\d+)?)\s*%", discount_info)
    if pct:
        return float(pct.group(1))
    won = re.search(r"(\d[\d,]*)\s*원", discount_info)
    if won:
        return float(won.group(1).replace(",", ""))
    return None


def _parse_hours(text: str) -> dict:
    """텍스트에서 영업시간과 휴무일을 추출"""
    result = {"open_time": "", "close_time": "", "closed_day": ""}
    m = re.search(r"(\d{1,2}:\d{2})\s*[-~]\s*(\d{1,2}:\d{2})", text)
    if m:
        result["open_time"] = m.group(1)
        result["close_time"] = m.group(2)
    closed = re.search(r"([월화수목금토일][\w\s]*휴무|연중무휴|매주\s*[월화수목금토일])", text)
    if closed:
        result["closed_day"] = closed.group(0).strip()
    return result


def _make_row(
    name="", category="", address="", phone="",
    main_menu="", discount_info="", open_time="", close_time="",
    closed_day="", source="", source_region="",
) -> dict:
    return {
        "name": _clean(name),
        "category": _clean(category),
        "business_type": "",
        "address": _full_address(address, source_region),
        "road_address": "",
        "phone": _clean(phone),
        "open_time": _clean(open_time),
        "close_time": _clean(close_time),
        "closed_day": _clean(closed_day),
        "main_menu": _clean(main_menu),
        "discount_info": _clean(discount_info),
        "discount_rate": _extract_discount_rate(discount_info),
        "latitude": None,
        "longitude": None,
        "source": source,
        "source_region": source_region,
        "data_base_date": "",
    }


# ==============================
# 동두천시 (ddc.go.kr)
# ==============================
def _parse_ddc_table(soup_table, col_map: dict, category: str, source_region: str) -> List[dict]:
    rows = []
    for tr in soup_table.find_all("tr"):
        cells = [_clean(td.get_text()) for td in tr.find_all("td")]
        if not cells:
            continue
        try:
            name = cells[col_map["name"]] if "name" in col_map else ""
            address = cells[col_map["address"]] if "address" in col_map else ""
            phone = cells[col_map["phone"]] if "phone" in col_map else ""
            main_menu_idx = col_map.get("main_menu")
            main_menu = cells[main_menu_idx] if main_menu_idx is not None and main_menu_idx < len(cells) else ""
            discount_idx = col_map.get("discount", -1)
            discount_raw = cells[discount_idx] if 0 <= discount_idx < len(cells) else ""
            note_idx = col_map.get("note", -1)
            note = cells[note_idx] if 0 <= note_idx < len(cells) else ""
        except IndexError:
            continue
        if not name:
            continue
        hours = _parse_hours(note)
        rows.append(_make_row(
            name=name, category=category, address=address, phone=phone,
            main_menu=main_menu, discount_info=discount_raw,
            open_time=hours["open_time"], close_time=hours["close_time"],
            closed_day=hours["closed_day"],
            source="ddc_web", source_region=source_region,
        ))
    return rows


def scrape_ddc() -> pd.DataFrame:
    """동두천시 군장병 할인업소 크롤링 (ddc.go.kr)"""
    url = "https://www.ddc.go.kr/ddc/contents.do?key=1570"
    source_region = "경기도 동두천시"
    logger.info("[DDC] 크롤링 시작: %s", url)

    html = _fetch(url)
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    # 각 테이블의 컬럼 구조 정의 (헤더 순서 기반)
    # Table 0: 지역, 업소명, 주소, 전화번호, 메뉴, 할인, 비고
    # Table 1: 지역, 업종, 업소명, 주소, 전화번호, 메뉴, 할인, 비고
    # Table 2: 지역, 업소명, 주소, 전화번호, 할인, 비고
    # Table 3: 지역, 업종, 업소명, 주소, 전화번호, 할인, 비고
    # Table 4: 지역, 업종, 업소명, 주소, 전화번호, 할인, 비고
    TABLE_SCHEMAS = [
        {"category": "일반음식점",       "name": 1, "address": 2, "phone": 3, "main_menu": 4, "discount": 5, "note": 6},
        {"category": "휴게음식점/제과점", "name": 2, "address": 3, "phone": 4, "main_menu": 5, "discount": 6, "note": 7},
        {"category": "이미용",           "name": 1, "address": 2, "phone": 3, "main_menu": None, "discount": 4, "note": 5},
        {"category": "목욕장/숙박/기타", "name": 2, "address": 3, "phone": 4, "main_menu": None, "discount": 5, "note": 6},
        {"category": "PC방/노래방/기타", "name": 2, "address": 3, "phone": 4, "main_menu": None, "discount": 5, "note": 6},
    ]

    all_rows = []
    for i, table in enumerate(tables):
        if i >= len(TABLE_SCHEMAS):
            break
        schema = TABLE_SCHEMAS[i]
        rows = _parse_ddc_table(table, schema, schema["category"], source_region)
        all_rows.extend(rows)
        logger.info("[DDC] 테이블 %d (%s): %d건", i + 1, schema["category"], len(rows))

    df = pd.DataFrame(all_rows)
    logger.info("[DDC] 완료: 총 %d건", len(df))
    return df


# ==============================
# 화천군 (ihc.go.kr)
# ==============================
def scrape_ihc() -> pd.DataFrame:
    """화천군 군장병 우대업소 크롤링 (ihc.go.kr)"""
    url = "https://www.ihc.go.kr/www/contents.do?key=2405"
    source_region = "강원특별자치도 화천군"
    logger.info("[IHC] 크롤링 시작: %s", url)

    html = _fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    all_rows = []
    for table in soup.find_all("table"):
        headers = [_clean(th.get_text()) for th in table.find_all("th")]
        # 컬럼 인덱스 찾기
        col_idx = {}
        for i, h in enumerate(headers):
            if "업소명" in h or "우대업소" in h:
                col_idx["name"] = i
            elif "업종" in h:
                col_idx["category"] = i
            elif "주소" in h:
                col_idx["address"] = i
            elif "전화" in h or "연락처" in h:
                col_idx["phone"] = i

        if "name" not in col_idx:
            continue

        for tr in table.find_all("tr"):
            cells = [_clean(td.get_text()) for td in tr.find_all("td")]
            if not cells:
                continue
            try:
                name = cells[col_idx["name"]] if col_idx["name"] < len(cells) else ""
                category = cells[col_idx.get("category", -1)] if col_idx.get("category", -1) >= 0 and col_idx.get("category", 0) < len(cells) else ""
                address = cells[col_idx.get("address", -1)] if col_idx.get("address", -1) >= 0 and col_idx.get("address", 0) < len(cells) else ""
                phone = cells[col_idx.get("phone", -1)] if col_idx.get("phone", -1) >= 0 and col_idx.get("phone", 0) < len(cells) else ""
            except IndexError:
                continue
            if not name or name.isdigit():
                continue
            all_rows.append(_make_row(
                name=name, category=category, address=address, phone=phone,
                source="ihc_web", source_region=source_region,
            ))

    df = pd.DataFrame(all_rows)
    logger.info("[IHC] 완료: 총 %d건", len(df))
    return df


# ==============================
# 고양시 (goyang.go.kr)
# ==============================
def scrape_goyang() -> pd.DataFrame:
    """고양시 군장병 우대업소 크롤링 (goyang.go.kr) - 페이지네이션"""
    base_url = "https://www.goyang.go.kr/dygu/sldrPrfrBsns/BD_selectSldrPrfrBsnsList.do"
    source_region = "경기도 고양시"
    logger.info("[GOYANG] 크롤링 시작: %s", base_url)

    all_rows = []
    page = 1
    total_pages = 99  # will be updated after first fetch

    while page <= total_pages:
        data = {
            "q_currPage": str(page),
            "q_rowPerPage": "4",
            "q_searchKeyTy": "",
            "q_searchKeyVal": "",
            "q_sortName": "",
            "q_sortOrder": "",
        }
        html = _fetch(base_url, method="POST", data=data)
        soup = BeautifulSoup(html, "html.parser")

        if page == 1:
            total_text = soup.find(class_="bbs-total")
            if total_text:
                match = re.search(r"(\d+)\s*/\s*(\d+)\s*page", total_text.get_text())
                if match:
                    total_pages = int(match.group(2))
            logger.info("[GOYANG] 총 %d페이지", total_pages)

        page_rows = 0
        # 각 업소는 독립 <table>에 담겨 있고, td를 순서대로 읽으면 됨
        # td 순서: 업소명, 업종, 주소, 전화번호, 할인내용
        for table in soup.find_all("table"):
            cells = [_clean(td.get_text()) for td in table.find_all("td")]
            if len(cells) < 3:
                continue
            name = cells[0]
            category = cells[1] if len(cells) > 1 else ""
            address = cells[2] if len(cells) > 2 else ""
            phone = cells[3] if len(cells) > 3 else ""
            discount_info = cells[4] if len(cells) > 4 else ""
            if not name:
                continue
            all_rows.append(_make_row(
                name=name, category=category, address=address, phone=phone,
                discount_info=discount_info,
                source="goyang_web", source_region=source_region,
            ))
            page_rows += 1

        logger.info("[GOYANG] 페이지 %d/%d: %d건", page, total_pages, page_rows)
        page += 1
        time.sleep(0.3)

    df = pd.DataFrame(all_rows)
    logger.info("[GOYANG] 완료: 총 %d건", len(df))
    return df


# ==============================
# 인제군 (inje.go.kr) - SSL 비검증
# ==============================
def scrape_inje() -> pd.DataFrame:
    """인제군 군장병 우대업소 크롤링 (inje.go.kr) - SSL 비검증"""
    categories = [
        ("restaurant", "음식점"),
        ("accommodation", "숙박"),
        ("hotel", "숙박"),
        ("pc", "PC방"),
        ("beauty", "이미용"),
    ]
    base_url = "https://www.inje.go.kr/portal/inje-news/soldier/givePreference"
    source_region = "강원특별자치도 인제군"
    logger.info("[INJE] 크롤링 시작: %s", base_url)

    all_rows = []
    seen_categories = set()

    for path, category_label in categories:
        if path in seen_categories:
            continue
        url = f"{base_url}/{path}"
        try:
            html = _fetch(url, ssl_context=_SSL_UNVERIFIED)
        except Exception as e:
            logger.warning("[INJE] %s 실패: %s", path, e)
            continue

        soup = BeautifulSoup(html, "html.parser")
        page_rows = 0

        for table in soup.find_all("table"):
            headers = [_clean(th.get_text()) for th in table.find_all("th")]
            has_region_col = any("행정동" in h or "지역" in h for h in headers)
            has_name_col = any("업소명" in h for h in headers)

            if not has_name_col:
                continue

            seen_categories.add(path)
            # 행정동 컬럼은 rowspan으로 병합되어 있어 일부 행에서 누락됨
            # 이름(업소명)이 행정동 위치에 오지 않도록 rowspan 상태를 추적
            current_region = ""
            region_remaining = 0  # 남은 rowspan 행 수

            for tr in table.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue

                cells = [_clean(td.get_text()) for td in tds]
                rowspans = [int(td.get("rowspan", 1)) for td in tds]

                if has_region_col:
                    if region_remaining > 0:
                        # 행정동 셀이 없는 행: 업소명, 주소, 전화번호 순
                        region_remaining -= 1
                        name = cells[0] if len(cells) > 0 else ""
                        address = cells[1] if len(cells) > 1 else ""
                        phone = cells[2] if len(cells) > 2 else ""
                    else:
                        # 행정동 셀이 있는 행: 행정동, 업소명, 주소, 전화번호 순
                        current_region = cells[0] if len(cells) > 0 else ""
                        region_remaining = rowspans[0] - 1
                        name = cells[1] if len(cells) > 1 else ""
                        address = cells[2] if len(cells) > 2 else ""
                        phone = cells[3] if len(cells) > 3 else ""
                else:
                    name = cells[0] if len(cells) > 0 else ""
                    address = cells[1] if len(cells) > 1 else ""
                    phone = cells[2] if len(cells) > 2 else ""

                if not name:
                    continue
                all_rows.append(_make_row(
                    name=name, category=category_label, address=address, phone=phone,
                    source="inje_web", source_region=source_region,
                ))
                page_rows += 1

        logger.info("[INJE] %s (%s): %d건", path, category_label, page_rows)

    df = pd.DataFrame(all_rows)
    logger.info("[INJE] 완료: 총 %d건", len(df))
    return df


# ==============================
# 통합 실행
# ==============================
SCRAPERS = {
    "ddc": (scrape_ddc, "경기도 동두천시"),
    "ihc": (scrape_ihc, "강원특별자치도 화천군"),
    "goyang": (scrape_goyang, "경기도 고양시"),
    "inje": (scrape_inje, "강원특별자치도 인제군"),
}

WEB_SCRAPE_COLUMNS = [
    "name", "category", "business_type", "address", "road_address",
    "phone", "open_time", "close_time", "closed_day", "main_menu",
    "discount_info", "discount_rate", "latitude", "longitude",
    "source", "source_region", "data_base_date",
]


def scrape_all_sites(targets: Optional[List[str]] = None) -> pd.DataFrame:
    """모든 (또는 지정된) 사이트 크롤링 후 병합"""
    targets = targets or list(SCRAPERS.keys())
    frames = []

    for key in targets:
        if key not in SCRAPERS:
            logger.warning("알 수 없는 크롤링 대상: %s", key)
            continue
        scraper_fn, _ = SCRAPERS[key]
        try:
            df = scraper_fn()
            if not df.empty:
                frames.append(df)
        except Exception as e:
            logger.error("[%s] 크롤링 실패: %s", key.upper(), e)

    if not frames:
        return pd.DataFrame(columns=WEB_SCRAPE_COLUMNS)

    merged = pd.concat(frames, ignore_index=True)
    # 빈 이름 및 중복 제거
    merged = merged[merged["name"].str.strip() != ""]
    merged = merged.drop_duplicates(subset=["name", "address"])
    merged = merged.reset_index(drop=True)
    return merged
