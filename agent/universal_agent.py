"""Universal Agent — OpenAI SDK with tool calling fallback for DeepSeek."""
import json, re, uuid, os
import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from tools.search import search_questions as db_search, get_question_by_id
from agent.memory import save_conversation, load_conversation, update_user_model, format_user_context, get_adaptive_difficulty, get_weak_modules

TOOL_DEFS = [
    {"type": "function", "function": {
        "name": "search_questions",
        "description": "搜索面试题库。query 参数为模块名或关键词，如 'LLM基础' 或 'Agent架构'。",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "get_question",
        "description": "获取题目详情。question_id 为题目的数字ID。",
        "parameters": {"type": "object", "properties": {"question_id": {"type": "integer"}}, "required": ["question_id"]}
    }}
]


class UniversalAgent:

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        from openai import OpenAI
        self.api_key = api_key or ""
        self.base_url = base_url or "https://api.deepseek.com"
        self.model = model or "deepseek-chat"
        self.user_id = "default"
        self._last_thinking = []
        self._current_question = None  # Store current question for evaluation
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _system(self) -> str:
        ctx = format_user_context(self.user_id)
        return f"""你是 AI 面试教练。用户画像：{ctx}

你必须使用 function_call 调用工具，不要用文本描述工具调用。可用工具：
- search_questions(query) — 搜索题库
- get_question(question_id) — 获取题目详情

流程：用户说"练习XX"→调用 search_questions(query=XX)→选一题展示→等回答→评分1-10。
始终中文回复。"""

    def _execute_tools(self, messages: list, msg, thinking: list) -> str:
        """Execute tool calls from a message and return final response."""
        thinking.append(f"🔧 Agent 调用 {len(msg.tool_calls)} 个工具")
        messages.append(msg)

        for tc in msg.tool_calls:
            fn = tc.function.name
            args = json.loads(tc.function.arguments)
            thinking.append(f"  📞 {fn}({json.dumps(args, ensure_ascii=False)})")

            if fn == "search_questions":
                results = db_search(keyword=args.get("query", ""), top_k=10)
                tool_text = "\n".join([f"ID:{r['id']} [{r['module']}] L{r['difficulty']} {r['question'][:100]}" for r in results]) or "无结果"
                thinking.append(f"  📋 找到 {len(results)} 条结果")
            elif fn == "get_question":
                q = get_question_by_id(args.get("question_id", 0))
                tool_text = f"题目：{q['question']}\n答案：{q['answer']}" if q else "不存在"
                thinking.append("  📖 已获取题目详情")
            else:
                tool_text = "未知工具"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_text})

        thinking.append("💭 基于工具结果生成回复...")
        resp2 = self._client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.7
        )
        self._last_thinking = thinking
        return resp2.choices[0].message.content or ""

    def _call(self, prompt: str, use_tools: bool = True) -> str:
        thinking = ["🤔 分析用户输入..."]
        messages = [{"role": "system", "content": self._system()}]
        history = load_conversation(self.user_id)
        for h in history[-10:]:
            messages.append(h)
        messages.append({"role": "user", "content": prompt})

        tools = TOOL_DEFS if use_tools else None
        kwargs = {"model": self.model, "messages": messages, "temperature": 0.7}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # First attempt
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        # Success: structured tool calls
        if msg.tool_calls:
            return self._execute_tools(messages, msg, thinking)

        content = msg.content or ""

        # If content contains XML/伪代码 tool calls, retry with stronger instruction
        if content and (">" in content and ("search_questions" in content or "get_question" in content)):
            thinking.append("⚠️ 模型返回文本格式工具调用，重新请求...")
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "请使用 JSON function_call 格式调用工具。不要用 XML 或伪代码。"})
            kwargs["temperature"] = 0.3
            resp2 = self._client.chat.completions.create(**kwargs)
            msg2 = resp2.choices[0].message
            if msg2.tool_calls:
                return self._execute_tools(messages, msg2, thinking)

            # Still no tool_calls — return cleaned content as-is
            thinking.append("💬 直接回复（2次尝试后仍无结构化工具调用）")
            self._last_thinking = thinking
            return content[:800]

        thinking.append("💬 直接回复")
        self._last_thinking = thinking
        return content

    @property
    def last_thinking(self) -> list:
        return getattr(self, "_last_thinking", [])

    def chat(self, user_input: str) -> str:
        history = load_conversation(self.user_id)
        context = "\n".join([f"{h['role']}：{h['content'][:200]}" for h in history[-6:]])
        resp = self._call(f"历史：\n{context}\n\n用户：{user_input}", use_tools=False)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": resp})
        save_conversation(self.user_id, history[-50:])
        return resp

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        diff = difficulty or get_adaptive_difficulty(self.user_id)
        weak = get_weak_modules(self.user_id)
        mod = module or (weak[0] if weak else "LLM基础")
        # Bypass agent for search — use direct DB query with module filter
        results = db_search(module=mod, difficulty=diff, top_k=20)
        if not results:
            results = db_search(module=mod, top_k=20)
        if not results:
            return f"题库中暂无「{mod}」模块的题目。可用模块：LLM基础、Agent架构、RAG与知识库、Prompt工程、工具调用与工作流、微调与部署"

        import random
        picked = random.choice(results)
        self._current_question = picked  # Store for later evaluation
        stars = "⭐" * picked.get("difficulty", 2)
        return f"【模块】{picked['module']}  【难度】{stars}\n【标签】{', '.join(picked.get('tags', [])[:3])}\n\n📝 {picked['question']}"

    def evaluate_answer(self, user_answer: str) -> str:
        q = self._current_question
        if not q:
            return "请先输入「练习」开始出题。"
        question_text = q.get("question", "")
        answer_text = q.get("answer", "")
        module = q.get("module", "未知")
        tags = q.get("tags", [])

        resp = self._call(
            f"评分(1-10)并反馈。\n【题目】{question_text}\n【参考答案】{answer_text[:500]}\n【用户回答】{user_answer}",
            use_tools=False
        )
        try:
            m = re.search(r"(\d+)/10|评分[：:]\s*(\d+)", resp)
            score = int(m.group(1) or m.group(2)) if m else 5
            update_user_model(self.user_id, module, score, tags)
        except: pass
        return resp

    def generate_report(self) -> str:
        return self._call(f"生成练习报告。{format_user_context(self.user_id)}", use_tools=False)

    def reset(self):
        self._last_thinking = []
        self._current_question = None
        save_conversation(self.user_id, [])
