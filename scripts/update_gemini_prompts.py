"""
Script para preencher a coluna Gemini_Prompt no Sheet com prompts técnicos
gerados a partir do Image Text de cada linha.

Requisitos: .env com GOOGLE_SERVICE_ACCOUNT_JSON e IG_SHEET_ID.

Corre: py -m scripts.update_gemini_prompts
(ou: python scripts/update_gemini_prompts.py)
"""
import sys
from pathlib import Path

# Garantir que o projeto está no path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Template de prompt para quote cards (igual ao usado no image_generator)
GEMINI_PROMPT_TEMPLATE = (
    "Create a single square or 4:5 vertical image for Instagram. "
    "The image must display this text clearly and prominently as the main content, "
    "like a motivational or affirmation quote card: \"{text}\". "
    "Use a clean, modern design with readable typography. "
    "Style: minimalist, positive, soft colors or gradient background. "
    "Do not add extra sentences, only the given text must appear."
)


def main():
    from instagram_poster.sheets_client import get_all_rows_with_image_text, update_gemini_prompt

    rows = get_all_rows_with_image_text()
    if not rows:
        print("Nenhuma linha com Image Text encontrada.")
        return

    print(f"A preencher Gemini_Prompt para {len(rows)} linhas...")
    for rec in rows:
        image_text = (rec.get("image_text") or "").strip()
        if not image_text:
            continue
        row_index = rec["row_index"]
        prompt = GEMINI_PROMPT_TEMPLATE.format(text=image_text)
        update_gemini_prompt(row_index, prompt)
        print(f"  Linha {row_index} ({rec.get('date')}): OK")
    print("Concluído.")


if __name__ == "__main__":
    main()
