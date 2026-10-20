# RAG 阶段代码标注

逐个阶段贴出实际代码并标注优化点。改动或排查 RAG 时的对照手册。

前置阅读：[RAG-INTRO.md](RAG-INTRO.md) 讲这套机制在做什么，[RAG.md](RAG.md) 讲整体架构与上传链路。本文只关注**每一段代码在优化什么**。

所有阶段签名统一为 `(ctx: RagContext) -> None`，靠读写 `ctx` 传递状态——这是可插拔的前提。新增一个优化 = 写一个函数 + 装饰器注册 + 环境变量启用。

```ini
RAG_STAGES_PRE=normalize,lang_detect,intent_gate,keywords,rewrite
RAG_STAGES_RETRIEVE=bm25,vector,graph
RAG_STAGES_FUSE=rrf
RAG_STAGES_RERANK=lexical
RAG_STAGES_POST=threshold,dedup,compress,cite
```

---

# 一、检索前（`app/rag/stages/pre.py`）

## 1. `normalize` —— 查询规整

```python
@register_stage(StageKind.PRE, "normalize")
def normalize(ctx: RagContext) -> None:
    text = ctx.query.strip()

    # 优化点①：全角转半角
    # 中文输入法常打出 ＡＢＡＮＤＯＮ 这种全角字符，BM25 按字面匹配时
    # 全角 Ａ 与半角 a 是两个不同的码点，直接导致一个词都搜不到
    halfwidth = "".join(
        chr(ord(ch) - _HALFWIDTH_OFFSET)                       # 0xFEE0 固定偏移
        if _FULLWIDTH_START <= ord(ch) <= _FULLWIDTH_END        # 0xFF01~0xFF5E
        else ch
        for ch in text
    )

    # 优化点②：连续空白压成一个空格
    ctx.normalized = re.sub(r"\s+", " ", halfwidth).strip()

    # 优化点③：原始 query 与检索 query 分开存
    ctx.retrieval_query = ctx.normalized
```

三个优化点中，第 ③ 点容易被忽略：展示与日志要保留用户原话，检索用归一后的版本，两者不能混用。

## 2. `lang_detect` —— 语言判定

```python
@register_stage(StageKind.PRE, "lang_detect")
def lang_detect(ctx: RagContext) -> None:
    text = ctx.normalized or ctx.query

    cjk = len(_CJK.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = cjk + latin
    if total == 0:
        ctx.lang = "en"; return

    ratio = cjk / total
    if ratio >= 0.6:   ctx.lang = "zh"      # 现在完成时怎么构成
    elif ratio <= 0.2: ctx.lang = "en"      # present perfect tense
    else:              ctx.lang = "mixed"   # abandon 怎么用
```

**为什么要三档**：`abandon 怎么用` 是 `mixed`，而这类混合查询正是英语学习场景的主流形态——英文术语加中文疑问词。它既不能纯按中文处理（会丢掉那个英文词），也不能纯按英文处理（会被中文虚词干扰）。

这是跨语言检索的前提：知道语言，后面才能决定要不要走查询翻译。

## 3. `intent_gate` —— 意图门控

**整个 RAG 里性价比最高的一个阶段。**

```python
_SMALLTALK = {"hi", "hello", "hey", "thanks", "ok", "yes", "no", "bye", ...}
_CORRECTION_HINTS = (
    "correct", "grammar", "mistake", "wrong", "polish", "translate",
    "怎么翻译", "帮我翻译", "纠正", "改一下", "对吗", "语法对吗",
)

@register_stage(StageKind.PRE, "intent_gate")
def intent_gate(ctx: RagContext) -> None:
    text = (ctx.normalized or ctx.query).strip()

    if not text:
        ctx.skipped = "空消息"; return

    # 优化点①：过短直接跳过
    if len(text) < 3:
        ctx.skipped = "输入过短"; return

    # 优化点②：寒暄白名单
    lowered = text.lower()
    if lowered.strip(" .!?。，！？") in _SMALLTALK:
        ctx.skipped = "寒暄"; return

    # 优化点③：纠错类请求跳过，但只对短句生效
    if any(hint in lowered for hint in _CORRECTION_HINTS) and len(text) < 40:
        ctx.skipped = "纠错类请求，走现有纠错流程"; return
```

三点设计：

- `ctx.skipped` 一设，naive 策略立刻 return，后面所有阶段都不执行，embedding 一次都不调
- **`and len(text) < 40` 是关键**：`帮我改一下这句话的语法` 跳过，但 `请讲解一下现在完成时的语法并纠正我下面这个句子` 不跳过——后者确实在问知识点
- 没有这条，一半以上的对话会白白打 embedding，还会拿无关资料把原本很稳的纠错行为带偏

## 4. `keywords` —— 关键词抽取

```python
_QUOTED = re.compile(r"[\"'「『“”‘’]([^\"'「』“”‘’]{2,})[\"'」』“”‘’]")
_ENGLISH_TOKEN = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")
_CJK_BIGRAM = re.compile(r"[一-鿿]{2,}")

@register_stage(StageKind.PRE, "keywords")
def keywords(ctx: RagContext) -> None:
    text = ctx.normalized or ctx.query
    found: list[str] = []

    # 优化点①：引号里的词排最前
    # 「帮我讲讲 "abandon" 这个词」→ abandon 是被点名的对象，权重最高
    for match in _QUOTED.finditer(text):
        found.append(match.group(1).strip().lower())

    # 优化点②：英文 token，过滤 a / of 这类功能词
    for token in _ENGLISH_TOKEN.findall(text):
        lowered = token.lower()
        if len(lowered) >= 3 and lowered not in found:
            found.append(lowered)

    # 优化点③：中文用 2-gram 而非单字
    for match in _CJK_BIGRAM.finditer(text):
        found.append(match.group(0))

    ctx.keywords = found[:24]      # 优化点④：封顶，防止长查询把重排拖慢
```

**这里中文用 2-gram，而 BM25 的分词用单字——两者刻意不同。** BM25 的 IDF 对单字更稳，2-gram 会让长查询的分词组合爆炸；但作为重排的匹配特征，2-gram 更精确。

`found[:24]` 封顶是防御性的：`lexical` 重排要对每个候选做包含判断，关键词无上限会让候选多时变成 O(n×m)。

## 5. `rewrite` —— 指代还原

```python
@register_stage(StageKind.PRE, "rewrite")
def rewrite(ctx: RagContext) -> None:
    text = ctx.normalized or ctx.query

    # 优化点①：从对话历史里还原「这个词」
    if re.search(r"这个词|这个单词|上面那个|刚才那个|它", text) and ctx.history:
        mentioned = _latest_mentioned_word(ctx.history)
        if mentioned:
            text = re.sub(r"这个词|这个单词|上面那个|刚才那个|它", mentioned, text)
            ctx.retrieval_query = text


def _latest_mentioned_word(history: list[dict]) -> str | None:
    for message in reversed(history[-6:]):           # 只看最近 6 轮
        content = message.get("content") or ""

        # 优化点②：优先取被引号点名的词
        for match in _QUOTED.finditer(content):
            candidate = match.group(1).strip()
            if candidate.isascii() and 2 < len(candidate) < 32:
                return candidate

        # 优化点③：过滤功能词，避免把 the / and 当成指代对象
        tokens = _ENGLISH_TOKEN.findall(content)
        content_words = [t for t in tokens if len(t) >= 4]
        if content_words:
            return content_words[-1]                  # 取最近提到的那个
    return None
```

**这个阶段有一个刻意不做的优化**，写在 docstring 里：

> 刻意不做拼写纠正：那要逐个字母试删再查库，延迟不可控，而且一旦把专有名词改错，检索结果会比不改更糟。学习者的笔误交给 BM25 的模糊度与向量的语义相似度去兜。

---

# 二、检索中（`retrieve.py` + `ranking.py`）

## 6. `bm25` —— 词法召回

分词与参数：

```python
_TOKEN = re.compile(r"[A-Za-z]+|[㐀-鿿]")      # 英文按词，中文按单字
_BM25_K1 = 1.5        # 词频饱和度
_BM25_B = 0.75        # 长度归一化强度
```

打分核心（`Bm25Index.search`）：

```python
terms = _tokenize(query)
scores = [0.0] * total_docs

for term in set(terms):                              # 优化点①：去重
    df = self._df.get(term, 0)
    if df == 0: continue                             # 优化点②：语料里没有的词跳过

    # 优化点③：IDF —— 越稀有的词权重越高
    # 「的」出现在所有文档里，权重趋近 0；「abandon」只在几篇里出现，权重高
    idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))

    for index, freq in enumerate(self._term_freqs):
        hits = freq.get(term, 0)
        if not hits: continue

        # 优化点④：长度归一化 —— 防止长文档靠堆词刷分
        length_norm = 1 - _BM25_B + _BM25_B * (self._doc_len[index] / (self._avg_len or 1.0))

        # 优化点⑤：词频饱和 —— 出现 10 次不等于出现 1 次的 10 倍
        scores[index] += idf * (hits * (_BM25_K1 + 1) / (hits + _BM25_K1 * length_norm))
```

五个优化点里有两个值得单说：

- **IDF**：让「的」这类到处都有的词几乎不加分，「abandon」这种词加很多分
- **词频饱和（`k1`）**：一个词出现 20 次不会比出现 2 次强 10 倍，收益递减

### 索引缓存

```python
def _signature(db: Session) -> tuple:
    """必须用 count 而不是 scalar(select(id))——后者取的是最小主键，
    新增文档不会改变它，缓存会一直不失效。"""
    return (
        _count(KnowledgeDocument, KnowledgeDocument.status == DOC_READY),
        _count(KbChunk),
        _count(Word, Word.status == STATUS_ACTIVE),
    )

def get_index(db: Session) -> Bm25Index:
    signature = _signature(db)
    if _CACHE is not None and _CACHE_SIGNATURE == signature:
        return _CACHE                                # 语料没变，省掉全表扫描
```

**这里修过一个真 bug**：原本写的是 `scalar(select(KbChunk.id))`，取的是最小主键，新增文档根本不会改变它，缓存永远不失效。

## 7. `vector` —— 语义召回

```python
@register_stage(StageKind.RETRIEVE, "vector")
def vector(ctx: RagContext) -> None:
    db = ctx.db
    if db is None: return

    # 优化点①：懒加载兜底
    # 正常由启动时的后台线程预热线程建好，这里只是兜底
    corpus.ensure_kb_index(db)
    corpus.ensure_word_index(db)

    query = ctx.retrieval_query or ctx.normalized or ctx.query
    try:
        query_vector = embeddings.embed_query(query)
    except embeddings.EmbeddingError:
        # 优化点②：embedding 挂了不阻断，只是这一路没结果
        ctx.notes.append("embedding 不可用，向量路跳过")
        return
    ctx.embedding_calls += 1                        # 供测试验证「只调一次」

    vector_store = store.get_store()
    # 优化点③：两个集合各查一遍
    for collection, kind in ((COLLECTION_KB, "chunk"), (COLLECTION_WORD, "word")):
        for position, row in enumerate(
            vector_store.query(collection, query_vector, top_k=settings.rag_top_k * 2),
            start=1,
        ):
            ctx.candidates.append(Hit(kind=kind, source="vector", ...))
```

`ctx.embedding_calls` 是**专门为测试留的**：有一条测试断言它 `<= 1`，用来钉住「默认路径零额外 LLM 调用、embedding 只调一次」这条延迟契约。

## 8. `graph` —— 词汇图谱召回

```python
@register_stage(StageKind.RETRIEVE, "graph")
def graph(ctx: RagContext) -> None:
    db = ctx.db
    if db is None or not ctx.keywords: return

    matched = _match_words(db, ctx.keywords[:8])     # 优化点①：只取前 8 个关键词
    if not matched: return

    for position, word in enumerate(matched, start=1):
        relations = db.scalars(
            select(WordRelation).where(WordRelation.head_word_id == word.id)
        ).all()
        if not relations: continue

        # 优化点②：近义词排最前
        # 「和 X 有什么区别」是最高频的提问形态
        ordered = sorted(relations,
                         key=lambda item: 0 if item.relation == RELATION_SYNONYM else 1)

        parts = [f"{word.word} {word.translation}"]
        for relation in ordered:
            label = RELATION_LABELS.get(relation.relation, relation.relation)
            note = f"：{relation.note}" if relation.note else ""
            parts.append(f"{label} {relation.tail_word}{note}")

        ctx.candidates.append(Hit(
            kind="relation", source="graph",
            content="\n".join(parts),
            score=1.0,                                 # 优化点③：固定满分
            ...
        ))
```

**零 LLM 索引成本** —— 关系边是管理端人工录入的，不是让模型抽出来的。这是它和完整 Microsoft GraphRAG 的根本区别。

## 9. `rrf` —— 倒数排名融合（`ranking.py`）

```python
_RRF_K = 60                                       # 检索领域常用取值

@register_stage(StageKind.FUSE, "rrf")
def rrf(ctx: RagContext) -> None:
    if not ctx.candidates: return

    # 优化点①：融合前先去重
    # 同一块内容可能被 BM25 和向量各召回一次
    best: dict[str, Hit] = {}
    for hit in ctx.candidates:
        key = f"{hit.kind}:{hit.dedup_key[:120]}"
        existing = best.get(key)
        if existing is None or hit.rank < existing.rank:      # 取更好的名次
            best[key] = hit

    fused: list[Hit] = []
    for hit in best.values():
        # 优化点②：只看名次，不看分数
        # BM25 的分数量纲与余弦相似度完全不同，直接相加毫无意义
        score = 1.0 if hit.source == "graph" else 1.0 / (_RRF_K + hit.rank)

        # 优化点③：graph 路固定满分，不参与排名融合
        # 它是人工维护的关系，置信度高于向量的模糊命中，
        # 若参与融合会被 BM25 与向量的名次稀释掉
        fused.append(Hit(..., score=score, ...))

    fused.sort(key=lambda item: item.score, reverse=True)
    ctx.candidates = fused[: settings.rag_top_k * 3]           # 优化点④：封顶
```

**docstring 里专门标了标度坑**：

> 单路第一名的分是 1/61 ≈ 0.0164，三路同时第一也不过 0.049。`rag_score_threshold` 必须落在这个量级上，否则 BM25 与向量的命中会被阈值全部挡掉，RAG 等于白接。

## 10. `lexical` —— 词法加分重排

```python
@register_stage(StageKind.RERANK, "lexical")
def lexical(ctx: RagContext) -> None:
    # 优化点①：过滤短于 3 字符的词，避免 the / of 这类噪音词加分
    keywords = [keyword for keyword in ctx.keywords if len(keyword) >= 3]
    if not keywords or not ctx.candidates: return

    for hit in ctx.candidates:
        lowered = hit.content.lower()
        hits = sum(1 for keyword in keywords if keyword in lowered)

        # 优化点②：加分但封顶
        # 上限压在 0.5，避免词法命中完全盖过语义相似度
        hit.score += min(hits * 0.05, 0.5)

    ctx.candidates.sort(key=lambda item: item.score, reverse=True)
    ctx.candidates = ctx.candidates[: settings.rag_top_k]     # 优化点③：封顶
```

**补的是 RRF 的盲区**：RRF 只看名次，会把「恰好精确命中查询词」和「语义相近但没提这个词」排成一样。

加分封顶在 0.5 很重要——不封顶的话，一个堆满关键词的垃圾文档能把语义最相关的候选完全盖过去。

---

# 三、检索后（`app/rag/stages/post.py`）

## 11. `threshold` —— 阈值门控

```python
@register_stage(StageKind.POST, "threshold")
def threshold(ctx: RagContext) -> None:
    if not ctx.candidates:
        ctx.skipped = ctx.skipped or "没有召回任何内容"
        ctx.final = []
        return

    best = max(hit.score for hit in ctx.candidates)

    # 优化点：低于阈值就全部丢弃，一条都不注入
    if best < settings.rag_score_threshold:
        ctx.skipped = f"最高相关度 {best:.3f} 低于阈值 {settings.rag_score_threshold}"
        ctx.final = []
        ctx.candidates = []
        return

    ctx.final = list(ctx.candidates)
```

**只有十几行，但对结果质量影响最大。**

逻辑是「全有或全无」，不搞「低分的少给一点」这种折中。因为注入一段不相关的内容，模型会**顺着它编**；什么都不注入，模型至少知道自己没有依据。

当前阈值 `0.016`，对应「至少在某一路里排第一」。

## 12. `dedup` —— 近似去重

```python
def _similar(left: str, right: str) -> bool:
    """token 集合 Jaccard 超过 0.8 视为重复。"""
    if left == right: return True
    if not left or not right: return False
    a, b = set(left), set(right)
    union = len(a | b)
    return bool(union) and len(a & b) / union > 0.8            # 优化点①：不只比完全相同


@register_stage(StageKind.POST, "dedup")
def dedup(ctx: RagContext) -> None:
    kept, seen_keys = [], []
    for hit in ctx.final:
        key = hit.dedup_key[:160]                               # 优化点②：截断
        if any(_similar(key, other) for other in seen_keys):
            continue
        seen_keys.append(key)
        kept.append(hit)
    ctx.final = kept
```

两个优化点：

- **Jaccard 而非精确匹配** —— 两段文字只要有 80% 的字符集合重合就算重复。BM25 和向量召回的同一段，标题可能带不同前缀，精确匹配会漏
- **`[:160]` 截断** —— Jaccard 要建集合并求交并，字符数无上限时长文档会拖慢；截断后比较成本恒定

## 13. `compress` —— 上下文压缩

```python
def _best_window(text: str, keywords: list[str]) -> str:
    limit = min(600, settings.rag_max_context_chars)
    if len(text) <= limit:
        return text                                             # 优化点①：短的原样保留

    sentences = [match.group(0).strip() for match in _SENTENCE.finditer(text)]

    # 优化点②：找包含关键词最多的那句话
    lowered = [keyword.lower() for keyword in keywords if keyword]
    best_index, best_hits = 0, -1
    for index, sentence in enumerate(sentences):
        hits = sum(1 for keyword in lowered if keyword in sentence.lower())
        if hits > best_hits:
            best_index, best_hits = index, hits

    # 优化点③：以它为中心往前取一句，往后取到预算用完
    start = max(0, best_index - 1)
    window, used = [], 0
    for sentence in sentences[start:]:
        if used + len(sentence) > limit: break
        window.append(sentence); used += len(sentence)
    return "\n".join(window) if window else text[:limit]


@register_stage(StageKind.POST, "compress")
def compress(ctx: RagContext) -> None:
    budget = settings.rag_max_context_chars                    # 3000 字
    kept, used = [], 0
    for hit in ctx.final:                                      # 按排名顺序，靠前的先拿预算
        snippet = _best_window(hit.content, ctx.keywords or [ctx.retrieval_query])
        remaining = budget - used
        if remaining <= 0: break                               # 优化点④：预算用完就停
        if len(snippet) > remaining:
            snippet = snippet[:remaining].rstrip()
            if len(snippet) < 20: break                        # 优化点⑤：剩太少就别要了
        kept.append((hit, snippet)); used += len(snippet)

    ctx.final = [hit for hit, _ in kept]
    ctx.compressed = {id(hit): snippet for hit, snippet in kept}
```

核心是「**找关键词最密的句子为中心开窗**」而不是从头截断——截断经常把关键句切成两半，AI 拿到半句话只能猜。

`if len(snippet) < 20: break` 是细节：剩下的预算装不下有意义的片段时宁可不要，也不要塞个残缺句子进去。

## 14. `cite` —— 引用标注

```python
def _source_label(hit) -> str:
    if hit.kind == "chunk":
        name = hit.metadata.get("name", "知识库")
        heading = hit.heading or hit.metadata.get("heading", "")
        return f"来源: {name}" + (f" #{heading}" if heading else "")
    if hit.kind == "word":
        return f"词库词条: {hit.metadata.get('word', '')}"
    if hit.kind == "relation":
        return f"词汇关系: {hit.metadata.get('word', '')}"
    return hit.source


@register_stage(StageKind.POST, "cite")
def cite(ctx: RagContext) -> None:
    if not ctx.final:
        ctx.context = ""; return

    blocks, snippets = [], getattr(ctx, "compressed", {})
    for index, hit in enumerate(ctx.final, start=1):
        snippet = snippets.get(id(hit)) or hit.content        # 优化点①：优先用压缩后的
        label = _source_label(hit)
        prefix = f"[{index}] {label}\n" if label else f"[{index}]\n"
        blocks.append(prefix + snippet)

    ctx.context = "\n\n".join(blocks)                          # 注入 prompt 的最终产物
```

编号必须与给模型的指令对齐——`SYSTEM_PROMPT` 里写死了「用到哪条就标 `[n]`」。编号对不上时用户去核对会发现张冠李戴，**比不引用更糟**。

---

# 四、汇总：14 个阶段的优化点分布

| 环节 | 阶段 | 优化点数 | 最关键的一个 |
| :--- | :--- | :--- | :--- |
| PRE | `normalize` | 3 | 全半角归一（否则全角字母搜不到） |
| PRE | `lang_detect` | 1 | 三档而非两档，容纳混合查询 |
| PRE | `intent_gate` | 3 | **短句纠错也跳过**（`and len(text) < 40`） |
| PRE | `keywords` | 4 | 引号里的词排最前 |
| PRE | `rewrite` | 3 | **故意不做**拼写纠正（延迟不可控） |
| RETRIEVE | `bm25` | 5 | IDF + 词频饱和 |
| RETRIEVE | `vector` | 3 | 失败静默降级 |
| RETRIEVE | `graph` | 3 | 近义词排最前 |
| FUSE | `rrf` | 4 | **按名次不按分数** |
| RERANK | `lexical` | 3 | 加分封顶 0.5 |
| POST | `threshold` | 1 | **全有或全无** |
| POST | `dedup` | 2 | Jaccard 而非精确匹配 |
| POST | `compress` | 5 | **关键词最密句子为中心开窗** |
| POST | `cite` | 1 | 编号与指令对齐 |

加粗的五个是**改动时最容易破坏**的。它们的作用不体现在「找到了什么」，而体现在「没找到时怎么办」和「量纲对不对」，出问题时症状都很隐蔽——例如阈值标度设错，只会表现为「RAG 好像没起作用」。

# 五、改动前先做的三件事

1. **跑一遍检索调试页**（管理页「检索调试」）。输入问题，看各阶段耗时、候选排序、最终注入的上下文。改阈值或增减阶段都要先在这里看效果。
2. **确认延迟契约没被打破**。`tests/test_rag.py::TestPipeline::test_default_path_makes_no_llm_call` 断言默认路径零额外 LLM 调用、embedding 只调一次。引入任何新的模型调用都要先想清楚延迟代价。
3. **想清楚失败时怎么办**。每个 Stage 都要能在异常情况下优雅退出——检索拿不到结果时对话必须照常。`pipeline.run()` 的兜底保证了不冒泡，但阶段内部的早退路径要自己写清楚。
