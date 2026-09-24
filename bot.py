import os
import threading

from flask import Flask
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================================================
# CONFIG
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB", "caption_thumbnail_bot")

ADMIN_ID = int(os.environ["ADMIN_ID"])


# =========================================================
# FLASK SERVER
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "Caption + Thumbnail Bot is Running!"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================================================
# MONGODB
# =========================================================

mongo = MongoClient(MONGO_URI)

db = mongo[MONGO_DB]
settings_collection = db["settings"]


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
# ADMIN CHECK
# =========================================================

def is_admin(user_id):
    return user_id == ADMIN_ID


# =========================================================
# GET SETTINGS
# =========================================================

def get_settings():

    data = settings_collection.find_one(
        {"_id": "main"}
    )

    if not data:
        return {}

    return data


# =========================================================
# START
# =========================================================

@bot.on_message(filters.command("start"))
async def start(client, message):

    if not is_admin(message.from_user.id):

        await message.reply_text(
            "❌ यह Bot केवल Admin के लिए है."
        )

        return

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
                "🗑️ Clear",
                callback_data="clear"
            )
        ]
    ])

    await message.reply_text(
        "🤖 **Caption + Thumbnail Bot**\n\n"
        "Welcome Admin! 👋🏻\n\n"
        "नीचे दिए buttons से अपना Thumbnail और Caption set करें.",
        reply_markup=buttons
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================

@bot.on_callback_query()
async def callback_handler(client, query):

    if not is_admin(query.from_user.id):

        await query.answer(
            "❌ Admin Only!",
            show_alert=True
        )

        return

    if query.data == "set_thumb":

        user_state[query.from_user.id] = "thumbnail"

        await query.message.reply_text(
            "🖼️ अब अपना **Thumbnail Photo** भेजें."
        )

        await query.answer()


    elif query.data == "set_caption":

        user_state[query.from_user.id] = "caption"

        await query.message.reply_text(
            "📝 अब अपना **Caption** भेजें."
        )

        await query.answer()


    elif query.data == "preview":

        data = get_settings()

        caption = data.get("caption")
        thumbnail = data.get("thumbnail")

        if not caption and not thumbnail:

            await query.message.reply_text(
                "❌ अभी कोई Caption या Thumbnail saved नहीं है."
            )

        elif thumbnail:

            await client.send_photo(
                chat_id=query.message.chat.id,
                photo=thumbnail,
                caption=caption or "No Caption"
            )

        else:

            await query.message.reply_text(
                f"📝 **Saved Caption:**\n\n{caption}"
            )

        await query.answer()


    elif query.data == "clear":

        settings_collection.delete_one(
            {"_id": "main"}
        )

        user_state.pop(query.from_user.id, None)

        await query.message.reply_text(
            "🗑️ **Caption और Thumbnail Clear हो गए.**"
        )

        await query.answer()


# =========================================================
# PHOTO HANDLER
# =========================================================

@bot.on_message(filters.photo)
async def photo_handler(client, message):

    if not is_admin(message.from_user.id):
        return

    state = user_state.get(
        message.from_user.id
    )

    # -------------------------------
    # SET THUMBNAIL
    # -------------------------------

    if state == "thumbnail":

        file_id = message.photo.file_id

        settings_collection.update_one(
            {"_id": "main"},
            {
                "$set": {
                    "thumbnail": file_id
                }
            },
            upsert=True
        )

        user_state.pop(
            message.from_user.id,
            None
        )

        await message.reply_text(
            "✅ **Thumbnail Successfully Saved!**"
        )

        return

    # -------------------------------
    # NORMAL PHOTO
    # -------------------------------

    await send_photo_result(
        client,
        message
    )


# =========================================================
# CAPTION HANDLER
# =========================================================

@bot.on_message(
    filters.text
    & ~filters.command(
        ["start", "preview", "clear"]
    )
)
async def caption_handler(client, message):

    if not is_admin(message.from_user.id):
        return

    state = user_state.get(
        message.from_user.id
    )

    if state == "caption":

        settings_collection.update_one(
            {"_id": "main"},
            {
                "$set": {
                    "caption": message.text
                }
            },
            upsert=True
        )

        user_state.pop(
            message.from_user.id,
            None
        )

        await message.reply_text(
            "✅ **Caption Successfully Saved!**"
        )


# =========================================================
# VIDEO HANDLER
# =========================================================

@bot.on_message(filters.video)
async def video_handler(client, message):

    if not is_admin(message.from_user.id):
        return

    await send_video_result(
        client,
        message
    )


# =========================================================
# DOCUMENT HANDLER
# =========================================================

@bot.on_message(filters.document)
async def document_handler(client, message):

    if not is_admin(message.from_user.id):
        return

    data = get_settings()

    caption = data.get(
        "caption",
        ""
    )

    await client.send_document(
        chat_id=message.chat.id,
        document=message.document.file_id,
        caption=caption
    )


# =========================================================
# SEND PHOTO RESULT
# =========================================================

async def send_photo_result(
    client,
    message
):

    data = get_settings()

    caption = data.get(
        "caption",
        ""
    )

    thumbnail = data.get(
        "thumbnail"
    )

    if thumbnail:

        await client.send_photo(
            chat_id=message.chat.id,
            photo=thumbnail,
            caption=caption
        )

    else:

        await client.send_photo(
            chat_id=message.chat.id,
            photo=message.photo.file_id,
            caption=caption
        )


# =========================================================
# SEND VIDEO RESULT
# =========================================================

async def send_video_result(
    client,
    message
):

    data = get_settings()

    caption = data.get(
        "caption",
        ""
    )

    # Telegram/Pyrogram video thumbnail
    # के लिए saved thumbnail का file_id इस्तेमाल
    thumbnail = data.get(
        "thumbnail"
    )

    try:

        await client.send_video(
            chat_id=message.chat.id,
            video=message.video.file_id,
            caption=caption,
            thumb=thumbnail
        )

    except Exception:

        # अगर thumbnail Telegram द्वारा accept
        # नहीं होता तो बिना custom thumb भेजें

        await client.send_video(
            chat_id=message.chat.id,
            video=message.video.file_id,
            caption=caption
        )


# =========================================================
# PREVIEW COMMAND
# =========================================================

@bot.on_message(filters.command("preview"))
async def preview_command(client, message):

    if not is_admin(message.from_user.id):
        return

    data = get_settings()

    caption = data.get(
        "caption"
    )

    thumbnail = data.get(
        "thumbnail"
    )

    if not caption and not thumbnail:

        await message.reply_text(
            "❌ कोई Caption या Thumbnail saved नहीं है."
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


# =========================================================
# CLEAR COMMAND
# =========================================================

@bot.on_message(filters.command("clear"))
async def clear_command(client, message):

    if not is_admin(message.from_user.id):
        return

    settings_collection.delete_one(
        {"_id": "main"}
    )

    user_state.pop(
        message.from_user.id,
        None
    )

    await message.reply_text(
        "🗑️ **Caption और Thumbnail Clear हो गए.**"
    )


# =========================================================
# RUN BOT
# =========================================================

if __name__ == "__main__":

    threading.Thread(
        target=run_flask,
        daemon=True
    ).start()

    print(
        "🤖 Caption + Thumbnail Bot Started!"
    )

    bot.run()
