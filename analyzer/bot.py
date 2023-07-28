import asyncio
import os
import sys
import logging
import traceback

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils import markdown

import interactor
import matplotlib
import re

import config


logging.basicConfig(level=logging.INFO)

if len(sys.argv) > 1:
    API_TOKEN = config.read_config(sys.argv[1])["bot_api"]
    config.config = config.read_config(sys.argv[1])
else:
    API_TOKEN = config.config["bot_api"]

import bot_data_handler
import inline_keyboard_manager

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class Form(StatesGroup):
    table_name = State()  
    description = State()
    context = State()


@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    print("processing")
    first_time = await bot_data_handler.make_insertion(message.chat.id)

    if first_time:

        await help_info(message)
        
    text = "Вы можете выбрать одну из опций"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("🖹 Выбрать таблицу"),
        types.KeyboardButton("➕ Добавить описание таблицы"), 
        types.KeyboardButton("🖻 Режим визуализации"),
    )
    markup.add(
        types.KeyboardButton("❓ Режим отправки запроса"),
        types.KeyboardButton("Добавить контекст"),
        types.KeyboardButton("Группы таблиц")  
    )
    await message.reply(text, reply_markup=markup)


@dp.message_handler(commands=['help'])
async def help_info(message: types.Message):
    await message.reply("""Здравствуйте, я автономный помощник для проведения различной аналитики
Я могу отвечать на вопросы по предоставленным данным, строить графики и проводить нужные вычисления""")
    
    help_text = """
* Используйте кнопку 'Выбрать Таблицу' для выбора и добавления таблиц
* Используйте кнопку 'Добавить описание' для добавления описания к нужным таблицам
* Используйте кнопку 'Добавить контекст' для добавления контекста к нужным таблицам
* Используйте кнопку 'Режим отправки запроса' для взаимодействия со мной
* Используйте кнопку 'Режим визуализации' для настройки режима построения графиков
* Используйте кнопку 'Группы таблиц' для создания и настройки групп таблиц"""

    await message.reply(help_text, parse_mode=types.ParseMode.MARKDOWN)
    
    example = "Пример запроса: 'Проведи исследовательский анализ данных по предоставленной таблице'"
    await message.reply(example)
    
    instructions = """
Для того, чтобы начать общение с ботом:
1) Нажмите кнопку 'Выбрать таблицу', затем добавьте новую таблицу или воспользуйтесь уже добавленной
2) После этого вы можете добавить описание и контекст к вашим данным для лучшей работы модели
3) Нажмите кнопку 'Режим отправки запроса' и напишите свой запрос модели, дождитесь ответа
4) После получения ответа можете задать вопрос или выйти из режима в главное меню"""
    
    await message.reply(instructions)
    
    trouble = "В случае проблем с ботом попробуйте перезапустить его через команду '/start'"
    await message.reply(trouble)


@dp.message_handler(Text(equals="🖹 Выбрать таблицу"))
async def select_table(message: types.Message):

    await Form.table_name.set()
    markup = await create_inline_keyboard(message.chat.id, "table_page")

    await message.reply("Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)


@dp.message_handler(Text(equals="➕ Добавить описание таблицы"))
async def add_description(message: types.Message):
    await Form.description.set()

    markup = await create_inline_keyboard(message.chat.id, "description_page")
    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)


@dp.message_handler(Text(equals="➕ Добавить описание таблицы"))
async def add_description(message: types.Message):
    await Form.description.set()

    markup = await bot_data_handler.create_inline_keyboard(message.chat.id, "description_page")
    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)


@dp.message_handler(Text(equals="🖻 Режим визуализации"))
async def toggle_plots(message: types.Message):
    text = await bot_data_handler.set_plots(message)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Вернуться в главное меню"))
    await message.reply(text, reply_markup=markup)


@dp.message_handler(Text(equals="❓ Режим отправки запроса"))
async def request_mode(message: types.Message):
    #await call_to_model(message.chat.id)
    pass

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 exit"))
    await message.reply("Отправьте запрoс. До получения ответа взаимодействие с ботом блокируется",
                        reply_markup=markup)


@dp.message_handler(Text(equals="Группы таблиц"))
async def group_options(message: types.Message):
    markup = await inline_keyboard_manager.create_group_keyboard(message.chat.id)
    await message.reply("Вы можете выбрать опцию", reply_markup=markup)

@dp.message_handler()
async def create_inline_keyboard(chat_id, page_type, page=1, group_mode=False):
    print("start")
    keyboard_types = ["table_page", "description_page", "context_page"]
    if not page_type not in keyboard_types:
        raise ValueError("Invalid page type")
    print("HU")
    return await inline_keyboard_manager.inline_keyboard(chat_id=chat_id, page_type=page_type, page=page,
                                                         status_flag=False)

if __name__ == '__main__':

    executor.start_polling(dp, skip_updates=True)
