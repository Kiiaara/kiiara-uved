# 🏗️ Twitch→Telegram Notifier Architecture

## Overview

Python-based event poller that monitors Twitch stream status and sends live notifications to Telegram with screenshot preview.

---

## 🔄 System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Twitch Helix API                      │
│         (stream status, thumbnail, metadata)             │
└─────────────────────────────┬──────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────┐
│               Python Bot (bot.py)                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. Stream Poller (every 60s)                           │
│     └─ Check is_live status                            │
│                                                          │
│  2. State Manager (state.json)                          │
│     └─ Track previous status (avoid duplicates)        │
│                                                          │
│  3. Preview Downloader (if online)                      │
│     └─ Wait PREVIEW_DELAY seconds                      │
│     └─ Fetch fresh thumbnail from Twitch              │
│                                                          │
│  4. Message Formatter                                   │
│     ├─ Title: 🔴 LIVE or ⚫ OFFLINE                    │
│     ├─ Metadata: category, viewers                     │
│     └─ Link: https://twitch.tv/channel                │
│                                                          │
└─────────┬────────────────────────────────────┬──────────┘
          │                                    │
          ▼                                    ▼
┌────────────────────┐              ┌─────────────────────┐
│  Telegram API      │              │   local state.json  │
│  sendPhoto() for   │              │                     │
│  screenshot        │              │  {                  │
│  sendMessage() for │              │    "is_live": true  │
│  fallback text     │              │  }                  │
└────────────────────┘              └─────────────────────┘
```

---

## 📊 Flow Diagram

```
START
  │
  ├─ Load config (.env)
  ├─ Load state.json (last status)
  │
  └─ Loop every POLL_INTERVAL seconds:
      │
      ├─ GET /helix/streams?user_login=channel
      │
      ├─ Check response:
      │   ├─ data[] empty → stream OFFLINE
      │   └─ data[] has item → stream ONLINE
      │
      ├─ Compare with state.json:
      │   ├─ NEW ONLINE:
      │   │   ├─ Wait PREVIEW_DELAY seconds (for fresh thumbnail)
      │   │   ├─ Download thumbnail image from stream_thumbnail_url
      │   │   ├─ sendPhoto(preview) to Telegram
      │   │   ├─ Fallback: sendMessage(text) if image fails
      │   │   └─ Save state: is_live=true
      │   │
      │   ├─ NEW OFFLINE:
      │   │   ├─ sendMessage("⚫ Стрим завершён") to Telegram
      │   │   └─ Save state: is_live=false
      │   │
      │   └─ No change:
      │       └─ Do nothing (sleep)
      │
      └─ Repeat
```

---

## 🔐 Authentication Flow

### Twitch OAuth2
```
┌─────────────────────────────────────────┐
│   1. Bot starts                         │
├─────────────────────────────────────────┤
│   2. POST /oauth2/token                 │
│      ├─ client_id (from .env)          │
│      ├─ client_secret (from .env)      │
│      └─ grant_type=client_credentials  │
│                                         │
│   3. Response: access_token (valid 1h) │
│                                         │
│   4. Cache token in memory              │
│      (auto-refresh on expiry)          │
└─────────────────────────────────────────┘
```

### Telegram Bot
```
┌──────────────────────────┐
│  setWebhook() [optional] │
│  OR polling (simpler)    │
│                          │
│  sendPhoto/sendMessage   │
│  ├─ chat_id: user/group  │
│  ├─ media: image (binary)│
│  └─ text: HTML formatted │
└──────────────────────────┘
```

---

## 📁 File Structure

```
kiiara-uved/
├── bot.py                    (300+ lines, main logic)
├── requirements.txt          (python-telegram-bot, requests)
├── .env.example             (config template)
├── state.json               (runtime state, auto-created)
├── README.md                (setup guide)
├── LICENSE                  (MIT)
├── .gitignore               (excludes .env, state.json)
└── systemd/
    └── twitch-notifier.service  (Linux auto-start)
```

---

## 🔧 Configuration

### Environment Variables
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF  # From @BotFather
TELEGRAM_CHAT_IDS=-100xxx,327xxx   # Multiple chat IDs
TWITCH_CLIENT_ID=abc123xyz         # From Twitch Dev Console
TWITCH_CLIENT_SECRET=xyz789abc     # From Twitch Dev Console
TWITCH_LOGIN=kiiaara              # Channel to monitor
POLL_INTERVAL=60                   # Check every 60 seconds
PREVIEW_DELAY=150                  # Wait 150s for fresh thumbnail
LOG_LEVEL=INFO                     # DEBUG/INFO/WARNING/ERROR
```

### State File (state.json)
```json
{
  "is_live": false,
  "last_checked": "2026-09-17T12:00:00Z",
  "last_title": "Gaming Session",
  "thumbnail_url": "https://static-cdn.jtvnw.net/..."
}
```

---

## 🚀 Deployment Options

### Local Development
```bash
python bot.py  # Runs in foreground, Ctrl+C to stop
```

### Linux (systemd)
```bash
# Service runs in background, auto-restarts on failure
sudo systemctl start twitch-notifier
sudo systemctl status twitch-notifier
journalctl -u twitch-notifier -f  # View logs
```

### Docker
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "bot.py"]
```

### Windows Service
```batch
# Use NSSM (Non-Sucking Service Manager)
nssm install TwitchNotifier "C:\path\to\python.exe" "C:\path\to\bot.py"
nssm start TwitchNotifier
```

---

## 🔄 Error Handling

| Error | Recovery |
|-------|----------|
| Twitch API down | Retry next cycle (no alert) |
| Invalid token | Refresh OAuth2 token |
| Telegram unreachable | Log error, continue polling |
| Image download fails | Fallback to text message |
| state.json corrupted | Recreate with default values |

---

## ⚡ Performance

| Metric | Value |
|--------|-------|
| API call latency | 500ms-2s |
| Thumbnail download | 2-5s (if fresh) |
| Telegram send | 500ms-1s |
| Memory usage | ~50MB |
| CPU usage | <5% (between polls) |

---

## 🔐 Security

- ✅ Secrets in `.env` (never in code)
- ✅ `.env` in `.gitignore`
- ✅ OAuth2 tokens cached in memory only
- ✅ state.json has no sensitive data
- ⚠️ Rate limits: Twitch 100 req/min, Telegram 30 msg/sec

---

## 📈 Monitoring

### Health Checks
```bash
# Is bot running?
ps aux | grep bot.py

# Recent logs
journalctl -u twitch-notifier --lines=20

# Last state
cat state.json

# Test API manually
curl -X POST https://id.twitch.tv/oauth2/token \
  -d "client_id=$TWITCH_CLIENT_ID&client_secret=$TWITCH_CLIENT_SECRET&grant_type=client_credentials"
```

### Alerting
- Add to systemd: OnFailure=send-telegram-alert.service
- Or log to external service (Sentry, LogDNA, etc.)

---

## 🎯 Use Cases

✅ Stream announcements (fan communities)  
✅ Team notifications (co-streamers)  
✅ Content scheduling (go-live reminders)  
✅ Analytics (track stream start/end)  

---

## 🔮 Future Enhancements

- [ ] Multiple channel support (watch 5+ streamers)
- [ ] Stream metadata enrichment (game category, title)
- [ ] Custom messages per channel
- [ ] Viewer count tracking
- [ ] Integration with Discord/Slack
- [ ] Web dashboard for config

