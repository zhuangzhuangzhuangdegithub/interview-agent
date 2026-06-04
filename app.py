"""AI Interview Agent — Streamlit Web Interface."""
import streamlit as st
from agent.orchestrator import InterviewAgent


def main():
    st.set_page_config(page_title="AI 面试陪练", page_icon="🎓")
    st.title("🎓 AI 面试陪练 Agent")
    st.caption("基于 Agentic RAG 的智能面试教练 · LLM基础 / Agent架构 / RAG / Prompt工程")

    agent = InterviewAgent()

    # Init session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "mode" not in st.session_state:
        st.session_state.mode = "idle"  # idle | waiting_answer

    # Sidebar
    with st.sidebar:
        st.subheader("状态")
        mode_labels = {"idle": "等待指令", "waiting_answer": "等待你回答题目"}
        st.info(f"当前模式：{mode_labels.get(st.session_state.mode, '未知')}")

        st.subheader("快捷操作")
        if st.button("🔄 重置会话", use_container_width=True):
            agent.reset()
            st.session_state.messages = []
            st.session_state.mode = "idle"
            st.rerun()
        if st.button("📊 生成报告", use_container_width=True):
            report = agent.generate_report()
            st.info(report)

    # Display history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    placeholder = "输入'练习 LLM基础'开始出题"
    if st.session_state.mode == "waiting_answer":
        placeholder = "输入你的回答..."

    if prompt := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                lower = prompt.strip().lower()

                # Route based on current mode AND message content
                if lower.startswith("练习") or lower.startswith("开始"):
                    parts = prompt.strip().split()
                    module = parts[1] if len(parts) > 1 else None
                    difficulty = None
                    if len(parts) > 2 and parts[2].isdigit():
                        difficulty = int(parts[2])
                    resp = agent.start_practice(module=module, difficulty=difficulty)
                    st.session_state.mode = "waiting_answer"

                elif st.session_state.mode == "waiting_answer":
                    # User is answering the current question
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


if __name__ == "__main__":
    main()
