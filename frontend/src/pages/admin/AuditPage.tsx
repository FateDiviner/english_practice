import { useCallback, useEffect, useState } from "react";
import { Button, Space, Table, Tag, Typography } from "@arco-design/web-react";

import { fetchAuditLogs } from "@/api/admin";
import { toMessage } from "@/api/client";
import { Message } from "@arco-design/web-react";
import type { AuditLogEntry } from "@/types";

const PAGE_SIZE = 50;

const ACTION_LABEL: Record<string, string> = {
  "user.create": "新建用户",
  "user.ban": "封禁用户",
  "user.unban": "启用用户",
  "user.role_change": "调整角色",
  "user.delete": "删除用户",
  "wordbook.create": "新建词书",
  "wordbook.update": "编辑词书",
  "wordbook.archive": "下架词书",
  "wordbook.restore": "上架词书",
  "wordbook.import": "批量导入",
  "word.create": "新增词条",
  "word.update": "编辑词条",
  "word.archive": "下架词条",
  "word.restore": "上架词条",
  "word.purge": "物理删除词条",
  "word.relation_create": "新增词条关系",
  "word.relation_update": "编辑词条关系",
  "word.relation_delete": "删除词条关系",
  "kb.upload": "上传知识库",
  "kb.delete": "删除知识库文档",
};

export default function AuditPage() {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetchAuditLogs(PAGE_SIZE, (page - 1) * PAGE_SIZE);
      setItems(result.items);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>审计日志</h2>
          <p style={{ margin: "4px 0 0", color: "var(--text-2)", fontSize: 13 }}>
            管理端的每一次写操作都会留痕，只增不改不删。操作人被删除后日志仍可读
            ——外键置空，姓名走快照。
          </p>
        </div>
        <Button onClick={() => void load()}>刷新</Button>
      </header>

      <Table
        rowKey="id"
        loading={loading}
        data={items}
        noDataElement="暂无审计记录"
        pagination={{
          total: items.length >= PAGE_SIZE ? page * PAGE_SIZE + 1 : items.length,
          pageSize: PAGE_SIZE,
          current: page,
          onChange: (next) => setPage(next),
        }}
        columns={[
          {
            title: "时间",
            dataIndex: "created_at",
            width: 170,
            render: (value: string) => value.slice(0, 19).replace("T", " "),
          },
          {
            title: "操作人",
            dataIndex: "actor_name",
            width: 140,
            render: (value: string, row: AuditLogEntry) => (
              <Space size={4}>
                <span>{value}</span>
                {row.actor_id === null && (
                  <Tag size="small" color="gray">
                    [已删除]
                  </Tag>
                )}
              </Space>
            ),
          },
          {
            title: "动作",
            dataIndex: "action",
            width: 150,
            render: (value: string) => <Tag>{ACTION_LABEL[value] ?? value}</Tag>,
          },
          {
            title: "对象",
            width: 160,
            render: (_, row: AuditLogEntry) =>
              row.target_type ? (
                <span>
                  {row.target_type}
                  {row.target_id ? ` #${row.target_id}` : ""}
                </span>
              ) : (
                "-"
              ),
          },
          { title: "影响行数", dataIndex: "affected_rows", width: 100 },
          {
            title: "详情",
            dataIndex: "detail",
            render: (value: string | null) =>
              value ? (
                <Typography.Text style={{ fontSize: 12 }} ellipsis={{ showTooltip: true }}>
                  {value}
                </Typography.Text>
              ) : (
                "-"
              ),
          },
        ]}
      />
    </section>
  );
}
