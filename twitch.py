"""Клиент Twitch Helix API: app access token + получение стримов."""
import logging
import time
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)

OAUTH_URL = "https://id.twitch.tv/oauth2/token"
HELIX_STREAMS = "https://api.twitch.tv/helix/streams"


class TwitchClient:
    def __init__(self, session: aiohttp.ClientSession, client_id: str, client_secret: str):
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0  # unix-время истечения

    async def _get_token(self) -> str:
        """Возвращает кешированный токен или запрашивает новый."""
        # Запас в 60 секунд, чтобы не словить 401 на границе
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        params = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }
        async with self._session.post(OAUTH_URL, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

        self._token = data["access_token"]
        # expires_in в секундах, обычно ~5184000 (60 дней)
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        log.info("Twitch app access token обновлён")
        return self._token

    async def get_stream(self, login: str) -> Optional[dict]:
        """
        Возвращает объект стрима (dict) или None если канал оффлайн.
        На 401 - сбрасывает токен и пробует ещё раз (один повтор).
        """
        for attempt in (1, 2):
            token = await self._get_token()
            headers = {
                "Client-Id": self._client_id,
                "Authorization": f"Bearer {token}",
            }
            params = {"user_login": login}
            async with self._session.get(HELIX_STREAMS, headers=headers, params=params) as resp:
                if resp.status == 401 and attempt == 1:
                    # Токен протух раньше времени - сбрасываем и идём на второй круг
                    log.warning("Helix вернул 401, перезапрашиваю токен")
                    self._token = None
                    self._token_expires_at = 0.0
                    continue
                resp.raise_for_status()
                payload = await resp.json()

            data = payload.get("data") or []
            return data[0] if data else None

        return None
