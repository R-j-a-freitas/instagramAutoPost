"""
Registo de provedores de geração de imagens.
Cada provedor expõe generate(prompt: str) -> bytes (PNG).
"""
from typing import Protocol

AVAILABLE_PROVIDERS = {
    "gemini": "Gemini (Google – free tier)",
    "openai": "OpenAI DALL-E 3",
    "pollinations": "Pollinations (grátis)",
    "huggingface": "Hugging Face (free tier, créditos limitados)",
    "firefly": "Adobe Firefly",
}


class ImageProvider(Protocol):
    def generate(self, prompt: str) -> bytes: ...


def get_provider(name: str) -> ImageProvider:
    """Devolve a instância do provedor pelo nome."""
    name = (name or "").strip().lower()
    if name == "gemini":
        from instagram_poster.providers.provider_gemini import GeminiProvider
        return GeminiProvider()
    if name == "openai":
        from instagram_poster.providers.provider_openai import OpenAIProvider
        return OpenAIProvider()
    if name == "pollinations":
        from instagram_poster.providers.provider_pollinations import PollinationsProvider
        return PollinationsProvider()
    if name == "huggingface":
        from instagram_poster.providers.provider_huggingface import HuggingFaceProvider
        return HuggingFaceProvider()
    if name == "firefly":
        from instagram_poster.providers.provider_firefly import FireflyProvider
        return FireflyProvider()
    raise ValueError(
        f"Provedor de imagem desconhecido: '{name}'. "
        f"Opções: {', '.join(AVAILABLE_PROVIDERS.keys())}"
    )
