import { useEffect, useState } from "react";
import { Card, Table, Typography } from "@arco-design/web-react";
import { fetchAuditLogs } from "@/api/audit";
import type { AuditLogOut } from "@/types";

/** 审计日志：只读，管理端不提供任何修改或删除入口 */
export default function AuditPage() {
  const [rows, setRows] = useState<AuditLogOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void fetchAuditLogs()
      .then((page) => {
        if (!cancelled) setRows(page.items);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card className="card" title="审计日志">
      <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
        管理端的每一次写操作都会留痕，只增不改不删。
      </Typography.Text>
      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        pagination={false}
        size="small"
        noDataElement="暂无审计记录"
        columns={[
          { title: "时间", dataIndex: "created_at", width: 180 },
          { title: "操作人", dataIndex: "actor_name", width: 140 },
          { title: "动作", dataIndex: "action", width: 160 },
          { title: "对象", dataIndex: "target_type", width: 110 },
          { title: "影响行数", dataIndex: "affected_rows", width: 100 },
        ]}
      />
    </Card>
  );
}
