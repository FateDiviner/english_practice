import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
} from "@arco-design/web-react";
import { IconPlus, IconRefresh } from "@arco-design/web-react/icon";
import { useNavigate } from "react-router-dom";
import { createWordbook, fetchWordbooks, updateWordbook } from "@/api/words";
import { toMessage } from "@/api/client";
import type { WordbookAdminOut, WordbookCreatePayload } from "@/types";

/** 词书管理：列表、新建、编辑与上架 / 下架 */
export default function WordbooksPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<WordbookAdminOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<WordbookAdminOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<WordbookCreatePayload>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await fetchWordbooks());
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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

  const openEdit = (book: WordbookAdminOut) => {
    setEditing(book);
    form.setFieldsValue({
      code: book.code,
      title: book.title,
      description: book.description,
      difficulty: book.difficulty,
    });
  };

  const submit = async (values: WordbookCreatePayload) => {
    if (creating) {
      await run(() => createWordbook(values), "词书已创建");
      setCreating(false);
    } else if (editing) {
      await run(() => updateWordbook(editing.id, values), "词书已更新");
      setEditing(null);
    }
    form.resetFields();
  };

  return (
    <Card className="card" title="词书管理">
      <Space size={8} wrap style={{ marginBottom: 14 }}>
        <Button type="primary" className="focus-ring" icon={<IconPlus />} onClick={openCreate}>
          新建词书
        </Button>
        <Button className="focus-ring" icon={<IconRefresh />} onClick={() => void load()}>
          刷新
        </Button>
        <Typography.Text type="secondary">
          下架的词书对用户完全隐藏，但练习记录与备份一律保留
        </Typography.Text>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        pagination={false}
        columns={[
          { title: "Code", dataIndex: "code", width: 130 },
          { title: "名称", dataIndex: "title", width: 220 },
          { title: "难度", dataIndex: "difficulty", width: 90 },
          {
            title: "状态",
            dataIndex: "status",
            width: 110,
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
          { title: "可用词数", dataIndex: "total_words", width: 100 },
          {
            title: "已下架词",
            dataIndex: "archived_words",
            width: 100,
            render: (value: number) => (value > 0 ? value : "—"),
          },
          { title: "被激活用户", dataIndex: "active_users", width: 110 },
          {
            title: "操作",
            width: 280,
            render: (_, row: WordbookAdminOut) => (
              <Space size={6}>
                <Button
                  size="mini"
                  className="focus-ring"
                  onClick={() => navigate(`/wordbooks/${row.id}`)}
                >
                  词条
                </Button>
                <Button size="mini" className="focus-ring" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Popconfirm
                  title={
                    row.status === "active"
                      ? "下架该词书？用户端将不再展示，练习记录保留"
                      : "重新上架该词书？"
                  }
                  okText="确认"
                  cancelText="取消"
                  onOk={() =>
                    run(
                      () =>
                        updateWordbook(row.id, {
                          status: row.status === "active" ? "archived" : "active",
                        }),
                      row.status === "active" ? "已下架" : "已重新上架"
                    )
                  }
                >
                  <Button size="mini" className="focus-ring">
                    {row.status === "active" ? "下架" : "上架"}
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        visible={creating || Boolean(editing)}
        title={creating ? "新建词书" : "编辑词书"}
        okText="保存"
        cancelText="取消"
        onCancel={() => {
          setCreating(false);
          setEditing(null);
          form.resetFields();
        }}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onSubmit={submit}>
          <Form.Item
            label="Code"
            field="code"
            rules={[
              { required: true, message: "请输入 code" },
              { match: /^[a-z0-9_-]+$/, message: "只能是小写字母、数字、下划线与连字符" },
            ]}
            extra={editing ? "code 作为备份与导入的定位键，建议不要改动" : undefined}
          >
            <Input className="focus-ring" disabled={Boolean(editing)} />
          </Form.Item>
          <Form.Item label="名称" field="title" rules={[{ required: true, message: "请输入名称" }]}>
            <Input className="focus-ring" />
          </Form.Item>
          <Form.Item label="简介" field="description">
            <Input.TextArea className="focus-ring" autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Form.Item label="难度标签" field="difficulty">
            <Input className="focus-ring" placeholder="如：四级 / 六级" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
