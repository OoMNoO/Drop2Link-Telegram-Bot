import os
import asyncio
import logging
import time

from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument
from telethon.errors import FloodWaitError

import config

# --- Configs ---
LOG_FILE_PATH = f"{config.LOG_DIR}/userbot.log"
MAX_CONCURRENT_DOWNLOADS = 1  # safest is 1
PROGRESS_UPDATE_INTERVAL = 3  # seconds
PROGRESS_UPDATE_PERCENT = 5   # minimum % change before sending update

# --- Logging Setup ---
os.makedirs(config.LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

client = TelegramClient("userbot", config.API_ID, config.API_HASH)

# Temporary map of media_msg_id -> {user_id, file_name}
user_context = {}

# Download queue
download_queue = asyncio.Queue()

# --- Progress callback ---
async def send_progress(current, total, ctx, last_update):
    if total <= 0:
        return
    now = time.time()
    percent = int(current / total * 100)
    # Send update only if enough time passed or enough percent changed
    if (now - last_update[0] > PROGRESS_UPDATE_INTERVAL) or \
       (percent - last_update[1] >= PROGRESS_UPDATE_PERCENT):
        last_update[0] = now
        last_update[1] = percent

        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        msg = f"#upload_progress {ctx['user_id']} {ctx['file_name']} {percent} {current_mb:.2f} {total_mb:.2f}"
        await client.send_message(config.BOT_ID, msg)

# --- Worker to process downloads ---
async def download_worker():
    while True:
        ctx, message = await download_queue.get()
        try:
            file_name = ctx["file_name"]
            user_id = ctx["user_id"]
            file_path = os.path.join(config.UPLOAD_FOLDER, file_name)

            logging.info(f"[Worker] Downloading large file to {file_path}")

            last_update = [0, 0]  # [last_time_sent, last_percent]

            try:
                await client.download_media(
                    message,
                    file_path,
                    progress_callback=lambda cur, tot: asyncio.create_task(
                        send_progress(cur, tot, ctx, last_update)
                    )
                )
            except FloodWaitError as e:
                logging.warning(f"[Worker] Flood wait: sleeping {e.seconds}s")
                await asyncio.sleep(e.seconds)
                await client.download_media(
                    message,
                    file_path,
                    progress_callback=lambda cur, tot: asyncio.create_task(
                        send_progress(cur, tot, ctx, last_update)
                    )
                )

            await client.send_message(config.BOT_ID, f"#upload_done {user_id} {file_name}")
            logging.info(f"[Worker] File downloaded and confirmed: {file_name}")

        except Exception as e:
            logging.error(f"[Worker] Download failed: {e}")
            await client.send_message(config.BOT_ID, f"#upload_error {ctx['user_id']} {str(e)}")

        finally:
            download_queue.task_done()

# --- Handle metadata linking ---
@client.on(events.NewMessage(from_users=config.BOT_ID))
async def handle_file(event):
    message = event.message

    # Handle upload request metadata
    if message.message and message.message.startswith("#upload_request"):
        lines = message.message.splitlines()
        user_id_line = next((l for l in lines if l.startswith("UserID:")), None)
        name_line = next((l for l in lines if l.startswith("Name:")), None)

        if user_id_line and name_line:
            user_id = int(user_id_line.split(":")[1])
            file_name = name_line.split(":", 1)[1].strip()
            user_context[event.id] = {"user_id": user_id, "file_name": file_name}
            logging.info(f"Queued file metadata from user {user_id}: {file_name}")
        return

    # Handle actual file
    if isinstance(message.media, MessageMediaDocument):
        try:
            ctx = user_context.pop(event.reply_to_msg_id, None)
            if not ctx:
                logging.warning("Received file with no matching context.")
                return

            # Add to download queue instead of downloading immediately
            await download_queue.put((ctx, message))
            logging.info(f"[Queue] Added {ctx['file_name']} for download (queue size: {download_queue.qsize()})")
        except Exception as e:
            logging.error(f"Download failed: {e}")
            if ctx:
                await client.send_message(config.BOT_ID, f"#upload_error {ctx['user_id']} {str(e)}")

# --- Background log monitoring ---
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

    # Start workers
    for _ in range(MAX_CONCURRENT_DOWNLOADS):
        asyncio.create_task(download_worker())

    asyncio.create_task(background_tasks())
    logging.info("Userbot is up and running.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
