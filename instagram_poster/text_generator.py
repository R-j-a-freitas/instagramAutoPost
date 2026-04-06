import logging
import requests
from typing import Optional

import os
from instagram_poster import config
# Fallback se as funções não existirem (cache/shadowing)
if not hasattr(config, "get_text_provider"):
    def _tp(): return (os.getenv("TEXT_PROVIDER") or config.get_runtime_override("TEXT_PROVIDER") or "pollinations").strip()
    config.get_text_provider = _tp
if not hasattr(config, "get_nvidia_api_key"):
    def _nk(): return (os.getenv("NVIDIA_API_KEY") or config.get_runtime_override("NVIDIA_API_KEY") or "").strip()
    config.get_nvidia_api_key = _nk
if not hasattr(config, "get_pollinations_api_key"):
    def _pk(): return (os.getenv("POLLINATIONS_API_KEY") or config.get_runtime_override("POLLINATIONS_API_KEY") or "").strip()
    config.get_pollinations_api_key = _pk

from instagram_poster.config import get_text_provider, get_nvidia_api_key, get_pollinations_api_key

logger = logging.getLogger(__name__)

def generate_text(system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """
    Gera texto usando o provedor configurado (NVIDIA Kimi ou Pollinations).
    Se json_mode for True, força o output como JSON válido (para a geração de conteúdo em lote).
    """
    provider = get_text_provider()
    
    if json_mode and provider == "nvidia_kimi":
        system_prompt += "\nIMPORTANT: You must return ONLY a JSON object. Do not wrap it in markdown block quotes (```json). Just the raw JSON format."
        
    if provider == "nvidia_kimi":
        logger.info("Routing text request to NVIDIA Kimi API.")
        return _generate_with_nvidia(system_prompt, user_prompt, json_mode)
    else:
        logger.info("Routing text request to Pollinations API.")
        return _generate_with_pollinations(system_prompt, user_prompt, json_mode)

def _generate_with_nvidia(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    api_key = get_nvidia_api_key()
    if not api_key:
        raise ValueError("A NVIDIA_API_KEY não está configurada para o provedor de texto NVIDIA.")

    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": "moonshotai/kimi-k2.5",
        "messages": messages,
        "max_tokens": 8192,
        "temperature": 1.0,
        "top_p": 1.0,
        "stream": False,
        "chat_template_kwargs": {"thinking": True}
    }

    logger.info("NVIDIA Kimi: A gerar texto...")
    resp = requests.post(url, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    
    # Kimi sometimes still outputs markdown blocks, strip them safely
    if json_mode:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
    return content

def _generate_with_pollinations(system_prompt: str, user_prompt: str, json_mode: bool) -> str:
    api_key = get_pollinations_api_key()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": "openai",
        "messages": messages,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    logger.info("Pollinations: A gerar texto...")
    resp = requests.post(
        "https://gen.pollinations.ai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=180,
    )
    resp.raise_for_status()
    
    data = resp.json()
    return data["choices"][0]["message"]["content"]
