"""AI Interview Agent — Streamlit Web Interface with dual modes."""
import streamlit as st
import json
import re
import random
from agent.orchestrator import InterviewAgent
from tools.search import add_question, get_all_modules, search_questions


def interview_mode():
    """AI 面试陪练模式"""
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


def review_mode():
    """自主刷题模式"""
    if "review_questions" not in st.session_state:
        st.session_state.review_questions = []
    if "review_index" not in st.session_state:
        st.session_state.review_index = 0
    if "show_answer" not in st.session_state:
        st.session_state.show_answer = False

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        modules = get_all_modules()
        selected_module = st.selectbox("模块", ["全部"] + (modules if modules else []), key="review_module")
    with col2:
        selected_diff = st.selectbox("难度", ["全部", "初级", "中级", "高级"], key="review_diff")

    if st.button("🔀 随机抽题", use_container_width=True):
        module = None if selected_module == "全部" else selected_module
        diff = None if selected_diff == "全部" else ["初级", "中级", "高级"].index(selected_diff) + 1
        results = search_questions(module=module, difficulty=diff, top_k=50)
        if results:
            random.shuffle(results)
            st.session_state.review_questions = results
            st.session_state.review_index = 0
            st.session_state.show_answer = False
            st.rerun()

    questions = st.session_state.review_questions
    if not questions:
        results = search_questions(top_k=50)
        if results:
            random.shuffle(results)
            st.session_state.review_questions = results
            questions = results

    total = len(questions)
    if total == 0:
        st.warning("题库为空")
        return

    idx = st.session_state.review_index
    st.progress((idx + 1) / total, f"第 {idx+1} / {total} 题")
    q = questions[idx]

    with st.container(border=True):
        stars = "⭐" * q.get("difficulty", 2)
        st.caption(f"{q.get('module', '')} · {stars}")
        st.markdown(f"### {q['question']}")

        if st.button("💡 查看答案" if not st.session_state.show_answer else "🙈 隐藏答案", use_container_width=True):
            st.session_state.show_answer = not st.session_state.show_answer
            st.rerun()

        if st.session_state.show_answer:
            st.divider()
            st.markdown(q.get("answer", "暂无答案"))

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("⬅ 上一题", disabled=idx == 0, use_container_width=True):
            st.session_state.review_index = max(0, idx - 1)
            st.session_state.show_answer = False
            st.rerun()
    with c2:
        st.caption(f"第 {idx+1} / {total} 题")
    with c3:
        if st.button("下一题 ➡", disabled=idx >= total - 1, use_container_width=True):
            st.session_state.review_index = min(total - 1, idx + 1)
            st.session_state.show_answer = False
            st.rerun()

    st.markdown("""<script>
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') { const b = document.querySelector('button:has-text("⬅")'); if(b&&!b.disabled){e.preventDefault();b.click();} }
        if (e.key === 'ArrowRight') { const b = document.querySelector('button:has-text("➡")'); if(b&&!b.disabled){e.preventDefault();b.click();} }
        if (e.key === ' ') { e.preventDefault(); const b = document.querySelector('button:has-text("💡"),button:has-text("🙈")'); if(b)b.click(); }
    });
    </script>""", unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="AI 面试陪练", page_icon="🎓")

    # Top navigation tabs
    tab1, tab2 = st.tabs(["🤖 AI 面试陪练", "📝 自主刷题"])
    with tab1:
        interview_mode()
    with tab2:
        review_mode()

    # Sidebar
    with st.sidebar:
        tab = st.session_state.get("_active_tab", 0)

        if tab == 0 or st.session_state.get("_review_mode") is None:
            # Interview mode sidebar
            if "mode" in st.session_state:
                mode_labels = {"idle": "等待指令", "waiting_answer": "等待你回答题目"}
                st.info(f"当前模式：{mode_labels.get(st.session_state.mode, '未知')}")

        st.subheader("⌨️ 快捷键")
        st.caption("输入框聚焦时：Ctrl+P 练习 | Ctrl+R 报告 | Ctrl+X 重置")

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

        st.subheader("快捷操作")
        if st.button("🔄 重置会话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.mode = "idle"
            st.rerun()
        if st.button("📊 生成报告", use_container_width=True):
            if "agent" in st.session_state:
                report = st.session_state.agent.generate_report()
                st.info(report)

        st.divider()
        st.subheader("➕ 添加题目")
        st.caption("支持 JSON / MD / TXT 格式。JSON：`[{\"question\":\"...\",\"answer\":\"...\",\"tags\":[...]}]`")

        uploaded_file = st.file_uploader("📁 一键导入文件", type=["json", "md", "txt"], key="file_upload")
        if uploaded_file is not None:
            default_module = st.selectbox("导入到模块", get_all_modules() or ["LLM基础"], key="import_module")
            if st.button("开始导入", use_container_width=True):
                content = uploaded_file.read().decode("utf-8")
                count = 0
                if uploaded_file.name.endswith(".json"):
                    try:
                        data = json.loads(content)
                        for item in data if isinstance(data, list) else [data]:
                            q = item.get("question", "") or item.get("q", "")
                            a = item.get("answer", "") or item.get("a", "")
                            if q and a:
                                add_question(q, a, default_module, item.get("difficulty", 2), item.get("tags", []))
                                count += 1
                    except json.JSONDecodeError:
                        st.error("JSON 格式错误")
                else:
                    blocks = re.split(r"\n(?=## |Q[:：]|\d+\.\s*)", content)
                    q = None
                    for block in blocks:
                        block = block.strip()
                        if not block:
                            continue
                        qm = re.match(r"(?:##\s*)?Q[:：]\s*(.+)", block)
                        if qm:
                            q = qm.group(1)
                            continue
                        if q and len(block) > 10:
                            add_question(q, block, default_module, 2, [])
                            count += 1
                            q = None
                if count > 0:
                    st.success(f"成功导入 {count} 道题目")
                    st.rerun()
                else:
                    st.warning("未识别到有效题目")

        with st.expander("✏️ 手动添加"):
            with st.form("add_question_form"):
                q_text = st.text_area("题目")
                a_text = st.text_area("参考答案")
                c1, c2 = st.columns(2)
                with c1:
                    all_mods = get_all_modules() or ["LLM基础", "Agent架构", "RAG与知识库"]
                    module = st.selectbox("模块", all_mods)
                with c2:
                    difficulty = st.selectbox("难度", [1, 2, 3], format_func=lambda x: ["初级", "中级", "高级"][x - 1])
                tags_str = st.text_input("标签（逗号分隔）")
                if st.form_submit_button("添加"):
                    if q_text.strip() and a_text.strip():
                        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                        qid = add_question(q_text.strip(), a_text.strip(), module, difficulty, tags)
                        st.success(f"已添加 #{qid}")
                        st.rerun()
                    else:
                        st.error("不能为空")

    # Keyboard shortcuts
    st.markdown("""<script>
    document.addEventListener('keydown', function(e) {
        var input = document.querySelector('[data-testid="stChatInput"] textarea');
        if (!input || document.activeElement !== input) return;
        if (e.ctrlKey && e.key === 'p') { e.preventDefault(); input.value = '练习 '; input.dispatchEvent(new Event('input', {bubbles: true})); }
        if (e.ctrlKey && e.key === 'r') { e.preventDefault(); input.value = '报告'; input.dispatchEvent(new Event('input', {bubbles: true})); }
        if (e.ctrlKey && e.key === 'x') { e.preventDefault(); input.value = '重置'; input.dispatchEvent(new Event('input', {bubbles: true})); }
    });
    </script>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
