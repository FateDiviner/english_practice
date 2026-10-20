import { Navigate, Outlet } from "react-router-dom";

import { useAuthStore } from "@/stores/auth";

/**
 * 管理端路由守卫。
 *
 * 只在这一处判断角色，页面组件不再各自判断——否则 role 的判断会散落进
 * 每个页面，将来改权限模型要挨个文件找。
 *
 * 注意：这里只是隐藏入口，真正的权限在后端 require_admin 把关。
 * 普通用户手敲 /admin 地址会被挡回首页，但直接调接口仍会拿到 403。
 */
export default function AdminGuard() {
  const user = useAuthStore((state) => state.user);

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (user.role !== "admin") {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
