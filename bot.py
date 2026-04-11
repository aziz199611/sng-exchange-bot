import telebot
from telebot import types
import json
import logging

from config import *
import database as db

logging.basicConfig(level=logging.INFO)

bot = telebot.TeleBot(BOT_TOKEN)

# Владелец бота (твой ID)
OWNER_ID = 714403607


def is_manager(user_id):
    """Проверка менеджера (включая владельца)"""
    return user_id == OWNER_ID or db.is_manager(user_id)


def get_all_manager_ids():
    """Все менеджеры + владелец"""
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
    kb.add(types.KeyboardButton("💱 Обменять валюту", web_app=types.WebAppInfo(url=WEBAPP_URL)))
    kb.row(types.KeyboardButton("📋 Мои заявки"), types.KeyboardButton("💬 Поддержка"))
    if is_manager(user_id):
        kb.add(types.KeyboardButton("👨‍💼 Панель менеджера"))
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


def orders_kb(orders, back="mgr:menu"):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for o in orders[:10]:
        status = {"new": "🆕", "in_progress": "🔄", "awaiting": "📝"}.get(o["status"], "❓")
        name = (o.get("first_name") or "Клиент")[:12]
        kb.add(types.InlineKeyboardButton(
            f"{status} #{o['order_number'][-4:]} • {name} • {o['rub_amount']:,.0f}₽",
            callback_data=f"mgr:order:{o['id']}"
        ))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=back))
    return kb


def order_kb(order):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if order["status"] == "new":
        kb.add(types.InlineKeyboardButton("✅ Взять", callback_data=f"mgr:take:{order['id']}"))
    if order["status"] not in ("completed", "cancelled"):
        kb.row(
            types.InlineKeyboardButton("✅ Выполнено", callback_data=f"mgr:done:{order['id']}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data=f"mgr:cancel:{order['id']}")
        )
    kb.add(types.InlineKeyboardButton("⬅️ К заявкам", callback_data="mgr:active"))
    return kb


# ============ HANDLERS ============

# === OWNER COMMANDS ===

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


@bot.message_handler(commands=['setrate'])
def cmd_setrate(msg):
    if msg.from_user.id != OWNER_ID:
        return
    
    parts = msg.text.split()
    if len(parts) < 2:
        current = db.get_rate()
        bot.send_message(msg.chat.id, f"📊 Текущий курс: 1 CNY = {current} ₽\n\nИзменить: /setrate <курс>")
        return
    
    try:
        rate = float(parts[1].replace(",", "."))
        db.set_rate(rate)
        bot.send_message(msg.chat.id, f"✅ Курс изменён: 1 CNY = {rate} ₽")
    except ValueError:
        bot.send_message(msg.chat.id, "❌ Курс должен быть числом")


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


# === USER COMMANDS ===

@bot.message_handler(commands=['start', 'keyboard'])
def cmd_start(msg):
    user = db.get_user(msg.from_user.id)
    db.save_user(msg.from_user.id, msg.from_user.username, msg.from_user.first_name)
    
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


@bot.message_handler(content_types=['web_app_data'])
def on_webapp(msg):
    try:
        data = json.loads(msg.web_app_data.data)
        order = db.create_order(
            msg.from_user.id,
            data["rub_amount"],
            data["cny_amount"],
            data["rate"]
        )
        db.set_state(msg.from_user.id, "select_method", str(order["id"]))
        
        text = ORDER_CREATED.format(
            order_number=order["order_number"],
            rub_amount=order["rub_amount"],
            cny_amount=order["cny_amount"],
            rate=order["rate"]
        )
        bot.send_message(msg.chat.id, text, parse_mode="HTML", reply_markup=method_kb())
        
        # Уведомление менеджерам
        for mgr in get_all_manager_ids():
            try:
                bot.send_message(mgr, f"🆕 Новая заявка #{order['order_number']}")
            except:
                pass
                
    except Exception as e:
        logging.error(f"Webapp error: {e}")
        bot.send_message(msg.chat.id, "❌ Ошибка. Попробуйте ещё раз.")


@bot.callback_query_handler(func=lambda c: c.data.startswith("method:"))
def on_method(call):
    method = call.data.split(":")[1]
    state, order_id = db.get_state(call.from_user.id)
    
    if not order_id:
        bot.answer_callback_query(call.id, "Заявка не найдена", show_alert=True)
        return
    
    order = db.get_order(int(order_id))
    if not order:
        bot.answer_callback_query(call.id, "Заявка не найдена", show_alert=True)
        return
    
    db.update_order(order["id"], method=method, status="awaiting")
    db.set_state(call.from_user.id, "awaiting_details", order_id)
    
    instructions = {
        "alipay": ALIPAY_INSTRUCTIONS,
        "wechat": WECHAT_INSTRUCTIONS,
        "card": CARD_INSTRUCTIONS
    }
    
    bot.edit_message_text(instructions[method], call.message.chat.id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: m.text == "📋 Мои заявки")
def my_orders(msg):
    order = db.get_user_active_order(msg.from_user.id)
    if order:
        status_text = {
            "new": "🆕 Новая",
            "awaiting": "📝 Ожидаем реквизиты",
            "in_progress": "🔄 В работе",
            "completed": "✅ Выполнена",
            "cancelled": "❌ Отменена"
        }.get(order["status"], order["status"])
        
        method_text = {
            "alipay": "Alipay",
            "wechat": "WeChat", 
            "card": "Карта"
        }.get(order.get("method"), "Не выбран")
        
        bot.send_message(msg.chat.id,
            f"📋 <b>Заявка {order['order_number']}</b>\n\n"
            f"💵 {order['rub_amount']:,.0f} ₽ → {order['cny_amount']:,.2f} ¥\n"
            f"💳 Способ: {method_text}\n"
            f"📌 Статус: {status_text}",
            parse_mode="HTML"
        )
    else:
        bot.send_message(msg.chat.id, "📭 У вас нет активных заявок.")


@bot.message_handler(func=lambda m: m.text == "💬 Поддержка")
def support(msg):
    bot.send_message(msg.chat.id,
        "💬 <b>Поддержка</b>\n\n"
        "Напишите сообщение в этот чат — менеджер ответит.\n\n"
        "⏰ Работаем: 24/7",
        parse_mode="HTML"
    )


# ============ MANAGER ============

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
    
    db.set_state(call.from_user.id, "mgr_chat", str(order_id))
    
    status = {"new": "🆕 Новая", "awaiting": "📝 Ждём реквизиты", "in_progress": "🔄 В работе"}.get(order["status"], order["status"])
    method = {"alipay": "Alipay", "wechat": "WeChat", "card": "Карта"}.get(order.get("method"), "—")
    
    bot.edit_message_text(
        f"📋 <b>Заявка {order['order_number']}</b>\n\n"
        f"👤 {order.get('first_name', 'Клиент')}\n"
        f"📱 {order.get('phone', 'нет')}\n"
        f"💬 @{order.get('username', 'нет')}\n\n"
        f"💵 {order['rub_amount']:,.0f} ₽ → {order['cny_amount']:,.2f} ¥\n"
        f"💳 Способ: {method}\n"
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
    
    # Обновляем
    db.set_state(call.from_user.id, "mgr_chat", str(order_id))
    status = {"new": "🆕 Новая", "awaiting": "📝 Ждём реквизиты", "in_progress": "🔄 В работе"}.get(order["status"], order["status"])
    method = {"alipay": "Alipay", "wechat": "WeChat", "card": "Карта"}.get(order.get("method"), "—")
    
    bot.edit_message_text(
        f"📋 <b>Заявка {order['order_number']}</b>\n\n"
        f"👤 {order.get('first_name', 'Клиент')}\n"
        f"📱 {order.get('phone', 'нет')}\n"
        f"💬 @{order.get('username', 'нет')}\n\n"
        f"💵 {order['rub_amount']:,.0f} ₽ → {order['cny_amount']:,.2f} ¥\n"
        f"💳 Способ: {method}\n"
        f"📌 Статус: {status}\n\n"
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
    
    bot.edit_message_text(f"✅ Заявка {order['order_number']} выполнена!", call.message.chat.id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id, "Готово!")


@bot.callback_query_handler(func=lambda c: c.data.startswith("mgr:cancel:"))
def mgr_cancel(call):
    if not is_manager(call.from_user.id):
        return
    
    order_id = int(call.data.split(":")[2])
    db.update_order(order_id, status="cancelled")
    order = db.get_order(order_id)
    db.clear_state(call.from_user.id)
    
    bot.send_message(order["user_id"], f"❌ Заявка {order['order_number']} отменена.", parse_mode="HTML")
    bot.edit_message_text(f"❌ Заявка {order['order_number']} отменена.", call.message.chat.id, call.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(call.id)


# ============ MESSAGE RELAY ============

@bot.message_handler(content_types=['text', 'photo', 'document'])
def relay(msg):
    # Пропускаем кнопки меню
    if msg.text in ["📋 Мои заявки", "💬 Поддержка", "👨‍💼 Панель менеджера", "💱 Обменять валюту"]:
        return
    
    user_id = msg.from_user.id
    state, data = db.get_state(user_id)
    
    # Менеджер пишет клиенту
    if is_manager(user_id) and state == "mgr_chat" and data:
        order = db.get_order(int(data))
        if order:
            try:
                if msg.photo:
                    bot.send_photo(order["user_id"], msg.photo[-1].file_id, caption=f"👨‍💼 <b>Менеджер:</b>\n{msg.caption or ''}", parse_mode="HTML")
                elif msg.document:
                    bot.send_document(order["user_id"], msg.document.file_id, caption=f"👨‍💼 <b>Менеджер:</b>\n{msg.caption or ''}", parse_mode="HTML")
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
                bot.send_photo(order["manager_id"], msg.photo[-1].file_id, caption=header + (msg.caption or ""), parse_mode="HTML")
            elif msg.document:
                bot.send_document(order["manager_id"], msg.document.file_id, caption=header + (msg.caption or ""), parse_mode="HTML")
            else:
                bot.send_message(order["manager_id"], header + msg.text, parse_mode="HTML")
            bot.send_message(msg.chat.id, "✅ Сообщение отправлено менеджеру")
        except:
            bot.send_message(msg.chat.id, "⏳ Менеджер получит ваше сообщение")
    elif order:
        for mgr in get_all_manager_ids():
            try:
                bot.send_message(mgr, f"💬 Новое сообщение в заявке #{order['order_number']}")
            except:
                pass
        bot.send_message(msg.chat.id, "✅ Сообщение получено. Менеджер скоро ответит.")
    else:
        bot.send_message(msg.chat.id, "💬 Создайте заявку, чтобы связаться с менеджером.", reply_markup=main_kb(user_id))


if __name__ == "__main__":
    print("Bot started...")
    bot.infinity_polling()
