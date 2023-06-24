import io
import logging
import traceback
import pathlib
from typing import Union
import numpy as np
import pandas as pd
import seaborn as sns
import plotly as plotly
from langchain.agents import Tool
from langchain.chat_models import ChatOpenAI
from agent import BaseMinion
from common_prompts import TableDescriptionPrompt
from custom_python_ast import CustomPythonAstREPLTool
from msg_parser import memo, memo2
import typer
import yaml


def preparation(path: Union[str, None], build_plots: Union[bool, None], current_summary: Union[str, None] = "", table_description: Union[str, None] = ""):
    with open("config.yaml") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
    if path is None:
        path = cfg["data_path"]
    if build_plots is None:
        build_plots = cfg["build_plots"]
    sheet_name = "Sheet1"
    file_extension = pathlib.Path(path).suffix
    if file_extension == '.XLSX':
        df = pd.read_excel(path, sheet_name=sheet_name)
    elif file_extension == ".json":
        df = pd.read_json(path)
    elif file_extension == ".csv":
        df = pd.read_csv(path)
    else:
        raise Exception("Unknown file extension")
    df_head = df.head()
    df_info = io.StringIO()
    df.info(buf=df_info)
    llm = ChatOpenAI(temperature=0.7, model='gpt-4',
                     openai_api_key="")
    python_tool = CustomPythonAstREPLTool(locals={"df": df, "python": None, "python_repl_ast": None},
                                          globals={"pd": pd, "np": np, "sns": sns, "plotly": plotly})
    python_tool.description = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "If you want to see the output of a value, you should print it out with `print(...)`."
        "Code should always produce a value"
    )
    context = ""  # there should be context that depends on task (memo + memo2 for example)
    prompt = TableDescriptionPrompt(table_description = table_description, context = "", build_plots=build_plots, current_summary = current_summary)
    ag = BaseMinion(base_prompt=prompt.__str__(),
                    available_tools=[
                        Tool(name=python_tool.name, description=python_tool.description, func=python_tool._run)],
                    model=llm, df_head=df_head, df_info=df_info)
    return ag, df_head, df_info


logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")


def run_loop_bot(path: Union[str, None] = None, build_plots: Union[bool, None] = False, user_question: Union[str, None] = None, current_summary: Union[str, None] = "", table_description: Union[str, None] = ""):
    ag, df_head, df_info = preparation(path=path, build_plots=build_plots, current_summary=current_summary, table_description=table_description)

    while True:
        question = user_question  # this is for interacting with the user's request via a bot
        if question == "exit":
            break
        try:
            answer = ag.run(input=question, df_head=df_head, df_info=df_info.getvalue())

            return answer
        except Exception as e:

            return (f"Failed with error: {traceback.format_exc()}")


# rewrite the code above using typer library
app = typer.Typer()


@app.command()
def run_loop(path: Union[str, None] = None, build_plots: Union[bool, None] = False):
    ag, df_head, df_info = preparation(path=path, build_plots=build_plots)

    while True:

        question = input()

        if question == "exit":
            break
        try:
            answer = ag.run(input=question, df_head=df_head, df_info=df_info.getvalue())
            print(f"Answer: {answer[0]}")

        except Exception as e:
            print(f"Failed with error: {traceback.format_exc()}")


if __name__ == "__main__":
    app()