import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Empty,
  Input,
  Message,
  Space,
  Tag,
  Typography,
} from "@arco-design/web-react";

import { fetchRagConfig, fetchRagHealth, previewRag } from "@/api/admin";
import { toMessage } from "@/api/client";
import type { RagConfig, RagPreview } from "@/types";

const KIND_LABEL: Record<string, string> = {
  chunk: "知识库",
  word: "词库词条",
  relation: "词汇关系",
};

const SOURCE_LABEL: Record<string, string> = {
  bm25: "BM25",
  vector: "向量",
  graph: "图谱",
};

export default function RagDebugPage() {
  const [config, setConfig] = useState<RagConfig | null>(null);
  const [health, setHealth] = useState<{ embedding: boolean; kb_chunks: number; word_chunks: number } | null>(null);
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RagPreview | null>(null);

  const loadConfig = useCallback(async () => {
    try {
      const [cfg, hc] = await Promise.all([fetchRagConfig(), fetchRagHealth()]);
      setConfig(cfg);
      setHealth(hc);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const run = async () => {
    const text = query.trim();
    if (!text) {
      Message.warning({ content: "先输入一个问题" });
      return;
    }
    setRunning(true);
    setResult(null);
    try {
      setResult(await previewRag(text));
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setRunning(false);
    }
  };

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header>
        <h2 style={{ margin: 0, fontSize: 20 }}>检索调试</h2>
        <p style={{ margin: "4px 0 0", color: "var(--text-2)", fontSize: 13 }}>
          这里跑的就是线上对话会用的同一条管线。调阈值、增减阶段都先在这里看 trace，
          再改配置——没有 trace 只能盲调。
        </p>
      </header>

      {config && (
        <Card title="当前生效配置" style={{ borderRadius: "var(--border-radius-md)" }}>
          <Space wrap size={[16, 8]}>
            <Tag color={config.enabled ? "green" : "gray"}>
              RAG {config.enabled ? "已启用" : "已关闭"}
            </Tag>
            <Tag>策略 {config.strategy}</Tag>
            <Tag color={config.llm_rerank ? "orangered" : "gray"}>
              LLM 重排 {config.llm_rerank ? "开" : "关"}
            </Tag>
            <Tag>top_k {config.top_k}</Tag>
            <Tag>阈值 {config.score_threshold}</Tag>
            <Tag>上下文预算 {config.max_context_chars} 字</Tag>
            <Tag>模型 {config.embedding_model}</Tag>
          </Space>
          <div style={{ marginTop: 10 }}>
            {Object.entries(config.stages).map(([kind, list]) => (
              <div key={kind} style={{ fontSize: 13, marginBottom: 4 }}>
                <code style={{ color: "var(--text-2)" }}>{kind}</code>：{list}
              </div>
            ))}
          </div>
          {health && (
            <div style={{ marginTop: 10, fontSize: 13 }}>
              <Tag color={health.embedding ? "green" : "red"}>
                embedding {health.embedding ? "可用" : "不可用"}
              </Tag>
              <Tag>知识库向量 {health.kb_chunks}</Tag>
              <Tag>词库向量 {health.word_chunks}</Tag>
            </div>
          )}
        </Card>
      )}

      {/* Arco 2.66 没有 Space.Compact，用 flex 拼一个等效的输入+按钮组 */}
      <div style={{ display: "flex", gap: 8, width: "100%" }}>
        <Input
          placeholder="输入一个问题，例如：现在完成时怎么构成"
          value={query}
          onChange={setQuery}
          onPressEnter={() => void run()}
          allowClear
          style={{ flex: 1 }}
        />
        <Button type="primary" loading={running} onClick={() => void run()}>
          试跑检索
        </Button>
      </div>

      {result && (
        <>
          <Card title="结论" style={{ borderRadius: "var(--border-radius-md)" }}>
            {result.skipped ? (
              <Typography.Text type="warning">跳过：{result.skipped}</Typography.Text>
            ) : (
              <Space wrap>
                <Tag>语言 {result.lang}</Tag>
                <Tag color="green">命中 {result.hits.length} 条</Tag>
                <Tag>策略 {result.strategy}</Tag>
              </Space>
            )}
          </Card>

          {result.trace.length > 0 && (
            <Card title="阶段耗时" style={{ borderRadius: "var(--border-radius-md)" }}>
              {result.trace.map((trace, index) => (
                <div
                  key={`${trace.stage}-${index}`}
                  style={{ fontSize: 13, marginBottom: 4, display: "flex", gap: 12, flexWrap: "wrap" }}
                >
                  <code style={{ minWidth: 110 }}>{trace.stage}</code>
                  <span style={{ color: "var(--text-2)", minWidth: 70 }}>{trace.kind}</span>
                  <span style={{ minWidth: 80 }}>{trace.duration_ms} ms</span>
                  <span style={{ minWidth: 110 }}>
                    {trace.input_count} → {trace.output_count}
                  </span>
                  {trace.note && <span style={{ color: "var(--color-warning)" }}>{trace.note}</span>}
                </div>
              ))}
            </Card>
          )}

          <Card title="候选（按最终排序）" style={{ borderRadius: "var(--border-radius-md)" }}>
            {result.hits.length === 0 ? (
              <Empty description="没有候选，阈值或召回有问题" />
            ) : (
              result.hits.map((hit) => (
                <div
                  key={`${hit.kind}-${hit.rank}`}
                  style={{
                    padding: "8px 0",
                    borderBottom: "1px solid var(--border-color)",
                    fontSize: 13,
                  }}
                >
                  <Space wrap size={[8, 4]}>
                    <Tag size="small">#{hit.rank}</Tag>
                    <Tag size="small" color="arcoblue">
                      {KIND_LABEL[hit.kind] ?? hit.kind}
                    </Tag>
                    <Tag size="small">{SOURCE_LABEL[hit.source] ?? hit.source}</Tag>
                    <Typography.Text code>{hit.score.toFixed(4)}</Typography.Text>
                    {hit.heading && <Tag size="small">{hit.heading}</Tag>}
                  </Space>
                  <div style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>
                    {hit.content.slice(0, 220)}
                    {hit.content.length > 220 ? "…" : ""}
                  </div>
                </div>
              ))
            )}
          </Card>

          {result.context && (
            <Card title="注入 prompt 的上下文" style={{ borderRadius: "var(--border-radius-md)" }}>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 12, maxHeight: 300, overflowY: "auto" }}>
                {result.context}
              </pre>
            </Card>
          )}
        </>
      )}
    </section>
  );
}
