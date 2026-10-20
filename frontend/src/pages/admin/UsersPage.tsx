import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
} from "@arco-design/web-react";

import {
  createAdminUser,
  deleteUser,
  fetchUsers,
  updateUser,
} from "@/api/admin";
import { toMessage } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import type { AdminUser, UserRole, UserStatus } from "@/types";

const PAGE_SIZE = 20;

const ROLE_LABEL: Record<UserRole, string> = { admin: "管理员", user: "普通用户" };
const STATUS_LABEL: Record<UserStatus, string> = { active: "[正常]", banned: "[已封禁]" };

interface FormValues {
  username: string;
  password: string;
  confirm: string;
  role: UserRole;
}

export default function UsersPage() {
  const me = useAuthStore((state) => state.user);
  const [items, setItems] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | undefined>();
  const [statusFilter, setStatusFilter] = useState<UserStatus | undefined>();
  const [page, setPage] = useState(1);
  const [createVisible, setCreateVisible] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm<FormValues>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchUsers({
        search: search || undefined,
        role: roleFilter,
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
  }, [search, roleFilter, statusFilter, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const isSelf = (row: AdminUser) => row.id === me?.id;

  const toggleRole = async (row: AdminUser) => {
    const next: UserRole = row.role === "admin" ? "user" : "admin";
    try {
      await updateUser(row.id, { role: next });
      Message.success({ content: `已将 ${row.username} 设为${ROLE_LABEL[next]}` });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const toggleStatus = async (row: AdminUser) => {
    const next: UserStatus = row.status === "active" ? "banned" : "active";
    try {
      await updateUser(row.id, { status: next });
      Message.success({
        content:
          next === "banned"
            ? `已封禁 ${row.username}，其现有令牌立即失效`
            : `已启用 ${row.username}`,
      });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const remove = async (row: AdminUser) => {
    try {
      const result = await deleteUser(row.id);
      Message.success({
        content: `已删除 ${row.username}，连带清理 ${result.affected_rows} 条练习数据`,
      });
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    }
  };

  const submitCreate = async () => {
    const values = await form.validate();
    if (values.password !== values.confirm) {
      Message.error({ content: "两次输入的密码不一致" });
      return;
    }
    setCreating(true);
    try {
      await createAdminUser({
        username: values.username,
        password: values.password,
        role: values.role,
      });
      Message.success({ content: `已创建 ${values.username}` });
      setCreateVisible(false);
      form.resetFields();
      await load();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setCreating(false);
    }
  };

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>用户管理</h2>
          <p style={{ margin: "4px 0 0", color: "var(--text-2)", fontSize: 13 }}>
            封禁即时生效，已有令牌在下次请求时立即失效；删除会连带清理该用户的全部练习数据。
          </p>
        </div>
        <Button type="primary" onClick={() => setCreateVisible(true)}>
          新建用户
        </Button>
      </header>

      <Space wrap>
        <Input.Search
          placeholder="按用户名搜索"
          allowClear
          style={{ width: 220 }}
          onSearch={(value) => {
            setSearch(value.trim());
            setPage(1);
          }}
        />
        <Select
          placeholder="角色"
          allowClear
          style={{ width: 130 }}
          value={roleFilter}
          onChange={(value) => {
            setRoleFilter(value as UserRole | undefined);
            setPage(1);
          }}
          options={[
            { label: ROLE_LABEL.admin, value: "admin" },
            { label: ROLE_LABEL.user, value: "user" },
          ]}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 130 }}
          value={statusFilter}
          onChange={(value) => {
            setStatusFilter(value as UserStatus | undefined);
            setPage(1);
          }}
          options={[
            { label: "[正常]", value: "active" },
            { label: "[已封禁]", value: "banned" },
          ]}
        />
        <Button onClick={() => void load()}>刷新</Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        data={items}
        pagination={{
          total,
          pageSize: PAGE_SIZE,
          current: page,
          onChange: (next) => setPage(next),
          showTotal: true,
        }}
        noDataElement="还没有其他用户"
        columns={[
          {
            title: "ID",
            dataIndex: "id",
            width: 70,
          },
          {
            title: "用户名",
            dataIndex: "username",
            render: (value: string, row: AdminUser) => (
              <Space>
                <span>{value}</span>
                {row.is_guest && <Tag size="small">[游客]</Tag>}
                {isSelf(row) && <Tag size="small" color="arcoblue">[我]</Tag>}
              </Space>
            ),
          },
          {
            title: "角色",
            dataIndex: "role",
            width: 110,
            render: (value: UserRole) => (
              <Tag color={value === "admin" ? "orangered" : "gray"}>{ROLE_LABEL[value]}</Tag>
            ),
          },
          {
            title: "状态",
            dataIndex: "status",
            width: 100,
            render: (value: UserStatus) => (
              <Tag color={value === "banned" ? "red" : "green"}>{STATUS_LABEL[value]}</Tag>
            ),
          },
          {
            title: "练习次数",
            dataIndex: "practice_count",
            width: 100,
          },
          {
            title: "最近活跃",
            dataIndex: "last_practiced_at",
            width: 170,
            render: (value: string | null) => value ?? "从未练习",
          },
          {
            title: "注册时间",
            dataIndex: "created_at",
            width: 170,
            render: (value: string) => value.slice(0, 19).replace("T", " "),
          },
          {
            title: "操作",
            width: 250,
            render: (_, row: AdminUser) => {
              const nextRole: UserRole = row.role === "admin" ? "user" : "admin";
              const nextStatus: UserStatus = row.status === "active" ? "banned" : "active";
              return (
                <Space wrap size={4}>
                  <Tooltip content={isSelf(row) ? "不能修改自己的角色" : ""}>
                    <Popconfirm
                      title={row.is_guest ? "该账号是游客，确定提升为管理员？" : `设为${ROLE_LABEL[nextRole]}？`}
                      okText="确认"
                      cancelText="取消"
                      disabled={isSelf(row)}
                      onOk={() => toggleRole(row)}
                    >
                      <Button size="small" disabled={isSelf(row)}>
                        {nextRole === "admin" ? "升为管理员" : "降为普通用户"}
                      </Button>
                    </Popconfirm>
                  </Tooltip>
                  <Tooltip content={isSelf(row) ? "不能封禁自己" : ""}>
                    <Popconfirm
                      title={nextStatus === "banned" ? "封禁该账号？其现有令牌将立即失效" : "启用该账号？"}
                      okText="确认"
                      cancelText="取消"
                      disabled={isSelf(row)}
                      onOk={() => toggleStatus(row)}
                    >
                      <Button size="small" status={nextStatus === "banned" ? "danger" : "default"} disabled={isSelf(row)}>
                        {nextStatus === "banned" ? "封禁" : "启用"}
                      </Button>
                    </Popconfirm>
                  </Tooltip>
                  <Tooltip content={isSelf(row) ? "不能删除自己" : ""}>
                    <Popconfirm
                      title="删除该用户及其全部练习数据？"
                      okText="确认删除"
                      cancelText="取消"
                      disabled={isSelf(row)}
                      onOk={() => remove(row)}
                    >
                      <Button size="small" status="danger" disabled={isSelf(row)}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Tooltip>
                </Space>
              );
            },
          },
        ]}
      />

      <Modal
        title="新建用户"
        visible={createVisible}
        okText="创建"
        cancelText="取消"
        confirmLoading={creating}
        onCancel={() => setCreateVisible(false)}
        onOk={() => void submitCreate()}
      >
        <Form form={form} layout="vertical" initialValues={{ role: "user" as UserRole }}>
          <Form.Item
            label="用户名"
            field="username"
            rules={[
              { required: true, message: "请输入用户名" },
              { minLength: 3, message: "至少 3 个字符" },
            ]}
          >
            <Input placeholder="至少 3 个字符" />
          </Form.Item>
          <Form.Item
            label="密码"
            field="password"
            rules={[
              { required: true, message: "请输入密码" },
              { minLength: 6, message: "至少 6 位" },
            ]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
          <Form.Item
            label="确认密码"
            field="confirm"
            rules={[{ required: true, message: "请再次输入密码" }]}
          >
            <Input.Password placeholder="再输一次" />
          </Form.Item>
          <Form.Item label="角色" field="role">
            <Select
              options={[
                { label: ROLE_LABEL.user, value: "user" },
                { label: ROLE_LABEL.admin, value: "admin" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  );
}
