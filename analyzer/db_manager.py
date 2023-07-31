import aiosqlite
import yaml
import chardet
from typing import Union, Callable, List
from msg_parser import msg_to_string
import config
import traceback
import logging
import aiofiles
logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

bot_name = config.config["bot_name"]
bot_api = config.config["bot_api"]
demo = config.config["demo"][0]
max_requests = config.config["demo"][1]
reset = config.config["demo"][2]
db_name = config.config["db_name"]


async def create_tables():
    # Установить соединение с базой данных
    con = await aiosqlite.connect(db_name)

    # Создание таблицы users
    await con.execute("""CREATE TABLE IF NOT EXISTS users
                          (user_id INTEGER PRIMARY KEY,
                          conv_sum TEXT,
                          current_tables VARCHAR,
                          build_plots boolean DEFAULT 1
                          )""")
    await con.commit()

    # Создание таблицы groups
    await con.execute("""CREATE TABLE IF NOT EXISTS groups
                          (group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                          admin_id INTEGER,
                          group_plot boolean DEFAULT 1,
                          group_name VARCHAR,
                          group_link VARCHAR,
                          group_conv TEXT,
                          current_tables VARCHAR,
                          design_flag boolean DEFAULT 0)""")
    await con.commit()

    # Создание таблицы callback_manager
    await con.execute("""CREATE TABLE IF NOT EXISTS callback_manager
                          (user_id INTEGER PRIMARY KEY,
                          table_page INTEGER DEFAULT 1,
                          context_page INTEGER DEFAULT 1,
                          description_page INTEGER DEFAULT 1,
                          group_flag boolean DEFAULT 0,
                          group_name VARCHAR,
                          admin_id INTEGER,
                          req_count INTEGER DEFAULT 0,
                          FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    await con.commit()

    # Создание таблицы group_manager
    await con.execute("""CREATE TABLE IF NOT EXISTS group_manager
                          (admin_id INTEGER,
                          group_name,
                          table_page INTEGER DEFAULT 1,
                          context_page INTEGER DEFAULT 1,
                          description_page INTEGER DEFAULT 1)
                          """)
    await con.commit()

    # Создание таблицы tables
    await con.execute("""CREATE TABLE IF NOT EXISTS tables 
                          (table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                          user_id INTEGER, 
                          table_name VARCHAR,
                          table_description TEXT,
                          context TEXT,
                          FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    await con.commit()

    # Создание таблицы group_tables
    await con.execute("""CREATE TABLE IF NOT EXISTS group_tables
                          (group_name VARCHAR,
                          admin_id INTEGER,
                          table_name VARCHAR,
                          table_description TEXT,
                          context TEXT)
                          """)
    await con.commit()

# Запустите функцию создания таблиц в асинхронном контексте
import asyncio
asyncio.run(create_tables())


async def check_for_group(message) -> bool:
    async with aiosqlite.connect(db_name) as con:
        try:
            text = message.text
            start, group_data = map(str, text.split())
            group, admin_id, group_id = map(str, text.split("_"))

        except Exception as e:
            text = message.text
            if text == "/start":

                await con.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ? ", (0, message.chat.id))
                await con.commit()

            return False

        if start == "/start":

            existing_record = await con.execute("SELECT * FROM groups where group_id == ?", (group_id,))
            existing_record = existing_record.fetchone()
            if existing_record is not None:
                group_name = await con.execute("SELECT group_name FROM groups where group_id == ?", (group_id,))
                group_name = await group_name.fetchone()
                group_name = group_name[0]
                await con.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (1, message.chat.id))
                await con.commit()
                await con.execute("UPDATE callback_manager SET group_name = ? WHERE user_id == ?", (group_name, message.chat.id))
                await con.commit()
                await con.execute("UPDATE callback_manager SET admin_id = ? WHERE user_id == ?", (admin_id, message.chat.id))
                await con.commit()

                return True
            else:
                await con.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (0, message.chat.id))
                await con.commit()
                return False
        else:
            is_group = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ? ", (message.chat_id,))
            is_group = await is_group.fetchone()
            is_group = is_group[0]
            if is_group:

                return True
            else:

                return False


async def check_group_design(chat_id: int = None) -> Union[int, None]:

    admin_id = chat_id
    async with aiosqlite.connect(db_name) as con:
        current = await con.execute("SELECT group_name FROM groups where admin_id = ? AND design_flag == 1 ", (admin_id,))
        group_name = await current.fetchone()

    if group_name is not None:
        return group_name[0]
    else:
        return None


async def get_settings(chat_id: int) -> dict:
    group_name = await check_group_design(chat_id)

    async with aiosqlite.connect(db_name) as con:
        group_flag = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_flag = await group_flag.fetchone()
        group_flag = group_flag[0]

        if group_flag:

            group_name = await con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
            group_name = await group_name.fetchone()
            group_name = group_name[0]
            chat_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
            chat_id = await chat_id.fetchone()
            chat_id = chat_id[0]

            table_names = await con.execute(
                "SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
            table_names = await table_names.fetchone()
            build_plots = await con.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
            build_plots = await build_plots.fetchone()

        elif group_name is not None:

            table_names = await con.execute("SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
            table_names = await table_names.fetchone()
            build_plots = await con.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
            build_plots = await build_plots.fetchone()

        else:
            table_names = await con.execute("SELECT current_tables FROM users WHERE user_id = ?", (chat_id,))
            table_names = await table_names.fetchone()
            build_plots = await con.execute("SELECT build_plots FROM users WHERE user_id = ?", (chat_id,))
            build_plots = await build_plots.fetchone()

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
    async with aiosqlite.connect(db_name) as con:
        group_flag = await con.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

        group_flag = await group_flag.fetchone()
        group_flag = group_flag[0]
        if group_flag == True:
            group_name = await con.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
            group_name = await group_name.fetchone()
            group_name = group_name[0]
            admin_id = await con.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
            admin_id = await admin_id.fetchone()
            admin_id = admin_id[0]
            await con.execute("UPDATE groups SET group_conv = ? WHERE admin_id == ? AND group_name == ?",
                    (new_summary, admin_id, group_name))
            await con.commit()
        else:
            await con.execute("UPDATE users SET conv_sum = ? WHERE user_id == ?", (new_summary, chat_id))
            await con.commit()


async def create_group(admin_id: int, group_name: str, group_name_for_link: str) -> str:
    async with aiosqlite.connect(db_name) as con:

        existing_record = await con.execute("SELECT * FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
        existing_record = existing_record.fetchone()
        if existing_record is None:
            await con.execute("INSERT INTO groups(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
            await con.commit()
            group_id = await con.execute("SELECT group_id FROM groups where admin_id == ? AND group_name == ?", (admin_id, group_name))
            group_id = await group_id.fetchone()
            group_id = group_id[0]
            group_link = "https://t.me/auto_analyzer_bot?start=" + group_name_for_link + "_" + str(group_id)
            await con.execute("UPDATE groups SET group_link = ? WHERE admin_id == ? and group_name == ? ",
                    (group_link, admin_id, group_name))
            await con.commit()
            await con.execute("INSERT INTO group_manager(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
            await con.commit()

            message = "Группа создана"
        else:
            message = "Данная группа уже создавалась"
        return message


async def set_plots(message) -> str:
    chat_id = message.chat.id
    async with aiosqlite.connect(db_name) as con:
        group_name = await check_group_design(chat_id)
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

        return text


async def add_table(message=None, downloaded_file=None) -> None:
    chat_id = message.chat.id
    message = message
    group_name = await check_group_design(chat_id)
    src = "data/" + message.document.file_name
    src.replace("|", "_")

    async with aiofiles.open(src, 'wb') as f:
        await f.write(downloaded_file.getvalue())
        async with aiosqlite.connect(db_name) as con:
            if group_name is not None:
                existing_record = await con.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ?",(chat_id, message.document.file_name))
                existing_record = await existing_record.fetchone()
                if existing_record is None:
                    await con.execute("""INSERT INTO group_tables(admin_id, group_name, table_name) VALUES(?,?,?)""",
                                (chat_id, group_name, message.document.file_name))
                    await con.commit()

                    await con.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?",
                                (message.document.file_name, chat_id, group_name))
                    await con.commit()
            else:
                existing_record = await con.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?",(chat_id, message.document.file_name))
                existing_record = await existing_record.fetchone()
                if existing_record is None:

                    await con.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""",
                                (chat_id, message.document.file_name))
                    await con.commit()
                    await con.execute("UPDATE users SET current_tables = ? WHERE user_id == ?",
                                (message.document.file_name, chat_id))
                    await con.commit()


async def choose_description_db(message, table_name: str = None, downloaded_file = None) -> None:
    table_name = table_name
    chat_id = message.from_user.id
    group_name = await check_group_design(chat_id)
    async with aiosqlite.connect(db_name) as con:
        if message.content_type == "text":
            description = str(message.text)
            if group_name is not None:

                existing_record = await con.execute("select table_name from group_tables where admin_id == ? and group_name == ?",
                        (chat_id, group_name))
                existing_record = await existing_record.fetchall()
                if existing_record:
                    await con.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ?""",
                    (
                        description, table_name, chat_id, group_name))

                await con.commit()


            else:
                existing_record = await con.execute("select table_name from tables where user_id == ?", (chat_id,))
                existing_record = await existing_record.fetchall()
                if existing_record:
                    await con.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? and user_id = ? """,
                            (description, table_name, chat_id))

                await con.commit()

        elif message.content_type == "document":
            downloaded_file = downloaded_file
            src = "data/" + message.document.file_name

            encoding_info = chardet.detect(downloaded_file)
            file_encoding = encoding_info['encoding']

        # Проверяем кодировку и отправляем сообщение пользователю
            if file_encoding:
                print(file_encoding)
            else:
                print("no file encoding")

            try:
                description = await downloaded_file.decode('utf-8')
            except UnicodeDecodeError as e:
                description = await downloaded_file.decode("cp1251", "ignore")

            if group_name is not None:
                existing_record = await con.execute("select table_name from group_tables where admin_id == ? and group_name == ?",(chat_id, group_name))

                existing_record = await existing_record.fetchall()
                if existing_record:
                    await con.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                    (description, table_name, chat_id, group_name))
                await con.commit()

            else:
                existing_record = await con.execute("select table_name from tables where user_id == ?", (chat_id,))
                existing_record = await existing_record.fetchall()
                if existing_record:
                    await con.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? """,
                                (description, table_name))
                await con.commit()


async def add_context(message=None, table_name=None, downloaded_file=None) -> None:
    chat_id = message.chat.id
    table_name = table_name
    group_name = check_group_design(chat_id)
    async with aiosqlite.connect(db_name) as con:
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

        elif message.content_type == "document":

            downloaded_file = downloaded_file
            src = "data/" + message.document.file_name
            if ".msg" in src:
                async with aiofiles.open(src, 'wb') as f:
                    await f.write(downloaded_file.getvalue())
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


async def check_for_demo(chat_id : int = None) -> Union[None, str]:
    async with aiosqlite.connect(db_name) as con:
        if demo:
            req_count = await con.execute("SELECT req_count FROM callback_manager WHERE user_id == ?", (chat_id,))
            req_count = await req_count.fetchone()
            req_count = req_count[0]
            if reset:
                req_count = 0
                await con.execute("UPDATE callback_manager SET req_count = 0")
                await con.commit()

            if req_count > max_requests:
                return "К сожалению, лимит запросов исчерпан, попробуйте позднее"

            req_count += 1

            await con.execute("UPDATE callback_manager SET req_count = ? WHERE user_id == ?", (req_count, chat_id))
            await con.commit()
            return None


async def save_group_settings(chat_id : int = None, group_name : str = None) -> str:
    async with aiosqlite.connect(db_name) as con:

        group_link = await con.execute("SELECT group_link FROM groups where admin_id == ? AND group_name == ?", (chat_id, group_name))
        await con.commit()

        group_link = await group_link.fetchone()

        await con.execute("UPDATE groups SET design_flag = 0 WHERE admin_id == ?", (chat_id,))
        await con.commit()

        if group_link is not None:
            group_link = group_link[0]
        return group_link


async def choose_group_db(admin_id: int = None, group_name: str = None) -> None:
    async with aiosqlite.connect(db_name) as con:
        await con.execute("UPDATE groups SET design_flag = True WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
        await con.commit()


async def update_table(chat_id: int = None, settings : dict = None) -> None:

    group_name = await check_group_design(chat_id=chat_id)
    async with aiosqlite.connect(db_name) as con:
        if group_name is not None:
            await con.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? and group_name == ?",
                    (settings["table_name"], chat_id, group_name))
            await con.commit()
        else:
            await con.execute(
            "UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
            await con.commit()


async def get_group_id(group_name : str = None, admin_id : int = None):
    async with aiosqlite.connect(db_name) as con:
        result = await con.execute("SELECT group_id FROM group_tables WHERE group_name = ? AND admin_id = ?", (group_name, admin_id))
        result = await result.fetchone()
    return result
