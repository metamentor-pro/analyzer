import logging

import pandas as pd
from langchain.chat_models import ChatOpenAI

from kek import create_pandas_dataframe_agent

df = pd.read_json("data/data.json")

llm = ChatOpenAI(temperature=0, model='gpt-3.5-turbo',
                 openai_api_key="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")

ag = create_pandas_dataframe_agent(llm, df, verbose=True)

logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")

while True:
    question = input()
    if question == "exit":
        break
    try:
        print(f"Answer: {ag.run(question)}")
    except Exception as e:
        print(f"Failed with error: {str(e)}")
