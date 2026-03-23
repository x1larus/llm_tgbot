import telebot
import helper
import config

@config.bot.message_handler(content_types=["text"])
def repeat_all_messages(message : telebot.types.Message): # Название функции не играет никакой роли
    helper.log_msg(message)
    config.bot.send_message(message.chat.id, message.text)

@config.bot.message_handler(func=lambda message: True, content_types=['text'])
def echo_message(message):
    config.bot.reply_to(message, message.text)

if __name__ == '__main__':
    config.initializeWebhookServer()
    #config.bot.infinity_polling()