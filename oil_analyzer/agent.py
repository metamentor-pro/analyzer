"""Agent for working with pandas objects."""
import io
import logging
import re
from typing import Any, Dict, List, Optional, Union

from langchain.agents import Tool
from langchain.agents.agent import AgentExecutor, AgentOutputParser
# from langchain.agents.agent_toolkits.pandas.prompt import PREFIX, SUFFIX
from langchain.agents.mrkl.base import ZeroShotAgent
from langchain.agents.mrkl.output_parser import FINAL_ANSWER_ACTION
from langchain.base_language import BaseLanguageModel
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.llm import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.schema import AgentAction, AgentFinish
from langchain.tools import HumanInputRun
from langchain.tools.python.tool import PythonAstREPLTool

PREFIX = """
You are working with a pandas dataframe in Python. The name of the dataframe is `df`. It is passed as a local variable, so there is no need to read it.
This dataframe is the report produced by oil production company.
It contains the following columns:
date - column with date
column_268 - a column in which oil production losses are calculated for a 24-hour shift.
column_281 – a column containing the planned coefficient as a percentage of geologists, which reflects the specific proportion of water in the produced oily fluid. Water cut: the higher, the lower the proportion of oil in the reservoir fluid.
column_310 – a column in which the oil production of the well is calculated for 24 hours of operation. The calculation is based on the ratio of the mass of oil to the mass of pure water (column_354), taking into account the equality of the volume and temperature of the substance and water. Density (column_370) shows the weight of a unit of oil.
column_314 - a column with planned indicators of daily oil production provided by geologists.
column_331 – a column in which the difference between the planned oil production (column_314) and the actual oil production (column_310) is calculated.
column_354 - a column that stores data on the well fluid production for 24 hours of operation.
column_362 – a column with data on the actual water cut in the well as a percentage.
column_364 – column containing information about gas production.
column_370 – column with oil density data.
column_372 – column with information about the actual operation of the well.
column_386 - column with data on fluid production, taking into account intra-shift losses.
column_475 - A column containing the planned fluid production provided by the geologists.
Your task is to provide an answer to a question in user-friendly form, understandable for anyone.
Answer should be in the form of analysis, not just data. Don't use names of columns in answer. Instead of that, describe them.
There is a lot of missing values in table. Handle them properly, take them into account while analyzing.
Don't try to plot graphs, just use pandas.
You should use the tools below to answer the question posed of you (note that at least one should be used):"""

SUFFIX = """
This is the result of `print(df.head())`:
{df_head}
This is the result of `print(df.info())`:
{df_info}
Begin!
{chat_history}
Question: {input}
Answer ONLY in Russian.
{agent_scratchpad}"""

FORMAT_INSTRUCTIONS = """Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action_Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action_Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question. Should be in Russian.

Don't omit any parts of this scheme.
"""


class MyOutputParser(AgentOutputParser):
    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        logging.info(text)
        if FINAL_ANSWER_ACTION in text:
            return AgentFinish(
                {"output": text.split(FINAL_ANSWER_ACTION)[-1].strip()}, text
            )
        # \s matches against tab/newline/whitespace

        regex = (
            r"Action\s*\d*\s*:[\s]*(.*?)[\s]*Action_Input\s*\d*\s*:[\s]*(.*)"
        )
        # regex_action = (
        #     r"Action\s*\d*\s*:[\s]*(.*?)[\s]*"
        # )
        # regex_action_input = r"Action_Input\s*\d*\s*:[\s]*(.*)"

        match = re.search(regex, text, re.DOTALL)
        # match_action = re.search(regex_action, text, re.DOTALL)
        # match_action_input
        if "Action:" not in text and "Action_Input:" not in text:
            return AgentFinish({"output" : text.strip()}, text)
        if not match:
            return AgentAction("No", "hidden", text)
            # raise OutputParserException(f"Could not parse LLM output: `{text}`")

        action = match.group(1).strip()
        action_input = match.group(2)
        return AgentAction(action, action_input.strip(" ").strip('"'), text)


def create_pandas_dataframe_agent(
        llm: BaseLanguageModel,
        df: Any,
        callback_manager: Optional[BaseCallbackManager] = None,
        prefix: str = PREFIX,
        suffix: str = SUFFIX,
        input_variables: Optional[List[str]] = None,
        verbose: bool = False,
        return_intermediate_steps: bool = False,
        max_iterations: Optional[int] = 15,
        max_execution_time: Optional[float] = None,
        early_stopping_method: str = "force",
        agent_executor_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Dict[str, Any],
) -> AgentExecutor:
    """Construct a pandas agent from an LLM and dataframe."""
    try:
        import pandas as pd
    except ImportError:
        raise ValueError(
            "pandas package not found, please install with `pip install pandas`"
        )

    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Expected pandas object, got {type(df)}")

    if input_variables is None:
        input_variables = ["df_head", "df_info", "input", "agent_scratchpad", "chat_history"]

    def NoFunc(x):
        if x == "hidden":
            return "Use Final Answer if you have nothing to do, if you have work to do, just do it"
            return "You didn't follow Thought/Action/Action_Input scheme"

    tools = [PythonAstREPLTool(locals={"df": df, "python": None}),
             HumanInputRun(),
             Tool(name="No", func=NoFunc, description="Use this tool if no tool is needed")
             ]
    # tools.extend(load_tools(["google-search"]))
    prompt = ZeroShotAgent.create_prompt(
        tools, prefix=prefix, suffix=suffix, format_instructions=FORMAT_INSTRUCTIONS, input_variables=input_variables
    )
    buf = io.StringIO()
    df.info(buf=buf)

    partial_prompt = prompt.partial(df_head=str(df.head().to_markdown()), df_info=buf.getvalue())
    llm_chain = LLMChain(
        llm=llm,
        prompt=partial_prompt,
        callback_manager=callback_manager,
    )
    tool_names = [tool.name for tool in tools]
    agent = ZeroShotAgent(
        llm_chain=llm_chain,
        allowed_tools=tool_names,
        callback_manager=callback_manager,
        **kwargs,
    )
    agent.output_parser = MyOutputParser()
    memory = ConversationBufferMemory(memory_key="chat_history")
    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        memory=memory,
        callback_manager=callback_manager,
        verbose=verbose,
        return_intermediate_steps=return_intermediate_steps,
        max_iterations=max_iterations,
        max_execution_time=max_execution_time,
        early_stopping_method=early_stopping_method,
        **(agent_executor_kwargs or {}),
    )
