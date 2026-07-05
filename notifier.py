"""Рассылка сообщений в Telegram по списку chat_id."""
import logging
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import URLInputFile

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bot: Bot, chat_ids: Iterable[int]):
        self._bot = bot
        self._chat_ids = list(chat_ids)

    async def broadcast(self, text: str) -> None:
        """Шлёт текстовое сообщение во все chat_id. Падение одного не валит остальных."""
        for chat_id in self._chat_ids:
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
                log.info("Сообщение отправлено в chat_id=%s", chat_id)
            except TelegramAPIError as e:
                # Бот забанен/чат удалён/нет прав - логируем и едем дальше
                log.error("Не удалось отправить в chat_id=%s: %s", chat_id, e)

    async def broadcast_photo(self, photo_url: str, caption: str) -> None:
        """
        Шлёт фото-пост (превью стрима) с подписью во все chat_id.
        Если фото не отправилось - падаем на текстовый пост, чтобы уведомление
        всё равно ушло, а не потерялось.
        """
        photo = URLInputFile(photo_url)
        for chat_id in self._chat_ids:
            try:
                await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                )
                log.info("Фото-пост отправлен в chat_id=%s", chat_id)
            except TelegramAPIError as e:
                # Твич отдал битую/пустую картинку либо нет прав - не теряем уведомление
                log.error("Фото не ушло в chat_id=%s (%s), шлю текстом", chat_id, e)
                try:
                    await self._bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="HTML",
                        disable_web_page_preview=False,
                    )
                    log.info("Текстовый фолбэк отправлен в chat_id=%s", chat_id)
                except TelegramAPIError as e2:
                    log.error("И текст не ушёл в chat_id=%s: %s", chat_id, e2)
