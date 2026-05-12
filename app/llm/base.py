from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system: str, user: str) -> str:
        """Send a system + user prompt, return the raw text response."""
