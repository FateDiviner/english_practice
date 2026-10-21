import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Button,
  Empty,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
} from "@arco-design/web-react";

import {
  createRelation,
  createWord,
  deleteRelation,
  deleteWord,
  exportWordbook,
  extractIssues,
  fetchAdminWords,
  fetchRelations,
  importWordsIntoBook,
  setWordStatus,
  updateWord,
  type WordPayload,
} from "@/api/admin";
import RecordCard from "@/components/RecordCard";
import ResponsiveList from "@/components/ResponsiveList";
import { toMessage } from "@/api/client";
import type {
  AdminWord,
  ContentStatus,
  ValidationIssue,
  WordRelation,
  WordRelationType,
} from "@/types";

const PAGE_SIZE = 20;

const RELATION_LABEL: Record<WordRelationType, string> = {
  collocation: "[搭配]",
  derived: "[派生]",
  confuse: "[易混]",
  synonym: "[近义]",
  antonym: "[反义]",
};

export default function WordbookDetailPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const numericId = Number(bookId);

  const [items, setItems] = useState<AdminWord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ContentStatus | undefined>();
  const [page, setPage] = useState(1);

  const [wordVisible, setWordVisible] = useState(false);
  const [wordSaving, setWordSaving] = useState(false);
  const [editingWord, setEditingWord] = useState<AdminWord | null>(null);
  const [wordForm] = Form.useForm<WordPayload>();

  const [importing, setImporting] = useState(false);
  const [importFailure, setImportFailure] = useState<{ message: string; issues: ValidationIssue[] } | null>(null);

  const [relationWord, setRelationWord] = useState<AdminWord | null>(null);
  const [relations, setRelations] = useState<WordRelation[]>([]);
  const [relationForm] = Form.useForm<{ tail_word: string; relation: WordRelationType; note: string }>();

  const load = useCallback(async () => {
    if (!Number.isFinite(numericId)) return;
    setLoading(true);
    try {
      const result = await fetchAdminWords(numericId, {
        search: search || undefined,
        status: statusFilter,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [numericId, search, statusFilter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = () => {
    setEditingWord(null);
    wordForm.resetFields();
    setWordVisible(true);
  };

  const openEdit = (row: AdminWord) => {
    setEditingWord(row);
    wordForm.setFieldsValue({
      word: row.word,
      phonetic: row.phonetic,
      translation: row.translation,
      example_en: row.example_en,
      example_cn: row.example_cn,
    });
    setWordVisible(true);
  };

  const submitWord = async () => {
    const values = await wordForm.validate();
    setWordSaving(true);
    try {
      if (editingWord) {
        await updateWord(editingWord.id, values);
        Message.success({ content: "词条已更新" });
      } else {
        await createWord(numericId, values);
        Message.success({ content: `已新增 ${values.word}` });
      }
      setWordVisible(false);
      await load();
    } catch (error) {
      // 服务端 422 直接把 validator 的结论原样展示，不另写文案
      Message.error({ content: toMessage(error), duration: 6000 });
    } finally {
      setWordSaving(false);
    }
  };

  const toggleStatus = async (row: AdminWord) => {
    const next: ContentStatus = row.status === "active" ? "archived" : "active";
    try {
      await setWordStatus(row.id, next);
      Message.success({ content: next === "archived" ? `已下架 ${row.word}` : `已上架 ${row.word}` });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const remove = async (row: AdminWord, purge: boolean) => {
    try {
      await deleteWord(row.id, purge);
      Message.success({
        content: purge ? `已物理删除 ${row.word}` : `已下架 ${row.word}`,
      });
      await load();
    } catch (error) {
      // 零引用闸：有用户练习记录引用时后端会拒绝物理删除
      Message.error({ content: toMessage(error) });
    }
  };

  const handleImportFile = async (file: File) => {
    setImportFailure(null);
    let payload: unknown;
    try {
      payload = JSON.parse(await file.text());
    } catch {
      Message.error({ content: "文件不是有效的 JSON" });
      return;
    }

    // 词条管理页的导入作用于当前词书：兼容「单个词条对象 / 词条数组」两种直觉
    const words = Array.isArray(payload) ? payload : [payload];
    setImporting(true);
    try {
      const result = await importWordsIntoBook(numericId, words);
      Message.success({
        content: `导入完成：新增词条 ${result.words_created} 条、更新 ${result.words_updated} 条`,
      });
      await load();
    } catch (error) {
      // 任一条不通过则整批拒绝，issues 会告诉我们错在第几条哪个词
      const failure = extractIssues(error);
      if (failure) {
        setImportFailure(failure);
      } else {
        Message.error({ content: toMessage(error) });
      }
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    try {
      const payload = await exportWordbook(numericId);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${payload.code ?? bookId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      Message.success({ content: "已导出，可直接写回 data/ 目录" });
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const openRelations = async (row: AdminWord) => {
    setRelationWord(row);
    relationForm.resetFields();
    try {
      setRelations(await fetchRelations(row.id));
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const submitRelation = async () => {
    if (!relationWord) return;
    const values = await relationForm.validate();
    try {
      await createRelation(relationWord.id, {
        tail_word: values.tail_word,
        relation: values.relation,
        note: values.note,
      });
      Message.success({ content: "已添加关系" });
      relationForm.resetFields();
      setRelations(await fetchRelations(relationWord.id));
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const removeRelation = async (relation: WordRelation) => {
    if (!relationWord) return;
    try {
      await deleteRelation(relation.id);
      setRelations(await fetchRelations(relationWord.id));
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const importHint = useMemo(
    () =>
      "批量导入作用于当前词书：JSON 文件应为词条数组（也可单条对象），先校验后入库、任一条不通过则整批拒绝；导出格式与 data/*.json 的词条部分一致。",
    []
  );

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <Button size="small" onClick={() => navigate("/admin/wordbooks")}>
            返回词书列表
          </Button>
          <h2 style={{ margin: "8px 0 0", fontSize: 20 }}>词条管理</h2>
          <p style={{ margin: "4px 0 0", color: "var(--text-2)", fontSize: 13 }}>
            {importHint}
          </p>
        </div>
        <Space wrap>
          <Upload
            accept=".json,application/json"
            showUploadList={false}
            beforeUpload={(file) => {
              void handleImportFile(file);
              // 阻止 Arco 自动上传：导入完全在前端读文件后走接口
              return false;
            }}
          >
            <Button loading={importing}>批量导入</Button>
          </Upload>
          <Button onClick={() => void handleExport()}>导出</Button>
          <Button type="primary" onClick={openCreate}>
            新增词条
          </Button>
        </Space>
      </header>

      {importFailure && (
        <div
          data-testid="import-issues"
          style={{
            background: "var(--color-danger-soft)",
            borderRadius: "var(--border-radius-md)",
            padding: 12,
          }}
        >
          <Typography.Text type="error" bold>
            {importFailure.message}
          </Typography.Text>
          <ul style={{ margin: "8px 0 0", paddingLeft: 18, maxHeight: 200, overflowY: "auto" }}>
            {importFailure.issues.map((issue, index) => (
              <li key={`${issue.field}-${index}`} style={{ fontSize: 13, marginBottom: 4 }}>
                <code>{issue.field}</code> · {issue.message}
              </li>
            ))}
          </ul>
          <Button size="small" style={{ marginTop: 8 }} onClick={() => setImportFailure(null)}>
            收起
          </Button>
        </div>
      )}

      <Space wrap>
        <Input.Search
          placeholder="按单词搜索"
          allowClear
          style={{ width: 220 }}
          onSearch={(value) => {
            setSearch(value.trim());
            setPage(1);
          }}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 130 }}
          value={statusFilter}
          onChange={(value) => {
            setStatusFilter(value as ContentStatus | undefined);
            setPage(1);
          }}
          options={[
            { label: "[可用]", value: "active" },
            { label: "[已下架]", value: "archived" },
          ]}
        />
        <Button onClick={() => void load()}>刷新</Button>
      </Space>

      <ResponsiveList
        rowKey="id"
        loading={loading}
        data={items}
        noDataElement="还没有词条，可新增或批量导入"
        pagination={{
          total,
          pageSize: PAGE_SIZE,
          current: page,
          onChange: (next) => setPage(next),
          showTotal: true,
        }}
        renderCard={(row) => (
          <RecordCard
            title={row.word}
            tags={[
              <Tag key="p" size="small" className="phonetic-display">
                {row.phonetic}
              </Tag>,
              <Tag key="s" size="small" color={row.status === "active" ? "green" : "gray"}>
                {row.status === "active" ? "[可用]" : "[已下架]"}
              </Tag>,
            ]}
            fields={[
              { label: "释义", value: row.translation },
              { label: "例句", value: row.example_en },
            ]}
            actions={
              <Space size={4} wrap>
                <Button size="small" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Button size="small" onClick={() => void openRelations(row)}>
                  关系
                </Button>
                <Button
                  size="small"
                  status={row.status === "active" ? "danger" : "default"}
                  onClick={() => void toggleStatus(row)}
                >
                  {row.status === "active" ? "下架" : "上架"}
                </Button>
                <Popconfirm
                  title="物理删除该词条？仅在没有任何用户练习记录时允许"
                  okText="确认删除"
                  cancelText="取消"
                  onOk={() => void remove(row, true)}
                >
                  <Button size="small" status="danger">
                    物理删除
                  </Button>
                </Popconfirm>
              </Space>
            }
          />
        )}
        columns={[
          {
            title: "单词",
            dataIndex: "word",
            width: 160,
            render: (value: string, row: AdminWord) => (
              <Space size={4}>
                <span className="word-display" style={{ fontSize: 16 }}>
                  {value}
                </span>
                <Tag size="small" color={row.status === "active" ? "green" : "gray"}>
                  {row.status === "active" ? "[可用]" : "[已下架]"}
                </Tag>
              </Space>
            ),
          },
          { title: "音标", dataIndex: "phonetic", width: 140, className: "phonetic-display" },
          { title: "释义", dataIndex: "translation" },
          { title: "例句", dataIndex: "example_en", ellipsis: true },
          {
            title: "操作",
            width: 260,
            render: (_, row: AdminWord) => (
              <Space size={4} wrap>
                <Button size="small" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Button size="small" onClick={() => void openRelations(row)}>
                  关系
                </Button>
                <Button
                  size="small"
                  status={row.status === "active" ? "danger" : "default"}
                  onClick={() => void toggleStatus(row)}
                >
                  {row.status === "active" ? "下架" : "上架"}
                </Button>
                <Popconfirm
                  title="物理删除该词条？仅在没有任何用户练习记录时允许"
                  okText="确认删除"
                  cancelText="取消"
                  onOk={() => void remove(row, true)}
                >
                  <Button size="small" status="danger">
                    物理删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingWord ? "编辑词条" : "新增词条"}
        visible={wordVisible}
        okText={editingWord ? "保存" : "创建"}
        cancelText="取消"
        confirmLoading={wordSaving}
        onCancel={() => setWordVisible(false)}
        onOk={() => void submitWord()}
      >
        <Form form={wordForm} layout="vertical">
          <Form.Item
            label="单词"
            field="word"
            extra="小写词头，ASCII 字符"
            rules={[
              { required: true, message: "请输入单词" },
              { match: /^[a-z][a-z'-]*$/, message: "应为小写 ASCII 词头" },
            ]}
          >
            <Input placeholder="abandon" />
          </Form.Item>
          <Form.Item
            label="音标"
            field="phonetic"
            extra="必须用 / / 包裹，例如 /əˈbændən/"
            rules={[
              { required: true, message: "请输入音标" },
              { match: /^\/.{2,}\/$/, message: "必须用 / / 包裹" },
            ]}
          >
            <Input placeholder="/əˈbændən/" />
          </Form.Item>
          <Form.Item
            label="释义"
            field="translation"
            extra="以词性开头，例如 v. 放弃，遗弃"
            rules={[
              { required: true, message: "请输入释义" },
              {
                match: /^(conj|prep|pron|adj|adv|num|art|aux|intj|int|vt|vi|n|v)\b/,
                message: "需以词性前缀开头",
              },
            ]}
          >
            <Input placeholder="v. 放弃，遗弃" />
          </Form.Item>
          <Form.Item
            label="英文例句"
            field="example_en"
            extra="必须包含目标词本身，并以 . ! ? 结尾"
            rules={[{ required: true, message: "请输入英文例句" }]}
          >
            <Input.TextArea placeholder="They had to abandon the plan." />
          </Form.Item>
          <Form.Item
            label="中文例句"
            field="example_cn"
            extra="不得夹杂英文单词，以 。！？ 结尾"
            rules={[{ required: true, message: "请输入中文例句" }]}
          >
            <Input.TextArea placeholder="他们不得不放弃这个计划。" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={relationWord ? `词汇关系：${relationWord.word}` : "词汇关系"}
        visible={Boolean(relationWord)}
        footer={null}
        onCancel={() => setRelationWord(null)}
        style={{ width: 560 }}
      >
        <div style={{ display: "grid", gap: 12 }}>
          <Space wrap>
            <Form form={relationForm} layout="inline" style={{ gap: 8 }}>
              <Form.Item
                field="tail_word"
                rules={[{ required: true, message: "请输入对象" }]}
                style={{ marginBottom: 8 }}
              >
                <Input placeholder="give up" style={{ width: 140 }} />
              </Form.Item>
              <Form.Item
                field="relation"
                initialValue="synonym"
                rules={[{ required: true }]}
                style={{ marginBottom: 8 }}
              >
                <Select
                  style={{ width: 120 }}
                  options={Object.entries(RELATION_LABEL).map(([value, label]) => ({
                    label,
                    value,
                  }))}
                />
              </Form.Item>
              <Form.Item field="note" style={{ marginBottom: 8 }}>
                <Input placeholder="中文说明（可选）" style={{ width: 160 }} />
              </Form.Item>
              <Button type="primary" size="small" onClick={() => void submitRelation()}>
                添加
              </Button>
            </Form>
          </Space>

          {relations.length === 0 ? (
            <Empty description="还没有关系边" />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {relations.map((relation) => (
                <li key={relation.id} style={{ marginBottom: 6 }}>
                  <Tag size="small">{RELATION_LABEL[relation.relation]}</Tag>{" "}
                  <strong>{relation.tail_word}</strong>
                  {relation.note && (
                    <span style={{ color: "var(--text-2)", marginLeft: 8 }}>{relation.note}</span>
                  )}
                  <Popconfirm
                    title="删除该关系？"
                    okText="确认"
                    cancelText="取消"
                    onOk={() => void removeRelation(relation)}
                  >
                    <Button size="mini" status="danger" style={{ marginLeft: 8 }}>
                      删除
                    </Button>
                  </Popconfirm>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Modal>
    </section>
  );
}
