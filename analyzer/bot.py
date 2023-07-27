"""
This module is the main entry point of the Telegram bot application. It uses the aiogram library to create a bot and a dispatcher for handling incoming messages. The bot token is read from a configuration file.

The bot has two main features:
1. Responding to the 'help' command by sending a message to the user with some information about the bot.
2. Responding to the 'start' and 'exit' commands by calling the 'main' function, which inserts the chat id into a database and sends the help message if it's the user's first time interacting with the bot.

Usage:
Run this module directly to start the bot. The bot will then listen for incoming messages from users.
"""

import os
import time
import requests
import sys
import config

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

from bot_data_handler import *
from handlers.handlers import help_info, main

bot: Bot = Bot(token=config.config['bot_api'])
dp: Dispatcher = Dispatcher(bot)

@dp.message_handler(commands=['help'])
def help_info_handler(message: types.Message):
    help_info(bot, message)

@dp.message_handler(commands=['start', 'exit'], content_types=['text', 'document'])
def main_handler(message: types.Message) -> None:
    main(bot, message)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)