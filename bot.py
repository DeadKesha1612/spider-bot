import telebot
import json

TOKEN = "9037922529:AAFXbac00LXXVDpMaX2zK9ua2HKpQvWxCko"
bot = telebot.TeleBot(TOKEN)

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
