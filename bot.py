import asyncio
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = "9037922529:AAFXbac00LXXVDpMaX2zK9ua2HKpQvWxCko"
ADMIN_ID = 5393257255
WEBAPP_URL = "https://dead-kesha.netlify.app/"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="🕷 Открыть мастерскую Храма Паука",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ]],
        resize_keyboard=True
    )
    await message.answer(
        "Добро пожаловать в мастерскую **Храм Паука** 🕸\n\n"
        "Нажми кнопку ниже, чтобы собрать кастомное изделие, выбрать параметры и отправить заказ мастеру.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    data = json.loads(message.web_app_data.data)
    user = message.from_user
    username = f"@{user.username}" if user.username else f"ID: {user.id}"

    order_text = (
        f"🔥 **НОВЫЙ ЗАКАЗ | Храм Паука**\n"
        f"👤 Клиент: {user.full_name} ({username})\n\n"
        f"📦 **Тип:** {data['type']}\n"
        f"⚙️ **Изделие:** {data['itemDetails']}\n"
    )

    if data['type'] == 'Браслет':
        order_text += (
            f"📏 **Запястье:** {data['wrist']}\n"
            f"🔗 **Застежка:** {data['clasp']}\n"
            f"✨ **Разделители:** {data['spacers']}\n"
        )

    if data['type'] != 'Бусина':
        order_text += f"🎨 **Паракорд:** {data['paracordColor']}\n"

    order_text += (
        f"✍️ **Гравировка:** {data['engraving']}\n\n"
        f"💰 **Итого к оплате:** {data['total']} ₽"
    )

    # Отправляем тебе в личку
    await bot.send_message(ADMIN_ID, order_text, parse_mode="Markdown")

    # Отвечаем покупателю
    await message.answer(
        "✅ **Заказ успешно отправлен мастеру!**\n"
        "Параметры зафиксированы. Скоро с тобой свяжутся для подтверждения деталей и оплаты.",
        parse_mode="Markdown"
    )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
