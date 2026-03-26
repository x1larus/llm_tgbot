from dotenv import load_dotenv 
import os 
import telebot
import cherrypy
load_dotenv()

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))

user_sessions_dict = dict()

client_types = {
    'Скептик (всё отрицает, просит доказательства)': 'skeptic',
    'Занятой (вечно спешит, нет времени)': 'busy',
    'Экономный (считает каждую копейку)': 'economical',
    'Агрессивный (грубит и хамит)': 'aggressive'
}

def initializeWebhookServer():
    bot.remove_webhook()
    bot.set_webhook(url=os.getenv("WEBHOOK_URL_BASE") + os.getenv("WEBHOOK_URL_PATH"),
                certificate=open(os.getenv("WEBHOOK_SSL_CERT"), 'r'))
    cherrypy.config.update({
        'server.socket_host': os.getenv("WEBHOOK_LISTEN"),
        'server.socket_port': int(os.getenv("WEBHOOK_PORT")),
        'server.ssl_module': 'builtin',
        'server.ssl_certificate': os.getenv("WEBHOOK_SSL_CERT"),
        'server.ssl_private_key': os.getenv("WEBHOOK_SSL_PRIV")
    })
    cherrypy.quickstart(WebhookServer(), os.getenv("WEBHOOK_URL_PATH"), {'/': {}})

class WebhookServer(object):
    @cherrypy.expose
    def index(self):
        if 'content-length' in cherrypy.request.headers and \
                        'content-type' in cherrypy.request.headers and \
                        cherrypy.request.headers['content-type'] == 'application/json':
            length = int(cherrypy.request.headers['content-length'])
            json_string = cherrypy.request.body.read(length).decode("utf-8")
            update = telebot.types.Update.de_json(json_string)
            
            bot.process_new_updates([update])
            return ''
        else:
            raise cherrypy.HTTPError(403)

class Config:
    # OpenRouter API
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    if not OPENROUTER_API_KEY:
        print("ВНИМАНИЕ: Не найден OPENROUTER_API_KEY!")
        print("Получи ключ на openrouter.ai и добавь в .env")

    LLM_MODEL = "stepfun/step-3.5-flash:free"
    #LLM_MODEL = "qwen/qwen-2.5-7b-instruct:free"
    # LLM_MODEL = "arcee-ai/trinity-large-preview:free"
    # LLM_MODEL = "meta-llama/llama-3.3-70b:free"
    # LLM_MODEL = "mistralai/mistral-small-3.1-24b:free"

    # LLM_MODEL = "openrouter/free"

    #типы клиентов
    CLIENT_TYPES = {
        'skeptic': {
            'name': 'Скептик',
            'description': 'Сомневается во всём, требует доказательств'
        },
        'busy': {
            'name': 'Занятой',
            'description': 'Вечно спешит, не любит долгих разговоров'
        },
        'economical': {
            'name': 'Экономный',
            'description': 'Считает деньги, ищет выгоду'
        },
        'aggressive': {
            'name': 'Агрессивный',
            'description': 'Грубит, не даёт слова вставить'
        }
    }

    #Пул готовых возражений
    OBJECTIONS_POOL = {
        'skeptic': [
            "Звучит слишком хорошо, чтобы быть правдой",
            "А есть реальные отзывы?",
            "Докажите, что это работает",
            "Почему я должен вам верить?",
            "Это какой-то развод",
            "Сколько уже таких обещаний было",
            "А если не сработает?",
            "Покажите кейсы",
            "Кто-то из наших конкурентов пользуется?",
            "Слишком рискованно"
        ],
        'busy': [
            "У меня нет времени",
            "Говорите короче",
            "Пришлите на почту, почитаю",
            "Я очень занят, давайте быстро",
            "Время - деньги, что конкретно?",
            "У меня ровно минута",
            "Ближе к делу",
            "Без воды, пожалуйста",
            "Я опаздываю на встречу",
            "Кратко: что, сколько, зачем?"
        ],
        'economical': [
            "Дороговато",
            "А дешевле есть?",
            "Скидку дадите?",
            "Не входит в бюджет",
            "У конкурентов дешевле",
            "За что такие деньги?",
            "А можно подешевле?",
            "Давайте торговаться",
            "Не готов столько платить",
            "А если возьму оптом, цена изменится?"
        ],
        'aggressive': [
            "Отстаньте!",
            "Я ничего не буду покупать!",
            "Хватит названивать!",
            "Вы мне надоели уже!",
            "Прекратите меня доставать!",
            "Я сказал - нет!",
            "Руки прочь от моего кошелька!",
            "Убирайтесь!",
            "Надоели эти продажники!",
            "Я позвоню в полицию!"
        ]
    }

    MAX_DIALOGUE_LENGTH = 20