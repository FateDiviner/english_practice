# Python 代码规范

- 命名：模块/函数/变量 snake_case；类 PascalCase；常量 UPPER_SNAKE_CASE
- 路由函数必须有返回类型注解
- 请求/响应必须用 Pydantic schema，禁止返回 ORM 对象或裸 dict
- 业务逻辑放 services/，路由层只做参数校验与调用
- 使用 async def 路由 + async SQLAlchemy session
- 异常统一处理，返回符合接口规范的错误响应
- 日志用 logging，不用 print
