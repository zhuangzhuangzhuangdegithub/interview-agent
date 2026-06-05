"""Universal Agent — SQL-based question fetch + LLM-based evaluation."""
import json, re, uuid, os, random
import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from tools.search import search_questions as db_search, get_question_by_id, get_all_modules
from agent.memory import save_conversation, load_conversation, update_user_model, format_user_context, get_adaptive_difficulty, get_weak_modules


class UniversalAgent:

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        from openai import OpenAI
        self.api_key = api_key or ""
        self.base_url = base_url or "https://api.deepseek.com"
        self.model = model or "deepseek-chat"
        self.user_id = "default"
        self._last_thinking = []
        self._current_question = None
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _system(self) -> str:
        ctx = format_user_context(self.user_id)
        available = get_all_modules()
        mods = "、".join(available) if available else "LLM基础、Agent架构、RAG与知识库"
        return f"""你是 AI 面试教练。用户画像：{ctx}
题库可用模块：{mods}。只讨论这些模块，不要提及题库中没有的内容。始终中文回复。"""

    def _call_llm(self, prompt: str) -> str:
        """Simple LLM call. No tools, no complexity."""
        messages = [
            {"role": "system", "content": self._system()},
            *load_conversation(self.user_id)[-10:],
            {"role": "user", "content": prompt}
        ]
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.7
        )
        text = resp.choices[0].message.content or ""
        # Clean any XML artifacts from DeepSeek
        import re as _re
        text = _re.sub(r"<[^>]*>", "", text)  # strip ALL XML tags
        text = _re.sub(r"\s+", " ", text).strip()
        return text

    @property
    def last_thinking(self) -> list:
        return getattr(self, "_last_thinking", [])

    def chat(self, user_input: str) -> str:
        history = load_conversation(self.user_id)
        context = "\n".join([f"{h['role']}：{h['content'][:200]}" for h in history[-6:]])
        resp = self._call_llm(f"历史：\n{context}\n\n用户：{user_input}")
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": resp})
        save_conversation(self.user_id, history[-50:])
        self._last_thinking = ["💬 直接对话（无工具调用）"]
        return resp

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        available = get_all_modules()
        diff = difficulty or get_adaptive_difficulty(self.user_id)
        weak = get_weak_modules(self.user_id)
        mod = module or (weak[0] if weak else "LLM基础")

        # Direct DB query — reliable, no XML issues
        results = db_search(module=mod, difficulty=diff, top_k=20)
        if not results:
            results = db_search(module=mod, top_k=20)
        if not results:
            mod_list = "、".join(available)
            return f"题库暂无「{mod}」的题目。可用：{mod_list}"

        picked = random.choice(results)
        self._current_question = picked
        stars = "⭐" * picked.get("difficulty", 2)
        tags = ", ".join(picked.get("tags", [])[:3])
        self._last_thinking = [f"📋 从 {mod} 模块 {len(results)} 题中随机抽选 1 题"]
        return f"【模块】{picked['module']}  【难度】{stars}\n【标签】{tags}\n\n📝 {picked['question']}"

    def evaluate_answer(self, user_answer: str) -> str:
        q = self._current_question
        if not q:
            return "请先输入「练习」开始出题。"

        resp = self._call_llm(
            f"评分(1-10)，给反馈和改进建议。\n"
            f"题目：{q.get('question','')}\n参考答案：{q.get('answer','')[:500]}\n用户回答：{user_answer}"
        )

        # Parse score
        try:
            m = re.search(r"(\d+)/10|评分[：:]\s*(\d+)", resp)
            score = int(m.group(1) or m.group(2)) if m else 5
            update_user_model(self.user_id, q.get("module","未知"), score, q.get("tags",[]))
        except: pass

        self._last_thinking = [f"📊 已评分，更新用户模型：{q.get('module','')}"]
        return resp

    def generate_report(self) -> str:
        ctx = format_user_context(self.user_id)
        resp = self._call_llm(f"生成练习报告。{ctx}")
        self._last_thinking = ["📊 生成练习报告"]
        return resp

    def reset(self):
        self._last_thinking = []
        self._current_question = None
        save_conversation(self.user_id, [])
