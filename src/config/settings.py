import os

from dotenv import load_dotenv

load_dotenv()

DATA_GO_KR_SERVICE_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY", "")
YEONGCHEON_API_URL = os.getenv("YEONGCHEON_API_URL", "")
MMA_NARASARANG_API_URL = os.getenv("MMA_NARASARANG_API_URL", "")
