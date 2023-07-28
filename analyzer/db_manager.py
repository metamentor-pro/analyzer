import aiosqlite
import yaml
import chardet
from typing import Union, Callable, List
from msg_parser import msg_to_string
import config
import traceback
import logging
import sqlite3 as sq
logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

bot_name = config.config["bot_name"]
bot_api = config.config["bot_api"]
demo = config.config["demo"][0]
max_requests = config.config["demo"][1]
reset = config.config["demo"][2]
db_name = config.config["db_name"]

connection = sq.connect(db_name)

connection.execute("""CREATE TABLE IF NOT EXISTS users
              (user_id INTEGER PRIMARY KEY,
              conv_sum TEXT,
              current_tables VARCHAR,
              build_plots boolean DEFAULT 1
              )""")
connection.commit()

connection.execute("""CREATE TABLE IF NOT EXISTS groups
              (group_id INTEGER PRIMARY KEY AUTOINCREMENT,
              admin_id INTEGER,
              group_plot boolean DEFAULT 1,
              group_name VARCHAR,
              group_link VARCHAR,
              group_conv TEXT,
              current_tables VARCHAR,
              design_flag boolean DEFAULT 0)""")
connection.commit()

connection.execute("""CREATE TABLE IF NOT EXISTS callback_manager
              (user_id INTEGER PRIMARY KEY,
              table_page INTEGER DEFAULT 1,
              context_page INTEGER DEFAULT 1,
              description_page INTEGER DEFAULT 1,
              group_flag boolean DEFAULT 0,
              group_name VARCHAR,
              admin_id INTEGER,
              req_count INTEGER DEFAULT 0,
              FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
connection.commit()

connection.execute("""CREATE TABLE IF NOT EXISTS group_manager
                                  (admin_id INTEGER,
                                  group_name,
                                  table_page INTEGER DEFAULT 1,
                                  context_page INTEGER DEFAULT 1,
                                  description_page INTEGER DEFAULT 1)
                                  """)
connection.commit()

connection.execute(""" CREATE TABLE IF NOT EXISTS tables 
                (table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, 
                table_name VARCHAR,
                table_description TEXT,
                context TEXT,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
connection.commit()

connection.execute("""CREATE TABLE IF NOT EXISTS group_tables
                               (group_name VARCHAR,
                               admin_id INTEGER,
                               table_name VARCHAR,
                               table_description TEXT,
                               context TEXT)
                               """)
connection.commit()
connection.close()


async def check_for_group(message) -> bool:
    con = aiosqlite.connect(db_name)
    try:
        text = message.text
        start, group_data = map(str, text.split())
        group, admin_id, group_id = map(str, text.split("_"))

    except Exception as e:
        text = message.text
        if text == "/start":

            await con.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ? ", (0, message.chat.id))
            await con.commit()
        await con.close()
        return False

    if start == "/start":

        existing_record = await con.execute("SELECT * FROM groups where group_id == ?", (group_id,))
        existing_record = existing_record.fetchone()
        if existing_record is not None:
            group_name = await con.execute("SELECT group_name FROM groups where group_id == ?", (group_id,))
            group_name = group_name.fetchone()[0]
            await con.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (1, message.chat.id))
            await con.commit()
            await con.execute("UPDATE callback_manager SET group_name = ? WHERE user_id == ?", (group_name, message.chat.id))
            await con.commit()
            await con.execute("UPDATE callback_manager SET admin_id = ? WHERE user_id == ?", (admin_id, message.chat.id))
            await con.commit()
            await con.close()
            return True
        else:
            await con.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (0, message.chat.id))
            await con.commit()
            return False
    else:
        is_group = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ? ", (message.chat_id,))
        is_group = is_group.fetchone()[0]
        if is_group:
            await con.close()
            return True
        else:
            await con.close()
            return False


async def check_group_design(chat_id: int = None) -> Union[int, None]:

    admin_id = chat_id
    async with aiosqlite.connect(db_name) as db:
        current = await db.execute("SELECT group_name FROM groups where admin_id = ? AND design_flag == 1 ", (admin_id,))
        group_name = await current.fetchone()
        await db.close()
    if group_name is not None:
        return group_name[0]
    else:
        return None

async def get_settings(chat_id: int) -> dict:
    group_name = check_group_design(chat_id)
    con = aiosqlite.connect(db_name)
    group_flag = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = group_flag.fetchone()[0]
    existing_record = await con.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
    existing_record = existing_record.fetchone()
    print("callback", existing_record)

    if group_flag:

        group_name = await con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = group_name.fetchone()[0]
        chat_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        chat_id = chat_id.fetchone()[0]

        con = aiosqlite.connect(db_name)
        table_names = await con.execute(
            "SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
        table_names = table_names.fetchone()
        build_plots = await con.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
        build_plots = build_plots.fetchone()
        await con.close()

    elif group_name is not None:

        con = aiosqlite.connect(db_name)
        table_names = await con.execute("SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
        table_names = table_names.fetchone()
        build_plots = await con.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
        build_plots = build_plots.fetchone()
        await con.close()

    else:
        con = aiosqlite.connect(db_name)
        table_names = await con.execute("SELECT current_tables FROM users WHERE user_id = ?", (chat_id,))
        table_names = table_names.fetchone()
        build_plots = await con.execute("SELECT build_plots FROM users WHERE user_id = ?", (chat_id,))
        build_plots = build_plots.fetchone()
        await con.close()

    if table_names is not None:
        settings = {"table_name": table_names[0],
                    "build_plots": build_plots[0],
                    }
    else:
        settings = {"table_name": None,
                    "build_plots": True,
                    }
    print(settings)
    return settings


async def update_summary(chat_id: int, new_summary: str) -> None:
    con = aiosqlite.connect(db_name)
    group_flag = con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = group_flag.fetchone()[0]
    await con.commit()

    if group_flag == True:
        group_name = await con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = group_name.fetchone()[0]
        admin_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        admin_id = admin_id.fetchone()[0]
        await con.execute("UPDATE groups SET group_conv = ? WHERE admin_id == ? AND group_name == ?",
                    (new_summary, admin_id, group_name))
        await con.commit()
    else:
        await con.execute("UPDATE users SET conv_sum = ? WHERE user_id == ?", (new_summary, chat_id))
        await con.commit()
    await con.close()


async def create_group_db(admin_id: int, group_name: str, group_name_for_link: str) -> str:
    con = aiosqlite.connect(db_name)

    existing_record = await con.execute("SELECT * FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
    existing_record = existing_record.fetchone()
    if existing_record is None:
        await con.execute("INSERT INTO groups(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        await con.commit()
        group_id = await con.execute("SELECT group_id FROM groups where admin_id == ? AND group_name == ?", (admin_id, group_name))
        group_id = con.fetchone()[0]
        group_link = "https://t.me/auto_analyzer_bot?start=" + group_name_for_link + "_" + str(group_id)
        await con.execute("UPDATE groups SET group_link = ? WHERE admin_id == ? and group_name == ? ",
                    (group_link, admin_id, group_name))
        await con.commit()
        await con.execute("INSERT INTO group_manager(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        await con.commit()
        await con.close()
        message = "Группа создана"
    else:
        message = "Данная группа уже создавалась"
    return message


async def set_plots(message) -> str:
    chat_id = message.chat.id
    con = aiosqlite.connect(db_name)

    group_name = check_group_design(chat_id)
    if message.text == "Выключить":
        text = "Режим визуализации отключён"
        if group_name is not None:
            await con.execute("UPDATE groups SET group_plot = 0 WHERE admin_id == ?", (chat_id,))
        else:
            await con.execute("UPDATE users SET build_plots = 0 where user_id == ?", (chat_id,))
        await con.commit()
    elif message.text == "Включить":
        text = "Режим визуализации включён"
        if group_name is not None:
            await con.execute("UPDATE groups SET group_plot = 1 WHERE admin_id == ?", (chat_id,))
        else:
            await con.execute("UPDATE users SET build_plots = 1 where user_id == ?", (chat_id,))
        await con.commit()
    await con.close()
    return text


async def add_table_db(message=None, call=None, downloaded_file=None) -> None:
    chat_id = message.chat.id
    message = message
    group_name = check_group_design(chat_id)
    src = "data/" + message.document.file_name
    src.replace("|", "_")

    with open(src, 'wb') as f:
        f.write(downloaded_file)
        con = aiosqlite.connect(db_name)
        if group_name is not None:
            existing_record = await con.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ?",(chat_id, message.document.file_name))
            existing_record = existing_record.fetchone()
            if existing_record is None:
                await con.execute("""INSERT INTO group_tables(admin_id, group_name, table_name) VALUES(?,?,?)""",
                                (chat_id, group_name, message.document.file_name))
                await con.commit()

                await con.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?",
                                (message.document.file_name, chat_id, group_name))
                await con.commit()
                await con.close()
        else:
            existing_record = await con.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?",(chat_id, message.document.file_name))
            existing_record = existing_record.fetchone()
            if existing_record is None:

                await con.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""",
                                (chat_id, message.document.file_name))
                await con.commit()
                await con.execute("UPDATE users SET current_tables = ? WHERE user_id == ?",
                                (message.document.file_name, chat_id))
                await con.commit()

                await con.close()

            await con.close()


async def choose_description_db(message, table_name: str = None, downloaded_file = None) -> None:
    table_name = table_name
    con = aiosqlite.connect(db_name)
    chat_id = message.from_user.id
    group_name = check_group_design(chat_id)
    if message.content_type == "text":
        description = str(message.text)
        if group_name is not None:

            existing_record = await con.execute("select table_name from group_tables where admin_id == ? and group_name == ?",
                        (chat_id, group_name))
            existing_record = existing_record.fetchall()
            if existing_record:
                await con.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ?""",
                    (
                        description, table_name, chat_id, group_name))

            await con.commit()
            await con.close()

        else:
            existing_record = await con.execute("select table_name from tables where user_id == ?", (chat_id,))
            existing_record = existing_record.fetchall()
            if existing_record:
                await con.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? and user_id = ? """,
                            (description, table_name, chat_id))

            await con.commit()
            await con.close()

    elif message.content_type == "document":
        downloaded_file = downloaded_file
        src = "data/" + message.document.file_name

        encoding_info = chardet.detect(downloaded_file)
        file_encoding = encoding_info['encoding']

        # Проверяем кодировку и отправляем сообщение пользователю
        if file_encoding:
            print(file_encoding)
        else:
            print("ni")

        try:
            description = downloaded_file.decode('utf-8')
        except UnicodeDecodeError as e:
            description = downloaded_file.decode("cp1251", "ignore")

        if group_name is not None:
            existing_record = await con.execute("select table_name from group_tables where admin_id == ? and group_name == ?",(chat_id, group_name))

            existing_record = existing_record.fetchall()
            if existing_record:
               await con.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                    (description, table_name, chat_id, group_name))
            await con.commit()
            await con.close()

        else:
            existing_record = await con.execute("select table_name from tables where user_id == ?", (chat_id,))
            existing_record = existing_record.fetchall()
            if existing_record:
                await con.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? """,
                                (description, table_name))
            await con.commit()
            await con.close()


async def add_context_db(message=None, table_name=None, downloaded_file=None) -> None:
    con = aiosqlite.connect(db_name)
    chat_id = message.chat.id
    table_name = table_name
    group_name = check_group_design(chat_id)
    if message.content_type == "text":
        context = str(message.text)
        if group_name is not None:
            await con.execute(
                """UPDATE group_tables SET context = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                    (context, table_name, chat_id, group_name))
            await con.commit()

        else:
            await con.execute("""UPDATE tables SET context = ? WHERE table_name == ? and user_id == ? """,
                            (context, table_name, chat_id))
            await con.commit()
        await con.close()

    elif message.content_type == "document":

        downloaded_file = downloaded_file
        src = "data/" + message.document.file_name
        if ".msg" in src:
            with open(src, 'wb') as f:
                f.write(downloaded_file)
            context = msg_to_string(src)
        else:
            context = downloaded_file.decode('utf-8')
        if group_name is not None:
            await con.execute(
                    """UPDATE group_tables SET context = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                (context, table_name, chat_id, group_name))
            await con.commit()

        else:
            await con.execute("""UPDATE tables SET context = ? WHERE table_name = ? and user_id == ? """,
                            (context, table_name, chat_id))
            await con.commit()

    await con.close()


async def check_for_demo(chat_id : int = None) -> Union[None, str]:
    if demo:
        con = aiosqlite.connect(db_name)
        req_count = await con.execute("SELECT req_count FROM callback_manager WHERE user_id == ?", (chat_id,))
        req_count = req_count.fetchone()[0]
        if reset:
            req_count = 0
            await con.execute("UPDATE callback_manager SET req_count = 0")
            await con.commit()

        if req_count > max_requests:
            return "К сожалению, лимит запросов исчерпан, попробуйте позднее"

        req_count += 1

        await con.execute("UPDATE callback_manager SET req_count = ? WHERE user_id == ?", (req_count, chat_id))
        await con.commit()
        await con.close()
        return None


async def save_group_settings_db(chat_id : int = None, group_name : str = None) -> str:
    con = aiosqlite.connect(db_name)
    group_link = await con.execute("SELECT group_link FROM groups where admin_id == ? AND group_name == ?", (chat_id, group_name))
    await con.commit()

    group_link = group_link.fetchone()

    await con.execute("UPDATE groups SET design_flag = 0 WHERE admin_id == ?", (chat_id,))
    await con.commit()

    if group_link is not None:
        group_link = group_link[0]
    await con.close()
    return group_link


async def choose_group_db(admin_id: int = None, group_name: str = None) -> None:
    con = aiosqlite.connect(db_name)
    await con.execute("UPDATE groups SET design_flag = True WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
    await con.commit()
    await con.close()


async def update_table(chat_id: int = None, settings : dict = None) -> None:

    group_name = check_group_design(chat_id=chat_id)
    con = aiosqlite.connect(db_name)
    if group_name is not None:
        await con.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? and group_name == ?",
                    (settings["table_name"], chat_id, group_name))
        await con.commit()
    else:
        await con.execute(
            "UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
        await con.commit()
    await con.close()

