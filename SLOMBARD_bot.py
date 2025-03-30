from flask import Flask, request, jsonify
import telebot
import requests
import logging
import re
from faqRU import get_response as get_ru_response
from faqKZ import get_response as get_kz_response

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = "7329116708:AAFsLQoXLZo1tMfHqyrtLmDrvoFnmvA1RR8"
BITRIX_WEBHOOK_URL = "https://superlombard.bitrix24.kz/rest/1/n1twqab43r1bwpkh/"
DEEPSEEK_API_KEY = "sk-10151018b0d14d5fa158139f226fa984"

# Инициализация
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

def detect_language(text):
    """Улучшенное определение языка с проверкой казахских символов"""
    text = text.lower().strip()
    if not text:
        return "ru"
    
    kazakh_chars = "әғқңөұүіһ"
    if any(char in text for char in kazakh_chars):
        return "kk"
    
    # Простые ключевые слова для русского
    ru_keywords = ["ломбард", "займ", "залог", "документы", "ставки"]
    if any(word in text for word in ru_keywords):
        return "ru"
    
    return "kk" if len(re.findall(r'[а-я]', text)) < len(re.findall(r'[a-z]', text)) else "ru"

def get_ai_response(prompt, language="ru"):
    """Запрос к DeepSeek AI с улучшенной обработкой ошибок"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = {
        "ru": "Ты консультант ломбарда Super Lombard. Отвечай кратко и по делу.",
        "kk": "Сен Super Lombard ломбардының кеңесшісісің. Қысқа және нақты жауап бер."
    }.get(language, "You are a consultant for Super Lombard. Respond concisely.")
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek API error: {str(e)}")
        return None

@bot.message_handler(commands=['start', 'help', 'помощь', 'анықтама'])
def send_welcome(message):
    lang = detect_language(message.text)
    responses = {
        "ru": (
            "🟢 Здравствуйте! Я виртуальный помощник Super Lombard.\n"
            "Могу ответить на вопросы:\n"
            "- Оформление займа под залог\n"
            "- Необходимые документы\n"
            "- Условия продления\n"
            "- Ставки и расчеты\n\n"
            "Просто задайте вопрос в чат!"
        ),
        "kk": (
            "🟢 Сәлеметсіз бе! Мен Super Lombard-тың виртуалды көмекшісімін.\n"
            "Мына сұрақтарға жауап бере аламын:\n"
            "- Кепіл бойынша несие алу\n"
            "- Қажетті құжаттар\n"
            "- Ұзарту шарттары\n"
            "- Ставкалар мен есептеулер\n\n"
            "Жай сұрақ қойыңыз!"
        )
    }
    bot.reply_to(message, responses.get(lang, responses["ru"]))

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_message = message.text.strip()
        chat_id = message.chat.id
        lang = detect_language(user_message)
        
        logger.info(f"New message ({lang}): {user_message}")

        # 1. Получаем ответ из FAQ
        faq_response = get_kz_response(user_message) if lang == "kk" else get_ru_response(user_message)
        
        # Если ответ не стандартное подтверждение
        if faq_response and not any(phrase in faq_response for phrase in 
                                  ["қабылданды", "принят", "свяжемся", "береміз"]):
            bot.reply_to(message, faq_response)
            return

        # 2. Запрос к AI, если FAQ не дал ответа
        ai_response = get_ai_response(user_message, lang)
        if ai_response:
            bot.reply_to(message, ai_response)
            return

        # 3. Создание лида в Bitrix24
        lead_data = {
            "fields": {
                "TITLE": f"Запрос из Telegram (ID: {chat_id})",
                "NAME": str(chat_id),
                "COMMENTS": user_message,
                "SOURCE_DESCRIPTION": f"Язык: {lang}",
                "IM": [{"VALUE": f"tg:{chat_id}", "VALUE_TYPE": "OTHER"}]
            }
        }
        
        bitrix_response = requests.post(
            f"{BITRIX_WEBHOOK_URL}crm.lead.add",
            json={"fields": lead_data},
            timeout=8
        )
        
        if bitrix_response.status_code == 200:
            logger.info(f"Lead created: {bitrix_response.json()}")
        else:
            logger.error(f"Bitrix24 error: {bitrix_response.text}")

        # Отправка подтверждения
        confirmation = {
            "ru": "✅ Ваш запрос передан специалисту. Ожидайте ответа!",
            "kk": "✅ Сұрағыңыз маманға жеткізілді. Жауап күтіңіз!"
        }.get(lang, "✅ Your request has been received.")
        
        bot.reply_to(message, confirmation)

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        error_msg = {
            "ru": "⚠ Произошла ошибка. Пожалуйста, попробуйте позже.",
            "kk": "⚠ Қате пайда болды. Кейінірек қайталаңыз."
        }.get(lang, "⚠ An error occurred. Please try again later.")
        
        bot.reply_to(message, error_msg)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_update = request.json
        update = telebot.types.Update.de_json(json_update)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

if __name__ == '__main__':
    logger.info("Starting bot...")
    bot.remove_webhook()
    bot.polling(none_stop=True, timeout=60)
