from flask import Flask, request
import telebot
from faqKZ import get_response as get_response_kz
from faqRU import get_response as get_response_ru

# Настройка Telegram бота
TOKEN = "7329116708:AAFsLQoXLZo1tMfHqyrtLmDrvoFnmvA1RR8"  # Замените на ваш реальный токен
bot = telebot.TeleBot(TOKEN)

# Создаем Flask приложение
app = Flask(__name__)

def detect_language(text):
    """
    Определяет язык сообщения на основе наличия казахских символов.
    :param text: Текст сообщения от пользователя.
    :return: "kk" (казахский) или "ru" (русский).
    """
    kazakh_chars = "қңүұөһ"  # Казахские символы
    if any(char in text for char in kazakh_chars):
        return "kk"
    return "ru"

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    """
    Обработчик команд /start и /help.
    Отправляет приветственное сообщение.
    """
    welcome_text = (
        "Здравствуйте! Я бот Super Lombard.\n"
        "Задайте свой вопрос, и я постараюсь помочь.\n"
        "Примеры вопросов:\n"
        "- Какие документы нужны для получения займа?\n"
        "- Несие алу үшін қандай құжаттар қажет?"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """
    Обработчик всех текстовых сообщений.
    Определяет язык вопроса и отправляет ответ.
    """
    user_message = message.text  # Текст сообщения от пользователя
    language = detect_language(user_message)  # Определяем язык

    # Получаем ответ в зависимости от языка
    if language == "kk":
        response = get_response_kz(user_message)
    else:
        response = get_response_ru(user_message)

    # Отправляем ответ пользователю
    bot.reply_to(message, response)

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Обработчик вебхука.
    """
    # Получаем обновление от Telegram
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    # Обрабатываем обновление
    bot.process_new_updates([update])
    return 'ok', 200

if __name__ == "__main__":
    # Удаляем вебхук, если он был установлен ранее
    bot.delete_webhook()

    # Устанавливаем вебхук
    bot.set_webhook(url="https://185.22.67.73/webhook")

    # Запускаем Flask сервер
    app.run(host='0.0.0.0', port=5000)
