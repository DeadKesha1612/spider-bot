import telebot
import os
import json
import requests
from flask import Flask, request

TOKEN = "9263601739:AAFIjFxcaOPi0T4SWR-9eF262TAkoAKyCn0"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)
WEBHOOK_URL = f"https://thespidertemplebot.onrender.com/{TOKEN}"

ADMIN_ID = 5393257255

# --- НАСТРОЙКИ SUPABASE ---
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

CUSTOM_OPTIONS = {
    "colors": ["Олива", "Койот", "Черный", "Камуфляж", "Песочный"],
    "thickness": {
        "Паракорд 550 (стандарт)": 550,
        "Микрокорд (тонкий)": 400
    },
    "weaves": {
        "Кобра (классика)": 0,
        "Змейка": 50,
        "Широкое (мощное)": 150
    },
    "beads": ["Самурай", "Маска Онимаска", "Череп", "Без бусины"],
    "clasps": {
        "Пластмассовый фастекс": 50,
        "Шакл (металлический)": 100,
        "Винтовая застежка": 70
    }
}

# --- ФУНКЦИИ РАБОТЫ С SUPABASE ---

def load_products():
    try:
        url = f"{SUPABASE_URL}/rest/v1/products?select=*"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            rows = response.json()
            products_dict = {}
            for row in rows:
                p_id = row.get("id")
                c_photos = row.get("color_photos")
                if isinstance(c_photos, str):
                    try:
                        c_photos = json.loads(c_photos)
                    except Exception:
                        c_photos = {}
                
                products_dict[p_id] = {
                    "category": row.get("category"),
                    "name": row.get("name"),
                    "photo": row.get("photo"),
                    "price": row.get("price"),
                    "material": row.get("material"),
                    "time": row.get("time"),
                    "color_photos": c_photos or {}
                }
            return products_dict
        else:
            print(f"Ошибка загрузки из Supabase: {response.text}")
    except Exception as e:
        print(f"Исключение при запросе в Supabase (load): {e}")
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

def save_product_to_db(item_id, item_data):
    try:
        url = f"{SUPABASE_URL}/rest/v1/products"
        payload = {
            "id": item_id,
            "category": item_data.get("category"),
            "name": item_data.get("name"),
            "photo": item_data.get("photo"),
            "price": item_data.get("price"),
            "material": item_data.get("material"),
            "time": item_data.get("time"),
            "color_photos": item_data.get("color_photos", {})
        }
        headers_upsert = HEADERS.copy()
        headers_upsert["Prefer"] = "resolution=merge-duplicates"
        response = requests.post(url, headers=headers_upsert, json=payload)
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Исключение Python при сохранении: {e}")
        return False

def delete_product_from_db(item_id):
    try:
        url = f"{SUPABASE_URL}/rest/v1/products?id=eq.{item_id}"
        requests.delete(url, headers=HEADERS)
    except Exception as e:
        print(f"Исключение при запросе в Supabase (delete): {e}")

# --- WEB & TELEGRAM ROUTES ---

@app.route('/')
def home():
    return "Hram Pauka Bot (Supabase edition) is running!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        print(f"Ошибка обработки апдейта: {e}")
    return '', 200

def clear_user_states(chat_id):
    for state_dict in (admin_states, custom_states, size_states):
        if chat_id in state_dict:
            del state_dict[chat_id]

def get_reply_markup():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, persistent=True)
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
    
    text = (
        "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\n"
        "Главное меню:"
    )
    reply_kb = get_reply_markup()
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, reply_markup_keyboard=reply_kb)

# --- КАТАЛОГ И КАТЕГОРИИ ---

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
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
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
        nav_buttons = [
            telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat_{cat_key}_0"),
            telebot.types.InlineKeyboardButton("Вперед ➡️", callback_data=f"cat_{cat_key}_0")
        ]
        markup.row(*nav_buttons)
        if is_admin:
            markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"admin_add_{cat_key}"))
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
    
    send_item_card(call.message.chat.id, item_id, item, index, cat_items, edit_message_id=call.message.message_id)

def send_item_card(chat_id, item_id, item, index, cat_items, edit_message_id=None):
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
    
    cat_key = str(item.get("category", "bracelets"))
    if cat_key in ["bracelets", "lanyards"]:
        markup.add(telebot.types.InlineKeyboardButton("🎨 Собрать свой вариант", callback_data=f"custom_start_{item_id}"))
    
    nav_buttons = [
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data=f"cat_{cat_key}_{index - 1}"),
        telebot.types.InlineKeyboardButton("Вперед ➡️", callback_data=f"cat_{cat_key}_{index + 1}")
    ]
    markup.row(*nav_buttons)
    
    is_admin = (int(chat_id) == int(ADMIN_ID))
    if is_admin:
        markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"admin_add_{cat_key}"))
        markup.add(
            telebot.types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"admin_edit_{item_id}"),
            telebot.types.InlineKeyboardButton("🗑 Удалить", callback_data=f"admin_del_{cat_key}_{index}_{item_id}")
        )

    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 К категориям", callback_data="catalog"))

    if edit_message_id:
        try:
            if current_photo:
                media = telebot.types.InputMediaPhoto(current_photo, caption=text)
                bot.edit_message_media(media, chat_id, edit_message_id, reply_markup=markup)
            else:
                try:
                    bot.edit_message_text(text, chat_id, edit_message_id, reply_markup=markup)
                except Exception:
                    bot.delete_message(chat_id, edit_message_id)
                    bot.send_message(chat_id, text, reply_markup=markup)
            return
        except Exception:
            pass

    if current_photo:
        bot.send_photo(chat_id, current_photo, caption=text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

# --- ИНТЕРАКТИВНЫЙ КОНСТРУКТОР ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("custom_start_"))
def custom_start(call):
    bot.answer_callback_query(call.id)
    item_id = call.data.replace("custom_start_", "")
    products = load_products()
    item = products.get(item_id)
    if not item:
        bot.send_message(call.message.chat.id, "❌ Товар не найден.")
        return
        
    chat_id = call.message.chat.id
    cat_key = str(item.get("category", "bracelets")).strip().lower()
    
    custom_states[chat_id] = {
        "item_id": item_id,
        "category": cat_key,
        "base_name": item.get("name"),
        "color": None,
        "thickness": None,
        "thickness_price": 0,
        "weave": None,
        "weave_price": 0,
        "bead": None,
        "clasp": None,
        "clasp_price": 0,
        "spacers": False,
        "measure_size": None,
        "step": "options",
        "msg_id": call.message.message_id
    }
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception:
        pass
    show_custom_paracord_menu(chat_id)

def show_custom_paracord_menu(chat_id, message_id=None):
    state = custom_states.get(chat_id, {})
    state["step"] = "options"
    text = (
        "🎨 Конструктор изделия (Шаг 1: Паракорд и Плетение)\n\n"
        f"📌 Основа: {state.get('base_name')}\n"
        f"🎨 Цвет шнура: {state.get('color') or '❌ Не выбран'}\n"
        f"📏 Толщина шнура: {state.get('thickness') or '❌ Не выбрана'}\n"
        f"🪢 Тип плетения: {state.get('weave') or '❌ Не выбрано'}\n"
        f"💀 Бусина: {state.get('bead') or 'Не выбрана'}\n"
        f"🪝 Застежка: {state.get('clasp') or 'Не выбрана'}\n"
        f"🔸 Разделители: {'Да' if state.get('spacers') else 'Нет'}\n\n"
        "👇 Выберите параметры шнура:"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🎨 Выбрать цвет паракорда", callback_data="custom_choose_color"))
    markup.add(telebot.types.InlineKeyboardButton("📏 Выбрать толщину паракорда", callback_data="custom_choose_thick"))
    markup.add(telebot.types.InlineKeyboardButton("🪢 Выбрать тип плетения", callback_data="custom_choose_weave"))
    
    if state.get("color") and state.get("thickness") and state.get("weave"):
        markup.add(telebot.types.InlineKeyboardButton("➡️ Далее: Выбор бусины", callback_data="custom_step_bead"))
        
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена кастома", callback_data="catalog"))
    
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            state["msg_id"] = message_id
            return
        except Exception:
            pass
    sent = bot.send_message(chat_id, text, reply_markup=markup)
    state["msg_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data == "custom_choose_color")
def custom_choose_color(call):
    bot.answer_callback_query(call.id)
    markup = telebot.types.InlineKeyboardMarkup()
    for color in CUSTOM_OPTIONS["colors"]:
        markup.add(telebot.types.InlineKeyboardButton(color, callback_data=f"set_color_{color}"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="custom_back_paracord"))
    bot.edit_message_text("🎨 Выберите цвет паракорда:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_color_"))
def set_color(call):
    bot.answer_callback_query(call.id)
    color = call.data.replace("set_color_", "")
    chat_id = call.message.chat.id
    if chat_id in custom_states:
        custom_states[chat_id]["color"] = color
    show_custom_paracord_menu(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_choose_thick")
def custom_choose_thick(call):
    bot.answer_callback_query(call.id)
    markup = telebot.types.InlineKeyboardMarkup()
    for thick_name, thick_price in CUSTOM_OPTIONS["thickness"].items():
        btn_text = f"{thick_name} — {thick_price} ₽"
        markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"set_thick_{thick_name}"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="custom_back_paracord"))
    bot.edit_message_text("📏 Выберите толщину паракорда:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_thick_"))
def set_thick(call):
    bot.answer_callback_query(call.id)
    thick_name = call.data.replace("set_thick_", "")
    chat_id = call.message.chat.id
    if chat_id in custom_states:
        custom_states[chat_id]["thickness"] = thick_name
        custom_states[chat_id]["thickness_price"] = CUSTOM_OPTIONS["thickness"].get(thick_name, 0)
    show_custom_paracord_menu(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_choose_weave")
def custom_choose_weave(call):
    bot.answer_callback_query(call.id)
    markup = telebot.types.InlineKeyboardMarkup()
    for weave_name, weave_price in CUSTOM_OPTIONS["weaves"].items():
        price_suffix = f" (+{weave_price} ₽)" if weave_price > 0 else ""
        markup.add(telebot.types.InlineKeyboardButton(f"{weave_name}{price_suffix}", callback_data=f"set_weave_{weave_name}"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="custom_back_paracord"))
    bot.edit_message_text("🪢 Выберите тип плетения:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_weave_"))
def set_weave(call):
    bot.answer_callback_query(call.id)
    weave_name = call.data.replace("set_weave_", "")
    chat_id = call.message.chat.id
    if chat_id in custom_states:
        custom_states[chat_id]["weave"] = weave_name
        custom_states[chat_id]["weave_price"] = CUSTOM_OPTIONS["weaves"].get(weave_name, 0)
    show_custom_paracord_menu(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_back_paracord")
def custom_back_paracord(call):
    bot.answer_callback_query(call.id)
    show_custom_paracord_menu(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_step_bead")
def custom_step_bead(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    state = custom_states.get(chat_id, {})
    state["step"] = "bead"
    
    text = (
        "🎨 Конструктор изделия (Шаг 2: Бусина)\n\n"
        f"🧵 Паракорд: {state.get('color')} / {state.get('thickness')}\n"
        f"🪢 Плетение: {state.get('weave')}\n"
        f"💀 Центральная бусина: {state.get('bead') or '❌ Не выбрана'}\n\n"
        "👇 Выберите центральную бусину:"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    for bead in CUSTOM_OPTIONS["beads"]:
        markup.add(telebot.types.InlineKeyboardButton(bead, callback_data=f"set_bead_{bead}"))
    
    markup.add(
        telebot.types.InlineKeyboardButton("⬅️ Назад к паракорду", callback_data="custom_back_to_paracord"),
        telebot.types.InlineKeyboardButton("➡️ Далее: Застежка", callback_data="custom_step_clasp")
    )
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_bead_"))
def set_bead(call):
    bot.answer_callback_query(call.id)
    bead = call.data.replace("set_bead_", "")
    chat_id = call.message.chat.id
    if chat_id in custom_states:
        custom_states[chat_id]["bead"] = bead
    custom_step_bead(call)

@bot.callback_query_handler(func=lambda call: call.data == "custom_back_to_paracord")
def custom_back_to_paracord(call):
    bot.answer_callback_query(call.id)
    show_custom_paracord_menu(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_step_clasp")
def custom_step_clasp(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    state = custom_states.get(chat_id, {})
    state["step"] = "clasp"
    cat_key = state.get("category", "bracelets")
    name_lower = state.get("base_name", "").lower()
    is_lanyard = (cat_key == "lanyards" or "темляк" in name_lower or "брелок" in name_lower)
    
    next_btn_label = "➡️ Далее: Длина шнура" if is_lanyard else "➡️ Далее: Обхват запястья"
    
    text = (
        "🎨 Конструктор изделия (Шаг 3: Застежка)\n\n"
        f"🧵 Паракорд: {state.get('color')} / {state.get('thickness')}\n"
        f"🪢 Плетение: {state.get('weave')}\n"
        f"💀 Бусина: {state.get('bead')}\n"
        f"🪝 Застежка: {state.get('clasp') or '❌ Не выбрана'}\n\n"
        "👇 Выберите застежку:"
    )
    markup = telebot.types.InlineKeyboardMarkup()
    for clasp_name, clasp_price in CUSTOM_OPTIONS["clasps"].items():
        btn_text = f"{clasp_name} (+{clasp_price} ₽)"
        markup.add(telebot.types.InlineKeyboardButton(btn_text, callback_data=f"set_clasp_{clasp_name}"))
        
    markup.add(
        telebot.types.InlineKeyboardButton("⬅️ Назад к бусине", callback_data="custom_step_bead"),
        telebot.types.InlineKeyboardButton(next_btn_label, callback_data="custom_step_measure")
    )
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_clasp_"))
def set_clasp(call):
    bot.answer_callback_query(call.id)
    clasp_name = call.data.replace("set_clasp_", "")
    chat_id = call.message.chat.id
    if chat_id in custom_states:
        custom_states[chat_id]["clasp"] = clasp_name
        custom_states[chat_id]["clasp_price"] = CUSTOM_OPTIONS["clasps"].get(clasp_name, 0)
    custom_step_clasp(call)

@bot.callback_query_handler(func=lambda call: call.data == "custom_step_measure")
def custom_step_measure(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    state = custom_states.get(chat_id, {})
    state["step"] = "measure"
    state["msg_id"] = call.message.message_id
    
    cat_key = state.get("category", "bracelets")
    name_lower = state.get("base_name", "").lower()
    is_lanyard = (cat_key == "lanyards" or "темляк" in name_lower or "брелок" in name_lower)
    val = state.get('measure_size') or '❌ Не указано'
    
    if is_lanyard:
        text = (
            "🎨 Конструктор изделия (Шаг 4: Длина шнура)\n\n"
            f"📏 Текущая длина части со шнуром: {val} см\n\n"
            "👇 Напиши в чат числом длину той части темляка/брелока, которая будет со шнуром (в см, например: 10 или 12):"
        )
    else:
        text = (
            "🎨 Конструктор изделия (Шаг 4: Обхват запястья)\n\n"
            f"📏 Текущий обхват запястья: {val} см\n\n"
            "👇 Напиши в чат числом обхват своего запястья в сантиметрах (например: 18 или 17.5):"
        )
        
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад к застежке", callback_data="custom_step_clasp"))
    if state.get("measure_size"):
        markup.add(telebot.types.InlineKeyboardButton("➡️ Далее: Итог", callback_data="custom_step_summary"))
        
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)

def render_custom_summary(chat_id, message_id=None):
    state = custom_states.get(chat_id, {})
    state["step"] = "summary"
    cat_key = state.get("category", "bracelets")
    name_lower = state.get("base_name", "").lower()
    is_lanyard = (cat_key == "lanyards" or "темляк" in name_lower or "брелок" in name_lower)
    
    spacers_text = "Да — красивые бусины по бокам (+100 ₽)" if state.get("spacers") else "Нет (чистый вид)"
    extra_spacers_price = 100 if state.get("spacers") else 0
    thick_price = state.get("thickness_price", 0)
    weave_price = state.get("weave_price", 0)
    clasp_price = state.get("clasp_price", 0)
    
    total_price = thick_price + weave_price + clasp_price + extra_spacers_price
    state["final_price"] = total_price
    
    measure_label = "Длина части со шнуром" if is_lanyard else "Обхват запястья"
    measure_display = f"{state.get('measure_size')} см" if state.get('measure_size') else "⚠️ Не указано"
    change_measure_btn = "🔄 Изменить длину шнура" if is_lanyard else "🔄 Изменить запястье"
    
    text = (
        "🔥 ВАШ СОБРАННЫЙ КАСТОМНЫЙ КОМПЛЕКТ 🔥\n"
        "Внимательно проверьте каждую деталь — именно так будет выглядеть ваше готовое изделие:\n\n"
        f"🏷 Основа каталога: {state.get('base_name')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎨 Цвет паракорда: {state.get('color') or 'Не указан'}\n"
        f"📏 Толщина шнура: {state.get('thickness') or 'Не указана'} — {thick_price} ₽\n"
        f"🪢 Тип плетения: {state.get('weave') or 'Не указано'}" + (f" — +{weave_price} ₽" if weave_price > 0 else " — входит в базу") + "\n"
        f"💀 Центральная бусина: {state.get('bead') or 'Без бусины'}\n"
        f"🪝 Тип застежки: {state.get('clasp') or 'Не указана'} — +{clasp_price} ₽\n"
        f"🔸 Бусины-разделители: {spacers_text}\n"
        f"📐 {measure_label}: {measure_display}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ИТОГОВАЯ СТОИМОСТЬ: {total_price} ₽\n\n"
        "💡 Всё верно? Нажимайте «Добавить в корзину» или измените любую деталь кнопками ниже:"
    )
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🔄 Изменить паракорд / плетение", callback_data=f"custom_start_{state.get('item_id')}"))
    markup.add(telebot.types.InlineKeyboardButton("🔄 Изменить бусину", callback_data="custom_step_bead"))
    markup.add(telebot.types.InlineKeyboardButton("🔄 Изменить застежку", callback_data="custom_step_clasp"))
    markup.add(telebot.types.InlineKeyboardButton(change_measure_btn, callback_data="custom_step_measure"))
    
    spacer_btn_text = "❌ Убрать бусины-разделители" if state.get("spacers") else "➕ Добавить бусины-разделители (+100 ₽)"
    markup.add(telebot.types.InlineKeyboardButton(spacer_btn_text, callback_data="custom_toggle_spacers"))
    
    if state.get("measure_size"):
        markup.add(telebot.types.InlineKeyboardButton("🛒 Добавить кастом в корзину", callback_data="custom_add_to_cart"))
    else:
        markup.add(telebot.types.InlineKeyboardButton("⚠️ Укажи размер выше", callback_data="custom_step_measure"))
        
    markup.add(telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="view_cart"))
    markup.add(telebot.types.InlineKeyboardButton("🔙 В каталог", callback_data="catalog"))
    
    target_id = message_id or state.get("msg_id")
    if target_id:
        try:
            bot.edit_message_text(text, chat_id, target_id, reply_markup=markup)
            state["msg_id"] = target_id
            return
        except Exception:
            pass
    sent = bot.send_message(chat_id, text, reply_markup=markup)
    state["msg_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data in ["custom_step_summary", "custom_toggle_spacers"])
def custom_step_summary(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    state = custom_states.get(chat_id, {})
    if call.data == "custom_toggle_spacers":
        state["spacers"] = not state.get("spacers", False)
    render_custom_summary(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "custom_add_to_cart")
def custom_add_to_cart(call):
    chat_id = call.message.chat.id
    state = custom_states.get(chat_id)
    if not state:
        bot.answer_callback_query(call.id, "❌ Данные кастома устарели.")
        return
        
    cat_key = state.get("category", "bracelets")
    name_lower = state.get("base_name", "").lower()
    is_lanyard = (cat_key == "lanyards" or "темляк" in name_lower or "брелок" in name_lower)
    
    measure_label = "Длина шнура" if is_lanyard else "Запястье"
    measure_val = f"{state.get('measure_size')} см" if state.get('measure_size') else "Не указано"
    
    custom_item = {
        "name": f"[Кастом] {state.get('base_name')} ({state.get('color')}, {state.get('weave')}, {state.get('bead')}, {state.get('clasp')})",
        "price": state.get("final_price", 0),
        "material": f"Цвет: {state.get('color')}, Толщина: {state.get('thickness')}, Плетение: {state.get('weave')}, Бусина: {state.get('bead')}, Застежка: {state.get('clasp')}, Разделители: {'Да' if state.get('spacers') else 'Нет'}, {measure_label}: {measure_val}",
        "time": "2-3 дня"
    }
    
    if chat_id not in user_carts:
        user_carts[chat_id] = []
    user_carts[chat_id].append(custom_item)
    
    bot.answer_callback_query(call.id, "✅ Кастомный товар добавлен в корзину!")
    del custom_states[chat_id]
    
    call.data = "view_cart"
    view_cart(call)

# --- КОРЗИНА И ЗАКАЗЫ ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("cart_add_"))
def add_to_cart(call):
    item_id = call.data.replace("cart_add_", "")
    products = load_products()
    item = products.get(item_id)
    
    if not item:
        bot.answer_callback_query(call.id, "❌ Товар не найден.")
        return
        
    chat_id = call.message.chat.id
    cat_key = str(item.get("category", "")).strip().lower()
    item_name_lower = str(item.get("name", "")).strip().lower()
    
    is_bracelet = (cat_key == "bracelets" or "браслет" in item_name_lower)
    is_lanyard = (cat_key == "lanyards" or "темляк" in item_name_lower or "брелок" in item_name_lower)
    
    if is_bracelet or is_lanyard:
        bot.answer_callback_query(call.id)
        
        measure_type = "lanyard" if is_lanyard else "wrist"
        
        if is_lanyard:
            prompt_text = (
                f"📌 {item.get('name')}\n\n"
                "📏 Укажи длину той части темляка/брелока, которая будет со шнуром (в см, например: 10 или 12):"
            )
        else:
            prompt_text = (
                f"📌 {item.get('name')}\n\n"
                "📏 Укажи обхват своего запястья в сантиметрах, чтобы браслет сидел четко (например: 18 или 17.5):"
            )
            
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
        
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
            
        sent = bot.send_message(chat_id, prompt_text, reply_markup=markup)
        size_states[chat_id] = {
            "item": item,
            "measure_type": measure_type,
            "msg_id": sent.message_id
        }
        return

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
            name = item.get('name', 'Товар')
            price = item.get('price', 0)
            text += f"{idx + 1}. {name} — {price} ₽\n"
            if item.get('material'):
                text += f"   └ {item.get('material')}\n"
            total += price
        text += f"\n💰 Итого: {total} ₽"
        
        markup.add(telebot.types.InlineKeyboardButton("🚀 Оформить заказ", callback_data="checkout"))
        markup.add(telebot.types.InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"))
        markup.add(telebot.types.InlineKeyboardButton("🛍 Продолжить покупки", callback_data="catalog"))
        
    markup.add(telebot.types.InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"))
    try:
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)
    except Exception:
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
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
    active_orders[order_id] = chat_id
    
    total = sum(item.get('price', 0) for item in cart)
    
    user = message.from_user
    if user.username:
        client_display = f"@{user.username}"
    else:
        client_display = f"<a href='tg://user?id={chat_id}'>{user.first_name or 'Клиент'}</a>"
    
    save_order_to_db(order_id, chat_id, cart, total)
    
    order_text = f"🚨 НОВЫЙ ЗАКАЗ №{order_id}!\n👤 Заказчик: {client_display}\n\n"
    for item in cart:
        name = item.get('name', 'Товар')
        price = item.get('price', 0)
        order_text += f"• {name} — {price} ₽\n"
        if item.get('material'):
            order_text += f"   └ {item.get('material')}\n"
    order_text += f"\n💰 Сумма: {total} ₽"
    
    admin_markup = telebot.types.InlineKeyboardMarkup()
    admin_markup.add(telebot.types.InlineKeyboardButton(
        f"✅ Заказ №{order_id} готов", 
        callback_data=f"order_ready_{order_id}"
    ))
    
    bot.send_message(chat_id, f"✅ Заказ №{order_id} успешно оформлен! Спасибо, что выбрали «Храм Паука»! Мастер уже принял его в работу.")
    
    try:
        bot.send_message(ADMIN_ID, order_text, parse_mode="HTML", reply_markup=admin_markup)
    except Exception as e:
        print(f"Не удалось отправить заказ админу: {e}")
    
    user_carts[chat_id] = []
    show_main_menu(chat_id, message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_menu(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    clear_user_states(chat_id)
    show_main_menu(chat_id, call.message.message_id)

# --- АДМИНКА ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("order_ready_"))
def mark_order_ready(call):
    if int(call.message.chat.id) != int(ADMIN_ID):
        bot.answer_callback_query(call.id, "❌ Доступно только администратору.")
        return
        
    order_id = int(call.data.replace("order_ready_", ""))
    client_chat_id = active_orders.get(order_id)
    
    if not client_chat_id:
        try:
            text_lines = call.message.text.split("\n")
            for line in text_lines:
                if "ID клиента:" in line:
                    client_chat_id = int(line.replace("ID клиента:", "").strip())
        except Exception:
            pass

    if client_chat_id:
        try:
            bot.send_message(
                client_chat_id, 
                f"🔥 Твой заказ №{order_id} готов!\n\nИзделие успешно создано мастерской «Храм Паука». Свяжись с администратором для уточнения деталей доставки или самовывоза."
            )
            bot.answer_callback_query(call.id, f"✅ Уведомление по заказу №{order_id} отправлено клиенту!")
        except Exception as e:
            print(f"Не удалось отправить сообщение клиенту {client_chat_id}: {e}")
            bot.answer_callback_query(call.id, "⚠️ Заказ отмечен, но не удалось доставить сообщение клиенту.")
    else:
        bot.answer_callback_query(call.id, f"✅ Заказ №{order_id} отмечен как готовый (ID клиента не найден).")
    
    try:
        new_text = call.message.text + "\n\n🟢 СТАТУС: ГОТОВ ✅"
        bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id)
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_add_"))
def admin_add_start(call):
    bot.answer_callback_query(call.id)
    if int(call.message.chat.id) != int(ADMIN_ID):
        return
    cat_key = call.data.replace("admin_add_", "")
    
    admin_states[call.message.chat.id] = {
        "action": "add", 
        "category": cat_key, 
        "step": "name",
        "msg_id": call.message.message_id
    }
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
    
    text = f"✍️ [Добавление в «{CATEGORIES.get(cat_key)}»] Шаг 1/6: Напиши название товара:"
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    sent = bot.send_message(call.message.chat.id, text, reply_markup=markup)
    admin_states[call.message.chat.id]["msg_id"] = sent.message_id

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_del_"))
def admin_delete_item(call):
    bot.answer_callback_query(call.id)
    if int(call.message.chat.id) != int(ADMIN_ID):
        return
    
    parts = call.data.replace("admin_del_", "").split("_")
    cat_key = parts[0]
    index = int(parts[1])
    item_id = "_".join(parts[2:])
    
    delete_product_from_db(item_id)
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
        
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
    sent = bot.send_message(call.message.chat.id, f"✏️ [Редактирование: {item.get('name')}]\nШаг 1/3: Напиши новое название:", reply_markup=markup)
    admin_states[call.message.chat.id] = {"action": "edit", "item_id": item_id, "step": "name", "msg_id": sent.message_id}

@bot.callback_query_handler(func=lambda call: call.data == "skip_photo")
def skip_photo(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    if chat_id in admin_states and admin_states[chat_id].get("step") == "photo":
        admin_states[chat_id]["photo"] = None
        admin_states[chat_id]["step"] = "material"
        text = "🧵 Шаг 3/6: Укажи материал (например: Паракорд 550):"
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
        try:
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup)
        except Exception:
            sent = bot.send_message(chat_id, text, reply_markup=markup)
            admin_states[chat_id]["msg_id"] = sent.message_id

# ИСПРАВЛЕННЫЙ ТЕКСТОВЫЙ ХЕНДЛЕР (реагирует только на активные шаги ввода, не блокируя /start)
@bot.message_handler(content_types=['text', 'photo', 'document'], func=lambda message: message.chat.id in admin_states or message.chat.id in custom_states or message.chat.id in size_states)
def handle_text_and_flows(message):
    chat_id = message.chat.id
    text_content = message.text.strip() if message.text else ""

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    # 1. ВВОД ЗАМЕРА ДЛЯ ГОТОВОГО ТОВАРА ИЗ КАТАЛОГА
    if chat_id in size_states:
        if not text_content:
            return
        state = size_states[chat_id]
        val = text_content
        item = state["item"].copy()
        measure_type = state["measure_type"]
        target_msg_id = state.get("msg_id")
        
        label = "Длина части со шнуром" if measure_type == "lanyard" else "Обхват запястья"
        old_mat = item.get("material", "")
        item["material"] = f"{old_mat} | {label}: {val} см" if old_mat else f"{label}: {val} см"
        
        if chat_id not in user_carts:
            user_carts[chat_id] = []
        user_carts[chat_id].append(item)
        
        del size_states[chat_id]
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🛒 Перейти в корзину", callback_data="view_cart"))
        markup.add(telebot.types.InlineKeyboardButton("🛍 Продолжить покупки", callback_data="catalog"))
        
        done_text = f"✅ Товар «{item.get('name')}» ({label}: {val} см) добавлен в корзину!"
        try:
            if target_msg_id:
                bot.edit_message_text(done_text, chat_id, target_msg_id, reply_markup=markup)
                return
        except Exception:
            pass
        bot.send_message(chat_id, done_text, reply_markup=markup)
        return

    # 2. КАСТОМ
    if chat_id in custom_states:
        state = custom_states[chat_id]
        if state.get("step") == "measure":
            if not text_content:
                return
            state["measure_size"] = text_content
            render_custom_summary(chat_id)
            return

    # 3. АДМИНКА
    if chat_id in admin_states and int(chat_id) == int(ADMIN_ID):
        state = admin_states[chat_id]
        action = state.get("action")
        step = state.get("step")
        target_msg_id = state.get("msg_id")

        def update_admin_prompt(new_text, reply_markup=None):
            nonlocal state
            if not reply_markup:
                reply_markup = telebot.types.InlineKeyboardMarkup()
                reply_markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
            try:
                if target_msg_id:
                    bot.edit_message_text(new_text, chat_id, target_msg_id, reply_markup=reply_markup)
                else:
                    raise Exception()
            except Exception:
                sent = bot.send_message(chat_id, new_text, reply_markup=reply_markup)
                state["msg_id"] = sent.message_id

        if action == "add":
            if step == "name":
                if not text_content:
                    return
                state["name"] = text_content
                state["step"] = "photo"
                
                markup = telebot.types.InlineKeyboardMarkup()
                markup.add(telebot.types.InlineKeyboardButton("🖼 Пропустить фото", callback_data="skip_photo"))
                markup.add(telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="catalog"))
                
                update_admin_prompt("🖼 Шаг 2/6: Отправь фотографию товара (или нажми кнопку):", reply_markup=markup)
                return
                
            elif step == "photo":
                photo_id = None
                if message.photo:
                    photo_id = message.photo[-1].file_id
                elif message.document:
                    photo_id = message.document.file_id
                    
                if photo_id:
                    state["photo"] = photo_id
                    state["step"] = "material"
                    update_admin_prompt("🧵 Шаг 3/6: Укажи материал (например: Паракорд 550):")
                else:
                    update_admin_prompt("🖼 Ошибка! Отправь картинку (фото) или нажми «Пропустить фото»:")
                return
                
            elif step == "material":
                if not text_content:
                    return
                state["material"] = text_content
                state["step"] = "color"
                update_admin_prompt("🎨 Шаг 4/6: Укажи цвет (например: Олива, Черный):")
                return

            elif step == "color":
                if not text_content:
                    return
                color_val = text_content
                base_mat = state.get("material", "")
                state["material"] = f"{base_mat}, Цвет: {color_val}"
                state["step"] = "price"
                update_admin_prompt("💵 Шаг 5/6: Напиши цену товара цифрами (например: 600):")
                return
                
            elif step == "price":
                if not text_content:
                    return
                try:
                    state["price"] = int(text_content)
                    state["step"] = "time"
                    update_admin_prompt("⏱ Шаг 6/6: Укажи срок изготовления (например: 1-2 дня):")
                except ValueError:
                    update_admin_prompt("❌ Ошибка! Цена должна быть целым числом (например: 600). Повтори ввод цены:")
                return
                    
            elif step == "time":
                text_val = text_content if text_content else "1-2 дня"
                state["time"] = text_val
                
                item_id = f"item_{int(os.urandom(3).hex(), 16)}"
                item_data = {
                    "category": state["category"],
                    "name": state["name"],
                    "photo": state.get("photo"),
                    "price": state["price"],
                    "material": state["material"],
                    "time": state["time"],
                    "color_photos": {}
                }
                
                success = save_product_to_db(item_id, item_data)
                cat_key = state["category"]
                
                if chat_id in admin_states:
                    del admin_states[chat_id]
                
                try:
                    if target_msg_id:
                        bot.delete_message(chat_id, target_msg_id)
                except Exception:
                    pass
                
                if success:
                    bot.send_message(chat_id, f"🎉 Товар успешно добавлен в категорию «{CATEGORIES.get(cat_key)}»!")
                else:
                    bot.send_message(chat_id, "⚠️ Ошибка сохранения в облако.")
                    
                show_main_menu(chat_id)
                return

        elif action == "edit":
            item_id = state["item_id"]
            products = load_products()
            item = products.get(item_id, {})
            
            if step == "name":
                if not text_content:
                    return
                state["new_name"] = text_content
                state["step"] = "price"
                update_admin_prompt(f"💵 Шаг 2/3: Напиши новую цену (текущая: {item.get('price')}):")
                return
                
            elif step == "price":
                if not text_content:
                    return
                try:
                    state["new_price"] = int(text_content)
                    state["step"] = "material"
                    update_admin_prompt(f"🧵 Шаг 3/3: Укажи новый материал/цвет (текущий: {item.get('material')}):")
                except ValueError:
                    update_admin_prompt("❌ Цена должна быть числом. Повтори ввод:")
                return
                    
            elif step == "material":
                if not text_content:
                    return
                
                item["name"] = state["new_name"]
                item["price"] = state["new_price"]
                item["material"] = text_content
                
                save_product_to_db(item_id, item)
                
                if chat_id in admin_states:
                    del admin_states[chat_id]
                
                try:
                    if target_msg_id:
                        bot.delete_message(chat_id, target_msg_id)
                except Exception:
                    pass
                
                bot.send_message(chat_id, "✅ Товар успешно обновлен в облаке!")
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
