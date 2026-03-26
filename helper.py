from telebot.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
import config

def print_header(text):
    "Печатает заголовок с рамкой"
    res = ''
    res += "\n" + "-" * 10 + '\n'
    res += f" {text}" + '\n'
    res += "-" * 10 + '\n'
    return res

def returnToMenuMarkup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn = KeyboardButton('Вернуться в меню')
    markup.row(btn)
    return markup

def menuMarkup():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    for x in config.client_types:
        btn = KeyboardButton(x)
        markup.row(btn)
    return markup