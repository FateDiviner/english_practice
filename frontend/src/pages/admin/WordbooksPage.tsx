import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Space,
  Tag,
} from "@arco-design/web-react";

import { createWordbook, fetchAdminWordbooks, updateWordbook } from "@/api/admin";
import RecordCard from "@/components/RecordCard";
import ResponsiveList from "@/components/ResponsiveList";
import { toMessage } from "@/api/client";
import type { AdminWordbook, ContentStatus } from "@/types";

interface BookFormValues {
  code: string;
  title: string;
  description: string;
  difficulty: string;
}

export default function WordbooksPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<AdminWordbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<AdminWordbook | null>(null);
  const [form] = Form.useForm<BookFormValues>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchAdminWordbooks());
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setVisible(true);
  };

  const openEdit = (row: AdminWordbook) => {
    setEditing(row);
    form.setFieldsValue({
      code: row.code,
      title: row.title,
      description: row.description,
      difficulty: row.difficulty,
    });
    setVisible(true);
  };

  const submit = async () => {
    const values = await form.validate();
    setSaving(true);
    try {
      if (editing) {
        await updateWordbook(editing.id, {
          title: values.title,
          description: values.description,
          difficulty: values.difficulty,
        });
        Message.success({ content: "词书已更新" });
      } else {
        await createWordbook(values);
        Message.success({ content: `已创建词书 ${values.code}` });
      }
      setVisible(false);
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setSaving(false);
    }
  };

  const toggleStatus = async (row: AdminWordbook) => {
    const next: ContentStatus = row.status === "active" ? "archived" : "active";
    try {
      await updateWordbook(row.id, { status: next });
      Message.success({
        content: next === "archived" ? `已下架 ${row.title}` : `已上架 ${row.title}`,
      });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>词书管理</h2>
          <p style={{ margin: "4px 0 0", color: "var(--text-2)", fontSize: 13 }}>
            下架的词书对用户完全隐藏，但练习记录与备份一律保留。
          </p>
        </div>
        <Space>
          <Button onClick={() => void load()}>刷新</Button>
          <Button type="primary" onClick={openCreate}>
            新建词书
          </Button>
        </Space>
      </header>

      <ResponsiveList
        rowKey="id"
        loading={loading}
        data={items}
        noDataElement="还没有词书"
        pagination={false}
        renderCard={(row) => (
          <RecordCard
            title={row.title}
            tags={[
              <Tag key="c" size="small"><code>{row.code}</code></Tag>,
              <Tag key="s" size="small" color={row.status === "active" ? "green" : "gray"}>
                {row.status === "active" ? "[上架中]" : "[已下架]"}
              </Tag>,
            ]}
            fields={[
              { label: "难度", value: row.difficulty || "-" },
              { label: "可用词数", value: row.total_words },
              { label: "已下架词", value: row.archived_words },
              { label: "被激活用户", value: row.active_users },
            ]}
            actions={
              <Space size={4} wrap>
                <Button size="small" onClick={() => navigate(`/admin/wordbooks/${row.id}`)}>
                  词条
                </Button>
                <Button size="small" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Popconfirm
                  title={
                    row.status === "active"
                      ? "下架该词书？用户端将不再展示，练习记录保留"
                      : "上架该词书？"
                  }
                  okText="确认"
                  cancelText="取消"
                  onOk={() => void toggleStatus(row)}
                >
                  <Button size="small" status={row.status === "active" ? "danger" : "default"}>
                    {row.status === "active" ? "下架" : "上架"}
                  </Button>
                </Popconfirm>
              </Space>
            }
          />
        )}
        columns={[
          {
            title: "code",
            dataIndex: "code",
            width: 120,
            render: (value: string) => <code>{value}</code>,
          },
          { title: "名称", dataIndex: "title" },
          { title: "难度", dataIndex: "difficulty", width: 90 },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (value: ContentStatus) =>
              value === "active" ? (
                <Tag color="green">[上架中]</Tag>
              ) : (
                <Tag color="gray">[已下架]</Tag>
              ),
          },
          { title: "可用词数", dataIndex: "total_words", width: 100 },
          { title: "已下架词", dataIndex: "archived_words", width: 100 },
          { title: "被激活用户", dataIndex: "active_users", width: 110 },
          {
            title: "操作",
            width: 230,
            render: (_, row: AdminWordbook) => (
              <Space size={4}>
                <Button size="small" onClick={() => navigate(`/admin/wordbooks/${row.id}`)}>
                  词条
                </Button>
                <Button size="small" onClick={() => openEdit(row)}>
                  编辑
                </Button>
                <Popconfirm
                  title={
                    row.status === "active"
                      ? "下架该词书？用户端将不再展示，练习记录保留"
                      : "上架该词书？"
                  }
                  okText="确认"
                  cancelText="取消"
                  onOk={() => toggleStatus(row)}
                >
                  <Button size="small" status={row.status === "active" ? "danger" : "default"}>
                    {row.status === "active" ? "下架" : "上架"}
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? "编辑词书" : "新建词书"}
        visible={visible}
        okText={editing ? "保存" : "创建"}
        cancelText="取消"
        confirmLoading={saving}
        onCancel={() => setVisible(false)}
        onOk={() => void submit()}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="code"
            field="code"
            disabled={Boolean(editing)}
            extra={editing ? "code 作为备份与导入的定位键，建议不要改动" : "小写字母、数字、下划线与短横线"}
            rules={[
              { required: true, message: "请输入 code" },
              { match: /^[a-z0-9_-]{2,32}$/, message: "2~32 位，仅限小写字母、数字、_ 与 -" },
            ]}
          >
            <Input placeholder="例如 cet4" />
          </Form.Item>
          <Form.Item
            label="名称"
            field="title"
            rules={[{ required: true, message: "请输入名称" }]}
          >
            <Input placeholder="例如 大学英语四级核心高频词" />
          </Form.Item>
          <Form.Item label="简介" field="description">
            <Input.TextArea placeholder="给用户看的一句话说明" />
          </Form.Item>
          <Form.Item label="难度" field="difficulty">
            <Input placeholder="例如 初级 / 中级 / 高级" />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
}
