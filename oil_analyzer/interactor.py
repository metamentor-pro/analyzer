import io
import logging
import traceback
import pathlib

import numpy as np
import pandas as pd
from langchain.agents import Tool
from langchain.chat_models import ChatOpenAI

from agent import BaseMinion
from common_prompts import TableDescriptionPrompt
from custom_python_ast import CustomPythonAstREPLTool
from msg_parser import memo, memo2

path = "data/data.json"
sheet_name = "Sheet1"


file_extension = pathlib.Path(path).suffix

if file_extension == '.XLSX':
    df = pd.read_excel(path, sheet_name= sheet_name)
if file_extension == ".json":
    df = pd.read_json(path)
if file_extension == ".csv":
    df = pd.read_csv(path)



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
)
context = "" #there should be context that depends on task ( memo + memo2 for example)

prompt = TableDescriptionPrompt("""
date - column with date
row_title_column - column with name of well. One well can be included many times in the report.
column_268 – column with oil production losses per 24-hour shift (tons/day).
column_281 – column with planned water cut coefficient from geologists (in percent).
column_310 – column with oil production of the well for 24 hours of operation (tons/day).
column_314 – a column with planned indicators of daily oil production from geologists (tons/day).
column_331 – column with the difference between planned oil production and actual oil production (tons/day).
column_354 – column with data on well fluid production for 24 hours of operation (m³/day).
column_362 - column with data on the actual water cut of the well (in percent).
column_364 – column with information about gas production (m³/day).
column_370 – column with oil density data (tons/m³).
column_372 – column with information about the actual operation of the well (hours).
column_386 – column with data on fluid production, taking into account intra-shift losses (m³/day).
column_475 – column with planned fluid production from geologists (m³/day).""", context)

ag = BaseMinion(base_prompt=prompt.__str__(),
                available_tools=[
                    Tool(name=python_tool.name, description=python_tool.description, func=python_tool._run)], model=llm)


logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")
while True:
    question = input()
    if question == "exit":
        break
    try:
        df_info = df_info
        df_head = df_head
        question = question
        print(f"Answer: {ag.run(input=question, df_head=df_head, df_info=df_info.getvalue())}")
    except Exception as e:
        print(f"Failed with error: {traceback.format_exc()}")
