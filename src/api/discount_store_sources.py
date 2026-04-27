from dataclasses import dataclass


@dataclass(frozen=True)
class PublicDataSource:
    source_id: str
    region: str
    name: str
    data_page_url: str
    csv_url: str | None = None
    json_url: str | None = None


DISCOUNT_STORE_SOURCES = [
    PublicDataSource(
        source_id="yeongcheon_file",
        region="경상북도 영천시",
        name="경상북도 영천시_군장병 할인업소 현황",
        data_page_url="https://www.data.go.kr/data/15044647/fileData.do",
        # 공공데이터포털에서 다운로드 URL 확인 후 넣기
        csv_url=None,
        json_url=None,
    ),
    PublicDataSource(
        source_id="pocheon_file",
        region="경기도 포천시",
        name="경기도 포천시_군장병할인업소 현황",
        data_page_url="https://www.data.go.kr/data/15106202/fileData.do",
        # 공공데이터포털에서 다운로드 URL 확인 후 넣기
        csv_url=None,
        json_url=None,
    ),
    PublicDataSource(
        source_id="paju_file",
        region="경기도 파주시",
        name="경기도 파주시_군장병할인업소현황",
        data_page_url="https://www.data.go.kr/data/15126366/fileData.do",
        # 공공데이터포털에서 다운로드 URL 확인 후 넣기
        csv_url=None,
        json_url=None,
    ),
]
