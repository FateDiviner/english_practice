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
  IconUserGroup,
  IconStorage,
  IconFile,
  IconSettings,
  IconHistory,
  IconDashboard,
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

/** 用户功能。前四项是底部 Tab Bar 的全部内容，多一项都会挤到 44px 触控下限以下 */
const USER_NAV: NavItem[] = [
  { key: "dashboard", label: "词书中心", path: "/", icon: <IconHome /> },
  { key: "practice", label: "默写练习", path: "/practice", icon: <IconBulb /> },
  { key: "wrong", label: "错题本", path: "/wrong-book", icon: <IconBulb /> },
  { key: "chat", label: "AI 伴学", path: "/chat", icon: <IconMessage /> },
];

const ADMIN_NAV: NavItem[] = [
  { key: "admin-users", label: "用户管理", path: "/admin/users", icon: <IconUserGroup /> },
  { key: "admin-books", label: "词书管理", path: "/admin/wordbooks", icon: <IconStorage /> },
  { key: "admin-kb", label: "知识库", path: "/admin/knowledge", icon: <IconFile /> },
  { key: "admin-rag", label: "检索调试", path: "/admin/rag", icon: <IconSettings /> },
  { key: "admin-audit", label: "审计日志", path: "/admin/audit", icon: <IconHistory /> },
];

/** 移动端底部 Tab：管理入口收成一个「管理」，展开后用二级横向导航 */
const MOBILE_TABS: NavItem[] = [
  ...USER_NAV,
  { key: "admin", label: "管理", path: "/admin/users", icon: <IconDashboard /> },
];

/** 顶栏与侧栏共用的动作按钮，移动端塞进顶栏、桌面端放进侧栏底部 */
function ActionButtons({
  theme,
  onTheme,
  onBackup,
  onLogout,
}: {
  theme: string;
  onTheme: () => void;
  onBackup: () => void;
  onLogout: () => void;
}) {
  return (
    <Space size={4}>
      <Tooltip content="学习数据备份">
        <Button
          className="focus-ring"
          size="small"
          type="text"
          aria-label="学习数据备份"
          icon={<IconExport />}
          onClick={onBackup}
        />
      </Tooltip>
      <Tooltip content={theme === "dark" ? "切换为浅色" : "切换为深色"}>
        <Button
          className="focus-ring"
          size="small"
          type="text"
          aria-label="切换深浅色主题"
          icon={theme === "dark" ? <IconSun /> : <IconMoon />}
          onClick={onTheme}
        />
      </Tooltip>
      <Tooltip content="退出登录">
        <Button
          className="focus-ring"
          size="small"
          type="text"
          aria-label="退出登录"
          icon={<IconPoweroff />}
          onClick={onLogout}
        />
      </Tooltip>
    </Space>
  );
}

/** 管理页的二级导航。桌面端侧栏已经摊开全部入口，只在移动端出现 */
function AdminSubNav() {
  const navigate = useNavigate();
  const location = useLocation();
  return (
    <nav
      aria-label="管理子导航"
      style={{
        display: "flex",
        gap: "var(--space-2)",
        padding: "var(--space-2) var(--space-3)",
        overflowX: "auto",
        borderBottom: "1px solid var(--border-color)",
        background: "var(--bg-card)",
      }}
    >
      {ADMIN_NAV.map((item) => {
        const active = location.pathname.startsWith(item.path);
        return (
          <Button
            key={item.key}
            size="small"
            type={active ? "primary" : "outline"}
            className="focus-ring"
            style={{ flexShrink: 0 }}
            onClick={() => navigate(item.path)}
          >
            {item.label}
          </Button>
        );
      })}
    </nav>
  );
}

/** 应用外壳：桌面左侧栏 + 移动底部 Tab Bar，全站可键盘 Tab 到达 */
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

  // 管理入口只对管理员显示。这里只是隐藏入口，真正的权限在后端 require_admin 把关
  const isAdmin = user?.role === "admin";
  const desktopNav = isAdmin ? [...USER_NAV, ...ADMIN_NAV] : USER_NAV;
  const mobileTabs = isAdmin ? MOBILE_TABS : USER_NAV.slice(0, 4);
  const onAdminRoute = location.pathname.startsWith("/admin");

  const isActive = (path: string) =>
    path === "/" ? location.pathname === "/" : location.pathname.startsWith(path);

  const handleTheme = () => setTheme(theme === "dark" ? "light" : "dark");
  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const renderNavItem = (item: NavItem, variant: "sidebar" | "tab") => {
    const active = isActive(item.path);
    if (variant === "tab") {
      return (
        <button
          key={item.key}
          type="button"
          className="tabbar-item focus-ring"
          aria-current={active ? "page" : undefined}
          onClick={() => navigate(item.path)}
        >
          {item.icon}
          <span>{item.label}</span>
        </button>
      );
    }
    return (
      <button
        key={item.key}
        type="button"
        className="sidebar-item focus-ring"
        aria-current={active ? "page" : undefined}
        onClick={() => navigate(item.path)}
      >
        {item.icon}
        <span>{item.label}</span>
      </button>
    );
  };

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="主导航">
        <Typography.Title heading={6} style={{ margin: "0 0 var(--space-4)", padding: "0 var(--space-4)" }}>
          英语练习平台
        </Typography.Title>

        <nav aria-label="功能导航" style={{ display: "grid", gap: "var(--space-1)" }}>
          {desktopNav.map((item) => renderNavItem(item, "sidebar"))}
        </nav>

        <div style={{ flex: 1 }} />

        <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "var(--space-3)" }}>
          <Typography.Text type="secondary" style={{ padding: "0 var(--space-4)", display: "block" }}>
            {user?.username}
            {user?.is_guest ? "（游客）" : ""}
          </Typography.Text>
          <div style={{ padding: "var(--space-2) var(--space-2) 0" }}>
            <ActionButtons
              theme={theme}
              onTheme={handleTheme}
              onBackup={() => setBackupVisible(true)}
              onLogout={handleLogout}
            />
          </div>
        </div>
      </aside>

      <div className="shell-main">
        {/* 移动端顶栏：侧栏隐藏后，动作按钮要有去处 */}
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 20,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-2)",
            height: 52,
            padding: "0 var(--space-3)",
            background: "var(--bg-card)",
            borderBottom: "1px solid var(--border-color)",
          }}
          className="mobile-header"
        >
          <Typography.Title heading={6} style={{ margin: 0, whiteSpace: "nowrap" }}>
            英语练习平台
          </Typography.Title>
          <ActionButtons
            theme={theme}
            onTheme={handleTheme}
            onBackup={() => setBackupVisible(true)}
            onLogout={handleLogout}
          />
        </header>

        {onAdminRoute && <AdminSubNav />}

        {user?.is_guest && !bannerDismissed && (
          <div
            data-testid="guest-banner"
            style={{
              background: "var(--color-warning-soft)",
              borderBottom: "1px solid var(--border-color)",
              padding: "var(--space-2) var(--space-4)",
              display: "flex",
              flexWrap: "wrap",
              gap: "var(--space-2)",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Typography.Text style={{ fontSize: 13 }}>
              游客模式：练习记录只保存在本机浏览器，清缓存或换设备会全部丢失
            </Typography.Text>
            <Space size={8}>
              <Button size="mini" type="primary" className="focus-ring" onClick={() => navigate("/login")}>
                立即注册保存
              </Button>
              <Button size="mini" type="text" className="focus-ring" onClick={() => setBannerDismissed(true)}>
                知道了
              </Button>
            </Space>
          </div>
        )}

        <main className="shell-content">
          <Outlet />
        </main>
      </div>

      <nav className="tabbar" aria-label="主导航">
        {mobileTabs.map((item) => renderNavItem(item, "tab"))}
      </nav>

      <DataBackupModal visible={backupVisible} onClose={() => setBackupVisible(false)} />
    </div>
  );
}
