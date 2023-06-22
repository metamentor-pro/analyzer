import os
import telebot
import pymongo
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


@bot.message_handler(commands=["start", "exit"])
def main(message, settings=None):
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
    if message.text == "Режим отправки запроса":
        bot.send_message(message.chat.id, "Пожалуйста, отправьте запрос")
        bot.register_next_step_handler(message, call_to_model, settings)
    elif message.text == "Выбрать таблицу":
        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("Бованенково.XLSX")
        markup.row(btn1)
        bot.send_message(message.from_user.id, "Можете выбрать нужную таблицу или добавить новую", reply_markup=markup)
        bot.register_next_step_handler(message, choose_table, settings)

    elif message.text == "Режим визуализации":
        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("Выключить")
        btn2 = types.KeyboardButton("Включить")
        markup.row(btn1, btn2)
        bot.send_message(message.from_user.id, "Можете выбрать режим визуализации данных, выключен по умолчанию",
                         reply_markup=markup)
        bot.register_next_step_handler(message, settings_handler, settings)

    elif message.text == "Добавить описание таблицы":
        bot.register_next_step_handler(message, table_description, settings)


def choose_table(message, settings=None):
    settings["table_name"] = message.text

    markup = types.ReplyKeyboardMarkup()
    btn1 = types.KeyboardButton("exit")
    markup.row(btn1)

    bot.send_message(message.from_user.id, "Таблица выбрана. Теперь вы можете задавать вопросы. Нажмите 'exit', чтобы выйти из этого режима", reply_markup=markup)

    bot.register_next_step_handler(message, main, settings)
# function that contains all params that was set by user and will be used during interaction with model


def settings_handler(message, settings=None):

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


@bot.message_handler()
def call_to_model(message, settings=None):
    plot_files = None
    print(settings)
    if settings is not None:
        table = None
        if settings["table_name"] is not None:
            table = "data/" + settings["table_name"]

        else:
            bot.send_message(message.from_user.id, "Таблица не найдена, вы можете выбрать другую")
            bot.register_next_step_handler(message, main, settings)

        build_plots = settings["build_plots"]

        markup = types.ReplyKeyboardMarkup()
        btn1 = types.KeyboardButton("/exit")

        markup.add(btn1)

        bot.send_message(message.from_user.id, "Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью 'exit'", reply_markup=markup)

        user_question = message.text
        user_id = message.from_user.id
        answer_from_model = interactor.run_loop_bot(table, build_plots, user_question, user_id)
        bot.send_message(message.from_user.id, answer_from_model)

        pattern = r"\b\w+\.png\b"
        if ".png" in answer_from_model:
            plot_files = re.findall(pattern, answer_from_model)
            for plot_file in plot_files:
                path_to_file = "Plots/" + plot_file
                print(path_to_file)

            bot.send_photo(message.from_user.id, open(path_to_file, "rb"))
            os.remove(path_to_file)
        if user_question != "/exit":
            bot.register_next_step_handler(message, call_to_model, settings)
    else:
        bot.send_message(message.from_user.id, "Сначала нужно задать первоначальные настройки")
        bot.register_next_step_handler(message, main, settings)


@bot.message_handler(commands=["help"])
def help(message):
    bot.send_message(message.from_user.id, "Я - автономный помощник для проведения различной аналитики")


bot.polling()
