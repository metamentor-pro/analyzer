import sqlite3 as sq
from telebot import types
import yaml
from db_manager import *


def connect_to_db() -> tuple:
    """
    Connects to the SQLite database and returns a connection and a cursor.
    """
    con = sq.connect(db_name)
    cur = con.cursor()
    return con, cur


def get_page(chat_id: int, page_type: str) -> int:
    """
    This function gets the page number for a given chat_id and page_type.
    It checks if the chat_id belongs to a group, and if so, it fetches the page number from the group_manager table.
    If the chat_id does not belong to a group, it fetches the page number from the callback_manager table.
    :param chat_id: The chat ID to get the page number for.
    :param page_type: The type of page to get the number for.
    :return: The page number.
    """
    con, cur = connect_to_db()
    page = None
    group_name = check_group_design(chat_id)
    if group_name is not None:
        query = f"SELECT {page_type} FROM group_manager WHERE admin_id == ? AND group_name == ?"
        cur.execute(query, (chat_id, group_name))
        page = cur.fetchone()[0]
    else:
        query = f"SELECT {page_type} FROM callback_manager WHERE user_id == ?"
        cur.execute(query, (chat_id,))
        page = cur.fetchone()[0]
    con.commit()
    con.close()
    return page


def change_page(chat_id: int, page_type: str, new_page: int) -> None:
    """
    This function changes the page number for a given chat_id and page_type to new_page.
    It checks if the chat_id belongs to a group, and if so, it updates the page number in the group_manager table.
    If the chat_id does not belong to a group, it updates the page number in the callback_manager table.
    :param chat_id: The chat ID to change the page number for.
    :param page_type: The type of page to change the number for.
    :param new_page: The new page number.
    """
    con, cur = connect_to_db()
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
    """
    This function gets the total number of pages for a given chat_id.
    It checks if the chat_id belongs to a group, and if so, it fetches the number of rows from the group_tables table.
    If the chat_id does not belong to a group, it fetches the number of rows from the tables table.
    The total number of pages is calculated as the number of rows divided by 3, rounded up to the nearest integer.
    :param chat_id: The chat ID to get the total number of pages for.
    :return: The total number of pages.
    """
    con, cur = connect_to_db()
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
    """
    This function creates an inline keyboard for group management.
    If show_groups is True, it fetches the names of all groups for the given chat_id and adds a button for each group to the keyboard.
    If show_groups is False, it adds buttons for choosing a group, creating a group, and exiting.
    :param chat_id: The chat ID to create the keyboard for.
    :param show_groups: Whether to show the names of all groups.
    :return: The created inline keyboard.
    """
    markup = types.InlineKeyboardMarkup()
    con, cur = connect_to_db()
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
    """
    This function creates an inline keyboard for navigating through pages.
    It fetches the names of all tables for the given chat_id and adds a button for each table to the keyboard.
    It also adds buttons for navigating to the next and previous pages, and for exiting.
    :param chat_id: The chat ID to create the keyboard for.
    :param page_type: The type of page to create the keyboard for.
    :param page: The current page number.
    :param status_flag: Whether to show the status flag.
    :return: The created inline keyboard.
    """
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
    con, cur = connect_to_db()
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
            btn = types.InlineKeyboardButton(text=prepared_row, callback_data=f"{prefix}{row[0]}")
            markup.add(btn)
    if page_type == "table_page":
        btn1 = types.InlineKeyboardButton(text="Добавить новую таблицу", callback_data=f"t|new_table")
        btn2 = types.InlineKeyboardButton(text="Убрать последнюю таблицу из набора", callback_data=f"t|delete_tables")
        markup.row(btn1)
    if status_flag:
        btn3 = types.InlineKeyboardButton(text="Статус", callback_data=f"{prefix}status")
        markup.row(btn3)
    amount = get_pages_amount(chat_id)
    if page < amount:
        markup.add(types.InlineKeyboardButton(text=f"{page}/{amount}", callback_data=" "))
        right = types.InlineKeyboardButton(text="→", callback_data=f"{prefix}right")
        left = types.InlineKeyboardButton(text="←", callback_data=f"{prefix}left")
        if page > 1:
            markup.row(left, right)
        else:
            markup.row(right)
    btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data=f"{prefix}exit")
    markup.add(btn3)
    return markup