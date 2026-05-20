"""stores 테이블 매장 데이터 임베딩 생성 및 pgvector 적재

실행 전 준비:
  1. PostgreSQL에 pgvector 확장 설치 (최초 1회)
     CREATE EXTENSION IF NOT EXISTS vector;
  2. stores 테이블에 embedding 컬럼 추가 (최초 1회)
     ALTER TABLE stores ADD COLUMN IF NOT EXISTS embedding vector(1536);
  3. .env에 OPENAI_API_KEY 설정

실행 명령어:
  python -m src.main --mode embedding
"""
import os
import time

import psycopg2
from openai import OpenAI

from src.config.settings import OPENAI_API_KEY
from src.utils.logger import get_logger

logger = get_logger()

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50
RATE_LIMIT_SLEEP = 0.3


def _build_store_text(row: dict) -> str:
    """매장 데이터를 임베딩용 텍스트로 조합"""
    parts = [
        row.get("name") or "",
        row.get("category") or "",
        row.get("address") or "",
        row.get("discount_info") or "",
    ]
    return " ".join(p for p in parts if p and p.lower() != "nan").strip()


def _get_embedding(client: OpenAI, text: str) -> list[float]:
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def _setup_pgvector(conn) -> None:
    """pgvector 확장 및 embedding 컬럼 초기화 (최초 1회)"""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute(
            "ALTER TABLE stores ADD COLUMN IF NOT EXISTS embedding vector(1536);"
        )
    conn.commit()
    logger.info("pgvector 준비 완료")


def run_store_embedding_pipeline() -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:@localhost:5432/milzip",
    ).replace("postgresql+psycopg2://", "postgresql://")

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    client = OpenAI(api_key=OPENAI_API_KEY)

    conn = psycopg2.connect(database_url)

    try:
        _setup_pgvector(conn)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.name, s.category, s.address,
                       string_agg(sb.description, ' ') AS discount_info
                FROM stores s
                LEFT JOIN store_benefits sb ON s.id = sb.store_id
                WHERE s.embedding IS NULL
                GROUP BY s.id
                ORDER BY s.id
                """
            )
            rows = [
                dict(zip([desc[0] for desc in cur.description], row))
                for row in cur.fetchall()
            ]

        total = len(rows)
        logger.info("임베딩 대상: %d건", total)

        if total == 0:
            logger.info("모든 매장에 임베딩이 이미 존재합니다.")
            return

        success = 0
        skip = 0

        for i, row in enumerate(rows):
            text = _build_store_text(row)

            if not text:
                skip += 1
                continue

            try:
                embedding = _get_embedding(client, text)
                vector_str = "[" + ",".join(map(str, embedding)) + "]"

                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE stores SET embedding = %s::vector WHERE id = %s",
                        (vector_str, row["id"]),
                    )
                conn.commit()
                success += 1

            except Exception as e:
                logger.warning("임베딩 실패 - id: %d, error: %s", row["id"], e)
                skip += 1

            if (i + 1) % BATCH_SIZE == 0:
                logger.info("진행: %d / %d (성공 %d, 스킵 %d)", i + 1, total, success, skip)

            time.sleep(RATE_LIMIT_SLEEP)

        logger.info("임베딩 완료: 성공 %d건, 스킵 %d건 / 전체 %d건", success, skip, total)

    finally:
        conn.close()
