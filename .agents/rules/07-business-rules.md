# 核心业务规则

## 默写判分
1. 输入 normalize：trim + 转小写
2. 默认严格比对；宽松模式忽略连字符/空格差异
3. 英美拼写差异用映射表判定（color/colour 均正确）
4. 判分在 services/grading.py，路由只调用
5. 仅答错时返回正确拼写 + 例句
6. 重复提交同一题不重复计分

## 掌握度
- 连续正确 2 次 → mastery_level = 2（已掌握），阈值提成常量
- 答错 → mastery_level = 1（学习中），写入/累加 wrong_words
- 错词本重练达标 → resolved = true

## 导入
- 校验列映射：spelling 必填，phonetic/meaning 建议必填
- 逐行校验：空单词、重复、超长
- 事务批量入库；失败行写入 import_jobs.error_detail（JSON）
- 大文件走后台任务，不阻塞请求
- 单行失败不回滚合法行
