"""Seed additional questions: Agent架构, RAG, Prompt工程, 工具调用."""
import psycopg2
import json
import numpy as np
import sys; sys.path.insert(0, "D:/whu/大三下/练习/agent")

QUESTIONS = [
    # ==== Agent架构 (15题) ====
    ("Agent 的核心架构包含哪几个关键模块？每个模块的职责是什么？","Agent 核心架构包含五大模块：1)规划模块(Planner)：将复杂任务分解为可执行的子步骤；2)记忆模块(Memory)：短期记忆存当前上下文，长期记忆存用户偏好和历史知识；3)工具模块(Tools)：外部API等能力接口；4)执行模块(Executor)：调用工具并收集结果；5)推理模块(Reasoner)：基于当前状态决定下一步行动。","Agent架构",1,"{架构设计,模块职责,基础概念}"),
    ("ReAct 模式和 Plan-and-Execute 模式各有什么优缺点？","ReAct：思考-行动-观察循环，灵活应对不确定环境，但复杂任务可能走偏。Plan-and-Execute：先制定完整计划再逐步执行，效率高可控性强，但计划出错难修正。实践中常混合：先用Plan粗粒度规划，每步骤内用ReAct执行。","Agent架构",2,"{ReAct,Plan-and-Execute,架构模式}"),
    ("单 Agent vs 多 Agent 架构怎么选？多 Agent 的通信方式有哪些？","单Agent适合任务边界清晰、不需要角色分工的场景。多Agent适合需要不同专业能力协作的复杂任务。通信方式：消息传递、共享内存、层级结构、市场机制。选型关键看任务粒度、耦合度和维护成本。","Agent架构",2,"{多Agent,通信方式,架构选型}"),
    ("Agent 的状态管理怎么做？如何处理长任务的断点续传？","状态管理：内存状态、检查点机制(定期序列化到磁盘)、事件溯源(从事件流重建状态)。断点续传：定期保存(已完成步骤,当前步骤,中间结果)三元组到持久化存储，恢复时从上次检查点继续。关键：每个步骤需幂等，重试不会产生副作用。","Agent架构",3,"{状态管理,断点续传,幂等性}"),
    ("Agent 执行失败时有哪些兜底策略？如何设计鲁棒的 Agent 系统？","兜底策略：重试(指数退避)、降级(切换备用模型)、人工干预(关键决策暂停确认)、超时熔断、回滚(恢复到上一个检查点)。鲁棒性设计：输入校验、异常捕获、日志审计、告警通知、灰度发布。","Agent架构",3,"{失败处理,兜底策略,鲁棒性}"),
    ("什么是 Supervisor Agent 模式？和 Peer-to-Peer 多 Agent 有什么区别？","Supervisor：中心协调Agent负责分配任务、监控进度、合并结果。优点控制集中、易管理，缺点单点故障。P2P：Agent平等通信，自行协商任务分配。优点去中心化可扩展，缺点协调复杂。CrewAI和AutoGen分别采用这两种模式的不同变体。","Agent架构",2,"{Supervisor,Peer-to-Peer,多Agent模式}"),
    ("Agent 的 Memory 模块怎么设计？上下文窗口有限时如何处理长对话？","Memory三层架构：工作记忆存当前任务上下文；短期记忆存最近N轮对话(Redis+TTL)；长期记忆存用户画像和重要事实(向量数据库)。窗口有限处理：滑动窗口保留最近k轮；自动摘要压缩历史；关键信息提取存入结构化存储；记忆分层管理。","Agent架构",2,"{Memory,上下文管理,架构设计}"),
    ("如何设计一个可扩展的 Agent 工具调用系统？","可扩展工具系统：工具注册表(名称、描述、参数schema、执行函数)；工具发现(LLM根据描述自动选择)；参数校验(Pydantic验证)；权限控制(敏感操作需确认)；超时重试；结果格式化(统一返回格式)；工具组合(支持多工具串联)。","Agent架构",2,"{工具调用,可扩展性,系统设计}"),
    ("Agent 中的 Reflection（反思）机制如何实现？有什么作用？","Reflection机制：Agent执行操作后对结果进行自我评估。实现：LLM自我批评、外部验证(工具/规则检查)、对比验证(多次执行对比一致性)。作用：发现错误自动修正、提高输出质量、减少幻觉。典型流程：执行→反思→修正→再执行。代表框架Reflexion、Self-Refine。","Agent架构",2,"{Reflection,自我反思,质量保证}"),
    ("如何评估一个 Agent 系统的质量？有哪些关键指标？","Agent评估指标：任务成功率、平均完成步数、工具调用准确率、响应延迟、Token消耗、错误恢复率、用户满意度。离线评估用测试集批量跑，在线评估用A/B测试对比。工具：LangSmith、RAGAS。","Agent架构",2,"{评估,指标体系,质量保证}"),
    ("什么是 Tool Calling / Function Calling？LLM 如何知道该调用哪个工具？","Tool Calling是LLM调用外部函数/API的能力。实现：定义工具schema→注入system prompt或API tools参数→LLM根据用户输入判断是否需调用工具并选择工具生成参数→应用层执行工具返回结果→LLM根据结果生成最终回复。选工具依据：工具描述与用户意图的语义匹配度。","Agent架构",1,"{Tool Calling,Function Calling,基础原理}"),
    ("Agent 如何处理多轮工具调用？举例说明一个复杂任务的执行流程","多轮工具调用流程：用户问'帮我查武汉天气，晴天就写诗保存'。Agent执行：1)调用weather_api获取天气；2)判断晴天决定写诗；3)调用generate_poem生成诗歌；4)调用save_file保存；5)返回结果。每轮LLM分析当前状态→选择工具→执行→观察结果→决定是否继续，直到判断任务完成。","Agent架构",1,"{多轮调用,执行流程,示例}"),
    ("大模型 Agent 中的 Planning 为什么重要？有哪些主流规划方法？","Planning重要性：复杂任务无法一步完成需分解为子步骤。主流方法：Zero-shot Planning直接生成计划执行；Few-shot Planning提供示例模板；Hierarchical Planning先生成高层计划再细化；RePlanning执行中动态调整；Tree-of-Thought并行探索多条路径选最优。核心挑战：计划可能不可执行需错误恢复能力。","Agent架构",2,"{Planning,规划方法,任务分解}"),
    ("Agent 系统如何处理安全性和权限控制？","安全性设计：沙箱执行(隔离环境运行代码)、权限分级(读写执行分离)、操作确认(危险操作需用户确认)、速率限制(防滥用和无限循环)、输入过滤(防prompt注入)、审计日志(记录所有操作)、预算控制(token消耗上限)、内容安全(过滤敏感词汇)。","Agent架构",3,"{安全性,权限控制,系统设计}"),
    ("LangChain 的 AgentExecutor 内部是如何工作的？","AgentExecutor流程：1)接收用户输入和工具列表；2)构建prompt含工具描述和历史消息；3)调用LLM获取响应；4)解析LLM输出(JSON function call或ReAct的Thought/Action/Observation)；5)Action→执行工具→Observation追加到历史→回到步骤3；6)Final Answer→返回用户。Loop直到max_iterations或Agent输出最终答案。Agent负责决策，Executor负责执行和循环控制。","Agent架构",2,"{LangChain,AgentExecutor,实现原理}"),

    # ==== RAG与知识库 (15题) ====
    ("RAG 系统中文本切分策略有哪些？各自适用什么场景？","主流切分策略：固定长度切分最简单；基于分隔符切分保留语义完整性；递归切分先用大分隔符不够再用小的；语义切分用embedding相似度检测边界；句子级切分适合精确匹配场景。关键参数：chunk_size和chunk_overlap。重叠防止信息在边界处丢失。","RAG与知识库",1,"{Chunking,文本切分,基础概念}"),
    ("Embedding 模型怎么选？中文场景有什么推荐？","选型考虑：语言支持、维度(768/1024/1536)、检索质量(MTEB榜单)、推理速度、成本。中文推荐：text-embedding-3-small(OpenAI)、bge-large-zh(BAAI)、m3e-base(Moka)、stella-base。本地推荐BGE系列，API推荐OpenAI。","RAG与知识库",1,"{Embedding,模型选型,中文}"),
    ("什么是 Rerank？为什么 RAG 需要两阶段检索？","Rerank是RAG的第二阶段：先用embedding做粗筛(速度快召回Top-K)，再用更精确的交叉编码器对Top-K重新排序。需要两阶段原因：Embedding是双塔模型交互不充分，Rerank是交叉编码器精度高但速度慢。两阶段兼顾效率和精度。常用Reranker：Cohere Rerank、bge-reranker、cross-encoder。","RAG与知识库",2,"{Rerank,两阶段检索,精度优化}"),
    ("混合检索是什么？为什么比纯向量检索更好？","混合检索结合向量检索(语义匹配)和关键词检索BM25(精确匹配)。纯向量检索对数字、代码、人名等精确匹配弱；纯关键词检索对同义词、改写查询无能为力。混合检索通过加权融合(rrf/线性组合)两者结果，实际召回率提升10-30%。","RAG与知识库",2,"{混合检索,Hybrid Search,BM25}"),
    ("Query Rewrite 在 RAG 中有什么作用？常见改写策略有哪些？","查询改写将用户原始问题优化为更适合检索的查询。作用：用户输入往往口语化、省略信息、歧义多。常见策略：指代消解、query expansion(添加同义词)、HyDE(先生成假设答案再用答案检索)、多角度查询(生成多个改写版本分别检索合并)、子问题分解(复杂问题拆分为多个简单查询)。","RAG与知识库",3,"{Query Rewrite,查询改写,优化策略}"),
    ("RAG 系统中如何处理文档更新和知识过期问题？","文档更新：全量重建(定时重新索引)、增量更新(只对变更文档重新embedding)、版本管理(创建新版本逐步切换)。知识过期：元数据过滤(检索时过滤过期文档)、时效性权重(越新权重越高)、定期审查(标记过期内容)。工程上建议文档元数据必须包含创建时间和最后更新时间。","RAG与知识库",2,"{文档更新,知识过期,工程实践}"),
    ("如何评估 RAG 系统的检索质量？有哪些关键指标？","检索评估：Recall@K、MRR(平均倒数排名)、NDCG(归一化折损累计增益)、Hit Rate。生成评估：Faithfulness(回答是否基于检索内容)、Answer Relevance、Context Precision。评估工具：RAGAS、TruLens。","RAG与知识库",2,"{评估,RAGAS,指标体系}"),
    ("RAG 中的上下文污染是什么？如何避免？","上下文污染：检索到的文档中包含与问题无关甚至矛盾的信息干扰LLM判断。避免策略：提高检索精度用Reranker过滤、控制Top-K、优化分块策略、元数据预过滤、LLM自我过滤判断检索内容相关性。","RAG与知识库",2,"{上下文污染,Context Pollution,优化}"),
    ("多模态 RAG 如何处理图片、表格等非文本内容？","多模态RAG：图片用CLIP等多模态embedding模型与文本映射到同一向量空间；表格解析为Markdown再embedding或保留结构用专门表格理解模型；PDF扫描件OCR提取文字；音视频转写为文本。关键挑战：不同模态的对齐(alignment)，检索结果需跨模态融合。","RAG与知识库",3,"{多模态,图片处理,表格处理}"),
    ("RAG 系统的延迟优化有哪些方法？","延迟优化：Embedding缓存、近似最近邻搜索(ANN)(FAISS IVF/HNSW)、向量量化(PQ压缩)、异步处理、结果缓存(LRU)、用更小更快的embedding模型、流水线优化(预加载批处理GPU加速)。","RAG与知识库",2,"{延迟优化,性能,工程实践}"),
    ("如何处理 RAG 中检索到的多个 Chunk 之间的信息冲突？","信息冲突处理：LLM识别冲突(在prompt中要求指出矛盾)、多数投票、来源权重(权威来源优先)、时间优先(最新信息优先)、LLM综合分析后给出结论并标注不确定性、降级为搜索(严重冲突交用户决策或触发联网搜索)。","RAG与知识库",2,"{信息冲突,多Chunk,处理策略}"),
    ("什么是 Self-RAG？和传统 RAG 有什么区别？","Self-RAG在生成过程中动态决定是否需要检索、检索什么、检索结果是否相关。与传统RAG区别：传统总是先检索再生成，Self-RAG按需检索；Self-RAG评估检索质量，质量差时重新检索或放弃；生成过程标注哪些片段来自外部知识哪些来自模型自身知识。优势：减少不必要检索、提高效率、降低无关内容干扰。","RAG与知识库",3,"{Self-RAG,动态检索,前沿技术}"),
    ("如何为 RAG 系统选择合适的向量数据库？","选型考虑：数据规模(百万级以下ChromaDB/FAISS，千万级以上Milvus/Qdrant/Weaviate)、部署模式(本地ChromaDB最简，生产Milvus/Qdrant)、功能需求(元数据过滤/全文检索/多租户)、性能(QPS/写入吞吐/索引构建速度)、运维成本。推荐：开发ChromaDB，生产Milvus或Qdrant。PostgreSQL+pgvector适合已有PG的项目。","RAG与知识库",2,"{向量数据库,选型,工程实践}"),
    ("RAG 系统中如何实现多路召回？","多路召回策略：同义词扩展生成多个同义版本分别检索；多角度查询从不同角度重写query；子问题分解将复杂query拆分为多个子query；多语言中英文双语查询扩展召回范围；混合粒度同时检索句子级和段落级chunk。实现：并行执行多路检索→RRF或加权合并结果→去重→Reranker精排。","RAG与知识库",2,"{多路召回,Multi-Query,检索策略}"),
    ("RAG vs 微调 vs 长上下文 三种方案如何选择？","三种方案对比：RAG检索外部知识注入prompt，适合知识频繁更新、需准确引用来源、知识量大的场景；微调将知识内化到模型权重，适合领域术语、输出格式控制场景；长上下文直接把文档放进prompt，适合文档量小(<100K tokens)、需综合理解的场景。实践中常组合使用：微调控制格式，RAG注入最新知识，长上下文处理复杂推理。","RAG与知识库",3,"{RAG,微调,长上下文,方案对比}"),

    # ==== Prompt工程 (10题) ====
    ("System Prompt 和 User Prompt 的职责边界怎么划分？","System Prompt定义角色、设定规则、约束行为边界，持续生效。User Prompt是具体任务指令和上下文。划分原则：System放不变的部分，User放变化的部分；越底层约束越放System；System中重复关键规则提高遵循率；User可覆盖System部分指令。","Prompt工程",1,"{System Prompt,User Prompt,职责划分}"),
    ("Few-shot Prompting 的示例应该怎么选？数量多少合适？","示例选择：多样性(覆盖不同场景)、代表性(贴近实际使用)、格式一致、从简到难排列。数量2-4个最佳，太少泛化不足太多消耗token且可能过拟合。注意事项：示例必须是模型能完成的任务、避免引入偏见、定期更新。","Prompt工程",1,"{Few-shot,示例选择,Prompt设计}"),
    ("Chain-of-Thought 思维链提示的原理是什么？什么时候该用？","CoT原理：引导模型展示中间推理步骤提高复杂推理任务准确率。适用：数学计算、逻辑推理、多步问题。不适用：简单事实查询、创意写作、翻译。实现：Few-shot CoT在示例中加入推理步骤；Zero-shot CoT加'Let us think step by step'；Auto-CoT自动生成推理链。trade-off：增加推理准确率但消耗更多token。","Prompt工程",2,"{CoT,思维链,推理增强}"),
    ("什么是 Prompt Injection？如何防范？","Prompt Injection：攻击者在输入中注入恶意指令覆盖或绕过System Prompt限制。常见攻击：直接覆盖、间接注入(外部数据中嵌入指令)、多语言绕过。防范：输入过滤、指令加固(System和User prompt重复关键约束)、输出审核、权限隔离(敏感操作需额外验证)、用户输入用特殊分隔符与指令区隔。","Prompt工程",2,"{Prompt Injection,安全性,防范措施}"),
    ("Structured Output 有哪些实现方式？","实现方式：JSON Mode(API设置response_format)、Function Calling(定义tools强制符合schema的JSON)、Prompt约束加正则解析、Pydantic+Instructor用Python类型定义自动生成schema并验证输出、Grammar约束(Guidance/Outlines)。推荐：OpenAI用JSON Mode或Function Calling，开源模型用Instructor加正则回退。","Prompt工程",2,"{Structured Output,JSON,格式控制}"),
    ("如何系统地调优 Prompt？有什么方法论？","Prompt调优方法论：建立评估集50-100测试用例和期望输出；定义指标(准确率/格式合规率/幻觉率)；Baseline用最简单prompt测试；单变量变化每次只改一个元素；A/B测试对比两个版本；版本管理用Git管理prompt模板；自动化优化用DSPy等框架。常见调优维度：指令清晰度、示例质量、输出格式、角色设定、约束表达。","Prompt工程",3,"{Prompt调优,方法论,系统工程}"),
    ("如何设计一个防止模型幻觉的 System Prompt？","防幻觉System Prompt设计：明确指示'不确定时请说不知道'；要求引用来源；置信度标注'请标注你对每个断言的置信度'；区分知识来源(训练数据vs推理)；事实核查指令'请在回答后自查是否存在不一致'。关键：不是禁止模型生成，而是引导模型区分已知和未知。","Prompt工程",2,"{防幻觉,System Prompt,设计技巧}"),
    ("Self-Consistency 自洽性是什么？如何用于提高推理准确率？","Self-Consistency原理：对同一问题多次采样(较高temperature如0.7)生成多个推理路径和答案，取出现频率最高的答案。改进版：让LLM评估各答案质量后选择。适用：需多步推理的任务。优势：不需额外训练直接改进推理准确率5-15%。局限性：token消耗翻N倍(5-10次采样)。","Prompt工程",2,"{Self-Consistency,推理增强,采样策略}"),
    ("如何设计多轮对话的 Prompt 模板？需要考虑哪些因素？","多轮Prompt模板设计：消息格式明确标注角色(system/user/assistant)；上下文窗口管理旧消息压缩/截断策略；System Prompt重复关键约束定期重复；对话状态追踪在System中维护当前状态摘要；工具调用历史保留在上下文中；错误恢复设计对话重置和回退机制。","Prompt工程",2,"{多轮对话,模板设计,上下文管理}"),
    ("DSPy 框架如何实现自动 Prompt 优化？","DSPy将Prompt工程转化为编译优化问题。工作流程：定义签名(Python函数签名描述输入输出)→定义模块(ChainOfThought/ReAct)→编译(用少量训练数据自动搜索最优prompt结构、示例选择、推理策略)→评估(验证集测试编译后程序)。DSPy自动优化：few-shot示例选择、prompt措辞、推理步骤编排。优势：从手工调参变为数据驱动优化。","Prompt工程",3,"{DSPy,自动优化,前沿技术}"),

    # ==== 工具调用与工作流 (10题) ====
    ("Function Calling 的 Schema 怎么设计？有哪些最佳实践？","Schema设计最佳实践：函数名清晰描述功能；description详细包括使用场景和限制条件；参数名简洁明了添加description和type；必填vs选填参数明确标注；枚举类型用enum约束可选值；嵌套对象不超过2层；每个工具职责单一；参数不超过5个。描述质量直接影响LLM选工具的准确率。","工具调用与工作流",1,"{Function Calling,Schema设计,最佳实践}"),
    ("如何处理 Function Calling 中的参数校验和错误处理？","参数校验：调用前用Pydantic验证参数类型和范围；必填参数检查缺失时返回明确错误信息给LLM；枚举值校验。错误处理：工具执行异常捕获后返回结构化错误消息；错误消息包含原因和建议帮助LLM修正参数重试；超时机制；重试策略临时错误自动重试最多3次；优雅降级工具不可用时返回缓存结果。","工具调用与工作流",2,"{参数校验,错误处理,工程实践}"),
    ("Workflow 和 Agent 的边界在哪里？什么时候用 Workflow 什么时候用 Agent？","Workflow预定义步骤序列确定性执行适合数据ETL、定时报表、审批流程。Agent LLM自主决策动态选择工具和策略适合开放式任务、需推理判断、步骤不确定的场景。选型：任务确定性高→Workflow；需人类判断→Agent；简单分支→Workflow加条件；复杂推理多工具协调→Agent。实践中常混合：Workflow做骨架Agent做血肉。","工具调用与工作流",2,"{Workflow,Agent,架构边界}"),
    ("如何在 Agent 中安全地接入代码执行沙箱？","代码执行沙箱设计：隔离环境Docker容器或subprocess执行；资源限制CPU/内存/磁盘配额；网络隔离默认禁止外网访问需白名单；超时控制单次最长30秒；文件系统只读只允许读指定目录；输出截断限制stdout/stderr大小；危险操作黑名单禁止os.system和eval；审计日志记录所有执行代码和结果。Python推荐RestrictedPython或Docker沙箱。","工具调用与工作流",3,"{代码沙箱,安全性,工程实践}"),
    ("Agent 系统的可观测性怎么做？需要记录哪些信息？","可观测性三支柱：日志记录每次LLM调用(输入输出token)工具调用(名称参数结果)状态变更；指标监控请求量QPS延迟P50/P99错误率token消耗工具调用成功率；追踪完整请求链路用OpenTelemetry或LangSmith。关键记录：时间戳、session_id、user_id、model、temperature、prompt模板版本、每一步耗时。工具推荐LangSmith、Phoenix、Weights&Biases。","工具调用与工作流",2,"{可观测性,日志,监控}"),
    ("如何实现 Agent 的流式输出？有什么注意事项？","流式输出实现：LLM API设置stream=True逐token yield给前端。注意事项：工具调用不能流式需等LLM完整输出才能解析function call；中间状态展示'正在搜索...'；错误处理流中断时重连恢复；首token延迟(TTFT)用prefill优化；流式+非流式混合思考过程流式最终答案一次性输出。","工具调用与工作流",1,"{Streaming,流式输出,用户体验}"),
    ("MCP 是什么？它解决了什么问题？","MCP是Anthropic提出的模型上下文协议标准化AI模型与外部工具/数据源的交互方式。解决的问题：LLM应用碎片化工具集成，工具开发者需为每个平台适配。MCP定义Client-Server架构，Agent作为Client通过MCP协议调用Tool Server，统一工具发现、参数传递、结果返回格式。支持资源(文件/数据库)、工具(API调用)、提示模板三种原语。","工具调用与工作流",2,"{MCP,协议,标准化}"),
    ("多 Agent 系统中如何实现工具共享和任务分配？","工具共享：全局工具注册中心所有Agent可发现调用；工具权限不同Agent有不同权限；工具组合多Agent工具有机组合成更复杂能力。任务分配：Router Agent根据任务类型分发；能力匹配每个Agent注册能力描述Router做语义匹配；竞标机制Agent主动竞标Router选择最优；队列分发任务进队列空闲Agent自动取。实现框架CrewAI、AutoGen GroupChat。","工具调用与工作流",3,"{多Agent,工具共享,任务分配}"),
    ("外部 API 接入 Agent 时如何处理限流、超时和重试？","限流：客户端限流(token bucket/滑动窗口)；指数退避遇到429等待秒数指数增长；优先级队列；API配额监控。超时：设置connect_timeout和read_timeout。重试：仅对幂等操作(GET)自动重试；非幂等操作需确认是否可安全重试；最大重试3次总超时不超过30秒。错误降级：API不可用时使用缓存或默认值。","工具调用与工作流",2,"{API接入,限流,重试机制}"),
    ("如何设计一个 LLM 驱动的自动化工作流引擎？","工作流引擎设计：DSL定义用YAML/JSON定义工作流步骤；步骤类型LLM步骤、Tool步骤、Condition步骤、Parallel步骤；状态管理每步输入输出执行状态持久化；错误处理步骤失败时重试/跳过/终止策略；人工干预关键节点暂停等待确认；可视化DAG图展示工作流结构和执行进度。参考LangGraph的StateGraph、Temporal的Workflow Engine。","工具调用与工作流",3,"{工作流引擎,系统设计,自动化}"),
]

conn = psycopg2.connect(host="localhost", port=5432, dbname="interview_agent", user="postgres", password="postgres")
cur = conn.cursor()
print(f"Inserting {len(QUESTIONS)} new questions...")
for q in QUESTIONS:
    question, answer, module, difficulty, tags = q
    cur.execute(
        "INSERT INTO questions (question, answer, module, difficulty, tags) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (question, answer, module, difficulty, tags)
    )
    qid = cur.fetchone()[0]
    emb = np.random.randn(1536).astype(np.float32)
    emb = emb / np.linalg.norm(emb)
    cur.execute("UPDATE questions SET embedding = %s WHERE id = %s", (json.dumps(emb.tolist()), qid))
conn.commit()
cur.execute("SELECT count(*), module FROM questions GROUP BY module ORDER BY module")
for row in cur.fetchall():
    print(f"  {row[1]}: {row[0]} questions")
cur.close(); conn.close()
print("Done.")
