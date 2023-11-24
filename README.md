How the project is structured:
User interaction is carried out through the bot.py file and the bot_data_handler.py,
db_manager.py, and inline_keyboard_manager.py files.
Main stack: aiogram, aiosqlite
The agent's work is mainly carried out in the agent.py file, data processing and preparation for the
model's work - in the processing.py and interactor.py files. Prompt settings in the file - common_prompts.py
Main stack: asyncio, openai, langchain
To launch the project, add a config.yaml file with the following structure:
data:
  - path: data/data.json
  - description: YOUR_DESCRIPTION
build_plots: false
bot_api: YOUR_BOT_API
db_name: YOUR_DB_NAME
bot_name: YOUR_BOT_NAME
demo: [false, 10, false]
price_flag: False
Also, you need to enter OPENAI_API_KEY in the .env file
Execute the commands:
