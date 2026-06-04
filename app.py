"""AI Interview Agent — Streamlit Web Interface."""
import streamlit as st
from agent.orchestrator import InterviewAgent


@st.cache_resource
def get_agent():
    return InterviewAgent()


def main():
    st.set_page_config(page_title="AI 面试陪练", page_icon="🎓")
    st.title("🎓 AI 面试陪练 Agent")
    st.caption("基于 Agentic RAG 的智能面试教练 · LLM基础 / Agent架构 / RAG / Prompt工程")

    agent = get_agent()

    # Sidebar controls
    with st.sidebar:
        st.subheader("快捷操作")
        if st.button("🔄 重置会话", use_container_width=True):
            agent.reset()
            st.session_state.messages = []
            st.rerun()
        if st.button("📊 生成报告", use_container_width=True):
            report = agent.generate_report()
            st.info(report)

    # Init message history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("输入'练习 LLM基础'开始出题，或直接输入问题..."):
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
                elif lower.startswith("回答") or lower.startswith("我的答案"):
                    answer = prompt.strip()
                    for prefix in ["回答", "我的答案", "answer"]:
                        if answer.startswith(prefix):
                            answer = answer[len(prefix):].strip()
                            break
                    resp = agent.evaluate_answer(answer)
                elif lower == "报告":
                    resp = agent.generate_report()
                elif lower == "重置":
                    agent.reset()
                    st.session_state.messages = []
                    resp = "已重置。输入'练习'开始。"
                else:
                    resp = agent.chat(prompt)

            st.markdown(resp)
            st.session_state.messages.append({"role": "assistant", "content": resp})


if __name__ == "__main__":
    main()
