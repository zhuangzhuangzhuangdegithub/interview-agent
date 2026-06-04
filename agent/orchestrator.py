"""Agent orchestrator — Agentic RAG with smart selection, scoring, and profiling."""
import json
import uuid
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from config import LLM_API_KEY, LLM_API_BASE, LLM_MODEL
from tools.search import search_questions, get_question_by_id
from tools.practice import save_practice_record, get_user_profile, update_user_profile, get_session_stats


class InterviewAgent:

    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_BASE,
            model=LLM_MODEL,
            temperature=0.7,
        )
        self.embedding_llm = ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_BASE,
            model=LLM_MODEL,
            temperature=0.0,
        )
        self.session_id = str(uuid.uuid4())[:8]
        self.history: list = []
        self.current_question: dict = None
        self.asked_ids: set = set()
        self.total_score: int = 0
        self.total_questions: int = 0

    def chat(self, user_input: str) -> str:
        """General chat with context."""
        self.history.append(HumanMessage(content=user_input))
        system = self._load_system_prompt()
        messages = [SystemMessage(content=system)] + self.history[-15:]
        response = self.llm.invoke(messages)
        self.history.append(AIMessage(content=response.content))
        return response.content

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        """Agentic RAG: smart question selection based on weak modules."""
        profile = get_user_profile()
        weak_mods = profile.get("weak_modules", {})

        # Agentic: prioritize weak modules (70% chance)
        import random
        if not module and weak_mods:
            weakest = max(weak_mods, key=weak_mods.get)
            if random.random() < 0.7:
                module = weakest

        results = search_questions(module=module, difficulty=difficulty, top_k=10)

        # Filter out already asked
        fresh = [r for r in results if r["id"] not in self.asked_ids]
        if not fresh:
            self.asked_ids.clear()
            fresh = results

        self.current_question = fresh[0]
        self.asked_ids.add(self.current_question["id"])

        stars = self._star(self.current_question["difficulty"])
        tags = ", ".join(self.current_question.get("tags", [])[:3])
        weak_hint = f"\n\n💡 系统检测到你「{module}」模块较薄弱，已优先出题。" if module == weak_mods and weak_mods.get(module, 0) > 1 else ""
        return (
            f"【模块】{self.current_question['module']}  【难度】{stars}\n"
            f"【标签】{tags}{weak_hint}\n\n"
            f"📝 {self.current_question['question']}"
        )

    def evaluate_answer(self, user_answer: str) -> str:
        """Score answer, save record, update profile, generate follow-up."""
        if not self.current_question:
            return "请先输入「练习」开始出题。"

        q = self.current_question

        prompt = f"""你是资深 AI 面试官。请评估以下回答。

【题目】{q['question']}
【参考答案】{q['answer']}
【用户回答】{user_answer}

请严格按照以下格式回复（每行一个字段）：
评分：1-10的数字
反馈：1-2句话的具体评价
追问：如评分<7给提示，评分7-8追问深层问题，评分>8写"PASS"
"""

        response = self.embedding_llm.invoke([HumanMessage(content=prompt)])
        text = response.content.strip()

        # Parse response
        score = 5
        feedback = "无法解析评分"
        follow_up = ""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("评分："):
                try:
                    score = int(re.search(r"\d+", line).group())
                except:
                    pass
            elif line.startswith("反馈："):
                feedback = line.replace("反馈：", "").strip()
            elif line.startswith("追问："):
                follow_up = line.replace("追问：", "").strip()

        score = max(1, min(10, score))

        # Save record
        try:
            save_practice_record(self.session_id, q["id"], user_answer, score, feedback)
        except Exception:
            pass  # DB might not be available

        # Update profile
        try:
            update_user_profile(q["module"], q.get("tags", []), score)
        except Exception:
            pass

        self.total_score += score
        self.total_questions += 1

        result = f"【评分】{score}/10\n【反馈】{feedback}"
        if follow_up and follow_up != "PASS":
            result += f"\n\n🔍 {follow_up}"
        elif score >= 8:
            result += "\n\n🎉 回答得很好！输入「练习」继续下一题，或「报告」查看总结。"

        return result

    def generate_report(self) -> str:
        """Generate comprehensive session report."""
        profile = get_user_profile()
        stats = get_session_stats(self.session_id)

        lines = [
            f"📊 本次练习报告",
            f"会话 ID：{self.session_id}",
            f"练习题目：{self.total_questions} 道",
            f"平均得分：{round(self.total_score/max(1,self.total_questions),1)}",
            "",
            "📈 模块分析：",
        ]
        for mod, data in stats.get("modules", {}).items():
            lines.append(f"  · {mod}：{data['count']}题，均分{data['avg']}")

        weak = profile.get("weak_modules", {})
        if weak:
            lines.append(f"\n⚠️ 待加强：{', '.join(f'{k}({v:.0f})' for k,v in sorted(weak.items(), key=lambda x:-x[1])[:3])}")

        total = profile.get("total_practiced", 0)
        avg = profile.get("avg_score", 0)
        lines.append(f"\n📊 累计统计：共{total}题，均分{avg}")

        return "\n".join(lines)

    def reset(self):
        self.session_id = str(uuid.uuid4())[:8]
        self.history = []
        self.current_question = None
        self.asked_ids = set()
        self.total_score = 0
        self.total_questions = 0

    def _load_system_prompt(self) -> str:
        with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read()

    def _star(self, d: int) -> str:
        return "⭐" * d
