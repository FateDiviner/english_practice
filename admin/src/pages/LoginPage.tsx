import { useState } from "react";
import { Button, Card, Form, Input, Message, Typography } from "@arco-design/web-react";
import { IconLock, IconUser } from "@arco-design/web-react/icon";
import { login } from "@/api/auth";
import { setToken } from "@/api/client";
import { toMessage } from "@/api/client";
import type { AdminUser } from "@/types";

interface FormValues {
  username: string;
  password: string;
}

/** 管理端登录：只有管理员角色能进入，普通用户会被接口以 403 拒绝 */
export default function LoginPage({ onLoggedIn }: { onLoggedIn: (user: AdminUser) => void }) {
  const [pending, setPending] = useState(false);
  const [form] = Form.useForm<FormValues>();

  const handleSubmit = async (values: FormValues) => {
    setPending(true);
    try {
      const data = await login(values.username.trim(), values.password);
      if (data.user.role !== "admin") {
        Message.error({ content: "该账号不是管理员" });
        return;
      }
      setToken(data.access_token);
      Message.success({ content: "已进入管理端" });
      onLoggedIn(data.user);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setPending(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <Card className="card" style={{ width: 380, maxWidth: "100%" }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <Typography.Title heading={5} style={{ marginBottom: 4 }}>
            英语练习平台 · 管理端
          </Typography.Title>
          <Typography.Text type="secondary">仅限管理员访问</Typography.Text>
        </div>

        <Form form={form} layout="vertical" onSubmit={handleSubmit}>
          <Form.Item
            label="用户名"
            field="username"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input
              className="focus-ring"
              prefix={<IconUser />}
              autoComplete="username"
              disabled={pending}
            />
          </Form.Item>
          <Form.Item
            label="密码"
            field="password"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password
              className="focus-ring"
              prefix={<IconLock />}
              autoComplete="current-password"
              disabled={pending}
            />
          </Form.Item>
          <Button
            htmlType="submit"
            type="primary"
            long
            className="focus-ring"
            loading={pending}
          >
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
