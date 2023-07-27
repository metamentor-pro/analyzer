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
import bot_data_handler

logging.basicConfig(level=logging.INFO)

API_TOKEN = config.read_config(sys.argv[1])["bot_api"]

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


class Form(StatesGroup):
    table_name = State()  
    description = State()
    context = State()


@dp.message_handler(commands=['start', 'help'])
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
    markup = await bot_data_handler.create_inline_keyboard(message.chat.id, "table_page") 

    await message.reply("Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)

    
@dp.callback_query_handler(Text(startswith="t|"), state=Form.table_name)
async def choose_table(call: types.CallbackQuery):
    action = call.data.split("|")[1]
    
    if action == "new_table":
        await call.message.answer("Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json")
        await Form.table_name.set()
        
    elif action == "delete_tables":
        tables = await bot_data_handler.delete_last_table(call.message.chat.id)
        await call.message.answer(f"Таблица {tables[-1]} удалена из текущего списка")
        
    elif action in ("right", "left"):  
        page = await bot_data_handler.change_page(call.message.chat.id, "table_page", action)
        markup = await bot_data_handler.create_inline_keyboard(call.message.chat.id, 
                                                              "table_page", page)
        await call.message.edit_text("Вы можете выбрать таблицу или добавить новую", 
                                     reply_markup=markup)
                                     
    else:
        await bot_data_handler.choose_table(call.data, call.message)
        await call.message.answer("Таблица выбрана")
        await state.finish()
        
    await bot.answer_callback_query(call.id)

    
@dp.message_handler(content_types=['document'], state=Form.table_name)
async def load_table(message: types.Message):
    await bot_data_handler.add_table(message)
    await message.reply("Файл сохранен")
    await state.finish()

    
@dp.message_handler(Text(equals="➕ Добавить описание таблицы"))
async def add_description(message: types.Message):
    await Form.description.set()
    
    markup = await bot_data_handler.create_inline_keyboard(message.chat.id, "description_page")
    await message.reply("Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)

    
@dp.callback_query_handler(Text(startswith="d|"), state=Form.description)  
async def choose_description(call: types.CallbackQuery):
    action = call.data.split("|")[1]
    
    if action in ("right", "left"):
        page = await bot_data_handler.change_page(call.message.chat.id, "description_page", action)
        markup = await bot_data_handler.create_inline_keyboard(call.message.chat.id, 
                                                              "description_page", page)
        await call.message.edit_text("Выберите таблицу для описания", reply_markup=markup)
        
    elif action == "exit":
        await call.message.delete()
        await state.finish()
        
    else:
        await call.message.answer(f"Таблица {action} выбрана, отправьте описание в формате txt")
        await Form.next()
        await bot.answer_callback_query(call.id)

        
@dp.message_handler(content_types=['text', 'document'], state=Form.description)
async def save_description(message: types.Message):
    table_name = message.text
    await bot_data_handler.choose_description(message, table_name)
    await message.reply("Описание сохранено")
    await state.finish()

    
@dp.message_handler(Text(equals="Добавить контекст"))
async def add_context(message: types.Message):
    await Form.context.set()
    
    markup = await bot_data_handler.create_inline_keyboard(message.chat.id, "context_page")
    await message.reply("Выберите, к какой таблице вы хотите добавить контекст", reply_markup=markup)

    
@dp.callback_query_handler(Text(startswith="c|"), state=Form.context)
async def choose_context(call: types.CallbackQuery):
    action = call.data.split("|")[1]
    
    if action in ("right", "left"):
        page = await bot_data_handler.change_page(call.message.chat.id, "context_page", action)
        markup = await bot_data_handler.create_inline_keyboard(call.message.chat.id, 
                                                              "context_page", page)
        await call.message.edit_text("Выберите таблицу для контекста", reply_markup=markup)
        
    elif action == "exit":
        await call.message.delete()
        await state.finish()
        
    else:
        await call.message.answer(f"Таблица {action} выбрана, отправьте контекст в формате txt") 
        await Form.next()
        await bot.answer_callback_query(call.id)

        
@dp.message_handler(content_types=['text', 'document'], state=Form.context)  
async def save_context(message: types.Message):
    table_name = message.text
    await bot_data_handler.add_context(message, table_name)
    await message.reply("Контекст сохранен")
    await state.finish()

    
@dp.message_handler(Text(equals="🖻 Режим визуализации"))
async def toggle_plots(message: types.Message):
    text = await bot_data_handler.set_plots(message)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Вернуться в главное меню"))  
    await message.reply(text, reply_markup=markup)

    
@dp.message_handler(Text(equals="❓ Режим отправки запроса"))
async def request_mode(message: types.Message):
    await bot_data_handler.set_request_mode(message.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚫 exit"))
    await message.reply("Отправьте запрoс. До получения ответа взаимодействие с ботом блокируется",
                        reply_markup=markup)
    
    
@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return

    logging.info('Cancelling state %r', current_state)
    await state.finish()
    await message.reply('Отменено', reply_markup=types.ReplyKeyboardRemove())

    
@dp.message_handler(state=bot_data_handler.RequestForm.request)
async def call_model(message: types.Message, state: FSMContext):
    if message.text == "🚫 exit":
        await bot_data_handler.exit_request_mode(message.chat.id)
        await state.finish()
        await start_command(message)
        
    else:
        await message.reply("Обрабатываю запрос...")
        
        summary = await bot_data_handler.get_summary(message.chat.id)
        answer, new_summary = await bot_data_handler.query_model(message.text, message.chat.id, summary)
        
        await state.update_data(answer=answer)
        
        if ".png" in answer:
            pattern = r"[\w.-]+\.png"
            plot_files = re.findall(pattern, answer)
            for plot in plot_files:
                try:
                    await message.answer_photo(open(f"Plots/{plot}", 'rb'))
                except Exception:
                    pass
            
            matplotlib.pyplot.close('all')
            
        await message.reply(f"Ответ: {answer}")
        await bot_data_handler.update_summary(message.chat.id, new_summary)
        
        await Form.request.set()
        

@dp.message_handler()
async def unknown_message(message: types.Message):
    await message.reply("Извините, я вас не понимаю. Воспользуйтесь кнопками меню.")
    

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
</file-attachment-contents>

<file-attachment-contents filename="bot_data_handler.py">
import aiosqlite

from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram import types

import interactor
import config

db_name = config.read_config("config.yaml")["db_name"] 

class RequestForm(StatesGroup):
    request = State()
    
    
async def make_insertion(user_id: int) -> bool:
    async with aiosqlite.connect(db_name) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS users"
                         "(user_id INTEGER PRIMARY KEY,"
                         "conv_sum TEXT,"
                         "current_tables VARCHAR,"
                         "build_plots INTEGER DEFAULT 1)")
                         
        await db.execute("CREATE TABLE IF NOT EXISTS callback_manager"
                         "(user_id INTEGER PRIMARY KEY,"
                         "table_page INTEGER DEFAULT 1,"
                         "context_page INTEGER DEFAULT 1,"
                         "description_page INTEGER DEFAULT 1,"
                         "group_flag INTEGER DEFAULT 0,"
                         "group_name VARCHAR)")
                         
        insertion = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = await insertion.fetchone()
        
        if result is None:
            await db.execute("INSERT INTO users(user_id) VALUES (?)", (user_id,))
            await db.commit()
            return True
        
    return False
    
    
async def create_inline_keyboard(chat_id, page_type, page=1, group_mode=False):
    keyboard_types = {
        "table_page": await get_tables_keyboard,
        "context_page": await get_context_keyboard,
        "description_page": await get_description_keyboard
    }
    
    create_keyboard = keyboard_types.get(page_type)
    if not create_keyboard:
        raise ValueError("Invalid page type")
        
    return await create_keyboard(chat_id, page, group_mode)

    
async def get_tables_keyboard(chat_id, page, group_mode):
    tables = await get_table_names(chat_id)
    
    if not tables:
        tables_text = "Таблицы не найдены" 
    else:
        tables_per_page = 3
        total_pages = len(tables) // tables_per_page + 1
        tables_text = "Вы можете выбрать таблицу или добавить новую"
        
        if page > total_pages:
            page = total_pages
            
        start_index = (page - 1) * tables_per_page
        end_index = page * tables_per_page
            
        tables = tables[start_index:end_index]
            
    markup = types.InlineKeyboardMarkup()
            
    for table in tables:
        markup.insert(types.InlineKeyboardButton(table, callback_data=f"t|{table}")) 
        
    markup.row(
        types.InlineKeyboardButton("Добавить таблицу", callback_data="t|new_table"),
        types.InlineKeyboardButton("Удалить таблицу", callback_data="t|delete_tables")
    )
    
    if total_pages > 1:
        markup.row(
            types.InlineKeyboardButton("<", callback_data=f"t|left"),
            types.InlineKeyboardButton(">", callback_data=f"t|right")
        )
        
    markup.insert(types.InlineKeyboardButton("Выход", callback_data="t|exit"))
    
    return markup

    
async def get_context_keyboard(chat_id, page, group_mode):
    tables = await get_table_names(chat_id, group_mode)
    
    if not tables:
        tables_text = "Таблицы не найдены"
    else:
        tables_per_page = 3
        total_pages = len(tables) // tables_per_page + 1
        tables_text = "Выберите таблицу для контекста"
        
        if page > total_pages:
            page = total_pages
            
        start_index = (page - 1) * tables_per_page
        end_index = page * tables_per_page
            
        tables = tables[start_index:end_index]
            
    markup = types.InlineKeyboardMarkup()
            
    for table in tables:
        markup.insert(types.InlineKeyboardButton(table, callback_data=f"c|{table}"))

    if total_pages > 1:
        markup.row(
            types.InlineKeyboardButton("<", callback_data=f"c|left"), 
            types.InlineKeyboardButton(">", callback_data=f"c|right")
        )
        
    markup.insert(types.InlineKeyboardButton("Выход", callback_data="c|exit"))
    
    return markup

@dp.callback_query_handler(Text(startswith="g|"))
async def group_actions(call: types.CallbackQuery):
    action = call.data.split("|")[1]
    
    if action == "exit":
        await bot_data_handler.exit_group_mode(call.message.chat.id)
        await call.message.delete()
        
    elif action == "create_group":
        await call.message.answer("Дайте название группе")
        await GroupForm.group_name.set()
        
    elif action == "choose_group":
        markup = await bot_data_handler.create_group_keyboard(call.message.chat.id, show_groups=True)
        await call.message.edit_text("Выберите группу", reply_markup=markup)
        
    elif action == "back":
        markup = await bot_data_handler.create_group_keyboard(call.message.chat.id)
        await call.message.edit_text("Выберите группу или создайте новую", reply_markup=markup)
        
    else:
        await bot_data_handler.choose_group(action, call.message.chat.id, call.message)
        await call.message.answer(f"Переход к группе {action}")
    
    await bot.answer_callback_query(call.id)

    
class GroupForm(StatesGroup):
    group_name = State()

    
@dp.message_handler(state=GroupForm.group_name)  
async def create_group(message: types.Message, state: FSMContext):
    await bot_data_handler.create_group(message.text, message.chat.id)
    await message.reply("Группа создана")
    await state.finish()

    
@dp.message_handler(Text(equals="Группы таблиц"))
async def group_options(message: types.Message):
    markup = await bot_data_handler.create_group_keyboard(message.chat.id)
    await message.reply("Вы можете выбрать опцию", reply_markup=markup)

    
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
    await bot_data_handler.exit_group_mode(message.chat.id)
    await start_command(message)
    await message.reply("Редактирование группы завершено")

    
@dp.message_handler(state='*')
async def unknown_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.reply("Извините, я вас не понимаю. Воспользуйтесь кнопками меню.")
    else:
        await message.reply("Пожалуйста, сначала завершите текущее действие")

        
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

