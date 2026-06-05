"""Self-review flashcard mode."""
import streamlit as st
import random
from tools.search import search_questions, get_all_modules

st.set_page_config(page_title="自主刷题", page_icon="📝")
st.markdown("## 📝 自主刷题")
st.caption("按模块浏览题目，自己思考后点击查看答案 · 左侧导航可切换回 AI 陪练模式")

if "review_questions" not in st.session_state:
    st.session_state.review_questions = []
if "review_index" not in st.session_state:
    st.session_state.review_index = 0
if "show_answer" not in st.session_state:
    st.session_state.show_answer = False

col1, col2 = st.columns(2)
with col1:
    modules = get_all_modules()
    selected_module = st.selectbox("模块", ["全部"] + (modules if modules else []), key="rm")
with col2:
    selected_diff = st.selectbox("难度", ["全部", "初级", "中级", "高级"], key="rd")

if st.button("🔀 随机抽题", use_container_width=True):
    module = None if selected_module == "全部" else selected_module
    diff = None if selected_diff == "全部" else ["初级","中级","高级"].index(selected_diff)+1
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
    st.warning("题库为空，请先在侧边栏添加题目。")
else:
    idx = st.session_state.review_index
    st.progress((idx+1)/total, f"第 {idx+1} / {total} 题")
    q = questions[idx]

    with st.container(border=True):
        stars = "⭐" * q.get("difficulty", 2)
        st.caption(f"{q.get('module','')} · {stars}")
        st.markdown(f"### {q['question']}")

        if st.button("💡 查看答案" if not st.session_state.show_answer else "🙈 隐藏答案", use_container_width=True):
            st.session_state.show_answer = not st.session_state.show_answer
            st.rerun()
        if st.session_state.show_answer:
            st.divider()
            st.markdown(q.get("answer","暂无答案"))

    c1,c2,c3 = st.columns([1,2,1])
    with c1:
        if st.button("⬅ 上一题", disabled=idx==0, use_container_width=True):
            st.session_state.review_index = max(0, idx-1)
            st.session_state.show_answer = False
            st.rerun()
    with c2:
        st.caption(f"第 {idx+1} / {total} 题")
    with c3:
        if st.button("下一题 ➡", disabled=idx>=total-1, use_container_width=True):
            st.session_state.review_index = min(total-1, idx+1)
            st.session_state.show_answer = False
            st.rerun()

    st.markdown("""<script>
    document.addEventListener('keydown', function(e) {
        if (e.key==='ArrowLeft'){var b=document.querySelector('button:has-text("⬅")');if(b&&!b.disabled){e.preventDefault();b.click();}}
        if (e.key==='ArrowRight'){var b=document.querySelector('button:has-text("➡")');if(b&&!b.disabled){e.preventDefault();b.click();}}
        if (e.key===' '){e.preventDefault();var b=document.querySelector('button:has-text("💡"),button:has-text("🙈")');if(b)b.click();}
    });
    </script>""", unsafe_allow_html=True)
