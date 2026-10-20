"""
Script para preencher o campo gemini_prompt na base de dados com descrições visuais
geradas por LLM a partir do Image Text de cada post.

A quote é convertida numa descrição de cena (sem texto) para que o modelo de
imagem gere apenas um fundo visual. O texto da quote é sobreposto depois via Pillow.

Corre: py -m scripts.update_gemini_prompts
(ou: python scripts/update_gemini_prompts.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    from instagram_poster.image_generator import _quote_to_scene_prompt
    from instagram_poster.db import get_all_rows_with_image_text, update_gemini_prompt

    rows = get_all_rows_with_image_text()
    if not rows:
        print("Nenhuma linha com Image Text encontrada.")
        return

    print(f"A converter quotes em descrições visuais para {len(rows)} linhas...")
    ok = 0
    for rec in rows:
        image_text = (rec.get("image_text") or "").strip()
        if not image_text:
            continue
        row_index = rec["row_index"]
        scene_prompt = _quote_to_scene_prompt(image_text)
        update_gemini_prompt(row_index, scene_prompt)
        ok += 1
        print(f"  Post {row_index} ({rec.get('date')}): OK")
    print(f"Concluído — {ok} linhas actualizadas.")


if __name__ == "__main__":
    main()
