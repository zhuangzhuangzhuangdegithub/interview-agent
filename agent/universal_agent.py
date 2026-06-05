"""Universal Agent — auto-detects Claude SDK vs OpenAI SDK based on base URL."""
import json, re, uuid, os
from typing import AsyncGenerator

import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from tools.search import search_questions as db_search, get_question_by_id
from agent.memory import save_conversation, load_conversation, update_user_model, format_user_context, get_adaptive_difficulty, get_weak_modules


def _is_anthropic(base_url: str) -> bool:
    return base_url and ("anthropic.com" in base_url or "claude" in base_url.lower())


class UniversalAgent:
    """Auto-switches between Claude SDK and OpenAI SDK based on provider."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or ""
        self.base_url = base_url or "https://api.deepseek.com"
        self.model = model or "deepseek-chat"
        self.user_id = "default"
        self._backend = "openai"  # default
        self._client = None

        if _is_anthropic(self.base_url):
            self._backend = "claude"
            self._init_claude()
        else:
            self._init_openai()

    def _init_openai(self):
        from openai import OpenAI
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _init_claude(self):
        os.environ["ANTHROPIC_API_KEY"] = self.api_key
        if self.base_url:
            os.environ["ANTHROPIC_BASE_URL"] = self.base_url

    def _build_system(self) -> str:
        ctx = format_user_context(self.user_id)
        return f"""你是 AI 面试教练。用户画像：{ctx}

工具：你可以调用以下函数：
- search_questions(query) → 搜索题库，返回题目列表
- get_question(id) → 获取题目详情和答案

流程：用户说"练习XX"→搜索XX模块→选一题展示→等用户回答→评分1-10并反馈。
薄弱模块优先出题，自适应调整难度。始终中文回复。"""

    def _call_openai(self, prompt: str, tools: list = None) -> str:
        messages = [{"role": "system", "content": self._build_system()}]
        history = load_conversation(self.user_id)
        for h in history[-10:]:
            messages.append(h)
        messages.append({"role": "user", "content": prompt})

        kwargs = {"model": self.model, "messages": messages, "temperature": 0.7}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        # Handle tool calls
        if msg.tool_calls:
            thinking = []
            for tc in msg.tool_calls:
                fn = tc.function.name
                args = json.loads(tc.function.arguments)
                thinking.append(f"🔧 调用工具：{fn}({json.dumps(args, ensure_ascii=False)})")
                if fn == "search_questions":
                    results = db_search(keyword=args.get("query", ""), top_k=10)
                    text = "\n".join([f"  · ID:{r['id']} [{r['module']}] {r['question'][:80]}" for r in results]) or "  无结果"
                    thinking.append(f"📋 搜索结果：\n{text}")
                elif fn == "get_question":
                    q = get_question_by_id(args.get("question_id", 0))
                    text = f"  题目：{q['question'][:100]}..." if q else "  不存在"
                    thinking.append(f"📖 获取题目：\n{text}")
                else:
                    thinking.append(f"  未知工具")

                # Execute the actual tool call
                if fn == "search_questions":
                    results = db_search(keyword=args.get("query", ""), top_k=10)
                    tool_text = "\n".join([f"ID:{r['id']} [{r['module']}] {r['question'][:80]}" for r in results]) or "无结果"
                elif fn == "get_question":
                    q = get_question_by_id(args.get("question_id", 0))
                    tool_text = f"题目：{q['question']}\n答案：{q['answer']}" if q else "不存在"
                else:
                    tool_text = "未知工具"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_text})

            thinking.append("💭 正在分析结果...")
            resp2 = self._client.chat.completions.create(model=self.model, messages=messages, temperature=0.7)
            final = resp2.choices[0].message.content or ""
            self._last_thinking = thinking
            return final

        self._last_thinking = []
        return msg.content or ""

    def _call_claude(self, prompt: str) -> str:
        from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
        import anyio

        async def _run():
            parts = []
            opts = ClaudeAgentOptions(
                system_prompt=self._build_system(),
                max_turns=3,
                model=self.model,
                allowed_tools=[],
            )
            async for msg in query(prompt=prompt, options=opts):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
            return "\n".join(parts)

        return anyio.run(_run)

    def _call(self, prompt: str) -> str:
        if self._backend == "claude":
            return self._call_claude(prompt)
        else:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_questions",
                        "description": "搜索面试题库。参数：query(模块名或关键词)",
                        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_question",
                        "description": "获取题目详情。参数：question_id(题目ID)",
                        "parameters": {"type": "object", "properties": {"question_id": {"type": "integer"}}, "required": ["question_id"]}
                    }
                }
            ]
            return self._call_openai(prompt, tools)

    def chat(self, user_input: str) -> str:
        history = load_conversation(self.user_id)
        context = "\n".join([f"{h['role']}：{h['content'][:200]}" for h in history[-6:]])
        resp = self._call(f"历史：\n{context}\n\n用户：{user_input}")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": resp})
        save_conversation(self.user_id, history[-50:])
        return resp

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        diff = difficulty or get_adaptive_difficulty(self.user_id)
        weak = get_weak_modules(self.user_id)
        mod = module or (weak[0] if weak else None)
        if mod:
            return self._call(f"请用 search_questions 搜索{mod}模块，选一道难度{diff}的题展示。只出题不展示答案。")
        return self._call(f"请用 search_questions 随机搜索，选一道难度{diff}的题展示。只出题不展示答案。")

    def evaluate_answer(self, user_answer: str) -> str:
        history = load_conversation(self.user_id)
        last_q = ""
        for h in reversed(history):
            if h.get("role") == "assistant" and "【模块】" in h.get("content", ""):
                last_q = h["content"][:300]
                break
        resp = self._call(f"评分(1-10)并反馈。题目：{last_q}\n回答：{user_answer}")
        try:
            m = re.search(r"(\d+)/10|评分[：:]\s*(\d+)", resp)
            score = int(m.group(1) or m.group(2)) if m else 5
            mod_m = re.search(r"【模块】(\S+)", last_q)
            update_user_model(self.user_id, mod_m.group(1) if mod_m else "未知", score, [])
        except: pass
        return resp

    def generate_report(self) -> str:
        return self._call(f"生成本次练习报告。{format_user_context(self.user_id)}")

    @property
    def last_thinking(self) -> list:
        return getattr(self, "_last_thinking", [])

    def reset(self):
        self._last_thinking = []
        save_conversation(self.user_id, [])
