# userbot.py

import os
import asyncio
import logging

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument, DocumentAttributeFilename

import config

# --- Configs ---
LOG_FILE_PATH = f"{config.LOG_DIR}/userbot.log"

# --- Logging Setup ---
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_FILE_PATH}"),
        logging.StreamHandler()
    ]
)

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

client = TelegramClient("userbot", config.API_ID, config.API_HASH)

# Temporary map of file -> sender
user_context = {}

@client.on(events.NewMessage(from_users=config.BOT_ID))
async def handle_file(event):
    sender = await event.get_sender()
    message = event.message

    if message.message and message.message.startswith("#upload_request"):
        lines = message.message.splitlines()
        user_id_line = next((l for l in lines if l.startswith("UserID:")), None)
        name_line = next((l for l in lines if l.startswith("Name:")), None)

        if user_id_line and name_line:
            user_id = int(user_id_line.split(":")[1])
            file_name = name_line.split(":", 1)[1].strip()
            user_context[event.id] = {"user_id": user_id, "file_name": file_name}
            logging.info(f"Queued file for download from user {user_id}: {file_name}")
        return

    if isinstance(message.media, MessageMediaDocument):
        try:
            ctx = user_context.pop(event.reply_to_msg_id, None)
            if not ctx:
                logging.warning("Received file with no matching context.")
                return

            file_name = ctx["file_name"]
            user_id = ctx["user_id"]
            file_path = os.path.join(config.UPLOAD_FOLDER, file_name)

            logging.info(f"Downloading large file to {file_path}")
            await client.download_media(message, file_path)

            # Notify bot
            await client.send_message(config.BOT_ID, f"#upload_done {user_id} {file_name}")
            logging.info(f"File downloaded and confirmed: {file_name}")

        except Exception as e:
            logging.error(f"Download failed: {e}")
            if ctx:
                await client.send_message(config.BOT_ID, f"#upload_error {ctx['user_id']} {str(e)}")
                
async def background_tasks():
    while True:
        try:
            size_mb = os.path.getsize(LOG_FILE_PATH) / (1024 * 1024)
            if size_mb > config.MAX_LOG_SIZE_MB:
                await client.send_message(
                    config.BOT_ID,
                    f"⚠️ [Userbot] Log file exceeded {config.MAX_LOG_SIZE_MB}MB: ({size_mb:.2f}MB)"
                )
        except Exception as e:
            logging.error(f"[Log Monitor] Error: {e}")

        await asyncio.sleep(config.BACKGROUND_TASKS_INTERVAL_SECONDS)

# --- Main Entrypoint ---
async def main():
    logging.info("Starting userbot...")
    await client.start()
    asyncio.create_task(background_tasks())
    logging.info("Userbot is up and running.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
