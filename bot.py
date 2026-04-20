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


def contact_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton('Поделиться контактом', request_contact=True))
    return kb


def main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton('Обменять валюту'))
    kb.row(types.KeyboardButton('Мои заявки'), types.KeyboardButton('Поддержка'))
    if is_manager(user_id):
        kb.add(types.KeyboardButton('Панель менеджера'))
    return kb


def buy_currency_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('Китайский юань (CNY)', callback_data='buy:cny'))
    kb.add(types.InlineKeyboardButton('Отмена', callback_data='cancel'))
    return kb


def pay_currency_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('Российский рубль (RUB)', callback_data='pay:rub'))
    kb.add(types.InlineKeyboardButton('Отмена', callback_data='cancel'))
    return kb


def confirm_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton('Продолжить', callback_data='confirm:yes'),
        types.InlineKeyboardButton('Отмена', callback_data='confirm:no')
    )
    return kb


def method_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton('Alipay', callback_data='method:alipay'),
        types.InlineKeyboardButton('WeChat', callback_data='method:wechat'),
        types.InlineKeyboardButton('Банковская карта', callback_data='method:card')
    )
    return kb


def manager_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton('Новые заявки', callback_data='mgr:new'),
        types.InlineKeyboardButton('Все активные', callback_data='mgr:active'),
        types.InlineKeyboardButton('Обновить', callback_data='mgr:refresh')
    )
    return kb


def orders_kb(orders):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for o in orders[:10]:
        status = {'new': 'NEW', 'in_progress': 'WORK'}.get(o['status'], '?')
        name = (o.get('first_name') or 'Client')[:12]
        text = status + ' #' + o['order_number'][-4:] + ' ' + name + ' ' + str(int(o['cny_amount'])) + 'Y'
        kb.add(types.InlineKeyboardButton(text, callback_data='mgr:order:' + str(o['id'])))
    kb.add(types.InlineKeyboardButton('Назад', callback_data='mgr:menu'))
    return kb


def order_kb(order):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if order['status'] == 'new':
        kb.add(types.InlineKeyboardButton('Взять', callback_data='mgr:take:' + str(order['id'])))
    if order['status'] not in ('completed', 'cancelled', 'closed'):
        kb.row(
            types.InlineKeyboardButton('Выполнено', callback_data='mgr:done:' + str(order['id'])),
            types.InlineKeyboardButton('Закрыть', callback_data='mgr:close:' + str(order['id']))
        )
    kb.add(types.InlineKeyboardButton('К заявкам', callback_data='mgr:active'))
    return kb


@bot.message_handler(commands=['addmanager'])
def cmd_addmanager(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split()
    if len(parts) < 2:
        bot.send_message(msg.chat.id, 'Использование: /addmanager user_id')
        return
    try:
        user_id = int(parts[1])
        db.add_manager(user_id)
        bot.send_message(msg.chat.id, 'Менеджер ' + str(user_id) + ' добавлен!')
    except ValueError:
        bot.send_message(msg.chat.id, 'ID должен быть числом')


@bot.message_handler(commands=['delmanager'])
def cmd_delmanager(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split()
    if len(parts) < 2:
        bot.send_message(msg.chat.id, 'Использование: /delmanager user_id')
        return
    try:
        user_id = int(parts[1])
        if db.remove_manager(user_id):
            bot.send_message(msg.chat.id, 'Менеджер ' + str(user_id) + ' удален!')
        else:
            bot.send_message(msg.chat.id, 'Менеджер ' + str(user_id) + ' не найден')
    except ValueError:
        bot.send_message(msg.chat.id, 'ID должен быть числом')


@bot.message_handler(commands=['managers'])
def cmd_managers(msg):
    if msg.from_user.id != OWNER_ID:
        return
    managers = db.get_managers()
    if not managers:
        bot.send_message(msg.chat.id, 'Менеджеров нет (кроме вас)')
        return
    text = '<b>Менеджеры:</b>\n\n'
    for m in managers:
        username = '@' + m['username'] if m.get('username') else 'нет username'
        text = text + str(m['user_id']) + ' (' + username + ')\n'
    bot.send_message(msg.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['setrates'])
def cmd_setrates(msg):
    if msg.from_user.id != OWNER_ID:
        return
    parts = msg.text.split()
    if len(parts) < 7:
        rates = db.get_rates()
        text = '<b>Текущие курсы (1 CNY = X RUB):</b>\n\n'
        text = text + '1-100: ' + str(rates.get('1-100', 19.29)) + '\n'
        text = text + '101-500: ' + str(rates.get('101-500', 12.57)) + '\n'
        text = text + '501-1000: ' + str(rates.get('501-1000', 12.38)) + '\n'
        text = text + '1001-5000: ' + str(rates.get('1001-5000', 12.17)) + '\n'
        text = text + '5001-20000: ' + str(rates.get('5001-20000', 12.13)) + '\n'
        text = text + '20001+: ' + str(rates.get('20001+', 12.06)) + '\n\n'
        text = text + '<b>Изменить:</b>\n/setrates 19.29 12​​​​​​​​​​​​​​​​
