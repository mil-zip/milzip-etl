"""영화진흥위원회(KOBIS) API 클라이언트

주간 박스오피스 + 영화 상세정보(장르, 상영시간)를 수집합니다.
포스터 이미지는 KOBIS에 없으므로 TMDB API로 별도 수집합니다.
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import requests

from src.config.settings import KOBIS_API_KEY, TMDB_API_KEY
from src.utils.logger import get_logger

logger = get_logger()

BOXOFFICE_URL = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchWeeklyBoxOfficeList.json"
MOVIE_INFO_URL = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieInfo.json"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


def _last_saturday() -> str:
    """직전 토요일 날짜 반환 (YYYYMMDD)"""
    today = datetime.today()
    days_since_saturday = (today.weekday() + 2) % 7
    last_sat = today - timedelta(days=days_since_saturday)
    return last_sat.strftime("%Y%m%d")


def fetch_weekly_boxoffice(target_dt: Optional[str] = None) -> list[dict]:
    """주간 박스오피스 상위 10편 수집"""
    if not KOBIS_API_KEY:
        raise RuntimeError("KOBIS_API_KEY가 설정되지 않았습니다.")

    params = {
        "key": KOBIS_API_KEY,
        "targetDt": target_dt or _last_saturday(),
        "weekGb": "0",
    }

    resp = requests.get(BOXOFFICE_URL, params=params, timeout=10)
    resp.raise_for_status()

    movies = resp.json().get("boxOfficeResult", {}).get("weeklyBoxOfficeList", [])
    logger.info("[KOBIS] 주간 박스오피스 %d편 수집", len(movies))
    return movies


def fetch_movie_detail(movie_cd: str) -> Optional[dict]:
    """영화 상세정보 조회 (장르, 상영시간 등)"""
    params = {"key": KOBIS_API_KEY, "movieCd": movie_cd}
    try:
        resp = requests.get(MOVIE_INFO_URL, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("movieInfoResult", {}).get("movieInfo", {})
    except Exception as e:
        logger.warning("[KOBIS] 영화 상세 조회 실패 movieCd=%s: %s", movie_cd, e)
        return None


def fetch_movie_poster(movie_title: str) -> Optional[str]:
    """TMDB 검색으로 영화 포스터 URL 조회"""
    if not TMDB_API_KEY:
        return None

    try:
        resp = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": TMDB_API_KEY, "query": movie_title, "language": "ko-KR"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            poster_path = results[0].get("poster_path")
            if poster_path:
                return TMDB_IMAGE_BASE_URL + poster_path
    except Exception as e:
        logger.warning("[TMDB] 포스터 조회 실패 title=%s: %s", movie_title, e)

    return None


def run_weekly_boxoffice_pipeline() -> list[dict]:
    """주간 박스오피스 + 상세정보 + 포스터 통합 수집"""
    target_dt = _last_saturday()
    movies = fetch_weekly_boxoffice(target_dt=target_dt)
    result = []

    for movie in movies:
        movie_cd = movie.get("movieCd")
        movie_nm = movie.get("movieNm")

        detail = fetch_movie_detail(movie_cd) if movie_cd else None
        time.sleep(0.3)

        genres = [g.get("genreNm") for g in (detail or {}).get("genres", [])] if detail else []
        show_tm = detail.get("showTm") if detail else None

        poster_url = fetch_movie_poster(movie_nm) if movie_nm else None
        time.sleep(0.3)

        result.append({
            "target_dt": target_dt,
            "rank": int(movie.get("rank", 0)),
            "movie_cd": movie_cd,
            "title": movie_nm,
            "open_date": movie.get("openDt"),
            "audience_count": int(movie.get("audiAcc", 0)),
            "genre": ", ".join(genres) if genres else None,
            "runtime_minutes": int(show_tm) if show_tm and show_tm.isdigit() else None,
            "poster_url": poster_url,
        })

        logger.info("[KOBIS] %d위 %s 처리 완료", int(movie.get("rank", 0)), movie_nm)

    return result
