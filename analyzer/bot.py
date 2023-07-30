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
import aiosqlite

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
    db_name = config.config["db_name"]

import bot_data_handler
import inline_keyboard_manager
import db_manager

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class Form(StatesGroup):
    start = State()
    working = State()
    load_table = State()
    choose_table = State()
    description = State()
    context = State()
    plot = State()
    request = State()
    question = State()

class GroupForm(StatesGroup):
    group = State()

data_keys = {
    Form.load_table: "call_message_id"
}


@dp.message_handler(commands=["start"], state="*")
@dp.message_handler(state=[Form.start, None])
async def main_menu(message: types.Message, state: FSMContext):
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
    await Form.working.set()


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


@dp.message_handler(Text(equals="🖹 Выбрать таблицу"), state="*")
async def select_table(message: types.Message):
    markup = await create_inline_keyboard(message.chat.id, "table_page")
    await message.reply("Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)


@dp.callback_query_handler(Text(startswith="t|"))
async def callback_query(call: types.CallbackQuery, state: FSMContext) -> None:
    action = call.data.split("|")[1]
    chat_id = call.message.chat.id
    print(action)
    if action == "new_table":
        await call.message.answer("Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json")
        await Form.load_table.set()
        await state.update_data({load_table: call.message.message_id})

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
        await choose_table(call.data)
        await call.message.answer("Таблица выбрана")
    await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['document'], state=Form.load_table)
async def load_table(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    message = message
    message_id = await state.get_data()
    message_id = message_id.get(load_table)
    group_name = await db_manager.check_group_design(chat_id)
    group_id = await db_manager.get_group_id(group_name, chat_id)
    if message.text == "🚫 exit":
        await main_menu(message)
    else:
        try:

            file_id = message.document.file_id
            file_info = await bot.get_file(file_id)
            file_path = await file_info.file_path
            downloaded_file = bot.download_file(file_path)
            if len(message.document.file_name) > 40:
                await message.answer("К сожалению, название таблицы слишком длинное, придётся его сократить")
                #bot.register_next_step_handler(message, add_table, call)
            else:
                message.document.file_name = str(chat_id) + "_" + message.document.file_name
                if group_name is not None:
                    async with aiosqlite.connect(db_name) as con:
                        existing_reocd = await con.execute(
                        """SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ? and group_id and group_id == ?""",
                        (chat_id, message.document.file_name, group_id))
                    existing_record = await existing_reocd.fetchone()
                    if existing_record is None:
                        await db_manager.add_table(message=message, downloaded_file=downloaded_file)
                        await message.reply('Файл сохранен')
                        page_type = "table_page"
                        markup2 = await create_inline_keyboard(chat_id=chat_id, page_type=page_type)
                        bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                              text="Вы можете выбрать таблицу или добавить новую",
                                              reply_markup=markup2)
                        #group_main(message)
                    else:
                        await bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")
                        #bot.register_next_step_handler(message, add_table, call)
                else:
                    async with aiosqlite.connect(db_name) as con:
                        existing_record = await con.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?",
                                (chat_id, message.document.file_name))
                        existing_record = await existing_record.fetchone()
                        if existing_record is None:
                            await db_manager.add_table(message=message, downloaded_file=downloaded_file)
                            await message.reply('Файл сохранен')
                            page_type = "table_page"
                            markup2 = await create_inline_keyboard(chat_id=chat_id, page_type=page_type)
                            bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                              text="Вы можете выбрать таблицу или добавить новую",
                                              reply_markup=markup2)
                            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                            btn1 = types.KeyboardButton("Нет")
                            btn2 = types.KeyboardButton("Да")
                            markup.row(btn2, btn1)
                            await bot.send_message(chat_id, "Хотите ли вы получить предварительную информацию по таблице?",
                                         reply_markup=markup)
                        #bot.register_next_step_handler(message, call_to_model)
                        else:
                            await bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")
                            #bot.register_next_step_handler(message, add_table, call)
        except Exception as e:
            print(e)
            await bot.send_message(chat_id, "Что-то пошло не так, попробуйте другой файл")
            #bot.register_next_step_handler(message, add_table, call)


@dp.message_handler(content_types=['document'], state=Form.choose_table)
async def choose_table(call: types.callback_query, state: FSMContext):
    try:
        chat_id = call.message.chat.id
        text = call.data
        message = call.message
    except Exception as e:
        print(e)
        chat_id = call.chat.id
        text = call.text
        message = call

    settings = await db_manager.get_settings(chat_id)
    if settings["table_name"] is not None and len(settings["table_name"]) != 0:
        if text not in settings["table_name"]:
            settings["table_name"] += ", " + text
            await message.answer("Таблица добавлена")
        else:
            await message.answer("Данная таблица уже добавлена в список")
    else:
        settings["table_name"] = text
        await message.answer("Таблица выбрана.")
    await db_manager.update_table(chat_id=chat_id, settings=settings)


@dp.message_handler(Text(equals="Добавить контекст"), state="*")
async def add_description(message: types.Message, state: FSMContext):
    markup = await create_inline_keyboard(message.chat.id, "context_page")

    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)
    await main_menu(message)


@dp.callback_query_handler(Text(startswith="c|"))
async def callback_query(call: types.CallbackQuery, state: FSMContext):
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


@dp.message_handler(Text(equals="➕ Добавить описание таблицы"), state="*")
async def description(message: types.Message, state: FSMContext):
    markup = await create_inline_keyboard(message.chat.id, "description_page")
    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)


@dp.callback_query_handler(Text(startswith="d|"))
async def callback_query(call: types.CallbackQuery):
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
        await Form.description.set()
        await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['text', 'document'], state=Form.description)
async def save_description(message: types.Message, state: FSMContext):
    table_name = message.text
    await db_manager.choose_description_db(message, table_name)
    await message.reply("Описание сохранено")
    await state.finish()



@dp.message_handler(Text(equals="🖻 Режим визуализации"), state="*")
async def plot_on_click(message: types.Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    settings = await db_manager.get_settings(chat_id)
    if settings["build_plots"] == 0:
        build_plots = "выключен"
    else:
        build_plots = "включен"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Выключить")
    btn2 = types.KeyboardButton("Включить")
    markup.row(btn1, btn2)
    await bot.send_message(chat_id, f"Можете выбрать режим визуализации данных, он  {build_plots}  в данный момент",
                     reply_markup=markup)
    await Form.plot.set()


@dp.message_handler(state=Form.plot)
async def plots_handler(message: types.Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Вернуться в главное меню")
    markup.add(btn1)
    group_name = await db_manager.check_group_design(chat_id)
    if group_name is not None:
        pass#bot.register_next_step_handler(message, group_main)
    else:
        pass
    text = await bot_data_handler.set_plots(message)
    await message.answer(text, reply_markup=markup)


@dp.message_handler(Text(equals="❓ Режим отправки запроса"), state="*")
async def request_mode(message: types.Message, state: FSMContext):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 exit"))
    await message.reply("Отправьте запрoс. До получения ответа взаимодействие с ботом блокируется",
                        reply_markup=markup)
    await Form.question.set()


@dp.message_handler(Text(equals="Группы таблиц"), state="*")
async def group_options(message: types.Message, state: FSMContext):
    markup = await inline_keyboard_manager.create_group_keyboard(message.chat.id)
    await message.reply("Вы можете выбрать опцию", reply_markup=markup)
    await main_menu(message)


@dp.message_handler()
async def create_inline_keyboard(chat_id, page_type, page=1, group_mode=False):

    keyboard_types = ["table_page", "description_page", "context_page"]

    if page_type not in keyboard_types:
        raise ValueError("Invalid page type")

    return await inline_keyboard_manager.inline_keyboard(chat_id=chat_id, page_type=page_type, page=page,
                                                         status_flag=False)


@dp.message_handler(state=GroupForm)
async def create_group(message: types.Message, state: FSMContext):
    await db_manager.create_group(message.text, message.chat.id)
    await message.reply("Группа создана")
    await state.finish()



@dp.message_handler(Text(equals="Сохранить настройки группы"))
async def save_group(message: types.Message):
    link = await bot_data_handler.save_group_settings(message.chat.id)
    await message.reply("Изменения группы сохранены")
    await message.reply(f"Ссылка для группы: {link}")


@dp.message_handler(Text(equals="Доступные таблицы"))
async def list_tables(message: types.Message):
    tables = await bot_data_handler.get_table_names(message.chat.id, group_mode=True)
    if not tables:
        await message.reply("В группе пока нет доступных таблиц")
    else:
        await message.reply(f"Доступные таблицы: {', '.join(tables)}")


@dp.message_handler(Text(equals="exit"))
async def exit_group_mode(message: types.Message):
    await bot_data_handler.exit_from_group(message.chat.id)
    await message.reply("Редактирование группы завершено")


@dp.message_handler(state=Form.question)
async def call_to_model(message: types.Message, state: FSMContext):
    demo_status = await db_manager.check_for_demo(chat_id=message.chat.id)
    if demo_status is not None:
        pass
    if message.text == "🚫 exit":
        await bot_data_handler.exit_from_model(message.chat.id)
        await Form.start.set()
        await main_menu(message, state)

    elif message.text == "Нет":
        await main_menu(message)

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
