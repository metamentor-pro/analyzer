import os
import telebot
import sqlite3 as sq
import interactor
import time
import requests


import re
import yaml
import matplotlib
matplotlib.use('Agg')

from telebot import types
from msg_parser import msg_to_string

user_question = None

plot_files = ""


with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

bot_name = cfg["bot_name"]
bot_api = cfg["bot_api"]


class Bot(telebot.TeleBot):
    def __init__(self):
        self.name = bot_name
        super().__init__(bot_api)


bot = Bot()


@bot.message_handler(commands=["help"])
def help_info(message):
    bot.send_message(message.chat.id, "Я - автономный помощник для проведения различной аналитики")


@bot.message_handler(commands=["start", "exit"], content_types=["text", "document"])
def main(message=None, settings=None):
    try:
        chat_id = message.chat.id

    except Exception as e:
        chat_id = message
        print(message)
        print(e)

    con = sq.connect("user_data.sql")
    cur = con.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users 
                (user_id INTEGER UNIQUE,
                conv_sum TEXT,
                current_tables VARCHAR,
                build_plots boolean,
                VARCHAR)""")
    con.commit()

    cur.execute("""CREATE TABLE IF NOT EXISTS callback_manager
                (user_id INTEGER UNIQUE,
                table_callback boolean DEFAULT False,
                context_callback boolean DEFAULT False,
                description_callback boolean DEFAULT False,
                table_page INTEGER DEFAULT 1,
                context_page INTEGER DEFAULT 1,
                description_page INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    con.commit()
    cur.execute("SELECT * FROM callback_manager WHERE user_id = '%s'" % (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("INSERT  INTO callback_manager(user_id) VALUES(?)", (chat_id,))
    con.commit()
    cur.execute("Select * from callback_manager")
    dsf = cur.fetchall()

    cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("""INSERT INTO users(user_id) values(?)""", (chat_id,))

    cur.execute("SELECT * FROM users")

    con.commit()

    cur.execute(""" CREATE TABLE IF NOT EXISTS tables (user_id INTEGER, 
                table_name VARCHAR,
                table_description TEXT,
                context TEXT,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    con.commit()

    cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("""INSERT INTO tables(user_id) values(?)""", (chat_id,))

    cur.execute("SELECT * FROM tables")
    print(cur.fetchall())
    con.commit()

    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT current_tables FROM users WHERE user_id = '%s'" % (chat_id,))
    table_names = cur.fetchone()
    cur.execute("SELECT build_plots FROM users WHERE user_id = '%s'" % (chat_id,))
    build_plots = cur.fetchone()

    con.close()

    settings = {"table_name": table_names[0],
                "build_plots": build_plots[0],
                }

    print(settings)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🖹 Выбрать таблицу")
    btn2 = types.KeyboardButton("➕ Добавить описание таблицы")
    btn3 = types.KeyboardButton("🖻 Режим визуализации")
    btn4 = types.KeyboardButton("❓ Режим отправки запроса")
    btn5 = types.KeyboardButton("Добавить контекст")
    markup.row(btn1, btn2)
    markup.row(btn3, btn4, btn5)

    bot.send_message(chat_id, "Вы можете  выбрать одну из опций", reply_markup=markup)

    bot.register_next_step_handler(message, on_click, settings)




def get_settings(chat_id):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT current_tables FROM users WHERE user_id = '%s'" % (chat_id,))
    table_names = cur.fetchone()
    cur.execute("SELECT build_plots FROM users WHERE user_id = '%s'" % (chat_id,))
    build_plots = cur.fetchone()
    con.close()
    settings = {"table_name": table_names[0],
                "build_plots": build_plots[0],
                }
    return settings


def get_callback(chat_id, callback_type):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    callback = None
    if callback_type == "table_callback":
        cur.execute("SELECT table_callback FROM  callback_manager WHERE user_id == '%s'" % (chat_id,))

        callback = cur.fetchone()[0]
        con.commit()
    elif callback_type == "context_callback":
        cur.execute("SELECT context_callback FROM  callback_manager WHERE user_id == '%s'" % (chat_id,))

        callback = cur.fetchone()[0]
        con.commit()
    elif callback_type == "description_callback":
        cur.execute("SELECT description_callback FROM  callback_manager WHERE user_id == '%s'" % (chat_id,))

        callback = cur.fetchone()[0]
        con.commit()
    con.close()

    return callback

def get_page(chat_id, page_type):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    page = None
    if page_type == "table_page":
        cur.execute("SELECT table_page FROM callback_manager WHERE user_id == '%s'"% (chat_id,))
        page = cur.fetchone()[0]
    elif page_type == "context_page":
        cur.execute("SELECT context_page FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        page = cur.fetchone()[0]
    elif page_type == "description_page":
        cur.execute("SELECT description_page FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        page = cur.fetchone()[0]
    con.commit()
    con.close()
    return page

def change_page(chat_id, page_type, new_page):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    if page_type == "table_page":
        cur.execute("UPDATE callback_manager SET table_page = '%s' WHERE user_id == '%s'"% (new_page, chat_id))

    elif page_type == "context_page":
        cur.execute("UPDATE callback_manager SET context_page = '%s' WHERE user_id == '%s'" % (new_page, chat_id))

    elif page_type == "description_page":
        cur.execute("UPDATE callback_manager SET description_page = '%s' WHERE user_id == '%s'" % (new_page, chat_id))

    con.commit()
    con.close()

def get_pages_amount(chat_id):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (chat_id,))
    amount = len(cur.fetchall())//3 + 1

    con.commit()
    con.close()
    return amount
def create_inline_keyboard(chat_id=None, keyboard_type=None):
    markup = types.InlineKeyboardMarkup(row_width=3)
    prefix = keyboard_type[0]+"|"
    settings = get_settings(chat_id)
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))
    rows = cur.fetchall()
    con.commit()
    con.close()
    btn = None

    for row in rows:

        if row[0] is not None:
            btn = types.InlineKeyboardButton(text=row[0], callback_data=f"{prefix}{row[0]}")

            markup.add(btn)
    if keyboard_type == "tables":
        btn1 = types.InlineKeyboardButton(text="Добавить новую таблицу", callback_data="t|new_table")
        btn2 = types.InlineKeyboardButton(text="Очистить набор таблиц", callback_data="t|delete_tables")
        markup.row(btn1)

        if settings["table_name"] is not None and len(settings["table_name"]) > 0:
            bot.send_message(chat_id, f"Сейчас доступны для анализа: {settings['table_name']}")
            markup.add(btn2)
        page_type = "table_page"
        page = get_page(chat_id=chat_id, page_type=page_type)
        amount = get_pages_amount(chat_id=chat_id)
        markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data="t|exit")
        markup.add(btn3)
        right = types.InlineKeyboardButton(text="-->", callback_data="t|right")
        left = types.InlineKeyboardButton(text="<--", callback_data="t|left")
        markup.row(left, right)

    elif keyboard_type == "context":
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data="c|exit")
        markup.add(btn3)
        right = types.InlineKeyboardButton(text="-->", callback_data="c|right")
        left = types.InlineKeyboardButton(text="<--", callback_data="c|left")
        markup.row(left, right)
        page_type = "context_page"
        page = get_page(chat_id=chat_id, page_type=page_type)
        amount = get_pages_amount(chat_id=chat_id)
        markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))


    elif keyboard_type == "description":
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data="d|exit")
        markup.add(btn3)
        right = types.InlineKeyboardButton(text="-->", callback_data="d|right")
        left = types.InlineKeyboardButton(text="<--", callback_data="d|left")
        markup.row(left, right)
        page_type = "description_page"
        page = get_page(chat_id=chat_id, page_type=page_type)
        amount = get_pages_amount(chat_id=chat_id)
        markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))
    return markup


def on_click(message, settings=None):
    chat_id = message.chat.id

    if message.text == "❓ Режим отправки запроса":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        bot.send_message(chat_id, "Отправьте запроc. Пожалуйста, вводите запросы последовательно", reply_markup=markup)

        bot.register_next_step_handler(message, call_to_model, settings)
    elif message.text == "🖹 Выбрать таблицу":
        callback_type = "table_callback"
        table_callback = get_callback(chat_id=chat_id, callback_type=callback_type)
        if table_callback == 0:
            keyboard_type = "tables"
            markup = create_inline_keyboard(chat_id=chat_id, keyboard_type=keyboard_type)
            table_callback = 1
            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("UPDATE callback_manager SET table_callback = '%s'" % (table_callback,))
            con.commit()
            con.close()
            bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)
        bot.register_next_step_handler(message, on_click, settings)

    elif message.text == "🖻 Режим визуализации":
        if settings["build_plots"] == 0:
            build_plots = "выключен"
        else:
            build_plots = "включен"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Выключить")
        btn2 = types.KeyboardButton("Включить")
        markup.row(btn1, btn2)
        bot.send_message(chat_id, f"Можете выбрать режим визуализации данных, он  {build_plots}  в данный момент",
                         reply_markup=markup)
        bot.register_next_step_handler(message, plots_handler, settings)

    elif message.text == "➕ Добавить описание таблицы":
        keyboard_type = "description"
        callback_type = "description_callback"
        description_callback = get_callback(chat_id=chat_id, callback_type=callback_type)

        if description_callback == 0:

            markup = create_inline_keyboard(chat_id=chat_id, keyboard_type=keyboard_type)
            table_callback = 1
            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("UPDATE callback_manager SET description_callback = '%s'" % (table_callback,))
            con.commit()
            con.close()

            bot.send_message(chat_id, "Выберите, к какой таблице вы хотите добавить описание",
                         reply_markup=markup)
        bot.register_next_step_handler(message, on_click, settings)
    elif message.text == "Добавить контекст":
        keyboard_type = "context"
        callback_type = "context_callback"
        context_callback = get_callback(chat_id=chat_id, callback_type=callback_type)
        if context_callback == 0:
            markup = create_inline_keyboard(chat_id=chat_id, keyboard_type=keyboard_type)
            table_callback = 1
            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("UPDATE callback_manager SET context_callback = '%s'" % (table_callback,))
            con.commit()
            con.close()

            bot.send_message(chat_id, "Выберите, к какой таблице вы хотите добавить контекст",
                             reply_markup=markup)
        bot.register_next_step_handler(message, on_click, settings)

@bot.callback_query_handler(func=lambda call: call.data.startswith("t|"))
def callback_query(call):

    callback_type, action = map(str, call.data.split("|"))

    call.data = action
    chat_id = call.message.chat.id
    page_type = "table_page"
    page = get_page(chat_id=chat_id,page_type=page_type)
    if call.data == "exit":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE callback_manager SET table_callback = '%s'" % (0,))
        con.commit()
        bot.delete_message(call.message.chat.id, call.message.message_id)
    elif call.data == "new_table":
        bot.send_message(call.message.chat.id, "Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json")

        choose_table(call)
    elif call.data == "delete_tables":
        new_cur = ""
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE users SET current_tables = '%s'" % (new_cur,))
        con.commit()
        con.close()
    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "tables"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)




    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "tables"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)




    else:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))
        rows = cur.fetchall()
        con.commit()
        con.close()
        cnt = 0
        find_table_flag = False
        for row in rows:

            if row[0] is not None:
                if call.data == row[0]:
                    find_flag = True
                    choose_flag = True
                    choose_table(call, choose_flag)
        if not find_table_flag:
            bot.send_message(call.message.chat.id, "Эта таблица не была загружена")


@bot.callback_query_handler(func=lambda call: call.data.startswith("c|"))
def callback_query(call):
    callback_type, action = map(str, call.data.split("|"))
    call.data = action
    chat_id = call.message.chat.id
    page_type = "context_page"
    page = get_page(chat_id=chat_id, page_type=page_type)
    if call.data == "exit":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE callback_manager SET context_callback = '%s'" % (0,))
        con.commit()
        con.close()
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "context"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)

    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "context"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))
        rows = cur.fetchall()
        con.commit()
        con.close()
        find_table_flag = False
        for row in rows:

            if row[0] is not None:
                if call.data == row[0]:
                    find_table_flag = True
                    choose_flag = True
                    choose_table_context(call)
        if not find_table_flag:
            bot.send_message(call.message.chat.id, "Эта таблица не была загружена")


@bot.callback_query_handler(func=lambda call: call.data.startswith("d|"))
def callback_query(call):

    callback_type, action = map(str, call.data.split("|"))
    call.data = action

    chat_id = call.message.chat.id

    page_type = "description_page"
    page = get_page(chat_id=chat_id, page_type=page_type)
    if call.data == "exit":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE callback_manager SET description_callback = '%s'" % (0,))
        con.commit()
        con.close()
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "description"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "description"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))
        rows = cur.fetchall()
        con.commit()
        con.close()
        find_table_flag = False
        for row in rows:

            if row[0] is not None:
                if call.data == row[0]:

                    find_table_flag = True
                    choose_flag = True
                    table_description(call)
        if not find_table_flag:
            bot.send_message(call.message.chat.id, "Эта таблица не была загружена")


def choose_table_context(call, settings=None):
    chat_id = call.message.chat.id
    message = call.message

    bot.send_message(chat_id,
                     f"Таблица {call.data} выбрана, для добавления контекста отправьте текст или файл в формате txt или msg",
                     )
    bot.register_next_step_handler(message, add_context, settings, call.data)


def add_context(message, settings=None, table_name=None):
    chat_id = message.chat.id
    if message.text == "🚫 exit":
        main(message, settings)

    else:
        try:
            table_name = table_name

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn1 = types.KeyboardButton("🚫 exit")
            markup.add(btn1)
            if message.content_type == "text":
                context = str(message.text)

                con = sq.connect("user_data.sql")
                cur = con.cursor()
                cur.execute("""UPDATE tables SET context = '%s' WHERE table_name = '%s' and user_id = '%s' """ % (context, table_name, chat_id))
                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Контекст сохранен', reply_markup=markup)
                bot.register_next_step_handler(message, main, settings)
            elif message.content_type == "document":
                file_id = message.document.file_id
                file_info = bot.get_file(file_id)
                file_path = file_info.file_path

                downloaded_file = bot.download_file(file_path)
                src = "data/" + message.document.file_name
                if ".msg" in src:
                    with open(src, 'wb') as f:
                        f.write(downloaded_file)
                    context = msg_to_string(src)
                else:
                    context = downloaded_file.decode('utf-8')

                con = sq.connect("user_data.sql")
                cur = con.cursor()
                cur.execute("""UPDATE tables SET context = '%s' WHERE table_name = '%s' """ % (context, table_name))
                con.commit()
                con.close()
                bot.send_message(chat_id, 'Контекст сохранен', reply_markup=markup)
                bot.register_next_step_handler(message, main, settings)

        except Exception:
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            choose_table(message, settings, error_message_flag)


def choose_table(call, choose_flag=False):
    chat_id = call.message.chat.id
    text = call.data
    if choose_flag is False:
        bot.register_next_step_handler(call.message, add_table, call)
    else:
        settings = get_settings(chat_id)
        if text not in settings["table_name"]:
            if settings["table_name"] is not None:
                settings["table_name"] += "," + text
            else:
                settings["table_name"] = text
            bot.send_message(chat_id, "Таблица выбрана.")
            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute(
                "UPDATE users SET current_tables = '%s' WHERE user_id == '%s'" % (settings["table_name"], chat_id))
            con.commit()
            con.close()

        else:
            bot.send_message(chat_id, "Данная таблица уже добавлена в список")



def add_table(message, call=None):
    chat_id = message.chat.id
    settings = get_settings(chat_id)
    if message.text == "🚫 exit":
        main(message, settings)

    else:
        try:

            settings = get_settings(chat_id)

            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path

            downloaded_file = bot.download_file(file_path)
            src = "data/" + message.document.file_name

            with open(src, 'wb') as f:
                f.write(downloaded_file)

            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("""INSERT OR REPLACE INTO tables(user_id, table_name) VALUES(?,?)""", (chat_id, message.document.file_name))
            con.commit()
            cur.execute("SELECT * FROM tables")

            if settings["table_name"] is not None:
                settings["table_name"] += "," + message.document.file_name
            else:
                settings["table_name"] = message.document.file_name

            cur.execute("UPDATE users SET current_tables = '%s' WHERE user_id == '%s'" %(message.document.file_name, chat_id))
            con.commit()
            con.close()
            bot.reply_to(message, 'Файл сохранен')
            keyboard_type = "tables"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id,  keyboard_type=keyboard_type)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
            main(message, settings)
        except Exception as e:
            print(e)
            bot.send_message(chat_id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            bot.register_next_step_handler(message, add_table, settings)

# function that contains all params that was set by user and will be used during interaction with model


def plots_handler(message, settings=None):

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Вернуться в главное меню")
    markup.add(btn1)
    con = sq.connect("user_data.sql")
    cur = con.cursor()

    if message.text == "Выключить":
        settings["build_plots"] = 0
        cur.execute("UPDATE users SET build_plots = '%s'" % (settings["build_plots"]))
        con.commit()
        bot.send_message(message.chat.id, "Режим визуализации отключён", reply_markup=markup)
        bot.register_next_step_handler(message, main, settings)
    elif message.text == "Включить":
        settings["build_plots"] = 1
        cur.execute("UPDATE users SET build_plots = '%s'" % (settings["build_plots"]))
        con.commit()
        bot.send_message(message.chat.id, "Режим визуализации включён", reply_markup=markup)
        bot.register_next_step_handler(message, main, settings)


def table_description(call, settings=None):
    table_name = call.data
    message = call.message
    bot.send_message(message.chat.id,
                         "Таблица выбрана. Чтобы добавить описание таблицы, отправьте файл с описанием столбцов в формате txt или качестве сообщения.")
    bot.register_next_step_handler(message, choose_description, settings, table_name)


def choose_description(message, settings=None, table_name=None):
    table_name = table_name
    chat_id = message.from_user.id
    if message.content_type == "text":
        description = str(message.text)

        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))

        existing_record = cur.fetchall()
        if existing_record:
            cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' and user_id = '%s' """ % (description, table_name, chat_id))

        con.commit()
        con.close()
        bot.send_message(message.from_user.id, 'Описание сохранено')
        main(message, settings)
    elif message.content_type == "document":
        try:
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path

            downloaded_file = bot.download_file(file_path)
            src = "data/" + message.document.file_name

            description = downloaded_file.decode('utf-8')

            con = sq.connect("user_data.sql")
            cur = con.cursor()

            cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' """ % (description, table_name))
            con.commit()
            con.close()
            main(message, settings)

        except:
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            bot.register_next_step_handler(message, table_description, settings)


# to do: there should be some ways to optimize interaction with database

def call_to_model(message, settings=None):

    if message.text == "🚫 exit":
        main(message, settings)
    else:
        chat_id = message.chat.id

        def callback(sum_on_step):
            message_id = send_message.message_id

            edited_message = bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                   text=send_message.text + f"\n{sum_on_step}")
        settings = get_settings(chat_id)

        user_question = message.text
        table_name = list(map(str, settings["table_name"].split(",")))
        print("available tables for model:", table_name)
        context_line = ""
        table_description_line = ""
        try:
            if settings["table_name"] is None:
                bot.send_message(message.from_user.id, "Таблица не найдена, вы можете выбрать другую")
                bot.register_next_step_handler(message, main, settings)
                markup = types.ReplyKeyboardMarkup()
                btn1 = types.KeyboardButton("🚫 exit")
                markup.add(btn1)
                bot.send_message(message.from_user.id,
                             "Вы можете выйти из режима работы с моделью с помощью 'exit'",
                             reply_markup=markup)
            else:

                table_name_path = table_name.copy()
                for table in range(len(table_name_path)):
                    table_name_path[table] = "data/" + table_name_path[table]
                con = sq.connect("user_data.sql")
                for table in table_name:

                    cur = con.cursor()
                    cur.execute("SELECT * FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, table))
                    existing_record = cur.fetchone()

                    if existing_record:

                        cur.execute("SELECT table_description FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, table))
                        table_description = cur.fetchone()

                        if not table_description or table_description[0] is None:
                            table_description_line = table + ":"
                        else:
                            table_description_line = table + ":" + table_description[0]

                    con.commit()

                    cur.execute("SELECT context FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, table))
                    context = cur.fetchone()

                    if not context or context[0] is None:
                        context_line += table + ":"
                    else:
                        context_line += table + ":" + context[0]
                print(context_line)
                print(table_description_line)
                cur = con.cursor()

                cur.execute("SELECT conv_sum FROM users WHERE user_id = '%s'" % (chat_id,))
                current_summary = cur.fetchone()

                if not current_summary or current_summary[0] is None:
                    current_summary = ""
                else:
                    current_summary = current_summary[0]


                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                btn1 = types.KeyboardButton("🚫 exit")

                markup.add(btn1)

                bot.send_message(message.from_user.id,
                                 "Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью 'exit'",
                                 reply_markup=markup)
                send_message = bot.send_message(message.from_user.id, "Здесь будет описан процесс моих рассуждений:")

                build_plots = settings["build_plots"]
                answer_from_model = interactor.run_loop_bot(table_name_path, build_plots, user_question, current_summary,
                                                            table_description_line, context_line, callback=callback)
                summary = answer_from_model[1]
                new_summary = current_summary + summary

                cur.execute("INSERT OR REPLACE INTO users(user_id, conv_sum) VALUES(?, ?)", (chat_id, new_summary))

                cur.execute("select * from users")
                con.commit()
                con.close()

                time.sleep(10)
                pattern = r"\b\w+\.png\b"
                if ".png" in answer_from_model[1]:

                    plot_files = re.findall(pattern, answer_from_model[1])
                    for plot_file in plot_files:
                        path_to_file = "Plots/" + plot_file

                        if os.path.exists(path_to_file):
                            bot.send_photo(message.from_user.id, open(path_to_file, "rb"))
                    for plot_file in plot_files:

                        path_to_file = "Plots/" + plot_file
                        if os.path.exists(path_to_file):
                            os.remove(path_to_file)
                    matplotlib.pyplot.close("all")
                    bot.send_message(message.from_user.id, f"Answer: {answer_from_model[0]}")
                else:
                    bot.send_message(message.from_user.id, f"Answer: {answer_from_model[0]}")
                bot.register_next_step_handler(message, call_to_model, settings)
        except requests.exceptions.ConnectionError:
            bot.send_message(message.from_user.id, "Что-то пошло не так")
            main(user_question, settings)


#try:
    #bot.polling()
#except Exception as e:
    #print("error is:", e)
    #time.sleep(2)
bot.polling()