import json
import os
import uuid
from flask import Flask, request
import requests
import telebot

TOKEN = os.environ.get("BOT_TOKEN", "9263601739:AAFhakRpWA0uOrev0vQ7TRRk2iFLOMdn5Y8")
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = int(os.environ.get("ADMIN_ID", "5393257255"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@TheSpiderTemple")

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://cztrrtvajptalfjdfpmy.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY", "sb_publishable_2HnmPT650giFwrbjE8G4IQ_2GYLbPQ-"
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

user_carts = {}
checkout_states = {}
admin_states = {}

CATEGORIES = {
    "bracelets": "Браслеты",
    "lanyards": "Брелоки / Темляки",
    "beads": "Бусины, фигурки",
    "runes_set": "Руны: Полный набор",
    "runes_single": "Руны: Отдельные руны",
}


def escape_html(text):
  if text is None:
    return ""
  return (
      str(text)
      .replace("&", "&amp;")
      .replace("<", "&lt;")
      .replace(">", "&gt;")
  )


def load_products():
  try:
    url = f"{SUPABASE_URL}/rest/v1/products?select=*"
    response = requests.get(url, headers=HEADERS, timeout=10)
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
            "meaning": row.get("meaning"),
            "time": row.get("time"),
        }
      return products_dict
  except Exception as e:
    print(f"Ошибка загрузки из Supabase: {e}")
  return {}


def save_user_to_db(chat_id):
  try:
    url = f"{SUPABASE_URL}/rest/v1/users"
    check_res = requests.get(
        f"{url}?chat_id=eq.{chat_id}", headers=HEADERS, timeout=10
    )
    if check_res.status_code == 200 and not check_res.json():
      requests.post(url, headers=HEADERS, json={"chat_id": chat_id}, timeout=10)
  except Exception as e:
    print(f"Ошибка сохранения пользователя: {e}")


def get_all_users():
  try:
    url = f"{SUPABASE_URL}/rest/v1/users?select=chat_id"
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code == 200:
      return [
          row.get("chat_id") for row in response.json() if row.get("chat_id")
      ]
  except Exception as e:
    print(f"Ошибка получения пользователей: {e}")
  return []


def get_next_order_number():
  try:
    url = f"{SUPABASE_URL}/rest/v1/orders?select=order_id"
    response = requests.get(url, headers=HEADERS, timeout=10)
    if response.status_code == 200:
      rows = response.json()
      if rows and isinstance(rows, list) and len(rows) > 0:
        max_id = 0
        for row in rows:
          val = row.get("order_id")
          if val is not None:
            try:
              num = int(val)
              if num > max_id:
                max_id = num
            except ValueError:
              pass
        return max_id + 1
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
        "status": "new",
    }
    requests.post(url, headers=HEADERS, json=payload, timeout=10)
  except Exception as e:
    print(f"Ошибка сохранения заказа в БД: {e}")


def update_order_status_in_db(order_id, new_status):
  try:
    url = f"{SUPABASE_URL}/rest/v1/orders?order_id=eq.{order_id}"
    payload = {"status": new_status}
    requests.patch(url, headers=HEADERS, json=payload, timeout=10)
  except Exception as e:
    print(f"Ошибка обновления статуса заказа в БД: {e}")


def clear_user_states(chat_id):
  if chat_id in checkout_states:
    del checkout_states[chat_id]
  if chat_id in admin_states:
    del admin_states[chat_id]


def get_reply_markup(user_id):
  markup = telebot.types.ReplyKeyboardMarkup(
      resize_keyboard=True, is_persistent=True
  )
  markup.add(telebot.types.KeyboardButton("🕷 Запустить Храм Паука"))
  if user_id == ADMIN_ID:
    markup.add(telebot.types.KeyboardButton("➕ Добавить товар"))
  return markup


def format_customer_html(user_info, chat_id):
  username = getattr(user_info, "username", None)
  bot_username = (bot.get_me().username or "").lower()
  if username and username.lower() != bot_username:
    return f"@{escape_html(username)}"
  first_name = getattr(user_info, "first_name", None) or "Клиент"
  return f'<a href="tg://user?id={chat_id}">{escape_html(first_name)}</a>'


def send_order_to_admin(order_id, chat_id, user_info, cart, total):
  customer_str = format_customer_html(user_info, chat_id)
  admin_text = (
      f"🔥 <b>Новый заказ №{order_id}!</b>\n"
      f"👤 Заказчик: {customer_str}\n\n"
      f"🛒 <b>Состав заказа:</b>\n"
  )
  for idx, item in enumerate(cart):
    item_name = escape_html(item.get("name", "Товар"))
    item_price = escape_html(item.get("price", 0))
    admin_text += f"{idx + 1}. {item_name} — {item_price} ₽\n"
  admin_text += f"\n💰 <b>Итого:</b> {total} ₽"

  admin_markup = telebot.types.InlineKeyboardMarkup()
  admin_markup.add(
      telebot.types.InlineKeyboardButton(
          "✅ Заказ готов", callback_data=f"ready_{order_id}_{chat_id}"
      )
  )

  try:
    bot.send_message(
        ADMIN_ID, admin_text, parse_mode="HTML", reply_markup=admin_markup
    )
  except Exception as e:
    print(f"Ошибка отправки уведомления админу: {e}")


@bot.callback_query_handler(func=lambda call: call.data == "noop")
def handle_noop(call):
  bot.answer_callback_query(call.id, "Заказ уже выполнен")


@bot.message_handler(commands=["start"])
def send_welcome(message):
  chat_id = message.chat.id
  user_carts[chat_id] = []
  clear_user_states(chat_id)
  save_user_to_db(chat_id)
  show_main_menu(chat_id, user_id=message.from_user.id)


@bot.message_handler(func=lambda msg: msg.text == "🕷 Запустить Храм Паука")
def handle_reply_start(message):
  chat_id = message.chat.id
  user_carts[chat_id] = []
  clear_user_states(chat_id)
  save_user_to_db(chat_id)
  show_main_menu(chat_id, user_id=message.from_user.id)


def show_main_menu(chat_id, message_id=None, user_id=None):
  effective_user_id = user_id if user_id is not None else chat_id
  markup = telebot.types.InlineKeyboardMarkup()
  markup.add(
      telebot.types.InlineKeyboardButton("🛍 Каталог", callback_data="catalog")
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🛒 Корзина", callback_data="view_cart"
      )
  )

  text = "Приветствую! Добро пожаловать в мастерскую Храм Паука.\n\nГлавное меню:"
  reply_kb = get_reply_markup(effective_user_id)
  if message_id:
    try:
      bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
      return
    except Exception:
      pass
  bot.send_message(chat_id, text, reply_markup=reply_kb)
  bot.send_message(chat_id, "Выбери действие:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_menu(call):
  bot.answer_callback_query(call.id)
  clear_user_states(call.message.chat.id)
  show_main_menu(
      call.message.chat.id, call.message.message_id, user_id=call.from_user.id
  )


# --- АДМИНКА: ДОБАВЛЕНИЕ ТОВАРА (ПОШАГОВО) ---
@bot.message_handler(
    func=lambda msg: msg.text == "➕ Добавить товар"
    and msg.from_user.id == ADMIN_ID
)
def start_add_product_msg(message):
  chat_id = message.chat.id
  admin_states[chat_id] = {"step": "category"}

  markup = telebot.types.InlineKeyboardMarkup()
  for cat_key, cat_name in CATEGORIES.items():
    markup.add(
        telebot.types.InlineKeyboardButton(
            cat_name, callback_data=f"admin_cat_{cat_key}"
        )
    )

  bot.send_message(
      chat_id,
      "🛠 **Добавление нового товара**\n\nВыбери категорию:",
      parse_mode="Markdown",
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("admin_cat_")
    and call.from_user.id == ADMIN_ID
)
def admin_choose_category(call):
  bot.answer_callback_query(call.id)
  chat_id = call.message.chat.id
  cat_key = call.data.replace("admin_cat_", "")

  if chat_id not in admin_states:
    admin_states[chat_id] = {}
  admin_states[chat_id]["category"] = cat_key
  admin_states[chat_id]["step"] = "name"

  bot.edit_message_text(
      "✍️ Введи **название** товара:",
      chat_id,
      call.message.message_id,
      parse_mode="Markdown",
  )


@bot.message_handler(
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "name"
    and msg.from_user.id == ADMIN_ID
)
def admin_step_name(message):
  chat_id = message.chat.id
  if message.text.startswith("/"):
    clear_user_states(chat_id)
    return
  admin_states[chat_id]["name"] = message.text.strip()
  admin_states[chat_id]["step"] = "photo"
  bot.send_message(
      chat_id, "📸 Пришли **фотографию** товара:", parse_mode="Markdown"
  )


@bot.message_handler(
    content_types=["photo", "text"],
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "photo"
    and msg.from_user.id == ADMIN_ID,
)
def admin_step_photo(message):
  chat_id = message.chat.id

  if message.photo:
    photo_id = message.photo[-1].file_id
    admin_states[chat_id]["photo"] = photo_id
  elif message.text:
    if message.text.startswith("/"):
      clear_user_states(chat_id)
      return
    if message.text.strip().lower() == "нет":
      admin_states[chat_id]["photo"] = None
    else:
      bot.send_message(
          chat_id, "❌ Пожалуйста, отправь фото картинкой (или напиши «нет»):"
      )
      return
  else:
    return

  admin_states[chat_id]["step"] = "material"
  bot.send_message(
      chat_id,
      "🧵 Введи **материал** (например: Эпоксидная смола):",
      parse_mode="Markdown",
  )


@bot.message_handler(
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "material"
    and msg.from_user.id == ADMIN_ID
)
def admin_step_material(message):
  chat_id = message.chat.id
  text = message.text.strip()
  if text.startswith("/"):
    clear_user_states(chat_id)
    return
  admin_states[chat_id]["material"] = text
  admin_states[chat_id]["step"] = "color"
  bot.send_message(
      chat_id,
      "🎨 Введи **цвет** (например: Каменный серый):",
      parse_mode="Markdown",
  )


@bot.message_handler(
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "color"
    and msg.from_user.id == ADMIN_ID
)
def admin_step_color(message):
  chat_id = message.chat.id
  text = message.text.strip()
  if text.startswith("/"):
    clear_user_states(chat_id)
    return
  admin_states[chat_id]["color"] = text

  if admin_states[chat_id].get("category") == "runes_single":
    admin_states[chat_id]["step"] = "meaning"
    bot.send_message(
        chat_id,
        "🔮 Введи **значение** руны (например: Защита, сила, прорыв):",
        parse_mode="Markdown",
    )
  else:
    admin_states[chat_id]["step"] = "price"
    bot.send_message(
        chat_id,
        "💵 Введи **цену** товара (только цифры, например: 2800):",
        parse_mode="Markdown",
    )


@bot.message_handler(
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "meaning"
    and msg.from_user.id == ADMIN_ID
)
def admin_step_meaning(message):
  chat_id = message.chat.id
  text = message.text.strip()
  if text.startswith("/"):
    clear_user_states(chat_id)
    return
  admin_states[chat_id]["meaning"] = text
  admin_states[chat_id]["step"] = "price"
  bot.send_message(
      chat_id,
      "💵 Введи **цену** товара (только цифры, например: 2800):",
      parse_mode="Markdown",
  )


@bot.message_handler(
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "price"
    and msg.from_user.id == ADMIN_ID
)
def admin_step_price(message):
  chat_id = message.chat.id
  text = message.text.strip()
  if text.startswith("/"):
    clear_user_states(chat_id)
    return
  try:
    admin_states[chat_id]["price"] = int(text)
    admin_states[chat_id]["step"] = "time"
    bot.send_message(
        chat_id,
        "⏱ Введи **срок изготовления** (например: 2-3 дня):",
        parse_mode="Markdown",
    )
  except ValueError:
    bot.send_message(chat_id, "❌ Цена должна быть числом. Введи цену повторно:")


@bot.message_handler(
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "time"
    and msg.from_user.id == ADMIN_ID
)
def admin_step_time(message):
  chat_id = message.chat.id
  text = message.text.strip()
  if text.startswith("/"):
    clear_user_states(chat_id)
    return

  state = admin_states[chat_id]
  state["time"] = text
  full_material_str = f"{state['material']}, Цвет: {state['color']}"
  generated_id = str(uuid.uuid4())

  try:
    url = f"{SUPABASE_URL}/rest/v1/products"
    payload = {
        "id": generated_id,
        "category": state["category"],
        "name": state["name"],
        "price": state["price"],
        "material": full_material_str,
        "meaning": state.get("meaning"),
        "time": state["time"],
        "photo": state["photo"],
    }
    res = requests.post(url, headers=HEADERS, json=payload, timeout=10)
    if res.status_code in [200, 201]:
      markup = telebot.types.InlineKeyboardMarkup()
      markup.add(
          telebot.types.InlineKeyboardButton(
              "🚀 Да, запустить дроп",
              callback_data=f"broadcast_yes_{generated_id}",
          ),
          telebot.types.InlineKeyboardButton(
              "🙅‍♂️ Нет", callback_data="broadcast_no"
          ),
      )
      bot.send_message(
          chat_id,
          (
              "✅ Товар успешно добавлен в базу!\n\n**Опубликовать новинку в"
              " канал и разослать клиентам?**"
          ),
          parse_mode="Markdown",
          reply_markup=markup,
      )
    else:
      bot.send_message(chat_id, f"❌ Ошибка сохранения в БД: {res.text}")
      show_main_menu(chat_id, user_id=ADMIN_ID)
  except Exception as e:
    bot.send_message(chat_id, f"❌ Ошибка: {e}")
    show_main_menu(chat_id, user_id=ADMIN_ID)

  clear_user_states(chat_id)


# --- ОБРАБОТКА КНОПОК РАССЫЛКИ ---
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("broadcast_")
    and call.from_user.id == ADMIN_ID
)
def handle_broadcast_decision(call):
  bot.answer_callback_query(call.id)
  chat_id = call.message.chat.id

  if call.data == "broadcast_no":
    bot.edit_message_text(
        "👍 Товар добавлен только в каталог.", chat_id, call.message.message_id
    )
    show_main_menu(chat_id, user_id=ADMIN_ID)
    return

  item_id = call.data.replace("broadcast_yes_", "")
  products = load_products()
  item = products.get(item_id)

  if not item:
    bot.edit_message_text(
        "❌ Товар не найден для рассылки.", chat_id, call.message.message_id
    )
    show_main_menu(chat_id, user_id=ADMIN_ID)
    return

  meaning_line = (
      f"🔮 Значение: {item.get('meaning')}\n" if item.get("meaning") else ""
  )
  post_text = (
      f"🔥 **НОВИНКА В МАСТЕРСКОЙ!** 🔥\n\n"
      f"📌 **{item.get('name')}**\n\n"
      f"🧵 Материал: {item.get('material')}\n"
      f"{meaning_line}"
      f"💵 Цена: {item.get('price')} ₽\n"
      f"⏱ Срок изготовления: {item.get('time')}\n\n"
      f"Заглядывай в бота, чтобы оформить заказ!"
  )

  bot_username = bot.get_me().username
  channel_markup = telebot.types.InlineKeyboardMarkup()
  channel_markup.add(
      telebot.types.InlineKeyboardButton(
          "🛒 Открыть каталог в боте", url=f"https://t.me/{bot_username}"
      )
  )

  try:
    if item.get("photo"):
      bot.send_photo(
          CHANNEL_USERNAME,
          item.get("photo"),
          caption=post_text,
          parse_mode="Markdown",
          reply_markup=channel_markup,
      )
    else:
      bot.send_message(
          CHANNEL_USERNAME,
          post_text,
          parse_mode="Markdown",
          reply_markup=channel_markup,
      )
  except Exception as e:
    print(f"Ошибка публикации в канал: {e}")

  all_users = get_all_users()
  success_count = 0

  for uid in all_users:
    if int(uid) == ADMIN_ID:
      continue
    try:
      client_msg = (
          f"🔥 **Пополнение в Храме Паука!**\n\nДоступна новинка:"
          f" *{item.get('name')}* ({item.get('price')} ₽).\nЗацени в каталоге!"
      )
      bot.send_message(int(uid), client_msg, parse_mode="Markdown")
      success_count += 1
    except Exception:
      pass

  bot.edit_message_text(
      (
          f"✅ Дроп успешно улетел в канал и в лички ({success_count}"
          " клиентам)!"
      ),
      chat_id,
      call.message.message_id,
  )
  show_main_menu(chat_id, user_id=ADMIN_ID)


# --- АДМИНКА: УДАЛЕНИЕ И РЕДАКТИРОВАНИЕ ТОВАРА ---
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("del_item_")
    and call.from_user.id == ADMIN_ID
)
def admin_delete_item(call):
  item_id = call.data.replace("del_item_", "")
  try:
    url = f"{SUPABASE_URL}/rest/v1/products?id=eq.{item_id}"
    res = requests.delete(url, headers=HEADERS, timeout=10)
    if res.status_code in [200, 204]:
      bot.answer_callback_query(call.id, "🗑 Товар удален!")
      bot.edit_message_text(
          "✅ Товар успешно удален из каталога.",
          call.message.chat.id,
          call.message.message_id,
      )
      show_main_menu(call.message.chat.id, user_id=ADMIN_ID)
    else:
      bot.answer_callback_query(call.id, "❌ Не удалось удалить товар.")
  except Exception as e:
    bot.answer_callback_query(call.id, f"❌ Ошибка: {e}")


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("edit_item_")
    and call.from_user.id == ADMIN_ID
)
def admin_edit_item_start(call):
  item_id = call.data.replace("edit_item_", "")
  bot.answer_callback_query(call.id)
  chat_id = call.message.chat.id

  admin_states[chat_id] = {"step": "edit_field", "item_id": item_id}

  markup = telebot.types.InlineKeyboardMarkup()
  markup.add(
      telebot.types.InlineKeyboardButton(
          "📝 Название", callback_data=f"edit_field_name_{item_id}"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "💵 Цена", callback_data=f"edit_field_price_{item_id}"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🧵 Материал", callback_data=f"edit_field_material_{item_id}"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🔮 Значение", callback_data=f"edit_field_meaning_{item_id}"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "⏱ Срок", callback_data=f"edit_field_time_{item_id}"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🖼 Фото", callback_data=f"edit_field_photo_{item_id}"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton("🔙 Отмена", callback_data="catalog")
  )

  bot.edit_message_text(
      "✏️ Что именно ты хочешь изменить в этом товаре?",
      chat_id,
      call.message.message_id,
      reply_markup=markup,
  )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("edit_field_")
    and call.from_user.id == ADMIN_ID
)
def admin_edit_field_choose(call):
  bot.answer_callback_query(call.id)
  parts = call.data.split("_")
  field = parts[2]
  item_id = parts[3]
  chat_id = call.message.chat.id

  admin_states[chat_id] = {
      "step": "save_edit",
      "item_id": item_id,
      "field": field,
  }
  if field == "photo":
    bot.edit_message_text(
        "📸 Пришли **новое фото** для этого товара:",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
    )
  else:
    bot.edit_message_text(
        f"✍️ Введи новое значение для поля **{field}**:",
        chat_id,
        call.message.message_id,
        parse_mode="Markdown",
    )


@bot.message_handler(
    content_types=["photo", "text"],
    func=lambda msg: msg.chat.id in admin_states
    and admin_states[msg.chat.id].get("step") == "save_edit"
    and msg.from_user.id == ADMIN_ID,
)
def admin_save_edited_field(message):
  chat_id = message.chat.id
  state = admin_states[chat_id]
  item_id = state["item_id"]
  field = state["field"]

  if field == "photo":
    if message.photo:
      val = message.photo[-1].file_id
    else:
      bot.send_message(chat_id, "❌ Пришли именно картинку!")
      return
  else:
    val = message.text.strip()
    if field == "price":
      try:
        val = int(val)
      except ValueError:
        bot.send_message(chat_id, "❌ Цена должна быть числом. Попробуй еще раз:")
        return

  try:
    url = f"{SUPABASE_URL}/rest/v1/products?id=eq.{item_id}"
    payload = {field: val}
    res = requests.patch(url, headers=HEADERS, json=payload, timeout=10)
    if res.status_code in [200, 204]:
      bot.send_message(
          chat_id,
          "✅ Товар успешно обновлен!",
          reply_markup=get_reply_markup(ADMIN_ID),
      )
    else:
      bot.send_message(chat_id, f"❌ Ошибка обновления: {res.text}")
  except Exception as e:
    bot.send_message(chat_id, f"❌ Ошибка: {e}")

  clear_user_states(chat_id)
  show_main_menu(chat_id, user_id=ADMIN_ID)


# --- КАТАЛОГ И ПРОСМОТР ТОВАРОВ ---
@bot.callback_query_handler(func=lambda call: call.data == "catalog")
def open_catalog(call):
  bot.answer_callback_query(call.id)
  clear_user_states(call.message.chat.id)
  markup = telebot.types.InlineKeyboardMarkup()

  markup.add(
      telebot.types.InlineKeyboardButton(
          "Браслеты", callback_data="cat_bracelets_0"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "Брелоки / Темляки", callback_data="cat_lanyards_0"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "Бусины, фигурки", callback_data="cat_beads_0"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🔮 Рунные наборы", callback_data="runes_menu"
      )
  )

  markup.add(
      telebot.types.InlineKeyboardButton(
          "🛒 Корзина", callback_data="view_cart"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🔙 Главное меню", callback_data="main_menu"
      )
  )

  text = "🛍 Выбери категорию товаров:"
  try:
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
  except Exception:
    bot.send_message(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "runes_menu")
def open_runes_menu(call):
  bot.answer_callback_query(call.id)
  markup = telebot.types.InlineKeyboardMarkup()
  markup.add(
      telebot.types.InlineKeyboardButton(
          "📦 Полный набор", callback_data="cat_runes_set_0"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🪄 Отдельные руны", callback_data="cat_runes_single_0"
      )
  )
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🔙 К категориям", callback_data="catalog"
      )
  )

  text = "🔮 Выберите раздел рун:"
  try:
    bot.edit_message_text(
        text, call.message.chat.id, call.message.message_id, reply_markup=markup
    )
  except Exception:
    bot.send_message(call.message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def view_category_item(call):
  bot.answer_callback_query(call.id)
  parts = call.data.split("_")
  if parts[1] == "runes" and parts[2] in ["set", "single"]:
    cat_key = f"{parts[1]}_{parts[2]}"
    index = int(parts[3])
  else:
    cat_key = parts[1]
    index = int(parts[2])

  products = load_products()
  cat_items = []
  for item_id, item in products.items():
    if isinstance(item, dict):
      item_cat = str(item.get("category", "")).strip().lower()
      target_cat = str(cat_key).strip().lower()
      if (
          item_cat == target_cat
          or (target_cat == "bracelets" and "браслет" in item_cat)
          or (
              target_cat == "beads"
              and ("бусин" in item_cat or "фигурк" in item_cat)
          )
          or (target_cat == "runes_set" and "runes_set" in item_cat)
          or (target_cat == "runes_single" and "runes_single" in item_cat)
      ):
        cat_items.append((item_id, item))

  markup = telebot.types.InlineKeyboardMarkup()

  if not cat_items:
    text = (
        f"📁 Категория: {CATEGORIES.get(cat_key, 'Товары')}\n\nВ этой"
        " категории пока нет товаров."
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🛒 Корзина", callback_data="view_cart"
        )
    )
    if "runes" in cat_key:
      markup.add(
          telebot.types.InlineKeyboardButton(
              "🔙 К рунам", callback_data="runes_menu"
          )
      )
    else:
      markup.add(
          telebot.types.InlineKeyboardButton(
              "🔙 К категориям", callback_data="catalog"
          )
      )
    try:
      bot.edit_message_text(
          text,
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
      )
    except Exception:
      bot.send_message(call.message.chat.id, text, reply_markup=markup)
    return

  total_items = len(cat_items)
  index = index % total_items
  item_id, item = cat_items[index]

  name = item.get("name", "Товар")
  price = item.get("price", 0)
  material = item.get("material", "Не указан")
  meaning = item.get("meaning")
  time_val = item.get("time", "Не указан")
  current_photo = item.get("photo")

  meaning_str = f"🔮 Значение: {meaning}\n" if meaning else ""
  text = (
      f"📌 {name}\n\n"
      f"🧵 Материал: {material}\n"
      f"{meaning_str}"
      f"💵 Цена: {price} ₽\n"
      f"⏱ Срок изготовления: {time_val}"
  )

  markup = telebot.types.InlineKeyboardMarkup()
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🛒 Добавить в корзину", callback_data=f"cart_add_{item_id}"
      )
  )

  if call.from_user.id == ADMIN_ID:
    markup.add(
        telebot.types.InlineKeyboardButton(
            "✏️ Редактировать", callback_data=f"edit_item_{item_id}"
        ),
        telebot.types.InlineKeyboardButton(
            "❌ Удалить", callback_data=f"del_item_{item_id}"
        ),
    )

  nav_buttons = [
      telebot.types.InlineKeyboardButton(
          "⬅️ Назад", callback_data=f"cat_{cat_key}_{index - 1}"
      ),
      telebot.types.InlineKeyboardButton(
          "Вперед ➡️", callback_data=f"cat_{cat_key}_{index + 1}"
      ),
  ]
  markup.row(*nav_buttons)
  markup.add(
      telebot.types.InlineKeyboardButton(
          "🛒 Корзина", callback_data="view_cart"
      )
  )
  if "runes" in cat_key:
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🔙 К рунам", callback_data="runes_menu"
        )
    )
  else:
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🔙 К категориям", callback_data="catalog"
        )
    )

  try:
    if current_photo:
      media = telebot.types.InputMediaPhoto(current_photo, caption=text)
      bot.edit_message_media(
          media, call.message.chat.id, call.message.message_id, reply_markup=markup
      )
    else:
      bot.edit_message_text(
          text,
          call.message.chat.id,
          call.message.message_id,
          reply_markup=markup,
      )
  except Exception:
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
      pass
    if current_photo:
      bot.send_photo(
          call.message.chat.id, current_photo, caption=text, reply_markup=markup
      )
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
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🛍 В каталог", callback_data="catalog"
        )
    )
  else:
    text = "🛒 Ваш заказ:\n\n"
    total = 0
    for idx, item in enumerate(cart):
      text += f"{idx + 1}. {item.get('name')} — {item.get('price')} ₽\n"
      total += item.get("price", 0)
    text += f"\n💰 Итого: {total} ₽"
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Оформить заказ", callback_data="checkout"
        )
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🗑 Очистить корзину", callback_data="clear_cart"
        )
    )
    markup.add(
        telebot.types.InlineKeyboardButton(
            "🛍 В каталог", callback_data="catalog"
        )
    )

  markup.add(
      telebot.types.InlineKeyboardButton(
          "🔙 Главное меню", callback_data="main_menu"
      )
  )
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

  real_user = call.from_user

  bracelet_indices = []
  for idx, item in enumerate(cart):
    cat = str(item.get("category", "")).lower()
    name = str(item.get("name", "")).lower()
    if "браслет" in cat or "bracelet" in cat or "браслет" in name:
      bracelet_indices.append(idx)

  if bracelet_indices:
    checkout_states[chat_id] = {
        "cart": cart,
        "indices": bracelet_indices,
        "current_idx": 0,
        "message_id": message.message_id,
        "user": real_user,
    }
    ask_next_wrist_size(chat_id)
  else:
    finalize_direct_order(chat_id, real_user, cart, message.message_id)


def ask_next_wrist_size(chat_id):
  state = checkout_states.get(chat_id)
  if not state:
    return

  current_item_index = state["indices"][state["current_idx"]]
  item_name = state["cart"][current_item_index].get("name", "Браслет")

  text = (
      f"📏 Введите размер запястья для товара:\n*{item_name}* (например, 18"
      " см):"
  )
  markup = telebot.types.InlineKeyboardMarkup()
  markup.add(
      telebot.types.InlineKeyboardButton(
          "❌ Отмена", callback_data="view_cart"
      )
  )

  try:
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)
  except Exception:
    pass


@bot.message_handler(func=lambda msg: msg.chat.id in checkout_states)
def process_wrist_size_input(message):
  chat_id = message.chat.id
  size_text = message.text.strip()

  if size_text == "🕷 Запустить Храм Паука" or size_text.startswith("/"):
    clear_user_states(chat_id)
    return

  state = checkout_states[chat_id]
  current_item_index = state["indices"][state["current_idx"]]

  state["cart"][current_item_index]["name"] += f" (Запястье: {size_text})"
  state["current_idx"] += 1

  if state["current_idx"] < len(state["indices"]):
    ask_next_wrist_size(chat_id)
  else:
    cart = state["cart"]
    user_info = state.get("user") or message.from_user
    clear_user_states(chat_id)

    order_id = get_next_order_number()
    total = sum(item.get("price", 0) for item in cart)
    save_order_to_db(order_id, chat_id, cart, total)

    bot.send_message(
        chat_id,
        f"✅ Заказ №{order_id} успешно оформлен! Мастер принял его в работу.",
        reply_markup=get_reply_markup(user_info.id),
    )
    show_main_menu(chat_id, user_id=user_info.id)
    send_order_to_admin(order_id, chat_id, user_info, cart, total)
    user_carts[chat_id] = []


def finalize_direct_order(chat_id, user_obj, cart, message_id=None):
  order_id = get_next_order_number()
  total = sum(item.get("price", 0) for item in cart)
  user_id = getattr(user_obj, "id", chat_id)

  save_order_to_db(order_id, chat_id, cart, total)

  client_text = (
      f"✅ Заказ №{order_id} успешно оформлен! Мастер принял его в работу."
  )
  try:
    if message_id:
      bot.edit_message_text(client_text, chat_id, message_id)
    else:
      bot.send_message(
          chat_id, client_text, reply_markup=get_reply_markup(user_id)
      )
    show_main_menu(chat_id, user_id=user_id)
  except Exception:
    bot.send_message(
        chat_id, client_text, reply_markup=get_reply_markup(user_id)
    )
    show_main_menu(chat_id, user_id=user_id)

  send_order_to_admin(order_id, chat_id, user_obj, cart, total)
  user_carts[chat_id] = []


@bot.callback_query_handler(func=lambda call: call.data.startswith("ready_"))
def mark_order_ready(call):
  bot.answer_callback_query(call.id, "Статус обновлен!")
  parts = call.data.split("_")
  order_id = parts[1]
  client_id = parts[2]

  update_order_status_in_db(order_id, "ready")

  try:
    bot.send_message(
        int(client_id),
        (
            f"🎉 Твой заказ №{order_id} готов! Мастер связался с тобой или ждет"
            " для выдачи."
        ),
    )
  except Exception as e:
    print(f"Не удалось отправить уведомление клиенту: {e}")

  try:
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ Выполнено", callback_data="noop")
    )
    bot.edit_message_reply_markup(
        call.message.chat.id, call.message.message_id, reply_markup=markup
    )
  except Exception as e:
    print(f"Ошибка изменения кнопки у админа: {e}")


# --- FLASK СЕРВЕР ДЛЯ ВЕБХУКОВ ---
app = Flask(__name__)


@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
  if request.headers.get("content-type") == "application/json":
    json_string = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200
  else:
    return "Invalid", 403


@app.route("/")
def index():
  return "Bot is running on Webhook!"


if __name__ == "__main__":
  WEBHOOK_URL = f"https://thespidertemplebot.onrender.com/{TOKEN}"
  bot.remove_webhook()
  bot.set_webhook(url=WEBHOOK_URL)
  print(f"Вебхук автоматически установлен на: {WEBHOOK_URL}")

  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
