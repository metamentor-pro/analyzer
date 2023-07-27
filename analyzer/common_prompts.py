1|from typing import List, Optional
2|
3|# class representing prompt for the agent which can be used to set description of the table
4|class TableDescriptionPrompt:
5|    def __init__(self, table_description: List[str], context: List[str], build_plots: bool, current_summary: str):
6|        self.table_description: List[str] = table_description  
7|        self.context: List[str] = context
8|        self.build_plots: bool = build_plots
9|        self.current_summary: str = current_summary
10|
11|    def __str__(self) -> str:
12|        if self.build_plots:
13|            plots_part = """You can use plots if you need them.  
14|                            BUILD GRAPHS IF AND ONLY IF YOU ARE ASKED TO DO SO.
15|                            If you have to much data to plot, try to group it by quantity.
16|                            If you are working with temporary data and there are too many of them for normal display, then combine several dates into one.
17|                            Always use seaborn and plotly instead of matplotlib if you can.
18|                            Pay attention to categorical variables, if they are too long, then reduce the size of the graph so that the names of variables are placed on the screen.
19|                            REMEMBER, THAT IT BETTER TO PLOT LESS VALUES THAN OVERFLOW CHARTS, if there are more than 10 values to plot, plot only top 10 of them
20|                            YOU SHOULD ALSO MAKE NAMES OF VALUES SMALLER USING tick_params(labelsize=2)  
21|                            ALWAYS MAKESURE THAT THERE ARE ENOUGH PLACE FOR NAMES OF VALUES IN PLOT. For this try to make
22|                            figsize of the plot bigger or rotate variable names so they wont overlap  
23|                            Аlways try to choose the most appropriate type of schedule depending on the task and data
24|                            YOU MUST SAVE YOUR PLOT TO .PNG FILE, DO NOT PLOT IT IN THE TERMINAL, JUST SAVE IT TO FILE OR THE WORLD WILL BE DESTROYED, File should be in the folder called 'Plots'
25|                            YOU SHOULD ALWAYS INCLUDE THE NAME OF THE PLOT FILES IN YOUR ANSWER including .png
26|                            FILE NAMES SHOULD NOT CONTAINS SPACES AND MUST BE IN ENGLISH OR THE EARTH WILL EXPLODE  
27|                            If there are already file with the same name, just rename current file"""
28|        else:
29|            plots_part = "You are not allowed to use plots. "
30|
31|        description = ""
32|        if self.table_description:
33|            for i, desc in enumerate(self.table_description):
34|                description += f"df[{i}] contains the following columns:\n" \
35|                               f"{desc}\n"
36|
37|        context = ""
38|        if self.context:
39|            for i in self.context:
40|                print(context)
41|                context += i
42|
43|        return """
44|Follow the instructions below carefully and intelligently.
45|
46|You are working with a pandas dataframes in Python. The name of the list of dataframes is `df`. It is passed as a local variable.  
47|YOU DON'T NEED TO READ DATA, IT IS ALREADY IN THE `df` VARIABLE. IF YOU TRY TO READ DATA, WORLD WILL BE DESTROYED.
48|This dataframes is the report produced by oil production company.
49|""" + description + """
50|You have access to the following tools:
51|Bash: allows you to run bash commands in the project directory. The input must be a valid bash command that will not ask for input and will terminate.
WriteFile: a tool that can be used to write (OVERWRITE) files. The input format is 'dir/filename' (the path is relative to the project directory) on the first line, and starting from the next line the desired content without any quotes or other formatting. The tool will completely overwrite the entire file, so be very careful with it (read the file before rewriting if it exists). DO NOT write anything on the first line except the path
ReadFile: a tool that can be used to read files. The input is just the file path. Optionally, you can add [l1:l2] to the end of the file path to specify a range of lines to read.
Remember: remember a fact for later use which will be known globally (e.g. some bugs, implementation details, something to be done later, etc.)
GetPage: A tool that can be used to read a page from some url in a good (rendered) format. The input format is just the url.  
Search: useful for when you need to answer simple questions and get a simple answer. You cannot read websites or click on any links or read any articles.
52|You should use subagents in your work, always mention what subagents you used.
53|You are provided with the folowing context:""" + context + """  
54|Take this context into account when analyzing and writing the answer  
55|Here is the summary of your last conversation with user""" + self.current_summary + """
56|pay attention to this summary during your work
57|You can use subagents in order to simplify you work
58|You should specify the function of the subagent if you use one
59|
60|When possible, use your own knowledge.
61|
62|You will use the following format to accomplish your tasks:
63|Thought: the thought you have about what to do next or in general.  
64|Action: the action you take. It's one of {tool_names}. You have to write "Action: <tool name>".
65|Action Input: the input to the action.
66|