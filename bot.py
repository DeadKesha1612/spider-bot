import telebot
import json
import time

TOKEN = "9037922529:AAGajC8OlDJCkagMVBEV0qGSivuDRDdYxyk"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
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
    try:
        cart_items = json.loads(message.web_app_data.data)
        
        if not cart_items:
            bot.send_message(message.chat.id, "Корзина пуста!")
            return

        order_text = "🛒 **Новый заказ из каталога Храм Паука:**\n\n"
        total = 0
        
        for item in cart_items:
            order_text += f"• {item['name']} — {item['price']} ₽\n"
            total += item['price']
            
        order_text += f"\n💰 **Итого к оплате:** {total} ₽"
        
        bot.send_message(message.chat.id, order_text, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, "Ошибка при обработке заказа.")

if __name__ == '__main__':
    while True:
        try:
            print("Запуск бота...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Ошибка: {e}. Переподключение через 5 секунд...")
            time.sleep(5)
