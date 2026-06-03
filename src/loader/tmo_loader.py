"""TMO 데이터 DB 적재 (data/processed/tmo_list.json → tmos 테이블)"""
import json
import os
from datetime import datetime
from pathlib import Path

import psycopg2

from src.utils.logger import get_logger

logger = get_logger()

JSON_PATH = Path("data/processed/tmo_list.json")


def load_tmos(reset: bool = False) -> None:
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:@localhost:5432/milzip"
    ).replace("postgresql+psycopg2://", "postgresql://")

    if not JSON_PATH.exists():
        raise FileNotFoundError(f"{JSON_PATH} 없음. --mode tmo 먼저 실행하세요.")

    with open(JSON_PATH, encoding="utf-8") as f:
        tmos = json.load(f)

    conn = psycopg2.connect(database_url)
    now = datetime.now()

    try:
        with conn.cursor() as cur:
            if reset:
                cur.execute("DELETE FROM tmos")
                conn.commit()
                logger.info("기존 TMO 데이터 삭제 완료")

            inserted = 0
            skipped = 0

            for tmo in tmos:
                name = tmo.get("name")
                if not name:
                    skipped += 1
                    continue

                cur.execute("SELECT id FROM tmos WHERE name = %s", (name,))
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO tmos (
                        name, phone,
                        weekday_start_time, weekday_end_time,
                        weekend_start_time, weekend_end_time,
                        location_description, note, is_mobile,
                        latitude, longitude, address,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        name,
                        tmo.get("phone"),
                        tmo.get("weekday_start_time"),
                        tmo.get("weekday_end_time"),
                        tmo.get("weekend_start_time"),
                        tmo.get("weekend_end_time"),
                        tmo.get("location_description"),
                        tmo.get("note"),
                        tmo.get("is_mobile", False),
                        tmo.get("latitude"),
                        tmo.get("longitude"),
                        tmo.get("address"),
                        now,
                    ),
                )
                inserted += 1

        conn.commit()
        logger.info("✅ TMO 적재 완료 — 신규: %d건, 스킵: %d건", inserted, skipped)

    except Exception as e:
        conn.rollback()
        logger.error("❌ TMO 적재 실패: %s", e)
        raise
    finally:
        conn.close()
