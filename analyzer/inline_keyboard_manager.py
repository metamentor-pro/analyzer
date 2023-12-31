
from aiogram import types
import yaml
from db_manager import *


async def get_page(chat_id: int, page_type: str) -> int:
    async with aiosqlite.connect(db_name) as con:
        group_name = await check_group_design(chat_id)
        if group_name is not None:
            query = f"SELECT {page_type} FROM group_manager WHERE admin_id == ? AND group_name == ?"
            page = await con.execute(query, (chat_id, group_name))
            page = await page.fetchone()
            page = page[0]

            await con.commit()

        else:
            query = f"SELECT {page_type} FROM callback_manager WHERE user_id == ?"
            page = await con.execute(query, (chat_id,))
            page = await page.fetchone()
            page = page[0]
            await con.commit()

        return page


async def change_page(chat_id: int, page_type: str, new_page: int) -> None:
    async with aiosqlite.connect(db_name) as con:
        group_name = await check_group_design(chat_id)
        if group_name is not None:
            query = f"UPDATE group_manager SET {page_type} = ? WHERE admin_id == ?"
            await con.execute(query, (new_page, chat_id))

        else:
            query = f"UPDATE callback_manager SET {page_type} = ? WHERE user_id == ?"
            await con.execute(query, (new_page, chat_id))

        await con.commit()


async def get_pages_amount(chat_id: int) -> int:
    async with aiosqlite.connect(db_name) as con:
        group_name = await check_group_design(chat_id)
        if group_name is not None:
            amount = await con.execute("SELECT * FROM group_tables WHERE admin_id == ? AND  group_name == ?", (chat_id, group_name))
        else:
            amount = await con.execute("SELECT * FROM tables WHERE user_id = ?", (chat_id,))
        amount = await amount.fetchall()
        amount = len(amount)//3 + 1

        await con.commit()

        return amount


async def create_group_keyboard(chat_id: int = None, show_groups: bool = False):
    markup = types.InlineKeyboardMarkup()

    if show_groups:
        async with aiosqlite.connect(db_name) as con:
            rows = await con.execute("select group_name from groups where admin_id == ? ", (chat_id,))
            rows = await rows.fetchall()
            await con.commit()
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

    return markup


async def inline_keyboard(chat_id: int = None, page_type: str = None, page: int = 1, status_flag: bool = True):
    group_name = await check_group_design(chat_id)
    group_id = await get_group_id(group_name=group_name, admin_id=chat_id)
    if group_name is not None:
        query = "select table_name from group_tables where admin_id == ? and group_name == ? and group_id = ? LIMIT 3 OFFSET ?"
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
    settings = await get_settings(chat_id)

    async with aiosqlite.connect(db_name) as con:
        if group_name is not None:
            current = await con.execute(query, (chat_id, group_name, group_id, offset))
        else:
            current = await con.execute(query, (chat_id, offset))

        rows = await current.fetchall()

        await con.commit()

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

        if settings["table_name"] is not None and len(settings["table_name"]) > 0:

            markup.add(btn2)

    page = await get_page(chat_id=chat_id, page_type=page_type)
    amount = await get_pages_amount(chat_id=chat_id)
    markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))
    right = types.InlineKeyboardButton(text="→", callback_data=f"{prefix}right")
    left = types.InlineKeyboardButton(text="←", callback_data=f"{prefix}left")
    if page > 1:
        markup.row(left, right)
    else:
        markup.row(right)

    btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data=f"{prefix}exit")
    markup.add(btn3)
    return markup

