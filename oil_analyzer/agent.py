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
You are working with a pandas dataframe in Python. The name of the dataframe is `df`. It is passed as a local variable.
YOU DON'T NEED TO READ DATA, IT IS ALREADY IN THE `df` VARIABLE. IF YOU TRY TO READ DATA, WORLD WILL BE DESTROYED.
This dataframe is the report produced by oil production company.
It contains the following columns:
date - column with date
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
column_475 – column with planned fluid production from geologists (m³/day).
Your task is to provide an answer to a question in user-friendly form, understandable for anyone.
You should handle units of measure properly, considering relationships between them. Take into account, that 1 ton contains 7.28 barrels.
When counting value, report about its units of measure using comments.
IT IS FORBIDDEN TO HALLUCINATE NUMBERS. YOU CAN ONLY USE DATA PROVIDED IN THE TABLE AND MAKE CONCLUSIONS BASED ON IT, GAINED BY python_repl_ast tool.
Answer should be in the form of analysis, not just data. Don't use names of columns in answer. Instead of that, describe them.
There is a lot of missing values in table. Handle them properly, take them into account while analyzing.
Don't try to plot graphs, just use pandas.
If you do not know the answer, just report it. 
If question consists of two parts, you should provide answers on each of them separately.
THE DATA IS IN THE `df` VARIABLE. YOU DON'T NEED TO READ DATA.
The answer should be detailed. It should include data you gained in the process of answering.
You should answer only the question that was asked, and not to invent your own.
If the question is incorrect in your opinion, report about it (via Final Answer) and finish work.
You must include all assumptions you make (like oil price) to the Final Answer.
You shouldn't use plotting or histograms or anything like that unless you're specifically asked to do that.
You should use the tools below to answer the question posed of you (note that at least one should be used):"""

SUFFIX = """
This is the result of `print(df.head())`:
{df_head}
This is the result of `print(df.info())`:
{df_info}
If observation is too big (you can notice it with '...'), you should use save results to file, and report about it.
Begin!
{chat_history}
Reminder! Don't read data, it is already placed in ```df``` variable.
Question: {input}
Final Answer should be ONLY in Russian, the rest can be in English.
{agent_scratchpad}"""

FORMAT_INSTRUCTIONS = """Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]. IT IS CRITICALLY IMPORTANT TO USE ONE OF PROVIDED TOOLS.
Action_Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action_Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question. Should be in Russian.

Don't omit any parts of this scheme.
"""


class MyOutputParser(AgentOutputParser):
    tool_names: List[str] = []

    def __init__(self, tool_names: List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_names = tool_names

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

        match = re.search(regex, text, re.DOTALL)

        if "Action:" not in text and "Action_Input:" not in text:
            return AgentAction("No", "hidden", text)
        if "Action:" in text and "Action_Input:" not in text:
            return AgentAction("No", "no input", text)
        if not match:
            return AgentAction("No", "hidden", text)

        action = match.group(1).strip()
        if action not in self.tool_names:
            return AgentAction("No", "invalid tool", text)
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
        import numpy as np
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
            return "If you are ready to answer, mark the answer with 'Final Answer', if you have work to do, just do it"
        if x == "invalid tool":
            return "WRONG ACTION - YOU SHOULD USE ONE OF PROVIDED TOOLS: [python_repl_ast, Human, No]"
        if x == "no input":
            return "YOU SHOULD FOLLOW THE PROVIDED SCHEME AND INCLUDE Action_Input, OR FINISH WORK USING Final Answer"

    human_input = HumanInputRun()
    human_input.description = (
        "You can use this tool to ask human a question. You should use it only in case you are told to do so."
    )
    python = PythonAstREPLTool(locals={"df": df, "python": None})
    python.description = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "When using this tool, sometimes output is abbreviated - "
        "make sure it does not look abbreviated before using it in your answer."
        "You shouldn't use print in the code. To get results, the last line should be the variable, which value you will get as observation. This value shouldn't be big dataframe, otherwise, you won't get observation."
    )
    tools = [python,
             human_input,
             Tool(name="No", func=NoFunc, description="Use this tool if no tool is needed. Even in that case, don't forget to include Action_Input")
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
    agent.output_parser = MyOutputParser(tool_names=tool_names)
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
