"""
Lógica de escolha do próximo post e de publicação.
Acionado por botão na UI (sem cron nem loops dentro do Streamlit).
"""
import logging
from datetime import date, datetime, time
from typing import Any, Literal, Optional

from instagram_poster import ig_client, sheets_client

logger = logging.getLogger(__name__)


def select_post_to_publish(
    mode: Literal["next", "row"],
    row_index: Optional[int] = None,
    today: Optional[date] = None,
    now: Optional[time] = None,
) -> Optional[dict[str, Any]]:
    """
    Seleciona o post a publicar.
    - mode="next": usa get_next_ready_post(today, now).
    - mode="row": usa a linha específica row_index (1-based; 2 = primeira linha de dados).
    Devolve o dicionário do post (com row_index, image_url, caption, etc.) ou None.
    """
    if mode == "next":
        return sheets_client.get_next_ready_post(today=today or date.today(), now=now or datetime.now().time())
    if mode == "row":
        if row_index is None:
            raise ValueError("Para mode='row' é obrigatório indicar row_index.")
        return sheets_client.get_row_by_index(row_index)
    raise ValueError("mode deve ser 'next' ou 'row'")


def publish_post(post: dict[str, Any]) -> str:
    """
    Publica um post no Instagram e marca o Sheet como publicado.
    - post: dicionário com image_url (opcional), image_text, caption, row_index.
    - Se image_url estiver vazio e image_text existir, gera a imagem com Gemini (Nano Banana)
      e faz upload para Cloudinary para obter um URL público.
    - Devolve o media_id do post publicado.
    """
    image_url = (post.get("image_url") or "").strip()
    image_text = (post.get("image_text") or "").strip()
    caption = (post.get("caption") or "").strip()
    row_index = post.get("row_index")
    if row_index is None:
        raise ValueError("O post não tem row_index (linha do Sheet).")

    if not image_url and image_text:
        try:
            from instagram_poster import image_generator
            image_url = image_generator.get_image_url_from_sheet_description(
                image_text, public_id_prefix=f"keepcalm_{row_index}"
            )
        except Exception as e:
            raise ValueError(
                f"Imagem gerada pela Gemini mas falha ao obter URL público: {e}. "
                "Preenche ImageURL no Sheet ou configura CLOUDINARY_URL no .env."
            ) from e
    if not image_url:
        raise ValueError(
            "O post não tem ImageURL no Sheet. Preenche a coluna ImageURL com um link da imagem "
            "ou deixa vazio e garante que Image Text está preenchido e que GEMINI_API_KEY e CLOUDINARY_URL estão no .env."
        )

    creation_id = ig_client.create_media(image_url=image_url, caption=caption)
    media_id = ig_client.publish_media(creation_id)
    sheets_client.mark_published(row_index)
    return media_id


def run_publish_next(today: Optional[date] = None, now: Optional[time] = None) -> tuple[bool, str, Optional[str]]:
    """
    Publica o próximo post (ready, não publicado, Date <= hoje).
    Devolve (sucesso, mensagem, media_id ou None).
    """
    post = select_post_to_publish(mode="next", today=today, now=now)
    if not post:
        return False, "Nenhum post pronto para publicar (Status=ready, Published vazio, Date <= hoje).", None
    try:
        media_id = publish_post(post)
        return True, f"Post publicado com sucesso. Media ID: {media_id}", media_id
    except Exception as e:
        logger.exception("Erro ao publicar próximo post")
        return False, str(e), None


def run_publish_row(row_index: int) -> tuple[bool, str, Optional[str]]:
    """
    Publica o post da linha row_index (1-based).
    Devolve (sucesso, mensagem, media_id ou None).
    """
    post = select_post_to_publish(mode="row", row_index=row_index)
    if not post:
        return False, f"Linha {row_index} não encontrada ou inválida.", None
    try:
        media_id = publish_post(post)
        return True, f"Post publicado com sucesso. Media ID: {media_id}", media_id
    except Exception as e:
        logger.exception("Erro ao publicar post da linha %s", row_index)
        return False, str(e), None
