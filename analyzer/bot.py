import os
import telebot
import sqlite3 as sq
import interactor
import asyncio

import re
import yaml
import matplotlib
matplotlib.use('Agg')
from telebot import types

user_question = None

plot_files = ""

# to do: solve problem with matplotlib GUI outside main thread

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
    bot.send_message(message.from_user.id, "Я - автономный помощник для проведения различной аналитики")


@bot.message_handler(commands=["start", "exit"], content_types=["text", "document"])
def main(message, settings=None):
    user_id = message.from_user.id

    with sq.connect("user_data.sql") as con:
        cur = con.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER UNIQUE,
                    conv_sum TEXT)
                   """)
        con.commit()
    with sq.connect("user_data.sql") as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (user_id,))
        existing_record = cur.fetchone()

        if existing_record is None:
            cur.execute("""INSERT INTO users(user_id) values(?)""", (user_id,))

        cur.execute("SELECT * FROM users")
        print(cur.fetchall())

        con.commit()

    with sq.connect("user_data.sql") as con:
        cur = con.cursor()
        cur.execute(""" CREATE TABLE IF NOT EXISTS tables (user_id INTEGER, 
                        table_name VARCHAR,
                        table_description VARCHAR,
                        FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
        con.commit()
    with sq.connect("user_data.sql") as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (user_id,))
        existing_record = cur.fetchone()

        if existing_record is None:
            cur.execute("""INSERT INTO tables(user_id) values(?)""", (user_id,))

        cur.execute("SELECT * FROM tables")
        print(cur.fetchall())

        con.commit()
    if settings is None:
        settings = {"table_name": None,
                    "build_plots": True,
                    "user_id": None}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Выбрать таблицу")
    btn2 = types.KeyboardButton("Добавить описание таблицы")
    btn3 = types.KeyboardButton("Режим визуализации")
    btn4 = types.KeyboardButton("Режим отправки запроса")
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)

    bot.send_message(message.chat.id, "Вы можете  выбрать одну из опций", reply_markup=markup)

    bot.register_next_step_handler(message, on_click, settings)

# to do: find a way to split this function into small parts


def on_click(message, settings=None):
    user_id = message.from_user.id

    if message.text == "Режим отправки запроса":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id, "Отправьте запроc. Пожалуйста, вводите запросы последовательно", reply_markup=markup)

        bot.register_next_step_handler(message, call_to_model, settings)
    elif message.text == "Выбрать таблицу":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        with sq.connect("user_data.sql") as con:
            cur = con.cursor()
            cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))
            rows = cur.fetchall()
            con.commit()
        btn = None
        print(rows)

        for row in rows:

            if row[0] is not None:

                btn = types.KeyboardButton(row[0])

                markup.add(btn)

        btn1 = types.KeyboardButton("Добавить новую таблицу")
        markup.row(btn1)
        bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)
        bot.register_next_step_handler(message, choose_table, settings)

    elif message.text == "Режим визуализации":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Выключить")
        btn2 = types.KeyboardButton("Включить")
        markup.row(btn1, btn2)
        bot.send_message(message.from_user.id, "Можете выбрать режим визуализации данных, он включен по умолчанию",
                         reply_markup=markup)
        bot.register_next_step_handler(message, plots_handler, settings)

    elif message.text == "Добавить описание таблицы":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        with sq.connect("user_data.sql") as con:
            cur = con.cursor()
            cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))
            rows = cur.fetchall()
            con.commit()
            existing_record = cur.fetchall()

        btn = None

        for row in rows:

            if row[0] is not None:
                btn = types.KeyboardButton(row[0])

                markup.add(btn)

        btn1 = types.KeyboardButton("exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id, "Выберите, к какой таблице вы хотите добавить описание",
                         reply_markup=markup)
        bot.register_next_step_handler(message, table_description, settings)


def choose_table(message, settings=None, error_table_flag=False):
    if message.text == "Добавить новую таблицу" or error_table_flag:
        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("exit")
        markup.row(btn1)
        bot.send_message(message.from_user.id, "Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json", reply_markup=markup)
        bot.register_next_step_handler(message, add_table, settings)

    else:
        settings["table_name"] = message.text

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("exit")
        markup.row(btn1)

        bot.send_message(message.from_user.id, "Таблица выбрана. Теперь вы можете задавать вопросы. Нажмите 'exit', чтобы выйти из этого режима", reply_markup=markup)

        bot.register_next_step_handler(message, main, settings)


def add_table(message, settings=None, error_message_flag=False):
    if message.text == "exit":
        main(message, settings)

    else:
        try:
            user_id = message.from_user.id
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path

            downloaded_file = bot.download_file(file_path)
            src = "data/" + message.document.file_name

            with open(src, 'wb') as f:
                f.write(downloaded_file)

            with sq.connect("user_data.sql") as con:
                cur = con.cursor()
                cur.execute("""SELECT * FROM tables WHERE table_name = (?) and user_id = (?)""", (message.document.file_name,user_id))
                existing_record = cur.fetchall()
                print("this:", existing_record)
                if not existing_record:
                    cur.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""", (user_id, message.document.file_name))

                con.commit()
            bot.reply_to(message, 'Файл сохранен')
            settings["table_name"] = message.document.file_name
            bot.register_next_step_handler(message, main, settings)
        except Exception:
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            choose_table(message, settings, error_message_flag)
# function that contains all params that was set by user and will be used during interaction with model


def plots_handler(message, settings=None):

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Вернуться в главное меню")
    markup.add(btn1)

    if message.text == "Выключить":
        settings["build_plots"] = False
        bot.send_message(message.from_user.id, "Режим визуализации отключён", reply_markup=markup)
        bot.register_next_step_handler(message, main, settings)
    elif message.text == "Включить":
        settings["build_plots"] = True
        bot.send_message(message.from_user.id, "Режим визуализации включён", reply_markup=markup)
        bot.register_next_step_handler(message, main, settings)


def table_description(message, settings=None):
    table_name = message.text
    if message.text == "exit":
        main(message, settings)
    else:

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id,
                         "Таблица выбрана. Чтобы добавить описание таблицы, отправьте файл с описанием столбцов в формате txt или качестве сообщения.",
                         reply_markup=markup)
        bot.register_next_step_handler(message, choose_description, settings, table_name)


def choose_description(message, settings=None, table_name=None):
    table_name = table_name
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("exit")
    markup.add(btn1)
    if message.content_type == "text":

        description = str(message.text)
        print(description)
        with sq.connect("user_data.sql") as con:
            cur = con.cursor()
            cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))


            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' """ % (description, table_name))

            con.commit()
        bot.send_message(message.from_user.id, 'Описание сохранено', reply_markup=markup)
        bot.register_next_step_handler(message, main, settings)
    elif message.content_type == "document":

            user_id = message.from_user.id
            file_id = message.document.file_id
            file_info = bot.get_file(file_id)
            file_path = file_info.file_path

            downloaded_file = bot.download_file(file_path)
            src = "data/" + message.document.file_name

            description = downloaded_file.decode('utf-8')

            with sq.connect("user_data.sql") as con:
                cur = con.cursor()

                cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' """ % (description, table_name))
                con.commit()
            bot.send_message(message.from_user.id, 'Описание сохранено', reply_markup=markup)
            bot.register_next_step_handler(message, main, settings)

            # bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            # error_message_flag = True
            # bot.register_next_step_handler(message, table_description, settings)


# to do: there should be some ways to optimize interaction with database

def call_to_model(message, settings=None):
    if message.text == "exit":
        main(message, settings)
    else:
        if settings["table_name"] is None:
            bot.send_message(message.from_user.id, "Таблица не найдена, вы можете выбрать другую")
            bot.register_next_step_handler(message, main, settings)
            markup = types.ReplyKeyboardMarkup()
            btn1 = types.KeyboardButton("exit")
            markup.add(btn1)
            bot.send_message(message.from_user.id,
                             "Вы можете выйти из режима работы с моделью с помощью 'exit'",
                             reply_markup=markup)
        else:
            user_id = message.from_user.id
            with sq.connect("user_data.sql") as con:
                cur = con.cursor()
                cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (user_id,))
                existing_record = cur.fetchone()

                if existing_record:
                    cur.execute("SELECT conv_sum FROM users WHERE user_id = '%s'" % (user_id,))
                    current_summary = cur.fetchone()[0]
                    if current_summary is None:
                        current_summary = ""

                con.commit()
            with sq.connect("user_data.sql") as con:
                cur = con.cursor()
                cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (user_id,))
                existing_record = cur.fetchone()

                if existing_record:
                    cur.execute("SELECT table_description FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (user_id, settings["table_name"]))
                    table_description = cur.fetchone()[0]
                    if table_description is None:
                        table_description = ""
                con.commit()

            plot_files = None
            print(settings)
            table = None

            table = "data/" + settings["table_name"]
            build_plots = settings["build_plots"]

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn1 = types.KeyboardButton("exit")

            markup.add(btn1)

            bot.send_message(message.from_user.id, "Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью 'exit'", reply_markup=markup)

            user_question = message.text

            answer_from_model = interactor.run_loop_bot(table, build_plots, user_question, current_summary, table_description)
            summary = answer_from_model[1]

            with sq.connect("user_data.sql") as con:
                cur = con.cursor()
                cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (user_id,))
                existing_record = cur.fetchone()

                if existing_record:
                    cur.execute("SELECT conv_sum FROM users WHERE user_id = '%s'" % (user_id,))
                    current_summary = cur.fetchone()[0]
                    if current_summary is None:
                        current_summary = ""


                    new_summary = current_summary + summary

                    #cur.execute("UPDATE users SET conv_sum = '%s' WHERE user_id = '%s'" % (new_summary, user_id))
                else:
                    cur.execute("INSERT INTO users VALUES('%s', '%s')" % (user_id, summary))

                cur.execute("select * from users")

                con.commit()



            pattern = r"\b\w+\.png\b"
            if ".png" in answer_from_model[1]:

                plot_files = re.findall(pattern, answer_from_model[1])
                for plot_file in plot_files:
                    path_to_file = "Plots/" + plot_file
                    print(path_to_file)

                    bot.send_photo(message.from_user.id, open(path_to_file, "rb"))
                    os.remove(path_to_file)
            else:
                bot.send_message(message.from_user.id, f"Answer: {answer_from_model[0]}")
            bot.register_next_step_handler(message, call_to_model, settings)


bot.polling()
