import logging
import requests
import random
import re
import json
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(self):
        "Инициализация клиента OpenRouter"
        self.api_key = Config.OPENROUTER_API_KEY
        self.model = Config.LLM_MODEL
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8080",
            "X-Title": "Sales Manager Simulator"
        }

        if not self.api_key:
            print("\nНет ключа\n")
            self.working = False
        else:
            print(f"\nКлюч загружен, модель: {self.model}\n")
            self.working = True

        # Статистика использования
        self.stats = {
            'api_success': 0,
            'fallback_used': 0,
            'api_errors': 0
        }

    def evaluate_answer(self, client_type, objection, answer):
        "Оценивает ответ менеджера на возражение"

        if not self.working:
            self.stats['fallback_used'] += 1
            result = self._get_fallback_evaluation(client_type, objection, answer)
            result['from_fallback'] = True
            return result

        try:
            client_info = Config.CLIENT_TYPES.get(client_type, {})
            client_name = client_info.get('name', 'Клиент')

            #ПРОМПТ с примерами
            prompt = f"""Ты - тренер по продажам. Твоя задача - дать обратную связь менеджеру.

Клиент: {client_name}
Возражение: "{objection}"
Ответ менеджера: "{answer}"

ПРИМЕР хорошей обратной связи:
"Эмпатия: 7/10 - есть понимание, но можно теплее. 
Аргументация: 8/10 - убедительные доводы. 
Работа с возражением: 6/10 - не до конца отработал. 
Тон: 9/10 - спокойный и уверенный.

Что удалось: хороший контакт с клиентом, четкая структура ответа.
Что улучшить: добавить больше вопросов, привести конкретный пример.
Совет: спроси клиента 'Что именно вызывает сомнения?' - это поможет точнее попасть в возражение."

Твой ответ (только обратная связь, без пояснений и рассуждений):"""

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system",
                     "content": "Ты тренер по продажам. Отвечаешь только обратной связью, без лишних слов."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 400
            }



            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=data,
                timeout=15
            )

            if response.status_code == 200:
                result = response.json()

                raw_response = None
                if 'choices' in result and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    if 'message' in choice:
                        msg = choice['message']
                        #берем content
                        if 'content' in msg and msg['content']:
                            raw_response = msg['content']
                        #берем последнюю часть reasoning
                        elif 'reasoning' in msg and msg['reasoning']:
                            reasoning = msg['reasoning']
                            #берем последние 400 символов reasoning
                            raw_response = reasoning[-400:] if len(reasoning) > 400 else reasoning

                if raw_response:
                    #очищаем ответ от рассуждений
                    cleaned = self._clean_feedback(raw_response)

                    #парсим оценки
                    scores = self._extract_scores(cleaned)

                    #извлекаем плюсы и минусы
                    good_points = self._extract_points(cleaned, keywords=['удалось', 'хорошо', 'плюс'])
                    improvements = self._extract_points(cleaned, keywords=['улучшить', 'минус', 'не хватает', 'плохо',
                                                                           'стоит поработать'])

                    #извлекаем совет
                    advice = self._extract_advice(cleaned)

                    #формируем фидбек
                    feedback = cleaned
                    if advice and advice not in cleaned:
                        feedback += f"\n\nСовет: {advice}"

                    self.stats['api_success'] += 1
                    return {
                        "scores": scores,
                        "total": sum(scores.values()) // 4,
                        "feedback": feedback,
                        "good_points": good_points if good_points else ["Есть положительные моменты"],
                        "improvements": improvements if improvements else ["Можно расти дальше"],
                        "from_fallback": False
                    }

            #если не получили ответ
            self.stats['api_errors'] += 1
            self.stats['fallback_used'] += 1
            result = self._get_fallback_evaluation(client_type, objection, answer)
            result['from_fallback'] = True
            return result

        except Exception as e:
            print(f"\nОшибка при оценке: {e}")
            self.stats['api_errors'] += 1
            self.stats['fallback_used'] += 1
            result = self._get_fallback_evaluation(client_type, objection, answer)
            result['from_fallback'] = True
            return result

    def _clean_feedback(self, text):
        """Очищает фидбек от рассуждений модели"""
        # Убираем фразы-рассуждения
        patterns = [
            r'Хм,.*?\.',
            r'Пользователь.*?\.',
            r'Мне нужно.*?\.',
            r'Я должен.*?\.',
            r'Как тренер.*?\.',
            r'Давай.*?\.',
            r'Нужно разобрать.*?\.',
            r'Рассмотрим.*?\.',
            r'^[А-Я][а-я]+.*?\?',  # Вопросительные предложения в начале
            r'^Давайте.*?\.',
        ]

        cleaned = text
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

        #разбиваем на строки и убираем пустые
        lines = [line.strip() for line in cleaned.split('\n') if line.strip()]

        #убираем строки рассуждений
        filtered_lines = []
        reasoning_phrases = ['нужно оценить', 'рассмотрим', 'проанализируем', 'во-первых', 'во-вторых']

        for line in lines:
            if not any(phrase in line.lower() for phrase in reasoning_phrases):
                filtered_lines.append(line)

        return '\n'.join(filtered_lines) if filtered_lines else text

    def _extract_scores(self, text):
        "Извлекает оценки из текста"
        scores = {
            "empathy": 7,
            "arguments": 7,
            "objection_handling": 7,
            "tone": 7
        }

        # Ищем числа от 1 до 10 рядом с ключевыми словами
        patterns = [
            (r'эмпати[июе][^\\d]*(\\d+)', 'empathy'),
            (r'эмпати[июе].*?(\\d+)[^\\d]*', 'empathy'),
            (r'аргумент\\w*[^\\d]*(\\d+)', 'arguments'),
            (r'аргумент\\w*.*?(\\d+)[^\\d]*', 'arguments'),
            (r'работ[ау]\\s+с\\s+возраж\\w*[^\\d]*(\\d+)', 'objection_handling'),
            (r'работ[ау].*?возраж.*?(\\d+)', 'objection_handling'),
            (r'по возражению.*?(\\d+)', 'objection_handling'),
            (r'тон[^\\d]*(\\d+)', 'tone'),
            (r'тон.*?(\\d+)[^\\d]*', 'tone'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        scores[key] = score
                except:
                    pass

        return scores

    def _extract_points(self, text, keywords):
        "Извлекает пункты из текста по ключевым словам"
        points = []
        lines = text.split('\n')

        capture = False
        current_points = []

        for i, line in enumerate(lines):
            line_lower = line.lower()

            #Проверяем на новый блок
            if any(keyword in line_lower for keyword in keywords):
                capture = True
                current_points = []
                #Текст прсое двоеточия
                if ':' in line:
                    after_colon = line.split(':', 1)[1].strip()
                    if after_colon and len(after_colon) > 5:
                        #Разюиваем по запятым
                        parts = after_colon.split(',')
                        for part in parts[:2]:
                            part = part.strip()
                            if part and len(part) > 5:
                                current_points.append(part)
                continue


            if capture:
                #ищем маркеры списка
                marker_match = re.match(r'^\s*[•\-*\d.)]\s*(.+)', line)
                if marker_match:
                    point = marker_match.group(1).strip()
                    if point and len(point) > 5 and point not in current_points:
                        current_points.append(point)
                #если строка пустая или начинается с новой темы - выходим
                elif not line.strip() or any(kw in line_lower for kw in ['эмпати', 'аргумент', 'тон', 'оценк']):
                    if current_points:
                        points.extend(current_points[:2])
                        capture = False
                #если это продолжение предыдущего пункта
                elif current_points and line.strip():
                    current_points[-1] += ' ' + line.strip()

        #последний блок если есть
        if current_points:
            points.extend(current_points[:2])

        #очищаем пункты
        cleaned_points = []
        for point in points[:2]:
            point = re.sub(r'^(что удалось|что улучшить|совет)[:\s]*', '', point, flags=re.IGNORECASE)
            point = point.strip()
            if point and len(point) > 5:
                cleaned_points.append(point)

        return cleaned_points

    def _extract_advice(self, text):
        "Извлекает совет из текста"
        lines = text.split('\n')

        #ищем строки с советом
        for line in lines:
            if re.search(r'совет|рекомендац|попробуй|используй', line.lower()):
                #убираем "Совет:" и подобное
                advice = re.sub(r'^(совет|рекомендация)[:\s]*', '', line, flags=re.IGNORECASE)
                advice = advice.strip()
                if advice and len(advice) > 10:
                    return advice

        #ищем в конце текста
        sentences = text.split('.')
        for sentence in reversed(sentences):
            if len(sentence.strip()) > 20 and any(
                    word in sentence.lower() for word in ['спроси', 'скажи', 'используй', 'попробуй', 'добавь']):
                return sentence.strip() + '.'

        return None

    def generate_tip(self, client_type):
        "Генерирует совет по работе с конкретным типом клиента"

        if not self.working:
            return self._get_fallback_tip(client_type), True

        try:
            client_info = Config.CLIENT_TYPES.get(client_type, {})
            client_name = client_info.get('name', 'Клиент')

            #промпт с примером
            prompt = f"""Дай один короткий совет менеджеру для работы с {client_name}.

ПРИМЕРЫ правильных советов:
- Для скептика: "Спроси клиента: 'Какие именно сомнения у вас возникают?' - это поможет понять его реальные опасения"
- Для занятого: "Начни разговор с фразы 'Я понимаю, что вы заняты, поэтому скажу главное за 30 секунд'"
- Для экономного: "Сделай акцент не на цене, а на выгоде: 'Это сэкономит вам X рублей в месяц'"
- Для агрессивного: "На грубость отвечай спокойно: 'Я вижу, вы расстроены, давайте разберемся'"

Твой совет (только одна фраза, без пояснений):"""

            data = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8,
                "max_tokens": 100
            }

            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()

                if 'choices' in result and len(result['choices']) > 0:
                    choice = result['choices'][0]
                    if 'message' in choice:
                        msg = choice['message']
                        if 'content' in msg and msg['content']:
                            tip = msg['content'].strip()

                            tip = re.sub(r'^(совет|рекомендация)[:\s]*', '', tip, flags=re.IGNORECASE)
                            return tip, False
                        elif 'reasoning' in msg and msg['reasoning']:

                            reasoning = msg['reasoning']
                            #ием фразу в кавычках или после двоеточия
                            quote_match = re.search(r'"([^"]+)"', reasoning)
                            if quote_match:
                                return quote_match.group(1), False
                            #ищщем последнее предложение
                            sentences = reasoning.split('.')
                            for s in reversed(sentences):
                                if len(s.strip()) > 20:
                                    return s.strip() + '.', False

            return self._get_fallback_tip(client_type), True

        except Exception as e:
            print(f"\nОшибка при генерации совета: {e}")
            return self._get_fallback_tip(client_type), True

    def _get_fallback_tip(self, client_type):
        """Запасные советы с вариациями"""
        tips = {
            'skeptic': [
                "Спроси: 'Какие доказательства были бы для вас убедительны?'",
                "Приведи конкретный кейс из похожей компании",
                "Используй фразу: 'Давайте я покажу расчёт окупаемости'",
                "Предложи: 'Можем сделать пилотный проект'",
                "Спроси: 'Что именно вызывает сомнения?'"
            ],
            'busy': [
                "Начни с: 'Я буду краток, ровно 2 минуты'",
                "Сразу скажи главную выгоду в одном предложении",
                "Спроси: 'Когда вам удобнее созвониться?'",
                "Используй фразу: 'Отправлю краткую презентацию на почту'",
                "Говори: 'По сути, наше предложение поможет вам...'"
            ],
            'economical': [
                "Сделай акцент на: 'Это окупится за месяц'",
                "Спроси: 'Что для вас дороже - цена или отсутствие результата?'",
                "Предложи: 'Давайте посчитаем потенциальную выгоду'",
                "Скажи: 'У нас есть гибкая система скидок'",
                "Подчеркни: 'В долгосрочной перспективе это выгоднее'"
            ],
            'aggressive': [
                "Сохраняй спокойствие: 'Я слышу ваше недовольство'",
                "Дай выговориться, не перебивай",
                "Скажи: 'Понимаю вашу реакцию, давайте разберемся'",
                "Используй технику 'Я-сообщения'",
                "Предложи: 'Расскажите, что именно вас не устраивает'"
            ]
        }
        return random.choice(tips.get(client_type, ["Будь внимателен к клиенту"]))

    def _get_fallback_evaluation(self, client_type=None, objection=None, answer=None):
        "Запасной вариант оценки"

        answer_lower = answer.lower() if answer else ""

        #aнализируем ответ
        has_question = "?" in answer
        word_count = len(answer.split())

        #генерируем случайные оценки
        empathy_score = random.randint(5, 9)
        args_score = random.randint(5, 9)
        objection_score = random.randint(5, 9)
        tone_score = random.randint(6, 10)

        if has_question:
            empathy_score = min(10, empathy_score + 1)
            objection_score = min(10, objection_score + 1)

        if word_count < 10:
            args_score = max(4, args_score - 1)

        scores = {
            "empathy": empathy_score,
            "arguments": args_score,
            "objection_handling": objection_score,
            "tone": tone_score
        }

        #база для разных ответов
        feedback_templates = [
            f"""Эмпатия: {scores['empathy']}/10 - {'хорошо чувствуешь клиента' if scores['empathy'] > 7 else 'можно теплее'}.
Аргументация: {scores['arguments']}/10 - {'убедительно' if scores['arguments'] > 7 else 'не хватает фактов'}.
Работа с возражением: {scores['objection_handling']}/10 - {'попал в точку' if scores['objection_handling'] > 7 else 'можно глубже'}.
Тон: {scores['tone']}/10 - {'спокойный и уверенный' if scores['tone'] > 7 else 'профессиональный'}.""",

            f"""По шкале от 1 до 10:
• Эмпатия: {scores['empathy']} - {'есть понимание' if scores['empathy'] > 7 else 'можно проявить больше участия'}
• Аргументы: {scores['arguments']} - {'логично и убедительно' if scores['arguments'] > 7 else 'стоит добавить конкретики'}
• Работа с возражением: {scores['objection_handling']} - {'хорошо отработал' if scores['objection_handling'] > 7 else 'не до конца раскрыл'}
• Тон: {scores['tone']} - {'отличный' if scores['tone'] > 8 else 'подходящий'}""",

            f"""Оценка ответа:
Эмпатия: {scores['empathy']}/10 - {'клиент чувствует внимание' if scores['empathy'] > 7 else 'может быть теплее'}
Аргументация: {scores['arguments']}/10 - {'убедительные доводы' if scores['arguments'] > 7 else 'можно сильнее'}
По возражению: {scores['objection_handling']}/10 - {'точно в цель' if scores['objection_handling'] > 7 else 'хороший заход'}
Тон общения: {scores['tone']}/10 - {'профессионально' if scores['tone'] > 7 else 'уверенно'}"""
        ]

        #плюсы
        good_pools = [
            ["Четкая структура ответа", "Спокойный тон"],
            ["Хороший контакт с клиентом", "Убедительные аргументы"],
            ["Задал уточняющие вопросы", "Проявил эмпатию"],
            ["Кратко и по делу", "Использует факты"],
            ["Не поддается на провокации", "Держится уверенно"],
        ]

        #минусы
        improve_pools = [
            ["Можно больше эмпатии", "Добавить конкретных примеров"],
            ["Слишком общие фразы", "Мало вопросов к клиенту"],
            ["Не хватает цифр", "Упустил возможность уточнить"],
            ["Спешит с ответом", "Перебивает клиента"],
            ["Тон мог бы быть мягче", "Глубже проработать возражение"],
        ]

        #советы
        advice_pool = [
            f"Спроси клиента: '{random.choice(['Что именно вызывает сомнения?', 'Какой опыт у вас был раньше?', 'Что для вас самое важное?'])}'",
            f"Используй фразу: '{random.choice(['Давайте посмотрим на цифры', 'Я понимаю ваши опасения', 'Расскажите подробнее'])}'",
            f"Добавь конкретики: приведи пример из практики",
            f"Покажи выгоду: объясни долгосрочную перспективу",
        ]

        #фидбек
        feedback = random.choice(feedback_templates)
        good = random.choice(good_pools)
        improve = random.choice(improve_pools)
        advice = random.choice(advice_pool)

        feedback += f"\n\nЧто удалось: {good[0]}, {good[1]}"
        feedback += f"\nЧто улучшить: {improve[0]}, {improve[1]}"
        feedback += f"\nСовет: {advice}"

        return {
            "scores": scores,
            "total": sum(scores.values()) // 4,
            "feedback": feedback,
            "good_points": good,
            "improvements": improve
        }

    def get_stats(self):
        "Возвращает статистику использования"
        total = self.stats['api_success'] + self.stats['fallback_used']
        if total == 0:
            return "Пока нет данных"

        api_percent = (self.stats['api_success'] / total) * 100
        fallback_percent = (self.stats['fallback_used'] / total) * 100
        error_percent = (self.stats['api_errors'] / total) * 100 if total > 0 else 0

        return (f"Успешных API-запросов: {self.stats['api_success']} ({api_percent:.1f}%)\n"
                f"⚠Fallback-ответов: {self.stats['fallback_used']} ({fallback_percent:.1f}%)\n"
                f"Ошибок API: {self.stats['api_errors']} ({error_percent:.1f}%)")


llm_client = OpenRouterClient()