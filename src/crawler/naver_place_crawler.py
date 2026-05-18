import re
import time
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


def get_naver_place_info(query: str) -> dict:
    """네이버 플레이스에서 매장 정보를 크롤링하는 함수"""
    if not query:
        return {}

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,1200")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    try:
        encoded_query = quote(query)
        url = f"https://map.naver.com/p/search/{encoded_query}"
        driver.get(url)
        time.sleep(2)

        if _switch_to_entry_iframe(driver):
            return _extract_entry_info(driver)

        if not _switch_to_search_iframe(driver):
            return {}

        items = driver.find_elements(By.CSS_SELECTOR, "li")
        if not items:
            return {}

        driver.execute_script("arguments[0].scrollIntoView(true);", items[0])
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", items[0])
        time.sleep(2)

        if _switch_to_entry_iframe(driver):
            return _extract_entry_info(driver)

        return {}

    finally:
        driver.quit()


def _switch_to_entry_iframe(driver) -> bool:
    try:
        driver.switch_to.default_content()
        WebDriverWait(driver, 7).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "entryIframe"))
        )
        return True
    except TimeoutException:
        driver.switch_to.default_content()
        return False


def _switch_to_search_iframe(driver) -> bool:
    try:
        driver.switch_to.default_content()
        WebDriverWait(driver, 7).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, "searchIframe"))
        )
        return True
    except TimeoutException:
        driver.switch_to.default_content()
        return False


def _extract_entry_info(driver) -> dict:
    _expand_business_hours(driver)
    _scroll_to_menu_area(driver)

    page_text = _get_body_text(driver)
    business_hours = _extract_business_hours_from_text(page_text)

    return {
        "phone": _extract_phone(page_text),
        "open_time": business_hours["open_time"],
        "close_time": business_hours["close_time"],
        "closed_day": _extract_closed_day(page_text),
        "main_menu": _extract_menu_text(page_text),
    }


def _get_body_text(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except NoSuchElementException:
        return ""


def _expand_business_hours(driver) -> None:
    click_keywords = ["영업시간", "영업 중", "영업 전", "영업 종료", "라스트오더"]

    for keyword in click_keywords:
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{keyword}')]")

        for element in elements:
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    element,
                )
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", element)
                time.sleep(0.8)
                return
            except Exception:
                continue


def _scroll_to_menu_area(driver) -> None:
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.6);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
    except Exception:
        return


def _extract_phone(text: str) -> str:
    match = re.search(r"\d{2,4}-\d{3,4}-\d{4}", text)
    return match.group() if match else ""


def _extract_business_hours_from_text(text: str) -> dict:
    result = {"open_time": "", "close_time": ""}

    if not text:
        return result

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        range_match = re.search(
            r"((?:[01]?\d|2[0-3]):[0-5]\d)\s*[-~]\s*((?:[01]?\d|2[0-3]):[0-5]\d)",
            line,
        )

        if range_match:
            result["open_time"] = range_match.group(1)
            result["close_time"] = range_match.group(2)
            return result

    times = re.findall(r"(?:[01]?\d|2[0-3]):[0-5]\d", text)

    if len(times) >= 2:
        result["open_time"] = times[0]
        result["close_time"] = times[1]

    return result


def _extract_closed_day(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        if "휴무" in line or "정기휴무" in line:
            return line

    return ""


def _extract_menu_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if "메뉴" not in lines:
        return ""

    menu_start_index = lines.index("메뉴")
    menu_lines = lines[menu_start_index + 1 :]

    menu_candidates = []

    exclude_keywords = [
        "더보기",
        "접기",
        "펼쳐보기",
        "리뷰",
        "주소",
        "영업시간",
        "전화번호",
        "편의",
        "길찾기",
        "거리뷰",
        "저장",
        "공유",
        "원산지",
    ]

    for line in menu_lines:
        if any(keyword in line for keyword in exclude_keywords):
            continue

        if re.search(r"\d{1,3},?\d{3}\s*원", line):
            continue

        if len(line) > 30:
            continue

        if re.search(r"[가-힣]{2,}", line):
            menu_candidates.append(line)

        if len(menu_candidates) >= 2:
            break

    unique_menus = list(dict.fromkeys(menu_candidates))
    return ", ".join(unique_menus[:2])
