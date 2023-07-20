import sqlite3 as sq
from telebot import types
import yaml
from db_manager import *

with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)
db_name = cfg["db_name"]


def get_page(chat_id: int, page_type: str) -> int:
    con = sq.connect(db_name)
    cur = con.cursor()
    page = None
    group_name = check_group_design(chat_id)
    if group_name is not None:
        query = f"SELECT {page_type} FROM group_manager WHERE admin_id == ? AND group_name == ?"
        cur.execute(query, (chat_id, group_name))
        page = cur.fetchone()[0]

        con.commit()
        con.close()
    else:
        query = f"SELECT {page_type} FROM callback_manager WHERE user_id == ?"
        cur.execute(query, (chat_id,))
        page = cur.fetchone()[0]
        con.commit()
        con.close()
    return page


def change_page(chat_id: int, page_type: str, new_page: int) -> None:
    con = sq.connect(db_name)
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if group_name is not None:
        query = f"UPDATE group_manager SET {page_type} = ? WHERE admin_id == ?"
        cur.execute(query, (new_page, chat_id))

    else:
        query = f"UPDATE callback_manager SET {page_type} = ? WHERE user_id == ?"
        cur.execute(query, (new_page, chat_id))

    con.commit()
    con.close()


def get_pages_amount(chat_id: int) -> int:
    con = sq.connect(db_name)
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if group_name is not None:
        cur.execute("SELECT * FROM group_tables WHERE admin_id == ? AND  group_name == ?", (chat_id, group_name))
    else:
        cur.execute("SELECT * FROM tables WHERE user_id = ?", (chat_id,))
    amount = len(cur.fetchall())//3 + 1

    con.commit()
    con.close()
    return amount


def create_group_keyboard(chat_id: int = None, show_groups: bool = False):
    markup = types.InlineKeyboardMarkup()
    con = sq.connect(db_name)
    cur = con.cursor()
    if show_groups:
        cur.execute("select group_name from groups where admin_id == ? ", (chat_id,))
        rows = cur.fetchall()
        con.commit()
        for row in rows:

            if row[0] is not None:
                btn = types.InlineKeyboardButton(text=row[0], callback_data=f"g|{row[0]}")

                markup.add(btn)

        btn3 = types.InlineKeyboardButton(text="Назад", callback_data="g|back")
        markup.add(btn3)

    else:

        btn1 = types.InlineKeyboardButton(text="Выбрать группу", callback_data="g|choose_group")
        btn2 = types.InlineKeyboardButton(text="Создать группу", callback_data="g|create_group")
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data="g|exit")
        markup.add(btn1)
        markup.add(btn2)
        markup.add(btn3)
    con.close()
    return markup



def inline_keyboard(chat_id: int = None, page_type: str = None, page: int = 1, status_flag: bool = True):
    group_name = check_group_design(chat_id)

    if group_name is not None:
        query = "select table_name from group_tables where admin_id == ? and group_name == ? LIMIT 3 OFFSET ?"
        if page == 1:
            offset = 0
        else:
            offset = ((page - 1) * 3)
    else:
        query = "select table_name from tables where user_id == ? LIMIT 3 OFFSET ?"
        if page == 1:
            offset = 0
        else:
            offset = ((page - 1) * 3)
    markup = types.InlineKeyboardMarkup(row_width=3)
    prefix = page_type[0] + "|"
    settings = get_settings(chat_id)
    con = sq.connect(db_name)
    cur = con.cursor()
    if group_name is not None:
        cur.execute(query, (chat_id, group_name, offset))
    else:
        cur.execute(query, (chat_id, offset))

    rows = cur.fetchall()

    con.commit()
    con.close()
    btn = None

    for row in rows:

        if row[0] is not None:
            prep_arr = list(row[0].split("_"))

            prepared_row = "_".join(prep_arr[1:])

            print("here", f"{prefix}{row[0]}")
            btn = types.InlineKeyboardButton(text=prepared_row, callback_data=f"{prefix}{row[0]}")

            markup.add(btn)
    if page_type == "table_page":
        btn1 = types.InlineKeyboardButton(text="Добавить новую таблицу", callback_data=f"t|new_table")
        btn2 = types.InlineKeyboardButton(text="Убрать последнюю таблицу из набора", callback_data=f"t|delete_tables")
        markup.row(btn1)

        if settings["table_name"] is not None and len(settings["table_name"]) > 0:

            markup.add(btn2)

    page = get_page(chat_id=chat_id, page_type=page_type)
    amount = get_pages_amount(chat_id=chat_id)
    markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))
    right = types.InlineKeyboardButton(text="-->", callback_data=f"{prefix}right")
    left = types.InlineKeyboardButton(text="<--", callback_data=f"{prefix}left")
    if page > 1:
        markup.row(left, right)
    else:
        markup.row(right)

    btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data=f"{prefix}exit")
    markup.add(btn3)
    return markup

