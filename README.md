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
`
$ docker-compose build`  
`
$ docker-compose up`  