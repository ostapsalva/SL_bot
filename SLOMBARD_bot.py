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

# Конфигурация (рекомендуется использовать переменные окружения)
TELEGRAM_TOKEN = "7329116708:AAFsLQoXLZo1tMfHqyrtLmDrvoFnmvA1RR8"
BITRIX_WEBHOOK_URL = "https://superlombard.bitrix24.kz/rest/1/n1twqab43r1bwpkh/"
DEEPSEEK_API_KEY = "sk-10151018b0d14d5fa158139f226fa984"

# Инициализация
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)

def detect_language(text):
    """Улучшенное определение языка с проверкой казахских символов"""
    if not text or not isinstance(text, str):
        return "ru"
    
    text = text.lower().strip()
    kazakh_chars = "әғқңөұүіһ"
    
    # Проверка казахских символов
    if any(char in text for char in kazakh_chars):
        return "kk"
    
    # Простые ключевые слова для определения языка
    ru_keywords = ["ломбард", "займ", "залог", "документ", "ставк", "рубл"]
    kz_keywords = ["ломбард", "несие", "кепіл", "құжат", "ставка", "теңге"]
    
    ru_count = sum(1 for word in ru_keywords if word in text)
    kz_count = sum(1 for word in kz_keywords if word in text)
    
    return "kk" if kz_count > ru_count else "ru"

def get_ai_response(prompt, language="ru"):
    """Улучшенная функция запроса к DeepSeek с обработкой ошибок"""
    if not prompt or not isinstance(prompt, str):
        return None
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = {
        "ru": (
            "Ты консультант ломбарда Super Lombard. Отвечай только на вопросы "
            "по тематике займов под залог. Если вопрос не по теме, вежливо "
            "сообщи, что помогаешь только с вопросами о залогах и кредитах. "
            "Будь кратким и конкретным. Максимум 3 предложения."
        ),
        "kk": (
            "Сен Super Lombard ломбардының кеңесшісісің. Тек кепілге несие "
            "беруге қатысты сұрақтарға жауап бер. Егер сұрақ тақырыпқа "
            "қатысты болмаса, кепіл несиелері туралы ғана көмектесе "
            "алатыныңды мейірімді айт. Қысқа және нақты бол."
        )
    }.get(language, "You are a pawnshop consultant.")
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 300,
        "top_p": 0.9
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"DeepSeek API error: {response.status_code} - {response.text}")
            return None
            
        return response.json()["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        logger.warning("DeepSeek API timeout")
        return None
    except Exception as e:
        logger.error(f"DeepSeek connection error: {str(e)}")
        return None

@bot.message_handler(commands=['start', 'help', 'помощь', 'анықтама'])
def send_welcome(message):
    lang = detect_language(message.text)
    
    welcome_messages = {
        "ru": (
            "🏦 Добро пожаловать в Super Lombard!\n\n"
            "Я могу помочь с информацией о:\n"
            "- Залогах и кредитах\n"
            "- Необходимых документах\n"
            "- Условиях продления\n"
            "- Ставках и расчетах\n\n"
            "Просто задайте ваш вопрос в чат!"
        ),
        "kk": (
            "🏦 Super Lombard-қа қош келдіңіз!\n\n"
            "Мен мына туралы ақпарат бере аламын:\n"
            "- Кепіл несиелері\n"
            "- Қажетті құжаттар\n"
            "- Ұзарту шарттары\n"
            "- Ставкалар мен есептеулер\n\n"
            "Жай сұрақ қойыңыз!"
        )
    }
    
    bot.reply_to(message, welcome_messages.get(lang, welcome_messages["ru"]))

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    try:
        user_message = message.text.strip()
        chat_id = message.chat.id
        lang = detect_language(user_message)
        
        logger.info(f"New message ({lang}): {user_message[:100]}...")  # Логируем первые 100 символов

        # 1. Пробуем получить ответ из FAQ
        try:
            faq_response = get_kz_response(user_message) if lang == "kk" else get_ru_response(user_message)
            
            # Проверяем, что это не стандартное подтверждение
            if faq_response and not any(phrase in faq_response.lower() for phrase in 
                                      ["қабылданды", "принят", "свяжемся", "береміз"]):
                logger.info("Sending FAQ response")
                bot.reply_to(message, faq_response)
                return
        except Exception as faq_error:
            logger.error(f"FAQ processing error: {str(faq_error)}")

        # 2. Пробуем получить ответ от DeepSeek
        try:
            ai_response = get_ai_response(user_message, lang)
            if ai_response:
                logger.info("Sending AI response")
                bot.reply_to(message, ai_response)
                return
        except Exception as ai_error:
            logger.error(f"DeepSeek processing failed: {str(ai_error)}")

        # 3. Создаем лид в Bitrix24 как резервный вариант
        try:
            lead_data = {
                "fields": {
                    "TITLE": f"Необработанный запрос от {chat_id}",
                    "NAME": f"Telegram User {chat_id}",
                    "COMMENTS": f"Язык: {lang}\n\nЗапрос:\n{user_message}\n\nНе удалось сгенерировать автоматический ответ",
                    "IM": [{"VALUE": f"tg:{chat_id}", "VALUE_TYPE": "OTHER"}],
                    "SOURCE_ID": "TELEGRAM_BOT"
                }
            }
            
            bitrix_response = requests.post(
                f"{BITRIX_WEBHOOK_URL}crm.lead.add",
                json={"fields": lead_data},
                timeout=8
            )
            
            if bitrix_response.status_code == 200:
                logger.info(f"Bitrix lead created: {bitrix_response.json()}")
            else:
                logger.error(f"Bitrix24 error: {bitrix_response.status_code} - {bitrix_response.text}")
        except Exception as bitrix_error:
            logger.error(f"Bitrix24 connection failed: {str(bitrix_error)}")

        # 4. Отправляем пользователю информативное сообщение
        backup_responses = {
            "ru": (
                "📌 Ваш вопрос требует уточнения\n\n"
                "Мы передали его специалистам и ответим вам в ближайшее время.\n"
                "Пока вы можете уточнить:\n"
                "- О каком виде залога идет речь?\n"
                "- Какая сумма вам нужна?\n"
                "- На какой срок?\n\n"
                "Это поможет нам ответить быстрее и точнее!"
            ),
            "kk": (
                "📌 Сұрағыңыз нақтылауды талап етеді\n\n"
                "Біз оны мамандарға жеткіздік және жауап береміз.\n"
                "Сіз мынаны нақтылай аласыз:\n"
                "- Қандай кепіл туралы айтып отырсыз?\n"
                "- Қандай сома қажет?\n"
                "- Қанша уақытқа?\n\n"
                "Бұл бізге жылдам және дәл жауап беруге көмектеседі!"
            )
        }
        
        bot.reply_to(message, backup_responses.get(lang, backup_responses["ru"]))

    except Exception as e:
        logger.error(f"Critical error in message processing: {str(e)}", exc_info=True)
        error_msg = {
            "ru": "⚠ На сервере произошла ошибка. Мы уже работаем над решением проблемы.",
            "kk": "⚠ Серверде қате пайда болды. Біз мәселені шешу үстіндеміз."
        }.get(lang, "⚠ System error. Please try again later.")
        
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
