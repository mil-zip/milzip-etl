import os

from dotenv import load_dotenv

load_dotenv()

DATA_GO_KR_SERVICE_KEY = os.getenv("DATA_GO_KR_SERVICE_KEY", "")
YEONGCHEON_API_URL = os.getenv("YEONGCHEON_API_URL", "")
MMA_NARASARANG_API_URL = os.getenv("MMA_NARASARANG_API_URL", "")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
TOUR_API_BASE_URL = os.getenv("TOUR_API_BASE_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
YOUTH_POLICY_API_KEY = os.getenv("YOUTH_POLICY_API_KEY", "")
KOBIS_API_KEY = os.getenv("KOBIS_API_KEY", "")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
