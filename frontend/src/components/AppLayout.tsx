import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { Button, Space, Tooltip, Typography } from "@arco-design/web-react";
import {
  IconHome,
  IconBulb,
  IconMessage,
  IconMoon,
  IconSun,
  IconPoweroff,
  IconExport,
} from "@arco-design/web-react/icon";
import DataBackupModal from "@/components/DataBackupModal";
import { useAuthStore } from "@/stores/auth";
import { useAppStore } from "@/stores/app";

interface NavItem {
  key: string;
  label: string;
  path: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { key: "dashboard", label: "词书中心", path: "/", icon: <IconHome /> },
  { key: "practice", label: "默写练习", path: "/practice", icon: <IconBulb /> },
  { key: "wrong", label: "错题本", path: "/wrong-book", icon: <IconBulb /> },
  { key: "chat", label: "AI 伴学", path: "/chat", icon: <IconMessage /> },
];

/** 应用外壳：顶部导航 + 内容区，全站可键盘 Tab 到达 */
export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const theme = useAppStore((state) => state.theme);
  const setTheme = useAppStore((state) => state.setTheme);
  // 提示条只在本次会话内可折叠，下次打开页面仍会提醒，避免数据静默丢失
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [backupVisible, setBackupVisible] = useState(false);

  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  return (
    <div style={{ minHeight: "100%", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 20,
          background: "var(--bg-card)",
          borderBottom: "1px solid var(--border-color)",
          backdropFilter: "blur(8px)",
        }}
      >
        <div
          style={{
            maxWidth: 1120,
            margin: "0 auto",
            padding: "0 20px",
            height: 56,
            display: "flex",
            alignItems: "center",
            gap: 24,
          }}
        >
          <Typography.Title heading={5} style={{ margin: 0, whiteSpace: "nowrap" }}>
            英语练习平台
          </Typography.Title>

          <nav style={{ display: "flex", gap: 4, flex: 1, overflowX: "auto" }}>
            {NAV_ITEMS.map((item) => (
              <Button
                key={item.key}
                type={isActive(item.path) ? "primary" : "text"}
                size="small"
                className="focus-ring"
                icon={item.icon}
                onClick={() => navigate(item.path)}
                style={{ flexShrink: 0 }}
              >
                {item.label}
              </Button>
            ))}
          </nav>

          <Space size={8}>
            <Tooltip content="学习数据备份">
              <Button
                className="focus-ring"
                size="small"
                type="text"
                aria-label="学习数据备份"
                icon={<IconExport />}
                onClick={() => setBackupVisible(true)}
              />
            </Tooltip>

            <Tooltip content={theme === "dark" ? "切换为浅色" : "切换为深色"}>
              <Button
                className="focus-ring"
                size="small"
                type="text"
                aria-label="切换深浅色主题"
                icon={theme === "dark" ? <IconSun /> : <IconMoon />}
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              />
            </Tooltip>

            <Typography.Text type="secondary" style={{ whiteSpace: "nowrap" }}>
              {user?.username}
              {user?.is_guest ? " (游客)" : ""}
            </Typography.Text>

            <Tooltip content="退出登录">
              <Button
                className="focus-ring"
                size="small"
                type="text"
                aria-label="退出登录"
                icon={<IconPoweroff />}
                onClick={() => {
                  logout();
                  navigate("/login", { replace: true });
                }}
              />
            </Tooltip>
          </Space>
        </div>
      </header>

      {user?.is_guest && !bannerDismissed && (
        <div
          data-testid="guest-banner"
          style={{
            background: "var(--color-warning-soft)",
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <div
            style={{
              maxWidth: 1120,
              margin: "0 auto",
              padding: "8px 20px",
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Typography.Text style={{ fontSize: 13 }}>
              游客模式：练习记录只保存在本机浏览器，清缓存或换设备会全部丢失
            </Typography.Text>
            <Space size={8}>
              <Button
                size="mini"
                type="primary"
                className="focus-ring"
                onClick={() => navigate("/login")}
              >
                立即注册保存
              </Button>
              <Button
                size="mini"
                type="text"
                className="focus-ring"
                onClick={() => setBannerDismissed(true)}
              >
                知道了
              </Button>
            </Space>
          </div>
        </div>
      )}

      <main style={{ flex: 1, maxWidth: 1120, width: "100%", margin: "0 auto", padding: "24px 20px 48px" }}>
        <Outlet />
      </main>

      <DataBackupModal
        visible={backupVisible}
        onClose={() => setBackupVisible(false)}
      />
    </div>
  );
}
