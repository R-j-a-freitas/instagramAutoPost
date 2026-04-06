"""Provedor de imagens e vídeo: NVIDIA NIM."""
import base64
import logging
import time
from typing import Optional

import requests

from instagram_poster.config import (
    get_nvidia_api_key,
    get_nvidia_image_model,
    get_nvidia_video_model,
)

logger = logging.getLogger(__name__)

# Base URLs para NVIDIA NIM
_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NVIDIAProvider:
    def generate(self, prompt: str) -> bytes:
        """Gera uma imagem via NVIDIA NIM."""
        api_key = get_nvidia_api_key()
        if not api_key:
            raise ValueError("NVIDIA: API Key necessária para gerar imagem.")

        model_name = get_nvidia_image_model()
        # A maioria dos modelos de imagem no NVIDIA NIM segue o padrão generative
        invoke_url = f"{_NVIDIA_BASE_URL}/genai/{model_name}"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        
        # Payload padrão para modelos como Playground v2.5
        payload = {
            "prompt": prompt,
            "negative_prompt": "text, letters, words, watermark, blurry, low quality",
            "sampler": "K_EULER_ANCESTRAL",
            "steps": 25,
            "cfg_scale": 5,
            "width": 1024,
            "height": 1024,
        }

        logger.info("NVIDIA: a gerar imagem (modelo %s)...", model_name)
        
        # Em alguns NIMs, o endpoint pode estar sob v1/images/generations ou v1/genai/...
        # Tentamos primeiro o genai/... que é comum no portal NVIDIA Build
        try:
            resp = requests.post(invoke_url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 404:
                # Fallback para v1/images/generations (OpenAI compatible)
                logger.info("NVIDIA: genai endpoint 404, a tentar OpenAI-compatible API...")
                invoke_url = f"{_NVIDIA_BASE_URL}/images/generations"
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "size": "1024x1024",
                    "n": 1,
                    "response_format": "b64_json"
                }
                resp = requests.post(invoke_url, headers=headers, json=payload, timeout=120)
            
            resp.raise_for_status()
            data = resp.json()
            
            # Formatos variam entre b64_json, artifacts, ou "image" em base64
            if "artifacts" in data:
                b64_data = data["artifacts"][0]["base64"]
            elif "data" in data and isinstance(data["data"], list):
                b64_data = data["data"][0].get("b64_json") or data["data"][0].get("url")
                if b64_data and b64_data.startswith("http"):
                    return requests.get(b64_data).content
            elif "image" in data:
                b64_data = data["image"]
            else:
                # Às vezes está diretamente num campo b64_json root
                b64_data = data.get("b64_json")
                
            if not b64_data:
                raise ValueError(f"NVIDIA: Formato de resposta desconhecido: {data.keys()}")
            
            return base64.b64decode(b64_data)
        except Exception as e:
            logger.error("NVIDIA Image Error: %s", e)
            raise

    def generate_video(self, prompt: str, model: Optional[str] = None, aspect_ratio: str = "9:16", duration: int = 5) -> bytes:
        """
        Gera um vídeo via NVIDIA NIM (NVIDIA Cosmos 1.0 ou Stable Video Diffusion).
        """
        api_key = get_nvidia_api_key()
        if not api_key:
            raise ValueError("NVIDIA: API Key necessária para gerar vídeo.")

        model_name = model or get_nvidia_video_model()
        invoke_url = f"{_NVIDIA_BASE_URL}/genai/{model_name}"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        
        # Payload para NVIDIA Cosmos 1.0
        payload = {
            "prompt": prompt,
            "negative_prompt": "blurry, low quality, jittery",
            "video": "", # Campo necessário para alguns modelos Cosmos
        }

        logger.info("NVIDIA: a gerar vídeo (modelo %s)...", model_name)
        
        try:
            resp = requests.post(invoke_url, headers=headers, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            
            # Cosmos e modelos de vídeo costumam devolver campo "video" ou "artifacts"
            if "video" in data:
                b64_data = data["video"]
            elif "artifacts" in data:
                b64_data = data["artifacts"][0]["base64"]
            else:
                raise ValueError(f"NVIDIA Video: Formato de resposta desconhecido: {data.keys()}")
            
            return base64.b64decode(b64_data)
        except Exception as e:
            logger.error("NVIDIA Video Error: %s", e)
            raise
