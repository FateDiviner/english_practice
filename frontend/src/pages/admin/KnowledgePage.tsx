import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Empty,
  Message,
  Popconfirm,
  Tag,
  Typography,
  Upload,
} from "@arco-design/web-react";

import {
  deleteDocument,
  fetchDocuments,
  fetchKbFormats,
  uploadDocument,
} from "@/api/admin";
import RecordCard from "@/components/RecordCard";
import ResponsiveList from "@/components/ResponsiveList";
import { toMessage } from "@/api/client";
import type { KbDocument } from "@/types";

const STATUS_LABEL: Record<KbDocument["status"], string> = {
  pending: "[待索引]",
  indexing: "[索引中]",
  ready: "[可用]",
  failed: "[失败]",
};

const STATUS_COLOR: Record<KbDocument["status"], string> = {
  pending: "gray",
  indexing: "arcoblue",
  ready: "green",
  failed: "red",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function KnowledgePage() {
  const [items, setItems] = useState<KbDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [formats, setFormats] = useState<{ extensions: string[]; max_bytes: number } | null>(
    null
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchDocuments());
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void fetchKbFormats()
      .then(setFormats)
      .catch(() => setFormats(null));
  }, [load]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const document = await uploadDocument(file);
      Message.success({
        content: `已上传 ${document.source_filename}，切成 ${document.chunk_count} 块，等待向量化`,
      });
      await load();
    } catch (error) {
      // 扫描版 PDF 这类解析失败会在上传时就报错，不会静默入库空内容
      Message.error({ content: toMessage(error), duration: 6000 });
    } finally {
      setUploading(false);
    }
    return false;
  };

  const remove = async (row: KbDocument) => {
    try {
      await deleteDocument(row.id);
      Message.success({ content: `已删除 ${row.source_filename}` });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const accept = formats ? formats.extensions.join(",") : ".md,.txt,.pdf,.docx";
  const maxMb = formats ? Math.round(formats.max_bytes / 1024 / 1024) : 10;

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>知识库</h2>
          <p style={{ margin: "4px 0 0", color: "var(--text-2)", fontSize: 13 }}>
            上传的资料对所有用户的 AI 伴学生效。上传时同步解析与切块，向量化在后台进行。
            扫描版 PDF 没有文字层会被拒绝——本平台不做 OCR。
          </p>
        </div>
        <Upload
          accept={accept}
          showUploadList={false}
          beforeUpload={(file) => {
            void handleUpload(file);
            // 阻止 Arco 自动上传，完全由我们走接口
            return false;
          }}
        >
          <Button type="primary" loading={uploading}>
            上传资料（最大 {maxMb}MB）
          </Button>
        </Upload>
      </header>

      {formats && (
        <Typography.Text type="secondary" style={{ fontSize: 13 }}>
          支持格式：{formats.extensions.join(" / ")}
        </Typography.Text>
      )}

      <ResponsiveList
        rowKey="id"
        loading={loading}
        data={items}
        noDataElement="还没有上传任何资料"
        pagination={false}
        renderCard={(row) => (
          <RecordCard
            title={row.source_filename}
            tags={[
              <Tag key="s" size="small" color={STATUS_COLOR[row.status]}>
                {STATUS_LABEL[row.status]}
              </Tag>,
            ]}
            fields={[
              { label: "大小", value: formatSize(row.size_bytes) },
              { label: "字数", value: row.char_count },
              { label: "切块数", value: row.chunk_count },
              { label: "上传时间", value: row.created_at.slice(0, 10) },
            ]}
            actions={
              row.error ? (
                <Typography.Text type="error" style={{ fontSize: 13 }}>
                  {row.error}
                </Typography.Text>
              ) : (
                <Popconfirm
                  title="删除该资料及其全部切块？"
                  okText="确认删除"
                  cancelText="取消"
                  onOk={() => void remove(row)}
                >
                  <Button size="small" status="danger">
                    删除
                  </Button>
                </Popconfirm>
              )
            }
          />
        )}
        columns={[
          {
            title: "名称",
            dataIndex: "source_filename",
            render: (value: string) => <strong>{value}</strong>,
          },
          { title: "大小", dataIndex: "size_bytes", width: 100, render: (v: number) => formatSize(v) },
          { title: "字数", dataIndex: "char_count", width: 90 },
          { title: "切块数", dataIndex: "chunk_count", width: 90 },
          {
            title: "状态",
            dataIndex: "status",
            width: 110,
            render: (value: KbDocument["status"]) => (
              <Tag color={STATUS_COLOR[value]}>{STATUS_LABEL[value]}</Tag>
            ),
          },
          {
            title: "失败原因",
            dataIndex: "error",
            render: (value: string | null) =>
              value ? (
                <Typography.Text type="error" style={{ fontSize: 13 }}>
                  {value}
                </Typography.Text>
              ) : (
                "-"
              ),
          },
          {
            title: "上传时间",
            dataIndex: "created_at",
            width: 170,
            render: (value: string) => value.slice(0, 19).replace("T", " "),
          },
          {
            title: "操作",
            width: 100,
            render: (_, row: KbDocument) => (
              <Popconfirm
                title="删除该资料及其全部切块？"
                okText="确认删除"
                cancelText="取消"
                onOk={() => void remove(row)}
              >
                <Button size="small" status="danger">
                  删除
                </Button>
              </Popconfirm>
            ),
          },
        ]}
      />

      {items.length === 0 && !loading && (
        <Empty description="上传教材笔记、语法总结或场景对话，AI 伴学就能引用它们回答问题" />
      )}
    </section>
  );
}
