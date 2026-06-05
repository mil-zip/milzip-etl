"""store_images 테이블의 외부 이미지 URL을 AWS S3에 업로드하고 DB URL을 교체합니다.

흐름:
  1. store_images 테이블에서 외부 URL(S3가 아닌) 목록 조회
  2. 이미지 다운로드
  3. AWS S3에 업로드
  4. store_images.image_url을 S3 URL로 UPDATE
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Optional
from urllib.parse import urlparse

import psycopg2
import requests

from src.config.settings import S3_ACCESS_KEY, S3_BUCKET, S3_REGION, S3_SECRET_KEY
from src.utils.logger import get_logger

logger = get_logger()

S3_BASE_URL = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com"


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL", "postgresql://postgres:@localhost:5432/milzip"
    ).replace("postgresql+psycopg2://", "postgresql://")


def _s3_client():
    import boto3

    return boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )


def _is_external_url(url: str) -> bool:
    """AWS S3 URL이 아닌 외부 URL인지 확인"""
    return not url.startswith(S3_BASE_URL)


def _download_image(url: str) -> Optional[tuple[bytes, str]]:
    """이미지 다운로드. (bytes, content_type) 반환. 실패 시 None."""
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return resp.content, content_type
    except Exception as e:
        logger.warning("[S3] 이미지 다운로드 실패 url=%s: %s", url, e)
        return None


def _upload_to_s3(s3, image_bytes: bytes, content_type: str, ext: str) -> Optional[str]:
    """S3에 업로드 후 URL 반환. 실패 시 None."""
    key = f"store/{uuid.uuid4()}{ext}"
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
        )
        return f"{S3_BASE_URL}/{key}"
    except Exception as e:
        logger.warning("[S3] 업로드 실패 key=%s: %s", key, e)
        return None


def _ext_from_url(url: str, content_type: str) -> str:
    """URL 또는 content-type에서 확장자 추출"""
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        return ext
    ct_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return ct_map.get(content_type, ".jpg")


def run_s3_image_upload_pipeline() -> None:
    """외부 이미지 URL → S3 업로드 → DB URL 교체"""
    if not all([S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET]):
        logger.error("[S3] S3 환경변수가 설정되지 않았습니다. (S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET)")
        return

    s3 = _s3_client()
    conn = psycopg2.connect(_database_url())

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, image_url FROM store_images WHERE image_url NOT LIKE %s",
                (f"{S3_BASE_URL}%",),
            )
            rows = cur.fetchall()

        logger.info("[S3] 업로드 대상: %d건", len(rows))

        success = 0
        skip = 0

        for image_id, url in rows:
            result = _download_image(url)
            if result is None:
                skip += 1
                continue

            image_bytes, content_type = result
            ext = _ext_from_url(url, content_type)
            s3_url = _upload_to_s3(s3, image_bytes, content_type, ext)

            if s3_url is None:
                skip += 1
                continue

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE store_images SET image_url = %s WHERE id = %s",
                    (s3_url, image_id),
                )
            conn.commit()
            success += 1

            if success % 50 == 0:
                logger.info("[S3] 진행: %d건 완료 (스킵 %d건)", success, skip)

            time.sleep(0.1)

        logger.info("✅ S3 이미지 업로드 완료: 성공 %d건, 스킵 %d건", success, skip)

    except Exception as e:
        conn.rollback()
        logger.error("[S3] 파이프라인 실패: %s", e)
        raise
    finally:
        conn.close()
