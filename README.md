# 🗂️ Drop2Link Telegram Bot

**Drop2Link** is a private, lightweight Telegram bot built in Python that allows selected users to **upload files and receive direct download links** — self-hosted, secure, and minimal.

---

## ✨ Features

- 🔐 **Restricted Access**: Only approved users can interact with the bot
- 📤 **Upload via Telegram**: Send documents or videos directly in chat
- 🔗 **Instant Download Links**: Get a link to download the file from your own server
- ⏱️ **Auto File Expiration**: Files are deleted automatically after 24 hours
- 🧹 **Manual & Background Cleanup**: Optional `/cleanup` command and hourly background job
- 📊 **Storage Status**: Use `/status` to check file count and disk usage
- 🪵 **Logging**: Logs activity to both console and file (`logs/bot.log`)
- 🛑 **Unauthorized Handling**: All unauthorized users are shown a helpful message
- ⚙️ **Self-hosted**: Run it on any Linux server with a static IP — no domain required

---

## 📦 Requirements

- Python 3.10+
- `aiogram` v3
- A Telegram bot token
- Your Telegram user ID
- A server with static IP to host the files

---

## 🚀 Getting Started

1. Clone the repo
2. Create a `config.py` with:
   ```python
   BOT_TOKEN = "Your Bot Token"
   ALLOWED_USER_ID = 123456789  # your Telegram user ID
   UPLOAD_FOLDER = "./uploads"
   URL = "http://your-server-ip"  # Without trailing slash
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

---

## 🛡️ Security

This bot is currently restricted to a single Telegram user (you).  
You can expand access by updating the `is_allowed_user()` function in `bot.py`.

---

## 📈 Roadmap

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

---

## 📬 Contact

Created by [@oomnoo](https://t.me/yourhandle) — feel free to reach out for collaboration, licensing, or premium bot access.

---
