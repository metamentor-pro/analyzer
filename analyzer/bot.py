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
    bot.send_message(message.from_user.id, "Я - автономный помощник для проведения различной аналитики")


@bot.message_handler(commands=["start", "exit"], content_types=["text", "document"])
def main(message, settings=None):
    user_id = message.from_user.id

    con = sq.connect("user_data.sql")
    cur = con.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users 
                (user_id INTEGER UNIQUE,
                conv_sum TEXT)""")
    con.commit()

    cur.execute("SELECT * FROM users WHERE user_id = '%s'" % (user_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("""INSERT INTO users(user_id) values(?)""", (user_id,))

    cur.execute("SELECT * FROM users")

    print(cur.fetchall())

    con.commit()

    cur.execute(""" CREATE TABLE IF NOT EXISTS tables (user_id INTEGER, 
                table_name VARCHAR,
                table_description VARCHAR,
                context VARCHAR,
                FOREIGN KEY(user_id) REFERENCES users (user_id) on DELETE CASCADE)""")
    con.commit()

    cur.execute("SELECT * FROM tables WHERE user_id = '%s'" % (user_id,))
    existing_record = cur.fetchone()

    if not existing_record:
        cur.execute("""INSERT INTO tables(user_id) values(?)""", (user_id,))

    cur.execute("SELECT * FROM tables")
    print(cur.fetchall())

    con.commit()
    con.close()
    if settings is None:
        settings = {"table_name": [],
                    "build_plots": True,
                    }

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🖹 Выбрать таблицу")
    btn2 = types.KeyboardButton("➕ Добавить описание таблицы")
    btn3 = types.KeyboardButton("🖻 Режим визуализации")
    btn4 = types.KeyboardButton("❓ Режим отправки запроса")
    btn5 = types.KeyboardButton("Добавить контекст")
    markup.row(btn1, btn2)
    markup.row(btn3, btn4, btn5)

    bot.send_message(message.chat.id, "Вы можете  выбрать одну из опций", reply_markup=markup)

    bot.register_next_step_handler(message, on_click, settings)

# to do: find a way to split this function into small parts


def on_click(message, settings=None):
    user_id = message.from_user.id

    if message.text == "❓ Режим отправки запроса":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id, "Отправьте запроc. Пожалуйста, вводите запросы последовательно", reply_markup=markup)

        bot.register_next_step_handler(message, call_to_model, settings)
    elif message.text == "🖹 Выбрать таблицу":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))
        rows = cur.fetchall()
        con.commit()
        con.close()
        btn = None

        for row in rows:

            if row[0] is not None:

                btn = types.KeyboardButton(row[0])

                markup.add(btn)

        btn1 = types.KeyboardButton("Добавить новую таблицу")
        btn2 = types.KeyboardButton("Очистить набор таблиц")
        markup.row(btn1)

        if len(settings["table_name"]) > 0:
            bot.send_message(message.from_user.id, f"Сейчас доступны для анализа: {settings['table_name']}")
            markup.row(btn2)
        btn3 = types.KeyboardButton("🚫 exit")
        markup.row(btn3)
        bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)
        bot.register_next_step_handler(message, choose_table, settings)

    elif message.text == "🖻 Режим визуализации":
        if settings["build_plots"] == False:
            build_plots = "выключен"
        else:
            build_plots = "включен"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Выключить")
        btn2 = types.KeyboardButton("Включить")
        markup.row(btn1, btn2)
        bot.send_message(message.from_user.id, f"Можете выбрать режим визуализации данных, он  {build_plots}  в данный момент",
                         reply_markup=markup)
        bot.register_next_step_handler(message, plots_handler, settings)

    elif message.text == "➕ Добавить описание таблицы":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        con = sq.connect("user_data.sql")
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
        con.close()

        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id, "Выберите, к какой таблице вы хотите добавить описание",
                         reply_markup=markup)
        bot.register_next_step_handler(message, table_description, settings)
    elif message.text == "Добавить контекст":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        con = sq.connect("user_data.sql")
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
        con.close()

        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id, "Выберите, к какой таблице вы хотите добавить контекст",
                         reply_markup=markup)
        bot.register_next_step_handler(message, choose_table_context, settings)
        

def choose_table_context(message, settings=None):
    if message.text == "🚫 exit":
        main(message, settings)
    else:
        table_name = message.text
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🚫 exit")

        markup.row(btn1)
        bot.send_message(message.from_user.id, f"Таблица {table_name} выбрана, для добавления контекста отправьте текст или файл в формате txt или msg", reply_markup=markup)
        bot.register_next_step_handler(message, add_context, settings, table_name)


def add_context(message, settings=None, table_name=None):
    if message.text == "🚫 exit":
        main(message, settings)

    else:
        try:
            table_name = table_name
            user_id = message.from_user.id
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            btn1 = types.KeyboardButton("🚫 exit")
            markup.add(btn1)
            if message.content_type == "text":
                context = str(message.text)

                con = sq.connect("user_data.sql")
                cur = con.cursor()
                cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute(
                        """UPDATE tables SET context = '%s' WHERE table_name = '%s' and user_id = '%s' """ % (
                        context, table_name, user_id))

                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Описание сохранено', reply_markup=markup)
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

                cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))

                existing_record = cur.fetchall()
                if existing_record:
                    cur.execute("""UPDATE tables SET context = '%s' WHERE table_name = '%s' """ % (
                    context, table_name))
                con.commit()
                con.close()
                bot.send_message(message.from_user.id, 'Контекст сохранен', reply_markup=markup)
                bot.register_next_step_handler(message, main, settings)

        except Exception:
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            choose_table(message, settings, error_message_flag)


def choose_table(message, settings=None, error_table_flag=False):
    if message.text == "🚫 exit":
        main(message, settings)
    elif message.text == "Очистить набор таблиц":
        settings["table_name"] = []
        main(message, settings)
    elif message.text == "Добавить новую таблицу" or error_table_flag:
        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("🚫 exit")
        markup.row(btn1)
        bot.send_message(message.from_user.id, "Чтобы добавить таблицу, отправьте файл в формате csv, XLSX или json", reply_markup=markup)
        bot.register_next_step_handler(message, add_table, settings)

    else:
        if message.text in settings["table_name"]:
            bot.send_message(message.from_user.id, "Данная таблица уже есть в наборе")
            main(message, settings)
        else:
            settings["table_name"].append(message.text)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        btn1 = types.KeyboardButton("🚫 exit")
        markup.row(btn1)

        bot.send_message(message.from_user.id, "Таблица выбрана. Теперь вы можете задавать вопросы. Нажмите 'exit', чтобы выйти из этого режима", reply_markup=markup)

        bot.register_next_step_handler(message, call_to_model, settings)


def add_table(message, settings=None, error_message_flag=False):
    if message.text == "🚫 exit":
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

            con = sq.connect("user_data.sql")
            cur = con.cursor()
            cur.execute("""SELECT * FROM tables WHERE table_name = (?) and user_id = (?)""", (message.document.file_name,user_id))
            existing_record = cur.fetchall()
            print("this:", existing_record)
            if not existing_record:
                cur.execute("""INSERT INTO tables(user_id, table_name) VALUES(?,?)""", (user_id, message.document.file_name))

            con.commit()
            con.close()
            bot.reply_to(message, 'Файл сохранен')
            settings["table_name"].append(message.document.file_name)
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
    if message.text == "🚫 exit":
        main(message, settings)
    else:

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("🚫 exit")
        markup.add(btn1)
        bot.send_message(message.from_user.id,
                         "Таблица выбрана. Чтобы добавить описание таблицы, отправьте файл с описанием столбцов в формате txt или качестве сообщения.",
                         reply_markup=markup)
        bot.register_next_step_handler(message, choose_description, settings, table_name)


def choose_description(message, settings=None, table_name=None):
    table_name = table_name
    user_id = message.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🚫 exit")
    markup.add(btn1)
    if message.content_type == "text":
        description = str(message.text)
        print(description)
        con = sq.connect("user_data.sql")
        cur = con.cursor()
        cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))

        existing_record = cur.fetchall()
        if existing_record:
            cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' and user_id = '%s' """ % (description, table_name, user_id))

        con.commit()
        con.close()
        bot.send_message(message.from_user.id, 'Описание сохранено', reply_markup=markup)
        bot.register_next_step_handler(message, main, settings)
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

            cur.execute("select table_name from tables where user_id == '%s'" % (user_id,))

            existing_record = cur.fetchall()
            if existing_record:
                cur.execute("""UPDATE tables SET table_description = '%s' WHERE table_name = '%s' """ % (description, table_name))
            con.commit()
            con.close()
            bot.send_message(message.from_user.id, 'Описание сохранено', reply_markup=markup)
            bot.register_next_step_handler(message, main, settings)

        except:
            bot.send_message(message.from_user.id, "Что-то пошло не так, попробуйте другой файл")
            error_message_flag = True
            bot.register_next_step_handler(message, table_description, settings)


# to do: there should be some ways to optimize interaction with database

def call_to_model(message, settings=None):

    def callback(sum_on_step):
        message_id = send_message.message_id

        edited_message = bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=send_message.text + f"\n{sum_on_step}")

    chat_id = message.chat.id
    user_question = message.text
    table_name = settings["table_name"]
    context_line = ""
    table_description_line = ""

    if message.text == "🚫 exit":
        main(message, settings)
    else:
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
                    user_id = message.from_user.id


                    cur = con.cursor()
                    cur.execute("SELECT * FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (user_id, table))
                    existing_record = cur.fetchone()

                    if existing_record:

                        cur.execute("SELECT table_description FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (user_id, table))
                        table_description = cur.fetchone()

                        if not table_description or table_description[0] is None:
                            table_description_line = table + " "
                        else:
                            table_description_line = table + table_description[0]

                    con.commit()

                    cur.execute("SELECT context FROM tables WHERE user_id = '%s' AND table_name = '%s'" % (user_id, table))
                    context = cur.fetchone()

                    if not context or context[0] is None:
                        context_line += table + " "
                    else:
                        context_line += table + context[0]
                print(context_line)
                print(table_description_line)
                cur = con.cursor()

                cur.execute("SELECT conv_sum FROM users WHERE user_id = '%s'" % (user_id,))
                current_summary = cur.fetchone()

                if not current_summary or current_summary[0] is None:
                    current_summary = ""
                else:
                    current_summary = current_summary[0]



                print(settings)
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

                cur.execute("INSERT OR REPLACE INTO users VALUES(?, ?)", (user_id, new_summary))

                cur.execute("select * from users")
                #print(cur.fetchall())
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