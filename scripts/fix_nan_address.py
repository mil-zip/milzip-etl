"""
DB에 'nan'으로 저장된 address를 road_address로 업데이트하는 일회성 픽스 스크립트.

실행:
    cd milzip-etl
    .venv/bin/python scripts/fix_nan_address.py
"""
import os

import pandas as pd
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/milzip",
)

CSV_PATH = "data/processed/integrated_final_discount_stores.csv"


def fix_nan_addresses() -> None:
    df = pd.read_csv(CSV_PATH)

    # address가 NaN/빈 값이고 road_address가 있는 행만 추출
    addr_is_empty = df["address"].isna() | df["address"].astype(str).str.strip().isin(["", "nan"])
    road_available = df["road_address"].notna() & ~df["road_address"].astype(str).str.strip().isin(["", "nan"])
    targets = df[addr_is_empty & road_available][["name", "road_address"]].copy()
    targets["road_address"] = targets["road_address"].astype(str).str.strip()

    print(f"[INFO] 업데이트 대상: {len(targets)}건")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    updated = 0
    skipped = 0

    for _, row in targets.iterrows():
        name = str(row["name"]).strip()
        road_address = row["road_address"]

        cur.execute(
            "UPDATE stores SET address = %s WHERE name = %s AND address = 'nan'",
            (road_address, name),
        )
        count = cur.rowcount
        if count > 0:
            updated += count
            print(f"  ✅ {name} → {road_address}")
        else:
            skipped += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n[DONE] 업데이트: {updated}건, 스킵(이미 정상): {skipped}건")


if __name__ == "__main__":
    fix_nan_addresses()
