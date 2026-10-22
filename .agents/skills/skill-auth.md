# Skill：认证与权限

## 触发场景
登录注册、JWT、角色校验。

## 步骤
1. 注册：username/email 唯一校验，bcrypt 哈希密码
2. 登录：校验密码，签发 access token（含 user_id、role、exp）
3. 依赖注入 get_current_user；管理员接口叠加 require_admin
4. 前端：token 存 Pinia + localStorage，axios 拦截器附加 Header
5. 401 跳登录；403 提示无权限
6. 路由守卫：/admin/* 校验 role

## 红线
- 密码不落明文日志
- token 不写死在代码
- 禁用用户不得登录
