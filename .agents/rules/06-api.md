# 接口规范

- 前缀 /api/v1
- 响应包装：{ "code": 0, "message": "ok", "data": ... }；错误时 code 非 0
- 分页：{ "items": [], "total": 0, "page": 1, "page_size": 20 }
- 鉴权：Authorization: Bearer <token>；管理员接口必须校验 role == "admin"
- 状态码：400 参数错、401 未登录、403 无权限、404 不存在、409 冲突、422 校验失败、501 未实现
- 安全红线：出题接口绝不返回单词拼写；判分只在服务端完成
- 字段名与接口路径以 docs/api-contract.md 为准
