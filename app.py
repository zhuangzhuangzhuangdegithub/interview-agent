"""AI Interview Agent — Streamlit Web Interface."""
import streamlit as st
from agent.orchestrator import InterviewAgent
from tools.search import add_question, get_all_modules, search_questions


def main():
    st.set_page_config(page_title="AI 面试陪练", page_icon="🎓")
    st.title("🎓 AI 面试陪练 Agent")
    st.caption("基于 Agentic RAG 的智能面试教练 · LLM基础 / Agent架构 / RAG / Prompt工程")

    # Keyboard shortcuts via JS injection
    st.markdown("""
    <script>
    document.addEventListener('keydown', function(e) {
        const input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (!input || document.activeElement !== input) return;
        if (e.ctrlKey && e.key === 'p') { e.preventDefault(); input.value = '练习 '; input.dispatchEvent(new Event('input', {bubbles: true})); }
        if (e.ctrlKey && e.key === 'r') { e.preventDefault(); input.value = '报告'; input.dispatchEvent(new Event('input', {bubbles: true})); }
        if (e.ctrlKey && e.key === 'x') { e.preventDefault(); input.value = '重置'; input.dispatchEvent(new Event('input', {bubbles: true})); }
    });
    </script>
    """, unsafe_allow_html=True)

    # Init session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "mode" not in st.session_state:
        st.session_state.mode = "idle"
    if "agent" not in st.session_state:
        st.session_state.agent = InterviewAgent()

    agent = st.session_state.agent

    # Display history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
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
                    resp = "已重置会话。输入'练习'开始。"

                else:
                    resp = agent.chat(prompt)

            st.markdown(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})
            st.rerun()  # Force rerun to update sidebar state immediately

    # Sidebar at bottom for correct state display
    with st.sidebar:
        st.subheader("状态")
        mode_labels = {"idle": "等待指令", "waiting_answer": "等待你回答题目"}
        st.info(f"当前模式：{mode_labels.get(st.session_state.mode, '未知')}")

        # Module stats
        try:
            modules = get_all_modules()
            total = 0
            lines = []
            for m in modules:
                results = search_questions(module=m, top_k=1000)
                count = len(results)
                total += count
                lines.append(f"· {m}：{count} 题")
            with st.expander(f"📚 题库统计（共 {total} 题）"):
                for line in lines:
                    st.caption(line)
        except Exception:
            pass

        st.subheader("⌨️ 快捷键")
        st.caption("输入框聚焦时：Ctrl+P 练习 | Ctrl+R 报告 | Ctrl+X 重置")

        st.subheader("快捷操作")
        if st.button("🔄 重置会话", use_container_width=True):
            agent.reset()
            st.session_state.messages = []
            st.session_state.mode = "idle"
            st.rerun()
        if st.button("📊 生成报告", use_container_width=True):
            report = agent.generate_report()
            st.info(report)

        st.divider()
        st.subheader("➕ 添加自定义题目")
        with st.expander("展开添加"):
            with st.form("add_question_form"):
                q_text = st.text_area("题目", placeholder="输入面试题目...")
                a_text = st.text_area("参考答案", placeholder="输入参考答案...")
                col1, col2 = st.columns(2)
                with col1:
                    existing_modules = get_all_modules()
                    default_modules = ["LLM基础", "Agent架构", "RAG与知识库", "Prompt工程", "工具调用与工作流", "微调与部署"]
                    all_modules = existing_modules if existing_modules else default_modules
                    module = st.selectbox("模块", all_modules)
                with col2:
                    difficulty = st.selectbox("难度", [1, 2, 3], format_func=lambda x: ["初级", "中级", "高级"][x-1])
                tags_str = st.text_input("标签（逗号分隔）", placeholder="如: Transformer, Attention")
                if st.form_submit_button("添加题目", use_container_width=True):
                    if q_text.strip() and a_text.strip():
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        qid = add_question(q_text.strip(), a_text.strip(), module, difficulty, tags)
                        st.success(f"已添加题目 #{qid} 到 {module} 模块")
                        st.rerun()
                    else:
                        st.error("题目和答案不能为空")


if __name__ == "__main__":
    main()
