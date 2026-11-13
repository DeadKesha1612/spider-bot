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
    markup = telebot.types.InlineKeyboardMarkup()
    web_app = telebot.types.WebAppInfo(url="https://deadkesha1612.github.io/spider-bot/") 
    markup.add(telebot.types.InlineKeyboardButton("🛍 Открыть каталог «Храм Паука»", web_app=web_app))
    
    bot.send_message(
        message.chat.id, 
        "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\nНажми кнопку ниже, чтобы открыть каталог:",
        reply_markup=markup
    )

@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    print(f"--- СЫРЫЕ ДАННЫЕ: {message.web_app_data.data} ---")
    # Отправляем в чат всё, что пришло от каталога, без сложной обработки
    bot.send_message(
        message.chat.id, 
        f"📥 Получены данные из каталога:\n\n{message.web_app_data.data}"
    )

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Вебхук установлен на: {WEBHOOK_URL}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
