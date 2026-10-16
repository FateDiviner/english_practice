import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import { IconExport, IconImport, IconPlus, IconRefresh, IconLeft } from "@arco-design/web-react/icon";
import { useNavigate, useParams } from "react-router-dom";
import {
  createWord,
  deleteWord,
  exportWordbook,
  fetchWordbooks,
  fetchWords,
  importWordbooks,
  setWordStatus,
  updateWord,
} from "@/api/words";
import { RequestError, toMessage } from "@/api/client";
import type {
  ImportFailureDetail,
  ValidationIssueOut,
  WordAdminOut,
  WordUpsertPayload,
} from "@/types";

/** 词条管理：增改、上下架、批量导入与导出 */
export default function WordbookDetailPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const numericId = Number(bookId);

  const [bookTitle, setBookTitle] = useState("");
  const [rows, setRows] = useState<WordAdminOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<WordAdminOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [issues, setIssues] = useState<ValidationIssueOut[]>([]);
  const [importMessage, setImportMessage] = useState("");
  const [form] = Form.useForm<WordUpsertPayload>();

  const limit = 20;

  useEffect(() => {
    void fetchWordbooks()
      .then((books) => setBookTitle(books.find((b) => b.id === numericId)?.title ?? ""))
      .catch(() => undefined);
  }, [numericId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await fetchWords(numericId, {
        search: search.trim() || undefined,
        status: status || undefined,
        limit,
        offset,
      });
      setRows(page.items);
      setTotal(page.total);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [numericId, search, status, offset]);

  useEffect(() => {
    if (Number.isFinite(numericId)) void load();
  }, [load, numericId]);

  const run = async (action: () => Promise<unknown>, success: string) => {
    try {
      await action();
      Message.success({ content: success });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const openCreate = () => {
    form.resetFields();
    setCreating(true);
  };

  const openEdit = (word: WordAdminOut) => {
    setEditing(word);
    form.setFieldsValue({
      word: word.word,
      phonetic: word.phonetic,
      translation: word.translation,
      example_en: word.example_en,
      example_cn: word.example_cn,
    });
  };

  const submit = async (values: WordUpsertPayload) => {
    try {
      if (creating) {
        await createWord(numericId, values);
        Message.success({ content: "词条已新增" });
        setCreating(false);
      } else if (editing) {
        await updateWord(editing.id, values);
        Message.success({ content: "词条已更新" });
        setEditing(null);
      }
      form.resetFields();
      await load();
    } catch (error) {
      // 校验失败的文案由后端给出，直接原样展示
      Message.error({ content: toMessage(error) });
    }
  };

  const handleExport = async () => {
    try {
      const payload = await exportWordbook(numericId);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${String(payload.code ?? "wordbook")}.json`;
      link.click();
      URL.revokeObjectURL(url);
      Message.success({ content: "已导出，可直接写回 data/ 目录" });
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const handleImport = async (file: File) => {
    let payload: unknown;
    try {
      payload = JSON.parse(await file.text());
    } catch {
      Message.error({ content: "文件不是有效的 JSON" });
      return false;
    }

    setImporting(true);
    setIssues([]);
    setImportMessage("");
    try {
      const result = await importWordbooks(payload);
      Message.success({
        content: `导入完成：新增 ${result.words_created} 词、更新 ${result.words_updated} 词`,
      });
      setImporting(false);
      await load();
    } catch (error) {
      setImporting(false);
      const detail = error instanceof RequestError ? error.detail : null;
      if (detail && typeof detail === "object" && "issues" in detail) {
        const failure = detail as unknown as ImportFailureDetail;
        setImportMessage(failure.message);
        setIssues(failure.issues);
      } else {
        Message.error({ content: toMessage(error) });
      }
    }
    // 阻止组件库自动上传，导入完全在前端读文件后走接口
    return false;
  };

  const wordForm = (
    <Form form={form} layout="vertical" onSubmit={submit}>
      <Form.Item
        label="单词"
        field="word"
        rules={[{ required: true, message: "请输入单词" }]}
      >
        <Input className="focus-ring" spellCheck={false} disabled={Boolean(editing)} />
      </Form.Item>
      <Form.Item
        label="音标"
        field="phonetic"
        rules={[{ required: true, message: "请输入音标" }]}
        extra="必须用 / / 包裹，例如 /əˈbændən/"
      >
        <Input className="focus-ring" spellCheck={false} />
      </Form.Item>
      <Form.Item
        label="释义"
        field="translation"
        rules={[{ required: true, message: "请输入释义" }]}
        extra="以词性开头，例如 v. 放弃，遗弃"
      >
        <Input className="focus-ring" />
      </Form.Item>
      <Form.Item
        label="英文例句"
        field="example_en"
        rules={[{ required: true, message: "请输入英文例句" }]}
        extra="必须包含目标词本身"
      >
        <Input.TextArea className="focus-ring" autoSize={{ minRows: 2, maxRows: 4 }} />
      </Form.Item>
      <Form.Item label="中文例句" field="example_cn" rules={[{ required: true, message: "请输入中文例句" }]}>
        <Input.TextArea className="focus-ring" autoSize={{ minRows: 2, maxRows: 4 }} />
      </Form.Item>
    </Form>
  );

  return (
    <Card className="card">
      <Space
        size={8}
        wrap
        style={{ width: "100%", justifyContent: "space-between", marginBottom: 14 }}
      >
        <Space size={10} align="center" wrap>
          <Button
            className="focus-ring"
            size="small"
            icon={<IconLeft />}
            onClick={() => navigate("/wordbooks")}
          >
            返回词书
          </Button>
          <Typography.Title heading={5} style={{ margin: 0 }}>
            {bookTitle || "词条管理"}
          </Typography.Title>
          <Tag size="small" color="arcoblue">
            共 {total} 条
          </Tag>
        </Space>
        <Space size={8} wrap>
          <label style={{ display: "inline-flex" }}>
            <input
              type="file"
              accept=".json,application/json"
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleImport(file);
                event.target.value = "";
              }}
            />
            <span>
              <Button className="focus-ring" icon={<IconImport />} disabled={importing}>
                批量导入
              </Button>
            </span>
          </label>
          <Button className="focus-ring" icon={<IconExport />} onClick={() => void handleExport()}>
            导出 JSON
          </Button>
          <Button type="primary" className="focus-ring" icon={<IconPlus />} onClick={openCreate}>
            新增词条
          </Button>
        </Space>
      </Space>

      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 10 }}>
        导入先校验后入库，任一条不通过则整批拒绝，下面会列出错在第几条哪个词；导出格式与
        data/*.json 一致，可直接写回仓库。
      </Typography.Text>

      {issues.length > 0 && (
        <div
          data-testid="import-issues"
          style={{
            marginBottom: 12,
            padding: "10px 12px",
            borderRadius: "var(--border-radius-md)",
            background: "var(--color-danger-soft)",
          }}
        >
          <Typography.Text type="error" style={{ fontWeight: 600 }}>
            {importMessage}
          </Typography.Text>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18, maxHeight: 200, overflowY: "auto" }}>
            {issues.map((issue, index) => (
              <li key={`${issue.field}-${index}`} style={{ fontSize: 13 }}>
                <code style={{ color: "var(--text-2)" }}>{issue.field}</code> · {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <Space size={8} wrap style={{ marginBottom: 12 }}>
        <Input
          className="focus-ring"
          placeholder="按单词搜索"
          value={search}
          allowClear
          style={{ width: 200 }}
          onChange={(value) => {
            setSearch(value);
            setOffset(0);
          }}
        />
        <Select
          placeholder="状态"
          allowClear
          className="focus-ring"
          style={{ width: 130 }}
          value={status || undefined}
          onChange={(value) => {
            setStatus(value ?? "");
            setOffset(0);
          }}
          options={[
            { label: "上架中", value: "active" },
            { label: "已下架", value: "archived" },
          ]}
        />
        <Button className="focus-ring" icon={<IconRefresh />} onClick={() => void load()}>
          刷新
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        pagination={{
          total,
          pageSize: limit,
          current: Math.floor(offset / limit) + 1,
          onChange: (page) => setOffset((page - 1) * limit),
          showTotal: (count) => `共 ${count} 条`,
        }}
        noDataElement={<Empty description="还没有词条，可新增或批量导入" />}
        columns={[
          { title: "单词", dataIndex: "word", width: 140 },
          {
            title: "音标",
            dataIndex: "phonetic",
            width: 150,
            render: (value: string) => <span style={{ fontFamily: "monospace" }}>{value}</span>,
          },
          { title: "释义", dataIndex: "translation" },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (value: string) =>
              value === "archived" ? (
                <Tag color="gray" size="small">
                  [已下架]
                </Tag>
              ) : (
                <Tag color="green" size="small">
                  [上架中]
                </Tag>
              ),
          },
          {
            title: "操作",
            width: 250,
            render: (_, row: WordAdminOut) => (
              <Space size={6}>
                <Button size="mini" className="focus-ring" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Button
                  size="mini"
                  className="focus-ring"
                  onClick={() =>
                    run(
                      () =>
                        setWordStatus(
                          row.id,
                          row.status === "active" ? "archived" : "active"
                        ),
                      row.status === "active" ? "已下架" : "已重新上架"
                    )
                  }
                >
                  {row.status === "active" ? "下架" : "上架"}
                </Button>
                <Popconfirm
                  title="物理删除该词条？仅在没有任何用户练习记录时允许"
                  okText="确认删除"
                  cancelText="取消"
                  onOk={async () => {
                    try {
                      await deleteWord(row.id, true);
                      Message.success({ content: "已物理删除" });
                      await load();
                    } catch (error) {
                      // 有引用时后端会拒绝并说明原因，这里如实转达
                      Message.error({ content: toMessage(error) });
                    }
                  }}
                >
                  <Button size="mini" status="danger" className="focus-ring">
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        visible={creating || Boolean(editing)}
        title={creating ? "新增词条" : "编辑词条"}
        okText="保存"
        cancelText="取消"
        style={{ width: 560 }}
        onCancel={() => {
          setCreating(false);
          setEditing(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
      >
        {wordForm}
      </Modal>
    </Card>
  );
}
