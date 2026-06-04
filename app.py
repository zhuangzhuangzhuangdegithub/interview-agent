"""Gradio web interface for Interview Agent — Gradio 6.0 compatible."""
import gradio as gr
from agent.orchestrator import InterviewAgent

agent = InterviewAgent()


def respond(message, history):
    """Handle chat messages. history is list of {"role":"user/assistant","content":"..."}"""
    if not message.strip():
        return "", history

    lower = message.strip().lower()

    if lower.startswith("练习") or lower.startswith("开始"):
        parts = message.strip().split()
        module = parts[1] if len(parts) > 1 else None
        difficulty = None
        if len(parts) > 2 and parts[2].isdigit():
            difficulty = int(parts[2])
        resp = agent.start_practice(module=module, difficulty=difficulty)

    elif lower.startswith("回答") or lower.startswith("我的答案"):
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

    # Gradio 6.0: history is list of dicts, not tuples
    new_history = list(history) if history else []
    new_history.append({"role": "user", "content": message})
    new_history.append({"role": "assistant", "content": resp})
    return "", new_history


with gr.Blocks(title="AI 面试陪练") as demo:
    gr.Markdown("# AI 面试陪练 Agent")
    gr.Markdown("基于 Agentic RAG 的智能面试教练。LLM基础 / Agent架构 / RAG / Prompt工程")

    chatbot = gr.Chatbot(height=500, type="messages")
    msg = gr.Textbox(placeholder="输入'练习 LLM基础'开始出题...", label="")

    with gr.Row():
        gr.Examples(["练习 LLM基础", "练习 Agent架构 2", "报告", "重置"], inputs=msg)

    msg.submit(respond, [msg, chatbot], [msg, chatbot])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
