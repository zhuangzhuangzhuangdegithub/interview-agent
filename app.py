"""AI Interview Agent — Dual mode with sidebar navigation."""
import streamlit as st
import json, re, random
from agent.universal_agent import UniversalAgent
from tools.search import add_question, get_all_modules, search_questions
from config import LLM_API_KEY as DEFAULT_KEY, LLM_API_BASE as DEFAULT_BASE, LLM_MODEL as DEFAULT_MODEL, PROJECT_ROOT

USER_CONFIG_FILE = PROJECT_ROOT + "/user_config.json"

def load_user_config():
    """Load saved user API config from local file."""
    try:
        with open(USER_CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_user_config(data: dict):
    """Save user API config to local file."""
    with open(USER_CONFIG_FILE, "w") as f:
        json.dump(data, f)


def interview_tab():
    """AI 面试陪练"""
    if "messages" not in st.session_state: st.session_state.messages = []
    if "mode" not in st.session_state: st.session_state.mode = "idle"
    own_key = bool(st.session_state.get("user_api_key")) or bool(DEFAULT_KEY)
    if own_key:
        current_key = st.session_state.get("user_api_key") or DEFAULT_KEY
        current_base = st.session_state.get("user_api_base") or DEFAULT_BASE
        current_model = st.session_state.get("user_api_model") or DEFAULT_MODEL
        # Recreate agent if API key changed or not exists
        if "agent" not in st.session_state or st.session_state.get("_agent_key") != current_key:
            st.session_state.agent = UniversalAgent(
                api_key=current_key, base_url=current_base, model=current_model
            )
            st.session_state._agent_key = current_key
        agent = st.session_state.agent
    else:
        # No key available - clear existing agent
        if "agent" in st.session_state:
            del st.session_state.agent
        agent = None

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if not own_key:
        st.warning("⚠️ 请先在侧边栏「⚙️ API 设置」中配置你的 API Key，才能使用 AI 面试陪练功能。自主刷题模式不需要 API Key。")
        return

    placeholder = "请输入 练习（模块名称） 将会开始出题，如：练习 Agent架构"
    if st.session_state.mode == "waiting_answer":
        placeholder = "输入你的回答，Enter 提交评分"

    if prompt := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                lower = prompt.strip().lower()
                if lower.startswith("练习") or lower.startswith("开始"):
                    text = prompt.strip()
                    module = None; difficulty = None
                    # Support both "练习 Agent架构" and "练习Agent架构"
                    if text.startswith("练习"):
                        rest = text[2:].strip()  # Remove "练习"
                    else:
                        rest = text[2:].strip()  # Remove "开始"
                    if rest:
                        parts = rest.split()
                        module = parts[0]  # First word is module
                        if len(parts) > 1 and parts[1].isdigit():
                            difficulty = int(parts[1])
                    resp = agent.start_practice(module=module, difficulty=difficulty)
                    st.session_state.mode = "waiting_answer"
                elif st.session_state.mode == "waiting_answer":
                    resp = agent.evaluate_answer(prompt)
                    st.session_state.mode = "idle"
                elif lower in ("报告", "report"):
                    resp = agent.generate_report()
                elif lower in ("重置", "reset"):
                    agent.reset(); st.session_state.messages = []; st.session_state.mode = "idle"
                    resp = "已重置。"
                else:
                    resp = agent.chat(prompt)
            # Show thinking process if available
            if hasattr(agent, "last_thinking") and agent.last_thinking:
                with st.expander("🧠 查看思考过程"):
                    for step in agent.last_thinking:
                        st.caption(step)
            st.markdown(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.rerun()


def review_tab():
    """自主刷题 with mastery tracking"""
    st.markdown("## 📝 自主刷题")
    if "rq" not in st.session_state: st.session_state.rq = []
    if "ri" not in st.session_state: st.session_state.ri = 0
    if "sa" not in st.session_state: st.session_state.sa = False
    if "mastered" not in st.session_state: st.session_state.mastered = set()
    if "needs_review" not in st.session_state: st.session_state.needs_review = set()
    if "reviewed_count" not in st.session_state: st.session_state.reviewed_count = 0

    # Stats row
    total_q = len(search_questions(top_k=1000))
    mastered = len(st.session_state.mastered)
    reviewed = st.session_state.reviewed_count
    pending = len(st.session_state.needs_review)

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("题库", total_q)
    with c2: st.metric("已刷", reviewed)
    with c3: st.metric("已掌握", mastered)
    with c4: st.metric("待复习", pending)

    # Filters
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        modules = get_all_modules()
        mod = st.selectbox("模块", ["全部"] + (modules if modules else []), key="rm")
    with fc2:
        mode_filter = st.selectbox("范围", ["全部题目", "仅未掌握"], key="rf")
    with fc3:
        diff = st.selectbox("难度", ["全部","初级","中级","高级"], key="rd")

    if st.button("🔀 随机抽题", use_container_width=True):
        m = None if mod == "全部" else mod
        d = None if diff == "全部" else ["初级","中级","高级"].index(diff)+1
        results = search_questions(module=m, difficulty=d, top_k=200)
        if results:
            random.shuffle(results)
            if mode_filter == "仅未掌握":
                results = [r for r in results if r["id"] not in st.session_state.mastered]
            st.session_state.rq = results; st.session_state.ri = 0; st.session_state.sa = False
            st.rerun()

    if not st.session_state.rq:
        results = search_questions(top_k=100)
        if results:
            random.shuffle(results)
            if mode_filter == "仅未掌握":
                results = [r for r in results if r["id"] not in st.session_state.mastered]
            st.session_state.rq = results
    questions = st.session_state.rq
    total = len(questions)
    if total == 0:
        if mode_filter == "仅未掌握":
            st.success("🎉 全部题目已掌握！")
        else:
            st.warning("题库为空")
        return

    idx = st.session_state.ri
    if idx >= total: idx = 0; st.session_state.ri = 0
    st.progress((idx+1)/total, f"第 {idx+1} / {total} 题")
    q = questions[idx]

    with st.container(border=True):
        stars = "⭐" * q.get("difficulty", 2)
        mastered_str = "✅ 已掌握" if q["id"] in st.session_state.mastered else ""
        st.caption(f"{q.get('module','')} · {stars}  {mastered_str}")
        st.markdown(f"### {q['question']}")

        btn_label = "💡 查看答案" if not st.session_state.sa else "🙈 隐藏答案"
        if st.button(btn_label, use_container_width=True):
            st.session_state.sa = not st.session_state.sa; st.rerun()
        if st.session_state.sa:
            st.divider(); st.markdown(q.get("answer","暂无答案"))

            # Mastery buttons
            mc1, mc2 = st.columns(2)
            with mc1:
                if st.button("✅ 已掌握", use_container_width=True):
                    st.session_state.mastered.add(q["id"])
                    st.session_state.needs_review.discard(q["id"])
                    st.session_state.reviewed_count += 1
                    st.session_state.sa = False
                    st.rerun()
            with mc2:
                if st.button("🔄 再复习", use_container_width=True):
                    st.session_state.needs_review.add(q["id"])
                    st.session_state.mastered.discard(q["id"])
                    st.session_state.reviewed_count += 1
                    st.session_state.sa = False
                    if idx < total - 1:
                        st.session_state.ri = idx + 1
                    st.rerun()

    # Navigation
    c1,c2,c3 = st.columns([1,2,1])
    with c1:
        if st.button("⬅ 上一题", disabled=idx==0, use_container_width=True):
            st.session_state.ri = max(0, idx-1); st.session_state.sa = False; st.rerun()
    with c2:
        st.caption(f"第 {idx+1} / {total} 题")
    with c3:
        if st.button("下一题 ➡", disabled=idx>=total-1, use_container_width=True):
            st.session_state.ri = min(total-1, idx+1); st.session_state.sa = False; st.rerun()

    st.markdown("""<script>
    document.addEventListener('keydown', function(e) {
        if (e.key==='ArrowLeft'){var b=document.querySelector('button:has-text("⬅")'); if(b&&!b.disabled){e.preventDefault();b.click();}}
        if (e.key==='ArrowRight'){var b=document.querySelector('button:has-text("➡")'); if(b&&!b.disabled){e.preventDefault();b.click();}}
        if (e.key===' '){e.preventDefault(); var b=document.querySelector('button:has-text("💡"),button:has-text("🙈")'); if(b)b.click();}
    });</script>""", unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="AI 面试陪练", page_icon="🤖")
    if "page" not in st.session_state: st.session_state.page = "interview"
    own_key = bool(st.session_state.get("user_api_key")) or bool(DEFAULT_KEY)

    with st.sidebar:
        st.subheader("⚙️ API 设置")
        with st.expander("配置 AI API"):
            # Load saved config from file
            saved = load_user_config()
            if not st.session_state.get("user_api_key") and saved.get("key"):
                st.session_state.user_api_key = saved["key"]
                st.session_state.user_api_base = saved.get("base","")
                st.session_state.user_api_model = saved.get("model","")

            providers = {
                "DeepSeek": {"base": "https://api.deepseek.com", "model": "deepseek-chat"},
                "OpenAI": {"base": "https://api.openai.com/v1", "model": "gpt-4o"},
                "Moonshot": {"base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
                "Anthropic Claude": {"base": "https://api.anthropic.com", "model": "claude-sonnet-4-6"},
                "通义千问": {"base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
                "自定义": {"base": "", "model": ""},
            }
            provider = st.selectbox("模型提供商", list(providers.keys()),
                index=0 if DEFAULT_BASE and "deepseek" in DEFAULT_BASE else 5)
            preset = providers[provider]

            api_key = st.text_input("API Key", value=st.session_state.get("user_api_key",""),
                                    placeholder="输入 API 密钥...", type="password")
            api_base = st.text_input("API Base URL", value=st.session_state.get("user_api_base") or preset["base"] or DEFAULT_BASE)
            api_model = st.text_input("Model", value=st.session_state.get("user_api_model") or preset["model"] or DEFAULT_MODEL)
            if st.button("保存设置", use_container_width=True):
                st.session_state.user_api_key = api_key
                st.session_state.user_api_base = api_base
                st.session_state.user_api_model = api_model
                save_user_config({"key": api_key, "base": api_base, "model": api_model})
                if "agent" in st.session_state: del st.session_state.agent
                st.success("已保存到本地，刷新浏览器后依然有效")
                st.rerun()

        st.divider()
        st.subheader("📌 选择模式")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🤖 AI 面试陪练", use_container_width=True,
                         type="primary" if st.session_state.page == "interview" else "secondary"):
                st.session_state.page = "interview"
                st.rerun()
        with c2:
            if st.button("📝 自主刷题", use_container_width=True,
                         type="primary" if st.session_state.page == "review" else "secondary"):
                st.session_state.page = "review"
                st.rerun()

        st.divider()

        if st.session_state.page == "interview" and "mode" in st.session_state:
            labels = {"idle": "等待指令", "waiting_answer": "等待你回答题目"}
            st.info(f"当前状态：{labels.get(st.session_state.mode, '未知')}")

        st.subheader("⌨️ 快捷键")
        st.caption("Ctrl+P 练习 | Ctrl+R 报告 | Ctrl+X 重置")

        # Module stats
        try:
            modules = get_all_modules(); total = 0; lines = []
            for m in modules:
                c = len(search_questions(module=m, top_k=1000)); total += c
                lines.append(f"· {m}：{c} 题")
            with st.expander(f"📚 题库统计（共 {total} 题）"):
                for l in lines: st.caption(l)
        except: pass

        if st.session_state.page == "interview":
            if own_key:
                if st.button("🔄 重置会话", use_container_width=True):
                    st.session_state.messages = []; st.session_state.mode = "idle"; st.rerun()
                if st.button("📊 生成报告", use_container_width=True):
                    if "agent" in st.session_state:
                        st.info(st.session_state.agent.generate_report())
            else:
                st.caption("配置 API Key 后可使用")

        st.divider()
        st.subheader("📁 一键导入题库")
        with st.expander("📋 查看支持的格式"):
            st.markdown("""
**JSON 格式** — 推荐用于结构化导入：
```json
[
  {
    "question": "什么是 RAG？",
    "answer": "RAG 即检索增强生成...",
    "difficulty": 2,
    "tags": ["RAG", "LLM"]
  }
]
```
**Markdown / TXT 格式** — 适合笔记导入：
```
Q: 什么是 RAG？
RAG 即检索增强生成，是一种结合检索和生成的技术...

Q: Agent 和普通 LLM 的区别？
Agent 具有自主规划和工具调用能力...
```
每条 `Q:` 开头为题目，下方段落为答案，题目之间自动分隔。
""")
        uf = st.file_uploader("选择文件上传", type=["json","md","txt"])
        if uf is not None:
            dm = st.selectbox("导入到模块", get_all_modules() or ["LLM基础"])
            if st.button("开始导入", use_container_width=True):
                content = uf.read().decode("utf-8"); count = 0
                if uf.name.endswith(".json"):
                    try:
                        for item in json.loads(content) if isinstance(json.loads(content), list) else [json.loads(content)]:
                            q = item.get("question","") or item.get("q","")
                            a = item.get("answer","") or item.get("a","")
                            if q and a: add_question(q,a,dm,item.get("difficulty",2),item.get("tags",[])); count += 1
                    except: st.error("JSON 格式错误")
                else:
                    blocks = re.split(r"\n(?=## |Q[:：]|\d+\.\s*)", content); q = None
                    for b in blocks:
                        b = b.strip()
                        if not b: continue
                        qm = re.match(r"(?:##\s*)?Q[:：]\s*(.+)", b)
                        if qm: q = qm.group(1); continue
                        if q and len(b) > 10: add_question(q,b,dm,2,[]); count += 1; q = None
                if count > 0: st.success(f"成功导入 {count} 道题目"); st.rerun()
                else: st.warning("未识别到有效题目")

        with st.expander("✏️ 手动添加"):
            with st.form("af"):
                qt = st.text_area("题目"); at = st.text_area("参考答案")
                c1,c2 = st.columns(2)
                with c1: mod = st.selectbox("模块", get_all_modules() or ["LLM基础"])
                with c2: diff = st.selectbox("难度", [1,2,3], format_func=lambda x:["初级","中级","高级"][x-1])
                tg = st.text_input("标签（逗号分隔）")
                if st.form_submit_button("添加"):
                    if qt.strip() and at.strip():
                        tags = [t.strip() for t in tg.split(",") if t.strip()]
                        add_question(qt.strip(), at.strip(), mod, diff, tags)
                        st.success("已添加"); st.rerun()
                    else: st.error("不能为空")

    # Render selected page
    if st.session_state.page == "interview":
        st.markdown("## 🤖 AI 面试陪练")
        st.caption("基于 Agentic RAG 的智能面试教练")
        interview_tab()
    else:
        review_tab()

    st.markdown("""<script>
    document.addEventListener('keydown', function(e) {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (!input || document.activeElement !== input) return;
        if (e.ctrlKey && e.key === 'p') { e.preventDefault(); input.value = '练习 '; input.dispatchEvent(new Event('input',{bubbles:true})); }
        if (e.ctrlKey && e.key === 'r') { e.preventDefault(); input.value = '报告'; input.dispatchEvent(new Event('input',{bubbles:true})); }
        if (e.ctrlKey && e.key === 'x') { e.preventDefault(); input.value = '重置'; input.dispatchEvent(new Event('input',{bubbles:true})); }
    });</script>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
