import config
import telebot
import llmClient
import helper
from objectionTrainer import ObjectionTrainer

@config.bot.message_handler(commands=['start'])
def start(message : telebot.types.Message):
    config.bot.send_message(message.chat.id, "Выберите тип клиента:", reply_markup=helper.menuMarkup())

@config.bot.message_handler(content_types=['text'])
def get_text_messages(message: telebot.types.Message):
    client_data = getClientData(message.chat.id)
    answer = ''

    if message.text == 'Вернуться в меню':
        client_data = deleteLlmTrainer(message.chat.id)
        answer = 'Сессия завершена!\nВыберите тип клиента'
        config.bot.send_message(message.chat.id, answer, reply_markup=helper.menuMarkup())
        return
    
    if message.text in config.client_types.keys():
        client_type = config.client_types[message.text]
        client_name = config.Config.CLIENT_TYPES[client_type]['name']
        client_data = createLlmTrainer(message.chat.id)
        client_data[1].start_training(client_type)
        client_data[4] = client_type
        answer += helper.print_header(f"Общение с {client_name.upper()}")

    # in training
    if client_data[2] == True:
        if client_data[3] == True: # Wait for response
            client_data[1].add_answer(message.text)
            config.bot.send_message(message.chat.id, "Анализируем ответ...", reply_markup=helper.returnToMenuMarkup())
            evaluation = client_data[0].evaluate_answer(client_data[4], client_data[5], message.text)
            if evaluation.get('from_fallback', True):
                answer += "Оценка(базовый анализ):\n"
            else:
                answer += "Оценка(ЛЛМ):\n"
            
            answer += f"\nКомментарий:\n"
            answer += f"{evaluation['feedback']}\n"

            if evaluation['good_points']:
                answer += f"\nЧто получилось:\n"
                for point in evaluation['good_points']:
                    answer += f"  • {point}\n"

            if evaluation['improvements']:
                answer += f"\nИсправить:\n"
                for imp in evaluation['improvements']:
                    answer += f"  • {imp}\n"

            progress = client_data[1].get_progress()
            if progress['completed'] >= progress['total']:
                answer += "\nВы отработали все возражения!\nВыберите тип клиента:"
                client_data = deleteLlmTrainer(message.chat.id)
                config.bot.send_message(message.chat.id, answer, reply_markup=helper.menuMarkup())
                return

            client_data[1].get_next_objection()
            config.bot.send_message(message.chat.id, answer, reply_markup=helper.returnToMenuMarkup())

        progress = client_data[1].get_progress()
        answer = f"\nПрогресс: {progress['completed']}/{progress['total']} ({progress['percent']}%)\n"
        tip, is_fallback_tip = client_data[0].generate_tip(client_data[4])
        if is_fallback_tip:
            answer += f"\n💡 Совет (из базы): {tip}\n"
        else:
            answer += f"\n💡 Совет (ЛЛМ): {tip}\n"

        #Возражение
        objection = client_data[1].current_objection
        answer += f"\nКлиент: \"{objection}\"\n"
        client_data[3] = True
        client_data[5] = objection
        config.bot.send_message(message.chat.id, answer, reply_markup=helper.returnToMenuMarkup())

# llm, trainer, created, isWaitAnswer, client_type, objection

def getClientData(id):
    if id not in config.user_sessions_dict:
        config.user_sessions_dict[id] = [None, None, False, False, None, None]
    return config.user_sessions_dict[id]

def createLlmTrainer(id):
    llm = llmClient.OpenRouterClient()
    trainer = ObjectionTrainer(llm)
    config.user_sessions_dict[id] = [llm, trainer, True, False, None, None]
    return config.user_sessions_dict[id]

def deleteLlmTrainer(id):
    config.user_sessions_dict[id] = [None, None, False, False, None, None]
    return config.user_sessions_dict[id]