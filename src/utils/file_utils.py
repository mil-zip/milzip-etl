import json
from pathlib import Path
from typing import Any, Union

import pandas as pd


def ensure_parent_dir(file_path: Union[str, Path]) -> None:
    """파일 저장 전 상위 폴더를 생성하는 함수"""
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def save_json(data: Any, file_path: Union[str, Path]) -> None:
    """데이터를 JSON 파일로 저장하는 함수"""
    ensure_parent_dir(file_path)

    with Path(file_path).open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def save_dataframe_csv(dataframe: pd.DataFrame, file_path: Union[str, Path]) -> None:
    """DataFrame을 CSV 파일로 저장하는 함수"""
    ensure_parent_dir(file_path)
    dataframe.to_csv(file_path, index=False, encoding="utf-8-sig")


def load_csv(file_path: Union[str, Path]) -> pd.DataFrame:
    """CSV 파일을 읽어 DataFrame으로 반환하는 함수"""
    return read_csv_with_encoding(file_path)


def read_csv_with_encoding(file_path: Union[str, Path]) -> pd.DataFrame:
    """CSV 파일을 여러 인코딩으로 시도하여 읽는 함수"""
    encodings = ["utf-8-sig", "cp949", "euc-kr"]

    for encoding in encodings:
        try:
            return pd.read_csv(file_path, encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeError("CSV 인코딩을 확인할 수 없습니다.")
