"""주간 박스오피스 데이터 적재

data/processed/weekly_boxoffice.json 을 생성한 뒤,
PostgreSQL 테이블에 upsert 합니다.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

import psycopg2

from src.utils.logger import get_logger

logger = get_logger()


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://postgres:@localhost:5432/milzip"
    ).replace("postgresql+psycopg2://", "postgresql://")


def _parse_target_dt(movies: list[dict[str, Any]], target_dt: Optional[str]) -> str:
    if target_dt:
        return target_dt
    if movies and movies[0].get("target_dt"):
        return str(movies[0]["target_dt"])
    raise ValueError("target_dt가 없습니다. (movies에 target_dt 포함 필요)")


def load_weekly_boxoffice(movies: list[dict[str, Any]], target_dt: Optional[str] = None) -> None:
    """weekly_boxoffice 테이블에 upsert"""
    target_dt = _parse_target_dt(movies, target_dt)
    conn = psycopg2.connect(_database_url())
    now = datetime.now()

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS weekly_boxoffice (
                    id BIGSERIAL PRIMARY KEY,
                    target_dt DATE NOT NULL,
                    rank INT NOT NULL,
                    movie_cd TEXT NOT NULL,
                    title TEXT NOT NULL,
                    open_date DATE NULL,
                    audience_count BIGINT NULL,
                    genre TEXT NULL,
                    runtime_minutes INT NULL,
                    poster_url TEXT NULL,
                    updated_at TIMESTAMP NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS weekly_boxoffice_uq
                ON weekly_boxoffice (target_dt, movie_cd);
                """
            )

            upsert_sql = """
                INSERT INTO weekly_boxoffice (
                    target_dt, rank, movie_cd, title, open_date, audience_count,
                    genre, runtime_minutes, poster_url, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (target_dt, movie_cd) DO UPDATE SET
                    rank = EXCLUDED.rank,
                    title = EXCLUDED.title,
                    open_date = EXCLUDED.open_date,
                    audience_count = EXCLUDED.audience_count,
                    genre = EXCLUDED.genre,
                    runtime_minutes = EXCLUDED.runtime_minutes,
                    poster_url = EXCLUDED.poster_url,
                    updated_at = EXCLUDED.updated_at;
            """

            inserted = 0
            skipped = 0
            for m in movies:
                movie_cd = str(m.get("movie_cd") or "").strip()
                title = str(m.get("title") or "").strip()
                rank = _to_int_or_none(m.get("rank"))
                if not movie_cd or not title or not rank:
                    skipped += 1
                    continue

                open_dt = m.get("open_date") or None
                # KOBIS openDt는 YYYY-MM-DD 형태이지만 빈 문자열도 올 수 있음
                if isinstance(open_dt, str) and not open_dt.strip():
                    open_dt = None

                cur.execute(
                    upsert_sql,
                    (
                        _yyyymmdd_to_date(target_dt),
                        int(rank),
                        movie_cd,
                        title,
                        _yyyy_mm_dd_to_date(open_dt),
                        _to_int_or_none(m.get("audience_count")),
                        m.get("genre"),
                        _to_int_or_none(m.get("runtime_minutes")),
                        m.get("poster_url"),
                        now,
                    ),
                )
                inserted += 1

        conn.commit()
        logger.info(
            "✅ 박스오피스 DB upsert 완료: %s 기준 %d건 (스킵 %d건)",
            target_dt,
            inserted,
            skipped,
        )
    except Exception as e:
        conn.rollback()
        logger.error("❌ 박스오피스 DB 적재 실패: %s", e)
        raise
    finally:
        conn.close()



def _to_int_or_none(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return int(v)
        return int(v)
    except Exception:
        return None


def _yyyymmdd_to_date(s: str):
    return datetime.strptime(s, "%Y%m%d").date()


def _yyyy_mm_dd_to_date(s: Optional[str]):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None
