Как устроен проект:  
Взаимодействие с пользователем осуществляется через файл bot.py и файлы bot_data_handler.py,
db_manager.py и inline_keyboard_manager.py  
Основной стек: aiogram, aiosqlite

Работа агента осуществялется в основном в файле agent.py, обработка данных и подготовка к работе 
модели - в файлах processing.py и interactor.py. Настройка промптов в файле - common_prompts.py  
Основной стек: asyncio, openai, langchain





Для запуска проeкта добавьте файл config.yaml со следующей структурой:

data: 
  - path: data/data.json 
  - description: YOUR_DESCRIPTION

build_plots: false  
bot_api: YOUR_BOT_API  
db_name: YOUR_DB_NAME     
bot_name: YOUR_BOT_NAME  
demo: [false, 10, false]  
price_flag: False  

Также нужно вписать OPENAI_API_KEY в файл .env

Выполнить команды:  
`docker-compose build && docker-compose up -d`