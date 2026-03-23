from datetime import datetime
import telebot

def log_msg(message: telebot.types.Message):
    time = datetime.fromtimestamp(message.date)
    timeStr = f'{time.hour}:{time.minute}:{time.second}'
    print(f'[{message.chat.username}][{timeStr}]: {message.text}')