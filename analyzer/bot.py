import os
import telebot
import sqlite3 as sq
import interactor


import re
import yaml

from telebot import types

user_question = None

plot_files = ""

# to do: solve problem with matplotlib GUI outside main thread


class Outside_main_thread(Exception):
    def __init__(self, message, plot_files):
        Exception.__init__(self)
        self.message = message
        self.plot_files = plot_files


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
                    user_id TEXT UNIQUE,
                    conv_sum VARCHAR)
                   """)

        con.commit()
    with sq.connect("user_data.sql") as con:
        cur = con.cursor()
        cur.execute(""" CREATE TABLE IF NOT EXISTS table_data (user_id INTEGER, 
                        table_name VARCHAR UNIQUE,
                        FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")

        con.commit()

    if settings is None:
        settings = {"table_name": None,
                    "build_plots": False,
                    "user_id": None}

    markup = types.ReplyKeyboardMarkup()
    btn1 = types.KeyboardButton("Выбрать таблицу")
    btn2 = types.KeyboardButton("Добавить описание таблицы")
    btn3 = types.KeyboardButton("Режим визуализации")
    btn4 = types.KeyboardButton("Режим отправки запроса")
    markup.row(btn1, btn2, btn3, btn4)

    bot.send_message(message.chat.id, "Вы можете  выбрать одну из опций", reply_markup=markup)

    bot.register_next_step_handler(message, on_click, settings)

# to do: find a way to split this function into small parts


def on_click(message, settings=None):
    user_id = message.from_user.id
    if message.text == "Режим отправки запроса":
        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("exit")
        markup.add(btn1)
        bot.send_message(message.chat.id, "Отправьте запроc. Пожалуйста, вводите запросы последовательно", reply_markup=markup)
        bot.register_next_step_handler(message, call_to_model, settings)
    elif message.text == "Выбрать таблицу":
        markup = types.ReplyKeyboardMarkup()
        with sq.connect("user_data.sql") as con:
            cur = con.cursor()
            cur.execute("select table_name from table_data where user_id == '%s'" % (user_id))
            rows = cur.fetchall()
            con.commit()
        btn = None
        for row in rows:
            btn = types.KeyboardButton(row[0])
            markup.add(btn)

        btn1 = types.KeyboardButton("Добавить новую таблицу")
        markup.row(btn1)
        bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)
        bot.register_next_step_handler(message, choose_table, settings)

    elif message.text == "Режим визуализации":
        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("Выключить")
        btn2 = types.KeyboardButton("Включить")
        markup.row(btn1, btn2)
        bot.send_message(message.from_user.id, "Можете выбрать режим визуализации данных, он выключен по умолчанию",
                         reply_markup=markup)
        bot.register_next_step_handler(message, plots_handler, settings)

    elif message.text == "Добавить описание таблицы":
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

        markup = types.ReplyKeyboardMarkup()
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

                cur.execute("""INSERT INTO table_data(user_id, table_name) values(?,?)""", (
                    user_id, message.document.file_name))

                cur.execute("select * from table_data")

                con.commit()
            bot.reply_to(message, 'Файл сохранен')
            bot.register_next_step_handler(message, main, settings)
        except Exception:
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            choose_table(message, settings, error_message_flag)
# function that contains all params that was set by user and will be used during interaction with model


def plots_handler(message, settings=None):

    markup = types.ReplyKeyboardMarkup()
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
    pass

# to do: rewrite this with less if/else statements


def call_to_model(message, settings=None):
    if message.text == "exit":
        main(message, settings)
    else:
        plot_files = None
        print(settings)
        table = None
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
            table = "data/" + settings["table_name"]
            build_plots = settings["build_plots"]

            markup = types.ReplyKeyboardMarkup()
            btn1 = types.KeyboardButton("exit")

            markup.add(btn1)

            bot.send_message(message.from_user.id, "Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью 'exit'", reply_markup=markup)

            user_question = message.text
            user_id = message.from_user.id
            answer_from_model = interactor.run_loop_bot(table, build_plots, user_question, user_id)
            summary = answer_from_model[1]

            with sq.connect("user_data.sql") as con:
                cur = con.cursor()
                cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (user_id))
                existing_record = cur.fetchone()

                if existing_record:
                    cur.execute("UPDATE users SET conv_sum = '%s' WHERE user_id = '%s'" % (summary, user_id))
                else:
                    cur.execute("INSERT INTO users VALUES('%s', '%s')" % (user_id, summary))

                cur.execute("select * from users")
                print(cur.fetchall())
                con.commit()

            bot.send_message(message.from_user.id, f"Answer: {answer_from_model[0]}")

            pattern = r"\b\w+\.png\b"
            if ".png" in answer_from_model:
                plot_files = re.findall(pattern, answer_from_model)
                for plot_file in plot_files:
                    path_to_file = "Plots/" + plot_file
                    print(path_to_file)

                bot.send_photo(message.from_user.id, open(path_to_file, "rb"))
                os.remove(path_to_file)
            bot.register_next_step_handler(message, call_to_model, settings)


bot.polling()
