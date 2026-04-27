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
    options.add_argument("--window-size=1280,900")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )

    try:
        encoded_query = quote(query)
        url = f"https://map.naver.com/p/search/{encoded_query}"
        driver.get(url)

        time.sleep(2)

        # 바로 entry iframe 들어갈 수 있는 경우
        if _switch_to_entry_iframe(driver):
            return _extract_entry_info(driver)

        # 검색 결과 iframe 진입
        if not _switch_to_search_iframe(driver):
            return {}

        items = driver.find_elements(By.CSS_SELECTOR, "li")
        if not items:
            return {}

        driver.execute_script("arguments[0].scrollIntoView(true);", items[0])
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", items[0])
        time.sleep(2)

        driver.switch_to.default_content()

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
    """상세 페이지에서 정보 추출"""
    result = {
        "phone": "",
        "open_time": "",
        "close_time": "",
        "closed_day": "",
        "main_menu": "",
    }

    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
    except NoSuchElementException:
        return result

    # 영업시간 분리
    business_hours = _extract_business_hours(page_text)

    result["phone"] = _extract_phone(page_text)
    result["open_time"] = business_hours["open_time"]
    result["close_time"] = business_hours["close_time"]
    result["closed_day"] = _extract_closed_day(page_text)
    result["main_menu"] = _extract_menu_text(driver)

    return result


def _extract_phone(text: str) -> str:
    """전화번호 추출"""
    match = re.search(r"\d{2,4}-\d{3,4}-\d{4}", text)
    return match.group() if match else ""


def _extract_business_hours(text: str) -> dict:
    """영업 시작/종료 시간 추출"""
    result = {"open_time": "", "close_time": ""}

    times = re.findall(r"(?:[01]?\d|2[0-3]):[0-5]\d", text)

    if len(times) >= 2:
        result["open_time"] = times[0]
        result["close_time"] = times[1]

    return result


def _extract_closed_day(text: str) -> str:
    """휴무일 추출"""
    for line in text.splitlines():
        if "휴무" in line or "정기휴무" in line:
            return line.strip()

    return ""


def _extract_menu_text(driver) -> str:
    """메뉴 추출"""
    try:
        menus = driver.find_elements(
            By.CSS_SELECTOR, "[class*='menu'], [class*='Menu']"
        )
        menu_texts = [menu.text.strip() for menu in menus if menu.text.strip()]
        return ", ".join(menu_texts[:5])
    except NoSuchElementException:
        return ""
