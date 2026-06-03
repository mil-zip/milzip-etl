"""
youth_policies.csv → PostgreSQL benefits 테이블 적재 (BenefitType: SELF_DEVELOPMENT)

필드 매핑:
  name            → title
  description     → description
  category        → category
  url             → apply_url
  support_content → support_type
  apply_method    → verification_method
  start_date      → valid_from
  end_date        → valid_until
"""
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import BigInteger, Column, Date, Enum as SAEnum, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from src.utils.logger import get_logger

logger = get_logger()

CSV_PATH = Path("data/processed/youth_policies.csv")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:password@localhost:5432/milzip",
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Benefit(Base):
    __tablename__ = "benefits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    benefit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description = mapped_column(String(1000), nullable=True)
    image_url = mapped_column(String(1000), nullable=True)
    cinema_chain = mapped_column(String(100), nullable=True)
    region = mapped_column(String(100), nullable=True)
    location = mapped_column(String(255), nullable=True)
    valid_from = mapped_column(Date, nullable=True)
    valid_until = mapped_column(Date, nullable=True)
    original_price = mapped_column(BigInteger, nullable=True)
    discounted_price = mapped_column(BigInteger, nullable=True)
    discount_description = mapped_column(String(500), nullable=True)
    verification_method = mapped_column(String(500), nullable=True)
    category = mapped_column(String(100), nullable=True)
    apply_url = mapped_column(String(1000), nullable=True)
    support_type = mapped_column(String(1000), nullable=True)
    supervise_inst = mapped_column(String(255), nullable=True)


def _parse_date(value) -> Optional[date]:
    if pd.isna(value) or not str(value).strip():
        return None
    try:
        from datetime import datetime
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def load_youth_policies(csv_path: Path = CSV_PATH, reset: bool = False) -> None:
    """CSV를 읽어 benefits 테이블 (SELF_DEVELOPMENT)에 적재한다."""
    df = pd.read_csv(csv_path)
    logger.info("청년정책 적재 대상: %d건", len(df))

    db = SessionLocal()
    try:
        if reset:
            db.query(Benefit).filter(
                Benefit.benefit_type == "SELF_DEVELOPMENT"
            ).delete()
            db.commit()
            logger.info("기존 SELF_DEVELOPMENT 데이터 삭제 완료")

        inserted = 0
        skipped = 0

        for _, row in df.iterrows():
            title = str(row.get("name", "")).strip()
            if not title:
                skipped += 1
                continue

            supervise_inst = str(row["supervise_inst"]).strip() if pd.notna(row.get("supervise_inst")) else None

            exists = db.query(Benefit).filter(
                Benefit.benefit_type == "SELF_DEVELOPMENT",
                Benefit.title == title,
                Benefit.supervise_inst == supervise_inst,
            ).first()

            if exists:
                skipped += 1
                continue

            benefit = Benefit(
                benefit_type="SELF_DEVELOPMENT",
                title=title,
                description=str(row["description"]).strip() if pd.notna(row.get("description")) else None,
                category=str(row["category"]).strip() if pd.notna(row.get("category")) else None,
                apply_url=str(row["url"]).strip() if pd.notna(row.get("url")) else None,
                support_type=str(row["support_content"]).strip() if pd.notna(row.get("support_content")) else None,
                verification_method=str(row["apply_method"]).strip() if pd.notna(row.get("apply_method")) else None,
                valid_from=_parse_date(row.get("start_date")),
                valid_until=_parse_date(row.get("end_date")),
                supervise_inst=supervise_inst,
            )
            db.add(benefit)
            inserted += 1

        db.commit()
        logger.info("✅ 청년정책 적재 완료 — 신규: %d건, 스킵: %d건", inserted, skipped)

    except Exception as e:
        db.rollback()
        logger.error("❌ 청년정책 적재 실패: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_youth_policies()
