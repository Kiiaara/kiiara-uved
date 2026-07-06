"""Рассылка сообщений в Telegram по списку chat_id."""
import logging
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

log = logging.getLogger(__name__)


def _watch_kb(url: str) -> InlineKeyboardMarkup:
    """Inline-кнопка 'Смотреть' со ссылкой на стрим."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Смотреть", url=url)]]
    )


class Notifier:
    def __init__(self, bot: Bot, chat_ids: Iterable[int]):
        self._bot = bot
        self._chat_ids = list(chat_ids)

    async def broadcast(self, text: str, url: str) -> list[dict]:
        """
        Шлёт текстовое сообщение с кнопкой 'Смотреть' во все chat_id.
        Возвращает [{chat_id, message_id}] успешно отправленных - для последующего удаления.
        Падение одного не валит остальных.
        """
        sent = []
        kb = _watch_kb(url)
        for chat_id in self._chat_ids:
            try:
                msg = await self._bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    # Не даём Telegram разворачивать link-preview: он подставляет
                    # аватарку канала вместо кадра эфира. Ссылка остаётся кликабельной.
                    disable_web_page_preview=True,
                    reply_markup=kb,
                )
                sent.append({"chat_id": chat_id, "message_id": msg.message_id})
                log.info("Сообщение отправлено в chat_id=%s (msg_id=%s)", chat_id, msg.message_id)
            except TelegramAPIError as e:
                # Бот забанен/чат удалён/нет прав - логируем и едем дальше
                log.error("Не удалось отправить в chat_id=%s: %s", chat_id, e)
        return sent

    async def broadcast_photo(self, photo_bytes: bytes, caption: str, url: str) -> list[dict]:
        """
        Шлёт фото-пост (превью стрима) с подписью и кнопкой 'Смотреть' во все chat_id.
        Картинку принимаем уже скачанной (bytes) и заливаем файлом - так Telegram
        не идёт качать её сам по URL (это капризно и ловит таймауты).
        Если фото не отправилось - падаем на текстовый пост, чтобы уведомление
        всё равно ушло, а не потерялось.
        Возвращает [{chat_id, message_id}] успешно отправленных - для удаления.
        """
        sent = []
        kb = _watch_kb(url)
        for chat_id in self._chat_ids:
            # Свежий InputFile на каждый чат: один и тот же переиспользовать нельзя
            # (буфер вычитывается при первой отправке).
            photo = BufferedInputFile(photo_bytes, filename="preview.jpg")
            try:
                msg = await self._bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
                sent.append({"chat_id": chat_id, "message_id": msg.message_id})
                log.info("Фото-пост отправлен в chat_id=%s (msg_id=%s)", chat_id, msg.message_id)
            except TelegramAPIError as e:
                # Нет прав/чат недоступен - не теряем уведомление, шлём текстом без превью
                log.error("Фото не ушло в chat_id=%s (%s), шлю текстом", chat_id, e)
                try:
                    msg = await self._bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=kb,
                    )
                    sent.append({"chat_id": chat_id, "message_id": msg.message_id})
                    log.info("Текстовый фолбэк отправлен в chat_id=%s (msg_id=%s)", chat_id, msg.message_id)
                except TelegramAPIError as e2:
                    log.error("И текст не ушёл в chat_id=%s: %s", chat_id, e2)
        return sent

    async def delete_messages(self, messages: Iterable[dict]) -> None:
        """
        Удаляет ранее отправленные посты (при завершении стрима).
        messages - список {chat_id, message_id}. Ошибку одного глотаем:
        пост мог быть удалён вручную или протух (>48ч Telegram уже не даст удалить).
        """
        for m in messages:
            chat_id, message_id = m.get("chat_id"), m.get("message_id")
            if chat_id is None or message_id is None:
                continue
            try:
                await self._bot.delete_message(chat_id=chat_id, message_id=message_id)
                log.info("Пост удалён в chat_id=%s (msg_id=%s)", chat_id, message_id)
            except TelegramAPIError as e:
                log.warning("Не удалил пост в chat_id=%s (msg_id=%s): %s", chat_id, message_id, e)
