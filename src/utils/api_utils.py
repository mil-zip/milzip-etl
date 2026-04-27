from src.config.settings import DATA_GO_KR_SERVICE_KEY


def mask_sensitive_text(text: str) -> str:
    """로그에 민감정보가 노출되지 않도록 마스킹하는 함수"""
    if not text:
        return text

    return text.replace(DATA_GO_KR_SERVICE_KEY, "****")
