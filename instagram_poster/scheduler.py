"""
Lógica de escolha do próximo post e de publicação.
Acionado por botão na UI (sem cron nem loops dentro do Streamlit).
"""
import logging
import time as _time
from datetime import date, datetime, time
from typing import Any, Literal, Optional

from instagram_poster import ig_client, sheets_client
from instagram_poster.config import get_autopublish_story_with_post, get_image_provider
from instagram_poster.providers import AVAILABLE_PROVIDERS

logger = logging.getLogger(__name__)

_SHEET_UPDATE_RETRIES = 3
_SHEET_UPDATE_RETRY_DELAY_SEC = 2


def _update_sheet_after_publish(row_index: int, image_url: str) -> None:
    """
    Marca a linha como publicada e atualiza ImageURL no Sheet, com retry.
    Se falhar após todos os retries, regista o erro em log (e no autopublish se disponível)
    mas não levanta exceção — o post já foi publicado no Instagram.
    """
    last_error = None
    for attempt in range(1, _SHEET_UPDATE_RETRIES + 1):
        try:
            sheets_client.mark_published(row_index)
            sheets_client.update_image_url(row_index, image_url)
            logger.info("Sheet atualizado: linha %s -> Published=yes, ImageURL (tentativa %s)", row_index, attempt)
            return
        except Exception as e:
            last_error = e
            logger.warning("Falha a atualizar Sheet (linha %s, tentativa %s/%s): %s", row_index, attempt, _SHEET_UPDATE_RETRIES, e)
            if attempt < _SHEET_UPDATE_RETRIES:
                _time.sleep(_SHEET_UPDATE_RETRY_DELAY_SEC)
    msg = (
        f"Sheet não atualizado após {_SHEET_UPDATE_RETRIES} tentativas (linha {row_index}). "
        f"O post foi publicado no Instagram. Marca manualmente Published=yes e ImageURL na linha {row_index}. Erro: {last_error}"
    )
    logger.error(msg)
    try:
        from instagram_poster import autopublish
        autopublish._add_log_entry(False, msg, entry_type="error")
    except Exception:
        pass


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
    - post: dicionário com image_url (opcional), gemini_prompt, image_text, caption, row_index.
    - Se image_url estiver vazio, gera a imagem com o provedor activo usando Gemini_Prompt (ou Image Text como fallback)
      e faz upload para Cloudinary para obter um URL público.
    - Devolve o media_id do post publicado.
    """
    image_url = (post.get("image_url") or "").strip()
    gemini_prompt = (post.get("gemini_prompt") or "").strip()
    image_text = (post.get("image_text") or "").strip()
    caption = (post.get("caption") or "").strip()
    row_index = post.get("row_index")
    if row_index is None:
        raise ValueError("O post não tem row_index (linha do Sheet).")

    if not image_url and (gemini_prompt or image_text):
        provider_name = get_image_provider()
        provider_label = AVAILABLE_PROVIDERS.get(provider_name, provider_name)
        try:
            from instagram_poster import image_generator
            image_url = image_generator.get_image_url_from_prompt(
                prompt=gemini_prompt or image_text,
                quote_text=image_text,
                use_full_prompt=bool(gemini_prompt),
                public_id_prefix=f"keepcalm_{row_index}",
            )
        except Exception as e:
            raise ValueError(
                f"Falha ao gerar imagem com {provider_label}: {e}. "
                "Verifica as credenciais na Configuração ou preenche ImageURL no Sheet."
            ) from e
    if not image_url:
        provider_name = get_image_provider()
        provider_label = AVAILABLE_PROVIDERS.get(provider_name, provider_name)
        raise ValueError(
            f"O post não tem ImageURL no Sheet. Preenche ImageURL ou configura "
            f"o provedor de imagens ({provider_label}) na página Configuração."
        )

    creation_id = ig_client.create_media(image_url=image_url, caption=caption)
    media_id = ig_client.publish_media(creation_id)
    _update_sheet_after_publish(row_index, image_url)

    # Publicar Story automaticamente com o mesmo conteúdo, se activado
    if get_autopublish_story_with_post():
        try:
            from instagram_poster import autopublish, image_generator
            story_url = image_generator.get_story_image_url_from_feed_image(image_url)
            story_creation_id = ig_client.create_story(image_url=story_url)
            story_media_id = ig_client.publish_media(story_creation_id, max_wait=180)
            autopublish.log_story_published(post, media_id=story_media_id)
            logger.info("Story publicada automaticamente (post linha %s)", row_index)
        except Exception as e:
            logger.warning("Falha ao publicar Story automatica (post linha %s): %s", row_index, e)

    return media_id


def publish_story_from_post(post: dict[str, Any]) -> tuple[bool, str, Optional[str]]:
    """
    Gera e publica uma Story no Instagram a partir da imagem de um post (feed).
    Post deve ter image_url preenchido. Devolve (sucesso, mensagem, media_id ou None).
    """
    image_url = (post.get("image_url") or "").strip()
    if not image_url:
        return False, "O post não tem ImageURL.", None
    try:
        from instagram_poster import autopublish, image_generator
        story_url = image_generator.get_story_image_url_from_feed_image(image_url)
        creation_id = ig_client.create_story(image_url=story_url)
        media_id = ig_client.publish_media(creation_id, max_wait=180)
        autopublish.log_story_published(post, media_id=media_id)
        return True, f"Story publicada. Media ID: {media_id}", media_id
    except Exception as e:
        logger.exception("Erro ao publicar Story a partir do post")
        return False, str(e), None


def run_publish_next(
    today: Optional[date] = None, now: Optional[time] = None,
) -> tuple[bool, str, Optional[str], Optional[dict[str, Any]]]:
    """
    Publica o próximo post (ready, não publicado, Date <= hoje).
    Devolve (sucesso, mensagem, media_id ou None, post_data ou None).
    """
    post = select_post_to_publish(mode="next", today=today, now=now)
    if not post:
        return False, "Nenhum post pronto para publicar (Status=ready, Published vazio, Date <= hoje).", None, None
    row_index = post.get("row_index")
    # Re-leitura opcional: evita republicar se o Sheet foi atualizado por outro processo
    fresh = sheets_client.get_row_by_index(row_index)
    if fresh and (str(fresh.get("published") or "").strip().lower() in ("yes", "y", "1", "true")):
        logger.info("Linha %s já está publicada no Sheet; a ignorar para evitar duplicado.", row_index)
        return False, f"Linha {row_index} já está publicada no Sheet. Pode ter sido atualizada por outro processo.", None, post
    post_date = post.get("date", "")
    post_time = post.get("time", "")
    logger.info("A publicar post: linha %s, agendado para %s %s", row_index, post_date, post_time)
    try:
        media_id = publish_post(post)
        logger.info("Post publicado: linha %s, media_id=%s", row_index, media_id)
        return True, f"Post publicado com sucesso. Media ID: {media_id}", media_id, post
    except Exception as e:
        logger.exception("Erro ao publicar próximo post (linha %s): %s", row_index, e)
        return False, str(e), None, post


def run_publish_row(row_index: int) -> tuple[bool, str, Optional[str], Optional[dict[str, Any]]]:
    """
    Publica o post da linha row_index (1-based).
    Devolve (sucesso, mensagem, media_id ou None, post_data ou None).
    """
    post = select_post_to_publish(mode="row", row_index=row_index)
    if not post:
        return False, f"Linha {row_index} não encontrada ou inválida.", None, None
    try:
        media_id = publish_post(post)
        return True, f"Post publicado com sucesso. Media ID: {media_id}", media_id, post
    except Exception as e:
        logger.exception("Erro ao publicar post da linha %s", row_index)
        return False, str(e), None, post
