import telebot
import os
import json
import requests
from flask import Flask, request

TOKEN = "9263601739:AAFhakRpWA0uOrev0vQ7TRRk2iFLOMdn5Y8"
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
admin_states = {}
custom_states = {}
size_states = {}
active_orders = {}

CATEGORIES = {
    "bracelets": "Браслеты",
    "lanyards": "Брелоки / Темляки",
    "beads": "Бусины, фигурки"
}

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
        print(f"Ошибка загрузки из Supabase: {e}")
    return {}

def get_next_order_number():
    try:
        url = f"{SUPABASE_URL}/rest/v1/orders?select=order_id&order=order_id.desc&limit=1"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            rows = response.json()
            if rows and "order_id" in rows[0]:
                return int(rows[0]["order_id"]) + 1
    except Exception as e:
        print(f"Ошибка получения номера заказа: {e}")
    return 1

def save_order_to_db(order_id, client_id, cart_items, total_price):
    try:
        url = f"{SUPABASE_URL}/rest/v1/orders"
        payload = {
            "order_id": order_id,
            "client_id": client_id,
            "items": json.dumps(cart_items, ensure_ascii=False),
            "total": total_price,
            "status": "new"
        }
        requests.post(url, headers=HEADERS, json=payload)
    except Exception as e:
        print(f"Ошибка сохранения заказа в БД: {e}")

def clear_user_states(chat_id):
    for state_dict in (admin_states, custom_states, size_states):
        if chat_id in state_dict:
            del state_dict[chat_id]

def get_reply_markup():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)
    markup.add(telebot.types.KeyboardButton("🕷 Запустить Храм Паука"))
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_carts[chat_id] = []
    clear_user_states(chat_id)
    show_main_menu(chat_id)

@bot.message_handler(func=lambda msg: msg.text == "🕷 Запустить Храм Паука")
def handle_reply_start(message):
    chat_id = message.chat.id
    user_carts[chat_id] = []
    clear_user_states(chat_id)
    show_main_menu(chat_id)

def show_main_menu(chat_id, message_id=None):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛍 Каталог", callback_data="catalog"))
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    
    text = "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\nГлавное меню:"
    reply_kb = get_reply_markup()
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, reply_markup_keyboard=reply_kb)

@bot.callback_query_handler(func=lambda call: call.data == "catalog")
def open_catalog(call):
    bot.answer_callback_query(call.id)
    clear_user_states(call.message.chat.id)
    markup = telebot.types.InlineKeyboardMarkup()
    
    for cat_key, cat_name in CATEGORIES.items():
        markup.add(telebot.types.InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_key}_0"))
        
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    
    text = "🛍 Выбери категорию товаров:"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def view_category_item(call):
    bot.answer_callback_query(call.id)
    parts = call.data.split("_")
    cat_key = parts[1]
    index = int(parts[2])
    
    products = load_products()
    cat_items = []
    for item_id, item in products.items():
        if isinstance(item, dict):
            item_cat = str(item.get("category", "")).strip().lower()
            target_cat = str(cat_key).strip().lower()
            if item_cat == target_cat or \
               (target_cat == "bracelets" and "браслет" in item_cat) or \
               (target_cat == "beads" and ("бусин" in item_cat or "фигурк" in item_cat)):
                cat_items.append((item_id, item))
    
    markup = telebot.types.InlineKeyboardMarkup()
    is_admin = (int(call.message.chat.id) == int(ADMIN_ID))
    
    if not cat_items:
        text = f"📁 Категория: {CATEGORIES.get(cat_key, 'Товары')}\n\nВ этой категории пока нет товаров."
        markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
        markup.add(telebot.types.InlineKeyboardButton("🔙 К категориям", callback_data="catalog"))
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        except Exception:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
        return

    total_items = len(cat_items)
    index = index % total_items
    item_id, item = cat_items[index]
    
    name = item.get('name', 'Товар')
    price = item.get('price', 0)
    material = item.get('material', 'Не указан')
    time_val = item.get('time', 'Не указан')
    current_photo = item.get("photo")
    
    text = (
        f"📌 {name}\n\n"
        f"🧵 Материал: {material}\n"
        f"💵 Цена: {price} ₽\n"
        f"⏱ Срок изготовления: {time_val}"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"cart_add_{item_id}"))
    
    nav_buttons = [
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat_{cat_key}_{index - 1}"),
        telebot.types.InlineKeyboardButton("Вперед ➡️", callback_data=f"cat_{cat_key}_{index + 1}")
    ]
    markup.row(*nav_buttons)
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 К категориям", callback_data="catalog"))

    try:
        if current_photo:
            media = telebot.types.InputMediaPhoto(current_photo, caption=text)
            bot.edit_message_media(media, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception:
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        if current_photo:
            bot.send_photo(call.message.chat.id, current_photo, caption=text, reply_markup=markup)
        else:
            bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cart_add_"))
def add_to_cart(call):
    item_id = call.data.replace("cart_add_", "")
    products = load_products()
    item = products.get(item_id)
    if not item:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")
        return
    chat_id = call.message.chat.id
    if chat_id not in user_carts:
        user_carts[chat_id] = []
    user_carts[chat_id].append(item)
    bot.answer_callback_query(call.id, "✅ Добавлено в корзину!")

@bot.callback_query_handler(func=lambda call: call.data == "view_cart")
def view_cart(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    cart = user_carts.get(chat_id, [])
    markup = telebot.types.InlineKeyboardMarkup()
    
    if not cart:
        text = "🛒 Ваша корзина пуста."
        markup.add(telebot.types.InlineKeyboardButton("🛍 В каталог", callback_data="catalog"))
    else:
        text = "🛒 Ваш заказ:\n\n"
        total = 0
        for idx, item in enumerate(cart):
            text += f"{idx + 1}. {item.get('name')} — {item.get('price')} ₽\n"
            total += item.get('price', 0)
        text += f"\n💰 Итого: {total} ₽"
        markup.add(telebot.types.InlineKeyboardButton("🚀 Оформить заказ", callback_data="checkout"))
        markup.add(telebot.types.InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"))
        markup.add(telebot.types.InlineKeyboardButton("🛍 В каталог", callback_data="catalog"))
        
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    try:
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
def clear_cart(call):
    user_carts[call.message.chat.id] = []
    view_cart(call)

@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def checkout_order(call):
    bot.answer_callback_query(call.id)
    message = call.message
    chat_id = message.chat.id
    cart = user_carts.get(chat_id, [])
    if not cart:
        return
    order_id = get_next_order_number()
    total = sum(item.get('price', 0) for item in cart)
    save_order_to_db(order_id, chat_id, cart, total)
    bot.send_message(chat_id, f"✅ Заказ №{order_id} успешно оформлен! Мастер принял его в работу.")
    user_carts[chat_id] = []
    show_main_menu(chat_id, message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    show_main_menu(call.message.chat.id, call.message.message_id)

# --- FLASK СЕРВЕР ДЛЯ ВЕБХУКА ---
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    else:
        return "Invalid", 403

@app.route('/')
def index():
    return "Bot is running on Webhook!"

if __name__ == '__main__':
    WEBHOOK_URL = f"https://thespidertemplebot.onrender.com/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Вебхук успешно установлен на: {WEBHOOK_URL}")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
