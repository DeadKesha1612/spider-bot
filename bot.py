import telebot
import json
import os
from flask import Flask, request

TOKEN = "9037922529:AAGajC8OlDJCkagMVBEV0qGSivuDRDdYxyk"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)
WEBHOOK_URL = f"https://thespidertemplebot.onrender.com/{TOKEN}"

# Файл для хранения товаров на сервере Render
PRODUCTS_FILE = "products.json"

# Временное хранилище корзин пользователей в памяти
user_carts = {}
# Состояние для пошагового добавления товаров админом
admin_states = {}

def load_products():
    if os.path.exists(PRODUCTS_FILE):
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Базовые товары по умолчанию, если файла еще нет
    return {
        "Темляки и брелоки": [
            {"id": "l1", "name": "Темляк 'Самурай'", "price": 450, "time": "1-2 дня"}
        ],
        "Браслеты из паракорда": [
            {"id": "b1", "name": "Браслет 'Кобра'", "price": 600, "time": "1 день"}
        ]
    }

def save_products(data):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@app.route('/')
def home():
    return "Hram Pauka Bot is running strictly in-chat!"

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
    text = (
        "Приветствую! Добро пожаловать в мастерскую **Храм Паука**.\n\n"
        "Здесь ты можешь посмотреть каталог изделий, собрать заказ "
        "и отправить его прямо в чат."
    )
    show_main_menu(message.chat.id, text)

def show_main_menu(chat_id, text):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛍 Открыть каталог", callback_data="catalog"))
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар (Админ)", callback_data="add_product_start"))
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# --- КАТАЛОГ И ПОКУПКИ ---

@bot.callback_query_handler(func=lambda call: call.data == "catalog")
def open_catalog(call):
    products = load_products()
    markup = telebot.types.InlineKeyboardMarkup()
    
    for cat_name, items in products.items():
        markup.add(telebot.types.InlineKeyboardButton(f"📁 --- {cat_name.upper()} ---", callback_data="noop"))
        for item in items:
            btn_text = f"{item['name']} — {item['price']} ₽"
            markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"add_{item['id']}"))
            
    markup.add(telebot.types.InlineKeyboardButton("🛒 В корзину / Оформить", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    
    bot.edit_message_text(
        "🛍 **Каталог товаров:**\nНажми на товар, чтобы добавить его в корзину:", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def add_to_cart(call):
    item_id = call.data.replace("add_", "")
    products = load_products()
    
    found_item = None
    for items in products.values():
        for item in items:
            if item['id'] == item_id:
                found_item = item
                break
                
    if found_item:
        chat_id = call.message.chat.id
        if chat_id not in user_carts:
            user_carts[chat_id] = []
        user_carts[chat_id].append(found_item)
        bot.answer_callback_query(call.id, f"✅ Добавлено: {found_item['name']}")
    else:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")

@bot.callback_query_handler(func=lambda call: call.data == "view_cart")
def view_cart(call):
    chat_id = call.message.chat.id
    cart = user_carts.get(chat_id, [])
    
    markup = telebot.types.InlineKeyboardMarkup()
    
    if not cart:
        text = "🛒 Ваша корзина пуста."
        markup.add(telebot.types.InlineKeyboardButton("🛍 В каталог", callback_data="catalog"))
    else:
        text = "🛒 **Ваш заказ:**\n\n"
        total = 0
        for idx, item in enumerate(cart):
            text += f"{idx + 1}. {item['name']} — {item['price']} ₽\n"
            total += item['price']
        text += f"\n💰 **Итого:** {total} ₽"
        
        markup.add(telebot.types.InlineKeyboardButton("🚀 Оформить заказ", callback_data="checkout"))
        markup.add(telebot.types.InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"))
        markup.add(telebot.types.InlineKeyboardButton("🛍 Продолжить покупки", callback_data="catalog"))
        
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
def clear_cart(call):
    user_carts[call.message.chat.id] = []
    view_cart(call)

@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def checkout_order(call):
    chat_id = call.message.chat.id
    cart = user_carts.get(chat_id, [])
    if not cart:
        return
        
    order_text = f"🚨 **НОВЫЙ ЗАКАЗ ИЗ ЧАТА!**\n(ID клиента: `{chat_id}`)\n\n"
    total = 0
    for item in cart:
        order_text += f"• {item['name']} — {item['price']} ₽\n"
        total += item['price']
    order_text += f"\n💰 **Сумма:** {total} ₽"
    
    # Отправляем подтверждение клиенту и копию заказа тебе в чат
    bot.send_message(chat_id, "✅ **Заказ успешно оформлен!** Спасибо, что выбрали «Храм Паука»!", parse_mode="Markdown")
    bot.send_message(chat_id, order_text, parse_mode="Markdown")
    
    user_carts[chat_id] = []

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_main_menu(call.message.chat.id, "Главное меню:")

@bot.callback_query_handler(func=lambda call: call.data == "noop")
def noop(call):
    bot.answer_callback_query(call.id)

# --- АДМИНКА: ДОБАВЛЕНИЕ ТОВАРОВ ИЗ ЧАТА ---

@bot.callback_query_handler(func=lambda call: call.data == "add_product_start")
def add_product_start(call):
    admin_states[call.message.chat.id] = {"step": "category"}
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("Темляки и брелоки", callback_data="cat_lanyards"))
    markup.add(telebot.types.InlineKeyboardButton("Браслеты из паракорда", callback_data="cat_bracelets"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="main_menu"))
    bot.edit_message_text("📁 Выбери категорию для нового товара:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def add_product_cat(call):
    cat_key = call.data.replace("cat_", "")
    cat_name = "Темляки и брелоки" if cat_key == "lanyards" else "Браслеты из паракорда"
    admin_states[call.message.chat.id] = {"step": "name", "category": cat_name}
    bot.edit_message_text("✍️ Напиши **название** нового товара ответным сообщением:", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.chat.id in admin_states)
def handle_admin_input(message):
    state = admin_states[message.chat.id]
    chat_id = message.chat.id
    
    if state["step"] == "name":
        state["name"] = message.text
        state["step"] = "price"
        bot.send_message(chat_id, "💵 Напиши **цену** товара цифрами (например: `750`):", parse_mode="Markdown")
        
    elif state["step"] == "price":
        try:
            price = int(message.text.strip())
            state["price"] = price
            state["step"] = "time"
            bot.send_message(chat_id, "⏱ Напиши **срок изготовления** (например: `1-2 дня`):")
        except ValueError:
            bot.send_message(chat_id, "❌ Цена должна быть числом. Введи цену еще раз:")
            
    elif state["step"] == "time":
        state["time"] = message.text.strip()
        
        products = load_products()
        cat = state["category"]
        
        new_id = f"item_{len(products.get(cat, [])) + 1}_{int(os.urandom(2).hex(), 16)}"
        new_item = {
            "id": new_id,
            "name": state["name"],
            "price": state["price"],
            "time": state["time"]
        }
        
        if cat not in products:
            products[cat] = []
        products[cat].append(new_item)
        save_products(products)
        
        del admin_states[chat_id]
        bot.send_message(chat_id, f"🎉 **Товар успешно добавлен!**\n\n📌 Название: {new_item['name']}\n💵 Цена: {new_item['price']} ₽\n⏱ Срок: {new_item['time']}", parse_mode="Markdown")
        show_main_menu(chat_id, "Главное меню:")

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print(f"Вебхук установлен на: {WEBHOOK_URL}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
