"""Точка входа: цикл поллинга Twitch и рассылка уведомлений в Telegram."""
import asyncio
import logging
import os
import random
import signal
import time

import aiohttp
from aiogram import Bot
from dotenv import load_dotenv

from notifier import Notifier
from state import load_state, save_state
from twitch import TwitchClient

log = logging.getLogger("twitch-tg-notifier")

# Сколько подряд "оффлайн"-тиков нужно, чтобы поверить, что стрим реально завершён.
# Защищает от секундных провалов в Helix
OFFLINE_THRESHOLD = 2

# Размер картинки-превью, который подставляем в thumbnail_url вместо {width}x{height}
PREVIEW_SIZE = "1280x720"

# Варианты текста уведомления о старте - бот берёт случайный при каждом стриме.
# {url} подставляется ссылкой на канал.
ONLINE_TEXTS = [
    "🔴 Погнали! Я в эфире, залетайте → {url}",
    "🔴 Стрим подрубила! Врывайтесь → {url}",
    "🔴 Я онлайн, го смотреть → {url}",
    "🔴 Начали! Жду вас на стриме → {url}",
    "🔴 Эфир пошёл, заходите → {url}",
    "🔴 Всё, стримлю! Залетайте в гости → {url}",
    "🔴 Стрим стартанул, залетайте → {url}",
    "🔴 Я в эфире! Собираемся → {url}",
    "🔴 Врубила трансляцию, велком → {url}",
    "🔴 Погнали стрим! Кто со мной → {url}",
    "🔴 Онлайн! Заходите потусить → {url}",
    "🔴 Эфир открыт, залетайте на огонёк → {url}",
    "🔴 Начинаем! Занимайте места → {url}",
    "🔴 Стрим уже идёт, подтягивайтесь → {url}",
    "🔴 Я в деле, врывайтесь → {url}",
    "🔴 Трансляция пошла, го к нам → {url}",
    "🔴 Всё, погнали! Жду вас → {url}",
    "🔴 Эфирчик стартанул, залетайте → {url}",
    "🔴 Я стримлю! Не пропустите → {url}",
    "🔴 Онлайн и жду именно вас → {url}",
]


def _setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _parse_chat_ids(raw: str) -> list[int]:
    """Парсит '123,-100456' -> [123, -100456]. Пустые элементы игнорим."""
    out = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def _msg_online(login: str) -> str:
    """Случайный текст из ONLINE_TEXTS с подставленной ссылкой."""
    url = f"https://twitch.tv/{login}"
    return random.choice(ONLINE_TEXTS).format(url=url)


def _preview_url(stream: dict) -> str | None:
    """
    Собирает URL кадра эфира из thumbnail_url.
    Twitch отдаёт шаблон с {width}x{height} - подставляем размер.
    Дописываем ?t=<unix> чтобы Telegram не подсунул старую версию из своего кэша
    (у картинки постоянный адрес, обновляется раз в ~5 мин).
    """
    tpl = stream.get("thumbnail_url")
    if not tpl:
        return None
    # thumbnail_url вида .../preview-{width}x{height}.jpg -> подставляем размер
    url = tpl.replace("{width}x{height}", PREVIEW_SIZE)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={int(time.time())}"


async def _fetch_preview(session: aiohttp.ClientSession, url: str) -> bytes | None:
    """Скачивает кадр превью с Twitch. None - если не вышло (шлём тогда текстом)."""
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                log.warning("Превью недоступно, HTTP %s", resp.status)
                return None
            data = await resp.read()
            if not data:
                log.warning("Превью пустое")
                return None
            return data
    except Exception as e:
        log.warning("Не смог скачать превью: %s", e)
        return None


async def tick(
    session: aiohttp.ClientSession,
    twitch: TwitchClient,
    notifier: Notifier,
    login: str,
    preview_delay: int,
) -> None:
    """Один цикл проверки: сравниваем Twitch с локальным state и шлём дельту."""
    state = load_state()

    try:
        stream = await twitch.get_stream(login)
    except Exception as e:
        log.error("Ошибка запроса к Twitch: %s", e)
        return

    if stream is not None:
        # Канал онлайн
        new_stream_id = stream.get("id")
        if not state["is_live"] or state.get("stream_id") != new_stream_id:
            # Переход offline -> online (или новый стрим с другим id)
            log.info("Обнаружен старт стрима id=%s", new_stream_id)

            # Записываем состояние ДО задержки и отправки: если бот упадёт/перезапустится
            # во время ожидания превью - при следующем старте не будет дубля уведомления.
            state.update({
                "is_live": True,
                "stream_id": new_stream_id,
                "offline_misses": 0,
            })
            save_state(state)

            if preview_delay > 0:
                # Твич обновляет кадр эфира раз в ~5 мин: в первые секунды там старый/пустой
                # кадр. Ждём, потом перезапрашиваем стрим ради свежего thumbnail.
                log.info("Жду %d с ради свежего кадра превью", preview_delay)
                await asyncio.sleep(preview_delay)
                try:
                    fresh = await twitch.get_stream(login)
                    if fresh and fresh.get("id") == new_stream_id:
                        stream = fresh  # свежий thumbnail
                except Exception as e:
                    log.warning("Не смог обновить данные перед постом: %s", e)

            preview_url = _preview_url(stream)
            caption = _msg_online(login)
            photo_bytes = await _fetch_preview(session, preview_url) if preview_url else None
            if photo_bytes:
                await notifier.broadcast_photo(photo_bytes, caption)
            else:
                # Нет/не скачался кадр - шлём текстом (без link-preview, чтоб не вылезла аватарка)
                await notifier.broadcast(caption)
        # Уже онлайн (или только что отпостили) - обновим state, ничего не шлём
        state["offline_misses"] = 0
        save_state(state)
        return

    # stream is None - Helix говорит, что канал оффлайн.
    # Завершение стрима подписчикам не постим, просто гасим флаг после подтверждения.
    if state["is_live"]:
        misses = state.get("offline_misses", 0) + 1
        if misses >= OFFLINE_THRESHOLD:
            log.info("Стрим завершён (после %d оффлайн-тиков), уведомление не шлю", misses)
            state.update({
                "is_live": False,
                "stream_id": None,
                "offline_misses": 0,
            })
        else:
            # Один промах - ждём следующий тик
            state["offline_misses"] = misses
            log.debug("Оффлайн-промах %d/%d, жду подтверждения", misses, OFFLINE_THRESHOLD)
        save_state(state)


async def main() -> None:
    load_dotenv()
    _setup_logging()

    tg_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_ids = _parse_chat_ids(os.environ["TELEGRAM_CHAT_IDS"])
    if not chat_ids:
        raise RuntimeError("TELEGRAM_CHAT_IDS пуст - некому слать уведомления")

    twitch_client_id = os.environ["TWITCH_CLIENT_ID"]
    twitch_client_secret = os.environ["TWITCH_CLIENT_SECRET"]
    login = os.getenv("TWITCH_LOGIN", "").strip().lower()
    if not login:
        raise RuntimeError("TWITCH_LOGIN пуст - укажи свой твич-ник в .env")
    poll_interval = int(os.getenv("POLL_INTERVAL", "60"))
    # Задержка перед постом ради свежего кадра превью (твич обновляет thumbnail ~раз в 5 мин)
    preview_delay = int(os.getenv("PREVIEW_DELAY", "150"))

    log.info(
        "Старт: канал=%s, интервал=%ds, задержка_превью=%ds, получателей=%d",
        login, poll_interval, preview_delay, len(chat_ids),
    )

    # Сигнальный flag для чистого выхода по SIGTERM/SIGINT
    stop_event = asyncio.Event()

    def _on_signal():
        log.info("Получен сигнал остановки")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _on_signal)
        except NotImplementedError:
            # Windows не поддерживает add_signal_handler - забиваем
            pass

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        twitch = TwitchClient(session, twitch_client_id, twitch_client_secret)
        bot = Bot(token=tg_token)
        try:
            notifier = Notifier(bot, chat_ids)
            while not stop_event.is_set():
                try:
                    await tick(session, twitch, notifier, login, preview_delay)
                except Exception as e:
                    # Никаких неперехваченных исключений в основной петле
                    log.exception("Ошибка в tick: %s", e)
                # Спим интервал, но просыпаемся раньше при сигнале
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            await bot.session.close()

    log.info("Остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
