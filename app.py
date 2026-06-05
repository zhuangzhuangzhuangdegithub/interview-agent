"""AI Interview Agent — Streamlit Web Interface."""
import streamlit as st
import json
import re
from agent.orchestrator import InterviewAgent
from tools.search import add_question, get_all_modules, search_questions


def main():
    st.set_page_config(page_title="AI 面试陪练", page_icon="🤖")

    # Header
    st.markdown("## 🤖 AI 面试陪练")
    st.caption("基于 Agentic RAG 的智能面试教练 · 左侧导航可切换刷题模式")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "mode" not in st.session_state:
        st.session_state.mode = "idle"
    if "agent" not in st.session_state:
        st.session_state.agent = InterviewAgent()
    agent = st.session_state.agent

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    placeholder = "请输入 练习（模块名称） 将会开始出题，如：练习 Agent架构"
    if st.session_state.mode == "waiting_answer":
        placeholder = "输入你的回答，Enter 提交评分"

    if prompt := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                lower = prompt.strip().lower()
                if lower.startswith("练习") or lower.startswith("开始"):
                    parts = prompt.strip().split()
                    module = parts[1] if len(parts) > 1 else None
                    difficulty = None
                    if len(parts) > 2 and parts[2].isdigit():
                        difficulty = int(parts[2])
                    resp = agent.start_practice(module=module, difficulty=difficulty)
                    st.session_state.mode = "waiting_answer"
                elif st.session_state.mode == "waiting_answer":
                    resp = agent.evaluate_answer(prompt)
                    st.session_state.mode = "idle"
                elif lower in ("报告", "report"):
                    resp = agent.generate_report()
                elif lower in ("重置", "reset"):
                    agent.reset()
                    st.session_state.messages = []
                    st.session_state.mode = "idle"
                    resp = "已重置。输入'练习'开始。"
                else:
                    resp = agent.chat(prompt)
            st.markdown(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.rerun()

    with st.sidebar:
        st.subheader("📌 导航")
        st.info("🤖 AI 面试陪练 — 当前页面")
        st.info("📝 自主刷题 — 点击左侧导航切换")

        if "mode" in st.session_state:
            mode_labels = {"idle": "等待指令", "waiting_answer": "等待你回答题目"}
            st.subheader("当前状态")
            st.info(mode_labels.get(st.session_state.mode, "未知"))

        st.subheader("⌨️ 快捷键")
        st.caption("Ctrl+P 练习 | Ctrl+R 报告 | Ctrl+X 重置")

        # Module stats
        try:
            modules = get_all_modules()
            total = 0; lines = []
            for m in modules:
                results = search_questions(module=m, top_k=1000)
                count = len(results); total += count
                lines.append(f"· {m}：{count} 题")
            with st.expander(f"📚 题库统计（共 {total} 题）"):
                for line in lines:
                    st.caption(line)
        except Exception:
            pass

        st.subheader("快捷操作")
        if st.button("🔄 重置会话", use_container_width=True):
            agent.reset()
            st.session_state.messages = []
            st.session_state.mode = "idle"
            st.rerun()
        if st.button("📊 生成报告", use_container_width=True):
            st.info(agent.generate_report())

        st.divider()
        st.subheader("➕ 添加题目")
        st.caption("JSON：`[{\"question\":\"...\",\"answer\":\"...\",\"tags\":[...]}]`")
        uploaded_file = st.file_uploader("📁 一键导入文件", type=["json", "md", "txt"])
        if uploaded_file is not None:
            default_module = st.selectbox("导入到模块", get_all_modules() or ["LLM基础"], key="import_module")
            if st.button("开始导入", use_container_width=True):
                content = uploaded_file.read().decode("utf-8")
                count = 0
                if uploaded_file.name.endswith(".json"):
                    try:
                        data = json.loads(content)
                        for item in data if isinstance(data, list) else [data]:
                            q = item.get("question","") or item.get("q","")
                            a = item.get("answer","") or item.get("a","")
                            if q and a:
                                add_question(q, a, default_module, item.get("difficulty",2), item.get("tags",[]))
                                count += 1
                    except json.JSONDecodeError:
                        st.error("JSON 格式错误")
                else:
                    blocks = re.split(r"\n(?=## |Q[:：]|\d+\.\s*)", content)
                    q = None
                    for block in blocks:
                        block = block.strip()
                        if not block: continue
                        qm = re.match(r"(?:##\s*)?Q[:：]\s*(.+)", block)
                        if qm: q = qm.group(1); continue
                        if q and len(block) > 10:
                            add_question(q, block, default_module, 2, [])
                            count += 1; q = None
                if count > 0:
                    st.success(f"成功导入 {count} 道题目")
                    st.rerun()
                else:
                    st.warning("未识别到有效题目")

        with st.expander("✏️ 手动添加"):
            with st.form("add_form"):
                q_text = st.text_area("题目")
                a_text = st.text_area("参考答案")
                c1, c2 = st.columns(2)
                with c1:
                    module = st.selectbox("模块", get_all_modules() or ["LLM基础"])
                with c2:
                    difficulty = st.selectbox("难度", [1,2,3], format_func=lambda x: ["初级","中级","高级"][x-1])
                tags_str = st.text_input("标签（逗号分隔）")
                if st.form_submit_button("添加"):
                    if q_text.strip() and a_text.strip():
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        qid = add_question(q_text.strip(), a_text.strip(), module, difficulty, tags)
                        st.success(f"已添加 #{qid}")
                        st.rerun()
                    else:
                        st.error("不能为空")

    st.markdown("""<script>
    document.addEventListener('keydown', function(e) {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (!input || document.activeElement !== input) return;
        if (e.ctrlKey && e.key === 'p') { e.preventDefault(); input.value = '练习 '; input.dispatchEvent(new Event('input',{bubbles:true})); }
        if (e.ctrlKey && e.key === 'r') { e.preventDefault(); input.value = '报告'; input.dispatchEvent(new Event('input',{bubbles:true})); }
        if (e.ctrlKey && e.key === 'x') { e.preventDefault(); input.value = '重置'; input.dispatchEvent(new Event('input',{bubbles:true})); }
    });
    </script>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
