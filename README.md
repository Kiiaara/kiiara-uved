# Twitch -> Telegram notifier (личный, с превью)

Копия основного нотифаера под мой личный канал. Поллит Helix API раз в минуту. Канал вышел в эфир - кидает в Telegram **фото-пост с кадром стрима** ("🔴 Я в эфире!" + название + категория + ссылка), закончил - "⚫ Стрим завершён".

Отличие от базового бота: при старте ждёт `PREVIEW_DELAY` секунд (по умолчанию 150), потом перезапрашивает стрим и постит свежий кадр эфира картинкой (`sendPhoto`). Твич обновляет thumbnail раз в ~5 мин, поэтому без паузы в первые минуты прилетел бы старый кадр. Если кадра нет - фолбэк на обычный текстовый пост со ссылкой.

## Что нужно
- Python 3.11+
- Telegram-бот (токен от @BotFather)
- Twitch app (Client ID + Secret) - https://dev.twitch.tv/console/apps

## Подготовка секретов

### Telegram
1. Пишешь @BotFather, `/newbot`, забираешь токен.
2. Узнаёшь chat_id:
   - Личка: пишешь своему боту любое сообщение, потом открываешь `https://api.telegram.org/bot<TOKEN>/getUpdates` - там в `chat.id` твой ID.
   - Канал/группа: добавляешь бота админом, постишь любое сообщение от бота, тот же `getUpdates` - chat_id канала будет с минусом (`-100...`).

### Twitch
1. https://dev.twitch.tv/console/apps -> Register Your Application.
2. OAuth Redirect URL - `http://localhost`, Category - `Application Integration`.
3. Забираешь Client ID и Client Secret.

## Локальный запуск
```bash
cp .env.example .env
# заполняешь .env

python -m venv .venv
.venv/bin/pip install -r requirements.txt   # Linux/Mac
.venv\Scripts\pip install -r requirements.txt  # Windows

python bot.py
```

## VPS (systemd)
```bash
# на сервере
sudo mkdir -p /opt/twitch-tg-notifier
sudo chown $USER /opt/twitch-tg-notifier

# заливаешь файлы проекта в /opt/twitch-tg-notifier
# (git clone, scp, rsync - как удобно)

cd /opt/twitch-tg-notifier
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env   # заполняешь

sudo cp systemd/twitch-notifier.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now twitch-notifier

# логи
journalctl -u twitch-notifier -f
```

## Конфиг (.env)
| Переменная | Что значит |
|---|---|
| `TELEGRAM_BOT_TOKEN` | токен от BotFather |
| `TELEGRAM_CHAT_IDS` | chat_id через запятую (личка + канал) |
| `TWITCH_CLIENT_ID` | Client ID Twitch app |
| `TWITCH_CLIENT_SECRET` | Client Secret Twitch app |
| `TWITCH_LOGIN` | твой логин канала (обязателен) |
| `POLL_INTERVAL` | интервал поллинга в секундах, дефолт 60 |
| `PREVIEW_DELAY` | пауза перед постом ради свежего кадра, сек, дефолт 150. 0 = постить сразу |
| `LOG_LEVEL` | DEBUG/INFO/WARNING, дефолт INFO |

## Состояние
Бот хранит состояние в `state.json` рядом со скриптом. Если перезапустить во время стрима - дублей не будет. Если хочешь "забыть" текущее состояние - удали этот файл.

## Проверить, что всё ок
```bash
# Twitch отдаёт данные?
curl -X POST "https://id.twitch.tv/oauth2/token?client_id=$TWITCH_CLIENT_ID&client_secret=$TWITCH_CLIENT_SECRET&grant_type=client_credentials"
# берёшь access_token из ответа
curl -H "Client-Id: $TWITCH_CLIENT_ID" -H "Authorization: Bearer $TOKEN" "https://api.twitch.tv/helix/streams?user_login=tpabomah"
```
Если в `data` пусто - канал оффлайн, если есть объект - онлайн.

Чтобы быстро проверить уведомление "запустился" не дожидаясь реального стрима - временно подставь в `TWITCH_LOGIN` любой канал, который сейчас стримит. Получишь сообщение в Telegram, потом верни обратно `tpabomah` и удали `state.json`.
