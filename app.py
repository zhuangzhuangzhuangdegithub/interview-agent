"""AI Interview Agent — Dual mode with sidebar navigation."""
import streamlit as st
import json, re, random
from agent.orchestrator import InterviewAgent
from tools.search import add_question, get_all_modules, search_questions


def interview_tab():
    """AI 面试陪练"""
    if "messages" not in st.session_state: st.session_state.messages = []
    if "mode" not in st.session_state: st.session_state.mode = "idle"
    has_api = bool(st.session_state.get("user_api_key"))
    if has_api:
        if "agent" not in st.session_state:
            st.session_state.agent = InterviewAgent(
                api_key=st.session_state.get("user_api_key"),
                base_url=st.session_state.get("user_api_base"),
                model=st.session_state.get("user_api_model"),
            )
        agent = st.session_state.agent
    else:
        agent = None

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if not has_api:
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
                    parts = prompt.strip().split()
                    module = parts[1] if len(parts) > 1 else None
                    difficulty = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
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
            st.markdown(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.rerun()


def review_tab():
    """自主刷题"""
    st.markdown("## 📝 自主刷题")
    if "rq" not in st.session_state: st.session_state.rq = []
    if "ri" not in st.session_state: st.session_state.ri = 0
    if "sa" not in st.session_state: st.session_state.sa = False

    c1, c2 = st.columns(2)
    with c1:
        modules = get_all_modules()
        mod = st.selectbox("模块", ["全部"] + (modules if modules else []), key="rm")
    with c2:
        diff = st.selectbox("难度", ["全部", "初级", "中级", "高级"], key="rd")

    if st.button("🔀 随机抽题", use_container_width=True):
        m = None if mod == "全部" else mod
        d = None if diff == "全部" else ["初级","中级","高级"].index(diff)+1
        results = search_questions(module=m, difficulty=d, top_k=50)
        if results:
            random.shuffle(results)
            st.session_state.rq = results; st.session_state.ri = 0; st.session_state.sa = False
            st.rerun()

    if not st.session_state.rq:
        results = search_questions(top_k=50)
        if results:
            random.shuffle(results)
            st.session_state.rq = results
    questions = st.session_state.rq
    total = len(questions)
    if total == 0:
        st.warning("题库为空")
        return

    idx = st.session_state.ri
    st.progress((idx+1)/total, f"第 {idx+1} / {total} 题")
    q = questions[idx]

    with st.container(border=True):
        stars = "⭐" * q.get("difficulty", 2)
        st.caption(f"{q.get('module','')} · {stars}")
        st.markdown(f"### {q['question']}")
        btn_label = "💡 查看答案" if not st.session_state.sa else "🙈 隐藏答案"
        if st.button(btn_label, use_container_width=True):
            st.session_state.sa = not st.session_state.sa; st.rerun()
        if st.session_state.sa:
            st.divider(); st.markdown(q.get("answer","暂无答案"))

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

    with st.sidebar:
        st.subheader("⚙️ API 设置")
        with st.expander("配置 AI API"):
            api_key = st.text_input("API Key", value=st.session_state.get("user_api_key",""),
                                    placeholder="sk-...", type="password",
                                    help="支持 DeepSeek / OpenAI / 兼容接口")
            api_base = st.text_input("API Base URL", value=st.session_state.get("user_api_base","https://api.deepseek.com"))
            api_model = st.text_input("Model", value=st.session_state.get("user_api_model","deepseek-chat"))
            if st.button("保存设置", use_container_width=True):
                st.session_state.user_api_key = api_key
                st.session_state.user_api_base = api_base
                st.session_state.user_api_model = api_model
                if "agent" in st.session_state: del st.session_state.agent
                st.success("已保存")
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
            if has_api:
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
