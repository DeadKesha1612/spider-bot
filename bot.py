import telebot
import json
import os
from flask import Flask, request

TOKEN = "9037922529:AAGajC8OlDJCkagMVBEV0qGSivuDRDdYxyk"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)
WEBHOOK_URL = f"https://thespidertemplebot.onrender.com/{TOKEN}"

ADMIN_ID = 5393257255
PRODUCTS_FILE = "products.json"

user_carts = {}
admin_states = {}

def load_products():
    if os.path.exists(PRODUCTS_FILE):
        try:
            with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_products(data):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@app.route('/')
def home():
    return "Hram Pauka Bot is running!"

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
    user_carts[message.chat.id] = []
    if message.chat.id in admin_states:
        del admin_states[message.chat.id]
        
    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛍 Открыть каталог", callback_data="catalog"))
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    
    if chat_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар (Админ)", callback_data="admin_new_product"))
        
    text = (
        "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\n"
        "Главное меню:"
    )
    bot.send_message(chat_id, text, reply_markup=markup)

# --- КАТАЛОГ И ПОКУПКИ ---

@bot.callback_query_handler(func=lambda call: call.data == "catalog")
def open_catalog(call):
    bot.answer_callback_query(call.id)
    products = load_products()
    markup = telebot.types.InlineKeyboardMarkup()
    
    # Удаляем старое сообщение, чтобы не было конфликтов интерфейса
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    
    if not products:
        markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
        bot.send_message(call.message.chat.id, "🛍 Каталог товаров пуст.\nВ каталоге пока нет ни одного товара.", reply_markup=markup)
        return

    for item_id, item in products.items():
        btn_text = f"{item['name']} — {item['price']} ₽"
        markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"view_item_{item_id}"))
            
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина / Оформить", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    
    bot.send_message(
        call.message.chat.id, 
        "🛍 Каталог товаров:\nВыбери товар, чтобы посмотреть подробности и добавить в корзину:", 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_item_"))
def view_item_card(call):
    bot.answer_callback_query(call.id)
    item_id = call.data.replace("view_item_", "")
    products = load_products()
    item = products.get(item_id)
    
    if not item:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")
        return

    caption = (
        f"📌 {item['name']}\n\n"
        f"💵 Цена: {item['price']} ₽\n"
        f"🧵 Материал: {item['material']}\n"
        f"⏱ Срок изготовления: {item['time']}"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_{item_id}"))
    markup.add(telebot.types.InlineKeyboardButton("◀️ Назад в каталог", callback_data="catalog"))

    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    
    if item.get("photo"):
        bot.send_photo(call.message.chat.id, item["photo"], caption=caption, reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_") and not call.data.startswith("admin"))
def add_to_cart(call):
    item_id = call.data.replace("add_", "")
    products = load_products()
    item = products.get(item_id)
    
    if item:
        chat_id = call.message.chat.id
        if chat_id not in user_carts:
            user_carts[chat_id] = []
        user_carts[chat_id].append(item)
        bot.answer_callback_query(call.id, f"✅ Добавлено: {item['name']}")
    else:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")

@bot.callback_query_handler(func=lambda call: call.data == "view_cart")
def view_cart(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    cart = user_carts.get(chat_id, [])
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
        
    markup = telebot.types.InlineKeyboardMarkup()
    
    if not cart:
        text = "🛒 Ваша корзина пуста."
        markup.add(telebot.types.InlineKeyboardButton("🛍 В каталог", callback_data="catalog"))
    else:
        text = "🛒 Ваш заказ:\n\n"
        total = 0
        for idx, item in enumerate(cart):
            text += f"{idx + 1}. {item['name']} — {item['price']} ₽\n"
            total += item['price']
        text += f"\n💰 Итого: {total} ₽"
        
        markup.add(telebot.types.InlineKeyboardButton("🚀 Оформить заказ", callback_data="checkout"))
        markup.add(telebot.types.InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"))
        markup.add(telebot.types.InlineKeyboardButton("🛍 Продолжить покупки", callback_data="catalog"))
        
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
def clear_cart(call):
    user_carts[call.message.chat.id] = []
    view_cart(call)

@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def checkout_order(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    cart = user_carts.get(chat_id, [])
    if not cart:
        return
        
    order_text = f"🚨 НОВЫЙ ЗАКАЗ ИЗ ЧАТА!\n(ID клиента: `{chat_id}`)\n\n"
    total = 0
    for item in cart:
        order_text += f"• {item['name']} — {item['price']} ₽\n"
        total += item['price']
    order_text += f"\n💰 Сумма: {total} ₽"
    
    bot.send_message(chat_id, "✅ Заказ успешно оформлен! Спасибо, что выбрали «Храм Паука»!")
    bot.send_message(chat_id, order_text)
    
    user_carts[chat_id] = []

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    if call.message.chat.id in admin_states:
        del admin_states[call.message.chat.id]
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    show_main_menu(call.message.chat.id)

# --- АДМИНКА ДЛЯ ДОБАВЛЕНИЯ ТОВАРА ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_new_product")
def add_product_start(call):
    bot.answer_callback_query(call.id)
    if call.message.chat.id != ADMIN_ID:
        return
        
    admin_states[call.message.chat.id] = {"step": "name"}
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="main_menu"))
    
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
        
    bot.send_message(call.message.chat.id, "✍️ Шаг 1/5: Напиши название нового товара:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "skip_photo")
def skip_photo(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    if chat_id in admin_states and admin_states[chat_id]["step"] == "photo":
        admin_states[chat_id]["photo"] = None
        admin_states[chat_id]["step"] = "price"
        bot.send_message(chat_id, "💵 Шаг 3/5: Напиши цену товара цифрами (например: 750):")

@bot.message_handler(content_types=['text', 'photo'], func=lambda message: message.chat.id in admin_states)
def handle_admin_creation(message):
    if message.chat.id != ADMIN_ID:
        return
        
    chat_id = message.chat.id
    state = admin_states[chat_id]
    step = state["step"]

    if step == "name":
        if not message.text:
            bot.send_message(chat_id, "❌ Пожалуйста, введи текстовое название товара:")
            return
        state["name"] = message.text.strip()
        state["step"] = "photo"
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("Пропустить фото", callback_data="skip_photo"))
        bot.send_message(chat_id, "🖼 Шаг 2/5: Отправь фотографию товара (или нажми кнопку ниже):", reply_markup=markup)
        
    elif step == "photo":
        if message.photo:
            state["photo"] = message.photo[-1].file_id
        else:
            state["photo"] = None
            
        state["step"] = "price"
        bot.send_message(chat_id, "💵 Шаг 3/5: Напиши цену товара цифрами (например: 750):")
        
    elif step == "price":
        text_val = message.text.strip() if message.text else ""
        try:
            price = int(text_val)
            state["price"] = price
            state["step"] = "material"
            bot.send_message(chat_id, "🧵 Шаг 4/5: Укажи материал (например: Паракорд 550, бусина латунь):")
        except ValueError:
            bot.send_message(chat_id, "❌ Цена должна быть целым числом (например, 600). Введи цену еще раз:")
            
    elif step == "material":
        if not message.text:
            bot.send_message(chat_id, "❌ Пожалуйста, введи материал текстом:")
            return
        state["material"] = message.text.strip()
        state["step"] = "time"
        bot.send_message(chat_id, "⏱ Шаг 5/5: Укажи срок изготовления (например: 1-2 дня):")
        
    elif step == "time":
        if not message.text:
            bot.send_message(chat_id, "❌ Пожалуйста, введи срок текстом:")
            return
        state["time"] = message.text.strip()
        
        products = load_products()
        item_id = f"item_{int(os.urandom(3).hex(), 16)}"
        
        products[item_id] = {
            "name": state["name"],
            "photo": state.get("photo"),
            "price": state["price"],
            "material": state["material"],
            "time": state["time"]
        }
        
        save_products(products)
        del admin_states[chat_id]
        
        bot.send_message(chat_id, f"🎉 Товар успешно добавлен в каталог!\n\n📌 {state['name']} — {state['price']} ₽")
        show_main_menu(chat_id)

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    
    try:
        bot.delete_chat_menu_button()
    except Exception:
        pass
        
    print(f"Вебхук установлен на: {WEBHOOK_URL}")
    
    port = int(os.environ.format("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
