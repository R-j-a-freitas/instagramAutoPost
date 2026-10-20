"""
Script de migração única: copia todos os posts da Google Sheet actual para a nova
base de dados interna (posts.db). A partir desta migração, a app passa a usar a BD
para ler e escrever posts — o Google Sheets deixa de ser necessário.

Corre: py -m scripts.migrate_sheets_to_db
(ou: python scripts/migrate_sheets_to_db.py)
Usa --force para reimportar mesmo que a BD já tenha posts (duplica linhas).
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Migra posts da Google Sheet para posts.db.")
    parser.add_argument("--force", action="store_true", help="Reimportar mesmo que a BD já tenha posts.")
    args = parser.parse_args()

    from instagram_poster import db
    from instagram_poster.sheets_client import get_upcoming_posts

    existing = db.get_all_posts()
    if existing and not args.force:
        print(f"A base de dados já tem {len(existing)} post(s). Usa --force para reimportar na mesma (duplica).")
        return

    print("A ler todas as linhas da Google Sheet...")
    rows = get_upcoming_posts(n=1_000_000, from_date=date(2000, 1, 1))
    if not rows:
        print("Nenhuma linha encontrada na Sheet. Nada para migrar.")
        return

    print(f"{len(rows)} linha(s) encontrada(s) na Sheet. A importar para posts.db...")
    payload = [
        {
            "date": r.get("date", ""),
            "time": r.get("time", ""),
            "image_text": r.get("image_text", ""),
            "caption": r.get("caption", ""),
            "gemini_prompt": r.get("gemini_prompt", ""),
            "status": r.get("status", ""),
            "published": r.get("published", ""),
            "image_url": r.get("image_url", ""),
            "image_prompt": r.get("image_prompt", ""),
            "post_type": r.get("post_type", "single"),
            "slide2_text": r.get("slide2_text", ""),
        }
        for r in rows
    ]
    count = db.append_rows(payload)
    print(f"Migração concluída: {count} posts importados para {db.DB_PATH}")


if __name__ == "__main__":
    main()
