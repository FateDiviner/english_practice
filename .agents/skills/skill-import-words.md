# Skill：管理员导入词书单词

## 触发场景
上传 Excel/CSV 批量导入单词。

## 步骤
1. 接收文件，创建 import_jobs 记录（status=pending）
2. 解析文件头，做列映射（spelling 必填；phonetic_uk/us、meaning_cn、part_of_speech、example 可选）
3. 逐行校验：空单词、重复（同词书内）、超长字段、音标格式
4. 合法行事务批量入库；失败行写入 error_detail（行号 + 原因）
5. 更新 import_jobs：total/success/failed、status=done
6. 前端 ImportWizard 展示预览、错误行、结果页

## 大文件
超过 500 行走后台任务，接口立即返回 import_job_id，前端轮询状态。

## 红线
- 不得阻塞请求
- 不得因单行错误回滚全部合法行
- 重复单词不得静默覆盖
