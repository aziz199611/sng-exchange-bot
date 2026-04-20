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
    kb.add(types.KeyboardButton('Podelitsya kontaktom', request_contact=True))
    return kb


def main_kb(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton('Obmenyat valyutu'))
    kb.row(types.KeyboardButton('Moi zayavki'), types.KeyboardButton('Podderzhka'))
    if is_manager(user_id):
        kb.add(types.KeyboardButton('Panel menedzhera'))
    return kb


def buy_currency_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('Kitayskiy yuan (CNY)', callback_data='buy:cny'))
    kb.add(types.InlineKeyboardButton('Otmena', callback_data='cancel'))
    return kb


def pay_currency_kb():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('Rossiyskiy rubl (RUB)', callback_data='pay:rub'))
    kb.add(types.InlineKeyboardButton('Otmena', callback_data='cancel'))
    return kb


def confirm_kb():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton('Prodolzhit', callback_data='confirm:yes'),
        types.InlineKeyboardButton('Otmena', callback_data='confirm:no')
    )
    return kb


def method_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton('Alipay', callback_data='method:alipay'),
        types.InlineKeyboardButton('WeChat', callback_data='method:wechat'),
        types.InlineKeyboardButton('Bankovskaya karta', callback_data='method:card')
    )
    return kb


def manager_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton('Novye zayavki', callback_data='mgr:new'),
        types.InlineKeyboardButton('Vse aktivnye', callback_data='mgr:active'),
        types.InlineKeyboardButton('Obnovit', callback_data='mgr:refresh')
    )
    return kb


def orders_kb(orders):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for o in orders[:10]:
        status =​​​​​​​​​​​​​​​​
