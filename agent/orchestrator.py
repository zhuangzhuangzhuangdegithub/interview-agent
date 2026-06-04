"""Agent orchestrator using LangChain + DeepSeek API."""
import json
import uuid
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool

import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from config import LLM_API_KEY, LLM_API_BASE, LLM_MODEL, AGENT_MAX_ITERATIONS, AGENT_VERBOSE
from tools.search import search_questions, get_question_by_id


class InterviewAgent:
    """AI Interview Coach Agent."""

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_BASE,
            model=LLM_MODEL,
            temperature=0.7,
        )
        self.session_id = str(uuid.uuid4())[:8]
        self.history: list = []
        self.current_question: dict = None
        self.asked_ids: set = set()

    def chat(self, user_input: str) -> str:
        """Main entry point: user says something, agent responds."""
        self.history.append(HumanMessage(content=user_input))

        # Build context
        system = self._build_system_prompt()
        messages = [SystemMessage(content=system)] + self.history[-20:]

        # Call LLM
        response = self.llm.invoke(messages)

        self.history.append(AIMessage(content=response.content))
        return response.content

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        """Start a practice session with the first question."""
        results = search_questions(
            module=module,
            difficulty=difficulty,
            top_k=10
        )
        # Filter out already asked
        fresh = [r for r in results if r["id"] not in self.asked_ids]
        if not fresh:
            self.asked_ids.clear()
            fresh = results

        self.current_question = fresh[0]
        self.asked_ids.add(self.current_question["id"])

        stars = "⭐" * self.current_question["difficulty"]
        tags = ", ".join(self.current_question["tags"][:3])
        return (
            f"【模块】{self.current_question['module']}  【难度】{stars}\n"
            f"【标签】{tags}\n\n"
            f"📝 {self.current_question['question']}"
        )

    def evaluate_answer(self, user_answer: str) -> str:
        """Evaluate user's answer against the current question."""
        if not self.current_question:
            return "请先开始练习。"

        prompt = f"""你是一位专业的 AI 面试官。请根据以下信息评估用户的回答。

【题目】{self.current_question['question']}
【参考答案】{self.current_question['answer']}
【用户回答】{user_answer}

请给出：
1. 评分（1-10）
2. 简短反馈（1-2句话）
3. 如果评分<6，给一个提示引导用户补充
4. 如果评分6-8，追问一个更深层的问题
5. 如果评分>8，简要确认并建议下一题

请直接回复，不要用JSON格式。"""

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def generate_report(self) -> str:
        """Generate a session summary."""
        asked = list(self.asked_ids)
        modules = {}
        for qid in asked:
            q = get_question_by_id(qid)
            if q:
                modules[q["module"]] = modules.get(q["module"], 0) + 1

        return (
            f"📊 本次练习报告\n"
            f"会话 ID：{self.session_id}\n"
            f"练习题目：{len(asked)} 道\n"
            f"涉及模块：{json.dumps(modules, ensure_ascii=False)}\n"
        )

    def _build_system_prompt(self) -> str:
        with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()

    def reset(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.history = []
        self.current_question = None
        self.asked_ids = set()
