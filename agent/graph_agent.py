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
from agent.memory import save_conversation, load_conversation, update_user_model, format_user_context, get_adaptive_difficulty, get_weak_modules


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

        self.user_id = "default"
        self.history = []
        self.system_prompt = """You are an AI interview coach with memory. You remember the user's past performance and adapt.

CAPABILITIES:
- Search the question bank for relevant questions
- Retrieve full question details by ID
- Evaluate user answers and provide feedback
- Track user's strengths and weaknesses over time

WORKFLOW:
1. When user says "练习" with a module, search and present a question
2. When user answers, evaluate: score 1-10, give specific feedback
3. Adapt difficulty based on user's past performance
4. Prioritize user's weak areas for targeted practice

Always respond in Chinese. Be encouraging but professional. Reference the user's past performance when relevant."""

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

    def _invoke_graph(self, user_input: str) -> str:
        """Internal: run graph with memory context."""
        # Load history from Redis
        history = load_conversation(self.user_id)
        # Build context-rich system prompt
        user_ctx = format_user_context(self.user_id)
        ctx_msg = SystemMessage(content=self.system_prompt + f"\n\nCurrent User Context:\n{user_ctx}")

        msgs = [ctx_msg] + history[-20:] + [HumanMessage(content=user_input)]

        result = self.graph.invoke({
            "messages": msgs,
            "session_id": self.user_id,
            "current_question": None,
            "asked_ids": [],
            "mode": "idle",
        })

        # Save conversation to Redis
        self.history = history + [
            HumanMessage(content=user_input),
            result["messages"][-1]
        ]
        save_conversation(self.user_id, self.history)

        last = result["messages"][-1]
        return last.content if hasattr(last, "content") else str(last)

    def chat(self, user_input: str) -> str:
        return self._invoke_graph(user_input)

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        adapt_diff = difficulty or get_adaptive_difficulty(self.user_id)
        weak = get_weak_modules(self.user_id)
        mod = module or (weak[0] if weak else None)
        if mod:
            prompt = f"请从{mod}模块选一道难度{adapt_diff}的面试题。用户薄弱模块包括：{', '.join(weak[:3])}。"
        else:
            prompt = f"请从题库中随机选一道难度{adapt_diff}的面试题。"
        return self._invoke_graph(prompt)

    def evaluate_answer(self, user_answer: str) -> str:
        # Get last question info from history
        history = load_conversation(self.user_id)
        last_q = ""
        for msg in reversed(history):
            if hasattr(msg, "content") and "【模块】" in str(msg.content):
                last_q = str(msg.content)[:200]
                break
        prompt = f"请评分(1-10)并反馈。最近题目：{last_q}\n用户回答：{user_answer}"
        resp = self._invoke_graph(prompt)

        # Update user model (simplified scoring - extract score from response)
        try:
            import re
            score_match = re.search(r"(\d+)/10|评分[：:]\s*(\d+)", resp)
            score = int(score_match.group(1) or score_match.group(2)) if score_match else 5
            # Extract module from last question
            mod_match = re.search(r"【模块】(\S+)", last_q)
            module = mod_match.group(1) if mod_match else "未知"
            update_user_model(self.user_id, module, score, [])
        except:
            pass

        return resp

    def generate_report(self) -> str:
        ctx = format_user_context(self.user_id)
        return self._invoke_graph(f"请生成练习报告。{ctx}")

    def reset(self):
        self.history = []
        save_conversation(self.user_id, [])
