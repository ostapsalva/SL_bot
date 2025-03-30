from flask import Flask, request, jsonify
import telebot
import requests
import logging
from langdetect import detect

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = "7329116708:AAFsLQoXLZo1tMfHqyrtLmDrvoFnmvA1RR8"  # Замените на реальный токен
BITRIX_WEBHOOK_URL = "https://superlombard.bitrix24.kz/rest/1/n1twqab43r1bwpkh/"
DEEPSEEK_API_KEY = "sk-10151018b0d14d5fa158139f226fa984"  # Ваш ключ DeepSeek
WEBHOOK_HOST = "https://185.22.67.73"  # Ваш IP
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

# --- СПРАВОЧНИКИ FAQ ---
FAQ_RU = {
    "документы": "Для займа нужны:\n- Паспорт\n- ИИН\n- Справка о доходах",
    "ставки": "Ставки от 15% годовых",
    "сроки": "Максимальный срок - 1 год"
}

FAQ_KZ = {
    "құжаттар": "Несие алу үшін қажет:\n- Паспорт\n- ЖСН\n- Табыс туралы анықтама",
    "ставкалар": "Жылдық ставкалар 15%-дан басталады",
    "мерзімдер": "Максималды мерзім - 1 жыл"
}

def get_faq_response(text, language):
    """Поиск ответа в FAQ по ключевым словам"""
    text = text.lower().strip()
    faq_dict = FAQ_KZ if language == "kk" else FAQ_RU
    
    for keyword in faq_dict:
        if keyword in text:
            return faq_dict[keyword]
    return None

def get_ai_response(prompt, language="ru"):
    """Запрос к DeepSeek AI"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = {
        "ru": "Вы консультант ломбарда Super Lombard. Отвечайте кратко и по делу на русском.",
        "kk": "Сіз Super Lombard ломбардының кеңесшісісіз. Қазақ тілінде қысқа және нақты жауап беріңіз."
    }[language]
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        logger.error(f"DeepSeek API error: {response.text}")
    except Exception as e:
        logger.error(f"DeepSeek connection error: {e}")
    return None

# Определение языка
def detect_language(text):
    try:
        return "kk" if detect(text) == "kk" else "ru"
    except:
        return "ru"

# Обработчики сообщений
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = {
        "ru": (
            "Здравствуйте! Я бот Super Lombard.\n"
            "Задайте вопрос о займах под залог.\n"
            "Примеры:\n"
            "- Какие документы нужны?\n"
            "- Какие ставки?"
        ),
        "kk": (
            "Сәлеметсіз бе! Мен Super Lombard ломбардының ботымын.\n"
            "Несие туралы сұрақ қойыңыз.\n"
            "Мысалдар:\n"
            "- Қандай құжаттар қажет?\n"
            "- Ставкалар қандай?"
        )
    }[detect_language(message.text)]
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_message = message.text
        chat_id = message.chat.id
        language = detect_language(user_message)

        # 1. Проверка FAQ
        if faq_response := get_faq_response(user_message, language):
            bot.reply_to(message, faq_response)
            return

        # 2. Запрос к DeepSeek
        if ai_response := get_ai_response(user_message, language):
            bot.reply_to(message, ai_response)
            return

        # 3. Создание лида в Bitrix24
        bitrix_data = {
            "fields": {
                "TITLE": f"Запрос от {chat_id}",
                "COMMENTS": user_message,
                "SOURCE_DESCRIPTION": f"Язык: {language}",
                "IM": f"tg:{chat_id}"
            }
        }
        response = requests.post(
            f"{BITRIX_WEBHOOK_URL}crm.lead.add",
            json=bitrix_data
        )
        bot.reply_to(message, {
            "ru": "✅ Ваш запрос принят! Мы скоро свяжемся.",
            "kk": "✅ Сұрағыңыз қабылданды! Жауап береміз."
        }[language])

    except Exception as e:
        logger.error(f"Error: {e}")
        bot.reply_to(message, {
            "ru": "⛔ Ошибка. Попробуйте позже.",
            "kk": "⛔ Қате. Кейінірек көріңіз."
        }[detect_language(message.text)])

# Вебхук
@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return 'ok', 200
    return 'Bad request', 400

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host='0.0.0.0', port=443, ssl_context='adhoc')
