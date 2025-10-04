import os
import asyncio
import logging
import socket
from datetime import datetime, timedelta
from functools import wraps

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

import config
from fileicons import FILE_ICONS

# Monkey patch TCPConnector to force IPv4
_original_tcp_connector = aiohttp.TCPConnector

def IPv4OnlyConnector(*args, **kwargs):
    kwargs["family"] = socket.AF_INET
    return _original_tcp_connector(*args, **kwargs)

aiohttp.TCPConnector = IPv4OnlyConnector

# --- Configs ---
LOG_FILE_PATH = f"{config.LOG_DIR}/bot.log"
CLEANUP_RUNNING = False

# --- Progress message tracking ---
# key: (user_id, filename), value: aiogram Message object
progress_messages = {}

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

def get_file_icon(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return FILE_ICONS.get(ext, '📄')

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
        progress_msg = await message.reply("📤 File is large, sending to backup system...\n⏳ Please wait for confirmation.")
        progress_messages[(message.from_user.id, file_name)] = progress_msg

@dp.message(Command("status"))
@only_allowed_user
async def status(message: Message):
    files = [
        f for f in os.listdir(config.UPLOAD_FOLDER)
        if os.path.isfile(os.path.join(config.UPLOAD_FOLDER, f))
    ]
    total_size = sum(os.path.getsize(os.path.join(config.UPLOAD_FOLDER, f)) for f in files)
    size_mb = round(total_size / (1024 * 1024), 2)

    stat = os.statvfs(config.UPLOAD_FOLDER)
    free_space_mb = round((stat.f_bavail * stat.f_frsize) / (1024 * 1024), 2)

    await message.reply(
        f"📊 Status:\n"
        f"📁 {len(files)} files\n"
        f"💾 {size_mb} MB used\n"
        f"📦 {free_space_mb} MB free\n"
        f"🧹 Auto-cleaning every {config.FILE_EXPIRATION_HOURS}h"
    )

@dp.message(Command("cleanup"))
@only_allowed_user
async def manual_cleanup(message: Message):
    user_id = message.from_user.id
    progress_message = await message.reply("🧹 Starting cleanup... ⏳")
    await asyncio.sleep(0.5)
    await progress_message.edit_text("🧹 Cleaning up:\n-/- processed\n 0 file deleted.")
    await asyncio.sleep(0.5)
    deleted, total = await cleanup_files("all", user_id, progress_message)
    if deleted == -2 or total == -2:
        await progress_message.edit_text("⚠️ Cleanup is already in progress.")
    else:
        await progress_message.edit_text(f"🧹 Manual cleanup done ✅\n{deleted}/{total} file(s) deleted.")

@dp.message(Command("files"))
@only_allowed_user
async def list_files(message: Message):
    try:
        if not os.path.exists(config.UPLOAD_FOLDER):
            await message.reply("⚠️ Upload folder not found.")
            return

        files = os.listdir(config.UPLOAD_FOLDER)
        if not files:
            await message.reply("📂 No files found.")
            return

        # Build file list with sizes
        file_list = []
        for f in files:
            full_path = os.path.join(config.UPLOAD_FOLDER, f)
            if os.path.isfile(full_path):
                size = os.path.getsize(full_path)
                size_mb = round(size / (1024 * 1024), 2)
                icon = get_file_icon(f)
                file_list.append(f"{icon} {f} — {size_mb} MB")

        # Send result
        await message.reply(
            "\n".join(file_list[:50]) if file_list else "📂 No files found.",
            parse_mode=None  # disable markdown parsing
        )
        # If too many files, we can paginate or limit
    except Exception as e:
        logging.error(f"Error listing files, error: {e}")
        await message.reply("❌ Error listing files.")

@dp.message(Command("links"))
@only_allowed_user
async def list_links(message: Message):
    try:
        if not os.path.exists(config.UPLOAD_FOLDER):
            await message.reply("⚠️ Upload folder not found.")
            return

        files = os.listdir(config.UPLOAD_FOLDER)
        if not files:
            await message.reply("🔗 No links found.")
            return

        # Build file list with sizes
        links_list = []
        for f in files:
            full_path = os.path.join(config.UPLOAD_FOLDER, f)
            if os.path.isfile(full_path):
                file_name = full_path.rsplit("/", 1)[-1]
                # Generate download link
                link = get_download_link(file_name)
                links_list.append(link)

        # Send result
        await message.reply(
            "\n".join(links_list[:50]) if links_list else "🔗 No links found.",
            parse_mode=None  # disable markdown parsing
        )
        # If too many files, we can paginate or limit
    except Exception as e:
        logging.error(f"Error listing files, error: {e}")
        await message.reply("❌ Error listing files.")

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
@dp.message(F.text.startswith("#upload_progress"))
async def handle_upload_progress(message: Message):
    try:
        # Format: #upload_progress user_id file_name percent mb_done mb_total
        parts = message.text.strip().split(" ", 6)
        if len(parts) < 6:
            return
        _, user_id_str, file_name, percent_str, mb_done_str, mb_total_str = parts
        user_id = int(user_id_str)
        percent = int(percent_str)
        mb_done = float(mb_done_str)
        mb_total = float(mb_total_str)

        key = (user_id, file_name)
        progress_msg = progress_messages.get(key)
        if not progress_msg:
            return  # no message to edit

        new_text = (
            f"📤 Uploading *{file_name}*\n"
            f"Progress: {percent}% ({mb_done:.2f} MB / {mb_total:.2f} MB)\n"
            "⏳ Please wait..."
        )
        # Edit the saved message (ignore MessageNotModified errors)
        try:
            await progress_msg.edit_text(new_text)
        except Exception as e:
            logging.debug(f"Edit message failed: {e}")
    except Exception as e:
        logging.error(f"Error handling upload progress: {e}")

@dp.message(F.text.startswith("#upload_done"))
async def handle_userbot_done(message: Message):
    try:
        _, user_id_str, file_name = message.text.strip().split(" ", 2)
        user_id = int(user_id_str)
        link = get_download_link(file_name)

        key = (user_id, file_name)
        progress_msg = progress_messages.pop(key, None)
        final_text = (
            f"✅ Upload complete!\n"
            f"📎 [Download {file_name}]({link})\n"
            f"🕒 Link expires: `{expiration_str()}`"
        )
        if progress_msg:
            try:
                await progress_msg.edit_text(final_text)
            except Exception:
                # fallback: just send a new message
                await bot.send_message(user_id, final_text)
        else:
            await bot.send_message(user_id, final_text)
    except Exception as e:
        logging.error(f"Error parsing userbot upload_done: {e}")

@dp.message(F.text.startswith("#upload_error"))
async def handle_userbot_error(message: Message):
    try:
        _, user_id_str, error_msg = message.text.strip().split(" ", 2)
        user_id = int(user_id_str)

        # Find any progress message for this user to edit:
        keys_to_remove = []
        for key in progress_messages.keys():
            if key[0] == user_id:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            progress_msg = progress_messages.pop(key, None)
            if progress_msg:
                try:
                    await progress_msg.edit_text(f"❌ Upload failed.\nReason: `{error_msg}`")
                except Exception:
                    await bot.send_message(user_id, f"❌ Upload failed.\nReason: `{error_msg}`")
                return
        # If no progress message found, just send a new message:
        await bot.send_message(user_id, f"❌ Upload failed.\nReason: `{error_msg}`")
    except Exception as e:
        logging.error(f"Error parsing userbot upload_error: {e}")

# --- Block all other messages from unauthorized users ---
@dp.message()
@only_allowed_user
async def block_unauthorized(message: Message):
    return

# --- Cleanup Function ---
async def cleanup_files(cleanup_mode: str, user_id=None, progress_message: Message = None):
    global CLEANUP_RUNNING
    if CLEANUP_RUNNING:
        logging.info("Cleanup skipped — already in progress.")
        return -2, -2
    CLEANUP_RUNNING = True
    
    now = datetime.now()
    deleted = 0
    total_files = 0
    
    try:
        now = datetime.now()
        files = [f for f in os.listdir(config.UPLOAD_FOLDER) if os.path.isfile(os.path.join(config.UPLOAD_FOLDER, f))]
        total_files = len(files)
        if progress_message:
            try:
                await progress_message.edit_text(f"🧹 Cleaning up:\n0/{total_files} processed\n0 file deleted.")
                await asyncio.sleep(0.5)
            except:
                pass
        else:
            logging.info(f"🧹 Cleaning up: 0/{total_files} processed, 0 deleted.")

        for i, f in enumerate(files, start=1):
            path = os.path.join(config.UPLOAD_FOLDER, f)
            age = now - datetime.fromtimestamp(os.path.getmtime(path))
            if age > timedelta(hours=config.FILE_EXPIRATION_HOURS) or cleanup_mode == "all":
                os.remove(path)
                deleted += 1
                logging.info(f"Deleted expired file: {f}")
                if progress_message:
                    try:
                        await progress_message.edit_text(
                            f"🧹 Cleaning up:\n{i}/{total_files} processed\n{f} deleted.",
                         parse_mode=None  # disable markdown parsing
                        )
                    except Exception as e:
                        logging.error(f"Failed to edit progress message: {e}")
                else:
                    logging.info(f"🧹 Cleaning up: {i}/{total_files} processed, file {f} deleted.")
            await asyncio.sleep(0.5)  # yield control
    except Exception as e:
        logging.error(f"Cleanup error: {e}")
        if user_id:
            await bot.send_message(user_id, f"❌ Cleanup failed")
        deleted = deleted if deleted != 0 else -1
        total_files = total_files if total_files != 0 else -1
    finally:
        CLEANUP_RUNNING = False
    return deleted, total_files

# --- Background Task ---
async def background_tasks():
    while True:
        logging.info("📝 Starting Background Tasks ⏳")
        logging.info("🧹 Starting Background cleanup... ⏳")
        logging.info("🧹 Cleaning up: -/- processed, 0 deleted.")
        deleted, total = await cleanup_files("old")
        logging.info(f"🧹 Background cleanup done: {deleted}/{total} file(s) deleted. ✅")

        try:
            size_mb = os.path.getsize(LOG_FILE_PATH) / (1024 * 1024)
            if size_mb > config.MAX_LOG_SIZE_MB:
                await bot.send_message(config.ALLOWED_USER_ID, f"⚠️ Log file > {config.MAX_LOG_SIZE_MB}MB ({size_mb:.2f}MB)")
        except Exception as e:
            logging.error(f"Log monitor error: {e}")
        
        logging.info("📝 Background Tasks done. ✅")

        await asyncio.sleep(config.BACKGROUND_TASKS_INTERVAL_SECONDS)

# --- Main Entrypoint ---
async def main():
    logging.info("Starting bot...")
    asyncio.create_task(background_tasks())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
