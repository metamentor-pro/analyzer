import logging
import re
from dataclasses import dataclass
from typing import Any, List

from langchain import LLMChain
from langchain.agents import LLMSingleActionAgent, AgentExecutor
from langchain.base_language import BaseLanguageModel
from langchain.prompts import StringPromptTemplate
from langchain.tools import Tool, BaseTool

from custom_output_parser import CustomOutputParser
from warning_tool import WarningTool


def extract_variable_names(prompt: str, interaction_enabled: bool = False):
    variable_pattern = r"\{(\w+)\}"
    variable_names = re.findall(variable_pattern, prompt)
    if interaction_enabled:
        for name in ["tools", "tool_names", "agent_scratchpad"]:
            if name in variable_names:
                variable_names.remove(name)
        variable_names.append("intermediate_steps")
    return variable_names


class CustomPromptTemplate(StringPromptTemplate):
    template: str
    # The list of tools available
    tools: List[Tool]
    agent_toolnames: List[str]
    summarize_every_n_steps: int = 4
    keep_n_last_thoughts: int = 1
    steps_since_last_summarize: int = 0
    my_summarize_agent: Any = None
    last_summary: str = ""
    project: Any | None = None

    @property
    def _prompt_type(self) -> str:
        return "taskmaster"

    def thought_log(self, thoughts: str) -> str:
        result = ""
        for action, AResult in thoughts:
            if AResult.startswith("\r"):
                result += action.log + f"\nSystem note: {AResult[1:]}\n"
            else:
                result += action.log + f"\nAResult: {AResult}\n"
        return result

    def format(self, **kwargs) -> str:
        # Get the intermediate steps (AgentAction, AResult tuples)
        # Format them in a particular way
        intermediate_steps = kwargs.pop("intermediate_steps")
        if (
                self.steps_since_last_summarize == self.summarize_every_n_steps
                and self.my_summarize_agent
        ):
            self.steps_since_last_summarize = 0
            self.last_summary = self.my_summarize_agent.run(
                summary=self.last_summary,
                thought_process=self.thought_log(
                    intermediate_steps[
                    -self.summarize_every_n_steps: -self.keep_n_last_thoughts
                    ]
                ),
            )

        if self.my_summarize_agent:
            kwargs["agent_scratchpad"] = (
                    "Here is a summary of what has happened:\n" + self.last_summary
            )
            kwargs["agent_scratchpad"] += "\nEND OF SUMMARY\n"
        else:
            kwargs["agent_scratchpad"] = ""

        kwargs["agent_scratchpad"] += "Here go your thoughts and actions:"

        kwargs["agent_scratchpad"] += self.thought_log(
            intermediate_steps[
            -self.steps_since_last_summarize + self.keep_n_last_thoughts:
            ]
        )

        self.steps_since_last_summarize += 1

        kwargs["tools"] = "\n".join(
            [
                f"{tool.name}: {tool.description}"
                for tool in self.tools
                if tool.name in self.agent_toolnames
            ]
        )
        kwargs["tool_names"] = self.agent_toolnames
        if self.project:
            for key, value in self.project.prompt_fields().items():
                kwargs[key] = value
        logging.info("Prompt:\n\n" + self.template.format(**kwargs) + "\n\n\n")
        result = self.template.format(**kwargs)
        return result


@dataclass
class BaseMinion:
    def __init__(self, base_prompt: str, available_tools: List[Tool], model: BaseLanguageModel,
                 max_iterations: int = 50) -> None:
        llm = model

        agent_toolnames = [tool.name for tool in available_tools]
        available_tools.append(WarningTool().get_tool())

        prompt = CustomPromptTemplate(
            template=base_prompt,
            tools=available_tools,
            input_variables=extract_variable_names(
                base_prompt, interaction_enabled=True
            ),
            agent_toolnames=agent_toolnames,
        )

        llm_chain = LLMChain(llm=llm, prompt=prompt)

        output_parser = CustomOutputParser()

        agent = LLMSingleActionAgent(
            llm_chain=llm_chain,
            output_parser=output_parser,
            stop=["AResult:"],
            allowed_tools=[tool.name for tool in available_tools],
        )

        self.agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=available_tools, verbose=True, max_iterations=max_iterations
        )

    def run(self, **kwargs):
        # kwargs["feedback"] = kwargs.get("feedback", "")
        return (
                self.agent_executor.run(**kwargs)
                or "No result. The execution was probably unsuccessful."
        )
