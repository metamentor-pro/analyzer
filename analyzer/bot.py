import os
import sys
import time
import requests
import logging
import traceback
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import aiosqlite
from dotenv import load_dotenv

import matplotlib
import re

import config
import tracemalloc

load_dotenv()
tracemalloc.start()
matplotlib.use('Agg')
logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")

if len(sys.argv) > 1:
    API_TOKEN = config.read_config(sys.argv[1])["bot_api"]
    config.config = config.read_config(sys.argv[1])
    db_name = config.config["db_name"]
else:
    API_TOKEN = config.config["bot_api"]
    db_name = config.config["db_name"]

import bot_data_handler
import inline_keyboard_manager
import db_manager

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
import telebot


class Bot(telebot.TeleBot):
    def __init__(self):
        super().__init__(API_TOKEN)


telebot_bot = Bot()


class Form(StatesGroup):
    working = State()
    start = State()
    load_table = State()
    choose_table = State()
    description = State()
    context = State()
    plot = State()
    request = State()
    question = State()


class GroupForm(StatesGroup):
    group_settings = State()
    group_menu = State()
    choose_group = State()
    create_group = State()


data_keys = {
    Form.load_table: "call_message_id"
}


@dp.message_handler(commands=["start"], state="*")
@dp.message_handler(state=[Form.start])
async def main_menu(message: types.Message, state: FSMContext):
    first_time = await bot_data_handler.make_insertion(message.chat.id)
    if first_time:
        await help_info(message)
    is_group = await db_manager.check_for_group(message)
    if is_group:
        markup = await bot_data_handler.start_markup(is_group=True)
    else:
        markup = await bot_data_handler.start_markup(is_group=False)
    text = "Вы можете выбрать одну из опций"
    await message.answer(text, reply_markup=markup)
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

    instructions = """
Для того, чтобы начать общение с ботом:
1) Нажмите кнопку 'Выбрать таблицу', затем добавьте новую таблицу или воспользуйтесь уже добавленной
2) После этого вы можете добавить описание и контекст к вашим данным для лучшей работы модели
3) Нажмите кнопку 'Режим отправки запроса' и напишите свой запрос модели, дождитесь ответа
4) После получения ответа можете задать вопрос или выйти из режима в главное меню

При общении с помощником желательно:
1) Как можно более полно и чётко формулировать запросы
2) Писать имена переменных полностью (названия продуктов, колонок и т.д)
3) Писать запросы последовательно
В случае неподходящего ответа лучше всего добавить к вопросу уточнения и отправить его ещё раз. Спасибо!"""

    await message.reply(instructions)

    trouble = "В случае проблем с ботом попробуйте перезапустить его через команду 'start'"
    await message.reply(trouble)


@dp.message_handler(Text(equals="📁 Выбрать таблицу"), state="*")
async def select_table(message: types.Message):
    markup = await create_inline_keyboard(message.chat.id, page_type="table_page")
    await message.reply("Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)


@dp.callback_query_handler(lambda query: query.data.startswith('t|'), state="*")
async def callback_query(call: types.CallbackQuery, state: FSMContext) -> None:
    action = call.data.split("|")[1]
    chat_id = call.message.chat.id
    call.data = action
    if action == "new_table":
        await call.message.answer("Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json")
        await Form.load_table.set()
        await state.update_data({'message_id': call.message.message_id})

    elif action == "delete_tables":
        tables = await bot_data_handler.delete_last_table(call.message.chat.id)
        await call.message.answer(f"Таблица {tables[-1]} удалена из текущего списка")

    elif action in ("right", "left"):
        amount = await inline_keyboard_manager.get_pages_amount(chat_id=chat_id, )
        page = await inline_keyboard_manager.get_page(chat_id=chat_id, page_type="table_page")
        new_page = page

        if page < amount:
            if action == "right":
                new_page = page + 1
        elif page > 1:
            new_page = page - 1

        await inline_keyboard_manager.change_page(call.message.chat.id, page_type="table_page", new_page=new_page)
        markup = await create_inline_keyboard(call.message.chat.id, page_type="table_page", page=new_page,
                                              status_flag=False)
        await call.message.edit_text("Вы можете выбрать таблицу или добавить новую",
                                     reply_markup=markup)
    elif action == "exit":
        await call.message.delete()
        await state.finish()
    else:
        await Form.choose_table.set()
        await choose_table(call, state)
    await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['document'], state=Form.load_table)
async def load_table(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    message = message
    data = await state.get_data()
    message_id = data.get("message_id")
    group_name = await db_manager.check_group_design(chat_id)
    if group_name is not None:
        group_id = await db_manager.get_group_id(group_name, chat_id)

    try:
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        downloaded_file = await bot.download_file_by_id(file.file_id)
        if len(message.document.file_name) > 40:
            await message.answer("К сожалению, название таблицы слишком длинное, придётся его сократить")

        else:
            message.document.file_name = str(chat_id) + "_" + message.document.file_name
            if group_name is not None:
                async with aiosqlite.connect(db_name) as con:
                    existing_record = await con.execute(
                        """SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ? and group_id == ?""",
                        (chat_id, message.document.file_name, group_id))
                    existing_record = await existing_record.fetchone()

                if existing_record is None:
                    await db_manager.add_table(message=message, downloaded_file=downloaded_file)
                    await message.reply('Файл сохранен')
                    page_type = "table_page"
                    markup2 = await create_inline_keyboard(chat_id=chat_id, page_type=page_type)
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                text="Вы можете выбрать таблицу или добавить новую",
                                                reply_markup=markup2)
                    await GroupForm.group_menu.set()
                    await group_main_menu(message, state)
                else:
                    await bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")

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
                        await bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                    text="Вы можете выбрать таблицу или добавить новую",
                                                    reply_markup=markup2)
                        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                        btn1 = types.KeyboardButton("Нет")
                        btn2 = types.KeyboardButton("Да")
                        markup.row(btn2, btn1)
                        await bot.send_message(chat_id, "Хотите ли вы получить предварительную информацию по таблице?",
                                               reply_markup=markup)
                        await Form.question.set()
                    else:
                        await bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")

    except Exception as e:
        print(e)
        await bot.send_message(chat_id, "Что-то пошло не так, попробуйте другой файл")
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        await Form.question.set()


@dp.message_handler(state=Form.choose_table)
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
    await Form.working.set()


@dp.message_handler(Text(equals="➕ Добавить контекст"), state="*")
async def add_description(message: types.Message, state: FSMContext):
    markup = await create_inline_keyboard(message.chat.id, page_type="context_page")

    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)


@dp.callback_query_handler(Text(startswith="c|"), state="*")
async def callback_query(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("|")[1]
    chat_id = call.message.chat.id
    call.data = action

    if action in ("right", "left"):
        amount = await inline_keyboard_manager.get_pages_amount(chat_id=chat_id, )
        page = await inline_keyboard_manager.get_page(chat_id=chat_id, page_type="context_page")
        new_page = page
        if page < amount:
            if action == "right":
                new_page = page + 1
        elif page > 1:
            new_page = page - 1

        await inline_keyboard_manager.change_page(call.message.chat.id, page_type="context_page", new_page=new_page)
        markup = await create_inline_keyboard(call.message.chat.id, page_type="context_page", page=new_page)
        await call.message.edit_text(text="Вы можете выбрать таблицу или добавить новую",
                                     reply_markup=markup)

    elif action == "exit":
        await call.message.delete()
        await state.finish()

    else:
        await call.message.answer(f"Таблица {action} выбрана, отправьте контекст в формате txt")
        await Form.context.set()
        await state.update_data({"table_name": call.data})
    await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['text', 'document'], state=Form.context)
async def save_context(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    try:
        data = await state.get_data()
        table_name = data.get("table_name")
        group_name = await db_manager.check_group_design(chat_id)
        if message.content_type == "text":
            await db_manager.add_context(message=message, table_name=table_name)
            if group_name is not None:
                await group_main_menu(message, state)
            else:
                await main_menu(message, state)
            await bot.send_message(message.chat.id, text='Контекст сохранен')
        elif message.content_type == "document":
            file_id = message.document.file_id
            file = await bot.get_file(file_id)
            downloaded_file = await bot.download_file_by_id(file.file_id)
            await db_manager.add_context(message=message, table_name=table_name, downloaded_file=downloaded_file)
            if group_name is not None:
                await GroupForm.group_menu.set()
                await group_main_menu(message, state)
            else:
                await Form.start.set()
                await main_menu(message, state)
            await bot.send_message(chat_id, 'Контекст сохранен')
    except Exception as e:
        print(e)
        await bot.send_message(chat_id, "Что-то пошло не так, попробуйте другой файл")
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        await Form.context.set()


@dp.message_handler(Text(equals="➕ Добавить описание таблицы"), state="*")
async def description(message: types.Message, state: FSMContext):
    markup = await create_inline_keyboard(message.chat.id, page_type="description_page")
    await message.reply(text="Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)


@dp.callback_query_handler(Text(startswith="d|"), state="*")
async def callback_query(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("|")[1]
    call.data = action
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

        await inline_keyboard_manager.change_page(call.message.chat.id, page_type="description_page", new_page=new_page)
        markup = await create_inline_keyboard(call.message.chat.id, page_type="description_page", page=new_page)
        await call.message.edit_text(text="Вы можете выбрать таблицу или добавить новую",
                                     reply_markup=markup)
    elif action == "exit":
        await call.message.delete()
        await state.finish()

    else:
        await call.message.answer(
            f"Таблица {action} выбрана, отправьте описание в формате txt или текстовым сообщением")
        await Form.description.set()
        await state.update_data({'table_name': call.data})
    await bot.answer_callback_query(call.id)


@dp.message_handler(content_types=['text', 'document'], state=Form.description)
async def save_description(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    data = await state.get_data()
    table_name = data.get("message_id")
    try:
        group_name = await db_manager.check_group_design(chat_id)
        if message.content_type == "text":
            await db_manager.choose_description_db(message=message, table_name=table_name)
            if group_name is not None:
                await group_main_menu(message, state)
            else:
                await main_menu(message, state)
            await bot.send_message(message.chat.id, text='Контекст сохранен')
        elif message.content_type == "document":
            file_id = message.document.file_id
            file = await bot.get_file(file_id)
            downloaded_file = await bot.download_file_by_id(file.file_id)
            await db_manager.choose_description_db(message=message, table_name=table_name,
                                                   downloaded_file=downloaded_file)
            if group_name is not None:
                await group_main_menu(message, state)
            else:
                await main_menu(message, state)
            await bot.send_message(chat_id, text='Контекст сохранен')
    except Exception as e:
        await bot.send_message(message.chat.id, text="Что-то пошло не так, попробуйте другой файл")
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        await Form.question.set()


@dp.message_handler(Text(equals="📈 Режим визуализации"), state="*")
async def plot_on_click(message: types.Message, state: FSMContext) -> None:
    # todo: we should add an inline keyboard here instead and not change the buttons
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
    group_name = await db_manager.check_group_design(chat_id)
    text = await bot_data_handler.set_plots(message)
    await message.answer(text)
    await state.finish()
    if group_name is not None:
        await group_main_menu(message, state)
    else:
        await main_menu(message, state)


@dp.message_handler(Text(equals="❓ Режим отправки запроса"), state="*")
async def request_mode(message: types.Message, state: FSMContext):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 exit"))
    await message.reply(text="Отправьте Ваш запрос",
                        reply_markup=markup)
    await Form.question.set()


@dp.message_handler(Text(equals="🗄️ Группы таблиц"), state="*")
async def group_options(message: types.Message, state: FSMContext):
    markup = await inline_keyboard_manager.create_group_keyboard(message.chat.id)
    await message.reply(text="Вы можете выбрать опцию", reply_markup=markup)


@dp.message_handler(state=GroupForm.group_menu)
async def group_main_menu(message: types.Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    group_name = await db_manager.check_group_design(chat_id)
    async with aiosqlite.connect(db_name) as con:
        await con.execute("select * from groups")
        if message.text == "Нет":
            await con.execute("UPDATE groups SET design_flag = False WHERE admin_id == ? AND group_name == ?",
                              (chat_id, group_name))
            await con.commit()
            await main_menu(message, state)
        else:
            print("да")
            chat_id = message.chat.id
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn1 = types.KeyboardButton("📁 Выбрать таблицу")
            btn2 = types.KeyboardButton("➕ Добавить описание таблицы")
            btn3 = types.KeyboardButton("📈 Режим визуализации")
            btn4 = types.KeyboardButton("exit")
            btn5 = types.KeyboardButton("➕ Добавить контекст")
            btn6 = types.KeyboardButton("Сохранить настройки группы")
            markup.row(btn1, btn2, btn3)
            markup.row(btn5, btn4, btn6)
            await GroupForm.group_settings.set()
            await bot.send_message(chat_id, text="Вы можете  выбрать одну из опций:", reply_markup=markup)


@dp.callback_query_handler(Text(startswith="g|"), state='*')
async def callback_query(call: types.CallbackQuery, state: FSMContext) -> None:
    callback_type, action = map(str, call.data.split("|"))
    call.data = action
    chat_id = call.message.chat.id
    if call.data == "exit":
        await bot_data_handler.exit_from_group(chat_id=chat_id)
        await bot.delete_message(call.message.chat.id, call.message.message_id)
    elif call.data == "create_group":
        await bot.send_message(chat_id, text="Дайте название группе")
        await GroupForm.create_group.set()
    elif call.data == "choose_group":

        markup = await inline_keyboard_manager.create_group_keyboard(chat_id=chat_id, show_groups=True)
        await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Вы можете выбрать группу",
                                    reply_markup=markup)
    elif call.data == "back":
        markup = await inline_keyboard_manager.create_group_keyboard(chat_id=chat_id, show_groups=False)
        await bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                    text="Вы можете выбрать группу или добавить новую",
                                    reply_markup=markup)
    else:

        await GroupForm.choose_group.set()
        await choose_group(chat_id, call, state)
    await bot.answer_callback_query(call.id)


@dp.message_handler(state=GroupForm.create_group)
async def create_group(message: types.Message, state: FSMContext) -> None:
    admin_id = message.chat.id
    group_name = message.text.replace(" ", "")
    group_name_for_link = "group_" + str(admin_id)
    text = await db_manager.create_group(admin_id=admin_id, group_name=group_name,
                                         group_name_for_link=group_name_for_link)
    await bot.send_message(admin_id, text)
    await main_menu(message, state)


@dp.message_handler(state=GroupForm.choose_group)
async def choose_group(admin_id: int = None, call: types.CallbackQuery = None, state: FSMContext = None) -> None:
    group_name = call.data
    await db_manager.choose_group_db(admin_id=admin_id, group_name=group_name)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Да")
    btn2 = types.KeyboardButton("Нет")
    markup.row(btn1, btn2)
    await bot.send_message(admin_id, text=f"Вы точно ходите перейти к редактированию группы {group_name}?",
                           reply_markup=markup)
    await GroupForm.group_menu.set()


@dp.message_handler(Text(equals="Сохранить настройки группы"), state="*")
async def save_group_settings(message: types.Message, state: FSMContext) -> None:
    group_name = await db_manager.check_group_design(message.chat.id)
    group_link = await db_manager.save_group_settings(chat_id=message.chat.id, group_name=group_name)
    await bot.send_message(message.chat.id, text="Изменения группы сохранены, ссылка для взаимодействия с группой: ")
    await bot.send_message(message.chat.id, text=f'{group_link}')
    await main_menu(message, state)


@dp.message_handler(Text(equals="Доступные таблицы"), state="*")
async def group_table_list(message: types.Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    prepared_settings = await bot_data_handler.settings_prep(chat_id)
    if not prepared_settings:
        await bot.send_message(chat_id, text="В данной группе пока нет доступных таблиц")
    else:
        await bot.send_message(chat_id, text=f"Доступные таблицы: {prepared_settings}")


@dp.message_handler(Text(equals="exit"), state="*")
async def exit_group_mode(message: types.Message, state: FSMContext):
    await bot_data_handler.exit_from_group(message.chat.id)
    await message.reply("Редактирование группы завершено")
    await Form.start.set()
    await main_menu(message, state)


@dp.message_handler(content_types=['photo', 'document', 'text'], state=Form.question)
async def call_to_model(message: types.Message, state: FSMContext):
    demo_status = await db_manager.check_for_demo(chat_id=message.chat.id)
    if demo_status is not None:
        pass
    if message.content_type != "text":
        await bot.send_message(chat_id=message.chat.id, text="В качестве запроса принимаются только текстовые данные")
        return
    if message.text == "🚫 exit":
        await bot_data_handler.exit_from_model(message.chat.id)
        await bot_data_handler.stop_process()
        await Form.start.set()
        await main_menu(message, state)
        return

    elif message.text == "Нет":
        await bot_data_handler.exit_from_model(message.chat.id)
        await Form.start.set()
        await main_menu(message, state)
        return

    else:
        asyncio.create_task(process_model(message, state))


async def process_model(message, state):
    if message.text == "Да":
        user_question = "Проведи исследовательский анализ данных по таблице"
    else:
        user_question = message.text

    chat_id = message.chat.id
    settings = await db_manager.get_settings(chat_id)
    try:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        if settings["table_name"] is None or settings["table_name"] == "":
            await message.answer("Таблицы не найдены, вы можете выбрать другие")
            await message.answer(text="Вы можете выйти из режима работы с моделью с помощью 'exit'",
                                 reply_markup=markup)
        else:
            await message.answer(text="Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью 'exit'",
                                 reply_markup=markup)
            await message.answer("Учтите, что первичная обработка больших таблиц может занять несколько минут, спасибо")
            send_message = await message.answer("Здесь будет описан процесс моих рассуждений:")

            def callback(sum_on_step):
                message_id = send_message.message_id
                telebot_bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                              text=send_message.text + f"\n{sum_on_step}")

            answer_from_model = await bot_data_handler.model_call(chat_id=chat_id, user_question=user_question,
                                                                  callback=callback)
            if answer_from_model[0] == "F":
                await message.answer("Что-то пошло не так, повторяю запрос")
                answer_from_model = await bot_data_handler.model_call(chat_id=chat_id, user_question=user_question,
                                                                      callback=callback)
            if answer_from_model[0] == "F":
                await message.answer("Что-то пошло не так")

            current_summary = await bot_data_handler.get_summary(chat_id)
            summary = answer_from_model[1]
            new_summary = current_summary + summary
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
    except requests.exceptions.ConnectionError:
        await message.answer("Что-то пошло не так, пожалуйста, повторите вопрос или используйте команду start")
    except Exception:
        logging.error(traceback.format_exc())
        print(traceback.format_exc())


@dp.message_handler(state='*')
async def unknown_message(message: types.Message, state: FSMContext):
    await message.reply("Извините, я вас не понимаю. Воспользуйтесь кнопками меню.")


@dp.message_handler(state="*")
async def create_inline_keyboard(chat_id, page_type, page=1, status_flag: bool = True):
    keyboard_types = ["table_page", "description_page", "context_page"]

    if page_type not in keyboard_types:
        raise ValueError("Invalid page type")
    if page_type == "table_page":
        settings = await db_manager.get_settings(chat_id)
        if settings["table_name"] is not None and len(settings["table_name"]) > 0:
            if status_flag:
                settings_prep = await bot_data_handler.settings_prep(chat_id)
                settings["table_name"] = settings_prep
                await bot.send_message(chat_id, text=f"Сейчас доступны для анализа: {settings['table_name']}")
    return await inline_keyboard_manager.inline_keyboard(chat_id=chat_id, page_type=page_type, page=page,
                                                         status_flag=False)


async def main():
    while True:
        try:
            await dp.start_polling()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(traceback.format_exc())
            logging.error(traceback.format_exc())
            await dp.start_polling()


if __name__ == "__main__":
    asyncio.run(main())
