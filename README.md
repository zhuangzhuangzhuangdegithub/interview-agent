# Interview Agent — AI 面试陪练

基于 Agentic RAG 的智能面试陪练系统。Agent 自主驱动检索、出题、追问、评分，帮助 AI 工程师备战技术面试。

## 技术栈

| 层级 | 组件 |
|------|------|
| LLM | DeepSeek API（Chat + Embedding） |
| Agent 框架 | LangChain（AgentExecutor + Memory + Tools） |
| 数据库 | PostgreSQL 15 + pgvector |
| 缓存 | Redis 7 |
| 前端 | Gradio |
| 微调 | Qwen2.5-7B + LLaMA-Factory + LoRA |
| 语言 | Python 3.11+ |

## 项目结构

```
agent/
├── agent/              # Agent 核心逻辑
│   ├── orchestrator.py # LangChain AgentExecutor
│   ├── router.py       # 意图分类
│   ├── evaluator.py    # 答案评分
│   └── memory.py       # Redis + LangChain Memory
├── tools/              # 工具层
│   ├── registry.py     # 工具注册
│   ├── search.py       # PGVector 检索
│   ├── practice.py     # 出题/追问
│   └── report.py       # 报告生成
├── data/               # 数据层
│   ├── schema.sql      # 数据库建表
│   └── seed.py         # 题库导入
├── prompts/            # Prompt 模板
│   └── system_prompt.txt
├── tests/              # 测试
├── app.py              # Gradio 入口
├── config.py           # 配置
├── requirements.txt    # 依赖
├── PROGRESS.md         # 开发进度
└── README.md
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动数据库
# PostgreSQL + Redis (Docker 或本地)

# 3. 初始化数据库
psql -U postgres -d interview_agent -f data/schema.sql

# 4. 导入题库
python data/seed.py

# 5. 配置 API Key
cp .env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY

# 6. 启动
python app.py
```

## 开发计划

详见 [PROGRESS.md](PROGRESS.md)
