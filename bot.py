import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiohttp import web

# Твои данные
TOKEN = "9037922529:AAGw-EXAMPLE_TOKEN_HERE"  # токен твоего бота
ADMIN_ID = 5393257255
WEB_APP_URL = "https://dead-kesha.netlify.app/"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище заказов или базовая логика
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = types.InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="🛍 Открыть каталог «Храм Паука»",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    ))
    await message.answer(
        "Приветствую! Добро пожаловать в мастерскую **Храм Паука**.\n\n"
        "Нажми кнопку ниже, чтобы выбрать кастомные бусины, темляки, браслеты или сделать индивидуальный заказ:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# Заглушка веб-сервера для Render (чтобы проходил проверку портов)
async def handle(request):
    return web.Response(text="Spider Bot is running 24/7!")

app = web.Application()
app.router.add_get("/", handle)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    # Запускаем веб-сервер для Render в фоне
    await start_web_server()
    # Запускаем телеграм бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
