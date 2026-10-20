# RAG 设计说明

本文解释 AI 伴学的知识检索为什么这么设计，以及知识库上传从前端到向量库的完整链路。
面向需要改动或排查 RAG 的开发者。

- 只想弄懂这套机制在做什么：[RAG-INTRO.md](RAG-INTRO.md)
- 要改某个阶段或排查召回问题：[RAG-STAGES.md](RAG-STAGES.md)，逐段贴代码并标注优化点

## 一、设计约束

思路是从约束推出来的，先列约束：

| 约束 | 对设计的影响 |
| :--- | :--- |
| 首字延迟预算 ≤ 2 秒 | 默认路径**零额外 LLM 调用**。所有「更聪明但要多调一次模型」的优化都做成开关且默认关 |
| 零运维 | 不引入向量数据库服务、消息队列、后台 worker 进程。预热用线程，不用任务队列 |
| 跨语言是核心风险 | 中文提问要去命中英文知识库。BM25 在这里必然全军覆没（没有共享 token），所以向量路不是可选项 |
| 学习场景的容错性 | 自信答错比「知识库里没有」危害大得多，因此有阈值门控与拒答契约 |

## 二、两层可插拔

CRAG / Self-RAG / GraphRAG 改的不是「多几个阶段」，而是**控制流**：

- CRAG 加循环（检索 → 逐条打分 → 分数低就改写重检索）
- Self-RAG 加反思调用（生成之后回头判断答案有没有被证据支撑）
- GraphRAG 加新检索器

只做阶段级插拔接不住 CRAG 的循环，因此分两层：

```text
        ┌─── Strategy（编排级）──────────────────┐
        │ naive（默认）| corrective（CRAG）      │
        │ self_rag（占位）                       │
        └────────────────┬───────────────────────┘
                         │ 决定调用哪些 Stage、是否循环、是否插反思
  PRE           RETRIEVE/FUSE/RERANK              POST
 normalize        bm25 / vector / graph           dedup
 lang_detect      rrf                             threshold
 intent_gate      lexical / llm                   compress
 keywords                                         cite
 rewrite
```

模块布局：

```text
backend/app/rag/
├── types.py          RagContext / Hit / StageTrace / RagResult
├── registry.py       @register_stage / @register_strategy
├── store.py          VectorStore 协议 + FaissVectorStore
├── embeddings.py     走供应商 /embeddings，自动分批
├── corpus.py         语料装载、懒加载、启动预热
├── pipeline.py       run() —— 唯一对外接口，永不抛出
├── strategies/       base.py：naive / corrective / self_rag
└── stages/           pre.py / retrieve.py / ranking.py / post.py
```

落地形式是**注册表 + 环境变量**，增删阶段不改代码：

```python
# backend/app/rag/stages/retrieve.py
@register_stage(StageKind.RETRIEVE, "vector")
def vector(ctx: RagContext) -> None:
    ...
```

```ini
# backend/.env
RAG_STAGES_PRE=normalize,lang_detect,intent_gate,keywords,rewrite
RAG_STAGES_RETRIEVE=bm25,vector,graph
RAG_STAGES_FUSE=rrf
RAG_STAGES_RERANK=lexical
RAG_STAGES_POST=threshold,dedup,compress,cite
```

`registry.resolve_stages()` 遇到配置里写了不存在的阶段名**直接报错**，不静默跳过——否则配错了只表现为「RAG 没效果」，从现象极难反查。

## 三、RagContext

贯穿两层的唯一状态对象。每个 Stage 签名统一为 `(ctx) -> None`，数据库会话挂在上下文上，这让策略可以任意编排、重排、循环：

```python
ctx = RagContext(query=..., history=..., db=session)
```

| 字段 | 用途 |
| :--- | :--- |
| `normalized` / `retrieval_query` | 归一后的查询与改写后的查询。检索用后者，展示与日志用前者 |
| `lang` | `zh` / `en` / `mixed`，跨语言检索的前提 |
| `keywords` | 英文 token 与中文 2-gram，供 BM25 与重排使用 |
| `candidates` | 当前候选，各阶段就地增删改 |
| `final` / `context` | 后处理结果与注入 prompt 的最终文本 |
| `trace` | 每阶段的耗时与输入输出条数 |
| `skipped` | 门控跳过的原因，便于排查「为什么没检索」 |
| `embedding_calls` | 验证「默认路径零额外 LLM 调用」 |

## 四、各阶段详解

### 检索前

| 阶段 | 做什么 | 为什么需要 |
| :--- | :--- | :--- |
| `normalize` | 去空白、全半角归一，**保留原始 query 不动** | 原始 query 要留给展示与日志 |
| `lang_detect` | CJK 占比判定语言 | 决定要不要走查询翻译 |
| `intent_gate` | 寒暄、过短、纠错类请求则跳过整条管线 | 伴学对话大半轮次是短句纠错。每轮都打 embedding 既烧延迟，又会用无关上下文**污染原本很稳的纠错行为** |
| `keywords` | 英文 token + 中文 2-gram，引号里的词权重最高 | 供 BM25 与重排使用 |
| `rewrite` | 结合对话历史还原「这个词」的指代 | 学习者输入多为碎片 |

`rewrite` 刻意**不做拼写纠正**：那要逐个字母试删再查库，延迟不可控，而且一旦把专有名词改错，检索结果会比不改更糟。笔误交给 BM25 的模糊度与向量的语义相似度兜底。

中文用单字而非 2-gram 做 BM25 分词：IDF 对单字更稳，而 2-gram 会让长查询的分词组合爆炸。

### 检索中

三路各有盲区，靠融合取长补短：

| 路 | 强项 | 弱项 |
| :--- | :--- | :--- |
| `bm25` | 精确词形，中文提问里英文原词的唯一可靠来源 | 完全抓不到改写与同义 |
| `vector` | 语义改写，中文提问命中英文原文的主要通道 | 对精确术语反而不如 BM25 |
| `graph` | 关系邻居，专治「abandon 的派生词」「和 give up 有什么区别」 | 只有词条存在关系边时才有结果 |

`vector` 第一次调用会触发懒加载（`corpus.ensure_word_index` / `ensure_kb_index`）。正常情况下这些在启动时已由 `corpus.warm_up()` 的后台线程建好，检索路径只是兜底。

`graph` 路读的是 `word_relations` 表——精简词汇图谱，靠管理端人工维护，**零 LLM 索引成本**。这与完整的 Microsoft GraphRAG 有意不同：后者要 LLM 抽实体、跑社区检测再生成社区摘要，索引阶段的开销与本项目「零运维」冲突，而且英语词汇的关系本来就是结构化已知的，不需要让模型去猜。

### 融合与重排

`rrf` 用倒数排名融合：

```text
score = Σ 1 / (60 + rank_i)
```

免调参是它最大的价值——BM25 的分数量纲与余弦相似度完全不同，直接加权求和要反复调权重，而 RRF 只看排名，天然免疫量纲问题。

**标度必须记住**：单路第一名只有 `1/61 ≈ 0.0164`，三路同时第一也不过 `0.049`。`RAG_SCORE_THRESHOLD` 必须落在同一量级。本项目曾把默认值设成 `0.15`，导致 BM25 与向量的命中**全被阈值挡掉**，RAG 等于白接，而症状只是「向量路没召回」。

`graph` 路刻意给固定分 1.0 不参与 RRF：它是人工维护的关系，置信度高于向量的模糊命中，在三路里会被 BM25 与向量的名次稀释掉。

`lexical` 补 RRF 的盲区——RRF 只看排名，会把「恰好精确命中查询词」和「语义相近但没提这个词」排成一样。

`llm` 重排默认关闭（`RAG_LLM_RERANK=0`）。开启后每次多一轮模型调用，会吃掉首字延迟预算；失败时静默保留原排序。

### 检索后

| 阶段 | 做什么 |
| :--- | :--- |
| `threshold` | 最高分低于阈值则**放弃全部上下文** |
| `dedup` | 同一块内容被多路各召回一次时合并（token 集合 Jaccard > 0.8 判重复） |
| `compress` | 压进字符预算，取包含关键词最多的句子为中心开窗，而非机械截断 |
| `cite` | 编号与来源标签，拼成注入 prompt 的上下文 |

`threshold` 是信任的最后一道闸：注入一段不相关的内容，模型会**顺着它编**；什么都不注入，模型至少知道自己没有依据。配合系统提示词里写死的拒答契约——知识库没覆盖到就直说，绝不假装引用说了没说的话。

## 五、观测

每个 Stage 执行完记一条 `StageTrace`，管理页「检索调试」可直接回放：

```text
bm25       12ms   0→18
vector    809ms  18→18
rrf        0.1ms 18→6
```

**没有 trace，阈值和权重只能盲调。**

试跑一次检索：

```bash
curl -X POST http://localhost:8080/api/admin/rag/preview \
  -H "Authorization: Bearer <admin token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "现在完成时怎么构成"}'
```

## 六、知识库上传全流程

### 前端

```text
用户点「上传资料」
  ↓
Upload beforeUpload            frontend/src/pages/admin/KnowledgePage.tsx
  └─ 返回 false  → 阻止 Arco 自动上传，完全由我们走接口
  ↓
handleUpload(file: File)
  ↓
uploadDocument(file)           frontend/src/api/admin.ts
  ├─ new FormData() → form.append("file", file)
  └─ http.post("/api/admin/kb/documents", form,
               { headers: { "Content-Type": "multipart/form-data" } })
  ↓
http 请求拦截器                 frontend/src/api/client.ts
  └─ config.headers.Authorization = `Bearer ${token}`
```

`handleUpload` 的 `finally` 块重置上传态；失败时用 `toMessage(error)` 展示后端的 422 文案。

### 后端路由

```text
POST /api/admin/kb/documents
  ↓
upload_route(request, file: UploadFile, admin, db)     app/api/admin/kb.py
  ├─ admin: User = Depends(require_admin)     权限闸，普通用户 403
  ├─ data = await file.read()                 一次性读进内存
  ↓
_guard(kb_service.create_document, db, admin, filename, data, request)
  └─ 把 AdminError 统一转成 HTTPException（400 / 413 / 422）
```

`_guard` 是管理端路由的统一错误转换器：业务层抛 `AdminError(message, status_code)`，路由层负责变成 HTTP 响应。

### 服务层

`create_document(db, actor, filename, data, request)`，位于 `backend/app/services/kb_service.py`：

```text
├─ 空文件                 → AdminError 422「上传的文件为空」
├─ 超过 kb_max_upload_bytes → AdminError 413
│
├─ extract_text(filename, data) → (name, mime, body)
│    ├─ _split_name()     返回 (不含扩展名的名字, 小写扩展名)
│    ├─ 查 SUPPORTED 表    .md / .txt / .pdf / .docx，不支持则 422 并列出支持格式
│    ├─ _parse_pdf()      pypdf.PdfReader；抽不出文字层则 ParseError
│    ├─ _parse_docx()     python-docx，遍历段落与表格单元格
│    └─ _read_text()      UTF-8 优先，失败回退 GB18030（中文教材常见 GBK 存盘）
│    ParseError 由外层捕获并转成 AdminError 422
│
├─ chunk_text(body) → list[Chunk]
│    ├─ 按 Markdown 标题（# 开头）与空行分段，记录所在小节 heading
│    ├─ 段内按 kb_chunk_chars(500) 滑窗，kb_chunk_overlap(100) 重叠
│    └─ 尽量在 。/ . / 换行处断开，避免把句子劈成两半
│    结果为空 → AdminError 422「解析后没有任何可检索的内容」
│
├─ db.add(KnowledgeDocument(status=DOC_PENDING, ...))
├─ db.flush() 取得 document.id
├─ db.add(KbChunk(document_id=..., seq, heading, content))   逐块入库
├─ audit_service.record(action="kb.upload", ...)              只 add 不 commit
└─ db.commit()
```

**返回 `status=pending`** 是关键设计：上传接口同步做解析与切块，向量化留到之后。否则一个大 PDF 会让上传请求挂十几秒。

扫描版 PDF 抽不出文字层时会明确报错并提示不做 OCR，**绝不静默入库空内容**——否则用户以为传上去了，到检索时才发现什么都没有。

### 向量化

不在上传时。正常由启动时的后台线程完成：

```text
app/main.py::lifespan()
  └─ corpus.warm_up()                    起一个 daemon 线程
       └─ ensure_word_index() + ensure_kb_index()
```

兜底在首次检索时触发：

```text
app/api/chat.py::_retrieve()
  → rag.pipeline.run()
      → naive(ctx)
          → run_stages(ctx, RETRIEVE, ...)
              → vector(ctx)                          stages/retrieve.py
                  ├─ corpus.ensure_kb_index(db)      pending 文档标 ready 并建索引
                  ├─ corpus.ensure_word_index(db)    词库懒加载
                  └─ embeddings.embed_query(query)   查询向量
```

`index_kb(db)` 把所有 ready 文档的切块批量嵌入后写进 faiss 的 `kb_chunks` 集合：

```text
embeddings.embed(texts)            分批，每批 ≤ EMBEDDING_BATCH_SIZE(10)
  ↓
FaissVectorStore.upsert("kb_chunks", ids, embeddings, documents, metadatas)
  → backend/data/rag_index/kb_chunks.index    faiss 索引
  → backend/data/rag_index/kb_chunks.json     sidecar，存 id 与元数据
```

`IndexFlatIP` 不保存 id 与元数据，所以每个 collection 配一个 sidecar JSON 记「第 n 行对应哪个 chunk」。

### 端到端调用链

```text
[前端 KnowledgePage.tsx]
  handleUpload → uploadDocument → http.post(multipart)
        │  Authorization: Bearer <admin token>
        ↓
[app/api/admin/kb.py]
  upload_route → _guard → kb_service.create_document
        ↓
[app/services/kb_service.py]
  extract_text → chunk_text → KnowledgeDocument(pending) + KbChunk[] → audit → commit
        ↓
[MySQL]  knowledge_documents(pending) / kb_chunks
        ↓  上传到此结束，用户看到「切成 N 块，等待向量化」
        ↓
[启动时后台线程 / 首次检索兜底]
  corpus.warm_up → ensure_kb_index → index_kb
        ↓
[app/rag/embeddings.py]
  embed(texts) 分批调供应商 /embeddings
        ↓
[app/rag/store.py]
  FaissVectorStore.upsert(...) → data/rag_index/kb_chunks.{index,json}
```

## 七、实现细节与已知取舍

- **`embeddings.embed()` 自动分批**。当前供应商的批量硬上限是 10 条，超了直接返回 400 `batch size is invalid`。该失败是静默降级的，症状只是「向量路没召回」，容易被误判成检索逻辑问题。
- **faiss 的文件路径不能含非 ASCII 字符**。其 C++ 写入在 Windows 上走 ANSI 代码页，遇到中文路径会直接打不开文件。`pytest.ini` 固定 `--basetemp` 到项目内纯 ASCII 路径即为此。容器内路径是纯 ASCII，不受影响；但若用 bind mount 挂 Windows 宿主路径，宿主目录名里的中文会透传进去，所以 compose 用 named volume。
- **删除文档时向量要一并摘掉**，否则检索会命中已不存在的 chunk。走 `corpus.remove_document_vectors()` → `store.delete()`；faiss 用 `reconstruct_n` 取回向量重建，不需要调用方重新 embed。
- **词库向量懒加载**。313 个词条就是 313 次 embedding 调用，放在启动路径上会让冷启动从几百毫秒变成十几秒，因此用后台线程预热、检索路径兜底。
- **CRAG 不做 web search 兜底**。英语教学场景引入外部网页内容不可控、有合规风险，且与「本地零运维」冲突。`corrective` 策略只保留「评分 + 改写重检索」循环，且默认关闭。
- **Self-RAG 只有占位**。它防的失效模式已经被「阈值门控 + 引用 + 拒答」用零延迟覆盖大半；真正实现需要 chat 管线暴露 post-generation 钩子并在流式输出中途插入反思轮。
- **跨语言对齐能力未实测**。`text-embedding-v3` 对「中文问题 → 英文原文」的余弦区分度是 RAG 能否用好的生死线。若实测差距不足，需在 `rewrite` 阶段加一环查询翻译并做成可开关 Stage。
