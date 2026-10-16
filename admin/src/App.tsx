import { useCallback, useEffect, useState } from "react";
import { Button, Layout, Space, Spin, Typography } from "@arco-design/web-react";
import {
  IconHistory,
  IconMoon,
  IconPoweroff,
  IconSun,
} from "@arco-design/web-react/icon";
import { Route, Routes, useLocation, useNavigate } from "react-router-dom";
import LoginPage from "@/pages/LoginPage";
import AuditPage from "@/pages/AuditPage";
import { fetchMe } from "@/api/auth";
import { clearToken, getToken } from "@/api/client";
import type { AdminUser } from "@/types";

export default function App() {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [dark, setDark] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!getToken()) {
      setChecking(false);
      return;
    }
    void fetchMe()
      .then((me) => {
        // 角色守卫：令牌有效但不是管理员一样要退出，前端不放行任何越权入口
        if (me.role !== "admin") {
          clearToken();
          setUser(null);
        } else {
          setUser(me);
        }
      })
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    navigate("/", { replace: true });
  }, [navigate]);

  if (checking) {
    return (
      <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Spin size={32} />
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLoggedIn={setUser} />;
  }

  return (
    <Layout style={{ minHeight: "100%" }}>
      <Layout.Header
        style={{
          background: "var(--bg-card)",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
        }}
      >
        <Typography.Title heading={6} style={{ margin: 0 }}>
          英语练习平台 · 管理端
        </Typography.Title>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Typography.Text type="secondary">{user.username}</Typography.Text>
          <Button
            size="small"
            type="text"
            className="focus-ring"
            aria-label="切换深浅色主题"
            icon={dark ? <IconSun /> : <IconMoon />}
            onClick={() => setDark((value) => !value)}
          />
          <Button
            size="small"
            type="text"
            className="focus-ring"
            aria-label="退出登录"
            icon={<IconPoweroff />}
            onClick={logout}
          />
        </div>
      </Layout.Header>

      <Layout style={{ maxWidth: 1120, width: "100%", margin: "0 auto", padding: 20 }}>
        <Space size={8} style={{ marginBottom: 16 }}>
          <Button
            type={location.pathname.startsWith("/audit-logs") ? "primary" : "text"}
            className="focus-ring"
            icon={<IconHistory />}
            onClick={() => navigate("/audit-logs")}
          >
            审计日志
          </Button>
        </Space>

        <Routes>
          <Route path="/" element={<AuditPage />} />
          <Route path="/audit-logs" element={<AuditPage />} />
        </Routes>
      </Layout>
    </Layout>
  );
}
