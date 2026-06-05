"""Self-review flashcard mode — browse questions and reveal answers."""
import streamlit as st
import random
from tools.search import search_questions, get_all_modules

st.set_page_config(page_title="自主刷题", page_icon="📝")
st.title("📝 自主刷题模式")
st.caption("按模块浏览题目，自己思考后点击查看答案")

# Init session state
if "review_index" not in st.session_state:
    st.session_state.review_index = 0
if "review_questions" not in st.session_state:
    st.session_state.review_questions = []
if "show_answer" not in st.session_state:
    st.session_state.show_answer = False

# Sidebar filters
with st.sidebar:
    st.subheader("筛选条件")
    modules = get_all_modules()
    selected_module = st.selectbox("模块", ["全部"] + (modules if modules else []))
    selected_diff = st.selectbox("难度", ["全部", "初级", "中级", "高级"])

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

    st.divider()
    st.subheader("⌨️ 快捷键")
    st.caption("← 上一题 | → 下一题 | Space 查看答案")

# Load questions if not loaded
if not st.session_state.review_questions:
    results = search_questions(top_k=50)
    if results:
        random.shuffle(results)
        st.session_state.review_questions = results

questions = st.session_state.review_questions
total = len(questions)
idx = st.session_state.review_index

if total == 0:
    st.warning("题库为空，请先添加题目。")
else:
    # Progress
    progress = (idx + 1) / total
    st.progress(progress, f"第 {idx+1} / {total} 题")

    q = questions[idx]

    # Question card
    with st.container(border=True):
        st.subheader(f"📝 题目")
        stars = "⭐" * q.get("difficulty", 2)
        module = q.get("module", "")
        st.caption(f"{module} · {stars}")
        st.markdown(f"### {q['question']}")

        # Answer toggle
        if st.button("💡 查看答案" if not st.session_state.show_answer else "🙈 隐藏答案", use_container_width=True):
            st.session_state.show_answer = not st.session_state.show_answer
            st.rerun()

        if st.session_state.show_answer:
            st.divider()
            st.subheader("📖 参考答案")
            st.markdown(q.get("answer", "暂无答案"))

    # Navigation
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅ 上一题", disabled=idx == 0, use_container_width=True):
            st.session_state.review_index = max(0, idx - 1)
            st.session_state.show_answer = False
            st.rerun()
    with col2:
        st.caption(f"第 {idx+1} / {total} 题")
    with col3:
        if st.button("下一题 ➡", disabled=idx >= total - 1, use_container_width=True):
            st.session_state.review_index = min(total - 1, idx + 1)
            st.session_state.show_answer = False
            st.rerun()

    # Keyboard shortcuts
    st.markdown("""
    <script>
    document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowLeft') {
            const btn = document.querySelector('button:has-text("⬅")');
            if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
        }
        if (e.key === 'ArrowRight') {
            const btn = document.querySelector('button:has-text("➡")');
            if (btn && !btn.disabled) { e.preventDefault(); btn.click(); }
        }
        if (e.key === ' ') {
            e.preventDefault();
            const btn = document.querySelector('button:has-text("💡"), button:has-text("🙈")');
            if (btn) btn.click();
        }
    });
    </script>
    """, unsafe_allow_html=True)
