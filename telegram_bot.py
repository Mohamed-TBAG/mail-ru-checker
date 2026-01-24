from telebot import TeleBot
import threading
import time

class TelegramBot:
    def __init__(self, token):
        self.bot = TeleBot(token)
        self.chat_id = None # captured from updates

    def edit_message(self, chat_id, message_id, text):
        try:
            self.bot.edit_message_text(text, chat_id, message_id)
        except Exception as e:
            print(f"Telegram Edit Error: {e}")