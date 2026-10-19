import { useEffect, useState } from "react";
import { Button, Card, Form, Input, Message, Typography } from "@arco-design/web-react";
import { IconLock, IconUser, IconSafe } from "@arco-design/web-react/icon";
import { fetchHealth, registerAdmin } from "@/api/register";
import { setToken } from "@/api/client";
import { toMessage } from "@/api/client";

interface FormValues {
  username: string;
  password: string;
  confirm?: string;
  invite_code?: string;
}

/** 管理员注册页：邀请码是否必填由后端健康检查决定，前端不自行猜测 */
export default function RegisterPage({
  onRegistered,
  onBackToLogin,
}: {
  onRegistered: () => void;
  onBackToLogin: () => void;
}) {
  const [pending, setPending] = useState(false);
  const [needInvite, setNeedInvite] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [form] = Form.useForm<FormValues>();

  useEffect(() => {
    void fetchHealth()
      .then((health) => setNeedInvite(health.invite_code_required))
      .catch(() => setNeedInvite(false))
      .finally(() => setLoaded(true));
  }, []);

  const handleSubmit = async (values: FormValues) => {
    if (values.password !== values.confirm) {
      Message.error({ content: "两次输入的密码不一致" });
      return;
    }
    setPending(true);
    try {
      const data = await registerAdmin({
        username: values.username.trim(),
        password: values.password,
        invite_code: values.invite_code?.trim() || undefined,
      });
      setToken(data.access_token);
      Message.success({ content: "管理员账号已创建" });
      onRegistered();
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
      <Card className="card" style={{ width: 400, maxWidth: "100%" }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <Typography.Title heading={5} style={{ marginBottom: 4 }}>
            创建管理员账号
          </Typography.Title>
          <Typography.Text type="secondary">
            {needInvite
              ? "本系统已配置邀请码，必须填写才能创建管理员"
              : "仅在系统还没有管理员时可注册；之后需由现有管理员代建"}
          </Typography.Text>
        </div>

        <Form
          form={form}
          layout="vertical"
          onSubmit={handleSubmit}
          disabled={!loaded || pending}
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
              autoComplete="username"
              allowClear
            />
          </Form.Item>

          <Form.Item
            label="密码"
            field="password"
            rules={[
              { required: true, message: "请输入密码" },
              { minLength: 6, message: "密码至少 6 位" },
            ]}
          >
            <Input.Password
              className="focus-ring"
              prefix={<IconLock />}
              autoComplete="new-password"
            />
          </Form.Item>

          <Form.Item
            label="确认密码"
            field="confirm"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入密码" },
              {
                validator: (value, callback) =>
                  value === form.getFieldValue("password")
                    ? callback()
                    : callback("两次输入的密码不一致"),
              },
            ]}
          >
            <Input.Password
              className="focus-ring"
              prefix={<IconLock />}
              autoComplete="new-password"
            />
          </Form.Item>

          {needInvite && (
            <Form.Item
              label="邀请码"
              field="invite_code"
              rules={[{ required: true, message: "请输入邀请码" }]}
            >
              <Input
                className="focus-ring"
                prefix={<IconSafe />}
                autoComplete="off"
              />
            </Form.Item>
          )}

          <Button htmlType="submit" type="primary" long className="focus-ring" loading={pending}>
            创建管理员
          </Button>
        </Form>

        <Button
          type="text"
          long
          className="focus-ring"
          style={{ marginTop: 10 }}
          onClick={onBackToLogin}
        >
          已有账号，返回登录
        </Button>
      </Card>
    </div>
  );
}
