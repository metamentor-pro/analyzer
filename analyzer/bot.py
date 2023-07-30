import asyncio
import os
import sys
import time
import requests
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
import db_manager

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class Form(StatesGroup):
    table_name = State()  
    description = State()
    context = State()
    request = State()
    question = State()

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):

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
    
    trouble = "В случае проблем с ботом попробуйте перезапустить его через команду 'start'"
    await message.reply(trouble)


@dp.message_handler(Text(equals="🖹 Выбрать таблицу"))
async def select_table(message: types.Message, state: FSMContext):
    await Form.table_name.set()
    markup = await create_inline_keyboard(message.chat.id, "table_page")
    await message.reply("Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)
    await send_welcome(message)


@dp.callback_query_handler(Text(startswith="t|"), state=Form.table_name)
async def choose_table(call: types.CallbackQuery):
    action = call.data.split("|")[1]
    chat_id = call.message.chat.id

    if action == "new_table":
        await call.message.answer("Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json")
        await Form.table_name.set()

    elif action == "delete_tables":
        tables = await bot_data_handler.delete_last_table(call.message.chat.id)
        await call.message.answer(f"Таблица {tables[-1]} удалена из текущего списка")

    elif action in ("right", "left"):
        amount = await inline_keyboard_manager.get_pages_amount(chat_id=chat_id,)
        page = await inline_keyboard_manager.get_page(chat_id=chat_id, page_type="table_page")
        new_page = page
        if page < amount:
            if action == "right":
                new_page = page + 1
            elif page > 1:
                new_page = page - 1

        await inline_keyboard_manager.change_page(call.message.chat.id, "table_page", new_page=new_page)
        markup = await create_inline_keyboard(call.message.chat.id,"table_page", new_page)
        await call.message.edit_text("Вы можете выбрать таблицу или добавить новую",
                                     reply_markup=markup)

    else:
        await choose_table(call.data, call.message)
        await call.message.answer("Таблица выбрана")


    await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['document'], state=Form.table_name)
async def load_table(message: types.Message, state: FSMContext):
    await db_manager.add_table_db(message)
    await message.reply("Файл сохранен")
    await state.finish()


@dp.message_handler(Text(equals="Добавить контекст"))
async def add_description(message: types.Message, state: FSMContext):
    await Form.description.set()

    markup = await create_inline_keyboard(message.chat.id, "context_page")

    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)
    await send_welcome(message)


@dp.callback_query_handler(Text(startswith="c|"), state=Form.context)
async def choose_context(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("|")[1]
    chat_id = call.message.chat.id

    if action in ("right", "left"):
        amount = await inline_keyboard_manager.get_pages_amount(chat_id=chat_id,)
        page = await inline_keyboard_manager.get_page(chat_id=chat_id, page_type="context_page")
        new_page = page
        if page < amount:
            if action == "right":
                new_page = page + 1
            elif page > 1:
                new_page = page - 1

        await inline_keyboard_manager.change_page(call.message.chat.id, "context_page", new_page=new_page)
        markup = await create_inline_keyboard(call.message.chat.id, "context_page", new_page)
        await call.message.edit_text("Вы можете выбрать таблицу или добавить новую",
                                     reply_markup=markup)

    elif action == "exit":
        await call.message.delete()
        await state.finish()

    else:
        await call.message.answer(f"Таблица {action} выбрана, отправьте контекст в формате txt")
        await Form.next()
        await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['text', 'document'], state=Form.context)
async def save_context(message: types.Message, state: FSMContext):
    table_name = message.text
    await db_manager.add_context(message, table_name)
    await message.reply("Контекст сохранен")
    await state.finish()


@dp.message_handler(Text(equals="➕ Добавить описание таблицы"))
async def add_description(message: types.Message, state: FSMContext):
    await Form.description.set()
    markup = await create_inline_keyboard(message.chat.id, "description_page")
    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)



@dp.callback_query_handler(Text(startswith="d|"), state=Form.description)
async def choose_description(call: types.CallbackQuery):
    action = call.data.split("|")[1]
    chat_id = call.message.chat.id
    if action in ("right", "left"):
        amount = await inline_keyboard_manager.get_pages_amount(chat_id=chat_id, )
        page = await inline_keyboard_manager.get_page(chat_id=chat_id, page_type="description_page")
        new_page = page
        if page < amount:
            if action == "right":
                new_page = page + 1
            elif page > 1:
                new_page = page - 1

        await inline_keyboard_manager.change_page(call.message.chat.id, "description_page", new_page=new_page)
        markup = await create_inline_keyboard(call.message.chat.id, "description_page", new_page)
        await call.message.edit_text("Вы можете выбрать таблицу или добавить новую",
                                     reply_markup=markup)


    elif action == "exit":
        await call.message.delete()
        #await state.finish()

    else:
        await call.message.answer(f"Таблица {action} выбрана, отправьте описание в формате txt")
        await Form.next()
        await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['text', 'document'], state=Form.description)
async def save_description(message: types.Message, state: FSMContext):
    table_name = message.text
    await db_manager.choose_description_db(message, table_name)
    await message.reply("Описание сохранено")
    await state.finish()


@dp.message_handler(Text(equals="🖻 Режим визуализации"))
async def toggle_plots(message: types.Message, state: FSMContext):
    text = await bot_data_handler.set_plots(message)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Вернуться в главное меню"))
    await message.reply(text, reply_markup=markup)
    await send_welcome(message)


@dp.message_handler(Text(equals="❓ Режим отправки запроса"))
async def request_mode(message: types.Message, state: FSMContext):
    #await call_to_model(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 exit"))
    await message.reply("Отправьте запрoс. До получения ответа взаимодействие с ботом блокируется",
                        reply_markup=markup)
    await Form.question.set()


@dp.message_handler(Text(equals="Группы таблиц"))
async def group_options(message: types.Message, state: FSMContext):
    markup = await inline_keyboard_manager.create_group_keyboard(message.chat.id)
    await message.reply("Вы можете выбрать опцию", reply_markup=markup)
    await send_welcome(message)


@dp.message_handler()
async def create_inline_keyboard(chat_id, page_type, page=1, group_mode=False):

    keyboard_types = ["table_page", "description_page", "context_page"]

    if page_type not in keyboard_types:
        raise ValueError("Invalid page type")

    return await inline_keyboard_manager.inline_keyboard(chat_id=chat_id, page_type=page_type, page=page,
                                                         status_flag=False)


@dp.message_handler(state=Form.question)
async def call_to_model(message: types.Message, state: FSMContext):
    demo_status = await db_manager.check_for_demo(chat_id=message.chat.id)
    if demo_status is not None:
        pass
    if message.text == "🚫 exit":

        await bot_data_handler.exit_from_model(message.chat.id)

        await state.finish()
        await send_welcome()

    elif message.text == "Нет":
        await send_welcome(message)

    else:
        if message.text == "Да":
            user_question = "Проведи исследовательский анализ данных по таблице"
        else:
            user_question = message.text
        chat_id = message.chat.id

        def callback(sum_on_step):
            message_id = send_message.message_id
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=send_message.text + f"\n{sum_on_step}")
        settings = await db_manager.get_settings(chat_id)
        try:
            if settings["table_name"] is None or settings["table_name"] == "":
                await message.answer("Таблицы не найдены, вы можете выбрать другие")
                markup = types.ReplyKeyboardMarkup()
                btn1 = types.KeyboardButton("🚫 exit")
                markup.add(btn1)
                await message.answer("Вы можете выйти из режима работы с моделью с помощью 'exit'",
                             reply_markup=markup)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                btn1 = types.KeyboardButton("🚫 exit")
                markup.add(btn1)
                await message.answer("Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью 'exit'",
                                 reply_markup=markup)
                await message.answer("Учтите, что первичная обработка больших таблиц может занять несколько минут, спасибо")
                send_message = await message.answer("Здесь будет описан процесс моих рассуждений:")
                answer_from_model = await bot_data_handler.model_call(chat_id=chat_id, user_question=user_question,callback=callback)
                if answer_from_model[0] == "F":
                    await message.answer("Что-то пошло не так, повторяю запрос")
                    answer_from_model = await bot_data_handler.model_call(chat_id=chat_id, user_question=user_question,
                                                   callback=callback)
                    if answer_from_model[0] == "F":
                        await message.answer("Что-то пошло не так")
                current_summary = await bot_data_handler.get_summary(chat_id)
                summary = answer_from_model[1]
                await message.reply("Обрабатываю запрос...")
                new_summary = current_summary + summary
                print(summary)
                await db_manager.update_summary(chat_id, new_summary)
                time.sleep(10)
                pattern = r"\b\w+\.png\b"
                pattern2 = r"[\w.-]+\.png"
                if ".png" in answer_from_model[1]:
                    plot_files = re.findall(pattern, answer_from_model[1])
                    plot_files_2 = re.findall(pattern2, answer_from_model[1])
                    print("plot_files", plot_files, plot_files_2)
                    for plot_file in plot_files:
                        path_to_file = "Plots/" + plot_file
                        if os.path.exists(path_to_file):
                            await message.answer_photo(open(path_to_file, "rb"))
                        path_to_file = "Plots/" + plot_file
                        if os.path.exists(path_to_file):
                            os.remove(path_to_file)
                    for plot_file in plot_files_2:
                        path_to_file = "Plots/" + plot_file
                        if os.path.exists(path_to_file) and path_to_file not in plot_files:
                            await message.answer_photo(open(path_to_file, "rb"))
                        path_to_file = "Plots/" + plot_file
                        if os.path.exists(path_to_file):
                            os.remove(path_to_file)
                    matplotlib.pyplot.close("all")
                    await message.answer(f"Answer: {answer_from_model[0]}")
                else:
                    await message.answer(f"Answer: {answer_from_model[0]}")
                #bot.register_next_step_handler(message, call_to_model)
        except requests.exceptions.ConnectionError:
            await call_to_model(message)
            await message.answer("Что-то пошло не так, пожалуйста, повторите вопрос или используйте команду start")


            #await message.reply(f"Ответ: {answer}")
            #await bot_data_handler.update_summary(message.chat.id, new_summary)

            #await Form.request.set()


async def main():
    # Your code to start the bot, setup handlers, etc.
    await dp.start_polling()

if __name__ == "__main__":
    # Run the main function inside the asyncio event loop
    asyncio.run(main())
