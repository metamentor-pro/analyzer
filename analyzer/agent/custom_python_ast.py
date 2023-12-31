from typing import Dict, Optional

import ast
import sys
import traceback
from io import StringIO

from langchain.callbacks.manager import CallbackManagerForToolRun, AsyncCallbackManagerForToolRun
from pydantic import Field, root_validator

from langchain.tools import BaseTool


class CustomPythonAstREPLTool(BaseTool):

    name: str = "python_repl_ast"
    description: str = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "When using this tool, sometimes output is abbreviated - "
        "make sure it does not look abbreviated before using it in your answer."
    )

    globals: Optional[Dict[str, object]] = Field(default_factory=dict)
    locals: Optional[Dict[str, object]] = Field(default_factory=dict)
    sanitize_input: bool = True

    @root_validator(pre=True)
    def validate_python_version(cls, values: Dict[str, object]) -> Dict[str, object]:
        """Validate valid python version."""
        if sys.version_info < (3, 9):
            raise ValueError(
                "This tool relies on Python 3.9 or higher "
                "(as it uses new functionality in the `ast` module, "
                f"you have Python version: {sys.version}"
            )
        return values

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        try:
            if self.sanitize_input:
                # Remove the triple backticks from the query.
                query = query.strip().strip("```")
            tree = ast.parse(query)
            module = ast.Module(tree.body[:-1], type_ignores=[])
            exec(ast.unparse(module), self.globals, self.locals)  # type: ignore
            module_end = ast.Module(tree.body[-1:], type_ignores=[])
            module_end_str = ast.unparse(module_end)  # type: ignore
            try:
                # todo: ???
                raise NotImplementedError("Not yet")
                return eval(module_end_str, self.globals, self.locals)
            except Exception:
                old_stdout = sys.stdout
                sys.stdout = mystdout = StringIO()
                try:
                    exec(module_end_str, self.globals, self.locals)
                    sys.stdout = old_stdout
                    output = mystdout.getvalue()
                except Exception as e:
                    sys.stdout = old_stdout
                    output = str(e)
                if output == "":
                    return "Program didn't produce output. Use ```print()``` if you want to know something"
                return output
        except Exception as e:
            return traceback.format_exc()

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool asynchronously."""
        raise NotImplementedError("PythonReplTool does not support async")
        
