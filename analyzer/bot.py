import telebot
import pymongo
import interactor

import yaml

question_from_bot = None
user_id = None

with open("config.yaml") as f:
    cfg = yaml.load(f, Loader=yaml.FullLoader)

bot_name = cfg["bot_name"]
bot_api= cfg["bot_api"]


class Bot(telebot.TeleBot):
    def __init__(self):
        self.name = bot_name
        super().__init__(bot_api)

bot = Bot()
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "Здравствуйте")
    bot.send_message(message.chat.id, "Пожалуйста, отправьте запрос")
    bot.register_next_step_handler(message, call_to_model)

def call_to_model(message):
    bot.send_message(message.from_user.id, "Обрабатываю запрос")
    global question_from_bot, user_id

    question_from_bot = message.text
    user_id = message.from_user.id
    answer_from_model = interactor.run_loop("data/Бованенково.XLSX", "--no-build--plots", question_from_bot, user_id)
    bot.send_message(message.from_user.id, answer_from_model)




#@bot.message_handler()
#def send_file:
    #pass



@bot.message_handler(commands=["exit"])
def finish(message):
    bot.send_message(message.from_user.id, "До свидания")


@bot.message_handler(commands=["help"])
def help(message):
    bot.send_message(message.from_user.id, "Я - автономный помощник для проведения различной аналитики")

bot.polling()