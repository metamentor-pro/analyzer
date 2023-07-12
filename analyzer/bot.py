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
demo = cfg["demo"][0]
max_requests = cfg["demo"][1]
reset = cfg["demo"][2]


class Bot(telebot.TeleBot):
    def __init__(self):
        self.name = bot_name
        super().__init__(bot_api)


bot = Bot()


def check_for_group(message):

    try:
        text = message.text
        start, group_data = map(str, text.split())
        group, admin_id, group_name = map(str, text.split("_"))


    except Exception as e:
        print(e)
        return False
    print(message.text)
    if start == "/start":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("SELECT * FROM groups where group_name == '%s'" % (group_name,))
        existing_record = cur.fetchone()
        cur.execute("UPDATE callback_manager SET group_flag = '%s' WHERE user_id =='%s'" % (True, message.chat.id))
        con.commit()
        cur.execute("UPDATE callback_manager SET group_name = '%s' WHERE user_id == '%s'" % (group_name, message.chat.id))
        con.commit()
        cur.execute("UPDATE callback_manager SET admin_id = '%s' WHERE user_id == '%s'" % (admin_id, message.chat.id))
        con.commit()
        con.close()
        if existing_record is not None:

            return True
        else:
            return False
    else:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == '%s' " % (message.chat_id,))
        is_group = cur.fetchone()[0]
        if is_group:
            return True
        else:
            return False


def check_group_design(chat_id=None):

    admin_id = chat_id
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT  group_name FROM groups where admin_id = '%s' AND design_flag == 1 " % (admin_id,))
    group_name = cur.fetchone()
    if group_name is not None:
        return group_name[0]
    else:
        return None


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
    bot.send_message(message.chat.id, "Желаю удачи!")


@bot.message_handler(commands=["start", "exit"], content_types=["text", "document"])
def main(message=None):
    try:
        chat_id = message.chat.id

    except Exception as e:
        chat_id = message
        print(message)
        print(e)


    con = sq.connect("user_data.sql")
    cur = con.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY,
                conv_sum TEXT,
                current_tables VARCHAR,
                build_plots boolean DEFAULT True
                )""")
    con.commit()

    cur.execute("""CREATE TABLE IF NOT EXISTS groups
                (group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                group_plot boolean DEFAULT True,
                group_name VARCHAR,
                group_link VARCHAR,
                group_conv TEXT,
                current_tables VARCHAR,
                design_flag boolean DEFAULT False)""")
    con.commit()

    cur.execute("""CREATE TABLE IF NOT EXISTS callback_manager
                (user_id INTEGER PRIMARY KEY,
                table_page INTEGER DEFAULT 1,
                context_page INTEGER DEFAULT 1,
                description_page INTEGER DEFAULT 1,
                group_flag boolean DEFAULT False,
                group_name VARCHAR,
                admin_id INTEGER,
                req_count INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    con.commit()

    cur.execute("SELECT * FROM callback_manager WHERE user_id = '%s'" % (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("INSERT  INTO callback_manager(user_id) VALUES(?)", (chat_id,))
    con.commit()

    cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (chat_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("""INSERT INTO users(user_id) values(?)""", (chat_id,))

    cur.execute("SELECT * FROM users")

    con.commit()

    cur.execute("""CREATE TABLE IF NOT EXISTS group_manager
                                  (admin_id INTEGER,
                                  group_name,
                                  table_page INTEGER DEFAULT 1,
                                  context_page INTEGER DEFAULT 1,
                                  description_page INTEGER DEFAULT 1)
                                  """)
    con.commit()

    cur.execute(""" CREATE TABLE IF NOT EXISTS tables 
                (table_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, 
                table_name VARCHAR,
                table_description TEXT,
                context TEXT,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    con.commit()

    cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (chat_id,))
    existing_record = cur.fetchone()
    print(cur.fetchall())
    if not existing_record:
        cur.execute("""INSERT INTO tables(user_id) values(?)""", (chat_id,))

    cur.execute("SELECT * FROM tables")

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

    bot.register_next_step_handler(message, on_click)


# to do: better foreign keys

def group_main(message=None):

    chat_id = message.chat.id
    group_name = check_group_design(chat_id)
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("select * from groups")
    print(cur.fetchall())

    if message.text == "Нет":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE groups SET design_flag = False WHERE admin_id == '%s' AND group_name == '%s'" % (
            chat_id, group_name))
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
        bot.register_next_step_handler(message, on_click)


def get_settings(chat_id):
    group_name = check_group_design(chat_id)

    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == '%s'" % (chat_id,))

    group_flag = cur.fetchone()[0]

    if group_flag:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        chat_id = cur.fetchone()[0]

    if group_name is not None or group_flag:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("SELECT current_tables FROM groups WHERE admin_id = '%s' and group_name == '%s'" % (chat_id, group_name))
        table_names = cur.fetchone()
        cur.execute("SELECT group_plot FROM groups WHERE admin_id = '%s' and group_name = '%s'" % (chat_id, group_name))
        build_plots = cur.fetchone()
        con.close()

    else:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("SELECT current_tables FROM users WHERE user_id = '%s'" % (chat_id,))
        table_names = cur.fetchone()
        cur.execute("SELECT build_plots FROM users WHERE user_id = '%s'" % (chat_id,))
        build_plots = cur.fetchone()
        con.close()

    if table_names is not None:
        settings = {"table_name": table_names[0],
                    "build_plots": build_plots[0],
                    }
    else:
        settings = {"table_name": None,
                    "build_plots": build_plots[0],
                    }

    return settings


def get_page(chat_id, page_type):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    page = None
    group_name = check_group_design(chat_id)
    if group_name is not None:
        if page_type == "table_page":
            cur.execute("SELECT table_page FROM group_manager WHERE admin_id == '%s' AND group_name == '%s'" % (chat_id, group_name))
            page = cur.fetchone()[0]
        elif page_type == "context_page":
            cur.execute("SELECT context_page FROM group_manager WHERE admin_id == '%s' AND group_name == '%s'" % (chat_id, group_name))
            page = cur.fetchone()[0]
        elif page_type == "description_page":
            cur.execute("SELECT description_page FROM group_manager WHERE admin_id == '%s' AND group_name == '%s'" % (chat_id, group_name))
            page = cur.fetchone()[0]
        con.commit()
        con.close()
    else:
        if page_type == "table_page":
            cur.execute("SELECT table_page FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
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
    group_name = check_group_design(chat_id)
    if group_name is not None:

        if page_type == "table_page":
            cur.execute("UPDATE group_manager SET table_page = '%s' WHERE admin_id == '%s'" % (new_page, chat_id))

        elif page_type == "context_page":
            cur.execute("UPDATE group_manager SET context_page = '%s' WHERE admin_id == '%s'" % (new_page, chat_id))

        elif page_type == "description_page":
            cur.execute("UPDATE group_manager SET description_page = '%s' WHERE admin_id == '%s'" % (new_page, chat_id))
    else:
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
    group_name = check_group_design(chat_id)
    if group_name is not None:
        cur.execute("SELECT * FROM group_tables WHERE admin_id == '%s' AND  group_name == '%s'" % (chat_id, group_name))
    else:
        cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (chat_id,))
    amount = len(cur.fetchall())//3 + 1

    con.commit()
    con.close()
    return amount


def create_inline_keyboard(chat_id=None, keyboard_type=None, page=1, status_flag=True):
    group_name = check_group_design(chat_id)

    if group_name is not None:
        query = "select table_name from group_tables where admin_id == '%s' and group_name == '%s' LIMIT 3 OFFSET '%s'"
        if page == 1:
            offset = 1
        else:
            offset = ((page - 1) * 3)
    else:
        query = "select table_name from tables where user_id == '%s' LIMIT 3 OFFSET '%s'"
        if page == 1:
            offset = 1
        else:
            offset = ((page-1)*3 +1)
    markup = types.InlineKeyboardMarkup(row_width=3)
    prefix = keyboard_type[0]+"|"
    settings = get_settings(chat_id)
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    if group_name is not None:
        cur.execute(query % (chat_id, group_name, offset))
    else:
        cur.execute(query % (chat_id, offset))

    rows = cur.fetchall()

    con.commit()
    con.close()
    btn = None

    for row in rows:

        if row[0] is not None:
            btn = types.InlineKeyboardButton(text=row[0], callback_data=f"{prefix}{row[0]}")

            markup.add(btn)
    if keyboard_type == "tables":
        btn1 = types.InlineKeyboardButton(text="Добавить новую таблицу", callback_data=f"t|new_table")
        btn2 = types.InlineKeyboardButton(text="Очистить набор таблиц", callback_data=f"t|delete_tables")
        markup.row(btn1)

        if settings["table_name"] is not None and len(settings["table_name"]) > 0:
            if status_flag:
                bot.send_message(chat_id, f"Сейчас доступны для анализа: {settings['table_name']}")
            markup.add(btn2)
        page_type = "table_page"
        page = get_page(chat_id=chat_id, page_type=page_type)
        amount = get_pages_amount(chat_id=chat_id)
        markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))

        right = types.InlineKeyboardButton(text="-->", callback_data=f"t|right")
        left = types.InlineKeyboardButton(text="<--", callback_data=f"t|left")
        markup.row(left, right)
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data=f"t|exit")
        markup.add(btn3)

    elif keyboard_type == "context":

        right = types.InlineKeyboardButton(text="-->", callback_data=f"c|right")
        left = types.InlineKeyboardButton(text="<--", callback_data=f"c|left")
        markup.row(left, right)
        page_type = "context_page"
        page = get_page(chat_id=chat_id, page_type=page_type)
        amount = get_pages_amount(chat_id=chat_id)
        markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data=f"c|exit")
        markup.add(btn3)

    elif keyboard_type == "description":
        right = types.InlineKeyboardButton(text="-->", callback_data=f"d|right")
        left = types.InlineKeyboardButton(text="<--", callback_data=f"d|left")
        markup.row(left, right)
        page_type = "description_page"
        page = get_page(chat_id=chat_id, page_type=page_type)
        amount = get_pages_amount(chat_id=chat_id)
        markup.add(types.InlineKeyboardButton(text=f'{page}/{amount}', callback_data=f' '))
        btn3 = types.InlineKeyboardButton(text="🚫 exit", callback_data=f"d|exit")
        markup.add(btn3)
    return markup


def get_context(chat_id=None):
    settings = get_settings(chat_id)
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
    table_name = list(map(str, settings["table_name"].split(",")))

    group_flag = cur.fetchone()[0]
    context_list = []
    if group_flag:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        chat_id = cur.fetchone()[0]
        for table in table_name:
            cur.execute("SELECT context from group_tables WHERE admin_id == '%s' AND  group_name == '%s'" % (
            chat_id, group_name))
            context = cur.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)


    else:
        for table in table_name:
            cur.execute("SELECT context FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, table))
            context = cur.fetchone()
            if not context or context[0] is None:
                context_line = table + ":"
            else:
                context_line = table + ":" + context[0]
            context_list.append(context_line)
    return context_list


def get_description(chat_id=None):
    settings = get_settings(chat_id)
    table_name = list(map(str, settings["table_name"].split(",")))
    table_description_line = ""
    table_name_path = table_name.copy()
    table_description = []

    for table in range(len(table_name_path)):
        table_name_path[table] = "data/" + table_name_path[table]
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == '%s'" % (chat_id,))

    group_flag = cur.fetchone()[0]
    if group_flag:
        cur.execute("SELECT group_name FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        group_name = cur.fetchone()[0]
        cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
        admin_id = cur.fetchone()[0]

        for table in table_name:

            cur = con.cursor()
            cur.execute("SELECT * FROM group_tables WHERE admin_id = '%s' AND table_name = '%s' AND group_name == '%s'" % (admin_id, table, group_name))
            existing_record = cur.fetchone()

            if existing_record is not None:

                cur.execute("SELECT table_description FROM group_tables WHERE admin_id = '%s' AND table_name = '%s' AND group_name  == '%s'" % (admin_id, table, group_name))
                description = cur.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]
                print(table_description_line)

                table_description.append(table_description_line)

                print("table description:", table_description)
            con.commit()
            con.close()


    else:
        for table in table_name:

            cur = con.cursor()
            cur.execute("SELECT * FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, table))
            existing_record = cur.fetchone()

            if existing_record is not None:

                cur.execute(
                    "SELECT table_description FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, table))
                description = cur.fetchone()

                if not description or description[0] is None:
                    table_description_line = table + ":"
                else:
                    table_description_line = table + ":" + description[0]

                table_description.append(table_description_line)

                print("table description:", table_description)
            con.commit()
    return table_description


def create_group_keyboard(chat_id=None, show_groups=False):
    markup = types.InlineKeyboardMarkup()

    if show_groups:
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select group_name from groups where admin_id == '%s' " % (chat_id,))
        rows = cur.fetchall()
        con.commit()
        con.close()

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


def on_click(message):
    chat_id = message.chat.id
    settings = get_settings(chat_id)
    group_name = check_group_design(chat_id)
    if message.text == "/help":
        help_info(message)

    elif message.text == "❓ Режим отправки запроса":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        bot.send_message(chat_id, "Отправьте запроc. Пожалуйста, вводите запросы последовательно", reply_markup=markup)

        bot.register_next_step_handler(message, call_to_model)

    elif message.text == "🖹 Выбрать таблицу":

        keyboard_type = "tables"
        markup = create_inline_keyboard(chat_id=chat_id, keyboard_type=keyboard_type)

        bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)

        if group_name is not None:
            group_main(message)
        else:
            main(message)

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
        bot.register_next_step_handler(message, plots_handler)

    elif message.text == "➕ Добавить описание таблицы":
        keyboard_type = "description"
        markup = create_inline_keyboard(chat_id=chat_id, keyboard_type=keyboard_type)

        bot.send_message(chat_id, "Выберите, к какой таблице вы хотите добавить описание", reply_markup=markup)

        if group_name is not None:
            group_main(message)
        else:
            main(message)

    elif message.text == "Добавить контекст":
        keyboard_type = "context"
        markup = create_inline_keyboard(chat_id=chat_id, keyboard_type=keyboard_type)
        bot.send_message(chat_id, "Выберите, к какой таблице вы хотите добавить контекст", reply_markup=markup)
        if group_name is not None:
            group_main(message)
        else:
            main(message)

    elif message.text == "Группы таблиц":
        markup = create_group_keyboard(chat_id)
        bot.send_message(chat_id, "Вы можете выбрать одну из опций", reply_markup=markup)
        main(message)

    elif message.text == "exit":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE groups SET design_flag = 0 WHERE admin_id == '%s' " % (message.chat.id,))
        con.commit()
        con.close()
        main(message)
        bot.send_message(message.chat.id, "Редактирование группы завершено")

    elif message.text == "Сохранить настройки группы":
        group_name = check_group_design(message.chat.id)
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("SELECT group_link FROM groups where admin_id = '%s' AND group_name = '%s'" % (message.chat.id, group_name))
        con.commit()

        group_link = cur.fetchone()

        cur.execute("UPDATE groups SET design_flag = 0 WHERE admin_id == '%s' " % (message.chat.id,))
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
        if group_name is not None:
            bd_name = "groups"
            name_id = "admin_id"
        else:
            bd_name = "users"
            name_id = "user_id"
        query = f"UPDATE {bd_name} SET current_tables = '%s' WHERE {name_id}"
        new_cur = ""
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute(query % (new_cur, chat_id))
        con.commit()
        con.close()
        amount = get_pages_amount(chat_id)
        keyboard_type = "tables"
        markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=amount)
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="Вы можете выбрать таблицу или добавить новую",
                              reply_markup=markup2)
    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "tables"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)

    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "tables"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)

    else:
        find_table_flag = True
        choose_flag = True
        choose_table(call, choose_flag)


@bot.callback_query_handler(func=lambda call: call.data.startswith("c|"))
def callback_query(call):
    callback_type, action = map(str, call.data.split("|"))
    call.data = action
    chat_id = call.message.chat.id
    print("here")
    page_type = "context_page"
    page = get_page(chat_id=chat_id, page_type=page_type)
    if call.data == "exit":
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "right":
        amount = get_pages_amount(chat_id)
        if page < amount:
            new_page = page + 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "context"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)

    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "context"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:

        choose_table_context(call)


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
            keyboard_type = "description"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    elif call.data == "left":
        if page > 1:
            new_page = page - 1
            change_page(chat_id=chat_id, page_type=page_type, new_page=new_page)
            keyboard_type = "description"
            markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type, page=new_page, status_flag=False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text="Вы можете выбрать таблицу или добавить новую",
                                  reply_markup=markup2)
    else:
        table_description(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("g|"))
def callback_query(call):
    callback_type, action = map(str, call.data.split("|"))
    call.data = action

    chat_id = call.message.chat.id
    group_name = check_group_design(chat_id)
    if call.data == "exit":
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("UPDATE groups SET design_flag = True WHERE admin_id == '%s' AND group_name == '%s'" % (chat_id, group_name))
        con.commit()
        cur.close()
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


def choose_table_context(call):
    chat_id = call.message.chat.id
    message = call.message

    bot.send_message(chat_id,
                     f"Таблица {call.data} выбрана, для добавления контекста отправьте текст или файл в формате txt или msg",
                     )
    bot.register_next_step_handler(message, add_context, call.data)


def add_context(message, table_name=None):
    chat_id = message.chat.id
    try:
        table_name = table_name
        group_name = check_group_design(chat_id)
        if message.content_type == "text":
            context = str(message.text)

            con = sq.connect("user_data.sql")
            cur = con.cursor()
            if group_name is not None:
                cur.execute("""UPDATE group_tables SET context = '%s' WHERE table_name = '%s' and admin_id = '%s' and group_name == '%s' """ % (context, table_name, chat_id, group_name))
                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Контекст сохранен')
                group_main(message)

            else:
                cur.execute("""UPDATE tables SET context = '%s' WHERE table_name = '%s' and user_id = '%s' """ % (context, table_name, chat_id))
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
                con = sq.connect("user_data.sql")
                cur = con.cursor()
                cur.execute("""UPDATE group_tables SET context = '%s' WHERE table_name = '%s' and admin_id == '%s' and group_name == '%s' """ % (context, table_name, chat_id, group_name))
                con.commit()
                con.close()
                bot.send_message(chat_id, 'Контекст сохранен')
                group_main(message)
            else:
                con = sq.connect("user_data.sql")
                cur = con.cursor()
                cur.execute("""UPDATE tables SET context = '%s' WHERE table_name = '%s' and user_id == '%s' """ % (context, table_name, chat_id))
                con.commit()
                con.close()
                bot.send_message(chat_id, 'Контекст сохранен')
                main(message)

    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "Что-то пошло не так, попробуйте другой файл")
        error_message_flag = True
        choose_table(message, error_message_flag)


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

        settings = get_settings(chat_id)
        if settings["table_name"] is not None:
            if text not in settings["table_name"]:
                settings["table_name"] += "," + text
                bot.send_message(chat_id, "Таблица добавлена")
            else:
                bot.send_message(chat_id, "Данная таблица уже добавлена в список")
        else:

            settings["table_name"] = text
            bot.send_message(chat_id, "Таблица выбрана.")
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute(
            "UPDATE users SET current_tables = '%s' WHERE user_id == '%s'" % (settings["table_name"], chat_id))
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
            if group_name is not None:
                cur.execute("SELECT * FROM group_tables WHERE admin_id = '%s' AND table_name = '%s'" % (chat_id, message.document.file_name))
                existing_record = cur.fetchone()

                if existing_record is None:
                    cur.execute("""INSERT INTO group_tables(admin_id, group_name, table_name) VALUES(?,?,?)""",
                                (chat_id, group_name, message.document.file_name))
                    con.commit()
                    cur.execute("select * from group_tables")
                    print("group_tables", cur.fetchall())
                    cur.execute("UPDATE groups SET current_tables = '%s' WHERE admin_id == '%s' AND group_name = '%s'" % (message.document.file_name, chat_id, group_name))
                    con.commit()

                    con.close()
                    bot.reply_to(message, 'Файл сохранен')
                    keyboard_type = "tables"
                    markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                          text="Вы можете выбрать таблицу или добавить новую",
                                          reply_markup=markup2)

                    group_main(message)
                else:
                    bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")
                    bot.register_next_step_handler(message, add_table)

            else:

                cur.execute("SELECT * FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (chat_id, message.document.file_name))
                existing_record = cur.fetchone()

                if existing_record is None:
                    cur.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""", (chat_id, message.document.file_name))
                    con.commit()
                    cur.execute("UPDATE users SET current_tables = '%s' WHERE user_id == '%s'" % (message.document.file_name, chat_id))
                    con.commit()

                    con.close()
                    bot.reply_to(message, 'Файл сохранен')
                    keyboard_type = "tables"
                    markup2 = create_inline_keyboard(chat_id=call.message.chat.id, keyboard_type=keyboard_type)
                    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      text="Вы можете выбрать таблицу или добавить новую",
                                      reply_markup=markup2)
                    main(message=message)
                else:
                    bot.send_message(chat_id, "Данная таблица уже была добавлена, попробуйте другую")
                    bot.register_next_step_handler(message, add_table)

        except telebot.apihelper.ApiTelegramException:
            bot.register_next_step_handler(message, add_table)

        except Exception as e:
            print(e)
            bot.send_message(chat_id, "Что-то пошло не так, попробуйте другой файл")

            bot.register_next_step_handler(message, add_table)


def plots_handler(message, settings=None):
    chat_id = message.chat.id
    settings = get_settings(chat_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Вернуться в главное меню")
    markup.add(btn1)
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    group_name = check_group_design(chat_id)
    if message.text == "Выключить":

        if group_name is not None:
            cur.execute("UPDATE groups SET group_plot = 0 WHERE admin_id == '%s'" % (chat_id,))
            bot.register_next_step_handler(message, group_main)
        else:
            cur.execute("UPDATE users SET build_plots = '%s'" % (settings["build_plots"]))
            bot.register_next_step_handler(message, main)
        con.commit()
        bot.send_message(message.chat.id, "Режим визуализации отключён", reply_markup=markup)

    elif message.text == "Включить":

        if group_name is not None:
            cur.execute("UPDATE groups SET group_plot = 1 WHERE admin_id == '%s'" % (chat_id,))
            bot.register_next_step_handler(message, group_main)
        else:
            cur.execute("UPDATE users SET build_plots = '%s'" % (settings["build_plots"]))
            bot.register_next_step_handler(message, main)
        con.commit()
        bot.send_message(message.chat.id, "Режим визуализации включён", reply_markup=markup)


def table_description(call):
    table_name = call.data
    message = call.message
    bot.send_message(message.chat.id, """Таблица выбрана. Чтобы добавить описание таблицы, отправьте файл с описанием столбцов в формате txt или качестве сообщения.""")

    bot.register_next_step_handler(message, choose_description, table_name)


def choose_description(message, table_name=None):
    table_name = table_name
    print(table_name)
    chat_id = message.from_user.id
    group_name = check_group_design(chat_id)
    if message.content_type == "text":
        description = str(message.text)
        if group_name is not None:
            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("select table_name from group_tables where admin_id == '%s' and group_name == '%s'" % (chat_id, group_name))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute(
                    """UPDATE group_tables SET table_description = '%s' WHERE table_name = '%s' and admin_id = '%s' and group_name == '%s'""" % (
                    description, table_name, chat_id, group_name))

            con.commit()
            con.close()
            bot.send_message(message.from_user.id, 'Описание сохранено')
            group_main(message)
        else:
            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' and user_id = '%s' """ % (description, table_name, chat_id))

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

            con = sq.connect("user_data.sql")
            cur = con.cursor()

            if group_name is not None:
                cur.execute("select table_name from group_tables where admin_id == '%s' and group_name == '%s'" % (chat_id, group_name))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute("""UPDATE group_tables SET table_description = '%s' WHERE table_name = '%s' and admin_id == '%s' and group_name == '%s' """ % (description, table_name, chat_id, group_name))
                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Описание сохранено')
                group_main(message)

            else:
                cur.execute("select table_name from tables where user_id == '%s'" % (chat_id,))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' """ % (description, table_name))
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
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("SELECT * FROM groups WHERE admin_id == '%s' AND group_name == '%s'" % (admin_id, group_name))
    existing_record = cur.fetchone()
    if existing_record is None:
        cur.execute("INSERT INTO groups(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        con.commit()
        group_link = "https://t.me/auto_analyzer_bot?start=" + group_name_for_link
        cur.execute("UPDATE groups SET group_link = '%s' WHERE admin_id = '%s' and group_name == '%s' " % (group_link, admin_id, group_name))
        con.commit()
        cur.execute("INSERT INTO group_manager(admin_id, group_name) VALUES(?,?)", (admin_id, group_name))
        con.commit()
        con.close()
        bot.send_message(admin_id, "Группа создана")
    else:
        bot.send_message(admin_id, "Данная группа уже создавалась")
    main(message)


def choose_group(group_name=None, admin_id=None, message=None):
    con = sq.connect("user_data.sql")
    cur = con.cursor()
    cur.execute("UPDATE groups SET design_flag = True WHERE admin_id == '%s' AND group_name == '%s'" % (admin_id, group_name))
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
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("SELECT req_count FROM callback_manager WHERE user_id == '%s'" % (message.chat.id,))
        req_count = cur.fetchone()[0]
        if reset:
            req_count = 0
            cur.execute("UPDATE callback_manager SET req_count = 0")
            con.commit()

        if req_count > max_requests:
            bot.send_message(message.chat.id, "К сожалению, лимит запросов исчерпан, попробуйте позднее")
            bot.register_next_step_handler(message, main)
        req_count += 1
        print(req_count, max_requests)
        cur.execute("UPDATE callback_manager SET req_count = '%s' WHERE user_id == '%s'" % (req_count, message.chat.id))
        con.commit()


    if message.text == "🚫 exit":
        main(message)
    else:
        chat_id = message.chat.id

        def callback(sum_on_step):
            message_id = send_message.message_id

            edited_message = bot.edit_message_text(chat_id=chat_id, message_id=message_id,
                                                   text=send_message.text + f"\n{sum_on_step}")
        settings = get_settings(chat_id)
        user_question = message.text
        try:
            if settings["table_name"] is None:
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
                context_line = ""
                table_description_line = ""
                table_name_path = table_name.copy()

                for table in range(len(table_name_path)):
                    table_name_path[table] = "data/" + table_name_path[table]
                con = sq.connect("user_data.sql")
                cur = con.cursor()
                table_description = get_description(chat_id)
                context_list = get_context(chat_id)
                cur.execute("SELECT group_flag FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
                table_name = list(map(str, settings["table_name"].split(",")))

                group_flag = cur.fetchone()[0]
                con.commit()
                if group_flag:
                    cur.execute("SELECT group_name FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
                    group_name = cur.fetchone()[0]
                    cur.execute("SELECT admin_id FROM callback_manager WHERE user_id == '%s'" % (chat_id,))
                    admin_id = cur.fetchone()[0]
                    cur.execute("SELECT group_conv FROM groups WHERE admin_id == '%s' AND group_name == '%s'" % (admin_id, group_name))
                    current_summary = cur.fetchone()
                else:

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
                                                            table_description, context_list, callback=callback)
                summary = answer_from_model[1]
                new_summary = current_summary + summary

                if group_flag:
                    cur.execute("UPDATE groups SET group_conv = '%s' WHERE admin_id == '%s' AND group_name == '%s'" % (new_summary, admin_id, group_name))

                else:
                    cur.execute("UPDATE users SET conv_sum = '%s' WHERE user_id == '%s'" % (new_summary, chat_id))

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
                bot.register_next_step_handler(message, call_to_model)
        except requests.exceptions.ConnectionError:
            bot.send_message(message.from_user.id, "Что-то пошло не так")
            main(user_question)


try:
    bot.polling()
except Exception as e:
    print("error is:", e)
    time.sleep(2)
    bot.polling()