"""LangGraph-based Interview Agent — proper state graph with tool nodes."""
import json, uuid, re, random
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from config import LLM_API_KEY, LLM_API_BASE, LLM_MODEL
from tools.search import search_questions as db_search, get_question_by_id
from tools.practice import save_practice_record, get_user_profile, update_user_profile


# Define tools
@tool
def search_questions_tool(query: str) -> str:
    """Search the interview question bank. Input: module name or keywords like 'LLM基础' or 'Agent架构'. Returns list of matching questions."""
    results = db_search(keyword=query, top_k=10)
    if not results:
        return "No matching questions found."
    lines = []
    for r in results:
        lines.append(f"ID:{r['id']} [{r['module']}] L{r['difficulty']} {r['question'][:80]}")
    return "\n".join(lines)


@tool
def get_question_tool(question_id: int) -> str:
    """Get the full content and answer of a specific question by ID."""
    q = get_question_by_id(question_id)
    if not q:
        return "Question not found."
    return f"Question: {q['question']}\nAnswer: {q['answer']}\nModule: {q['module']} Tags: {q.get('tags',[])}"


@tool
def evaluate_answer_tool(question: str, reference_answer: str, user_answer: str) -> str:
    """Evaluate a user's answer against the reference answer. Returns score 1-10 and feedback."""
    # This is called by the agent, not directly scoring
    return f"Reference: {reference_answer}\nUser: {user_answer}"


# State
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    session_id: str
    current_question: dict | None
    asked_ids: list
    mode: str  # "idle" | "practicing"


class InterviewGraphAgent:
    """LangGraph-based Agent for interview practice."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        key = api_key or LLM_API_KEY
        url = base_url or LLM_API_BASE
        mdl = model or LLM_MODEL

        self.llm = ChatOpenAI(api_key=key, base_url=url, model=mdl, temperature=0.7)
        self.tools = [search_questions_tool, get_question_tool]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        self.system_prompt = """You are an AI interview coach. Help users practice technical interview questions.

CAPABILITIES:
- Search the question bank for relevant questions
- Retrieve full question details by ID
- Evaluate user answers and provide feedback

WORKFLOW:
1. When user says "练习" or "practice" with a module name, use search_questions_tool to find questions
2. Pick a question and use get_question_tool to show it
3. Wait for user's answer
4. Evaluate: score 1-10, give feedback. If <7 give hint, if 7-8 ask follow-up, if >8 confirm and offer next

Always respond in Chinese. Be encouraging but professional."""

        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        builder.add_node("chatbot", self._chatbot_node)
        builder.add_node("tools", self._tool_node)

        builder.set_entry_point("chatbot")

        builder.add_conditional_edges(
            "chatbot",
            self._route,
            {"tools": "tools", END: END}
        )
        builder.add_edge("tools", "chatbot")

        return builder.compile()

    def _chatbot_node(self, state: AgentState) -> dict:
        messages = [SystemMessage(content=self.system_prompt)] + state["messages"]
        response = self.llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def _tool_node(self, state: AgentState) -> dict:
        messages = state["messages"]
        last_msg = messages[-1]
        tool_calls = last_msg.tool_calls

        results = []
        for tc in tool_calls:
            tool_name = tc["name"]
            args = tc["args"]
            if tool_name == "search_questions_tool":
                output = search_questions_tool.invoke(args)
            elif tool_name == "get_question_tool":
                output = get_question_tool.invoke(args)
            else:
                output = f"Unknown tool: {tool_name}"
            results.append(ToolMessage(content=str(output), tool_call_id=tc["id"]))

        return {"messages": results}

    def _route(self, state: AgentState) -> Literal["tools", "__end__"]:
        messages = state["messages"]
        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"
        return END

    def _invoke_graph(self, user_input: str, history: list = None) -> str:
        """Internal: run graph with message."""
        msgs = list(history) if history else []
        msgs.append(HumanMessage(content=user_input))
        result = self.graph.invoke({
            "messages": msgs,
            "session_id": str(uuid.uuid4())[:8],
            "current_question": None,
            "asked_ids": [],
            "mode": "idle",
        })
        last = result["messages"][-1]
        return last.content if hasattr(last, "content") else str(last)

    def chat(self, user_input: str) -> str:
        """General chat."""
        return self._invoke_graph(user_input)

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        """Search and present a question."""
        if module:
            prompt = f"请从{module}模块随机选一道面试题展示给用户，用中文回复。"
        else:
            prompt = "请从题库中随机选一道面试题展示给用户，用中文回复。"
        return self._invoke_graph(prompt)

    def evaluate_answer(self, user_answer: str) -> str:
        """Score user's answer."""
        prompt = f"请对用户刚才的回答进行评分(1-10)并给出反馈和建议。用户回答：{user_answer}"
        return self._invoke_graph(prompt)

    def generate_report(self) -> str:
        """Generate session report."""
        return self._invoke_graph("请生成本次练习的总结报告。")

    def reset(self):
        pass
