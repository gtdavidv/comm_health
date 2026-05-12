import structlog
from openai import AsyncOpenAI

from app.llm.base import LLMProvider

log = structlog.get_logger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(self, system: str, user: str) -> str:
        log.debug("llm_request", model=self._model, user_chars=len(user))
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        log.debug("llm_response", chars=len(content))
        return content
