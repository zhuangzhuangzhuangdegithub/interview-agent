"""Claude Agent SDK-based Interview Agent — replaces LangChain/LangGraph."""
import json, re, uuid
from typing import AsyncGenerator

from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions,
    tool, create_sdk_mcp_server,
    AssistantMessage, TextBlock,
)

import sys
sys.path.insert(0, "D:/whu/大三下/练习/agent")

from tools.search import search_questions as db_search, get_question_by_id
from agent.memory import save_conversation, load_conversation, update_user_model, format_user_context, get_adaptive_difficulty, get_weak_modules


# ── Custom Tools ──
@tool("search_questions", "搜索题库。参数：query-模块名或关键词如'LLM基础'", {"query": str})
async def search_questions_tool(args: dict) -> dict:
    query = args.get("query", "")
    results = db_search(keyword=query, top_k=10)
    text = "\n".join([f"ID:{r['id']} [{r['module']}] {r['question'][:80]}" for r in results]) if results else "未找到"
    return {"content": [{"type": "text", "text": text}]}


@tool("get_question", "获取题目详情。参数：question_id-题目ID", {"question_id": int})
async def get_question_tool(args: dict) -> dict:
    q = get_question_by_id(args.get("question_id", 0))
    if q:
        text = f"题目：{q['question']}\n答案：{q['answer']}\n模块：{q['module']}"
    else:
        text = "题目不存在"
    return {"content": [{"type": "text", "text": text}]}


# ── Agent Class ──
class CCSDKAgent:
    """Agent powered by Claude Agent SDK with custom interview tools."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        import os
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-6"
        self.user_id = "default"

        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
        if base_url:
            os.environ["ANTHROPIC_BASE_URL"] = base_url

        # Build MCP server with custom tools
        self.mcp = create_sdk_mcp_server(
            name="interview-tools", version="1.0.0",
            tools=[search_questions_tool, get_question_tool]
        )

        self._conversation = []

    def _build_options(self) -> ClaudeAgentOptions:
        user_ctx = format_user_context(self.user_id)
        system = f"""你是一位专业的 AI 面试教练。用户信息：{user_ctx}

能力：搜索题库、查看题目详情、评估回答、追踪学习进度。
策略：优先从用户薄弱模块出题，根据正确率自适应调整难度。
始终用中文回复。鼓励但不空洞。"""

        return ClaudeAgentOptions(
            system_prompt=system,
            mcp_servers={"tools": self.mcp},
            allowed_tools=["mcp__tools__search_questions", "mcp__tools__get_question"],
            max_turns=5,
            model=self.model,
        )

    async def _run(self, prompt: str) -> str:
        """Internal: run agent and collect text response."""
        result_parts = []
        options = self._build_options()

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            result_parts.append(block.text)

        return "\n".join(result_parts)

    def _sync(self, prompt: str) -> str:
        """Synchronous wrapper for the async agent."""
        import anyio
        return anyio.run(self._run, prompt)

    def chat(self, user_input: str) -> str:
        history = load_conversation(self.user_id)
        history_text = "\n".join([f"{'用户' if h.get('role')=='user' else 'AI'}：{h.get('content','')[:200]}"
                                  for h in history[-6:]])
        prompt = f"历史对话：\n{history_text}\n\n用户：{user_input}"
        resp = self._sync(prompt)

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": resp})
        save_conversation(self.user_id, history[-50:])
        return resp

    def start_practice(self, module: str = None, difficulty: int = None) -> str:
        diff = difficulty or get_adaptive_difficulty(self.user_id)
        weak = get_weak_modules(self.user_id)
        mod = module or (weak[0] if weak else "LLM基础")
        prompt = f"请用 search_questions 搜索{mod}模块，选一道难度{diff}的题目展示。只展示题目，不要答案。"
        return self._sync(prompt)

    def evaluate_answer(self, user_answer: str) -> str:
        history = load_conversation(self.user_id)
        last_q = ""
        for h in reversed(history):
            if h.get("role") == "assistant" and "【模块】" in h.get("content", ""):
                last_q = h["content"][:300]
                break
        prompt = f"对以下回答评分(1-10)并反馈。\n题目：{last_q}\n回答：{user_answer}"
        resp = self._sync(prompt)

        try:
            m = re.search(r"(\d+)/10|评分[：:]\s*(\d+)", resp)
            score = int(m.group(1) or m.group(2)) if m else 5
            mod_m = re.search(r"【模块】(\S+)", last_q)
            module = mod_m.group(1) if mod_m else "未知"
            update_user_model(self.user_id, module, score, [])
        except:
            pass
        return resp

    def generate_report(self) -> str:
        ctx = format_user_context(self.user_id)
        return self._sync(f"生成练习报告。{ctx}")

    def reset(self):
        self._conversation = []
        save_conversation(self.user_id, [])
