from langchain.memory import ConversationBufferMemory
import openai
import logging
import re
import typing
import tiktoken
from dataclasses import dataclass
from typing import Any, List, Callable, Union
from langchain import LLMChain
from langchain.agents import LLMSingleActionAgent, AgentExecutor
from langchain.base_language import BaseLanguageModel
from langchain.prompts import StringPromptTemplate
from langchain.tools import Tool
from custom_output_parser import CustomOutputParser
from warning_tool import WarningTool

df_head_sub = None
df_info_sub = None

encoding = tiktoken.encoding_for_model("gpt-4")

def find_thought(text):
    pattern = r"Thought:(.*)"
    match = re.search(pattern, text)
    if match:
        thought = match.group(1).strip()
        return thought
    else:
        return None


def extract_variable_names(prompt: str, interaction_enabled: bool = False):
    variable_pattern = r"\{(\w+)\}"
    variable_names = re.findall(variable_pattern, prompt)
    if interaction_enabled:
        for name in ["tools", "tool_names", "agent_scratchpad"]:
            if name in variable_names:
                variable_names.remove(name)
        variable_names.append("intermediate_steps")
    return variable_names


openai.api_key = ""


def get_answer(prompt: str, model: str) -> str:
    completion = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return completion.choices[0].message.content


class CustomPromptTemplate(StringPromptTemplate):
    template: str
    # The list of tools available
    tools: List[Tool]
    agent_toolnames: List[str]
    summarize_every_n_steps: int = 2
    keep_n_last_thoughts: int = 1
    steps_since_last_summarize: int = 0
    my_summarize_agent: Any = None
    last_summary: str = ""
    project: Any | None = None
    callback: Union[Callable, None] = None
    summary_line = ""

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

    async def format(self, **kwargs) -> str:
        # Get the intermediate steps (AgentAction, AResult tuples)
        # Format them in a particular way
        intermediate_steps = kwargs.pop("intermediate_steps")

        # if self.callback is not None and len(intermediate_steps) > 0:
        # self.callback(intermediate_steps[-1][0].log)
        if (
                self.steps_since_last_summarize == self.summarize_every_n_steps
                and self.my_summarize_agent
        ):
            self.steps_since_last_summarize = 0
            self.last_summary = self.my_summarize_agent.run(
                # to do: there should be better ways to do that
                summary=self.last_summary,
                thought_process=self.thought_log(
                    intermediate_steps[
                     -self.summarize_every_n_steps: -self.keep_n_last_thoughts
                    ]
                ),
            )
            if self.callback is not None:
                if self.last_summary is None:
                    self.last_summary = ""
                else:
                    self.summary_line += "\n" + self.last_summary
                    if len(self.summary_line) > 3900:
                        self.summary_line = self.summary_line[200:]
                await self.callback(self.summary_line)
        if self.my_summarize_agent:
            kwargs["agent_scratchpad"] = (
                    "Here is a summary of what has happened:\n" + self.last_summary
            )
            kwargs["agent_scratchpad"] += "\nEND OF SUMMARY\n"
        else:
            kwargs["agent_scratchpad"] = ""
        tokens_integer = encoding.encode(self.thought_log(intermediate_steps))
        if len(tokens_integer) > 3500:
            kwargs["agent_scratchpad"] = "Here go your thoughts and actions:\n" + self.thought_log(intermediate_steps[1000:])
            print("deleted")

        else:
            kwargs["agent_scratchpad"] = "Here go your thoughts and actions:\n" + self.thought_log(intermediate_steps)
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
        #print(result)
        return result


@dataclass
class BaseMinion:
    def __init__(self, base_prompt: str, available_tools: List[Tool], model: BaseLanguageModel,
                 max_iterations: int = 500, df_head: Any = None, df_info: Any = None,
                 callback: Union[Callable, None] = None, summarize_model: Union[str, None] = None) -> None:

        self.callback = callback
        self.model = model
        self.available_tools = available_tools
        self.base_prompt = base_prompt
        self.df_head = df_head
        self.df_info = df_info


        llm = model
        available_tools.append(WarningTool().get_tool())

        # dictionary of subagents

        subagents = {"Checker": Checker(self.base_prompt, self.available_tools, self.model, self.df_head, self.df_info),
                     "Calculator": Calculator(self.base_prompt, self.available_tools, self.model, self.df_head, self.df_info),
                     }
        for subagents_names in subagents.keys():
            subagent = subagents[subagents_names]
            available_tools.append(subagent.get_tool())
        agent_toolnames = [tool.name for tool in available_tools]

        class Summarizer:
            def __init__(self, inner_summarize_model: Union[str, None] = None):
                self.summary = ""
                self.summarize_model = inner_summarize_model

            def run(self, summary: str, thought_process: str):

                if self.summarize_model is None:
                    return self.summary

                thought = find_thought(thought_process)
                print("thoughts:", thought)

                last_summary = get_answer(f"Your task is to translate the thought process of the model into Russian language,"
                                            f"there should not be any  code or formulas, just brief explanation of the actions."
                                            f"YOU SHOULD ALWAYS DESCRIBE ONLY LAST ACTIONS"
                                            f"IF THERE IS A NAME OF FILE IN .png FORMAT, YOU SHOULD NOT CHANGE IT"
                                            f"Here is a summary of what has happened:\n {summary};\n"
                                            f"Here is the last actions happened: \n{thought}", self.summarize_model)

                return last_summary

            def add_question_answer(self, question: str, answer: str):
                self.summary += f"Previous question: {question}\nPrevious answer: {answer}\n\n"

                return self.summary

        self.summarizer = Summarizer(summarize_model)

        self.prompt = CustomPromptTemplate(
            template=base_prompt,
            tools=available_tools,
            input_variables=extract_variable_names(
                base_prompt, interaction_enabled=True
            ),
            agent_toolnames=agent_toolnames,
            my_summarize_agent=self.summarizer,
            callback=self.callback
        )
        llm_chain = LLMChain(llm=llm, prompt=self.prompt)
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

        question = kwargs["input"]
        ans = (
                self.agent_executor.run(**kwargs)
                or "No result. The execution was probably unsuccessful."
        )

        summary = self.summarizer.add_question_answer(question, ans)

        final_answer = []

        final_answer.append(ans)
        final_answer.append(summary)
        return final_answer


class SubagentTool(BaseMinion):
    def __init__(self, base_prompt: str, available_tools: List[Tool], model: BaseLanguageModel, df_head_sub: Any = None, df_info_sub: Any = None,
                 max_iterations: int = 50) -> None:

        llm = model
        agent_toolnames = [tool.name for tool in available_tools]

        class Summarizer:
            def __init__(self, inner_summarize_model: Union[str, None] = None):
                self.summary = ""
                self.summarize_model = inner_summarize_model

            def run(self, summary: str, thought_process: str):
                if self.summarize_model is None:
                    return self.summary

                thought = find_thought(thought_process)
                print("thoughts:", thought)

                last_summary = get_answer(
                    f"Your task is to translate the thought process of the model into Russian language,"
                    f"there should not be any  code or formulas, just brief explanation of the actions."
                    f"YOU SHOULD ALWAYS DESCRIBE ONLY LAST ACTIONS. ANSWER SHOULD BE IN RUSSIAN"
                    f"Here is a summary of what has happened:\n {summary};\n"
                    f"Here is the last actions happened: \n{thought}", self.summarize_model)

                return last_summary

            def add_question_answer(self, question: str, answer: str):
                self.summary += f"Previous question: {question}\nPrevious answer: {answer}\n\n"

                return self.summary

        self.summarizer = Summarizer()

        self.prompt = CustomPromptTemplate(
            template=base_prompt,
            tools=available_tools,
            input_variables=extract_variable_names(
                base_prompt, interaction_enabled=True
            ),
            agent_toolnames=agent_toolnames,
            my_summarize_agent=self.summarizer,

        )
        llm_chain = LLMChain(llm=llm, prompt=self.prompt)
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
        question = kwargs["input"]
        ans = (
                self.agent_executor.run(**kwargs)
                or "No result. The execution was probably unsuccessful."
        )
        return ans

    name: str
    description: str
    func: typing.Callable[[str], str]

    def get_tool(self):
        return Tool(name=self.name, func=self.func, description=self.description)


# there can be any subagents needed
class Calculator(SubagentTool):
    def __init__(self, base_prompt: str, available_tools: List[Tool], model: BaseLanguageModel, df_head: Any = None, df_info: Any = None,
                 max_iterations: int = 50) -> None:
        super().__init__(base_prompt, available_tools, model)
        self.base_prompt = base_prompt
        self.available_tools = available_tools
        self.model = model
        self.df_head = df_head
        self.df_info = df_info

    name: str = "Calculator"
    description: str = "A subagent tool that can be used for calculations "

    def func(self, args: str) -> str:
        if (self.df_head is not None) and (self.df_info is not None):
            result = self.run(input=args, df_head=self.df_head, df_info=self.df_info)
            return '\r' + result + '\n'
        else:
            return "Not enough data"


class Checker(SubagentTool):
    def __init__(self, base_prompt: str, available_tools: List[Tool], model: BaseLanguageModel, df_head: Any = None, df_info: Any = None,
                 max_iterations: int = 50) -> None:
        super().__init__(base_prompt, available_tools, model)
        self.base_prompt = base_prompt
        self.available_tools = available_tools
        self.model = model
        self.df_head = df_head
        self.df_info = df_info
    name: str = "Checker"
    description: str = "A subagent tool that can be used to check the results"

    def func(self, args: str) -> str:
        if (self.df_head is not None) and (self.df_info is not None):
            result = self.run(input=args, df_head=self.df_head, df_info=self.df_info)
            return '\r' + result + '\n'
        else:
            return "Not enough data"



