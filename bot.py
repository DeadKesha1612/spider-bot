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

CATEGORIES = {
    "bracelets": "Браслеты",
    "lanyards": "Брелоки / Темляки",
    "beads": "Бусины, фигурки"
}

def load_products():
    if not os.path.exists(PRODUCTS_FILE):
        return {}
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"Ошибка чтения products.json: {e}")
    return {}

def save_products(data):
    try:
        temp_file = PRODUCTS_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_file, PRODUCTS_FILE)
    except Exception as e:
        print(f"Ошибка сохранения products.json: {e}")

if not os.path.exists(PRODUCTS_FILE):
    save_products({})

@app.route('/')
def home():
    return "Hram Pauka Bot is running!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    content_type = request.headers.get('content-type', '')
    if 'application/json' in content_type:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return 'Forbidden', 403

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_carts[chat_id] = []
    if chat_id in admin_states:
        del admin_states[chat_id]
    show_main_menu(chat_id)

def show_main_menu(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🛍 Каталог", callback_data="catalog"))
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    
    text = (
        "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\n"
        "Главное меню:"
    )
    bot.send_message(chat_id, text, reply_markup=markup)

# --- КАТАЛОГ И КАТЕГОРИИ ---

@bot.callback_query_handler(func=lambda call: call.data == "catalog")
def open_catalog(call):
    bot.answer_callback_query(call.id)
    markup = telebot.types.InlineKeyboardMarkup()
    
    for cat_key, cat_name in CATEGORIES.items():
        markup.add(telebot.types.InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_key}_0"))
        
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    
    text = "🛍 Выбери категорию товаров:"
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
        if isinstance(item, dict) and str(item.get("category")).strip() == str(cat_key).strip():
            cat_items.append((item_id, item))
    
    markup = telebot.types.InlineKeyboardMarkup()
    is_admin = (int(call.message.chat.id) == int(ADMIN_ID))
    
    if not cat_items:
        text = f"📁 Категория: *{CATEGORIES.get(cat_key, 'Товары')}*\n\nВ этой категории пока нет товаров."
        
        nav_buttons = [
            telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat_{cat_key}_0"),
            telebot.types.InlineKeyboardButton("Вперед ➡️", callback_data=f"cat_{cat_key}_0")
        ]
        markup.row(*nav_buttons)
        
        if is_admin:
            markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"admin_add_{cat_key}"))
            
        markup.add(telebot.types.InlineKeyboardButton("🔙 К категориям", callback_data="catalog"))
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        return

    total_items = len(cat_items)
    index = index % total_items
    item_id, item = cat_items[index]
    
    name = item.get('name', 'Товар')
    price = item.get('price', 0)
    material = item.get('material', 'Не указан')
    time_val = item.get('time', 'Не указан')

    text = (
        f"📁 Категория: *{CATEGORIES.get(cat_key)}* (Товар {index + 1} из {total_items})\n\n"
        f"📌 **{name}**\n\n"
        f"💵 Цена: {price} ₽\n"
        f"🧵 Материал: {material}\n"
        f"⏱ Срок изготовления: {time_val}"
    )
    
    markup.add(telebot.types.InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"cart_add_{item_id}"))
    
    nav_buttons = [
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat_{cat_key}_{index - 1}"),
        telebot.types.InlineKeyboardButton("Вперед ➡️", callback_data=f"cat_{cat_key}_{index + 1}")
    ]
    markup.row(*nav_buttons)
    
    if is_admin:
        markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"admin_add_{cat_key}"))
        markup.add(
            telebot.types.InlineKeyboardButton("✏️ Редактировать товар", callback_data=f"admin_edit_{item_id}"),
            telebot.types.InlineKeyboardButton("🗑 Удалить товар", callback_data=f"admin_del_{cat_key}_{index}_{item_id}")
        )

    markup.add(telebot.types.InlineKeyboardButton("🔙 К категориям", callback_data="catalog"))
    
    if item.get("photo"):
        bot.send_photo(call.message.chat.id, item["photo"], caption=text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

# --- КОРЗИНА И ЗАКАЗЫ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("cart_add_"))
def add_to_cart(call):
    item_id = call.data.replace("cart_add_", "")
    products = load_products()
    item = products.get(item_id)
    
    if item:
        chat_id = call.message.chat.id
        if chat_id not in user_carts:
            user_carts[chat_id] = []
        user_carts[chat_id].append(item)
        bot.answer_callback_query(call.id, f"✅ Добавлено: {item.get('name', 'Товар')}")
    else:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")

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
            name = item.get('name', 'Товар')
            price = item.get('price', 0)
            text += f"{idx + 1}. {name} — {price} ₽\n"
            total += price
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
        
    order_text = f"🚨 **НОВЫЙ ЗАКАЗ ИЗ КАТАЛОГА!**\n(ID клиента: `{chat_id}`)\n\n"
    total = 0
    for item in cart:
        name = item.get('name', 'Товар')
        price = item.get('price', 0)
        order_text += f"• {name} — {price} ₽\n"
        total += price
    order_text += f"\n💰 **Сумма:** {total} ₽"
    
    bot.send_message(chat_id, "✅ **Заказ успешно оформлен!** Спасибо, что выбрали «Храм Паука»!", parse_mode="Markdown")
    
    try:
        bot.send_message(ADMIN_ID, order_text, parse_mode="Markdown")
    except Exception as e:
        print(f"Не удалось отправить заказ админу: {e}")
    
    user_carts[chat_id] = []
    show_main_menu(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    if call.message.chat.id in admin_states:
        del admin_states[call.message.chat.id]
    show_main_menu(call.message.chat.id)

# --- АДМИНКА ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_"))
def admin_add_start(call):
    bot.answer_callback_query(call.id)
    if int(call.message.chat.id) != int(ADMIN_ID):
        return
    cat_key = call.data.replace("admin_add_", "")
    
    admin_states[call.message.chat.id] = {"action": "add", "category": cat_key, "step": "name"}
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
    
    bot.send_message(call.message.chat.id, f"✍️ [Добавление в «{CATEGORIES.get(cat_key)}»] Шаг 1/5: Напиши название товара:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_del_"))
def admin_delete_item(call):
    bot.answer_callback_query(call.id)
    if int(call.message.chat.id) != int(ADMIN_ID):
        return
    
    parts = call.data.replace("admin_del_", "").split("_")
    cat_key = parts[0]
    index = int(parts[1])
    item_id = parts[2]
    
    products = load_products()
    if item_id in products:
        del products[item_id]
        save_products(products)
        bot.answer_callback_query(call.id, "✅ Товар успешно удален!")
    
    call.data = f"cat_{cat_key}_{index}"
    view_category_item(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_edit_"))
def admin_edit_start(call):
    bot.answer_callback_query(call.id)
    if int(call.message.chat.id) != int(ADMIN_ID):
        return
    item_id = call.data.replace("admin_edit_", "")
    products = load_products()
    item = products.get(item_id)
    
    if not item:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")
        return
        
    admin_states[call.message.chat.id] = {"action": "edit", "item_id": item_id, "step": "name"}
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
    
    bot.send_message(call.message.chat.id, f"✏️ [Редактирование: {item.get('name')}]\nШаг 1/3: Напиши новое название:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "skip_photo")
def skip_photo(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    if chat_id in admin_states and admin_states[chat_id].get("step") == "photo":
        admin_states[chat_id]["photo"] = None
        admin_states[chat_id]["step"] = "price"
        bot.send_message(chat_id, "💵 Шаг 3/5: Напиши цену товара цифрами (например: 750):")

@bot.message_handler(content_types=['photo'], func=lambda message: message.chat.id in admin_states and admin_states[message.chat.id].get("step") == "photo")
def handle_admin_photo(message):
    if int(message.chat.id) != int(ADMIN_ID):
        return
    chat_id = message.chat.id
    state = admin_states[chat_id]
    
    state["photo"] = message.photo[-1].file_id if message.photo else None
    state["step"] = "price"
    bot.send_message(chat_id, "💵 Шаг 3/5: Напиши цену цифрами (например: 600):")

@bot.message_handler(content_types=['text'], func=lambda message: message.chat.id in admin_states)
def handle_admin_text(message):
    if int(message.chat.id) != int(ADMIN_ID):
        return
        
    chat_id = message.chat.id
    state = admin_states[chat_id]
    action = state.get("action")
    step = state.get("step")

    if action == "add":
        if step == "name":
            if not message.text:
                bot.send_message(chat_id, "❌ Введи текстовое название:")
                return
            state["name"] = message.text.strip()
            state["step"] = "photo"
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("Пропустить фото", callback_data="skip_photo"))
            bot.send_message(chat_id, "🖼 Шаг 2/5: Отправь фото товара (или нажми кнопку):", reply_markup=markup)
            return
            
        elif step == "photo":
            # Если на шаге фото прислали текст вместо картинки
            bot.send_message(chat_id, "🖼 Пожалуйста, отправь фото товара или нажми «Пропустить фото»:")
            return
            
        elif step == "price":
            try:
                state["price"] = int(message.text.strip())
                state["step"] = "material"
                bot.send_message(chat_id, "🧵 Шаг 4/5: Укажи материал (например: Паракорд 550):")
            except ValueError:
                bot.send_message(chat_id, "❌ Цена должна быть числом. Повтори ввод:")
            return
                
        elif step == "material":
            if not message.text:
                bot.send_message(chat_id, "❌ Введи материал текстом:")
                return
            state["material"] = message.text.strip()
            state["step"] = "time"
            bot.send_message(chat_id, "⏱ Шаг 5/5: Укажи срок изготовления (например: 1-2 дня):")
            return
            
        elif step == "time":
            text_val = message.text.strip() if message.text else "1-2 дня"
            state["time"] = text_val
            
            products = load_products()
            item_id = f"item_{int(os.urandom(3).hex(), 16)}"
            
            products[item_id] = {
                "category": state["category"],
                "name": state["name"],
                "photo": state.get("photo"),
                "price": state["price"],
                "material": state["material"],
                "time": state["time"]
            }
            
            save_products(products)
            cat_key = state["category"]
            del admin_states[chat_id]
            
            bot.send_message(chat_id, f"🎉 Товар успешно добавлен в категорию «{CATEGORIES.get(cat_key)}»!")
            show_main_menu(chat_id)
            return

    elif action == "edit":
        item_id = state["item_id"]
        products = load_products()
        item = products.get(item_id, {})
        
        if step == "name":
            state["new_name"] = message.text.strip() if message.text else item.get('name')
            state["step"] = "price"
            bot.send_message(chat_id, f"💵 Шаг 2/3: Напиши новую цену (текущая: {item.get('price')}):")
            return
            
        elif step == "price":
            try:
                state["new_price"] = int(message.text.strip())
                state["step"] = "material"
                bot.send_message(chat_id, f"🧵 Шаг 3/3: Укажи новый материал (текущий: {item.get('material')}):")
            except ValueError:
                bot.send_message(chat_id, "❌ Цена должна быть числом. Повтори ввод:")
            return
                
        elif step == "material":
            if not message.text:
                bot.send_message(chat_id, "❌ Введи материал текстом:")
                return
            
            item["name"] = state["new_name"]
            item["price"] = state["new_price"]
            item["material"] = message.text.strip()
            
            products[item_id] = item
            save_products(products)
            del admin_states[chat_id]
            
            bot.send_message(chat_id, "✅ Товар успешно обновлен!")
            show_main_menu(chat_id)
            return

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    
    try:
        bot.delete_chat_menu_button()
    except Exception:
        pass
        
    print(f"Вебхук установлен на: {WEBHOOK_URL}")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
