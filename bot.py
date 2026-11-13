import telebot
import json
import os
from flask import Flask, request

TOKEN = "9037922529:AAGajC8OlDJCkagMVBEV0qGSivuDRDdYxyk"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

WEBHOOK_URL = f"https://thespidertemplebot.onrender.com/{TOKEN}"

@app.route('/')
def home():
    return "Hram Pauka Bot is running via Webhooks!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

@bot.message_handler(commands=['start'])
def send_welcome(message):
    print(f"Получена команда /start от {message.chat.id}")
    markup = telebot.types.InlineKeyboardMarkup()
    # Ссылка на каталог обновлена на GitHub Pages
    web_app = telebot.types.WebAppInfo(url="https://deadkesha1612.github.io/spider-bot/") 
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
        print("Заказ успешно отправлен в чат!")
        
    except Exception as e:
        print(f"Ошибка обработки заказа: {e}")
        bot.send_message(message.chat.id, "Ошибка при обработке заказа.")

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Вебхук установлен на: {WEBHOOK_URL}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
