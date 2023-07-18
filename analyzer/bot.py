import os
import telebot
import sqlite3 as sq
import interactor
import time
import traceback
import requests


import re
import yaml
import matplotlib
matplotlib.use('Agg')

from telebot import types
from msg_parser import msg_to_string
from db_manager import *
from inline_keyboard_manager import *

user_question = None

plot_files = ""


with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

bot_name = cfg["bot_name"]
bot_api = cfg["bot_api"]
demo = cfg["demo"][0]
max_requests = cfg["demo"][1]
reset = cfg["demo"][2]
db_name = cfg["db_name"]


class Bot(telebot.TeleBot):
    def __init__(self):
        self.name = bot_name
        super().__init__(bot_api)


bot = Bot()

connection = sq.connect(db_name)
cursor = connection.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users
              (user_id INTEGER PRIMARY KEY,
              conv_sum TEXT,
              current_tables VARCHAR,
              build_plots boolean DEFAULT 1
              )""")
connection.commit()

cursor.execute("""CREATE TABLE IF NOT EXISTS groups
              (group_id INTEGER PRIMARY KEY AUTOINCREMENT,
              admin_id INTEGER,
              group_plot boolean DEFAULT 1,
              group_name VARCHAR,
              group_link VARCHAR,
              group_conv TEXT,
              current_tables VARCHAR,
              design_flag boolean DEFAULT 0)""")
connection.commit()

cursor.execute("""CREATE TABLE IF NOT EXISTS callback_manager
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

cursor.execute("""CREATE TABLE IF NOT EXISTS group_manager
                                  (admin_id INTEGER,
                                  group_name,
                                  table_page INTEGER DEFAULT 1,
                                  context_page INTEGER DEFAULT 1,
                                  description_page INTEGER DEFAULT 1)
                                  """)
connection.commit()

cursor.execute(""" CREATE TABLE IF NOT EXISTS tables 
                (table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, 
                table_name VARCHAR,
                table_description TEXT,
                context TEXT,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
connection.commit()

connection.close()


@bot.message_handler(commands=["help"])
def help_info(message):
    bot.send_message(message.chat.id, """Здравствуйте, автономный помощник для проведения различной аналитики \n 
Я могу отвечать на вопросы по предоставленным данным, строить графики и проводить нужные вычисления""")
    bot.send_message(message.chat.id, """* Используйте кнопку 'Выбрать Таблицу' для выбора и добавления таблиц \n
* Используйте кнопку 'Добавить описание' для добавления описания к нужным таблицам \n
* Используйте кнопку 'Добавить контекст' для добавления контекста к нужным таблицам \n
* Используйте кнопку 'Режим отправки запроса' для взаимодействия со мной\n
* Используйте кнопку 'Режим визуализации' для настройки режима построения графиков \n
* Используйте кнопку 'Группы таблиц' для создания и настройки групп таблиц""")
    bot.send_message(message.chat.id, """Пример  запроса: 'Проведи исследовательский анализ данных по предоставленной таблице'""")
    bot.send_message(message.chat.id, """Для того, чтобы начать общение с ботом: \n
1) Нажмите кнопку 'Выбрать таблицу', затем добавьте новую таблицу или воспользуйтесь уже добавленной \n
2) После этого вы можете добавить описание и контекст к вашим данным для лучшей работы модели \n
3) Нажмите кнопку 'Режим отправки запроса' и напишите свой запрос модели, дождитесь ответа, \n
после получения ответа можете задать вопрос или выйти из режима в главное меню""")
    bot.send_message(message.chat.id, "В случае проблем с ботом попробуйте перезапустить его через команду '/start'")


@bot.message_handler(commands=["start", "exit"], content_types=["text", "document"])
def main(message=None):
    try:
        chat_id = message.chat.id

    except Exception as e:
        chat_id = message
        print(message)
        print(e)

    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT * FROM callback_manager WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("INSERT  INTO callback_manager(user_id) VALUES(?)", (chat_id,))
    con.commit()

    cur.execute("SELECT * FROM users WHERE user_id = ?", (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("""INSERT INTO users(user_id) values(?)""", (chat_id,))

    cur.execute("SELECT * FROM users")

    con.commit()
    con.close()

    # to do: fix this
    if message.text is not None:
        if "/start" in message.text:
            is_group = check_for_group(message)
        else:
            is_group = False
    else:
        is_group = False

    if not is_group:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🖹 Выбрать таблицу")
        btn2 = types.KeyboardButton("➕ Добавить описание таблицы")
        btn3 = types.KeyboardButton("🖻 Режим визуализации")
        btn4 = types.KeyboardButton("❓ Режим отправки запроса")
        btn5 = types.KeyboardButton("Добавить контекст")
        btn6 = types.KeyboardButton("Группы таблиц")
        markup.row(btn1, btn2, btn3)
        markup.row(btn4, btn5, btn6)
        bot.send_message(chat_id, "Вы можете  выбрать одну из опций", reply_markup=markup)

    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn4 = types.KeyboardButton("❓ Режим отправки запроса")
        markup.row(btn4)
        bot.send_message(chat_id, "Вы можете  выбрать одну из опций", reply_markup=markup)


def create_inline_keyboard(chat_id=None, page_type=None, page=1, status_flag=True):
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
            offset = ((page-1)*3)
    markup = types.InlineKeyboardMarkup(row_width=3)
    prefix = page_type[0]+"|"
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
            btn = types.InlineKeyboardButton(text=prepared_row, callback_data=f"{prefix}{row[0]}")

            markup.add(btn)
    if page_type == "table_page":
        btn1 = types.InlineKeyboardButton(text="Добавить новую таблицу", callback_data=f"t|new_table")
        btn2 = types.InlineKeyboardButton(text="Убрать последнюю таблицу из набора", callback_data=f"t|delete_tables")
        markup.row(btn1)

        if settings["table_name"] is not None and len(settings["table_name"]) > 0:
            if status_flag:
                bot.send_message(chat_id, f"Сейчас доступны для анализа: {settings['table_name']}")
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

# to do: better foreign keys


def group_main(message=None):

    chat_id = message.chat.id
    group_name = check_group_design(chat_id)
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("select * from groups")
    print(cur.fetchall())

    if message.text == "Нет":

        cur.execute("UPDATE groups SET design_flag = False WHERE admin_id == ? AND group_name == ?", (chat_id, group_name))
        con.commit()

        main(message)
    else:
        cur.execute("""CREATE TABLE IF NOT EXISTS group_tables
                               (group_name VARCHAR,
                               admin_id INTEGER,
                               table_name VARCHAR,
                               table_description TEXT,
                               context TEXT)
                               """)
        con.commit()

        chat_id = message.chat.id
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🖹 Выбрать таблицу")
        btn2 = types.KeyboardButton("➕ Добавить описание таблицы")
        btn3 = types.KeyboardButton("🖻 Режим визуализации")
        btn4 = types.KeyboardButton("exit")
        btn5 = types.KeyboardButton("Добавить контекст")
        btn6 = types.KeyboardButton("Сохранить настройки группы")
        markup.row(btn1, btn2, btn3)
        markup.row(btn5, btn4, btn6)
        bot.send_message(chat_id, "Вы можете  выбрать одну из опций", reply_markup=markup)
        con.close()


@bot.message_handler(func=lambda message: message.text == "❓ Режим отправки запроса")
def request_mode(message):
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🚫 exit")
    markup.add(btn1)
    bot.send_message(chat_id, "Отправьте запроc. Пожалуйста, вводите запросы последовательно", reply_markup=markup)

    bot.register_next_step_handler(message, call_to_model)


@bot.message_handler(func=lambda message: message.text == "🖹 Выбрать таблицу")
def table_click(message):
    chat_id = message.chat.id
    group_name = check_group_design(chat_id)
    page_type = "table_page"
    markup = create_inline_keyboard(chat_id=chat_id, page_type=page_type)

    bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)

    if group_name is not None:
        group_main(message)
    else:
        main(message)


@bot.message_handler(func=lambda message: message.text == "🖻 Режим визуализации")
def plot_on_click(message):
    chat_id = message.chat.id
    settings = get_settings(chat_id)
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
    bot.register_next_step_handler(message, plots_handler)


@bot.message_handler(func=lambda message: message.text == "➕ Добавить описание таблицы")
def desc_on_click(message):
    chat_id = message.chat.id
    group_name = check_group_design(chat_id)
    page_type = "description_page"
    markup = create_inline_keyboard(chat_id=chat_id, page_type=page_type)

    bot.send_message(chat_id, "Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)

    if group_name is not None:
        group_main(message)
    else:
        main(message)


@bot.message_handler(func=lambda message: message.text == "Добавить контекст")
def context_on_click(message):
    chat_id = message.chat.id
    group_name = check_group_design(chat_id)
    page_type = "context_page"
    markup = create_inline_keyboard(chat_id=chat_id, page_type=page_type)
    bot.send_message(chat_id, "Выберите, к какой таблице вы хотите добавить контекст", reply_markup=markup)
    if group_name is not None:
        group_main(message)
    else:
        main(message)


@bot.message_handler(func=lambda message: message.text == "Группы таблиц")
def groups_on_click(message):
    chat_id = message.chat.id
    markup = create_group_keyboard(chat_id)
    bot.send_message(chat_id, "Вы можете выбрать одну из опций", reply_markup=markup)
    main(message)


@bot.message_handler(func=lambda message: message.text == "exit")
def exit_from_group(message):
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("UPDATE groups SET design_flag = 0 WHERE admin_id == ? ", (message.chat.id,))
    con.commit()
    con.close()
    main(message)
    bot.send_message(message.chat.id, "Редактирование группы завершено")


@bot.message_handler(func=lambda message: message.text == "Сохранить настройки группы")
def save_group_settings(message):
    group_name = check_group_design(message.chat.id)
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT group_link FROM groups where admin_id == ? AND group_name == ?", (message.chat.id, group_name))
    con.commit()

    group_link = cur.fetchone()

    cur.execute("UPDATE groups SET design_flag = 0 WHERE admin_id == ?", (message.chat.id,))
    con.commit()

    if group_link is not None:
        group_link = group_link[0]
    con.close()
    bot.send_message(message.chat.id, "Изменения группы сохранены, ссылка для взаимодействия с группой: ")
    bot.send_message(message.chat.id, f'{group_link}')
    main(message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("t|"))
def callback_query(call):

    callback_type, action = map(str, call.data.split("|"))

    call.data = action
    chat_id = call.message.chat.id

    group_name = check_group_design(chat_id=chat_id)
    page_type = "table_page"
    page = get_page(chat_id=chat_id, page_type=page_type)
    if call.data == "exit":

        bot.delete_message(call.message.chat.id, call.message.message_id)
    elif call.data == "new_table":
        bot.send_message(call.message.chat.id, "Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json")

        choose_table(call)
    elif call.data == "delete_tables":
        settings = get_settings(chat_id)
        table_name = list(map(str, settings["table_name"].split(",")))
        bot.send_message(chat_id, f"Таблица {table_name[-1]} удалена из текущего списка")

        table_name = table_name[:-1]
        if len(table_name) == 0:
            settings["table_name"] = ''
        else:
            settings["table_name"] = ''
            for i in range(len(table_name)-1):
                settings["table_name"] += table_name[i] + ","
            settings["table_name"] += table_name[-1]

        con = sq.connect(db_name)
        cur = con.cursor()
        if group_name is not None:
            cur.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?", (settings["table_name"], chat_id, group_name))
            con.commit()
        else:
            cur.execute("UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
            con.commit()

        con.close()

    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            page_type = "table_page"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)

    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            page_type = "table_page"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:

        choose_flag = True
        choose_table(call, choose_flag)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("c|"))
def callback_query(call):
    callback_type, action = map(str, call.data.split("|"))
    call.data = action
    chat_id = call.message.chat.id

    page_type = "context_page"
    page = get_page(chat_id=chat_id, page_type=page_type)
    if call.data == "exit":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            page_type = "context_page"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)

    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            page_type = "context_page"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:

        choose_table_context(call)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("d|"))
def callback_query(call):

    callback_type, action = map(str, call.data.split("|"))
    call.data = action

    chat_id = call.message.chat.id
    group_name = check_group_design(chat_id)
    page_type = "description_page"
    page = get_page(chat_id=chat_id, page_type=page_type)
    if call.data == "exit":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            page_type = "description_page"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "description_page"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:
        table_description(call)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("g|"))
def callback_query(call):
    callback_type, action = map(str, call.data.split("|"))
    call.data = action

    chat_id = call.message.chat.id
    group_name = check_group_design(chat_id)
    if call.data == "exit":
        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("UPDATE groups SET design_flag = True WHERE admin_id == ? AND group_name == ?", (chat_id, group_name))
        con.commit()
        con.close()
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "create_group":
        bot.send_message(chat_id, "Дайте название группе")
        bot.register_next_step_handler(call.message, create_group)

    elif call.data == "choose_group":
        markup = create_group_keyboard(chat_id=chat_id, show_groups=True)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Вы можете выбрать группу",
                              reply_markup=markup)
    elif call.data == "back":
        markup = create_group_keyboard(chat_id=chat_id, show_groups=False)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Вы можете выбрать группу или добавить новую",
                              reply_markup=markup)
    else:
        choose_group(group_name=call.data, admin_id=call.message.chat.id, message=call.message)
    bot.answer_callback_query(call.id)


def choose_table_context(call):
    chat_id = call.message.chat.id
    message = call.message

    bot.send_message(chat_id,
                     f"Таблица {call.data} выбрана, для добавления контекста отправьте текст или файл в формате txt или msg",
                     )
    bot.register_next_step_handler(message, add_context, call.data)


def add_context(message, table_name=None):
    con = sq.connect(db_name)
    cur = con.cursor()
    chat_id = message.chat.id
    try:
        table_name = table_name
        group_name = check_group_design(chat_id)
        if message.content_type == "text":
            context = str(message.text)


            if group_name is not None:
                cur.execute("""UPDATE group_tables SET context = ? WHERE table_name == ? and admin_id == ? and group_name == ? """, (context, table_name, chat_id, group_name))
                con.commit()

                bot.send_message(message.from_user.id, 'Контекст сохранен')
                group_main(message)

            else:
                cur.execute("""UPDATE tables SET context = ? WHERE table_name == ? and user_id == ? """, (context, table_name, chat_id))
                con.commit()

                con.close()
                bot.send_message(message.from_user.id, 'Контекст сохранен')

                main(message)
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
            if group_name is not None:
                cur.execute("""UPDATE group_tables SET context = ? WHERE table_name == ? and admin_id == ? and group_name == ? """, (context, table_name, chat_id, group_name))
                con.commit()

                bot.send_message(chat_id, 'Контекст сохранен')
                group_main(message)
            else:
                cur.execute("""UPDATE tables SET context = ? WHERE table_name = ? and user_id == ? """, (context, table_name, chat_id))
                con.commit()

                bot.send_message(chat_id, 'Контекст сохранен')
                main(message)
        con.close()
    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Что-то пошло не так, попробуйте другой файл")
        error_message_flag = True
        add_context(message, error_message_flag)


def choose_table(call, choose_flag=False):
    try:
        chat_id = call.message.chat.id
        text = call.data
        message = call.message
    except Exception as e:
        print(e)
        chat_id = call.chat.id
        text = call.text
        message = call

    if choose_flag is False:
        bot.register_next_step_handler(message, add_table, call)
    else:
        group_name = check_group_design(chat_id)
        settings = get_settings(chat_id)

        if settings["table_name"] is not None and len(settings["table_name"]) != 0:
            if text not in settings["table_name"]:
                settings["table_name"] += ", " + text
                bot.send_message(chat_id, "Таблица добавлена")
            else:
                bot.send_message(chat_id, "Данная таблица уже добавлена в список")
        else:

            settings["table_name"] = text
            bot.send_message(chat_id, "Таблица выбрана.")
        con = sq.connect(db_name)
        cur = con.cursor()
        if group_name is not None:
            cur.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? and group_name == ?", (settings["table_name"], chat_id, group_name))
            con.commit()
        else:

            cur.execute(
                "UPDATE users SET current_tables = ? WHERE user_id == ?", (settings["table_name"], chat_id))
            con.commit()
        con.close()


def add_table(message, call=None):

    chat_id = message.chat.id
    message = message
    group_name = check_group_design(chat_id)
    if message.text == "🚫 exit":
        main(message)

    else:
        try:
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path

            downloaded_file = bot.download_file(file_path)
            src = "data/" + str(chat_id) + "_" + message.document.file_name
            src.replace("|", "_")
            message.document.file_name = str(chat_id) + "_" + message.document.file_name
            with open(src, 'wb') as f:
                f.write(downloaded_file)

            con = sq.connect(db_name)
            cur = con.cursor()
            if group_name is not None:
                cur.execute("SELECT * FROM group_tables WHERE admin_id == ? AND table_name == ?", (chat_id, message.document.file_name))
                existing_record = cur.fetchone()

                if existing_record is None:
                    cur.execute("""INSERT INTO group_tables(admin_id, group_name, table_name) VALUES(?,?,?)""",
                                (chat_id, group_name, message.document.file_name))
                    con.commit()
                    cur.execute("select * from group_tables")
                    # print("group_tables", cur.fetchall())
                    cur.execute("UPDATE groups SET current_tables = ? WHERE admin_id == ? AND group_name == ?", (message.document.file_name, chat_id, group_name))
                    con.commit()

                    con.close()
                    bot.reply_to(message, 'Файл сохранен')
                    page_type = "table_page"
                    markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type)
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Вы можете выбрать таблицу или добавить новую",
                                          reply_markup=markup2)

                    group_main(message)
                else:
                    bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")
                    bot.register_next_step_handler(message, add_table, call)

            else:

                cur.execute("SELECT * FROM tables WHERE user_id == ? AND table_name == ?", (chat_id, message.document.file_name))
                existing_record = cur.fetchone()

                if existing_record is None:
                    cur.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""", (chat_id, message.document.file_name))
                    con.commit()
                    cur.execute("UPDATE users SET current_tables = ? WHERE user_id == ?", (message.document.file_name, chat_id))
                    con.commit()

                    con.close()
                    bot.reply_to(message, 'Файл сохранен')
                    page_type = "table_page"
                    markup2 = create_inline_keyboard(chat_id=call.message.chat.id, page_type=page_type)
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Вы можете выбрать таблицу или добавить новую",
                                      reply_markup=markup2)

                    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                    btn1 = types.KeyboardButton("Нет")
                    btn2 = types.KeyboardButton("Да")
                    markup.row(btn2, btn1)
                    bot.send_message(chat_id, "Хотите ли вы получить предварительную информацию по таблице?",
                                     reply_markup=markup)
                    bot.register_next_step_handler(message, call_to_model)

                else:
                    bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")
                    bot.register_next_step_handler(message, add_table, call)

                con.close()

        except telebot.apihelper.ApiTelegramException:
            bot.register_next_step_handler(message, add_table, call)

        except Exception as e:
            print(e)
            bot.send_message(chat_id, "Что-то пошло не так, попробуйте другой файл")

            bot.register_next_step_handler(message, add_table, call)


def plots_handler(message, settings=None):
    chat_id = message.chat.id
    settings = get_settings(chat_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Вернуться в главное меню")
    markup.add(btn1)
    con = sq.connect(db_name)
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if message.text == "Выключить":

        if group_name is not None:
            cur.execute("UPDATE groups SET group_plot = 0 WHERE admin_id == ?", (chat_id,))
            bot.register_next_step_handler(message, group_main)
        else:
            cur.execute("UPDATE users SET build_plots = 0 where user_id == ?", (chat_id,))
            bot.register_next_step_handler(message, main)
        con.commit()
        bot.send_message(message.chat.id, "Режим визуализации отключён", reply_markup=markup)

    elif message.text == "Включить":

        if group_name is not None:
            cur.execute("UPDATE groups SET group_plot = 1 WHERE admin_id == ?", (chat_id,))
            bot.register_next_step_handler(message, group_main)
        else:
            cur.execute("UPDATE users SET build_plots = 1 where user_id == ?", (chat_id,))
            bot.register_next_step_handler(message, main)
        con.commit()
        bot.send_message(message.chat.id, "Режим визуализации включён", reply_markup=markup)
    con.close()


def table_description(call):
    table_name = call.data
    message = call.message
    bot.send_message(message.chat.id, """Таблица выбрана. Чтобы добавить описание таблицы, отправьте файл с описанием столбцов в формате txt или качестве сообщения.""")

    bot.register_next_step_handler(message, choose_description, table_name)


def choose_description(message, table_name=None):
    table_name = table_name
    con = sq.connect(db_name)
    cur = con.cursor()
    chat_id = message.from_user.id
    group_name = check_group_design(chat_id)
    if message.content_type == "text":
        description = str(message.text)
        if group_name is not None:

            cur.execute("select table_name from group_tables where admin_id == ? and group_name == ?", (chat_id, group_name))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute(
                    """UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ?""", (
                    description, table_name, chat_id, group_name))

            con.commit()
            con.close()
            bot.send_message(message.from_user.id, 'Описание сохранено')
            group_main(message)
        else:

            cur.execute("select table_name from tables where user_id == ?", (chat_id,))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? and user_id = ? """, (description, table_name, chat_id))

            con.commit()
            con.close()
            bot.send_message(message.from_user.id, 'Описание сохранено')
            main(message)
    elif message.content_type == "document":
        try:
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path

            downloaded_file = bot.download_file(file_path)
            src = "data/" + message.document.file_name

            description = downloaded_file.decode('utf-8')

            if group_name is not None:
                cur.execute("select table_name from group_tables where admin_id == ? and group_name == ?", (chat_id, group_name))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute("""UPDATE group_tables SET table_description = ? WHERE table_name == ? and admin_id == ? and group_name == ? """, (description, table_name, chat_id, group_name))
                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Описание сохранено')
                group_main(message)

            else:
                cur.execute("select table_name from tables where user_id == ?", (chat_id,))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute("""UPDATE tables SET table_description = ? WHERE table_name == ? """, (description, table_name))
                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Описание сохранено')
                main(message)

        except Exception as e:
            print(e)
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            bot.register_next_step_handler(message, table_description)


def create_group(message):
    admin_id = message.chat.id
    group_name = message.text.replace(" ", "-")
    group_name_for_link = "group_" + str(admin_id) + "_" + message.text.replace(" ", "-")
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("SELECT * FROM groups WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
    existing_record = cur.fetchone()
    if existing_record is None:
        cur.execute("INSERT INTO groups(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        con.commit()
        group_link = "https://t.me/auto_analyzer_bot?start=" + group_name_for_link
        cur.execute("UPDATE groups SET group_link = ? WHERE admin_id == ? and group_name == ? ", (group_link, admin_id, group_name))
        con.commit()
        cur.execute("INSERT INTO group_manager(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        con.commit()
        con.close()
        bot.send_message(admin_id, "Группа создана")
    else:
        bot.send_message(admin_id, "Данная группа уже создавалась")
    main(message)


def choose_group(group_name=None, admin_id=None, message=None):
    con = sq.connect(db_name)
    cur = con.cursor()
    cur.execute("UPDATE groups SET design_flag = True WHERE admin_id == ? AND group_name == ?", (admin_id, group_name))
    con.commit()
    cur.close()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Да")
    btn2 = types.KeyboardButton("Нет")
    markup.row(btn1, btn2)
    bot.send_message(message.chat.id, f"Вы точно ходите перейти к редактированию группы {group_name}?", reply_markup=markup)
    bot.register_next_step_handler(message, group_main)


def call_to_model(message):

    if demo:
        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("SELECT req_count FROM callback_manager WHERE user_id == ?", (message.chat.id,))
        req_count = cur.fetchone()[0]
        if reset:
            req_count = 0
            cur.execute("UPDATE callback_manager SET req_count = 0")
            con.commit()


        if req_count > max_requests:
            bot.send_message(message.chat.id, "К сожалению, лимит запросов исчерпан, попробуйте позднее")
            bot.register_next_step_handler(message, main)
        req_count += 1

        cur.execute("UPDATE callback_manager SET req_count = ? WHERE user_id == ?", (req_count, message.chat.id))
        con.commit()
        con.close()

    if message.text == "🚫 exit":
        con = sq.connect(db_name)
        cur = con.cursor()
        cur.execute("UPDATE callback_manager SET group_flag = 0 WHERE user_id == ?", (message.chat.id,))
        con.commit()
        con.close()
        main(message)

    elif message.text == "Нет":
        main(message)

    else:
        if message.text == "Да":
            user_question = "Проведи исследовательский анализ данных по таблице"
        else:
            user_question = message.text

        chat_id = message.chat.id

        def callback(sum_on_step):
            message_id = send_message.message_id

            edited_message = bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                   text=send_message.text + f"\n{sum_on_step}")
        settings = get_settings(chat_id)

        try:
            if settings["table_name"] is None or settings["table_name"] == "":
                bot.send_message(message.from_user.id, "Таблицы не найдены, вы можете выбрать другие")
                bot.register_next_step_handler(message, main)
                markup = types.ReplyKeyboardMarkup()
                btn1 = types.KeyboardButton("🚫 exit")
                markup.add(btn1)
                bot.send_message(message.from_user.id,
                             "Вы можете выйти из режима работы с моделью с помощью 'exit'",
                             reply_markup=markup)
            else:
                table_name = list(map(str, settings["table_name"].split(",")))
                print("available tables for model:", table_name)

                table_name_path = table_name.copy()

                for table in range(len(table_name_path)):
                    table_name_path[table] = "data/" + table_name_path[table].strip()

                table_description: list[str] = get_description(chat_id)
                context_list = get_context(chat_id)

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
                                                            table_description, context_list, callback=callback)
                if answer_from_model[0] == "F":
                    bot.send_message(message.chat.id, "Что-то пошло не так, пожалуйста, повторяю запрос")
                    answer_from_model = interactor.run_loop_bot(table_name_path, build_plots, user_question,
                                                                current_summary,
                                                                table_description, context_list, callback=callback)
                    if answer_from_model[0] == "F":
                        bot.send_message(message.chat.id, "Что-то пошло не так")

                summary = answer_from_model[1]
                new_summary = current_summary + summary
                print(summary)

                if group_flag:
                    cur.execute("UPDATE groups SET group_conv = ? WHERE admin_id == ? AND group_name == ?", (new_summary, admin_id, group_name))

                else:
                    cur.execute("UPDATE users SET conv_sum = ? WHERE user_id == ?", (new_summary, chat_id))

                con.commit()
                con.close()

                time.sleep(10)
                pattern = r"\b\w+\.png\b"
                if ".png" in answer_from_model[1]:
                    print("PLOT TRY IS HERE")

                    plot_files = re.findall(pattern, answer_from_model[1])
                    print("plot_files",  plot_files)
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
                bot.register_next_step_handler(message, call_to_model)
        except requests.exceptions.ConnectionError:
            bot.send_message(message.from_user.id, "Что-то пошло не так")
            main(user_question)

while True:
    try:
        bot.polling()
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(traceback.format_exc())
        print("error is:", e)

