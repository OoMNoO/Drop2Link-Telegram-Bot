![Drop2Link](./drop2link-banner.png)

# 🗂️ Drop2Link Telegram Bot + Userbot

**Drop2Link** is a private, self-hosted Telegram bot system that allows **approved users to upload files via Telegram and receive direct download links** — even for large files over 200MB.

It combines a **Telegram Bot** (using `aiogram`) and a **Telegram Userbot** (using `telethon`) to bypass Telegram Bot API upload limits.

---

## ✨ Features

- 🔐 **Restricted Access**: Only the approved user can interact with the bot
- 📤 **Upload via Telegram**: Send documents or videos directly to the bot
- 📦 **Large File Support**: Files >200MB are routed to the userbot for reliable downloading
- 🔗 **Instant Download Links**: Get a link to download your file directly from your server
- ⏱️ **Auto File Expiration**: Files are deleted automatically after 24 hours
- 🧹 **Manual & Background Cleanup**: `/cleanup` command + hourly cleanup task
- 📊 **Storage Status**: `/status` shows usage, file count, disk space
- 🪵 **Logging**: Logs for both bot and userbot under `logs/`
- ⚙️ **Self-hosted**: Run it on any Linux server with a static IP — no domain required
- 📥 **DM-based Interprocess Messaging**: Bot and userbot talk via private messages only
- ⚠️ **Log Monitor**: Userbot alerts if logs grow too large

---

## 🧱 Architecture

```
[User] → [Telegram Bot] → [Telegram Userbot] → [Your Server]
               ↓                 ↑
         handles <200MB   handles >200MB
```

- Files ≤ 200MB are downloaded by the **bot** directly.
- Files > 200MB are forwarded to the **userbot**, which downloads them and confirms completion.
- The bot then notifies the user with the final download link.

---

## 📦 Requirements

- `Python` 3.10+
- `aiogram` v3
- `telethon` v1.3
- Telegram Bot token
- Telegram API credentials (`api_id`, `api_hash`)
- Your Telegram User ID (`ALLOWED_USER_ID`)
- A second Telegram account for the **userbot** (`USER_BOT_ID`)
- A Linux server with static IP
- (Optional) Nginx for serving files

---

## 🚀 Getting Started

1. Clone this repo and `cd` into it:

   ```bash
   git clone https://github.com/youruser/drop2link.git
   cd drop2link
   ```

2. Create `config.py`:

   ```python
   BOT_TOKEN = "your_bot_token"
   BOT_ID = 1234567890  # Telegram ID of the bot
   ALLOWED_USER_ID = 123456789  # Your own Telegram user ID
   USER_BOT_ID = 987654321      # Telegram ID of the userbot account

   API_ID = 12345678  # Your Telegram API ID from https://my.telegram.org/apps
   API_HASH = "your_api_hash"  # Your Telegram API HASH from https://my.telegram.org/apps

   UPLOAD_FOLDER = "./uploads"
   LOG_DIR = "./logs"
   URL = "http://your-server-ip"  # Without trailing slash

   MAX_LOG_SIZE_MB = 10
   MAX_BOT_UPLOAD_SIZE_MB = 200 # MB
   FILE_EXPIRATION_HOURS = 24
   BACKGROUND_TASKS_INTERVAL_SECONDS = 3600
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the **userbot** (first-time setup will ask for login code):

   ```bash
   python userbot.py
   ```

5. Start the **main bot**:
   ```bash
   python bot.py
   ```

---

## 🌐 Nginx (Optional)

To serve files over HTTP:

1. Create a symlink if your upload folder is outside `/var/www/`:

   ```bash
   sudo ln -s /path/to/uploads /var/www/drop2link_bot/uploads
   ```

2. Sample Nginx config:

   ```nginx
   server {
       listen 80;
       server_name _;

       location /files/ {
           alias /var/www/drop2link_bot/uploads/;
           autoindex off;
           add_header Content-Disposition "attachment";
       }
   }
   ```

3. Reload Nginx:
   ```bash
   sudo systemctl reload nginx
   ```

Now your files will be downloadable via:  
`http://your-server-ip/files/<filename>`

---

## 🛡️ Security

This bot is currently restricted to a single Telegram user (you).  
You can expand access by updating the `is_allowed_user()` function in `bot.py`.

- Bot access is restricted to one user: `ALLOWED_USER_ID`
- Files expire automatically after 24 hours
- Logs are rotated if too large (you can monitor this from userbot alerts)
- Files are not indexed publicly via Nginx

---

## 🧩 Roadmap

This project started as a personal tool, but it's actively evolving.  
Planned future features include:

- 👥 **Multi-user Support**
- 🧾 **User-based Usage Quotas & Expiry Controls**
- 🧩 **Admin Dashboard** for uploads/logs/users (possibly web-based)
- 💳 **Premium Access Plans** for broader use
- 🌐 Optional **custom domain support** for public use
- 🔐 **Token-based file access** and enhanced security

If you're interested in using or contributing to these features, reach out!

---

## 🤖 Use Case

Perfect for developers, content creators, or power users who want a secure, private bridge between Telegram and their server — with zero third-party hosting or clutter.
useful for:

- Developers and sysadmins
- Remote file access
- Private backup links
- Sending media between devices

---

## 🧑‍💻 Author

Made with ❤️ by [@oomnoo](https://t.me/oomnoo)

If this tool helped you, consider giving feedback or contributing!

Feel free to reach out for collaboration, licensing, or premium bot access.

---
