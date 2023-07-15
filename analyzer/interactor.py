import io
import logging
import traceback
import pathlib
from typing import Union, Callable, List
import numpy as np
import pandas as pd
import seaborn as sns
import plotly as plotly
from langchain.agents import Tool
from langchain.chat_models import ChatOpenAI
from agent import BaseMinion
from common_prompts import TableDescriptionPrompt
from custom_python_ast import CustomPythonAstREPLTool

from processing import process, unmerge_sheets

import typer
import yaml


def read_df(path: str) -> (pd.DataFrame, str):
    file_extension = pathlib.Path(path).suffix.lower()
    file_name = pathlib.Path(path).name

    if file_extension == '.xlsx':
        prepared = process(path)
        return pd.read_excel(prepared[0]), prepared[1]
    elif file_extension == ".json":
        return pd.read_json(path), file_name
    elif file_extension == ".csv":
        return pd.read_csv(path), file_name
    else:
        raise Exception("Unknown file extension")


def df_head_description(i: int, df: pd.DataFrame, name) -> str:
    return f"table: {name} \n"\
           f"df[{i}].head():" \
           f"{df.head()}\n"


def df_info_description(i: int, df: pd.DataFrame) -> str:
    buf = io.StringIO()
    df.info(buf=buf)
    return f"df[{i}].info():" \
           f"{buf.getvalue()}\n"


def preparation(path_list: List[str], build_plots: Union[bool, None], current_summary: Union[str, None] = "",
                table_description: List[str] = None, context_list: List[str] = None, callback: Callable = None):

    with open("config.yaml") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)

    #assert path_list is None
    #print(cfg["data"])
    if path_list is None:
        path_list = [data_item["path"] for data_item in cfg["data"]]
    if build_plots is None:
        build_plots = cfg["build_plots"]

    prepared_path_list = list()
    print(path_list)
    for path in path_list:
        file_extension = pathlib.Path(path).suffix.lower()
        if file_extension == ".xlsx":
            prepared_path_list.extend(unmerge_sheets(path))
        else:
            prepared_path_list.append(path)
    print(prepared_path_list)
    df_list = [read_df(path) for path in prepared_path_list]
    df_head = ""
    for i, item in enumerate(df_list):
        df_head += df_head_description(i, item[0], item[1])

    df_work = list()
    df_info = ""
    for i, item in enumerate(df_list):
        df_info += df_info_description(i, item[0])
        df_work.append(item[0])

    llm = ChatOpenAI(temperature=0.7, model='gpt-4',
                     openai_api_key="")
    python_tool = CustomPythonAstREPLTool(locals={"df": df_work, "python": None, "python_repl_ast": None},
                                          globals={"pd": pd, "np": np, "sns": sns, "plotly": plotly})
    python_tool.description = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "If you want to see the output of a value, you should print it out with `print(...)`."
        "Code should always produce a value"
    )

    prompt = TableDescriptionPrompt(table_description=table_description, context=context_list, build_plots=build_plots, current_summary=current_summary)
    ag = BaseMinion(base_prompt=prompt.__str__(),
                    available_tools=[
                        Tool(name=python_tool.name, description=python_tool.description, func=python_tool._run)],
                    model=llm, df_head=df_head, df_info=df_info, callback=callback, summarize_model="gpt-3.5-turbo")
    return ag, df_head, df_info


logging.basicConfig(level=logging.INFO, filename="py_log.log", filemode="w")


def run_loop_bot(path_list: List[str] = None, build_plots: Union[bool, None] = False, user_question: Union[str, None] = None, current_summary: Union[str, None] = "",
                 table_description: List[str] = None, context_list: List[str] = None, callback: Callable = None):
    
    ag, df_head, df_info = preparation(path_list=path_list, build_plots=build_plots, current_summary=current_summary, table_description=table_description, context_list=context_list, callback=callback)

    while True:
        question = user_question  # this is for interacting with the user's request via a bot
        if question == "exit":
            break
        try:
            answer = ag.run(input=question, df_head=df_head, df_info=df_info)
            return answer

        except Exception as e:
            print(e)
            return (f"Failed with error: {traceback.format_exc()}")


# rewrite the code above using typer library
app = typer.Typer()


@app.command()
def run_loop(path_list: List[str] = None, build_plots: Union[bool, None] = False):

    ag, df_head, df_info = preparation(path_list=path_list, build_plots=build_plots)

    while True:

        question = input()

        if question == "exit":
            break
        try:
            answer = ag.run(input=question, df_head=df_head, df_info=df_info)
            print(f"Answer: {answer[0]}")

        except Exception as e:
            print(f"Failed with error: {traceback.format_exc()}")


if __name__ == "__main__":
    app()