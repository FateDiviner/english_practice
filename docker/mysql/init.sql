-- 首次启动时由 MySQL 官方镜像自动执行。
-- 只建库和字符集，不建表：表结构由后端启动时的 init_db() 用 ORM 统一创建，
-- 在这里手写 DDL 会和模型产生两份真相，改字段要同步两处。
CREATE DATABASE IF NOT EXISTS english_practice
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

-- 时区统一 UTC：后端的连续打卡、练习日期都按 UTC 自然日算，
-- 容器时区和宿主机不一致时不能依赖系统默认值
SET GLOBAL time_zone = '+00:00';
SET SESSION time_zone = '+00:00';
