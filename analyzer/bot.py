import os
import telebot
import pymongo
import interactor


import re
import yaml

from telebot import types

question_from_bot = None
user_id = None
Conv_flag = False
plot_files = ""

class Outside_main_thread(Exception):
    def __init__(self, message ,plot_files):
        Exception.__init__(self)
        self.message = message
        self.plot_files = plot_files



with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

bot_name = cfg["bot_name"]
bot_api= cfg["bot_api"]


class Bot(telebot.TeleBot):
    def __init__(self):
        self.name = bot_name
        super().__init__(bot_api)

bot = Bot()
@bot.message_handler(commands=["start", "exit"])
def start(message):
    markup  = types.ReplyKeyboardMarkup()
    btn1 =  types.KeyboardButton("Добавить таблицу")
    btn2 = types.KeyboardButton("Добавить описание таблицы")
    btn3 = types.KeyboardButton("Поменять режим визуализации")
    btn4 = types.KeyboardButton("Режим отправки запроса")
    markup.row(btn1,btn2,btn3, btn4)


    bot.send_message(message.chat.id, "Вы можете ввести запрос или выбрать одну из опций", reply_markup= markup)
    #bot.send_message(message.chat.id, "Пожалуйста, отправьте запрос")

    bot.register_next_step_handler(message, on_click)

def on_click(message):
    if message.text == "Режим отправки запроса":
        bot.send_message(message.chat.id, "Пожалуйста, отправьте запрос")
        bot.register_next_step_handler(message, call_to_model)


@bot.message_handler()
def call_to_model(message):


    global question_from_bot, user_id,plot_files

    markup = types.ReplyKeyboardMarkup()
    btn1 = types.KeyboardButton("/exit")
    btn2 = types.KeyboardButton("Поменять режим визуализации")
    markup.add(btn1, btn2)

    bot.send_message(message.from_user.id, "Обрабатываю запрос, вы можете выйти из режима работы с моделью с помощью exit'", reply_markup= markup)

    question_from_bot = message.text
    user_id = message.from_user.id
    answer_from_model = interactor.run_loop("data/Бованенково.XLSX", True , question_from_bot, user_id)
    bot.send_message(message.from_user.id, answer_from_model)

    pattern = r"\b\w+\.png\b"
    if ".png" in answer_from_model:
        plot_files = re.findall(pattern, answer_from_model)
    for plot_file in plot_files:
        path_to_file = "Plots/" + plot_file
        print(path_to_file)

        bot.send_photo(message.from_user.id, open(path_to_file, "rb"))
        os.remove(path_to_file)





def do_nothing(message):
    pass



@bot.message_handler(commands=["exit"])
def finish(message):
    bot.send_message(message.from_user.id, "До свидания")


@bot.message_handler(commands=["help"])
def help(message):
    bot.send_message(message.from_user.id, "Я - автономный помощник для проведения различной аналитики")

bot.polling()