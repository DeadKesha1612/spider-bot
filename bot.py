import telebot
import json
import os
from flask import Flask

TOKEN = "9037922529:AAGajC8OlDJCkagMVBEV0qGSivuDRDdYxyk"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

@app.route('/')
def home():
    return "Hram Pauka Bot is running!"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    print(f"Получена команда /start от {message.chat.id}")
    markup = telebot.types.InlineKeyboardMarkup()
    web_app = telebot.types.WebAppInfo(url="https://storied-concha-ccd27a.netlify.app/") 
    markup.add(telebot.types.InlineKeyboardButton("🛍 Открыть каталог «Храм Паука»", web_app=web_app))
    
    bot.send_message(
        message.chat.id, 
        "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\nНажми кнопку ниже, чтобы открыть каталог:",
        reply_markup=markup
    )

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    print(f"--- ПОЛУЧЕНЫ ДАННЫЕ ИЗ WEB APP от {message.chat.id} ---")
    try:
        cart_items = json.loads(message.web_app_data.data)
        
        if not cart_items:
            bot.send_message(message.chat.id, "Корзина пуста!")
            return

        order_text = "🛒 **Новый заказ из каталога Храм Паука:**\n\n"
        total = 0
        
        for item in cart_items:
            name = item.get('name', 'Товар')
            price = item.get('price', 0)
            order_text += f"• {name} — {price} ₽\n"
            total += price
            
        order_text += f"\n💰 **Итого к оплате:** {total} ₽"
        
        bot.send_message(message.chat.id, order_text, parse_mode="Markdown")
        print("Заказ успешно отправлен!")
        
    except Exception as e:
        print(f"Ошибка обработки заказа: {e}")
        bot.send_message(message.chat.id, f"Ошибка при обработке заказа.")

# Запуск поллинга в отдельном безопасном потоке только один раз
import threading
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("RENDER"):
    def run_polling():
        print("Старт бесконечного опроса Telegram...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    
    t = threading.Thread(target=run_polling, daemon=True)
    t.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    # Включаем use_reloader=False, чтобы Flask не перезапускал приложение и не плодил копии бота
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
