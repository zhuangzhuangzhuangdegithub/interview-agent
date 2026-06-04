"""Gradio web interface for Interview Agent."""
import gradio as gr
from agent.orchestrator import InterviewAgent

agent = InterviewAgent()


def respond(message, history):
    """Handle chat messages."""
    if not message.strip():
        return "", history

    lower = message.strip().lower()

    if lower.startswith("练习") or lower.startswith("开始"):
        # Parse: "练习 RAG 中级" or just "练习"
        parts = message.strip().split()
        module = parts[1] if len(parts) > 1 else None
        difficulty = None
        if len(parts) > 2 and parts[2].isdigit():
            difficulty = int(parts[2])
        resp = agent.start_practice(module=module, difficulty=difficulty)

    elif lower.startswith("回答") or lower.startswith("我的答案"):
        # Strip the command prefix
        answer = message.strip()
        for prefix in ["回答", "我的答案", "answer"]:
            if answer.startswith(prefix):
                answer = answer[len(prefix):].strip()
                break
        resp = agent.evaluate_answer(answer)

    elif lower == "报告":
        resp = agent.generate_report()

    elif lower == "重置":
        agent.reset()
        resp = "已重置会话。输入'练习'开始新的练习。"

    else:
        resp = agent.chat(message)

    history.append((message, resp))
    return "", history


with gr.Blocks(title="AI 面试陪练", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎓 AI 面试陪练 Agent")
    gr.Markdown("基于 Agentic RAG 的智能面试教练。支持 LLM基础 / Agent架构 / RAG / Prompt工程 等模块。")

    chatbot = gr.Chatbot(height=500, placeholder="<p style='color:#888'>输入'练习 LLM基础'开始出题，或直接提问...</p>")
    msg = gr.Textbox(placeholder="输入消息...", label="")

    with gr.Row():
        gr.Examples(["练习 LLM基础", "练习 Agent架构 2", "报告", "重置"], inputs=msg)
        gr.ClearButton([msg, chatbot])

    msg.submit(respond, [msg, chatbot], [msg, chatbot])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
