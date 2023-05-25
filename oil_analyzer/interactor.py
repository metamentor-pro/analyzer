import io
import logging
import traceback

import pandas as pd
import numpy as np
from langchain.chat_models import ChatOpenAI
from agent import BaseMinion
from prompts import *
from custom_python_ast import CustomPythonAstREPLTool
from langchain.agents import Tool
from langchain.utilities import PythonREPL

df = pd.read_json("data/data.json")
df_head = df.head()
df_info = io.StringIO()
df.info(buf=df_info)

llm = ChatOpenAI(temperature=0.7, model='gpt-4',
                 openai_api_key="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")

python_tool = CustomPythonAstREPLTool(locals={"df": df, "python": None, "python_repl_ast": None},
                                      globals={"pd": pd, "np": np})
python_tool.description = (
    "A Python shell. Use this to execute python commands. "
    "Input should be a valid python command. "
    "If you want to see the output of a value, you should print it out with `print(...)`."
    "Code should always produce a value"
    # "You shouldn't use print in the code. To get results, the last line should be the variable, which value you will get as observation. This value shouldn't be big dataframe, otherwise, you won't get observation."
)

ag = BaseMinion(base_prompt=execution_prompt,
                available_tools=[
                    Tool(name=python_tool.name, description=python_tool.description, func=python_tool._run)], model=llm)

# python_repl = PythonREPL(locals={"df": df, "python": None, "python_repl_ast": None},
#                          globals={"pd": pd, "np": np})
#
# ag = BaseMinion(base_prompt=execution_prompt, available_tools=[Tool(
#     name="python_repl_ast",
#     description="A Python shell. Use this to execute python commands. Input should be a valid python command. "
#                 "If you want to see the output of a value, you should print it out with `print(...)`.",
#     func=python_repl.run
# )
# ], model=llm)
#
# print(python_repl.run("import pandas as pd"
#                       "df = pd.read_json(\"data/data.json\")"))
# print(python_repl.run("print(df.head())"))

logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")
while True:
    question = input()
    if question == "exit":
        break
    try:
        df_info = df_info
        df_head = df_head
        question = question
        d = {"question": question, "df_head": df_head}
        print(f"Answer: {ag.run(input=question, df_head=df_head, df_info=df_info)}")
    except Exception as e:
        print(f"Failed with error: {traceback.format_exc()}")
