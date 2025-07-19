import os
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ContentType
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ALLOWED_USER_ID, UPLOAD_FOLDER, URL

# --- Logging Setup ---
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{log_dir}/bot.log"),
        logging.StreamHandler()
    ]
)

# --- Configs ---
CLEANUP_INTERVAL_SECONDS = 3600
FILE_EXPIRATION_HOURS = 24
MAX_LOG_SIZE_MB = 10
LOG_FILE_PATH = f"{log_dir}/bot.log"

# --- Bot Setup ---
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher(storage=MemoryStorage())

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Filters ---
def is_allowed_user(message: Message):
    return message.from_user.id == ALLOWED_USER_ID

# --- File Extension Filtering ---
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.docx', '.mp4', '.mov', '.avi', '.mkv'}

def is_allowed_file(filename: str) -> bool:
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS

# --- Handlers ---
@dp.message(F.document | F.video)
async def handle_file(message: Message):
    if not is_allowed_user(message):
        await message.reply(
            "⛔️ You are not authorized to use this bot.\n"
            "If you believe you should have access, contact [@oomnoo](https://t.me/oomnoo).",
            disable_web_page_preview=True
        )
        return

    file = message.document or message.video
    file_name = file.file_name if message.document else f"video_{file.file_id}.mp4"

    MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # Telegram bot limit
    if file.file_size > MAX_FILE_SIZE_BYTES:
        await message.reply("❌ This file is too large. Telegram bots only support files up to 200MB.")
        return

    if not is_allowed_file(file_name):
        await message.reply("❌ This file type is not allowed.")
        return

    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    await bot.download(file=file.file_id, destination=file_path)
    logging.info(f"Uploaded file saved: {file_path}")

    expiration = datetime.now() + timedelta(hours=FILE_EXPIRATION_HOURS)
    expiration_str = expiration.strftime("%Y-%m-%d %H:%M:%S")

    link = f"{URL}/files/{file_name}"
    await message.reply(
        f"✅ File uploaded!\n📎 [Download]({link})\n🕒 Link expires: `{expiration_str}`"
    )

@dp.message(Command("status"))
async def status(message: Message):
    if not is_allowed_user(message):
        return

    files = [
        os.path.join(UPLOAD_FOLDER, f)
        for f in os.listdir(UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))
    ]
    total_size = sum(os.path.getsize(f) for f in files)
    size_mb = round(total_size / (1024 * 1024), 2)

    await message.reply(
        f"📊 Status:\n📁 {len(files)} files\n💾 {size_mb} MB used\n🧹 Auto-cleaning every {FILE_EXPIRATION_HOURS}h"
    )

@dp.message(Command("cleanup"))
async def manual_cleanup(message: Message):
    if not is_allowed_user(message):
        return
    deleted = cleanup_old_files()
    await message.reply(f"🧹 Manual cleanup done: {deleted} file(s) deleted.")

@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        "👋 Welcome to *Drop2Link Bot!*\n\n"
        "📤 Upload files and get a private download link.\n"
        "🔒 Access to this bot is limited to approved users only.\n\n"
        "📩 Interested in using this bot or need something similar?\n"
        "Contact [@oomnoo](https://t.me/oomnoo)."
    )
    await message.answer(text, disable_web_page_preview=True)

# --- Block all other messages from unauthorized users ---
@dp.message()
async def block_unauthorized(message: Message):
    if not is_allowed_user(message):
        await message.reply(
            "⛔️ You are not authorized to use this bot.\n"
            "If you believe you should have access, contact [@oomnoo](https://t.me/oomnoo).",
            disable_web_page_preview=True
        )

# --- Cleanup Function ---
def cleanup_old_files():
    now = datetime.now()
    deleted = 0
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isfile(path):
            age = now - datetime.fromtimestamp(os.path.getmtime(path))
            if age > timedelta(hours=FILE_EXPIRATION_HOURS):
                try:
                    os.remove(path)
                    logging.info(f"Deleted file: {f}")
                    deleted += 1
                except Exception as e:
                    logging.error(f"Failed to delete {f}: {e}")
    return deleted

# --- Background Task: cleanup & log monitor ---
async def background_tasks():
    while True:
        deleted = cleanup_old_files()
        if deleted:
            logging.info(f"🧹 Background cleanup removed {deleted} files")

        try:
            size_mb = os.path.getsize(LOG_FILE_PATH) / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                await bot.send_message(ALLOWED_USER_ID, f"⚠️ Log file > {MAX_LOG_SIZE_MB}MB ({size_mb:.2f}MB)")
        except Exception as e:
            logging.error(f"Log monitor error: {e}")

        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

# --- Main Entrypoint ---
async def main():
    logging.info("Starting bot...")
    asyncio.create_task(background_tasks())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
