"""
integrated_final_discount_stores.csv → PostgreSQL Store / StoreBenefit 테이블 적재
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String, Time, DECIMAL, ForeignKey, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from typing import List, Optional

from src.utils.category_mapper import StoreCategory, map_category
from src.utils.logger import get_logger

logger = get_logger()

CSV_PATH = Path("data/processed/integrated_final_discount_stores.csv")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:password@localhost:5432/milzip",
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Store(Base):
    __tablename__ = "store"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[StoreCategory] = mapped_column(Enum(StoreCategory, name="storecategory"), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(DECIMAL(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(DECIMAL(10, 7), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_military_benefit: Mapped[bool] = mapped_column(Boolean, default=False)
    is_benefit_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    view_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    open_time = mapped_column(Time, nullable=True)
    close_time = mapped_column(Time, nullable=True)
    close_date = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    benefits: Mapped[List["StoreBenefit"]] = relationship(
        "StoreBenefit", back_populates="store", cascade="all, delete-orphan"
    )


class StoreBenefit(Base):
    __tablename__ = "store_benefit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("Store.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    discount_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    condition_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at = mapped_column(DateTime, onupdate=func.now(), nullable=True)

    store: Mapped["Store"] = relationship("Store", back_populates="benefits")


def _parse_time(value):
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").time()
    except (ValueError, TypeError):
        return None


def _is_valid(value) -> bool:
    return pd.notna(value) and str(value).strip() not in ("", "nan", "None")


def load_stores(csv_path: Path = CSV_PATH, reset: bool = False) -> None:
    """CSV를 읽어 Store / StoreBenefit 테이블에 적재한다.

    Args:
        csv_path: 적재할 CSV 파일 경로
        reset: True이면 기존 데이터를 모두 삭제하고 재적재
    """
    Base.metadata.create_all(bind=engine)

    df = pd.read_csv(csv_path)
    df = df[df["latitude"].notna() & df["longitude"].notna()].reset_index(drop=True)
    logger.info("적재 대상: %d건 (위도경도 보유)", len(df))

    db = SessionLocal()
    try:
        if reset:
            db.query(StoreBenefit).delete()
            db.query(Store).delete()
            db.commit()
            logger.info("기존 데이터 삭제 완료")

        inserted = 0
        skipped = 0

        for _, row in df.iterrows():
            name = str(row["name"]).strip()
            address = str(row["address"]).strip()

            exists = db.query(Store).filter(
                Store.name == name, Store.address == address
            ).first()
            if exists:
                skipped += 1
                continue

            store = Store(
                name=name,
                category=map_category(str(row.get("category", ""))),
                address=address,
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                phone=str(row["phone"]).strip() if _is_valid(row.get("phone")) else None,
                open_time=_parse_time(row.get("open_time")),
                close_time=_parse_time(row.get("close_time")),
                is_military_benefit=True,
                is_benefit_verified=False,
                view_count=0,
            )
            db.add(store)
            db.flush()

            discount_info = str(row.get("discount_info", "")).strip()
            if _is_valid(row.get("discount_info")) and discount_info:
                discount_rate_raw = row.get("discount_rate")
                discount_rate = int(discount_rate_raw) if _is_valid(discount_rate_raw) else None
                db.add(StoreBenefit(
                    store_id=store.id,
                    description=discount_info[:255],
                    discount_rate=discount_rate,
                ))

            inserted += 1
            if inserted % 100 == 0:
                db.commit()
                logger.info("진행: %d건 적재 완료", inserted)

        db.commit()
        logger.info("✅ 적재 완료 — 신규: %d건, 스킵: %d건", inserted, skipped)

    except Exception as e:
        db.rollback()
        logger.error("❌ 적재 실패: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_stores()
