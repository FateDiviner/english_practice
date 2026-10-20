import type { ReactNode } from "react";
import { Space } from "@arco-design/web-react";

interface RecordCardProps {
  /** 主标题，通常是用户名、词书名或文件名 */
  title: ReactNode;
  /** 标题右侧的状态标记 */
  tags?: ReactNode;
  /** 次要字段，成对的「标签 + 值」，窄屏两列排布 */
  fields?: { label: string; value: ReactNode }[];
  /** 操作按钮行，会自动换行，不会挤成一团 */
  actions?: ReactNode;
  testId?: string;
}

/**
 * 窄屏列表项。表格在手机上横向滚动不可用，改成一行一张卡：
 * 主信息在标题行，次要字段成对排列，操作单独一行。
 */
export default function RecordCard({
  title,
  tags,
  fields = [],
  actions,
  testId,
}: RecordCardProps) {
  return (
    <article className="record-card" data-testid={testId}>
      <div className="record-card__head">
        <strong style={{ minWidth: 0, wordBreak: "break-word" }}>{title}</strong>
        {tags && <Space wrap size={4}>{tags}</Space>}
      </div>

      {fields.length > 0 && (
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
            gap: "var(--space-2)",
            margin: 0,
          }}
        >
          {fields.map((field) => (
            <div key={field.label} className="record-card__row">
              <dt className="record-card__label">{field.label}</dt>
              <dd style={{ margin: 0, color: "var(--text-1)" }} className="numeric">
                {field.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {actions && <div className="record-card__actions">{actions}</div>}
    </article>
  );
}
