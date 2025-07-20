import os
import asyncio
import logging
from datetime import datetime, timedelta
from functools import wraps

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ContentType
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

import config

# --- Configs ---
LOG_FILE_PATH = f"{config.LOG_DIR}/bot.log"

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

# --- Bot Setup ---
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# --- Filters ---
def only_allowed_user(handler):
    @wraps(handler)
    async def wrapper(message: Message, *args, **kwargs):
        logging.info(f"=================================")
        logging.info(f"message from: {message.from_user.id} {message.from_user.username}")
        logging.info(f"---------------------------------")
        logging.info(f"message text: {message.text}")
        logging.info(f"---------------------------------")
        if message.from_user.id != config.ALLOWED_USER_ID and message.from_user.id != config.USER_BOT_ID:
            await message.reply(
                "⛔️ You are not authorized to use this bot.\n"
                "If you believe you should have access, contact [@oomnoo](https://t.me/oomnoo).",
                disable_web_page_preview=True
            )
            return
        return await handler(message, *args, **kwargs)
    return wrapper

def get_file_size_mb(size_bytes: int) -> float:
    return size_bytes / (1024 * 1024)

def expiration_str():
    exp = datetime.now() + timedelta(hours=config.FILE_EXPIRATION_HOURS)
    return exp.strftime("%Y-%m-%d %H:%M:%S")

def get_download_link(file_name: str) -> str:
    return f"{config.URL}/files/{file_name}"

# --- Handlers ---
@dp.message(F.document | F.video)
@only_allowed_user
async def handle_file(message: Message):
    file = message.document or message.video
    file_name = file.file_name or f"file_{file.file_id}"
    file_size = file.file_size

    if get_file_size_mb(file_size) <= config.MAX_BOT_UPLOAD_SIZE_MB:
        # Small file → direct download
        file_path = os.path.join(config.UPLOAD_FOLDER, file_name)
        await bot.download(file=file.file_id, destination=file_path)
        logging.info(f"Uploaded file saved: {file_path}")

        link = get_download_link(file_name)
        await message.reply(
            f"✅ File uploaded!\n📎 [Download]({link})\n🕒 Link expires: `{expiration_str()}`"
        )
        logging.info(f"Saved file: {file_path}")
    else:
        # Large file → send to userbot for handling
        logging.info(f"Forwarding large file to userbot: {file_name} ({file_size} bytes)")
        upload_req_msg = await bot.send_message(
            config.USER_BOT_ID,
            f"#upload_request\nUserID:{message.from_user.id}\nName:{file_name}\nSize:{get_file_size_mb(file_size):.2f}MB",
            parse_mode=None  # disable markdown parsing
        )
        await bot.copy_message(
            chat_id=config.USER_BOT_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_to_message_id=upload_req_msg.message_id
        )
        await message.reply("📤 File is large, sending to backup system...\n⏳ Please wait for confirmation.")

@dp.message(Command("status"))
@only_allowed_user
async def status(message: Message):
    files = [
        f for f in os.listdir(config.UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(config.UPLOAD_FOLDER, f))
    ]
    total_size = sum(os.path.getsize(os.path.join(config.UPLOAD_FOLDER, f)) for f in files)
    size_mb = round(total_size / (1024 * 1024), 2)

    await message.reply(
        f"📊 Status:\n📁 {len(files)} files\n💾 {size_mb} MB used\n🧹 Auto-cleaning every {config.FILE_EXPIRATION_HOURS}h"
    )

@dp.message(Command("cleanup"))
@only_allowed_user
async def manual_cleanup(message: Message):
    deleted = cleanup_files("all")
    await message.reply(f"🧹 Manual cleanup done: {deleted} file(s) deleted.")

@dp.message(CommandStart())
async def start(message: Message):
    text = (
        "👋 Welcome to *Drop2Link Bot!*\n\n"
        "📤 Upload files and get a private download link.\n"
        "🔒 Access to this bot is limited to approved users only.\n\n"
        "📩 Interested in using this bot or need something similar?\n"
        "Contact [@oomnoo](https://t.me/oomnoo)."
    )
    await message.answer(text, disable_web_page_preview=True)

# --- Handle Userbot Responses ---
@dp.message(F.text.startswith("#upload_done"))
async def handle_userbot_done(message: Message):
    try:
        logging.info(f"upload_done")
        _, user_id, file_name = message.text.strip().split(" ", 2)
        link = get_download_link(file_name)
        await bot.send_message(
            int(user_id),
            f"✅ File uploaded successfully!\n📎 [Download]({link})\n🕒 Expires: `{expiration_str()}`"
        )
    except Exception as e:
        logging.error(f"Error parsing userbot upload_done: {e}")

@dp.message(F.text.startswith("#upload_error"))
async def handle_userbot_error(message: Message):
    try:
        logging.info(f"upload_error")
        _, user_id, error_msg = message.text.strip().split(" ", 2)
        await bot.send_message(
            int(user_id),
            f"❌ Upload failed via userbot.\nReason: `{error_msg}`"
        )
    except Exception as e:
        logging.error(f"Error parsing userbot upload_error: {e}")

# --- Block all other messages from unauthorized users ---
@dp.message()
@only_allowed_user
async def block_unauthorized(message: Message):
    return

# --- Cleanup Function ---
def cleanup_files(cleanup_mode: str):
    now = datetime.now()
    deleted = 0
    for f in os.listdir(config.UPLOAD_FOLDER):
        path = os.path.join(config.UPLOAD_FOLDER, f)
        if os.path.isfile(path):
            age = now - datetime.fromtimestamp(os.path.getmtime(path))
            if age > timedelta(hours=config.FILE_EXPIRATION_HOURS) or cleanup_mode == "all":
                os.remove(path)
                deleted += 1
                logging.info(f"Deleted expired file: {f}")
    return deleted

# --- Background Task: cleanup & log monitor ---
async def background_tasks():
    while True:
        deleted = cleanup_files("old")
        if deleted:
            logging.info(f"🧹 Background cleanup removed {deleted} files")

        try:
            size_mb = os.path.getsize(LOG_FILE_PATH) / (1024 * 1024)
            if size_mb > config.MAX_LOG_SIZE_MB:
                await bot.send_message(config.ALLOWED_USER_ID, f"⚠️ Log file > {config.MAX_LOG_SIZE_MB}MB ({size_mb:.2f}MB)")
        except Exception as e:
            logging.error(f"Log monitor error: {e}")

        await asyncio.sleep(config.BACKGROUND_TASKS_INTERVAL_SECONDS)

# --- Main Entrypoint ---
async def main():
    logging.info("Starting bot...")
    asyncio.create_task(background_tasks())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
