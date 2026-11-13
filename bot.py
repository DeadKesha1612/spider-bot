import telebot
import json

TOKEN = "9037922529:AAGajC8OlDJCkagMVBEV0qGSivuDRDdYxyk"
bot = telebot.TeleBot(TOKEN)

# Приветствие и кнопка со ссылкой на твой Netlify-каталог
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

# Обработчик заказов из мини-приложения
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
    bot.infinity_polling()
