import sqlite3 as sq
import yaml

from typing import Union, Callable, List
from msg_parser import msg_to_string


with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
db_name = cfg["db_name"]


def check_for_group(message) -> bool:
    con = sq.connect(db_name)
    cur = con.cursor()

    try:
        text = message.text
        start, group_data = map(str, text.split())
        group, admin_id, group_name = map(str, text.split("_"))

    except Exception as e:
        text = message.text
        if text == "/start":

            cur.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ? ", (0, message.chat.id))
            con.commit()
        con.close()
        return False

    if start == "/start":

        cur.execute("SELECT * FROM groups where group_name == ?", (group_name,))
        existing_record = cur.fetchone()
        if existing_record is not None:

            cur.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (1, message.chat.id))
            con.commit()
            cur.execute("UPDATE callback_manager SET group_name = ? WHERE user_id == ?", (group_name, message.chat.id))
            con.commit()
            cur.execute("UPDATE callback_manager SET admin_id = ? WHERE user_id == ?", (admin_id, message.chat.id))
            con.commit()
            con.close()
            return True
        else:
            cur.execute("UPDATE callback_manager SET group_flag = ? WHERE user_id == ?", (0, message.chat.id))
            con.commit()
            return False
    else:
        cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ? ", (message.chat_id,))
        is_group = cur.fetchone()[0]
        if is_group:
            con.close()
            return True
        else:
            con.close()
            return False


def check_group_design(chat_id: int =None) -> Union[int, None]:

    admin_id = chat_id
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_name FROM groups where admin_id = ? AND design_flag == 1 ", (admin_id,))
    group_name = cur.fetchone()
    con.close()
    if group_name is not None:
        return group_name[0]
    else:
        return None


def get_settings(chat_id: int) -> dict:

    group_name = check_group_design(chat_id)

    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == ?", (chat_id,))

    group_flag = cur.fetchone()[0]
    cur.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()
    print("callback", existing_record)

    if group_flag:

        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == ?", (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == ?", (chat_id,))
        chat_id = cur.fetchone()[0]

        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute(
            "SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
        table_names = cur.fetchone()
        cur.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
        build_plots = cur.fetchone()
        con.close()

    elif group_name is not None:

        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("SELECT current_tables FROM groups WHERE admin_id = ? and group_name == ?", (chat_id, group_name))
        table_names = cur.fetchone()
        cur.execute("SELECT group_plot FROM groups WHERE admin_id = ? and group_name = ?", (chat_id, group_name))
        build_plots = cur.fetchone()
        con.close()

    else:
        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("SELECT current_tables FROM users WHERE user_id = ?", (chat_id,))
        table_names = cur.fetchone()
        cur.execute("SELECT build_plots FROM users WHERE user_id = ?", (chat_id,))
        build_plots = cur.fetchone()
        cur.execute("SELECT * FROM users")

        con.close()

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
        current_summary = current_summary[0][:250] + current_summary[0][:-250]
    return current_summary


def update_summary(chat_id: int, new_summary:str) -> None:
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
        cur.execute("UPDATE groups SET group_conv = ? WHERE admin_id == ? AND group_name == ?",
                    (new_summary, admin_id, group_name))
        con.commit()
    else:
        cur.execute("UPDATE users SET conv_sum = ? WHERE user_id == ?", (new_summary, chat_id))
        con.commit()
    con.close()


def create_group_db(admin_id: int, group_name: str, group_name_for_link: str) -> str:
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT * FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
    existing_record = cur.fetchone()
    if existing_record is None:
        cur.execute("INSERT INTO groups(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        con.commit()
        group_link = "https://t.me/auto_analyzer_bot?start=" + group_name_for_link
        cur.execute("UPDATE groups SET group_link = ? WHERE admin_id == ? and group_name == ? ",
                    (group_link, admin_id, group_name))
        con.commit()
        cur.execute("INSERT INTO group_manager(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        con.commit()
        con.close()
        message = "Группа создана"
    else:
        message = "Данная группа уже создавалась"
    return message


def set_plots(message) -> str:
    chat_id = message.chat.id
    con = sq.connect(db_name)
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if message.text == "Выключить":
        text = "Режим визуализации отключён"
        if group_name is not None:
            cur.execute("UPDATE groups SET group_plot = 0 WHERE admin_id == ?", (chat_id,))
        else:
            cur.execute("UPDATE users SET build_plots = 0 where user_id == ?", (chat_id,))
        con.commit()
    elif message.text == "Включить":
        text = "Режим визуализации включён"
        if group_name is not None:
            cur.execute("UPDATE groups SET group_plot = 1 WHERE admin_id == ?", (chat_id,))
        else:
            cur.execute("UPDATE users SET build_plots = 1 where user_id == ?", (chat_id,))
        con.commit()
    con.close()
    return text


def settings_prep(chat_id: int):
    settings = get_settings(chat_id)
    if settings["table_name"] is None:
        return False
    table_name = list(map(str, settings["table_name"].split(",")))
    for i in range(len(table_name)):
        prep_name = list(table_name[i].split("_"))
        table_name[i] = "_".join(prep_name[1:])
    return ",".join(table_name)


def add_table_db(message=None, call=None, downloaded_file=None) -> None:
    chat_id = message.chat.id
    message = message
    group_name = check_group_design(chat_id)
    src = "data/" + str(chat_id) + "_" + message.document.file_name
    src.replace("|", "_")

    with open(src, 'wb') as f:
        f.write(downloaded_file)
        con = sq.connect(db_name)
        cur = con.cursor()
        if group_name is not None:
            cur.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ?",(chat_id, message.document.file_name))
            existing_record = cur.fetchone()
            if existing_record is None:
                cur.execute("""INSERT INTO group_tables(admin_id, group_name, table_name) VALUES(?,?,?)""",
                                (chat_id, group_name, message.document.file_name))
                con.commit()
                cur.execute("select * from group_tables")
                # print("group_tables", cur.fetchall())
                cur.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?",
                                (message.document.file_name, chat_id, group_name))
                con.commit()
                con.close()
        else:
            cur.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?",(chat_id, message.document.file_name))
            existing_record = cur.fetchone()
            if existing_record is None:

                cur.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""",
                                (chat_id, message.document.file_name))
                con.commit()
                cur.execute("UPDATE users SET current_tables = ? WHERE user_id == ?",
                                (message.document.file_name, chat_id))
                con.commit()
                cur.execute("Select * from tables")
                print(cur.fetchall())
                con.close()

            con.close()


def choose_description_db(message, table_name: str = None, downloaded_file = None) -> None:
    table_name = table_name
    con = sq.connect(db_name)
    cur = con.cursor()
    chat_id = message.from_user.id
    group_name = check_group_design(chat_id)
    if message.content_type == "text":
        description = str(message.text)
        if group_name is not None:

            cur.execute("select table_name from group_tables where admin_id == ? and group_name == ?",
                        (chat_id, group_name))
            existing_record = cur.fetchall()
            if existing_record:
                cur.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ?""",
                    (
                        description, table_name, chat_id, group_name))

            con.commit()
            con.close()

        else:
            cur.execute("select table_name from tables where user_id == ?", (chat_id,))
            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? and user_id = ? """,
                            (description, table_name, chat_id))

            con.commit()
            con.close()

    elif message.content_type == "document":
        downloaded_file = downloaded_file
        src = "data/" + message.document.file_name
        description = downloaded_file.decode('utf-8')

        if group_name is not None:
            cur.execute("select table_name from group_tables where admin_id == ? and group_name == ?",(chat_id, group_name))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                    (description, table_name, chat_id, group_name))
            con.commit()
            con.close()

        else:
            cur.execute("select table_name from tables where user_id == ?", (chat_id,))
            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? """,
                                (description, table_name))
            con.commit()
            con.close()


def add_context_db(message=None, table_name=None, downloaded_file=None) -> None:
    con = sq.connect(db_name)
    cur = con.cursor()
    chat_id = message.chat.id
    table_name = table_name
    group_name = check_group_design(chat_id)
    if message.content_type == "text":
        context = str(message.text)
        if group_name is not None:
            cur.execute(
                """UPDATE group_tables SET context = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                    (context, table_name, chat_id, group_name))
            con.commit()

        else:
            cur.execute("""UPDATE tables SET context = ? WHERE table_name == ? and user_id == ? """,
                            (context, table_name, chat_id))
            con.commit()
        con.close()

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
            cur.execute(
                    """UPDATE group_tables SET context = ? WHERE table_name == ? and admin_id == ? and group_name == ? """,
                (context, table_name, chat_id, group_name))
            con.commit()

        else:
            cur.execute("""UPDATE tables SET context = ? WHERE table_name = ? and user_id == ? """,
                            (context, table_name, chat_id))
            con.commit()

    con.close()

