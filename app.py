import os
import base64
import hashlib
import httpx
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request

# Initialize Flask app
app = Flask(__name__)

# Initialize Telegram bot
bot = Bot(token='YOUR_TOKEN_HERE')  # REPLACE WITH YOUR TELEGRAM BOT TOKEN
dp = Dispatcher(bot)

API_KEY = "REMINI_API_KEY"  # REPLACE WITH YOUR REMINI API KEY THAT HAS CREDITS
CONTENT_TYPE = "image/jpeg"
_TIMEOUT = 60
_BASE_URL = "https://developer.remini.ai/api"
MAX_FILE_SIZE_MB = 5  # Set a max file size for images

def _get_image_md5_content(file_path: str) -> tuple[str, bytes]:
    with open(file_path, "rb") as fp:
        content = fp.read()
        image_md5 = base64.b64encode(hashlib.md5(content).digest()).decode("utf-8")
    return image_md5, content

async def enhance_photo_and_send_link(file_path: str, chat_id: int):
    image_md5, content = _get_image_md5_content(file_path)

    try:
        async with httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
        ) as client:
            # Initiate the enhancement process
            response = await client.post(
                "/tasks",
                json={
                    "tools": [
                        {"type": "face_enhance", "mode": "beautify"},
                        {"type": "background_enhance", "mode": "base"}
                    ],
                    "image_md5": image_md5,
                    "image_content_type": CONTENT_TYPE
                }
            )
            response.raise_for_status()
            body = response.json()
            task_id = body["task_id"]

            # Upload the photo
            response = await client.put(
                body["upload_url"],
                headers=body["upload_headers"],
                content=content,
                timeout=_TIMEOUT
            )
            response.raise_for_status()

            # Process the task
            response = await client.post(f"/tasks/{task_id}/process")
            response.raise_for_status()

            # Polling to check the status of the enhancement task
            for i in range(50):
                response = await client.get(f"/tasks/{task_id}")
                response.raise_for_status()

                if response.json()["status"] == "completed":
                    break
                else:
                    await asyncio.sleep(2)

            # Send the output URL to the user
            output_url = response.json()["result"]["output_url"]
            await bot.send_message(chat_id, f"<b>Enhanced photo: </b> {output_url}", parse_mode='html')

    except httpx.RequestError as e:
        await bot.send_message(chat_id, f"<b>An error occurred: {e}</b>", parse_mode='html')

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    # Send welcome image
    welcome_image_path = "welcome.jpg"  # Replace with the path to your welcome image
    with open(welcome_image_path, 'rb') as image_file:
        await bot.send_photo(message.chat.id, photo=image_file)
    
    # Create an inline keyboard with buttons
    keyboard = InlineKeyboardMarkup(row_width=2)
    dev_button = InlineKeyboardButton("Dev 👨‍💻", url="https://t.me/l_abani")
    update_button = InlineKeyboardButton("Update ✅", url="https://t.me/NOOBPrivate")
    features_button = InlineKeyboardButton("LeechxGroup 🔧", url="https://t.me/+Vng7VDXDy_M4MjNl")
    keyboard.add(dev_button, update_button, features_button)

    await bot.send_message(
        message.chat.id,
        "<b>Welcome! I am a Smart Enhancer BOT. Please send me a photo to enhance.</b>",
        parse_mode='html',
        reply_markup=keyboard
    )

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo(message: types.Message):
    photo = message.photo[-1]
    
    # Get file size in MB
    file_info = await bot.get_file(photo.file_id)
    file_size = file_info.file_size / (1024 * 1024)
    
    if file_size > MAX_FILE_SIZE_MB:
        await bot.send_message(
            message.chat.id,
            f"<b>The file is too large! Please send a file smaller than {MAX_FILE_SIZE_MB} MB.</b>",
            parse_mode='html'
        )
        return

    # Download and save the photo
    file_path = os.path.join(os.getcwd(), f"{photo.file_unique_id}.jpg")
    await photo.download(file_path)
    
    # Notify the user that the enhancement is starting
    await bot.send_message(message.chat.id, "<b>Enhancing your photo...</b>", parse_mode='html')

    # Enhance the photo and send the result
    await enhance_photo_and_send_link(file_path, message.chat.id)

@dp.message_handler()
async def handle_invalid_message(message: types.Message):
    await bot.send_message(
        message.chat.id,
        "<b>I am not allowed to receive text messages or emojis.\n\nPlease send only photos.</b>",
        parse_mode='html'
    )

@app.route('/webhook', methods=['POST'])
def webhook():
    json_str = request.get_data(as_text=True)
    update = types.Update.de_json(json_str)
    asyncio.run(dp.process_update(update))
    return 'OK', 200

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    from aiohttp import web

    # Run Flask and the bot's polling loop
    loop = asyncio.get_event_loop()
    app_runner = web.AppRunner(web.Application())
    loop.run_until_complete(app_runner.setup())
    web_server = web.TCPSite(app_runner.app, '0.0.0.0', 5000)
    loop.run_until_complete(web_server.start())
    loop.create_task(dp.start_polling())
    loop.run_forever()
