"""
The provider interface. Every AI provider (Gemini, Groq later) must implement
this same `generate` method. This is what lets the Gateway treat all providers
the same way — the heart of vendor independence.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GenerationResult:
    """A uniform result shape, no matter which provider produced it."""
    text: str
    tokens: int
    provider: str
    model: str


class AIProvider(ABC):
    name: str

    @abstractmethod
    async def generate(self, messages: list[dict]) -> GenerationResult:
        """
        messages: a list like [{"role": "user", "content": "..."}, ...]
        Returns a GenerationResult.
        """
        ...