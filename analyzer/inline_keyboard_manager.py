import sqlite3 as sq

from db_manager import *


def get_page(chat_id, page_type):
    con = sq.connect("user_data.sql")
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


def change_page(chat_id, page_type, new_page):
    con = sq.connect("user_data.sql")
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


def get_pages_amount(chat_id):
    con = sq.connect("user_data.sql")
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


