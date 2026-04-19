import telebot
from telebot import types
import json
import logging

from config import *
import database as db

logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(BOT_TOKEN)


def is_manager(user_id):
    return user_id == OWNER_ID or db.is_manager(user_id)


def get_all_manager_ids():
    ids = db.get_manager_ids()
    if OWNER_ID not in ids:
        ids.append(OWNER_ID)
    return ids


# ============ KEYBOARDS ============

def contact_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📱 Поделиться контактом", request_contact=True))
    return kb


def main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("💱 Обменять валюту"))
    kb.row(types.KeyboardButton("📋 Мои заявки"), types.KeyboardButton("💬 Поддержка"))
    if is_manager(user_id):
        kb.add(types.KeyboardButton("👨‍💼 Панель менеджера"))
    return kb


def buy_currency_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🇨🇳 Китайский юань (CNY)", callback_data="buy:cny"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def pay_currency_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🇷🇺 Российский рубль (RUB)", callback_data="pay:rub"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    return kb


def confirm_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Продолжить", callback_data="confirm:yes"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="confirm:no")
    )
    return kb


def method_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📱 Alipay", callback_data="method:alipay"),
        types.InlineKeyboardButton("💬 WeChat", callback_data="method:wechat"),
        types.InlineKeyboardButton("💳 Банковская карта", callback_data="method:card")
    )
    return kb


def manager_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🆕 Новые заявки", callback_data="mgr:new"),
        types.InlineKeyboardButton("📋 Все активные", callback_data="mgr:active"),
        types.InlineKeyboardButton("🔄 Обновить", callback_data="mgr:refresh")
    )
    return kb


def orders_kb(orders):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for o in orders[:10]:
        status = {"new": "🆕", "in_progress": "🔄"}.get(o["status"], "❓")
        name = (o.get("first_name") or "Клиент")[:12]
        kb.add(types.InlineKeyboardButton(
            f"{status} #{o['order_number'][-4:]} • {name} • {o['cny_amount']:,.0f}¥",
            callback_data=f"mgr:order:{o['id']}"
        ))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="mgr:menu"))
    return kb


def order_kb(order):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if order["status"] == "new":
        kb.add(types.InlineKeyboardButton("✅ Взять", callback_data=f"mgr:take:{order['id']}"))
    if order["status"] not in ("completed", "cancelled", "closed"):
        kb.row(
            types.InlineKeyboardButton("✅ Выполнено", callback_data=f"mgr:done:{order['id']}"),
            types.InlineKeyboardButton("🚫 Закрыть", callback_data=f"mgr:close:{order['id']}")
        )
    kb.add(types.InlineKeyboardButton("⬅️ К заявкам", callback_data="mgr:active"))
    return kb


# ============ OWNER COMMANDS ============

@bot.message_handler(commands=['addmanager'])
def cmd_addmanager(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split()
    if len(parts) < 2:
        bot.send_message(msg.chat.id, "❌ Использование: /addmanager <user_id>")
        return
    try:
        user_id = int(parts[1])
        db.add_manager(user_id)
        bot.send_message(msg.chat.id, f"✅ Менеджер {user_id} добавлен!")
    except ValueError:
        bot.send_message(msg.chat.id, "❌ ID должен быть числом")


@bot.message_handler(commands=['delmanager'])
def cmd_delmanager(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split()
    if len(parts) < 2:
        bot.send_message(msg.chat.id, "❌ Использование: /delmanager <user_id>")
        return
    try:
        user_id = int(parts[1])
        if db.remove_manager(user_id):
            bot.send_message(msg.chat.id, f"✅ Менеджер {user_id} удалён!")
        else:
            bot.send_message(msg.chat.id, f"❌ Менеджер {user_id} не найден")
    except ValueError:
        bot.send_message(msg.chat.id, "❌ ID должен быть числом")


@bot.message_handler(commands=['managers'])
def cmd_managers(msg):
    if msg.from_user.id != OWNER_ID:
        return
    managers = db.get_managers()
    if not managers:
        bot.send_message(msg.chat.id, "📋 Менеджеров нет (кроме вас)")
        return
    text = "👨‍💼 <b>Менеджеры:</b>\n\n"
    for m in managers:
        username = f"@{m['username']}" if m.get('username') else "нет username"
        text += f"• {m['user_id']} ({username})\n"
    bot.send_message(msg.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=['setrates'])
def cmd_setrates(msg):
    if msg.from_user.id != OWNER_ID:
        return
    
    parts = msg.text.split()
    if len(parts) < 7:
        rates = db.get_rates()
        text = f"""📊 <b>Текущие курсы (1 CNY = X RUB):</b>

• 1-100: {rates.get('1-100', 19.29)}
• 101-500: {rates.get('101-500', 12.57)}
• 501-1000: {rates.get('501-1000', 12.38)}
• 1001-5000: {rates.get('1001-5000', 12.17)}
• 5001-20000: {rates.get('5001-20000', 12.13)}
• 20001+: {rates.get('20001+', 12.06)}

<b>Изменить:</b>
/setrates 19.29 12.57 12.38 12.17 12.13 12.06
(6 чисел через пробел)
"""
        bot.send_message(msg.chat.id, text, parse_mode="HTML")
        return
    
    try:
        r = [float(x.replace(",", ".")) for x in parts[1:7]]
        rates = {
            "1-100": r[0],
            "101-500": r[1],
            "501-1000": r[2],
            "1001-5000": r[3],
            "5001-20000": r[4],
            "20001+": r[5]
        }
        db.set_rates(rates)
        bot.send_message(msg.chat.id, "✅ Курсы обновлены!")
    except:
        bot.send_message(msg.chat.id, "❌ Ошибка. Введите 6 чисел через пробел")


@bot.message_handler(commands=['stats'])
def cmd_stats(msg):
    if msg.from_user.id != OWNER_ID:
        return
    s = db.get_stats()
    text = f"""📊 <b>Статистика</b>

📋 Всего заявок: {s['total']}
✅ Выполнено: {s['completed']}
🔄 Активных: {s['active']}

💰 Оборот: {s['total_rub']:,.0f} ₽
💴 Отправлено: {s['total_cny']:,.2f} ¥
"""
    bot.send_message(msg.chat.id, text, parse_mode="HTML")


@bot.message_handler(commands=['setphoto'])
def cmd_setphoto(msg):
    """Команда для установки фото инструкций: /setphoto alipay (в ответ на фото)"""
    if msg.from_user.id != OWNER_ID:
        return
    
    parts = msg.text.split()
    if len(parts) < 2:
        bot.send_message(msg.chat.id, 
            "📷 <b>Установка фото инструкций</b>\n\n"
            "1. Отправьте фото\n"
            "2. Ответьте на него командой:\n"
            "   /setphoto alipay\n"
            "   /setphoto wechat\n"
            "   /setphoto card\n",
            parse_mode="HTML")
        return
    
    if not msg.reply_to_message or not msg.reply_to_message.photo:
        bot.send_message(msg.chat.id, "❌ Ответьте этой командой на фото")
        return
    
    key = parts[1].lower()
    if key not in ["alipay", "wechat", "card"]:
        bot.send_message(msg.chat.id, "❌ Допустимые ключи: alipay, wechat, card")
        return
    
    file_id = msg.reply_to_message.photo[-1].file_id
    db.set_photo(f"instruction_{key}", file_id)
    bot.send_message(msg.chat.id, f"✅ Фото для {key} сохранено!")


# ============ USER HANDLERS ============

@bot.message_handler(commands=['start', 'keyboard'])
def cmd_start(msg):
    user = db.get_user(msg.from_user.id)
    db.save_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    db.clear_state(msg.from_user.id)
    
    if not user or not user.get("phone"):
        bot.send_message(msg.chat.id, WELCOME_MESSAGE, parse_mode="HTML")
        bot.send_message(msg.chat.id, PHONE_REQUEST, parse_mode="HTML", reply_markup=contact_kb())
    else:
        bot.send_message(msg.chat.id, SAFETY_WARNING, parse_mode="HTML")
        bot.send_message(msg.chat.id, MAIN_MENU, parse_mode="HTML", reply_markup=main_kb(msg.from_user.id))


@bot.message_handler(content_types=['contact'])
def on_contact(msg):
    phone = msg.contact.phone_number
    db.save_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name, phone)
    
    bot.send_message(msg.chat.id, PHONE_SAVED.format(phone=phone), parse_mode="HTML")
    bot.send_message(msg.chat.id, SAFETY_WARNING, parse_mode="HTML")
    bot.send_message(msg.chat.id, MAIN_MENU, parse_mode="HTML", reply_markup=main_kb(msg.from_user.id))


@bot.message_handler(func=lambda m: m.text == "💱 Обменять валюту")
def start_exchange(msg):
    db.set_state(msg.from_user.id, "select_buy")
    bot.send_message(msg.chat.id, SELECT_BUY_CURRENCY, parse_mode="HTML", reply_markup=buy_currency_kb())


@bot.callback_query_handler(func=lambda c: c.data == "buy:cny")
def on_buy_cny(call):
    db.set_state(call.from_user.id, "select_pay", {"buy": "cny"})
    bot.edit_message_text(SELECT_PAY_CURRENCY, call.message.chat.id, call.message.message_id, 
                         parse_mode="HTML", reply_markup=pay_currency_kb())


@bot.callback_query_handler(func=lambda c: c.data == "pay:rub")
def on_pay_rub(call):
    state, data = db.get_state(call.from_user.id)
    data["pay"] = "rub"
    db.set_state(call.from_user.id, "enter_amount", data)
    
    rates = db.get_rates()
    text = ENTER_AMOUNT.format(
        r1=rates.get("1-100", 19.29),
        r2=rates.get("101-500", 12.57),
        r3=rates.get("501-1000", 12.38),
        r4=rates.get("1001-5000", 12.17),
        r5=rates.get("5001-20000", 12.13),
        r6=rates.get("20001+", 12.06)
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data == "cancel")
def on_cancel(call):
    db.clear_state(call.from_user.id)
    bot.edit_message_text("❌ Отменено", call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, MAIN_MENU, parse_mode="HTML", reply_markup=main_kb(call.from_user.id))


@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm:"))
def on_confirm(call):
    action = call.data.split(":")[1]
    
    if action == "no":
        db.clear_state(call.from_user.id)
        bot.edit_message_text("❌ Заявка отменена", call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, MAIN_MENU, parse_mode="HTML", reply_markup=main_kb(call.from_user.id))
        return
    
    # Подтвердили — создаём заявку
    state, data = db.get_state(call.from_user.id)
    if not data or "cny_amount" not in data:
        bot.answer_callback_query(call.id, "Ошибка, начните заново", show_alert=True)
        return
    
    order = db.create_order(
        call.from_user.id,
        data["cny_amount"],
        data["rub_amount"],
        data["rate"]
    )
    
    db.set_state(call.from_user.id, "select_method", {"order_id": order["id"]})
    
    bot.edit_message_text(
        f"✅ <b>Заявка #{order['order_number']} создана!</b>\n\n"
        f"💴 {order['cny_amount']:,.0f} CNY = {order['rub_amount']:,.0f} RUB\n\n"
        f"Выберите способ пополнения:",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=method_kb()
    )
    
    # Уведомляем менеджеров
    for mgr in get_all_manager_ids():
        try:
            bot.send_message(mgr, f"🆕 Новая заявка #{order['order_number']}\n💴 {order['cny_amount']:,.0f} CNY")
        except:
            pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("method:"))
def on_method(call):
    method = call.data.split(":")[1]
    state, data = db.get_state(call.from_user.id)
    
    if not data or "order_id" not in data:
        bot.answer_callback_query(call.id, "Ошибка", show_alert=True)
        return
    
    order = db.get_order(data["order_id"])
    if not order:
        bot.answer_callback_query(call.id, "Заявка не найдена", show_alert=True)
        return
    
    db.update_order(order["id"], status="in_progress")
    db.clear_state(call.from_user.id)
    
    # Текст инструкций
    instructions = {
        "alipay": """✅ <b>Для пополнения Alipay:</b>

1. QR-код: Отправьте QR-код для пополнения юаней:
   Pay/Collect → Receive → Save image (не скриншот)

2. Контакты: Укажите номер телефона или почту, привязанные к Alipay.

3. ФИО: Фамилия и имя (латиницей, как в загранпаспорте).

📌 Если реквизиты уже сохранены, ничего присылать не нужно.
❓ Есть вопросы? Пишите!""",
        
        "wechat": """✅ <b>Для пополнения WeChat:</b>

1. Откройте: Я → Платежи и услуги → Деньги → Receive money
2. Сохраните код получения
3. Отправьте QR-код сюда
4. Укажите ФИО (латиницей)

📌 Если реквизиты уже сохранены, ничего присылать не нужно.
❓ Есть вопросы? Пишите!""",
        
        "card": """✅ <b>Для пополнения карты:</b>

Отправьте:
• ФИО (латиницей)
• Название банка
• Номер карты

⚠️ Карта должна быть китайского банка

❓ Есть вопросы? Пишите!"""
    }
    
    bot.edit_message_text(
        f"Заявка #{order['order_number']} — способ: {method.upper()}",
        call.message.chat.id, call.message.message_id
    )
    
    # Отправляем фото если есть
    photo_id = db.get_photo(f"instruction_{method}")
    if photo_id:
        bot.send_photo(call.message.chat.id, photo_id, caption=instructions[method], parse_mode="HTML")
    else:
        bot.send_message(call.message.chat.id, instructions[method], parse_mode="HTML")
    
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: m.text == "📋 Мои заявки")
def my_orders(msg):
    order = db.get_user_active_order(msg.from_user.id)
    if order:
        status_text = {
            "new": "🆕 Новая",
            "in_progress": "🔄 В работе",
            "completed": "✅ Выполнена",
            "cancelled": "❌ Отменена",
            "closed": "🚫 Закрыта"
        }.get(order["status"], order["status"])
        
        bot.send_message(msg.chat.id,
            f"📋 <b>Заявка {order['order_number']}</b>\n\n"
            f"💴 {order['cny_amount']:,.0f} CNY = {order['rub_amount']:,.0f} RUB\n"
            f"📌 Статус: {status_text}",
            parse_mode="HTML"
        )
    else:
        bot.send_message(msg.chat.id, "📭 У вас нет активных заявок.")


@bot.message_handler(func=lambda m: m.text == "💬 Поддержка")
def support(msg):
    bot.send_message(msg.chat.id,
        "💬 <b>Поддержка</b>\n\n"
        "Напишите сообщение — менеджер ответит.\n\n"
        "⏰ Работаем: 24/7",
        parse_mode="HTML"
    )


# ============ MANAGER PANEL ============

@bot.message_handler(func=lambda m: m.text == "👨‍💼 Панель менеджера")
def manager_panel(msg):
    if not is_manager(msg.from_user.id):
        return
    
    new = len(db.get_new_orders())
    active = len(db.get_active_orders())
    
    bot.send_message(msg.chat.id,
        f"👨‍💼 <b>Панель менеджера</b>\n\n"
        f"🆕 Новых: {new}\n"
        f"📋 Активных: {active}",
        parse_mode="HTML",
        reply_markup=manager_kb()
    )


@bot.callback_query_handler(func=lambda c: c.data in ["mgr:menu", "mgr:refresh"])
def mgr_menu(call):
    if not is_manager(call.from_user.id):
        return
    
    new = len(db.get_new_orders())
    active = len(db.get_active_orders())
    
    bot.edit_message_text(
        f"👨‍💼 <b>Панель менеджера</b>\n\n"
        f"🆕 Новых: {new}\n"
        f"📋 Активных: {active}",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
        reply_markup=manager_kb()
    )
    bot.answer_callback_query(call.id, "Обновлено" if "refresh" in call.data else None)


@bot.callback_query_handler(func=lambda c: c.data == "mgr:new")
def mgr_new(call):
    if not is_manager(call.from_user.id):
        return
    
    orders = db.get_new_orders()
    if not orders:
        bot.answer_callback_query(call.id, "Нет новых заявок", show_alert=True)
        return
    
    bot.edit_message_text(
        f"🆕 <b>Новые заявки ({len(orders)})</b>",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
        reply_markup=orders_kb(orders)
    )


@bot.callback_query_handler(func=lambda c: c.data == "mgr:active")
def mgr_active(call):
    if not is_manager(call.from_user.id):
        return
    
    orders = db.get_active_orders()
    if not orders:
        bot.answer_callback_query(call.id, "Нет активных заявок", show_alert=True)
        return
    
    bot.edit_message_text(
        f"📋 <b>Активные заявки ({len(orders)})</b>",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
        reply_markup=orders_kb(orders)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("mgr:order:"))
def mgr_order(call):
    if not is_manager(call.from_user.id):
        return
    
    order_id = int(call.data.split(":")[2])
    order = db.get_order(order_id)
    
    if not order:
        bot.answer_callback_query(call.id, "Заявка не найдена", show_alert=True)
        return
    
    db.set_state(call.from_user.id, "mgr_chat", {"order_id": order_id})
    
    status = {"new": "🆕 Новая", "in_progress": "🔄 В работе"}.get(order["status"], order["status"])
    
    bot.edit_message_text(
        f"📋 <b>Заявка {order['order_number']}</b>\n\n"
        f"👤 {order.get('first_name', 'Клиент')}\n"
        f"📱 {order.get('phone', 'нет')}\n"
        f"💬 @{order.get('username', 'нет')}\n\n"
        f"💴 {order['cny_amount']:,.0f} CNY = {order['rub_amount']:,.0f} RUB\n"
        f"📌 Статус: {status}\n\n"
        f"<i>Напишите сообщение — оно уйдёт клиенту</i>",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
        reply_markup=order_kb(order)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("mgr:take:"))
def mgr_take(call):
    if not is_manager(call.from_user.id):
        return
    
    order_id = int(call.data.split(":")[2])
    db.update_order(order_id, status="in_progress", manager_id=call.from_user.id)
    order = db.get_order(order_id)
    
    bot.send_message(order["user_id"], MANAGER_CONNECTED, parse_mode="HTML")
    bot.answer_callback_query(call.id, "Заявка взята!")
    
    db.set_state(call.from_user.id, "mgr_chat", {"order_id": order_id})
    
    bot.edit_message_text(
        f"📋 <b>Заявка {order['order_number']}</b>\n\n"
        f"👤 {order.get('first_name', 'Клиент')}\n"
        f"📱 {order.get('phone', 'нет')}\n"
        f"💬 @{order.get('username', 'нет')}\n\n"
        f"💴 {order['cny_amount']:,.0f} CNY = {order['rub_amount']:,.0f} RUB\n"
        f"📌 Статус: 🔄 В работе\n\n"
        f"<i>Напишите сообщение — оно уйдёт клиенту</i>",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML",
        reply_markup=order_kb(order)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("mgr:done:"))
def mgr_done(call):
    if not is_manager(call.from_user.id):
        return
    
    order_id = int(call.data.split(":")[2])
    db.update_order(order_id, status="completed")
    order = db.get_order(order_id)
    db.clear_state(call.from_user.id)
    
    bot.send_message(
        order["user_id"],
        ORDER_COMPLETED.format(order_number=order["order_number"], cny_amount=order["cny_amount"]),
        parse_mode="HTML"
    )
    
    bot.edit_message_text(f"✅ Заявка {order['order_number']} выполнена!", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id, "Готово!")


@bot.callback_query_handler(func=lambda c: c.data.startswith("mgr:close:"))
def mgr_close(call):
    if not is_manager(call.from_user.id):
        return
    
    order_id = int(call.data.split(":")[2])
    db.update_order(order_id, status="closed")
    order = db.get_order(order_id)
    db.clear_state(call.from_user.id)
    
    bot.send_message(order["user_id"], DIALOG_CLOSED, parse_mode="HTML")
    bot.edit_message_text(f"🚫 Диалог по заявке {order['order_number']} закрыт.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


# ============ MESSAGE RELAY ============

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'document'])
def relay(msg):
    # Пропускаем кнопки меню
    if msg.text in ["📋 Мои заявки", "💬 Поддержка", "👨‍💼 Панель менеджера", "💱 Обменять валюту"]:
        return
    
    user_id = msg.from_user.id
    state, data = db.get_state(user_id)
    
    # Ввод суммы CNY
    if state == "enter_amount":
        try:
            cny = float(msg.text.replace(",", ".").replace(" ", ""))
            if cny < 1:
                bot.send_message(msg.chat.id, "❌ Минимум 1 CNY")
                return
            
            rate = db.get_rate_for_amount(cny)
            rub = cny * rate
            
            data["cny_amount"] = cny
            data["rub_amount"] = rub
            data["rate"] = rate
            db.set_state(user_id, "confirm", data)
            
            text = ORDER_CONFIRM.format(
                rate=rate,
                cny_amount=cny,
                rub_amount=rub
            )
            bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=confirm_kb())
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Введите число")
        return
    
    # Менеджер пишет клиенту
    if is_manager(user_id) and state == "mgr_chat" and data and "order_id" in data:
        order = db.get_order(data["order_id"])
        if order:
            try:
                if msg.photo:
                    bot.send_photo(order["user_id"], msg.photo[-1].file_id, 
                                  caption=f"👨‍💼 <b>Менеджер:</b>\n{msg.caption or ''}", parse_mode="HTML")
                elif msg.document:
                    bot.send_document(order["user_id"], msg.document.file_id, 
                                     caption=f"👨‍💼 <b>Менеджер:</b>\n{msg.caption or ''}", parse_mode="HTML")
                else:
                    bot.send_message(order["user_id"], f"👨‍💼 <b>Менеджер:</b>\n{msg.text}", parse_mode="HTML")
                bot.send_message(msg.chat.id, "✅ Отправлено")
            except Exception as e:
                bot.send_message(msg.chat.id, f"❌ Ошибка: {e}")
        return
    
    # Клиент пишет
    order = db.get_user_active_order(user_id)
    if order and order.get("manager_id"):
        try:
            header = f"💬 <b>Клиент #{order['order_number'][-4:]}</b> ({order.get('first_name', 'Клиент')}):\n\n"
            if msg.photo:
                bot.send_photo(order["manager_id"], msg.photo[-1].file_id, 
                              caption=header + (msg.caption or ""), parse_mode="HTML")
            elif msg.document:
                bot.send_document(order["manager_id"], msg.document.file_id, 
                                 caption=header + (msg.caption or ""), parse_mode="HTML")
            else:
                bot.send_message(order["manager_id"], header + msg.text, parse_mode="HTML")
            bot.send_message(msg.chat.id, "✅ Отправлено менеджеру")
        except:
            bot.send_message(msg.chat.id, "⏳ Менеджер получит ваше сообщение")
    elif order:
        for mgr in get_all_manager_ids():
            try:
                bot.send_message(mgr, f"💬 Сообщение в заявке #{order['order_number']}")
            except:
                pass
        bot.send_message(msg.chat.id, "✅ Сообщение получено. Менеджер скоро ответит.")
    else:
        bot.send_message(msg.chat.id, "💬 Нажмите «💱 Обменять валюту» чтобы создать заявку.", 
                        reply_markup=main_kb(user_id))


if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling()
