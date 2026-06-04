"""Seed the database with LLM基础 interview questions."""
import psycopg2
import json
import numpy as np
from openai import OpenAI

# ── Config ──
DB_CONFIG = {
    "host": "localhost", "port": 5432, "dbname": "interview_agent",
    "user": "postgres", "password": "postgres"
}
LLM_CONFIG = {
    "api_key": "sk-placeholder",  # Replace with actual key
    "base_url": "https://api.deepseek.com",
}

# ── LLM基础 Questions ──
QUESTIONS = [
    {
        "question": "Transformer 中 Self-Attention 的 Q/K/V 矩阵各自承担什么角色？为什么需要多头注意力？",
        "answer": "Q 表达'我在找什么'，K 表达'我能提供什么'，V 表达'我的实际内容'。多头注意力让模型在不同语义子空间中并行关注不同模式。Attention(Q,K,V)=softmax(QK^T/√d_k)×V。除以√d_k 防止点积过大导致 softmax 梯度消失。单头只能学习一种注意力模式，多头让模型同时关注句法、语义、指代、长距离依赖等不同维度。",
        "module": "LLM基础", "difficulty": 1,
        "tags": ["Transformer", "Attention", "基础原理"]
    },
    {
        "question": "大模型的幻觉是怎么产生的？从训练数据和推理机制两个角度解释",
        "answer": "幻觉是概率模型在知识边界外的合理行为——模型本质上在'猜下一个 token'而非'查数据库'。训练数据角度：数据中存在矛盾、过时、虚构信息；低频实体和长尾知识曝光不足。推理机制角度：自回归生成的每个 token 基于概率分布，采样引入随机性；错误一旦产生会级联放大；模型没有'我不知道'的内置机制。工程应对：RAG注入外部知识、限制temperature、用structured output。",
        "module": "LLM基础", "difficulty": 1,
        "tags": ["幻觉", "训练数据", "推理机制"]
    },
    {
        "question": "Context Window 是什么？增大上下文窗口会遇到哪些工程挑战？",
        "answer": "上下文窗口是模型一次能'看到'的最大 token 数。工程挑战：1)计算复杂度O(n²)，128K上下文需要处理160亿对注意力计算；2)KV Cache随序列长度线性增长，显存压力大；3)RoPE位置编码需调整base frequency；4)'Lost in the Middle'效应，中段信息利用效率低；5)Prefill阶段耗时显著增加。优化方向：FlashAttention、RingAttention、滑动窗口、KV Cache量化、稀疏注意力。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["上下文窗口", "注意力复杂度", "工程挑战"]
    },
    {
        "question": "Temperature 和 Top-P 有什么区别？代码生成和创意写作分别怎么调？",
        "answer": "Temperature控制分布的'平滑度'，Top-P控制候选集的'宽度'。Temperature在softmax之前除以T：T<1分布更尖锐确定性更强，T>1分布更平缓随机性更强。Top-P按概率从高到低累加，截断累积概率超过P之后的token。代码生成建议T=0~0.3，创意写作建议T=0.7~1.0。通常搭配使用：先调T控制整体随机度，再调Top-P裁剪尾部噪声。误区：T=0不等于'最准确'，可能产生重复循环。",
        "module": "LLM基础", "difficulty": 1,
        "tags": ["采样策略", "Temperature", "Top-P"]
    },
    {
        "question": "大模型的 System Prompt 在技术上是如何实现的？为什么有时候模型会忽视 System Prompt？",
        "answer": "System Prompt在大多数实现中只是拼在对话开头的一段特殊标记文本，没有独立的参数通道。模型容易'忽视'它是因为长对话中早期token的注意力权重被稀释。原因：1)长对话中后面消息占据主要注意力，system prompt在序列开头信息衰减；2)后文遇到冲突指令时跟随最近指令；3)训练数据中system prompt样本分布不均。工程建议：重要约束同时放在system prompt和最近的user prompt中；定期重复关键指令。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["System Prompt", "指令跟随", "注意力机制"]
    },
    {
        "question": "Token 和 Word 的区别是什么？为什么中文的 tokenization 比英文更吃亏？",
        "answer": "Token是模型处理的最小语义单元，不等于单词。中文因字符集大、常用词多，BPE分词后token数更多。英文一个单词约1-2个token，中文一个词如'人工智能'可能3-4个token。同样语义内容中文token数通常是英文的1.5-2.5倍。原因：BPE基于语料统计合并高频字符对，英文语料占比大压缩效率高；中文字符集有数万个字符远多于英文26个字母。缓解：选择中文优化tokenizer的模型如Qwen系列。",
        "module": "LLM基础", "difficulty": 1,
        "tags": ["Tokenization", "BPE", "多语言"]
    },
    {
        "question": "为什么 LLM 在长上下文中间位置的 recall 准确率最低？如何缓解？",
        "answer": "这个现象叫'Lost in the Middle'。模型对长文本开头和结尾的信息召回率高，中间部分显著下降。原因：训练数据的结构偏差导致模型学到位置偏好；decoder-only架构对中段位置建模天然弱于两端；中间位置token在注意力计算中既没有首因效应也没有近因效应。缓解策略：对检索到的chunk重排序，最重要放开头或结尾；使用reranker；分治策略长文档分段总结；用structured prompt标注各段落边界和重要性。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["Lost in the Middle", "长上下文", "注意力"]
    },
    {
        "question": "如何给一个陌生的大模型做能力评估？设计一个最小可行的评测流程",
        "answer": "不要只看榜单分数。最小可行评测应覆盖五大维度：1)指令跟随测试~20题，给定复杂约束检查格式和内容合规率；2)知识边界探测，混合已知事实、过时信息、虚构信息，评估模型能否说'不知道'；3)推理能力用学科选择题+逻辑推理题对比参考答案准确率；4)延迟与成本记录TTFT、TPS、单次调用成本；5)幻觉率用FactScore或人工抽样统计声称性错误比例。常见误区：只测MMLU/LMSYS榜单——这些是通用能力不代表领域表现。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["模型评测", "选型", "基准测试"]
    },
    {
        "question": "为什么 GPT-4 级别的模型能遵循复杂指令，而小模型往往不行？核心差异在哪？",
        "answer": "指令跟随是'涌现能力'——在参数规模达到一定阈值后才显著出现。核心差异：大模型的注意力头更多可以并行处理多个约束维度；表征空间更大，指令中细微差别能被区分；训练阶段经历更多RLHF/DPO对齐；上下文学习能力更强。实际判断标准：如果模型在10次测试中有7次以上无法完全遵循3条以上约束，它的指令跟随能力就不够生产使用。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["指令跟随", "模型规模", "涌现能力"]
    },
    {
        "question": "在模型选型中，如何权衡 API 调用 vs 本地部署？给出决策框架",
        "answer": "核心变量是调用量、延迟要求、数据安全、定制需求、预算。决策框架：1)数据安全涉密场景必须本地部署；2)调用量日均<1K次用API最经济，1K-10K考虑混合，>10K本地部署成本优势显现；3)实时场景(<500ms)本地部署或EDGE推理，离线批处理用API异步；4)需领域微调选开源模型+LoRA+本地部署；5)API成本=调用量×单价，本地部署成本=GPU服务器+运维人力。常见误区：看到API单价就做决策，忽略了长尾token消耗、重试成本、并发峰值。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["模型选型", "成本", "部署策略"]
    },
    {
        "question": "Transformer 中的位置编码解决了什么问题？RoPE 相比 Sinusoidal 有什么优势？",
        "answer": "位置编码让Self-Attention获得序列顺序信息。RoPE通过旋转矩阵将位置信息编码进QK内积，实现了相对位置编码的外推能力。Sinusoidal局限：绝对位置编码，训练长度固定后难以外推。RoPE优势：向量内积只依赖相对位置，天然支持相对位置编码；可通过调整base frequency如NTK-Aware Scaling扩展上下文窗口；几乎所有主流开源模型Llama、Qwen、Mistral都采用。为什么能外推？因为它是相对位置编码的隐式实现，修改base frequency相当于压缩旋转速度。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["位置编码", "RoPE", "Transformer"]
    },
    {
        "question": "为什么大模型有时会重复输出或陷入循环？怎么定位和解决？",
        "answer": "重复循环通常由采样策略不当或prompt设计问题引起，根因是概率分布过于尖锐导致模型困在局部最优。定位方法：检查temperature是否过低；检查repetition_penalty是否设置；查看prompt是否有模式诱导。解决方案：适当提高temperature(0.3-0.7)；设置repetition_penalty=1.05-1.1；在prompt末尾添加'请给出多样化的回答'；使用frequency_penalty或presence_penalty；设置合理的stop_sequence作为兜底。代码生成场景不建议用高temperature，用beam search或greedy decoding+语法约束。",
        "module": "LLM基础", "difficulty": 1,
        "tags": ["重复生成", "解码策略", "故障排查"]
    },
    {
        "question": "LLM 的推理延迟由哪些因素决定？如何优化？",
        "answer": "推理延迟=Prefill时间+Decode时间。Prefill瓶颈在计算，Decode瓶颈在显存带宽。延迟构成：Prefill处理所有输入token计算attention；Decode自回归逐个生成，每个token需加载全部KV Cache；网络延迟额外增加50-500ms RTT。优化策略：减少输入token；使用FlashAttention减少IO开销；KV Cache量化(INT8/INT4)；批处理continuous batching；投机解码用小模型生成候选大模型验证；流式输出不减少总时间但改善用户体验。Decode阶段瓶颈在显存带宽因为每个token只做少量计算但要读取全部KV Cache。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["推理优化", "延迟", "性能"]
    },
    {
        "question": "预训练和对齐分别解决了什么问题？为什么需要 SFT + RLHF 两步？",
        "answer": "预训练教会模型'世界知识'，SFT教会模型'对话格式'，RLHF教会模型'人类偏好'。两步对齐是因为单靠SFT无法让模型学会在多个合格回答中选最好的那个。预训练：目标NTP，输入海量互联网文本，产出Base Model知道很多但不会聊天。SFT：目标模仿高质量对话数据，产出会对话但可能输出不安全/低质量内容。RLHF：目标最大化人类偏好的奖励信号，同一prompt可能有多个正确回答SFT无法区分好坏。DPO作为替代方案直接从偏好对中学习无需训练奖励模型。不能跳过SFT直接RLHF因为Base Model没有对话能力。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["训练流程", "SFT", "RLHF"]
    },
    {
        "question": "如何判断一个 LLM 的知识边界？怎么区分'不知道'和'知道但答错了'？",
        "answer": "单个回答无法区分。需通过多次采样+一致性检验+概率分析来探测知识边界。区分方法：1)多次采样一致性对同一问题采样5-10次(T=0.5)，答案高度一致→模型知道，答案分散→模型在猜，一致且错误→系统性错误认知；2)Token概率分析检查关键实体token输出概率，高概率+正确→知道，高概率+错误→模型错误认知，低概率→模型不确定；3)提示词探测分别用不同prompt对比；4)内部一致性从不同角度问同一个事实交叉验证。工程应用：RAG系统中多次采样不一致触发检索兜底。",
        "module": "LLM基础", "difficulty": 3,
        "tags": ["知识边界", "置信度", "可解释性"]
    },
    {
        "question": "为什么开源模型在某些 benchmark 上超过闭源模型但实际体验差距很大？",
        "answer": "Benchmark分数和真实体验之间存在'评测-部署鸿沟'。原因：1)数据污染-开源模型训练数据可能包含benchmark测试集；2)评测维度单一-Benchmark侧重知识和推理但真实对话需要语境理解、安全性、格式遵从、多轮连贯性；3)长尾场景-闭源模型在99%常见场景和1%边缘场景都有投入，开源模型往往只在80%场景表现好；4)RLHF质量-人类的偏好标注质量和反馈循环深度直接影响好用程度；5)工程优化-闭源模型有专门推理优化、缓存策略、错误处理。工程建议：用自己的100道业务场景题做A/B测试。",
        "module": "LLM基础", "difficulty": 3,
        "tags": ["模型评测", "Benchmark", "开闭源对比"]
    },
    {
        "question": "大模型的涌现能力是什么？为什么小模型没有？",
        "answer": "涌现能力(Emergent Abilities)是指模型参数达到一定规模后突然出现的能力——在小模型中几乎不存在(随机水平)，跨过阈值后显著提升。典型如思维链推理、多步指令跟随。为什么小模型没有：复杂任务需要多个子能力组合，小模型的'能力矩阵'有空缺；注意力头数量不足无法并行建模多个语义维度；表征空间维度不够不同概念之间重叠严重。争议：部分研究者认为涌现是评测指标的非线性产物。对工程师意义：如果某个任务用7B完全做不了，换13B也不行，直接试70B+或闭源模型。",
        "module": "LLM基础", "difficulty": 3,
        "tags": ["涌现能力", "规模定律", "能力边界"]
    },
    {
        "question": "为什么 LLM 做数学题容易出错？是推理问题还是知识问题？",
        "answer": "根本原因是tokenization将数字拆分为不固定长度的子词，破坏了数值的'原子性'和位值概念。叠加自回归的单向生成特性，LLM在做多步数学推理时缺乏全局校验能力。深层原因：数字'123'可能被分为'12'+'3'或'1'+'23'；自回归限制只能从左到右计算不能回退修改；训练数据中数学推理样本占比低且大部分是直接答案；注意力机制适合模式匹配不适合精确符号计算。缓解策略：用code interpreter/tool calling让模型写Python计算；用chain-of-thought分步推理；使用专门的math-specialized模型。",
        "module": "LLM基础", "difficulty": 3,
        "tags": ["数学推理", "Tokenization", "推理局限"]
    },
    {
        "question": "如果你从零搭建一个 LLM 驱动的产品，如何做模型选型和架构设计？",
        "answer": "不要一上来就选模型。先定义产品需求→确定质量/延迟/成本约束→设计评估体系→再选模型。用'路由+降级'架构保证可用性。设计框架：1)需求分析-首token延迟要求、准确率要求、日调用量预估、是否需多模态；2)分层策略-简单任务(分类/提取)用小模型本地部署(1-7B)，中等任务(摘要/翻译)用中等模型API(13-70B)，复杂任务(推理/代码生成)用顶级模型API；3)模型路由-根据任务复杂度自动选择模型降低平均成本；4)降级策略-主模型不可用时自动切换备用；5)评估闭环-在线A/B测试+用户反馈持续优化路由策略。为什么不能只用一个模型？成本效益比。",
        "module": "LLM基础", "difficulty": 3,
        "tags": ["系统设计", "模型选型", "架构"]
    },
    {
        "question": "多轮对话中为什么模型会忘记之前说过的话？技术原因和解决方案？",
        "answer": "模型没有'记忆'，它只是每次把整个对话历史都重新输入。本质上是上下文窗口限制和注意力衰减导致早期内容被稀释。技术原因：对话长度超过上下文窗口时最早消息被截断；即使未截断长上下文中早期token注意力权重随距离衰减；话题漂移后模型倾向于关注最近语义语境。解决方案：滑动窗口保留最近N轮+摘要前文；自动摘要用LLM定期压缩历史对话为结构化摘要；关键信息提取人名、数字、决定、偏好等事实存入结构化存储；RAG式记忆将历史对话向量化存储需要时检索；在system prompt中重复关键约束和上下文。",
        "module": "LLM基础", "difficulty": 2,
        "tags": ["多轮对话", "上下文管理", "记忆"]
    },
]


def seed(api_key: str = None):
    """Import questions into database."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Clear existing
    cur.execute("DELETE FROM practice_records WHERE 1=1")
    cur.execute("DELETE FROM questions WHERE 1=1")

    # Insert questions
    for i, q in enumerate(QUESTIONS):
        cur.execute(
            """INSERT INTO questions (question, answer, module, difficulty, tags)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (q["question"], q["answer"], q["module"], q["difficulty"], q["tags"])
        )
        q_id = cur.fetchone()[0]
        # Generate simple embedding (placeholder: random projection)
        emb = np.random.randn(1536).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        cur.execute(
            "UPDATE questions SET embedding = %s WHERE id = %s",
            (json.dumps(emb.tolist()), q_id)
        )

    conn.commit()
    cur.execute("SELECT count(*) FROM questions")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"Seeded {count} questions")

if __name__ == "__main__":
    seed()
