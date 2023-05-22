import logging
import re
from typing import List, Union

from langchain.agents import AgentOutputParser
from langchain.schema import AgentAction, AgentFinish

FORMAT_INSTRUCTIONS = """Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: tool, one of [{tool_names}]. IT IS CRITICALLY IMPORTANT TO USE ONE OF PROVIDED TOOLS.
Action_Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action_Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question. Should be in Russian.
Assumptions <optional>: assumptions you made during computations (like oil price).

Don't omit any parts of this scheme.
"""

FINAL_ANSWER_ACTION = "Final Answer:"


class CustomOutputParser(AgentOutputParser):
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
            return AgentAction("No", "wrong scheme", text)
        if "Action:" in text and "Action_Input:" not in text:
            return AgentAction("No", "no input", text)
        if not match:
            return AgentAction("No", "wrong scheme", text)

        action = match.group(1).strip()
        if action not in self.tool_names:
            return AgentAction("No", "invalid tool", text)
        action_input = match.group(2)
        return AgentAction(action, action_input.strip(" ").strip('"'), text)
