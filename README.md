# 🔴 Twitch → Telegram Notifier

Python bot that monitors Twitch stream status and sends live notifications to Telegram with screenshot preview.

**Key Features:**
- 📡 Real-time Twitch stream monitoring (polls every 60 seconds)
- 📸 Screenshot preview download (waits 150s for fresh thumbnail)
- 💬 Telegram notifications with photo + metadata
- 🔄 State tracking (no duplicate notifications)
- ⚡ Lightweight (~50MB memory, <5% CPU)
- 🐧 Linux systemd support

---

## 🏗️ Tech Stack

- **Language:** Python 3.11+
- **Twitch API:** Helix API (OAuth2)
- **Telegram:** python-telegram-bot
- **State:** JSON file (local)
- **Deployment:** Systemd, Docker, Windows Service (NSSM)

---

## 🚀 Quick Start

### Local Setup

```bash
# Clone & setup
git clone https://github.com/kiiaara/kiiara-uved.git
cd kiiara-uved

# Python env
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Config
cp .env.example .env
nano .env  # fill in tokens

# Run
python bot.py
```

### Docker

```bash
docker build -t twitch-notifier .
docker run -d --env-file .env twitch-notifier
```

### Linux Systemd

```bash
sudo mkdir -p /opt/twitch-notifier
cd /opt/twitch-notifier
git clone https://github.com/kiiaara/kiiara-uved.git .

# Setup
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env  # fill tokens

# Install service
sudo cp systemd/twitch-notifier.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now twitch-notifier

# View logs
journalctl -u twitch-notifier -f
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_IDS=-1001234567890,327654321  # Multiple IDs

# Twitch
TWITCH_CLIENT_ID=abc123xyz...
TWITCH_CLIENT_SECRET=xyz789abc...
TWITCH_LOGIN=kiiaara  # Channel to monitor

# Polling
POLL_INTERVAL=60        # Check every 60 seconds
PREVIEW_DELAY=150       # Wait 150s for fresh thumbnail
LOG_LEVEL=INFO          # DEBUG/INFO/WARNING/ERROR
```

### State File

Bot creates `state.json` automatically:

```json
{
  "is_live": false,
  "last_checked": "2026-09-17T12:00:00Z",
  "last_title": "Gaming Session",
  "thumbnail_url": "https://static-cdn.jtvnw.net/..."
}
```

Delete this file to reset state (useful for testing).

---

## 📊 How It Works

1. **Poll Twitch:** Every 60 seconds, check if channel is live
2. **State Check:** Compare with previous state (avoid duplicates)
3. **Stream Starts:** 
   - Wait 150 seconds (for fresh thumbnail)
   - Download stream preview image
   - Send to Telegram with metadata
   - Fall back to text if image fails
4. **Stream Ends:** Send "🔴 Stream ended" notification

---

## 📁 Project Structure

```
kiiara-uved/
├── bot.py              # Main polling logic (300+ lines)
├── requirements.txt    # Dependencies
├── .env.example       # Config template
├── state.json         # Runtime state (auto-created)
├── systemd/
│   └── twitch-notifier.service
├── LICENSE
└── README.md
```

---

## 🔌 API Endpoints Used

### Twitch Helix API

```
GET https://id.twitch.tv/oauth2/token
  - Get OAuth2 access token (auto-refreshes)

GET https://api.twitch.tv/helix/streams?user_login={channel}
  - Check if stream is live
  - Get title, thumbnail_url, viewer_count
```

### Telegram Bot API

```
POST https://api.telegram.org/bot{TOKEN}/sendPhoto
  - Send stream preview image + metadata

POST https://api.telegram.org/bot{TOKEN}/sendMessage
  - Fallback: send text-only notification
```

---

## 🧪 Testing

### Verify Twitch API

```bash
# Get token
curl -X POST "https://id.twitch.tv/oauth2/token?client_id=$TWITCH_CLIENT_ID&client_secret=$TWITCH_CLIENT_SECRET&grant_type=client_credentials"

# Check if channel is live
curl -H "Client-Id: $TWITCH_CLIENT_ID" \
     -H "Authorization: Bearer $TOKEN" \
     "https://api.twitch.tv/helix/streams?user_login=kiiaara"
```

### Quick Notification Test

Temporarily change `TWITCH_LOGIN` to an active streamer, run bot once, you'll get a test notification, then revert.

---

## 📊 Monitoring

```bash
# Is bot running?
ps aux | grep bot.py

# Recent logs
journalctl -u twitch-notifier --lines=20

# Check current state
cat state.json

# Restart bot
sudo systemctl restart twitch-notifier
```

---

## 🔐 Security

✅ Secrets in `.env` (never in code)  
✅ `.env` in `.gitignore`  
✅ OAuth2 tokens cached in memory only  
✅ state.json has no sensitive data  
⚠️ Rate limits: Twitch 100 req/min, Telegram 30 msg/sec  

---

## 🔮 Future Enhancements

- [ ] Multiple channel monitoring (watch 5+ streamers)
- [ ] Stream metadata enrichment (game, title)
- [ ] Custom messages per channel
- [ ] Viewer count tracking
- [ ] Discord/Slack integration
- [ ] Web dashboard for config

---

## 📖 Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design, auth flow, error handling
- [LICENSE](LICENSE) - MIT License

---

**Author:** Kiiaara  
**Status:** Active Development
