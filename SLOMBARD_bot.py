from flask import Flask, request, jsonify
import telebot
import requests
import logging
from langdetect import detect
from faqRU import FAQ_RU, SYNONYMS_RU
from faqKZ import FAQ_KZ, SYNONYMS_KZ

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

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

def get_faq_response(text, language):
    """Поиск ответа в FAQ по ключевым словам с учетом синонимов"""
    text = text.lower().strip()
    faq_dict = FAQ_KZ if language == "kk" else FAQ_RU
    synonyms = SYNONYMS_KZ if language == "kk" else SYNONYMS_RU
    
    # Проверяем основные ключевые слова
    for keyword in faq_dict:
        if keyword in text:
            return faq_dict[keyword]
    
    # Проверяем синонимы
    for keyword, syn_list in synonyms.items():
        if any(syn in text for syn in syn_list):
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
            timeout=15
        )
        logger.info(f"DeepSeek API response: {response.status_code}, {response.text}")
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"DeepSeek API error: {response.text}")
            return None
    except Exception as e:
        logger.error(f"DeepSeek connection error: {e}")
        return None

def detect_language(text):
    """Определение языка с проверкой казахских символов"""
    try:
        text = text.lower()
        kazakh_chars = "әғқңөұүіһ"
        if any(char in text for char in kazakh_chars):
            return "kk"
        
        lang = detect(text)
        return "kk" if lang == "kk" else "ru"
    except:
        return "ru"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = {
        "ru": (
            "Здравствуйте! Я бот Super Lombard.\n"
            "Задайте вопрос о займах под залог.\n"
            "Примеры:\n"
            "- Какие документы нужны?\n"
            "- Какие ставки?\n"
            "- Что можно оставить в залог?"
        ),
        "kk": (
            "Сәлеметсіз бе! Мен Super Lombard ломбардының ботымын.\n"
            "Несие туралы сұрақ қойыңыз.\n"
            "Мысалдар:\n"
            "- Қандай құжаттар қажет?\n"
            "- Ставкалар қандай?\n"
            "- Кепілге не алуға болады?"
        )
    }[detect_language(message.text)]
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_message = message.text
        chat_id = message.chat.id
        language = detect_language(user_message)
        
        logger.info(f"New message ({language}): {user_message}")

        # 1. Проверка FAQ
        if faq_response := get_faq_response(user_message, language):
            logger.info("FAQ match found")
            bot.reply_to(message, faq_response)
            return

        # 2. Запрос к DeepSeek
        if ai_response := get_ai_response(user_message, language):
            logger.info("AI response generated")
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
            json=bitrix_data,
            timeout=10
        )
        
        logger.info(f"Bitrix24 response: {response.status_code}, {response.text}")
        
        bot.reply_to(message, {
            "ru": "✅ Ваш запрос принят! Мы скоро свяжемся.",
            "kk": "✅ Сұрағыңыз қабылданды! Жауап береміз."
        }[language])

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        bot.reply_to(message, {
            "ru": "⛔ Ошибка. Попробуйте позже.",
            "kk": "⛔ Қате. Кейінірек көріңіз."
        }[detect_language(message.text)])

if __name__ == '__main__':
    logger.info("Starting bot in polling mode...")
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=1, timeout=30)
