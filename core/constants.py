"""全项目共用的状态常量。

词书与词条共用同一套状态值，避免各处写死字符串导致口径漂移。
"""

# 正常可用
STATUS_ACTIVE = "active"
# 已下架：对用户不可见，但历史数据（练习记录、错题、备份）一律保留
STATUS_ARCHIVED = "archived"

# 账号状态：被封禁的账号无法登录，已有令牌在下次请求时立即失效
USER_STATUS_ACTIVE = "active"
USER_STATUS_BANNED = "banned"

# 下架词在错题本等历史视图里的中文标记
ARCHIVED_LABEL = "[已下架]"
