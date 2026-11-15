import telebot
import json
import requests

TOKEN = "9263601739:AAFIjFxcaOPi0T4SWR-9eF262TAkoAKyCn0"
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 5393257255

SUPABASE_URL = "https://cztrrtvajptalfjdfpmy.supabase.co"
SUPABASE_KEY = "sb_publishable_2HnmPT650giFwrbjE8G4IQ_2GYLbPQ-"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

user_carts = {}

def load_products():
    try:
        url = f"{SUPABASE_URL}/rest/v1/products?select=*"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            rows = response.json()
            products_dict = {}
            for row in rows:
                p_id = row.get("id")
                products_dict[p_id] = {
                    "category": row.get("category"),
                    "name": row.get("name"),
                    "photo": row.get("photo"),
                    "price": row.get("price"),
                    "material": row.get("material"),
                    "time": row.get("time")
                }
            return products_dict
    except Exception as e:
        print(f"Ошибка загрузки товаров: {e}")
    return {}

def get_reply_markup():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, persistent=True)
    markup.add(telebot.types.KeyboardButton("🕷 Запустить Храм Паука"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_carts[chat_id] = []
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛍 Каталог", callback_data="catalog"))
    
    text = "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\nГлавное меню:"
    reply_kb = get_reply_markup()
    bot.send_message(chat_id, text, reply_markup=markup, reply_markup_keyboard=reply_kb)

@bot.message_handler(func=lambda msg: msg.text == "🕷 Запустить Храм Паука")
def handle_reply_start(message):
    send_welcome(message)

@bot.callback_query_handler(func=lambda call: call.data == "catalog")
def open_catalog(call):
    bot.answer_callback_query(call.id)
    products = load_products()
    
    text = "🛍 Доступные товары:\n\n"
    if not products:
        text += "В каталоге пока пусто."
    else:
        for p_id, item in products.items():
            text += f"• {item.get('name')} — {item.get('price')} ₽\n"
            
    bot.send_message(call.message.chat.id, text)

if __name__ == '__main__':
    # Сбрасываем старые вебхуки, чтобы поллинг работал без конфликтов
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=true")
    except Exception:
        pass
        
    print("Бот успешно запущен и слушает Telegram...")
    bot.infinity_polling(skip_pending=True)
