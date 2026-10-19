import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Form,
  Input,
  Message,
  Tabs,
  Typography,
} from "@arco-design/web-react";
import { IconUser, IconLock } from "@arco-design/web-react/icon";
import { useAuthStore } from "@/stores/auth";
import { toMessage } from "@/api/client";

type Mode = "login" | "register";

interface FormValues {
  username: string;
  password: string;
  confirm?: string;
}

/** 登录 / 注册 / 一键游客体验 */
export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register, guest, pending } = useAuthStore();
  const [mode, setMode] = useState<Mode>("login");
  const [form] = Form.useForm<FormValues>();

  const enter = (message: string) => {
    Message.success({ content: message, duration: 2500 });
    navigate("/", { replace: true });
  };

  const handleSubmit = async (values: FormValues) => {
    try {
      if (mode === "register") {
        await register(values.username.trim(), values.password);
        enter("注册成功，欢迎开始练习");
      } else {
        const user = await login(values.username.trim(), values.password);
        enter(`欢迎回来，${user.username}`);
      }
    } catch (error) {
      Message.error({ content: toMessage(error), duration: 3500 });
    }
  };

  const handleGuest = async () => {
    try {
      await guest();
      enter("已进入游客体验模式，练习进度会在登录后自动迁移");
    } catch (error) {
      Message.error({ content: toMessage(error), duration: 3500 });
    }
  };

  const confirmValidator = (
    value: string | undefined,
    callback: (error?: ReactNode) => void
  ) => {
    if (!value || form.getFieldValue("password") === value) {
      callback();
      return;
    }
    callback("两次输入的密码不一致");
  };

  const passwordRules =
    mode === "register"
      ? [
          { required: true, message: "请输入密码" },
          { minLength: 6, message: "密码至少 6 位" },
        ]
      : [{ required: true, message: "请输入密码" }];

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
      <Card style={{ width: 400, maxWidth: "100%" }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <Typography.Title heading={4} style={{ marginBottom: 4 }}>
            英语练习平台
          </Typography.Title>
          <Typography.Text type="secondary">
            默写记忆 + AI 场景实战，一分钟开始练习
          </Typography.Text>
        </div>

        <Tabs activeTab={mode} onChange={(key) => setMode(key as Mode)} type="rounded">
          <Tabs.TabPane key="login" title="登录" />
          <Tabs.TabPane key="register" title="注册" />
        </Tabs>

        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 16 }}
          onSubmit={handleSubmit}
        >
          <Form.Item
            label="用户名"
            field="username"
            rules={[
              { required: true, message: "请输入用户名" },
              { minLength: 3, message: "用户名至少 3 个字符" },
            ]}
          >
            <Input
              className="focus-ring"
              prefix={<IconUser />}
              placeholder="至少 3 个字符"
              autoComplete="username"
              allowClear
              disabled={pending}
            />
          </Form.Item>

          <Form.Item label="密码" field="password" rules={passwordRules}>
            <Input.Password
              className="focus-ring"
              prefix={<IconLock />}
              placeholder={mode === "register" ? "至少 6 位" : "请输入密码"}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              disabled={pending}
            />
          </Form.Item>

          {mode === "register" && (
            <Form.Item
              label="确认密码"
              field="confirm"
              dependencies={["password"]}
              rules={[
                { required: true, message: "请再次输入密码" },
                { validator: confirmValidator },
              ]}
            >
              <Input.Password
                className="focus-ring"
                prefix={<IconLock />}
                placeholder="再次输入密码"
                autoComplete="new-password"
                disabled={pending}
              />
            </Form.Item>
          )}

          <Button
            htmlType="submit"
            type="primary"
            long
            loading={pending}
            className="focus-ring"
            style={{ marginTop: 8 }}
          >
            {mode === "login" ? "登录" : "注册并开始"}
          </Button>
        </Form>

        <Button
          long
          type="outline"
          className="focus-ring"
          style={{ marginTop: 12 }}
          loading={pending}
          onClick={handleGuest}
        >
          一键游客体验
        </Button>
      </Card>
    </div>
  );
}
