import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
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
import { IconPlus, IconRefresh, IconSearch } from "@arco-design/web-react/icon";
import { createUser, deleteUser, fetchUsers, updateUser } from "@/api/users";
import { toMessage } from "@/api/client";
import type { AdminUserOut, CreateUserPayload } from "@/types";

const ROLE_LABEL: Record<string, string> = { admin: "管理员", user: "普通用户" };

function StatusTag({ status }: { status: string }) {
  return status === "banned" ? (
    <Tag color="red" size="small">
      [已封禁]
    </Tag>
  ) : (
    <Tag color="green" size="small">
      [正常]
    </Tag>
  );
}

/** 用户管理：查询、代建、启用/封禁、改角色、删除 */
export default function UsersPage({ currentUser }: { currentUser: AdminUserOut | null }) {
  const [rows, setRows] = useState<AdminUserOut[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<CreateUserPayload & { confirm?: string }>();

  const limit = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const page = await fetchUsers({
        search: search.trim() || undefined,
        role: role || undefined,
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
  }, [search, role, status, offset]);

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

  const handleCreate = async (values: CreateUserPayload & { confirm?: string }) => {
    if (values.password !== values.confirm) {
      Message.error({ content: "两次输入的密码不一致" });
      return;
    }
    await run(
      () =>
        createUser({
          username: values.username.trim(),
          password: values.password,
          role: values.role,
        }),
      "用户已创建"
    );
    setCreating(false);
    form.resetFields();
  };

  const isSelf = (row: AdminUserOut) => currentUser?.id === row.id;

  return (
    <Card className="card" title="用户管理">
      <Space size={8} wrap style={{ marginBottom: 14 }}>
        <Input
          className="focus-ring"
          placeholder="按用户名搜索"
          prefix={<IconSearch />}
          value={search}
          allowClear
          style={{ width: 200 }}
          onChange={(value) => {
            setSearch(value);
            setOffset(0);
          }}
        />
        <Select
          placeholder="角色"
          allowClear
          style={{ width: 130 }}
          className="focus-ring"
          value={role || undefined}
          onChange={(value) => {
            setRole(value ?? "");
            setOffset(0);
          }}
          options={[
            { label: "管理员", value: "admin" },
            { label: "普通用户", value: "user" },
          ]}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 130 }}
          className="focus-ring"
          value={status || undefined}
          onChange={(value) => {
            setStatus(value ?? "");
            setOffset(0);
          }}
          options={[
            { label: "正常", value: "active" },
            { label: "已封禁", value: "banned" },
          ]}
        />
        <Button className="focus-ring" icon={<IconRefresh />} onClick={() => void load()}>
          刷新
        </Button>
        <Button
          type="primary"
          className="focus-ring"
          icon={<IconPlus />}
          onClick={() => setCreating(true)}
        >
          新增用户
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
          showTotal: (count) => `共 ${count} 人`,
        }}
        columns={[
          { title: "用户名", dataIndex: "username", width: 160 },
          {
            title: "角色",
            dataIndex: "role",
            width: 110,
            render: (value: string) => (
              <Tag size="small" color={value === "admin" ? "arcoblue" : "gray"}>
                {ROLE_LABEL[value] ?? value}
              </Tag>
            ),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 110,
            render: (value: string) => <StatusTag status={value} />,
          },
          {
            title: "类型",
            dataIndex: "is_guest",
            width: 90,
            render: (value: boolean) => (value ? "游客" : "正式"),
          },
          { title: "练习次数", dataIndex: "practice_count", width: 100 },
          {
            title: "最近活跃",
            dataIndex: "last_practiced_at",
            width: 170,
            render: (value: string | null) => value ?? "从未练习",
          },
          {
            title: "操作",
            width: 260,
            render: (_, row: AdminUserOut) => (
              <Space size={6}>
                <Popconfirm
                  title={row.role === "admin" ? "降级为普通用户？" : "升级为管理员？"}
                  okText="确认"
                  cancelText="取消"
                  disabled={isSelf(row)}
                  onOk={() =>
                    run(
                      () =>
                        updateUser(row.id, {
                          role: row.role === "admin" ? "user" : "admin",
                        }),
                      "角色已更新"
                    )
                  }
                >
                  <Button
                    size="mini"
                    className="focus-ring"
                    disabled={isSelf(row)}
                    title={isSelf(row) ? "不能修改自己的角色" : undefined}
                  >
                    {row.role === "admin" ? "降级" : "升级"}
                  </Button>
                </Popconfirm>

                <Popconfirm
                  title={row.status === "banned" ? "解除封禁？" : "封禁该账号？"}
                  okText="确认"
                  cancelText="取消"
                  disabled={isSelf(row)}
                  onOk={() =>
                    run(
                      () =>
                        updateUser(row.id, {
                          status: row.status === "banned" ? "active" : "banned",
                        }),
                      row.status === "banned" ? "已解封" : "已封禁"
                    )
                  }
                >
                  <Button
                    size="mini"
                    className="focus-ring"
                    disabled={isSelf(row)}
                    title={isSelf(row) ? "不能封禁自己" : undefined}
                  >
                    {row.status === "banned" ? "启用" : "封禁"}
                  </Button>
                </Popconfirm>

                <Popconfirm
                  title="删除该用户及其全部练习数据？"
                  okText="确认删除"
                  cancelText="取消"
                  disabled={isSelf(row)}
                  onOk={() =>
                    run(() => deleteUser(row.id), "用户已删除，练习数据已级联清理")
                  }
                >
                  <Button
                    size="mini"
                    status="danger"
                    className="focus-ring"
                    disabled={isSelf(row)}
                    title={isSelf(row) ? "不能删除自己" : undefined}
                  >
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        visible={creating}
        title="新增用户"
        okText="创建"
        cancelText="取消"
        onCancel={() => setCreating(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onSubmit={handleCreate}>
          <Form.Item
            label="用户名"
            field="username"
            rules={[
              { required: true, message: "请输入用户名" },
              { minLength: 3, message: "用户名至少 3 个字符" },
            ]}
          >
            <Input className="focus-ring" />
          </Form.Item>
          <Form.Item
            label="密码"
            field="password"
            rules={[
              { required: true, message: "请输入密码" },
              { minLength: 6, message: "密码至少 6 位" },
            ]}
          >
            <Input.Password className="focus-ring" />
          </Form.Item>
          <Form.Item
            label="确认密码"
            field="confirm"
            rules={[{ required: true, message: "请再次输入密码" }]}
          >
            <Input.Password className="focus-ring" />
          </Form.Item>
          <Form.Item label="角色" field="role" initialValue="user">
            <Select
              className="focus-ring"
              options={[
                { label: "普通用户", value: "user" },
                { label: "管理员", value: "admin" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Typography.Text type="secondary" style={{ display: "block", marginTop: 12 }}>
        封禁会立即生效：该账号无法登录，已有令牌在下次请求时就作废。删除会级联清掉
        该用户的词状态、练习记录与对话历史，且不可恢复。
      </Typography.Text>
    </Card>
  );
}
