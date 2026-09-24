import os
import json
import threading

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================================================
# CONFIG
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

SETTINGS_FILE = "settings.json"


# =========================================================
# FLASK SERVER - RENDER KEEP ALIVE
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Caption + Thumbnail Bot is Running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# SETTINGS
# =========================================================

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


settings = load_settings()


# =========================================================
# BOT
# =========================================================

bot = Client(
    "caption_thumbnail_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# =========================================================
# USER STATE
# =========================================================

user_state = {}


# =========================================================
# START
# =========================================================

@bot.on_message(filters.command("start"))
async def start(client, message):

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🖼️ Set Thumbnail",
                callback_data="set_thumb"
            )
        ],
        [
            InlineKeyboardButton(
                "📝 Set Caption",
                callback_data="set_caption"
            )
        ],
        [
            InlineKeyboardButton(
                "👀 Preview",
                callback_data="preview"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑️ Clear Settings",
                callback_data="clear"
            )
        ]
    ])

    await message.reply_text(
        "🤖 **Caption + Thumbnail Bot**\n\n"
        "Welcome!\n\n"
        "पहले Thumbnail और Caption set करें।\n"
        "उसके बाद कोई Photo/Video भेजें।",
        reply_markup=buttons
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================

@bot.on_callback_query()
async def callbacks(client, query):

    user_id = str(query.from_user.id)

    if query.data == "set_thumb":

        user_state[user_id] = "thumbnail"

        await query.message.reply_text(
            "🖼️ **Thumbnail Set करने के लिए Photo भेजें।**"
        )

        await query.answer()


    elif query.data == "set_caption":

        user_state[user_id] = "caption"

        await query.message.reply_text(
            "📝 **अब अपना Caption भेजें।**"
        )

        await query.answer()


    elif query.data == "preview":

        user_data = settings.get(user_id, {})

        caption = user_data.get("caption")
        thumbnail = user_data.get("thumbnail")

        if not caption and not thumbnail:
            await query.message.reply_text(
                "❌ अभी कोई Caption या Thumbnail Set नहीं है।"
            )

        elif thumbnail:

            await client.send_photo(
                chat_id=query.message.chat.id,
                photo=thumbnail,
                caption=caption or "No Caption Set"
            )

        else:

            await query.message.reply_text(
                f"📝 **Saved Caption:**\n\n{caption}"
            )

        await query.answer()


    elif query.data == "clear":

        settings.pop(user_id, None)
        save_settings(settings)

        user_state.pop(user_id, None)

        await query.message.reply_text(
            "🗑️ आपका Caption और Thumbnail Clear कर दिया गया।"
        )

        await query.answer()


# =========================================================
# SET THUMBNAIL
# =========================================================

@bot.on_message(filters.photo)
async def photo_handler(client, message):

    user_id = str(message.from_user.id)

    state = user_state.get(user_id)

    if state == "thumbnail":

        photo = message.photo

        settings.setdefault(user_id, {})

        settings[user_id]["thumbnail"] = str(photo.file_id)

        save_settings(settings)

        user_state.pop(user_id, None)

        await message.reply_text(
            "✅ **Thumbnail Successfully Saved!**\n\n"
            "अब `/start` दबाकर Caption Set कर सकते हैं।"
        )

        return


    # Normal photo
    await send_result(client, message)


# =========================================================
# SET CAPTION
# =========================================================

@bot.on_message(
    filters.text & ~filters.command(
        ["start", "preview", "clear"]
    )
)
async def caption_handler(client, message):

    user_id = str(message.from_user.id)

    state = user_state.get(user_id)

    if state == "caption":

        settings.setdefault(user_id, {})

        settings[user_id]["caption"] = message.text

        save_settings(settings)

        user_state.pop(user_id, None)

        await message.reply_text(
            "✅ **Caption Successfully Saved!**\n\n"
            "अब कोई Photo/Video भेजें।"
        )

        return


# =========================================================
# VIDEO
# =========================================================

@bot.on_message(filters.video)
async def video_handler(client, message):

    await send_result(client, message)


# =========================================================
# DOCUMENT
# =========================================================

@bot.on_message(filters.document)
async def document_handler(client, message):

    await send_result(client, message)


# =========================================================
# SEND FINAL RESULT
# =========================================================

async def send_result(client, message):

    user_id = str(message.from_user.id)

    user_data = settings.get(user_id, {})

    caption = user_data.get(
        "caption",
        "Caption Set नहीं है।"
    )

    thumbnail = user_data.get("thumbnail")

    # ---------------------------------------------
    # PHOTO
    # ---------------------------------------------

    if message.photo:

        if thumbnail:

            await client.send_photo(
                chat_id=message.chat.id,
                photo=thumbnail,
                caption=caption
            )

        else:

            await message.reply_photo(
                photo=message.photo.file_id,
                caption=caption
            )

    # ---------------------------------------------
    # VIDEO
    # ---------------------------------------------

    elif message.video:

        await client.send_video(
            chat_id=message.chat.id,
            video=message.video.file_id,
            caption=caption,
            thumb=thumbnail
        )

    # ---------------------------------------------
    # DOCUMENT
    # ---------------------------------------------

    elif message.document:

        await client.send_document(
            chat_id=message.chat.id,
            document=message.document.file_id,
            caption=caption
        )


# =========================================================
# COMMANDS
# =========================================================

@bot.on_message(filters.command("preview"))
async def preview_command(client, message):

    user_id = str(message.from_user.id)

    user_data = settings.get(user_id, {})

    caption = user_data.get("caption")
    thumbnail = user_data.get("thumbnail")

    if not caption and not thumbnail:

        await message.reply_text(
            "❌ कोई Caption/Thumbnail Set नहीं है।"
        )

        return

    if thumbnail:

        await client.send_photo(
            chat_id=message.chat.id,
            photo=thumbnail,
            caption=caption or "No Caption"
        )

    else:

        await message.reply_text(
            f"📝 **Caption:**\n\n{caption}"
        )


@bot.on_message(filters.command("clear"))
async def clear_command(client, message):

    user_id = str(message.from_user.id)

    settings.pop(user_id, None)

    save_settings(settings)

    user_state.pop(user_id, None)

    await message.reply_text(
        "🗑️ Caption और Thumbnail Clear हो गए।"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    print("🤖 Bot Started Successfully!")

    bot.run()
