from db_manager import *
import interactor


def get_context(chat_id: int =None) -> List:
    settings = get_settings(chat_id)
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))
    table_name = list(map(str, settings["table_name"].split(",")))

    group_flag = cur.fetchone()[0]
    context_list = []

    if group_flag == True:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        chat_id = cur.fetchone()[0]
        for table in table_name:
            cur.execute("SELECT context from group_tables WHERE admin_id == ? AND  group_name == ?", (chat_id, group_name))
            context = cur.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)

    else:
        for table in table_name:
            cur.execute("SELECT context FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
            context = cur.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)
    con.close()
    return context_list


def get_description(chat_id: int = None) -> List:
    settings = get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_name_path = table_name.copy()
    table_description = []

    for table in range(len(table_name_path)):
        table_name_path[table] = "data/" + table_name_path[table]
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = cur.fetchone()[0]
    if group_flag == True:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = cur.fetchone()[0]
        con.close()
        for table in table_name:
            con = sq.connect(db_name)

            cur = con.cursor()
            cur.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ? AND group_name == ?", (admin_id, table, group_name))
            existing_record = cur.fetchone()

            if existing_record is not None:

                cur.execute("SELECT table_description FROM group_tables WHERE admin_id == ? AND table_name == ? AND group_name  == ?",  (admin_id, table, group_name))
                description = cur.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]

                table_description.append(table_description_line)

            con.commit()

    else:
        for table in table_name:
            con = sq.connect(db_name)
            cur = con.cursor()
            cur.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
            existing_record = cur.fetchone()

            if existing_record is not None:

                cur.execute(
                    "SELECT table_description FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, table))
                description = cur.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]

                table_description.append(table_description_line)

                print("table description:", table_description)
            con.commit()
    con.close()
    return table_description


def get_summary(chat_id: int) -> str:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = cur.fetchone()[0]
    con.commit()
    if group_flag == True:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = cur.fetchone()[0]
        cur.execute("SELECT group_conv FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
        current_summary = cur.fetchone()
    else:

        cur.execute("SELECT conv_sum FROM users WHERE user_id = ?", (chat_id,))
        current_summary = cur.fetchone()

    if not current_summary or current_summary[0] is None:
        current_summary = ""
    else:
        current_summary = current_summary[0][:250] + current_summary[0][-500:]
    return current_summary

def settings_prep(chat_id: int):
    settings = get_settings(chat_id)
    if settings["table_name"] is None:
        return False
    table_name = list(map(str, settings["table_name"].split(",")))
    for i in range(len(table_name)):
        prep_name = list(table_name[i].split("_"))
        table_name[i] = "_".join(prep_name[1:])
    return ",".join(table_name)


def delete_last_table(chat_id : int = None) -> List[str]:
    settings = get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_name = table_name[:-1]
    if len(table_name) == 0:
        settings["table_name"] = ''
    else:
        settings["table_name"] = ''
        for i in range(len(table_name) - 1):
            settings["table_name"] += table_name[i] + ","
        settings["table_name"] += table_name[-1]

    con = sq.connect(db_name)
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if group_name is not None:
        cur.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?",
                    (settings["table_name"], chat_id, group_name))
        con.commit()
    else:
        cur.execute("UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
        con.commit()

    con.close()
    return table_name



def exit_from_group_db(chat_id: int = None) -> None:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (chat_id,))
    con.commit()
    con.close()


def exit_from_model(chat_id: int = None) -> None:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (chat_id,))
    con.commit()
    con.close()

def make_insertion(chat_id: int = None) -> bool:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()
    try:
        if not existing_record:
            cur.execute("INSERT  INTO callback_manager(user_id) VALUES(?)", (int(chat_id),))
        con.commit()
    except Exception as e:
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        con.close()

    cur.execute("SELECT * FROM users WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()

    try:
        if not existing_record:
            cur.execute("""INSERT INTO users(user_id) values(?)""", (chat_id,))
            con.commit()
            con.close()
            return True
        con.commit()
        con.close()
    except Exception as e:
        print(traceback.format_exc())
        print("error is:", e)
        logging.error(traceback.format_exc())
        con.close()


def model_call(chat_id, user_question, callback):
    settings = get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    print("available tables for model:", table_name)
    table_name_path = table_name.copy()
    for table in range(len(table_name_path)):
        table_name_path[table] = "data/" + table_name_path[table].strip()

    table_description = get_description(chat_id)
    context_list = get_context(chat_id)
    current_summary = get_summary(chat_id)

    build_plots = settings["build_plots"]

    answer_from_model = interactor.run_loop_bot(table_name_path, build_plots, user_question, current_summary,
                                                table_description, context_list, callback=callback)
    return answer_from_model


import aiosqlite

from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram import types

import interactor
import config

db_name = config.read_config("config.yaml")["db_name"]

class RequestForm(StatesGroup):
    request = State()


class GroupForm(StatesGroup):
    group_name = State()


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
    tables = await get_table_names(chat_id, group_mode)

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


async def get_description_keyboard(chat_id, page, group_mode):
    # Same logic as other keyboards

    tables = await get_table_names(chat_id, group_mode)

    markup = types.InlineKeyboardMarkup()

    for table in tables:
        markup.insert(types.InlineKeyboardButton(table, callback_data=f"d|{table}"))

    if total_pages > 1:
        markup.row(
            types.InlineKeyboardButton("<", callback_data=f"d|left"), 
            types.InlineKeyboardButton(">", callback_data=f"d|right")
        )
        
    markup.insert(types.InlineKeyboardButton("Выход", callback_data="d|exit"))

    return markup


async def get_table_names(chat_id, group_mode=False):
    async with aiosqlite.connect(db_name) as db:
        if group_mode:
            group_name = await in_group(chat_id)
            query = "SELECT table_name FROM group_tables WHERE group_name = ?"
            args = (group_name,)
        else:
            query = "SELECT current_tables FROM users WHERE user_id = ?"
            args = (chat_id,)

        async with db.execute(query, args) as cursor:
            tables = await cursor.fetchall()
            if tables:
                tables = [table[0].split(",") for table in tables][0]
            else:
                tables = []

        return tables


async def in_group(chat_id):
    async with aiosqlite.connect(db_name) as db:
        row = await db.execute("SELECT group_name FROM callback_manager WHERE user_id = ?", (chat_id,))
        group_name = await row.fetchone()
        if group_name:
            return group_name[0]


async def add_table(message: Message):
    chat_id = message.chat.id
    file_id = message.document.file_id
    file_info = await bot.get_file(file_id)
    downloaded_file = await bot.download_file(file_info.file_path)

    async with aiosqlite.connect(db_name) as db:
        await db.execute("INSERT INTO tables VALUES (?, ?)", (chat_id, message.document.file_name))
        await db.commit()

    await message.reply("Файл сохранен")


async def choose_table(table_name: str, message: Message):
    chat_id = message.chat.id
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE users SET current_tables=? WHERE user_id=?", 
                         (table_name, chat_id))
        await db.commit()
    
    await message.answer("Таблица выбрана")
    

async def change_page(chat_id, page_type, action):
    if action == "left":
        new_page = page - 1
    elif action == "right":
        new_page = page + 1
        
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE callback_manager SET ?_page=? WHERE user_id=?",
                         (page_type, new_page, chat_id))
        await db.commit()
        
    return new_page
    


async def choose_description(message: Message, table_name: str):
    chat_id = message.chat.id
    description = message.text if message.content_type == "text" else message.document.file_name
    
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE tables SET table_description=? WHERE table_name=? AND user_id=?", 
                    (description, table_name, chat_id))
        await db.commit()
        
    await message.reply("Описание сохранено")

    
async def add_context(message: Message, table_name: str):
    chat_id = message.chat.id
    context = message.text if message.content_type == "text" else message.document.file_name

    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE tables SET context=? WHERE table_name=? AND user_id=?",
                    (context, table_name, chat_id))
        await db.commit()
        
    await message.reply("Контекст сохранен")
    
# Other functions like create_group, choose_group etc

async def create_group(group_name: str, chat_id: int):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("INSERT INTO groups VALUES (?, ?)", (group_name, chat_id))
        await db.commit()
        
    await bot.send_message(chat_id, "Группа создана")

    
async def choose_group(group_name: str, chat_id: int, message: Message):
    await bot_data_handler.choose_group(group_name, chat_id)
        
    await message.answer(f"Переход к группе {group_name}")

async def set_plots(message: Message):
    chat_id = message.chat.id
    
    if message.text == "Включить":
        text = "Режим визуализации включен"
        build_plots = 1
    else:
        text = "Режим визуализации отключен"
        build_plots = 0
        
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE users SET build_plots=? WHERE user_id=?",
                         (build_plots, chat_id))
        await db.commit()
        
    return text
    

async def set_request_mode(chat_id):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("INSERT INTO callback_manager(user_id) VALUES (?)", (chat_id,))
        await db.commit()
        
    await RequestForm.request.set()

    
async def exit_request_mode(chat_id):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("DELETE FROM callback_manager WHERE user_id=?", (chat_id,))
        await db.commit()
        
    await RequestForm.request.finish()
    
    
async def get_summary(chat_id):
    async with aiosqlite.connect(db_name) as db:
        row = await db.execute("SELECT conv_sum FROM users WHERE user_id=?", (chat_id,))
        summary = await row.fetchone()
        if summary:
            return summary[0]
        else:
            return ""


async def update_summary(chat_id, new_summary):
    async with aiosqlite.connect(db_name) as db:
        await db.execute("UPDATE users SET conv_sum=? WHERE user_id=?",
                         (new_summary, chat_id))
        await db.commit()
        

async def query_model(question, chat_id, summary):
    settings = await get_settings(chat_id)
    
    tables = [f"data/{table}" for table in settings["tables"]] 
    plots = settings["build_plots"]
        
    context = await get_context(chat_id)
    descriptions = await get_descriptions(chat_id)
    
    answer, new_summary = await interactor.query(question, summary, 
                                                 tables, plots, context,
                                                 descriptions)
                                                 
    return answer, new_summary
    
    

