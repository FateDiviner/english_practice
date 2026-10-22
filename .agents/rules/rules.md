## 0. 项目一句话
英语单词默写练习平台：用户看**音标 + 中文释义**默写英文单词；管理员导入词书、管理用户。前端 Vue 3，后端 FastAPI + Pydantic，数据库 MySQL。UI 风格为「纸感学院风」。

## 1. 技术栈（不得擅自替换）
- 前端：Vue 3（Composition API + `<script setup>`）、Vite、Vue Router 4、Pinia、Axios
- 后端：Python 3.11+、FastAPI、Pydantic v2、SQLAlchemy 2.x（ORM）、Alembic（迁移）
- 数据库：MySQL 8.x
- 认证：JWT（access token），密码用 bcrypt 哈希
- 导入：pandas + openpyxl（Excel/CSV）

禁止引入：TypeScript（除非用户明确要求）、Nuxt、Next、Django、MongoDB、Redis（除非用户要求）、任何需要付费授权的库。

## 2. 目录结构约定
backend/app/{core,models,schemas,api/v1,services,db}、backend/alembic、backend/tests；
frontend/src/{api,components,layouts,router,stores,styles,views/{auth,user,admin}}。
新文件必须放进对应目录，不得在根目录随意创建脚本。

## 3. 命名与代码风格
- Python：snake_case / PascalCase / UPPER_SNAKE_CASE；路由函数必须有返回类型注解；请求响应必须用 Pydantic schema；业务逻辑放 services/；async def + async session。
- Vue：组件 PascalCase；API 统一走 src/api/；状态放 Pinia；样式 scoped 且颜色走 tokens.css，禁止硬编码色值。

## 4. 数据库规则
- 表名复数小写下划线；每表有 id、created_at、updated_at；外键显式声明并建索引。
- 唯一约束：words(wordbook_id, spelling)、word_progress(user_id, word_id)、wrong_words(user_id, word_id)。
- 表结构变更必须走 Alembic 迁移；utf8mb4 / utf8mb4_unicode_ci。

## 5. 接口规范
- 前缀 /api/v1；响应包装 {code, message, data}；分页 {items, total, page, page_size}。
- JWT 鉴权；管理员接口校验 role == "admin"。
- 状态码语义正确（400/401/403/404/409/422）。
- 安全红线：出题接口不得返回拼写；判分只在服务端。

## 6. 核心业务规则
- 判分：normalize(trim+lower) → 严格/宽松比对 → 英美拼写映射表 → services/grading.py；答错才返回正确拼写与例句。
- 掌握度：连续正确 2 次升为已掌握；答错降为学习中并写入错词本；错词本重练达标 resolved=true。
- 导入：校验列映射与逐行数据；事务批量入库；失败行写 import_jobs.error_detail；大文件后台任务。

## 7. UI 规范（纸感学院风）
- 禁止：紫/蓝紫渐变、玻璃拟态、光晕、机器人/AI 形象、emoji 当图标、大圆角卡片堆砌、3D 插画、弹窗式判分反馈。
- 颜色：底色 #F7F3E8、主文字 #23201A、墨蓝 #1F3A5F、赭石黄 #C8963E、墨绿 #3D6B4F、朱红 #B5462F、分割线 #D8D0BE。
- 字体：标题衬线（Noto Serif SC / Georgia），正文无衬线（Noto Sans SC）。
- 默写输入用下划线式；判分反馈就地呈现；所有元素覆盖 默认/hover/active/disabled/正确/错误/空状态；空状态用鼓励文案。

## 8. 禁止事项
- 不引入未声明依赖；密钥走环境变量；不得省略鉴权；不得前端存答案；不得注释掉校验/异常/事务；单文件不超 300 行；不用中文/拼音变量名；改表必须迁移；不用 print 调试；不伪造测试。

## 9. 输出要求
- 改代码前先说明改哪些文件、为什么；新增接口给出路由+schema+service+迁移+前端封装；涉及 UI 对照第 7 节自检；只做用户要求范围；不确定先提问。

## 10. 验收自检清单
- [ ] 鉴权与角色校验
- [ ] 出题接口无答案泄露
- [ ] Pydantic 覆盖输入输出
- [ ] 判分在 service 层且处理英美拼写
- [ ] 数据库变更走迁移
- [ ] 前端无硬编码颜色
- [ ] 判分反馈就地呈现
- [ ] 无未声明依赖、无硬编码密钥
- [ ] 错误响应符合统一包装