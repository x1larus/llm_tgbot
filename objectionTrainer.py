import random
import logging
from datetime import datetime
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ObjectionTrainer:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.current_objection = None
        self.client_type = None
        self.history = []

    def start_training(self, client_type):
        "Начинает тренировку с выбранным типом клиента"
        self.client_type = client_type
        self.history = []
        return self.get_next_objection()

    def get_next_objection(self):
        "Получает следующее возражение из пула"
        from config import Config

        pool = Config.OBJECTIONS_POOL.get(self.client_type, [])
        if not pool:
            pool = ["Расскажите о вашем предложении"]

        #выбираем случайное возражение
        used_objections = [item['objection'] for item in self.history]
        available = [o for o in pool if o not in used_objections]

        if not available:
            available = pool

        self.current_objection = random.choice(available)
        return self.current_objection

    def add_answer(self, answer):
        "Добавляет ответ менеджера в историю"
        if self.current_objection:
            self.history.append({
                'objection': self.current_objection,
                'answer': answer,
                'timestamp': datetime.now()
            })

    def get_progress(self):
        "Возвращает прогресс тренировки"
        total = len(Config.OBJECTIONS_POOL.get(self.client_type, []))
        completed = len(self.history)
        return {
            'total': total,
            'completed': completed,
            'percent': int(completed / total * 100) if total > 0 else 0
        }