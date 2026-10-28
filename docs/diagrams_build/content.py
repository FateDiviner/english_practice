# -*- coding: utf-8 -*-
"""流程图 PDF 的正文内容：每个功能一张图 + 分层调用表 + 关键分支表。"""

SECTIONS = []


def add(**kw):
    SECTIONS.append(kw)


add(
    num="00", title="系统总览与分层约定", feature="全局",
    diagram="00-overview.svg",
    summary=(
        "前端为 Vue 3 + Pinia + Vue Router 单页应用，所有请求经 src/api/request.js 统一封装；"
        "后端为 FastAPI + SQLAlchemy 2.0 异步会话，路由层只做参数与权限，业务规则集中在 services 层。"
        "响应统一为 {code, message, data}，前端在响应拦截器中按 code===0 解包，业务码非 0 时抛出 ApiError。"
        "除 AI 对话使用 SSE 外，其余接口均为 JSON。"
    ),
    nodes=[
        ("前端入口", "frontend/src/main.js", "createApp / 挂载 Pinia、Router", "注册全局状态与路由"),
        ("前端路由", "frontend/src/router/index.js:105", "beforeEach()", "登录态恢复、requiresAuth / requiresAdmin / guestOnly 判定"),
        ("前端请求", "frontend/src/api/request.js:16", "axios.create()", "baseURL=/api/v1，超时 20s"),
        ("前端请求", "frontend/src/api/request.js:21", "请求拦截器", "从 Pinia 取 token，注入 Authorization: Bearer"),
        ("前端请求", "frontend/src/api/request.js:57", "响应拦截器", "code===0 返回 payload.data；非 0 抛 ApiError"),
        ("前端请求", "frontend/src/api/request.js:38", "normalizeError()", "统一网络/HTTP/业务错误，40101 触发登出"),
        ("后端装配", "backend/app/main.py:17", "create_app()", "注册异常处理器与 /api/v1 路由"),
        ("后端装配", "backend/app/api/v1/router.py:20", "api_router.include_router()", "按模块挂载 auth / wordbooks / practice / agent 等路由"),
        ("后端依赖", "backend/app/core/deps.py:19", "get_current_user()", "解析 Bearer、查 User、校验 status"),
        ("后端依赖", "backend/app/core/deps.py:46", "require_admin()", "role!=admin 抛 403/40301"),
        ("后端异常", "backend/app/core/exception_handlers.py:94", "register_exception_handlers()", "AppError / 校验错误 / HTTP 错误 / 兜底 500"),
        ("后端会话", "backend/app/db/session.py:16", "get_session()", "请求级 AsyncSession，退出自动关闭"),
        ("数据模型", "backend/app/models/*.py", "SQLAlchemy 2.0 Mapped 模型", "users / wordbooks / words / 练习 / 错词 / 导入 / AI 会话"),
    ],
    branches=[
        ("未登录访问受保护接口", "backend/app/core/deps.py:27-34", "401 / 40101 未登录或登录已过期"),
        ("非管理员访问 /admin/*", "backend/app/core/deps.py:50-51", "403 / 40301 无管理员权限"),
        ("业务异常", "backend/app/core/exception_handlers.py:61", "AppError → {code, message, data:null}"),
        ("Pydantic 校验失败", "backend/app/core/exception_handlers.py:65", "HTTP 422，业务码 42201"),
        ("未捕获异常", "backend/app/core/exception_handlers.py:86", "HTTP 500，业务码 50000，不泄露堆栈"),
        ("前端收到 40101", "frontend/src/api/request.js:29-36", "清会话并 location.replace('/login')"),
    ],
)

add(
    num="01", title="注册与登录（F1）", feature="F1 注册登录",
    diagram="01-auth-login.svg",
    summary=(
        "注册在前端做用户名/邮箱/密码一致性校验，后端再次校验唯一性并 bcrypt 哈希入库；"
        "登录支持用户名或邮箱作为 account，校验密码与账号状态，成功后签发 HS256 JWT，"
        "前端写入 Pinia 与 localStorage，并按 redirect 参数回到原页面。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/auth/Login.vue:11", "form = reactive({account, password})", "登录表单状态"),
        ("前端视图", "frontend/src/views/auth/Login.vue:15", "submit()", "防重复提交、非空校验、调用 store、按 redirect 跳转"),
        ("前端视图", "frontend/src/views/auth/Register.vue:13", "validate()", "用户名、邮箱正则、密码长度、两次密码一致"),
        ("前端视图", "frontend/src/views/auth/Register.vue:21", "submit()", "提交注册，成功后跳 /login?registered=1"),
        ("前端状态", "frontend/src/stores/auth.js:49", "login(credentials)", "调用 API 并写入会话"),
        ("前端状态", "frontend/src/stores/auth.js:33", "setSession(session)", "保存 access_token 与 user"),
        ("前端状态", "frontend/src/stores/auth.js:25", "setToken(token)", "写 localStorage english_practice_token"),
        ("前端 API", "frontend/src/api/auth.js:3", "register(payload)", "POST /auth/register"),
        ("前端 API", "frontend/src/api/auth.js:7", "login(payload)", "POST /auth/login"),
        ("前端请求", "frontend/src/api/request.js:21", "请求拦截器", "注入 Bearer（登录时通常无 token）"),
        ("后端路由", "backend/app/api/v1/auth.py:22", "register()", "201，返回 ApiResponse[UserOut]"),
        ("后端路由", "backend/app/api/v1/auth.py:37", "login()", "校验凭据、签发 token、返回 TokenOut"),
        ("后端服务", "backend/app/services/auth.py:45", "register_user()", "唯一性预检、哈希、插入、并发冲突兜底"),
        ("后端服务", "backend/app/services/auth.py:25", "_has_identity_conflict()", "username/email 冲突检查"),
        ("后端服务", "backend/app/services/auth.py:79", "authenticate_user()", "查用户、校验密码、校验禁用状态"),
        ("后端服务", "backend/app/services/auth.py:16", "get_user_by_account()", "先按 username 查，再按 email 查"),
        ("后端安全", "backend/app/core/security.py:14", "hash_password()", "bcrypt 哈希，超过 72 字节抛 ValueError"),
        ("后端安全", "backend/app/core/security.py:23", "verify_password()", "bcrypt.checkpw"),
        ("后端安全", "backend/app/core/security.py:31", "create_access_token()", "HS256，载荷 sub/role/exp/iat"),
        ("数据模型", "backend/app/models/user.py:9", "User", "users 表；username、email 唯一；role/status 枚举"),
        ("数据契约", "backend/app/schemas/auth.py:9", "RegisterIn / LoginIn / UserOut / TokenOut", "字段长度、邮箱正则、密码 8-72"),
    ],
    branches=[
        ("账号或密码为空", "Login.vue:18-21", "前端内联提示，不发请求"),
        ("账号不存在或密码错误", "services/auth.py:82-83", "401 / 40101 账号或密码错误"),
        ("账号被禁用", "services/auth.py:85-86", "403 / 40301 账号已被禁用"),
        ("重复注册（预检命中）", "services/auth.py:52-53", "409 / 40901 用户名或邮箱已存在"),
        ("重复注册（并发唯一键冲突）", "services/auth.py:69-74", "IntegrityError 回滚后同样返回 409"),
        ("密码超过 bcrypt 上限", "security.py:17-18 → services/auth.py:57-58", "422 / 42201 密码长度超过限制"),
        ("Schema 校验失败", "exception_handlers.py:65-74", "HTTP 422，业务码 42201"),
        ("登录成功", "stores/auth.js:33-38", "token 与 user 写入 localStorage，跳转 redirect 或首页"),
    ],
)

add(
    num="02", title="路由守卫与请求鉴权（F1）", feature="F1 注册登录",
    diagram="02-auth-guard.svg",
    summary=(
        "前端首次进入时先通过 /auth/me 恢复会话，再由全局守卫按 meta 判定是否需要登录或管理员身份；"
        "后端不依赖前端判定，每个受保护接口都通过 get_current_user 重新解码 JWT、查库并校验账号状态。"
        "前端 40101 会统一清理会话并跳转登录页。"
    ),
    nodes=[
        ("前端路由", "frontend/src/router/index.js:105", "router.beforeEach()", "全局鉴权守卫"),
        ("前端路由", "frontend/src/router/index.js:107-113", "守卫内初始化", "未初始化时 await authStore.fetchMe()"),
        ("前端状态", "frontend/src/stores/auth.js:55", "fetchMe()", "有 token 才请求；失败清会话"),
        ("前端状态", "frontend/src/stores/auth.js:21", "isAuthenticated", "以 token 是否存在判断"),
        ("前端状态", "frontend/src/stores/auth.js:22", "isAdmin", "user.role === 'admin'"),
        ("前端 API", "frontend/src/api/auth.js:11", "fetchMe()", "GET /auth/me"),
        ("前端路由", "frontend/src/router/index.js:36", "用户区父路由 meta.requiresAuth", "未登录跳 login 并携带 redirect"),
        ("前端路由", "frontend/src/router/index.js:66", "管理区父路由 meta.requiresAdmin", "非管理员跳 home"),
        ("前端路由", "frontend/src/router/index.js:7-32", "login / register meta.guestOnly", "已登录访问则跳 home"),
        ("后端路由", "backend/app/api/v1/auth.py:57", "me()", "返回当前用户"),
        ("后端依赖", "backend/app/core/deps.py:16", "HTTPBearer(auto_error=False)", "关闭自动 403，交给自定义 401"),
        ("后端依赖", "backend/app/core/deps.py:19", "get_current_user()", "取凭据、解码、查库、校验状态"),
        ("后端依赖", "backend/app/core/deps.py:46", "require_admin()", "先取当前用户，再校验 role"),
        ("后端安全", "backend/app/core/security.py:46", "decode_access_token()", "验签、过期、sub/role 必填"),
        ("数据模型", "backend/app/models/user.py:18-31", "User.id / role / status", "身份与状态的数据来源"),
    ],
    branches=[
        ("无 Bearer 或 scheme 非 bearer", "deps.py:27-28", "401 / 40101 未登录或登录已过期"),
        ("JWT 过期、签名错误、缺字段", "deps.py:31-34；security.py:56-60", "401 / 40101"),
        ("token 中用户已不存在", "deps.py:36-38", "401 / 40101"),
        ("账号被禁用后仍持旧 token", "deps.py:40-41", "401 / 40101 账号已被禁用"),
        ("非管理员访问管理接口", "deps.py:50-51", "403 / 40301"),
        ("前端未登录访问受保护路由", "router/index.js:115-117", "跳 /login?redirect=&lt;fullPath&gt;"),
        ("前端非管理员访问 /admin/*", "router/index.js:118", "跳 home，不发请求"),
        ("前端收到 40101", "request.js:46-48 或 :62", "handleUnauthenticated() 清会话并跳登录"),
    ],
)

add(
    num="03", title="管理员词书管理（F2）", feature="F2 创建词书",
    diagram="03-wordbook-admin.svg",
    summary=(
        "词书管理页以 page 为唯一分页驱动，watch 页码变化触发列表加载；新建与编辑复用同一抽屉与同一保存函数，"
        "以 form.id 区分创建或更新。删除前服务端统计词书下单词数，非空直接返回 409，不支持 force 级联删除。"
        "用户端只能看到 status=published 的词书。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:128", "watch(page, loadWordbooks, {immediate:true})", "分页加载的唯一驱动点"),
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:54", "loadWordbooks()", "拉取分页列表并填充 items/total"),
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:37", "openCreate()", "重置表单并打开新建抽屉"),
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:42", "openEdit(book)", "回填表单并打开编辑抽屉"),
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:68", "saveWordbook()", "必填校验，按 form.id 分支创建或更新"),
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:95", "togglePublish(book)", "只传 status 更新上下架"),
        ("前端视图", "frontend/src/views/admin/WordbookManage.vue:107", "confirmDelete(book)", "二次确认后删除，处理 40901"),
        ("前端组件", "frontend/src/components/PagePagination.vue:13", "goTo(nextPage)", "emit update:page 驱动父页 page"),
        ("前端 API", "frontend/src/api/admin.js:3", "listAdminWordbooks()", "GET /admin/wordbooks"),
        ("前端 API", "frontend/src/api/admin.js:7", "createAdminWordbook()", "POST /admin/wordbooks"),
        ("前端 API", "frontend/src/api/admin.js:11", "updateAdminWordbook()", "PUT /admin/wordbooks/{id}"),
        ("前端 API", "frontend/src/api/admin.js:15", "deleteAdminWordbook()", "DELETE /admin/wordbooks/{id}"),
        ("后端路由", "backend/app/api/v1/admin_wordbooks.py:28", "Depends(require_admin)", "整组管理接口的权限依赖"),
        ("后端路由", "backend/app/api/v1/admin_wordbooks.py:32", "create_wordbook_endpoint()", "创建词书，默认 draft"),
        ("后端路由", "backend/app/api/v1/admin_wordbooks.py:51", "update_wordbook_endpoint()", "更新名称/描述/等级/状态"),
        ("后端路由", "backend/app/api/v1/admin_wordbooks.py:66", "delete_wordbook_endpoint()", "删除词书"),
        ("后端路由", "backend/app/api/v1/admin_wordbooks.py:78", "list_wordbooks_endpoint()", "管理端分页列表，含 word_count"),
        ("后端服务", "backend/app/services/wordbook.py:19", "create_wordbook()", "构造 Wordbook → add → commit → refresh"),
        ("后端服务", "backend/app/services/wordbook.py:43", "list_wordbooks()", "分页 + 标量子查询统计词数"),
        ("后端服务", "backend/app/services/wordbook.py:65", "update_wordbook()", "404 / 显式 null 422 / 逐字段 setattr"),
        ("后端服务", "backend/app/services/wordbook.py:89", "delete_wordbook()", "存在性校验 → 单词数校验 → 删除"),
        ("后端服务", "backend/app/services/wordbook.py:112", "get_published_wordbook()", "用户端仅可读 published，否则 404"),
        ("数据模型", "backend/app/models/wordbook.py:9", "Wordbook", "status: draft / published / archived"),
        ("数据模型", "backend/app/models/word.py:20", "Word", "uq(wordbook_id, spelling)"),
    ],
    branches=[
        ("名称为空", "WordbookManage.vue:69-72", "前端内联提示，不发请求"),
        ("编辑时 name 显式 null", "services/wordbook.py:76-79", "422 / 42201"),
        ("词书不存在", "services/wordbook.py:94-96", "404"),
        ("删除时词书下仍有单词", "services/wordbook.py:98-102", "409 / 40901 请先清空词书内单词"),
        ("删除触发外键约束", "services/wordbook.py:104-109", "回滚后 409 / 40901"),
        ("前端收到 40901", "WordbookManage.vue:117-118", "提示“还有单词，先清空”"),
        ("用户端访问未发布词书", "wordbook.py:115-116", "按不存在处理，404"),
    ],
)

add(
    num="04", title="单词导入：预览与提交（F3）", feature="F3 导入单词",
    diagram="04-import-preview.svg",
    summary=(
        "导入采用“先预览、再映射、后提交”的两阶段流程。预览接口解析 CSV/TSV/TXT/XLSX，返回表头、前 20 行与总行数；"
        "前端按字段别名自动推断列映射，并对样本做空拼写/重复/列数校验；确认后提交任务，服务端立即返回 202 与 job_id，"
        "真正的全量校验与入库在后台任务中完成。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:51", "loadWordbooks()", "加载可选词书（pageSize=100）"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:88", "handleFile(event)", "记录文件后立即请求预览"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:65", "loadPreviewFromServer()", "清空旧状态，调用预览接口并推断映射"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:37", "canContinue computed", "映射与样本校验通过才允许下一步"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:111", "confirmImport()", "提交文件与 mapping，进入轮询步骤"),
        ("前端工具", "frontend/src/utils/delimited.js:13", "suggestMapping(headers)", "按字段别名生成列映射"),
        ("前端工具", "frontend/src/utils/delimited.js:24", "validateImportRows(headers, rows, mapping)", "空拼写、样本内重复、列数校验"),
        ("前端组件", "frontend/src/components/admin/ImportPreview.vue:10", "previewRows / visibleErrors", "再截取前 20 行、前 10 条错误展示"),
        ("前端 API", "frontend/src/api/admin.js:68", "previewAdminImport()", "POST /admin/wordbooks/{id}/import/preview"),
        ("前端 API", "frontend/src/api/admin.js:74", "importAdminWords()", "POST /admin/wordbooks/{id}/import，FormData"),
        ("后端路由", "backend/app/api/v1/admin_import.py:40", "_read_upload()", "文件名清洗、读取上限字节、大小校验"),
        ("后端路由", "backend/app/api/v1/admin_import.py:50", "_parse_mapping()", "Pydantic 校验 mapping JSON"),
        ("后端路由", "backend/app/api/v1/admin_import.py:57", "_require_wordbook()", "词书不存在 404"),
        ("后端路由", "backend/app/api/v1/admin_import.py:62", "preview_import_endpoint()", "解析并返回 headers / rows[:20] / total_rows"),
        ("后端路由", "backend/app/api/v1/admin_import.py:88", "create_import_endpoint()", "创建 job 并投递后台任务，返回 202"),
        ("后端服务", "backend/app/services/import_file.py:71", "parse_import_file()", "按扩展名分派分隔文本或 XLSX 解析"),
        ("后端服务", "backend/app/services/import_file.py:152", "_parse_delimited()", "UTF-8-sig / GB18030 解码，推断分隔符"),
        ("后端服务", "backend/app/services/import_file.py:173", "_parse_xlsx()", "openpyxl 只读打开活动表"),
        ("后端服务", "backend/app/services/import_file.py:128", "_build_parsed_file()", "过滤空行、取表头、列≤100、行≤20000"),
        ("后端服务", "backend/app/services/import_job.py:8", "create_import_job()", "创建 status=pending 的导入任务"),
        ("数据模型", "backend/app/models/import_job.py:7", "ImportJob", "status / total_rows / success_rows / failed_rows / error_detail"),
    ],
    branches=[
        ("扩展名或大小不合法", "admin_import.py:40-47", "400 参数错误"),
        ("词书不存在", "admin_import.py:57-59", "404"),
        ("空文件 / 超 10MB", "import_file.py:63-68", "拒绝并返回参数错误"),
        ("首行无表头、列数>100、行数>20000", "import_file.py:136-143", "解析失败，返回 422/400"),
        ("样本存在空拼写/重复", "delimited.js:24-46", "前端阻断，不提交"),
        ("mapping 非法 JSON", "admin_import.py:50-54", "422 / 42201"),
        ("提交成功", "admin_import.py:105-111", "202 + import_job_id，后台异步执行"),
    ],
)

add(
    num="05", title="导入后台任务与进度（F3 / F12）", feature="F3 导入单词 · F12 导入进度",
    diagram="05-import-job.svg",
    summary=(
        "后台任务由 FastAPI BackgroundTasks 触发，使用独立 AsyncSession，与请求会话隔离。"
        "状态依次为 pending → processing → done/failed；逐行校验并入库，失败行记录行号、内容与原因，"
        "单行唯一键冲突通过 SAVEPOINT 回滚，不影响其他行。前端每 1.2 秒轮询任务状态直到终态。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:120-122", "importJob = {status:'pending'}", "提交成功后进入第 5 步"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:141", "scheduleJobPolling()", "setTimeout(loadImportJob, 1200)"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:130", "loadImportJob()", "查询一次状态，非终态继续轮询"),
        ("前端视图", "frontend/src/views/admin/ImportWizard.vue:60", "clearPolling()", "组件卸载或重开时清理定时器"),
        ("前端组件", "frontend/src/components/admin/ImportResultPanel.vue:12", "statusLabel", "pending/processing/done/failed 中文映射"),
        ("前端 API", "frontend/src/api/admin.js:81", "getAdminImportJob()", "GET /admin/import-jobs/{id}"),
        ("后端路由", "backend/app/api/v1/admin_import.py:105", "background_tasks.add_task()", "投递 process_import_job"),
        ("后端路由", "backend/app/api/v1/admin_import.py:119", "get_import_job_endpoint()", "返回状态、计数与失败明细"),
        ("后端服务", "backend/app/services/import_job.py:30", "get_import_job()", "任务不存在 404"),
        ("后台任务", "backend/app/services/import_worker.py:102", "process_import_job()", "任务入口：自建会话、状态推进、异常兜底"),
        ("后台任务", "backend/app/services/import_worker.py:109", "async_session_factory()", "后台独立会话，不复用请求会话"),
        ("后台任务", "backend/app/services/import_worker.py:114", "job.status='processing'", "开始处理前先提交状态"),
        ("后台任务", "backend/app/services/import_worker.py:42", "_process_rows()", "重新解析文件，逐行校验/入库/计数"),
        ("后台任务", "backend/app/services/import_worker.py:37", "_load_existing_spellings()", "casefold 预载词书已有拼写"),
        ("后台任务", "backend/app/services/import_file.py:83", "parse_word_row()", "空拼写、超长、sort_order 非负整数校验"),
        ("后台任务", "backend/app/services/import_worker.py:22", "_insert_word()", "begin_nested() 保存点，单行冲突只回滚该行"),
        ("后台任务", "backend/app/services/import_worker.py:95-99", "status='done'", "回写 success_rows / failed_rows / error_detail"),
        ("后台任务", "backend/app/services/import_worker.py:117-131", "except 兜底", "rollback 后置 failed 并写文件级错误"),
        ("数据模型", "backend/app/models/import_job.py:30", "ImportJob.status / error_detail", "任务状态与失败明细 JSON"),
        ("数据模型", "backend/app/models/word.py:25", "uq_words_wordbook_id_spelling", "数据库层最终去重"),
    ],
    branches=[
        ("任务不存在", "import_job.py:30-35", "404"),
        ("空拼写", "import_file.py:88-90 + worker:61-69", "记录「拼写为空」，继续下一行"),
        ("拼写 >100 或可选字段超长", "import_file.py:91-99", "记录超长原因"),
        ("sort_order 非整数/负数", "import_file.py:101-107", "记录「排序必须是非负整数」"),
        ("同词书内已存在（含批内重复）", "worker:71-80", "casefold 比较后记录「spelling 已存在」"),
        ("单行数据库冲突", "worker:22-34", "SAVEPOINT 回滚该行，其余行继续"),
        ("任意未捕获异常", "worker:117-131", "status=failed + 文件级错误明细"),
        ("前端轮询终止", "ImportWizard.vue:135", "仅 pending/processing 继续，终态停止"),
        ("组件卸载", "ImportWizard.vue:162", "onBeforeUnmount(clearPolling)"),
    ],
)

add(
    num="06", title="开始默写与出题（F4）", feature="F4 开始默写",
    diagram="06-practice-start.svg",
    summary=(
        "用户可从设置面板、词书详情或错词本进入练习。后端按 mode 选择候选词：normal 校验词书为 published 并读取全部单词，"
        "wrong_only 只取 resolved=false 的错词；随后优先未掌握词、按 1/5 比例混入已掌握复习词，随机打乱并限制题数。"
        "出题响应只返回音标、释义、词性与长度提示，绝不返回 spelling。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/user/Practice.vue:133", "onMounted()", "加载词书、绑定全局 Enter、处理 URL 参数开局"),
        ("前端视图", "frontend/src/views/user/Practice.vue:36", "loadWordbooks()", "拉取已发布词书供设置面板选择"),
        ("前端视图", "frontend/src/views/user/Practice.vue:69", "startFromQuery()", "解析 ?mode=wrong_only&amp;wordbook_id=&amp;count="),
        ("前端视图", "frontend/src/views/user/Practice.vue:55", "startPractice(config)", "phase==='loading' 时防重入"),
        ("前端视图", "frontend/src/views/user/Practice.vue:48", "applyConfig(config)", "记录本轮配置供“再来一组”复用"),
        ("前端组件", "frontend/src/components/practice/PracticeSetup.vue:28", "start()", "组装 mode/wordbookId/count/strictMode 并 emit"),
        ("前端组件", "frontend/src/components/practice/PracticeSetup.vue:111", "开始按钮 disabled", "加载中或 normal 未选词书时禁用"),
        ("前端状态", "frontend/src/stores/practice.js:31", "reset()", "清空上一轮会话状态"),
        ("前端状态", "frontend/src/stores/practice.js:44", "startSession()", "创建会话，phase=loading → answering"),
        ("前端 API", "frontend/src/api/practice.js:3", "createPracticeSession(payload)", "POST /practice/sessions"),
        ("后端路由", "backend/app/api/v1/practice.py:32", "create_session_endpoint()", "创建会话并组装 QuestionOut"),
        ("后端路由", "backend/app/api/v1/practice.py:46-57", "QuestionOut 组装", "hint 仅返回 length=len(spelling)，无 spelling"),
        ("后端服务", "backend/app/services/practice.py:103", "create_session()", "选题、落库会话与题目、生成 notice"),
        ("后端服务", "backend/app/services/practice.py:82", "_load_normal_words()", "校验 published 并按词书取词"),
        ("后端服务", "backend/app/services/practice.py:91", "_load_wrong_words()", "JOIN words，仅取 resolved=false"),
        ("后端服务", "backend/app/services/practice.py:66", "_load_progress()", "批量读取用户 WordProgress"),
        ("后端服务", "backend/app/services/practice.py:39", "_select_words()", "未掌握优先 + 已掌握配额 + 随机 + 补齐"),
        ("后端服务", "backend/app/services/practice.py:24", "_split_by_mastery()", "mastery_level ≥ 2 视为已掌握"),
        ("数据模型", "backend/app/models/practice_session.py:22", "PracticeSession", "mode / strict_mode / total_count / status"),
        ("数据模型", "backend/app/models/session_question.py:35", "SessionQuestion", "会话题目，uq(session_id, word_id)"),
        ("数据模型", "backend/app/models/word_progress.py:33", "WordProgress", "mastery_level 与连续正确次数"),
    ],
    branches=[
        ("normal 缺少 wordbook_id", "practice.py:114-115", "422 normal 模式需要 wordbook_id"),
        ("词书不存在或未发布", "practice.py:84-85；wordbook.py:115-116", "404"),
        ("候选词为空", "practice.py:121-123", "400 词书暂无单词 / 错词本为空"),
        ("可用词数少于题数", "practice.py:131-133", "按实际出题并返回 notice"),
        ("题量参数非法", "schemas/practice.py:10", "count 仅允许 10/20/50，默认 20"),
        ("前端重复点击开始", "Practice.vue:56", "phase==='loading' 直接返回"),
        ("出题响应泄露拼写", "schemas/practice.py:18-25", "QuestionOut 无 spelling 字段，从契约上杜绝"),
    ],
)

add(
    num="07", title="判分、掌握度与即时反馈（F5）", feature="F5 判分反馈",
    diagram="07-practice-answer.svg",
    summary=(
        "判分只在服务端进行：先做 strip+lower，再按 24 组英美变体判定，严格模式直接比较，宽松模式额外忽略连字符与空格。"
        "同一题重复提交通过 practice_records 唯一键与首次结果查询保证幂等。答对累加连续正确次数，达到 2 次升为已掌握并把错词置 resolved；"
        "答错降为学习中、错词累加或新建并复位。只有答错才回传正确拼写与例句。"
    ),
    nodes=[
        ("前端组件", "frontend/src/components/SpellInput.vue:31", "handleKeydown()", "Enter 触发 submit"),
        ("前端组件", "frontend/src/components/practice/QuestionCard.vue:34", "submit()", "isBusy / isSubmitted / 空输入拦截"),
        ("前端组件", "frontend/src/components/practice/QuestionCard.vue:28", "isBusy", "submitting/finishing 时禁用按钮"),
        ("前端视图", "frontend/src/views/user/Practice.vue:88", "submitAnswer()", "空答案直接返回"),
        ("前端状态", "frontend/src/stores/practice.js:71", "submitAnswer()", "状态守卫，phase=submitting → submitted"),
        ("前端 API", "frontend/src/api/practice.js:7", "submitPracticeAnswer()", "POST /practice/sessions/{id}/answer"),
        ("后端路由", "backend/app/api/v1/practice.py:75", "answer_question_endpoint()", "response_model_exclude_none 裁掉 None 字段"),
        ("后端服务", "backend/app/services/practice_answer.py:81", "answer_question()", "判分主流程"),
        ("后端服务", "backend/app/services/practice_answer.py:90-98", "会话校验", "行锁、归属、已结束判断"),
        ("后端服务", "backend/app/services/practice_answer.py:55", "_find_existing_answer()", "幂等：已作答则返回首次结果"),
        ("后端服务", "backend/app/services/practice_answer.py:104-111", "题目归属校验", "word 必须属于该 session"),
        ("后端服务", "backend/app/services/grading.py:22", "is_correct_answer()", "严格/宽松判分主函数"),
        ("后端服务", "backend/app/services/grading.py:6", "normalize_input()", "strip + lower"),
        ("后端服务", "backend/app/services/grading.py:17", "_remove_hyphens_and_spaces()", "宽松模式忽略连字符/空格"),
        ("后端服务", "backend/app/services/spelling_variants.py:37", "get_variant_group()", "24 组英美拼写变体"),
        ("后端服务", "backend/app/services/practice_answer.py:142-159", "正确分支", "correct_count+1；连续≥2 → mastery=2；错词 resolved"),
        ("后端服务", "backend/app/services/practice_answer.py:160-188", "错误分支", "mastery=1；错词新建/累加/复位"),
        ("后端服务", "backend/app/services/practice_answer.py:191-199", "PracticeRecord 写入", "答题流水"),
        ("后端服务", "backend/app/services/practice_answer.py:32", "_build_answer_result()", "正确不回拼写；错误回拼写与例句"),
        ("数据模型", "backend/app/models/practice_record.py:37", "PracticeRecord", "uq(session_id, word_id) 保证幂等"),
        ("数据模型", "backend/app/models/word_progress.py:44", "WordProgress.mastery_level", "0 新词 / 1 学习中 / 2 已掌握"),
        ("数据模型", "backend/app/models/wrong_word.py:32", "WrongWord", "wrong_count / resolved / resolved_at"),
    ],
    branches=[
        ("会话已结束", "practice_answer.py:97-98", "400 练习会话已结束"),
        ("session 或 word 不存在/不归属", "practice_answer.py:90-111", "404"),
        ("同一题重复提交", "practice_answer.py:100-102, 202-217", "返回首次结果，不重复计分"),
        ("答案正确", "practice_answer.py:32-44", "is_correct=true，correct_spelling 为 None 并被裁掉"),
        ("答案错误", "practice_answer.py:46-52", "is_correct=false，回传 correct_spelling + 例句"),
        ("连续正确达到 2 次", "grading.py:3；practice_answer.py:146-158", "mastery=2，错词 resolved=true"),
        ("答错已解决错词", "practice_answer.py:184-188", "resolved=false，resolved_at=null，wrong_count+1"),
        ("前端重复提交", "stores/practice.js:73；QuestionCard.vue:35,137", "状态守卫 + disabled 双重防护"),
    ],
)

add(
    num="08", title="错词本自动生成与移除（F6）", feature="F6 错词本",
    diagram="08-wrong-words.svg",
    summary=(
        "错词本不依赖独立录入，而是判分流程的副产物：答错时按 (user_id, word_id) 新建或累加，答对累计 2 次即置 resolved。"
        "列表默认只查 resolved=false，支持翻页、切换“已解决”与手动移除；移除后再答错会重新建条。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/user/WrongWords.vue:63", "watch(page, loadWrongWords, {immediate:true})", "列表加载驱动"),
        ("前端视图", "frontend/src/views/user/WrongWords.vue:22", "loadWrongWords()", "默认 resolved=false"),
        ("前端视图", "frontend/src/views/user/WrongWords.vue:41", "changeFilter(nextResolved)", "切换待攻克/已解决"),
        ("前端视图", "frontend/src/views/user/WrongWords.vue:47", "confirmRemove(wordId)", "removingId 防重复点击"),
        ("前端视图", "frontend/src/views/user/WrongWords.vue:155", "AudioButton", "行内发音（见 F11）"),
        ("前端 API", "frontend/src/api/wrongWords.js:3", "listWrongWords()", "GET /wrong-words"),
        ("前端 API", "frontend/src/api/wrongWords.js:9", "removeWrongWord()", "DELETE /wrong-words/{word_id}"),
        ("后端路由", "backend/app/api/v1/wrong_words.py:25", "list_wrong_words_endpoint()", "分页查询错词"),
        ("后端路由", "backend/app/api/v1/wrong_words.py:66", "remove_wrong_word_endpoint()", "移除单条错词"),
        ("后端服务", "backend/app/services/wrong_word.py:9", "list_wrong_words()", "resolved 过滤 + last_wrong_at 倒序"),
        ("后端服务", "backend/app/services/wrong_word.py:38", "remove_wrong_word()", "不存在 404"),
        ("后端服务", "backend/app/services/practice_answer.py:174-183", "错误分支：新建", "首次答错插入 WrongWord，wrong_count=1"),
        ("后端服务", "backend/app/services/practice_answer.py:184-188", "错误分支：累加复位", "wrong_count+1，resolved=false，resolved_at=null"),
        ("后端服务", "backend/app/services/practice_answer.py:146-158", "正确分支：解决", "连续正确≥2 置 resolved=true"),
        ("数据模型", "backend/app/models/wrong_word.py:32", "WrongWord", "uq(user_id, word_id)；wrong_count / resolved"),
    ],
    branches=[
        ("错词不存在（手动移除）", "wrong_word.py:50-51", "404"),
        ("答错首次", "practice_answer.py:174-183", "新建记录，立即出现在错词本"),
        ("答错已有错词", "practice_answer.py:184-188", "累加次数，不重复建条"),
        ("连续答对 2 次", "practice_answer.py:146-158", "resolved=true，从默认列表消失"),
        ("移除后再次答错", "practice_answer.py:174-183", "重新建条（唯一键已释放）"),
        ("移除请求重复点击", "WrongWords.vue:48", "removingId 非空直接返回"),
    ],
)

add(
    num="09", title="掌握度与词书进度（F7）", feature="F7 掌握度与进度",
    diagram="09-mastery-progress.svg",
    summary=(
        "掌握度存放在 word_progress，由判分流程实时回写：连续正确 2 次升为已掌握，答错降为学习中。"
        "词书进度不落冗余字段，而是每次由 word_progress 聚合出“已掌握/总词数”；练习结束时再 upsert user_wordbooks，"
        "全部掌握则标记 completed。单词列表支持按 mastery 精确筛选。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/user/WordbookDetail.vue:39", "loadPage()", "并发加载词书详情与单词列表"),
        ("前端视图", "frontend/src/views/user/WordbookDetail.vue:27", "masteryLabel(level)", "0 新词 / 1 学习中 / 2 已掌握"),
        ("前端视图", "frontend/src/views/user/WordbookDetail.vue:33", "masteryClass(level)", "掌握度颜色点样式"),
        ("前端视图", "frontend/src/views/user/Practice.vue", "PracticeComplete 展示", "本轮 total / correct / accuracy"),
        ("前端 API", "frontend/src/api/wordbooks.js:3", "listWordbooks()", "GET /wordbooks，含 my_progress"),
        ("前端 API", "frontend/src/api/wordbooks.js:11", "listWordbookWords()", "GET /wordbooks/{id}/words?mastery="),
        ("前端 API", "frontend/src/api/practice.js:11", "finishPracticeSession()", "POST /practice/sessions/{id}/finish"),
        ("后端路由", "backend/app/api/v1/wordbooks.py:31", "list_wordbooks_endpoint()", "用户端词书分页"),
        ("后端路由", "backend/app/api/v1/wordbooks.py:63", "get_wordbook_endpoint()", "词书详情"),
        ("后端路由", "backend/app/api/v1/wordbooks.py:83", "list_wordbook_words_endpoint()", "单词列表与掌握度"),
        ("后端路由", "backend/app/api/v1/practice.py:107", "finish_session_endpoint()", "结束练习"),
        ("后端服务", "backend/app/services/wordbook.py:120", "list_published_wordbooks()", "已掌握数/总词数聚合"),
        ("后端服务", "backend/app/services/wordbook.py:180", "list_published_words()", "coalesce(mastery_level,0) 过滤"),
        ("后端服务", "backend/app/services/practice_finish.py:132", "finish_session()", "幂等结束，写入 finished_at"),
        ("后端服务", "backend/app/services/practice_finish.py:82", "_update_user_wordbook()", "upsert 进度；全部掌握置 completed"),
        ("后端服务", "backend/app/services/practice_answer.py:142-164", "掌握度回写", "正确升/错误降的即时更新"),
        ("数据模型", "backend/app/models/word_progress.py:44", "mastery_level / consecutive_correct", "掌握度与连续正确计数"),
        ("数据模型", "backend/app/models/user_wordbook.py:25", "UserWordbook", "status: learning / completed"),
    ],
    branches=[
        ("单词从未练习", "wordbook.py:190-197", "coalesce 为 0，显示新词"),
        ("连续正确达到 2 次", "practice_answer.py:146-147", "mastery_level=2"),
        ("答错", "practice_answer.py:161-164", "mastery_level=1，consecutive_correct=0"),
        ("按掌握度筛选", "wordbook.py:190-197", "mastery=0/1/2 精确过滤"),
        ("练习结束且全部掌握", "practice_finish.py:128-129", "user_wordbooks.status=completed"),
        ("重复调用 finish", "practice_finish.py:139-140", "幂等返回既有汇总，不改 finished_at"),
        ("进度计算口径", "wordbook.py:133-143", "每次实时聚合，不存冗余字段"),
    ],
)

add(
    num="10", title="错词专项重练（F8）", feature="F8 错词重练",
    diagram="10-wrong-only-practice.svg",
    summary=(
        "错词重练复用普通练习的整套链路，只把 mode 换成 wrong_only：服务端忽略 wordbook_id，只从当前用户 resolved=false 的错词中出题，"
        "题数不超过错词数。作答与结束流程完全一致，因此掌握度提升与错词 resolved 规则不会出现两套实现。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/user/WrongWords.vue:74-79", "RouterLink → /practice?mode=wrong_only&amp;count=10", "错词本入口"),
        ("前端视图", "frontend/src/components/practice/PracticeSetup.vue:57-62", "切到错词专项 → start()", "设置面板入口"),
        ("前端视图", "frontend/src/views/user/Practice.vue:69", "startFromQuery()", "解析 mode 与题数"),
        ("前端视图", "frontend/src/views/user/Practice.vue:55", "startPractice()", "启动会话"),
        ("前端视图", "frontend/src/views/user/Practice.vue:114", "replay()", "按 activeConfig 再来一组"),
        ("前端状态", "frontend/src/stores/practice.js:53", "wrong_only 时 wordbook_id=null", "避免词书参数干扰"),
        ("前端 API", "frontend/src/api/practice.js:3", "createPracticeSession()", "POST /practice/sessions"),
        ("后端路由", "backend/app/api/v1/practice.py:32", "create_session_endpoint()", "创建重练会话"),
        ("后端服务", "backend/app/services/practice.py:117-119", "else 分支 wrong_only", "忽略 wordbook_id"),
        ("后端服务", "backend/app/services/practice.py:91", "_load_wrong_words()", "只取 resolved=false 的词"),
        ("后端服务", "backend/app/services/practice.py:121-123", "空错词本校验", "400 错词本为空"),
        ("后端服务", "backend/app/services/practice.py:39", "_select_words()", "随机与题数上限"),
        ("后端服务", "backend/app/services/practice_answer.py:81", "answer_question()", "与普通练习共用判分"),
        ("后端服务", "backend/app/services/practice_answer.py:184-188", "答错复位", "resolved=false，wrong_count+1"),
        ("后端服务", "backend/app/services/practice_answer.py:146-158", "达标解决", "连续正确 2 次 resolved=true"),
        ("数据模型", "backend/app/models/practice_session.py:37", "PracticeSession.mode", "normal / wrong_only"),
        ("数据模型", "backend/app/models/wrong_word.py:45", "WrongWord.resolved", "重练候选集来源"),
    ],
    branches=[
        ("错词本为空", "practice.py:121-123", "400，前端提示不可开始"),
        ("题数超过错词数", "practice.py:39-64", "按实际数量出题，返回 notice"),
        ("URL count 非 10/20/50", "Practice.vue:71-72", "前端回落到 10"),
        ("重练中答错", "practice_answer.py:184-188", "错词保留并累加，resolved 复位"),
        ("重练达标", "practice_answer.py:146-158", "resolved=true，从错词本消失"),
        ("复用普通练习", "practice.py:103 起", "同一套选题/判分/结束实现，无分支复制"),
    ],
)

add(
    num="11", title="个人数据看板（F9）", feature="F9 个人看板",
    diagram="11-stats-user.svg",
    summary=(
        "首页只取概览三项指标；学习账本额外按日期区间取每日答题趋势。后端以 practice_records JOIN practice_sessions 为主数据源，"
        "按应用时区计算活跃日期与连续天数；每日趋势在数据库内按本地自然日 GROUP BY，前端补零对齐后绘制折线图与迷你趋势线。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/user/Home.vue:22", "onMounted()", "并发加载概览与词书"),
        ("前端视图", "frontend/src/views/user/Home.vue:46-63", "模板渲染", "累计默写 / 正确率 / 连续天数"),
        ("前端视图", "frontend/src/views/user/Profile.vue:97", "loadProfile()", "并发加载概览与每日趋势"),
        ("前端视图", "frontend/src/views/user/Profile.vue:114", "changeRange(days)", "切换 7/30 天"),
        ("前端视图", "frontend/src/views/user/Profile.vue:38-46", "chartItems / trendValues", "按日期补零对齐"),
        ("前端视图", "frontend/src/views/user/Profile.vue:47-78", "metrics computed", "组装五项个人指标"),
        ("前端组件", "frontend/src/components/LineChart.vue:14", "chart computed", "折线坐标、polyline、峰值"),
        ("前端组件", "frontend/src/components/Sparkline.vue:10", "points computed", "迷你趋势线坐标"),
        ("前端工具", "frontend/src/utils/format.js:49", "buildDateRange(days)", "生成 {from,to}"),
        ("前端 API", "frontend/src/api/stats.js:3", "getStatsOverview()", "GET /stats/overview"),
        ("前端 API", "frontend/src/api/stats.js:7", "getStatsDaily()", "GET /stats/daily?from=&amp;to="),
        ("后端路由", "backend/app/api/v1/stats.py:22", "get_overview_endpoint()", "个人概览"),
        ("后端路由", "backend/app/api/v1/stats.py:42", "get_daily_endpoint()", "每日趋势"),
        ("后端服务", "backend/app/services/stats.py:69", "get_overview()", "五项指标聚合"),
        ("后端服务", "backend/app/services/stats.py:70-82", "累计答题/正确率", "practice_records JOIN practice_sessions"),
        ("后端服务", "backend/app/services/stats.py:60", "_compute_streak()", "活跃日期集合计算连续天数"),
        ("后端服务", "backend/app/services/stats.py:96-113", "已掌握/错词", "word_progress + wrong_words"),
        ("后端服务", "backend/app/services/stats.py:124", "get_daily()", "日期校验、时区换算、按日聚合"),
        ("数据模型", "backend/app/models/practice_record.py:19", "PracticeRecord", "统计主数据源"),
        ("数据模型", "backend/app/models/word_progress.py:20", "WordProgress", "已掌握词数来源"),
        ("数据模型", "backend/app/models/wrong_word.py:19", "WrongWord", "未解决错词数来源"),
    ],
    branches=[
        ("无任何练习记录", "services/stats.py:70-82", "返回 0，前端展示鼓励文案"),
        ("日期跨度超过 90 天", "services/stats.py:130-133", "422 校验失败"),
        ("起始日期晚于结束日期", "services/stats.py:130-133", "422"),
        ("某日无答题", "Profile.vue:38-45", "前端补零，折线连续"),
        ("断签", "services/stats.py:60-66", "连续天数归零"),
        ("时区边界", "services/stats.py:135-139", "按 APP_TIMEZONE 换算 UTC 边界"),
    ],
)

add(
    num="12", title="管理员用户管理（F10）", feature="F10 用户管理",
    diagram="12-admin-users.svg",
    summary=(
        "用户列表支持分页、关键词模糊搜索与状态筛选，并在同一次查询中聚合每人的练习次数。"
        "禁用/启用、重置密码、查看学习数据均通过 require_admin 保护；前后端都禁止管理员禁用自己，"
        "列表响应不返回密码哈希。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/admin/UserManage.vue:132", "watch(page, loadUsers, {immediate:true})", "列表加载驱动"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:43", "loadUsers()", "分页查询并填充 items/total"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:62", "applyFilters()", "关键词搜索并回到第 1 页"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:68", "applyStatusFilter()", "active / disabled 筛选"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:73", "toggleStatus(user)", "先在前端拦截禁用自己"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:92", "openReset(user)", "打开重置密码抽屉"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:101", "openStats(user)", "打开学习数据抽屉"),
        ("前端组件", "frontend/src/components/admin/ResetPasswordDrawer.vue:30", "submit()", "校验长度与一致性后提交"),
        ("前端组件", "frontend/src/components/admin/UserStatsDrawer.vue:17", "defineEmits", "close / load-profile"),
        ("前端 API", "frontend/src/api/admin.js:41", "listAdminUsers()", "GET /admin/users"),
        ("前端 API", "frontend/src/api/admin.js:52", "updateAdminUserStatus()", "PATCH /admin/users/{id}/status"),
        ("前端 API", "frontend/src/api/admin.js:56", "resetAdminUserPassword()", "POST /admin/users/{id}/reset-password"),
        ("前端 API", "frontend/src/api/admin.js:60", "getAdminUserStats()", "GET /admin/users/{id}/stats"),
        ("后端路由", "backend/app/api/v1/admin_users.py:29", "Depends(require_admin)", "整组接口权限依赖"),
        ("后端路由", "backend/app/api/v1/admin_users.py:33", "list_users_endpoint()", "分页/搜索/筛选"),
        ("后端路由", "backend/app/api/v1/admin_users.py:72", "update_user_status_endpoint()", "启用/禁用"),
        ("后端路由", "backend/app/api/v1/admin_users.py:88", "reset_password_endpoint()", "重置密码"),
        ("后端路由", "backend/app/api/v1/admin_users.py:104", "get_user_stats_endpoint()", "指定用户学习概览"),
        ("后端服务", "backend/app/services/admin_user.py:19", "list_users()", "模糊搜索 + 状态筛选 + 练习数聚合 + 分页"),
        ("后端服务", "backend/app/services/admin_user.py:55", "_require_user()", "用户不存在 404"),
        ("后端服务", "backend/app/services/admin_user.py:62", "update_user_status()", "禁止禁用自己"),
        ("后端服务", "backend/app/services/admin_user.py:78", "reset_password()", "长度校验 + bcrypt 哈希"),
        ("后端服务", "backend/app/services/admin_user.py:95", "get_user_stats()", "复用 stats.get_overview()"),
        ("数据模型", "backend/app/models/user.py:9", "User", "role / status / password_hash"),
    ],
    branches=[
        ("非管理员访问", "deps.py:50-51", "403 / 40301"),
        ("禁用自己", "admin_user.py:69-70", "400 不能禁用自己"),
        ("禁用自己（前端按钮）", "UserManage.vue:213", "按钮 disabled"),
        ("目标用户不存在", "admin_user.py:55-59", "404"),
        ("重置密码长度非法", "admin_user.py:85-86", "422"),
        ("关键词为空", "admin_users.py:46", "strip 后不参与模糊匹配"),
        ("分页越界", "admin_user.py:47-51", "返回空 items，total 仍为真实总数"),
        ("列表不返回密码", "schemas/admin_user.py", "响应模型不含 password_hash"),
    ],
)

add(
    num="13", title="管理员数据概览（F13）", feature="F13 数据概览",
    diagram="13-admin-overview.svg",
    summary=(
        "管理端概览把六项指标合并到一次数据库往返中：分别用标量子查询统计用户、活跃用户、词书、单词、今日会话与今日答题，"
        "再执行一次 execute 并 result.one() 取值，避免多次往返。今日边界按应用时区换算。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/admin/Overview.vue:62", "onMounted(loadOverview)", "进入页面即加载"),
        ("前端视图", "frontend/src/views/admin/Overview.vue:50", "loadOverview()", "请求管理员概览"),
        ("前端视图", "frontend/src/views/admin/Overview.vue:11-48", "metrics computed", "组装六项平台指标"),
        ("前端视图", "frontend/src/views/admin/Overview.vue:91-100", "模板渲染", "六张指标卡"),
        ("前端 API", "frontend/src/api/admin.js:37", "getAdminOverview()", "GET /admin/overview"),
        ("后端路由", "backend/app/api/v1/admin_stats.py:13-17", "Depends(require_admin)", "权限依赖"),
        ("后端路由", "backend/app/api/v1/admin_stats.py:20", "get_admin_overview_endpoint()", "概览端点"),
        ("后端服务", "backend/app/services/admin_stats.py:19", "get_admin_overview()", "六项指标聚合"),
        ("后端服务", "backend/app/services/admin_stats.py:21-28", "今日/近 7 天边界", "按 APP_TIMEZONE 换算 UTC"),
        ("后端服务", "backend/app/services/admin_stats.py:30", "total_users", "users 计数"),
        ("后端服务", "backend/app/services/admin_stats.py:31-40", "active_users", "练习会话 JOIN 答题，按用户去重"),
        ("后端服务", "backend/app/services/admin_stats.py:41-42", "total_wordbooks / total_words", "词书与单词计数"),
        ("后端服务", "backend/app/services/admin_stats.py:43-58", "today_sessions / today_answers", "按今日边界计数"),
        ("后端服务", "backend/app/services/admin_stats.py:60-70", "execute + result.one()", "一次查询返回六个标量"),
        ("数据模型", "backend/app/models/practice_session.py:9", "PracticeSession", "今日会话数据源"),
        ("数据模型", "backend/app/models/practice_record.py:19", "PracticeRecord", "今日答题与活跃用户数据源"),
    ],
    branches=[
        ("非管理员访问", "deps.py:50-51", "403 / 40301"),
        ("平台无数据", "admin_stats.py:30-58", "各计数返回 0"),
        ("活跃用户口径", "admin_stats.py:31-40", "近期有练习会话且产生答题的去重用户"),
        ("今日边界", "admin_stats.py:21-28", "按应用时区而非 UTC 自然日"),
    ],
)

add(
    num="14", title="发音播放（F11）", feature="F11 发音播放",
    diagram="14-audio.svg",
    summary=(
        "播放遵循三级回退：优先使用词库自带 audio_url；没有则请求服务端 TTS（Windows SAPI 合成 WAV，按单词与口音缓存）；"
        "服务端不可用或合成失败时，最后回退浏览器 SpeechSynthesis。英美音标切换由调用方传入 accent，语音与音标保持同步。"
    ),
    nodes=[
        ("前端组件", "frontend/src/components/AudioButton.vue:86", "play()", "三级回退主入口"),
        ("前端组件", "frontend/src/components/AudioButton.vue:28", "playUrl(url)", "释放旧音频后 new Audio 播放"),
        ("前端组件", "frontend/src/components/AudioButton.vue:35", "playSystemAudio()", "请求后端 TTS Blob 并播放"),
        ("前端组件", "frontend/src/components/AudioButton.vue:71", "playTts(text)", "浏览器 SpeechSynthesis 兜底"),
        ("前端组件", "frontend/src/components/AudioButton.vue:56", "pickVoice(lang)", "en-US / en-GB 语音选择"),
        ("前端组件", "frontend/src/components/AudioButton.vue:19", "releaseAudio()", "pause + revokeObjectURL"),
        ("前端组件", "frontend/src/components/practice/QuestionCard.vue:54-69", "accent ref 与切换", "默认 uk，切换后通过 :key 重建按钮"),
        ("前端页面", "frontend/src/views/user/WordbookDetail.vue:152", "AudioButton 使用", "词库详情行内发音"),
        ("前端页面", "frontend/src/views/user/WrongWords.vue:155", "AudioButton 使用", "错词行内发音"),
        ("前端 API", "frontend/src/api/audio.js:3", "getWordAudio()", "GET /words/{id}/audio"),
        ("前端 API", "frontend/src/api/audio.js:7", "getWordTtsAudio()", "GET /words/{id}/audio/file?accent=，blob"),
        ("后端路由", "backend/app/api/v1/audio.py:21", "路由级 get_current_user", "发音接口需登录"),
        ("后端路由", "backend/app/api/v1/audio.py:24", "get_word_audio_endpoint()", "返回 audio_url 或 TTS 标记"),
        ("后端路由", "backend/app/api/v1/audio.py:39", "get_word_audio_file_endpoint()", "合成并返回 WAV FileResponse"),
        ("后端服务", "backend/app/services/audio.py:7", "get_word_audio()", "读 Word.audio_url，缺失返回 fallback=tts"),
        ("后端服务", "backend/app/services/tts.py:89", "synthesize_word_audio()", "合成入口与缓存读写"),
        ("后端服务", "backend/app/services/tts.py:30", "_digest()", "按 voice/culture/rate/spelling 生成缓存键"),
        ("后端服务", "backend/app/services/tts.py:40", "_build_script()", "生成 PowerShell SAPI 脚本"),
        ("后端服务", "backend/app/services/tts.py:64", "_run_powershell()", "asyncio.to_thread 执行子进程"),
        ("数据模型", "backend/app/models/word.py:50", "Word.audio_url", "词库自带音频地址，可空"),
        ("数据契约", "backend/app/schemas/audio.py:6", "AudioOut", "audio_url / tts_text / fallback"),
    ],
    branches=[
        ("单词不存在", "audio.py:48-49；services/audio.py:13-14", "404 / 40401"),
        ("词库有 audio_url", "services/audio.py:16-17", "返回 audio_url，前端直接播放"),
        ("词库无 audio_url", "services/audio.py:18", "返回 {tts_text: spelling, fallback:'tts'}"),
        ("非 Windows 或无 PowerShell", "tts.py:91-96", "TtsUnavailableError → 503 / 50301"),
        ("合成输出为空", "tts.py:117-118", "503"),
        ("缓存命中", "tts.py:101-103", "直接返回已缓存 WAV"),
        ("后端 TTS 失败", "AudioButton.vue:39-42", "静默返回 false，回退浏览器 TTS"),
        ("浏览器不支持 speechSynthesis", "AudioButton.vue:72", "抛错并置 status=error"),
    ],
)

add(
    num="15", title="AI 会话管理（F14）", feature="F14 AI 英语对话",
    diagram="15-ai-sessions.svg",
    summary=(
        "会话与消息持久化在 ai_conversations / ai_messages。前端挂载时拉取列表并默认选中首条，"
        "切换会话读取详情，新建会话可带场景，删除会话时消息随外键级联删除。所有查询都带 user_id 过滤，"
        "越权访问统一返回 404。"
    ),
    nodes=[
        ("前端视图", "frontend/src/views/user/AiChat.vue:32", "loadSessions()", "拉取会话列表并默认选中第一条"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:47", "selectConversation(id)", "先中断流，再加载详情"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:75", "startNewConversation()", "新建会话并置为当前"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:149", "removeConversation(id)", "删除会话并切到下一条"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:165", "onMounted / onBeforeUnmount", "初始化加载 / 卸载中断流"),
        ("前端组件", "frontend/src/components/ai/ConversationSidebar.vue:14", "defineEmits(select/create/delete/close)", "会话侧栏事件"),
        ("前端组件", "frontend/src/components/ai/ConversationSidebar.vue:24", "confirmDelete(id)", "二次点击确认删除"),
        ("前端组件", "frontend/src/components/ai/ChatComposer.vue:15-21", "scenes / update:scene", "场景选择：自由/餐厅/面试/旅行/校园"),
        ("前端 API", "frontend/src/api/ai.js:8", "listAiSessions()", "GET /ai/sessions"),
        ("前端 API", "frontend/src/api/ai.js:12", "createAiSession()", "POST /ai/sessions"),
        ("前端 API", "frontend/src/api/ai.js:16", "getAiSession()", "GET /ai/sessions/{id}"),
        ("前端 API", "frontend/src/api/ai.js:20", "deleteAiSession()", "DELETE /ai/sessions/{id}"),
        ("后端路由", "backend/app/api/v1/ai.py:26-30", "router 级鉴权", "所有会话接口需要登录"),
        ("后端路由", "backend/app/api/v1/ai.py:33", "list_sessions_endpoint()", "会话分页列表"),
        ("后端路由", "backend/app/api/v1/ai.py:65", "create_session_endpoint()", "201 创建"),
        ("后端路由", "backend/app/api/v1/ai.py:84", "get_session_endpoint()", "详情 + 消息"),
        ("后端路由", "backend/app/api/v1/ai.py:113", "delete_session_endpoint()", "删除会话"),
        ("后端服务", "backend/app/services/ai_conversation.py:48", "list_conversations()", "user_id 过滤 + updated_at 倒序 + 消息数"),
        ("后端服务", "backend/app/services/ai_conversation.py:76", "create_conversation()", "新建并提交"),
        ("后端服务", "backend/app/services/ai_conversation.py:92", "get_conversation_detail()", "消息按 id 正序"),
        ("后端服务", "backend/app/services/ai_conversation.py:31", "get_owned_conversation()", "归属校验，越权/不存在 404"),
        ("后端服务", "backend/app/services/ai_conversation.py:108", "delete_conversation()", "校验归属后删除"),
        ("后端服务", "backend/app/services/ai_conversation.py:21", "build_conversation_title()", "首条消息压缩空白后前 30 字"),
        ("数据模型", "backend/app/models/ai_conversation.py:9", "AiConversation", "user_id / title / scene"),
        ("数据模型", "backend/app/models/ai_message.py:9", "AiMessage", "FK conversation_id ON DELETE CASCADE"),
    ],
    branches=[
        ("会话不属于当前用户", "ai_conversation.py:43-44", "404，不泄露是否存在"),
        ("会话不存在", "ai_conversation.py:38-42", "404"),
        ("删除会话语义", "ai_message.py:22-29", "消息随外键级联删除"),
        ("未传标题", "ai_conversation.py:21-28", "由首条用户消息生成"),
        ("删除当前会话时正在流式生成", "AiChat.vue:150", "先 abort 再删除"),
        ("列表为空", "AiChat.vue:37-39", "显示空状态，不自动新建"),
    ],
)

add(
    num="16", title="AI 流式对话（F14）", feature="F14 AI 英语对话",
    diagram="16-ai-stream.svg",
    summary=(
        "一次对话 = 会话准备 + Router 意图识别 + Skill 组装提示词 + 模型流式生成 + SSE 转发 + 消息落库。"
        "Router 先用本地关键词判断，意图明确直接分发；否则调用模型为全部技能评分。模型不可用或 JSON 非法时回退关键词规则，"
        "fallback_used=true。事件顺序固定为 meta → delta* → done；客户端中断时已生成的部分文本仍会保存。"
    ),
    nodes=[
        ("前端组件", "frontend/src/components/ai/ChatComposer.vue:23", "submit()", "非空且非流式时 emit('send')"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:98", "sendMessage(text)", "无会话先新建，push 占位消息"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:111-112", "AbortController", "流式请求控制器"),
        ("前端视图", "frontend/src/views/user/AiChat.vue:145", "stopStreaming()", "controller.abort()"),
        ("前端 API", "frontend/src/api/ai.js:32", "streamAgentChat()", "fetch POST /agent/chat，携带 Bearer"),
        ("前端工具", "frontend/src/utils/sse.js:63", "consumeSseResponse()", "getReader() 逐块读取"),
        ("前端工具", "frontend/src/utils/sse.js:38", "createSseParser()", "按 \\n\\n 分帧"),
        ("前端工具", "frontend/src/utils/sse.js:8", "parseSseFrame()", "解析 event / data"),
        ("前端 API", "frontend/src/api/ai.js:71-81", "事件分发", "meta / delta / done / error"),
        ("后端路由", "backend/app/api/v1/agent.py:74", "agent_chat()", "SSE 端点，StreamingResponse"),
        ("后端服务", "backend/app/services/ai_conversation.py:136", "prepare_chat_turn()", "建会话 / 归属校验 / 读历史 / 写用户消息"),
        ("后端服务", "backend/app/services/ai_conversation.py:118", "load_recent_history()", "最近 20 条消息"),
        ("后端服务", "backend/app/services/agent/service.py:56", "AgentService.stream_events()", "产出 meta / delta / done"),
        ("后端服务", "backend/app/services/agent/router.py:144", "IntentRouter.decide()", "关键词优先，否则模型评分"),
        ("后端服务", "backend/app/services/agent/heuristics.py:54", "keyword_classify()", "五类意图关键词规则"),
        ("后端服务", "backend/app/services/agent/router.py:83", "_fallback_scores()", "关键词评分兜底"),
        ("后端服务", "backend/app/services/agent/router.py:94", "_build_decision()", "选最高分并组装决策"),
        ("后端服务", "backend/app/services/agent/skills/base.py:26", "Skill.build_messages()", "system + history + user"),
        ("后端服务", "backend/app/services/agent/skills/__init__.py:12", "build_default_registry()", "注册 5 个技能，GENERAL 默认"),
        ("后端服务", "backend/app/services/agent/client.py:154", "OpenAICompatibleClient.stream()", "调用 /chat/completions 流式增量"),
        ("后端服务", "backend/app/services/agent/client.py:58", "MockLLMClient.stream()", "未配置模型时的假数据流"),
        ("后端服务", "backend/app/services/agent/client.py:196", "get_llm_client()", "按配置选择真实/Mock 客户端"),
        ("后端路由", "backend/app/api/v1/agent.py:30", "_stream_chat()", "转发事件并累计 delta"),
        ("后端服务", "backend/app/services/ai_conversation.py:174", "save_assistant_message()", "独立会话保存 assistant 全文"),
        ("数据模型", "backend/app/models/ai_message.py:9", "AiMessage", "用户消息流前写入，assistant 流后写入"),
        ("数据契约", "backend/app/schemas/agent.py:9", "AgentChatIn", "message / scene / conversation_id / history≤20"),
    ],
    branches=[
        ("关键词命中", "router.py:145-152", "直接分发，fallback_used=false"),
        ("模型评分失败或 JSON 非法", "router.py:165-167, 178-183", "回退关键词规则，fallback_used=true"),
        ("未配置 AI_PROVIDER/KEY", "client.py:189-206", "MockLLMClient 假数据流，链路仍可跑通"),
        ("模型 HTTP ≥400", "client.py:165-167 → agent.py:56-58", "发送 error 事件，已生成部分仍落库"),
        ("客户端中断", "agent.py:59-62, 65-71", "finally 拼接已生成文本，shield 落库"),
        ("会话不存在或不属于当前用户", "ai_conversation.py:43-44", "404"),
        ("SSE 未收到 done", "ai.js:84-86", "前端按连接中断处理"),
        ("无 conversation_id", "ai_conversation.py:145-153", "新建会话并用客户端 history"),
        ("meta 事件内容", "service.py:66-84；agent.py:51-52", "intent/skill/scene/confidence/fallback_used/candidates/reason/conversation_id"),
    ],
)

add(
    num="17", title="学情画像：黑板与多专家编排", feature="管理员学情画像",
    diagram="17-profile.svg",
    summary=(
        "画像由 Blackboard + Controller + 四位专家组成。每次请求先把用户的 word_progress、wrong_words、practice_sessions 装入黑板，"
        "用数据指纹作为缓存键；未命中时控制器按匹配度、优先级与依赖关系调度 data → habit → diagnosis → planner，"
        "每位专家先算确定性 heuristic，再尝试用 LLM 精炼，失败自动回退。最后评估整体置信度并组装可渲染的标签、雷达图与建议。"
    ),
    nodes=[
        ("前端组件", "frontend/src/components/admin/UserStatsDrawer.vue:55-67", "生成学情画像按钮", "emit('load-profile')"),
        ("前端视图", "frontend/src/views/admin/UserManage.vue:118", "loadProfile()", "请求画像并管理加载/错误态"),
        ("前端 API", "frontend/src/api/admin.js:64", "getAdminUserProfile()", "POST /admin/users/{id}/profile"),
        ("前端组件", "frontend/src/components/admin/ProfileReport.vue:33-45", "摘要 / 置信度 / 缓存状态", "报告头部渲染"),
        ("前端组件", "frontend/src/components/admin/ProfileAgentSection.vue:33-35", "专家卡片", "来源与置信度标签"),
        ("后端路由", "backend/app/api/v1/admin_profile.py:12-16", "Depends(require_admin)", "权限依赖"),
        ("后端路由", "backend/app/api/v1/admin_profile.py:20", "get_user_profile_endpoint()", "调用 orchestrator.analyze()"),
        ("后端服务", "backend/app/services/profile/service.py:159", "ProfileOrchestrator.analyze()", "画像总入口"),
        ("后端服务", "backend/app/services/profile/blackboard.py:169", "collect_blackboard()", "读取用户、词汇进度、错词、练习会话"),
        ("后端服务", "backend/app/services/profile/blackboard.py:130", "fingerprint()", "三类学习事实 SHA-256 指纹"),
        ("后端服务", "backend/app/services/profile/cache.py:37", "TTLProfileCache.get_or_create()", "命中直接返回，未命中执行工厂"),
        ("后端服务", "backend/app/services/profile/service.py:163", "run_experts()", "控制器求解 + 校验 + 组装"),
        ("后端服务", "backend/app/services/profile/controller.py:85", "Controller.solve()", "四轮调度知识源"),
        ("后端服务", "backend/app/services/profile/controller.py:45", "select_next_ks()", "匹配度 0.5 + 优先级 0.3 + 固定 0.2"),
        ("后端服务", "backend/app/services/profile/controller.py:72", "evaluate_solution()", "缺失源检查 + 平均置信度"),
        ("后端服务", "backend/app/services/profile/blackboard.py:94", "Blackboard.write() / write_artifact()", "写入专家条目、产物与轨迹"),
        ("后端服务", "backend/app/services/profile/agents.py:93", "BaseProfileExpert.analyze()", "先 heuristic，再尝试 LLM 精炼"),
        ("后端服务", "backend/app/services/profile/agents.py:144", "DataExpert（priority 40）", "正确率、趋势、词汇分布"),
        ("后端服务", "backend/app/services/profile/agents.py:273", "HabitExpert（priority 30）", "时长、活跃天数、连续、时段"),
        ("后端服务", "backend/app/services/profile/agents.py:447", "DiagnosisExpert（priority 20）", "错词长度/前缀/重复/未解决模式"),
        ("后端服务", "backend/app/services/profile/agents.py:622", "PlannerExpert（priority 10）", "依赖前三者，生成 7 日计划"),
        ("后端服务", "backend/app/services/profile/agents.py:114", "_refine()", "LLM 输出 JSON 解析与校验，失败返回 None"),
        ("后端服务", "backend/app/services/profile/service.py:61", "assemble_profile_report()", "汇总标签、雷达图、亮点与风险"),
        ("后端服务", "backend/app/services/profile/service.py:49", "_level()", "按覆盖率与总分定级"),
        ("数据模型", "backend/app/models/word_progress.py:20", "WordProgress", "画像词汇维度数据源"),
        ("数据模型", "backend/app/models/wrong_word.py:19", "WrongWord", "诊断维度数据源"),
        ("数据模型", "backend/app/models/practice_session.py:9", "PracticeSession", "习惯维度数据源"),
        ("配置", "backend/app/core/config.py:25", "PROFILE_CACHE_TTL_SECONDS", "默认 21600 秒"),
    ],
    branches=[
        ("缓存命中", "cache.py:45-46, 55-57", "跳过四位专家，直接返回缓存报告"),
        ("缓存键构成", "service.py:161；blackboard.py:130-140", "user_id + 学习数据指纹"),
        ("未配置 LLM", "service.py:190", "所有专家直接用 heuristic"),
        ("LLM 失败 / JSON 非法", "agents.py:136-141", "该专家回退 heuristic，source=heuristic"),
        ("规划依赖未满足", "agents.py:628", "Planner 最后执行，读取前三份产物"),
        ("置信度阈值", "controller.py:35, 82-83", "threshold=0.7，用于 solved 评估"),
        ("专家顺序校验", "service.py:169-170", "trace 顺序必须等于 data/habit/diagnosis/planner"),
        ("缓存 TTL 回填", "service.py:176-184", "model_copy 写回 hit / ttl_seconds / expires_at"),
    ],
)
