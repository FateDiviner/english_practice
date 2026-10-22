# 数据字典

约定：所有表含 id BIGINT PK AUTO_INCREMENT、created_at DATETIME、updated_at DATETIME。
字符集 utf8mb4，排序 utf8mb4_unicode_ci。时间统一 UTC 存储。

## users
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | 主键 |
| username | VARCHAR(50) | 否 | - | 唯一，登录名 |
| email | VARCHAR(100) | 否 | - | 唯一 |
| password_hash | VARCHAR(255) | 否 | - | bcrypt 哈希，禁止明文 |
| role | ENUM('user','admin') | 否 | 'user' | 角色 |
| status | ENUM('active','disabled') | 否 | 'active' | 禁用后不可登录 |
| created_at | DATETIME | 否 | now | |
| updated_at | DATETIME | 否 | now | |

索引：UNIQUE(username)、UNIQUE(email)

## wordbooks
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| name | VARCHAR(100) | 否 | - | 词书名 |
| description | TEXT | 是 | NULL | 简介 |
| level | VARCHAR(20) | 是 | NULL | CET4/IELTS 等 |
| status | ENUM('draft','published','archived') | 否 | 'draft' | 仅 published 用户可见 |
| created_by | BIGINT | 否 | - | FK users.id |
| created_at / updated_at | DATETIME | 否 | now | |

索引：idx_wordbooks_status、idx_wordbooks_created_by

## words
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| wordbook_id | BIGINT | 否 | - | FK wordbooks.id |
| spelling | VARCHAR(100) | 否 | - | 英文单词，同词书内唯一 |
| phonetic_uk | VARCHAR(100) | 是 | NULL | 英音音标 |
| phonetic_us | VARCHAR(100) | 是 | NULL | 美音音标 |
| meaning_cn | VARCHAR(255) | 是 | NULL | 中文释义，多义用 ; 分隔 |
| part_of_speech | VARCHAR(20) | 是 | NULL | n./v./adj. |
| example_en | TEXT | 是 | NULL | 英文例句 |
| example_cn | TEXT | 是 | NULL | 例句中文 |
| audio_url | VARCHAR(255) | 是 | NULL | 音频地址，可空 |
| sort_order | INT | 否 | 0 | 排序 |
| created_at / updated_at | DATETIME | 否 | now | |

索引：UNIQUE(wordbook_id, spelling)、idx_words_wordbook_id

## user_wordbooks
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| user_id | BIGINT | 否 | - | FK users.id |
| wordbook_id | BIGINT | 否 | - | FK wordbooks.id |
| status | ENUM('learning','completed') | 否 | 'learning' | |
| started_at | DATETIME | 是 | NULL | |
| last_practiced_at | DATETIME | 是 | NULL | |

索引：UNIQUE(user_id, wordbook_id)

## word_progress
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| user_id | BIGINT | 否 | - | FK users.id |
| word_id | BIGINT | 否 | - | FK words.id |
| mastery_level | TINYINT | 否 | 0 | 0新词 1学习中 2已掌握 |
| correct_count | INT | 否 | 0 | |
| wrong_count | INT | 否 | 0 | |
| consecutive_correct | INT | 否 | 0 | 连续正确数，用于升级判定 |
| last_result | ENUM('correct','wrong') | 是 | NULL | |
| last_practiced_at | DATETIME | 是 | NULL | |

索引：UNIQUE(user_id, word_id)、idx_word_progress_user

## practice_sessions
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| user_id | BIGINT | 否 | - | FK users.id |
| wordbook_id | BIGINT | 是 | NULL | 错词重练时为空 |
| mode | ENUM('normal','wrong_only') | 否 | 'normal' | |
| total_count | INT | 否 | 0 | |
| correct_count | INT | 否 | 0 | |
| status | ENUM('ongoing','finished') | 否 | 'ongoing' | |
| started_at | DATETIME | 否 | now | |
| finished_at | DATETIME | 是 | NULL | |

索引：idx_sessions_user、idx_sessions_started_at

## practice_records
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| session_id | BIGINT | 否 | - | FK practice_sessions.id |
| word_id | BIGINT | 否 | - | FK words.id |
| user_input | VARCHAR(100) | 否 | - | 用户输入原文 |
| is_correct | BOOLEAN | 否 | - | |
| used_hint | BOOLEAN | 否 | false | |
| answered_at | DATETIME | 否 | now | |

索引：idx_records_session、idx_records_word
约束：同一 session 同一 word 只能有一条有效记录（重复提交不重复计分）

## wrong_words
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| user_id | BIGINT | 否 | - | FK users.id |
| word_id | BIGINT | 否 | - | FK words.id |
| wrong_count | INT | 否 | 0 | 累加 |
| last_wrong_at | DATETIME | 是 | NULL | |
| resolved | BOOLEAN | 否 | false | 重练达标置 true |
| resolved_at | DATETIME | 是 | NULL | |

索引：UNIQUE(user_id, word_id)、idx_wrong_words_user_resolved

## import_jobs
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| wordbook_id | BIGINT | 否 | - | FK wordbooks.id |
| admin_id | BIGINT | 否 | - | FK users.id |
| file_name | VARCHAR(255) | 否 | - | |
| total_rows | INT | 否 | 0 | |
| success_rows | INT | 否 | 0 | |
| failed_rows | INT | 否 | 0 | |
| status | ENUM('pending','processing','done','failed') | 否 | 'pending' | |
| error_detail | JSON | 是 | NULL | [{row, content, reason}] |

索引：idx_import_jobs_wordbook、idx_import_jobs_status

## ai_conversations（预留）
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| user_id | BIGINT | 否 | - | FK users.id |
| title | VARCHAR(100) | 是 | NULL | |
| scene | VARCHAR(50) | 是 | NULL | 情景标签 |
| created_at / updated_at | DATETIME | 否 | now | |

## ai_messages（预留）
| 字段 | 类型 | 可空 | 默认 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | 自增 | |
| conversation_id | BIGINT | 否 | - | FK ai_conversations.id |
| role | ENUM('user','assistant') | 否 | - | |
| content | TEXT | 否 | - | |
| created_at | DATETIME | 否 | now | |

索引：idx_ai_messages_conversation
