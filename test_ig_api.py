import logging
import sys
import os
from pathlib import Path

from instagram_poster import ig_client
from dotenv import load_dotenv

# Configura logging para ver os detalhes
logging.basicConfig(level=logging.INFO)

def test_instagram_post():
    load_dotenv()
    
    # URL de imagem pública garantida
    test_image_url = "https://loremflickr.com/1080/1080/nature"
    test_caption = "Teste de integração Instagram API via Antigravity #test"
    
    print(f"--- Testando publicação com URL: {test_image_url} ---")
    
    try:
        creation_id = ig_client.create_media(image_url=test_image_url, caption=test_caption)
        print(f"SUCESSO: Media container criado com ID: {creation_id}")
    except Exception as e:
        print(f"ERRO: Falha no teste: {e}")

if __name__ == "__main__":
    test_instagram_post()
