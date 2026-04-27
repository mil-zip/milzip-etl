from src.config.settings import DATA_GO_KR_SERVICE_KEY, KAKAO_REST_API_KEY


def mask_sensitive_text(text):
    """로그에 민감정보가 노출되지 않도록 마스킹하는 함수"""
    if not text:
        return text

    sensitive_values = [
        DATA_GO_KR_SERVICE_KEY,
        KAKAO_REST_API_KEY,
    ]

    masked_text = text

    for value in sensitive_values:
        if value:
            masked_text = masked_text.replace(value, "****")

    return masked_text
