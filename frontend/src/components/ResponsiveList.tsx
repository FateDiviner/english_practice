import type { ReactNode } from "react";
import { Empty, Pagination, Table } from "@arco-design/web-react";
import type { TableProps } from "@arco-design/web-react";

import { useIsMobile } from "@/hooks/useMediaQuery";

interface ResponsiveListProps<T> extends Omit<TableProps<T>, "data" | "columns" | "pagination"> {
  data: T[];
  /** 桌面端表格列 */
  columns: TableProps<T>["columns"];
  /** 窄屏卡片渲染。表格在手机上横向滚动不可用，一行一条记录更好扫 */
  renderCard: (row: T, index: number) => ReactNode;
  pagination?: TableProps<T>["pagination"];
}

/**
 * 管理端列表：宽屏用表格，窄屏用卡片。
 *
 * 8 列表格在手机上只能横向滚动，扫一眼要拖好几次——所以窄屏改成一行一张卡，
 * 主信息在标题行，次要字段成对排列，操作按钮单独一行且可换行。
 */
export default function ResponsiveList<T extends object>({
  data,
  columns,
  renderCard,
  pagination,
  noDataElement,
  loading,
  rowKey,
  ...rest
}: ResponsiveListProps<T>) {
  const isMobile = useIsMobile();

  if (isMobile) {
    if (loading) {
      return <Empty description="加载中…" />;
    }
    if (data.length === 0) {
      return <Empty description={String(noDataElement ?? "暂无数据")} />;
    }
    return (
      <div className="record-list" data-testid="record-cards">
        {data.map((row, index) => (
          <div key={String(rowKey ? (row as Record<string, unknown>)[rowKey as string] : index)}>
            {renderCard(row, index)}
          </div>
        ))}
        {pagination && typeof pagination === "object" && (
          <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-2) 0" }}>
            {/* 窄屏用 simple 分页：省掉页码按钮，只留上下页，拇指操作更稳 */}
            <Pagination
              {...(pagination as Record<string, unknown>)}
              simple
              size="small"
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <Table<T>
      rowKey={rowKey}
      data={data}
      columns={columns}
      loading={loading}
      pagination={pagination}
      noDataElement={noDataElement}
      {...rest}
    />
  );
}
