"""Agent for working with pandas objects."""
import io
from typing import Any, Dict, List, Optional

from langchain.agents import Tool, load_tools
from langchain.agents.agent import AgentExecutor
from langchain.agents.mrkl.base import ZeroShotAgent
from langchain.base_language import BaseLanguageModel
from langchain.callbacks.base import BaseCallbackManager
from langchain.chains.llm import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.tools import HumanInputRun

from custom_output_parser import CustomOutputParser
from custom_python_ast import CustomPythonAstREPLTool
from custom_output_parser import FORMAT_INSTRUCTIONS

PREFIX = """
You are working with a pandas dataframe in Python. The name of the dataframe is `df`. It is passed as a local variable.
YOU DON'T NEED TO READ DATA, IT IS ALREADY IN THE `df` VARIABLE. IF YOU TRY TO READ DATA, WORLD WILL BE DESTROYED.
This dataframe is the report produced by oil production company.
It contains the following columns:
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
You must include ALL assumptions you make (like oil price) to the Final Answer.
Before writing code, you should EXPLAIN ALL FORMULAS.
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
YOU MUST FOLLOW THE PROVIDED SCHEME (Thought/Action/Action_Input). EVERYTHING WILL BE DESTROYED IF YOU WON'T! YOU SHOULD INCLUDE ALL PARTS OF THIS SCHEME TO ONE ANSWER.
Question: {input}
Final Answer should be ONLY in Russian, the rest can be in English.
{agent_scratchpad}"""

WOLFRAM_TOKEN = "3JW87A-T9JPV96HTA"


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

    def no_func_wrapper(tools: List):
        def no_func(x):
            # return "\nThought:"
            if x == "wrong scheme":
                return "DON'T STOP AFTER 'Thought'. Continue with action or final answer (if you are ready to provide it)"
                return """IF YOU ARE READY TO ANSWER, MARK THE ANSWER WITH 'Final Answer'. IF YOU HAVE WORK TO DO, DO IT USING 'Action/Action_Input'
FOR EXAMPLE:
Action: python_repl_ast
Action_Input:
```
df.head(5)
```"""
            if x == "invalid tool":
                return "WRONG ACTION - YOU SHOULD USE ONE OF PROVIDED TOOLS: {}".format([tool.name for tool in tools])
            if x == "no input":
                return "YOU SHOULD FOLLOW THE PROVIDED SCHEME AND INCLUDE Action_Input, OR FINISH WORK USING Final Answer"

        return no_func

    human_input = HumanInputRun()
    human_input.description = (
        "You can use this tool to ask human a question. You should use it only in case you are told to do so."
    )
    python = CustomPythonAstREPLTool(locals={"df": df, "python": None, "python_repl_ast": None},
                                     globals={"pd": pd, "np": np})
    python.description = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "When using this tool, sometimes output is abbreviated - "
        "make sure it does not look abbreviated before using it in your answer."
        "You shouldn't use print in the code. To get results, the last line should be the variable, which value you will get as observation. This value shouldn't be big dataframe, otherwise, you won't get observation."
    )
    tools = []
    tools.extend([python,
                  human_input,
                  Tool(name="No", func=no_func_wrapper(tools),
                       description="Use this tool if no tool is needed. Even in that case, don't forget to include Action_Input")
                  ])
    # tools.extend(load_tools(["google-search"]))
    tools.extend(load_tools(["wolfram-alpha"], wolfram_alpha_appid=WOLFRAM_TOKEN))
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
    agent.output_parser = CustomOutputParser(tool_names=tool_names)
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
