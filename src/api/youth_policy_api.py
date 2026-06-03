"""청년정책 API 클라이언트 (온통청년 - youthcenter.go.kr)

군인 관련 정책을 필터링하여 반환합니다.
"""
import time
from typing import Optional

import requests

from src.config.settings import YOUTH_POLICY_API_KEY
from src.utils.logger import get_logger

logger = get_logger()

BASE_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"

MILITARY_KEYWORDS = ["군인", "군장병", "병사", "현역", "복무", "군복무", "사병", "장병"]

# 대분류 → 단순 카테고리 매핑
CATEGORY_MAP = {
    "일자리": "일자리",
    "일자리,교육": "일자리",
    "주거": "주거",
    "교육": "교육",
    "교육･직업훈련": "교육",
    "복지문화": "복지·문화",
    "금융･복지･문화": "복지·금융",
    "금융·복지·문화": "복지·금융",
    "참여·권리": "참여·권리",
    "참여권리": "참여·권리",
}


def _is_military_related(policy: dict) -> bool:
    searchable = " ".join([
        policy.get("plcyNm") or "",
        policy.get("plcyKywdNm") or "",
        policy.get("plcyExplnCn") or "",
        policy.get("plcySprtCn") or "",
        policy.get("addAplyQlfcCndCn") or "",
        policy.get("sBizCd") or "",
    ])
    return any(kw in searchable for kw in MILITARY_KEYWORDS)


def _first_valid_url(*urls: str) -> Optional[str]:
    """여러 URL 중 첫 번째 유효한 값 반환"""
    for url in urls:
        if url and url.strip():
            return url.strip()
    return None


def _parse_date(value: str) -> Optional[str]:
    """빈 문자열·공백 → None, 유효한 날짜는 YYYY-MM-DD 형식으로 변환"""
    if not value or not value.strip():
        return None
    v = value.strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return v


def fetch_military_youth_policies(max_pages: int = 30) -> list:
    """군인 대상 청년정책 목록 수집"""
    if not YOUTH_POLICY_API_KEY:
        raise RuntimeError("YOUTH_POLICY_API_KEY가 설정되지 않았습니다.")

    all_policies = []

    for page in range(1, max_pages + 1):
        params = {
            "apiKeyNm": YOUTH_POLICY_API_KEY,
            "pageNum": page,
            "pageSize": 100,
            "rtnType": "json",
        }

        for attempt in range(3):
            try:
                resp = requests.get(BASE_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                policies = data.get("result", {}).get("youthPolicyList", [])
                if not policies:
                    logger.info("[YouthPolicy] 페이지 %d: 데이터 없음, 종료", page)
                    return all_policies

                military = [p for p in policies if _is_military_related(p)]
                all_policies.extend(military)
                logger.info("[YouthPolicy] 페이지 %d: 전체 %d건 중 군인 관련 %d건", page, len(policies), len(military))

                if len(policies) < 100:
                    return all_policies

                time.sleep(1.0)
                break

            except Exception as e:
                logger.warning("[YouthPolicy] 페이지 %d 요청 실패 (시도 %d/3): %s", page, attempt + 1, e)
                if attempt < 2:
                    time.sleep(3)
                else:
                    logger.error("[YouthPolicy] 페이지 %d 최종 실패, 건너뜀", page)

    logger.info("✅ 청년정책 수집 완료: 군인 관련 %d건", len(all_policies))
    return all_policies


def normalize_policy(p: dict) -> dict:
    """필요한 필드만 추출·정제"""
    large = p.get("lclsfNm") or ""
    category = CATEGORY_MAP.get(large.strip(), large.strip() or "기타")

    return {
        "name": p.get("plcyNm"),
        "category": category,
        "description": p.get("plcyExplnCn"),
        "support_content": p.get("plcySprtCn"),
        "apply_method": p.get("plcyAplyMthdCn"),
        "url": _first_valid_url(
            p.get("aplyUrlAddr"),
            p.get("refUrlAddr1"),
            p.get("refUrlAddr2"),
        ),
        "start_date": _parse_date(p.get("bizPrdBgngYmd")),
        "end_date": _parse_date(p.get("bizPrdEndYmd")),
        "supervise_inst": p.get("sprvsnInstCdNm"),
    }
