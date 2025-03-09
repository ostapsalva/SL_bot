import telebot
from faqKZ import get_response as get_response_kz
from faqRU import get_response as get_response_ru

# Настройка Telegram бота
TOKEN = "7329116708:AAFsLQoXLZo1tMfHqyrtLmDrvoFnmvA1RR8"  # Замените на ваш реальный токен
bot = telebot.TeleBot(TOKEN)

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

if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)  # Запуск бота
