from app.config.settings import settings
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider


def create_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    raise ValueError(f"Unsupported LLM provider: {provider!r}. Supported: openai")
