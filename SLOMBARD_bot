import json
import telebot
from deepseek import DeepSeekAPI
from flask import Flask, request

# Загрузка FAQ из файлов
from faqKZ import FAQ as FAQ_KZ
from faqRU import FAQ as FAQ_RU

# Настройка API DeepSeek (предположительно есть библиотека deepseek)
deepseek = DeepSeekAPI(api_key="sk-10151018b0d14d5fa158139f226fa984")

# Настройка Telegram бота
TOKEN = "7329116708:AAFsLQoXLZo1tMfHqyrtLmDrvoFnmvA1RR8"
bot = telebot.TeleBot(TOKEN)

def get_faq_response(message, language):
    """Ищет ответ в соответствующем FAQ."""
    faq = FAQ_KZ if language == "kk" else FAQ_RU
    return faq.get(message, None)

def get_ai_response(message):
    """Получает ответ от DeepSeek, если вопрос отсутствует в FAQ."""
    return deepseek.get_response(message)

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    bot.reply_to(message, "Здравствуйте! Задайте свой вопрос, и я постараюсь помочь.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    language = "kk" if any(c in message.text for c in "қңүұөһ") else "ru"
    response = get_faq_response(message.text, language) or get_ai_response(message.text)
    bot.reply_to(message, response)

if __name__ == "__main__":
    bot.polling(none_stop=True)
