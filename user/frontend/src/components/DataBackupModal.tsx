import { useState } from "react";
import { Button, Message, Modal, Space, Typography, Upload } from "@arco-design/web-react";
import { IconDownload, IconImport } from "@arco-design/web-react/icon";
import type { BackupFile } from "@/types";
import { fetchBackup, importBackup } from "@/api/user";
import { toMessage } from "@/api/client";

const BACKUP_FORMAT = "english-practice-backup";
const BACKUP_VERSION = 1;

function buildFileName(): string {
  const stamp = new Date().toISOString().slice(0, 10);
  return `english-practice-backup-${stamp}.json`;
}

/** 学习数据备份：导出下载与导入合并 */
export default function DataBackupModal({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);

  const handleExport = async () => {
    setBusy(true);
    try {
      const payload = await fetchBackup();
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = buildFileName();
      link.click();
      URL.revokeObjectURL(url);
      Message.success({
        content: `已导出 ${payload.summary.words} 个词、${payload.summary.sessions} 次练习`,
      });
      onClose();
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async (file: File) => {
    let payload: BackupFile;
    try {
      payload = JSON.parse(await file.text()) as BackupFile;
    } catch {
      Message.error({ content: "文件不是有效的 JSON，请确认选的是备份文件" });
      return false;
    }

    if (payload.format !== BACKUP_FORMAT || payload.version !== BACKUP_VERSION) {
      Message.error({ content: "不是本平台当前版本的备份文件，请用最新版本重新导出" });
      return false;
    }

    const words = payload.word_records?.length ?? 0;
    const sessions = payload.sessions?.length ?? 0;
    const messages = payload.chat_messages?.length ?? 0;

    Modal.confirm({
      title: "导入学习数据",
      content: `备份包含 ${words} 个词、${sessions} 次练习、${messages} 条对话，将与当前进度合并，不会覆盖已有记录。确定继续吗？`,
      okText: "确认导入",
      cancelText: "取消",
      onOk: async () => {
        setBusy(true);
        try {
          const result = await importBackup(payload);
          const parts = [
            `新增 ${result.records_new} 个词`,
            `合并 ${result.records_merged} 个`,
          ];
          if (result.words_unmatched > 0) {
            // 词库被增删过时会有词对不上，必须让用户看见而不是静默吞掉
            parts.push(`${result.words_unmatched} 个词在当前词库中不存在，已跳过`);
          }
          Message.success({ content: `导入完成：${parts.join("，")}` });
          onClose();
        } catch (error) {
          Message.error({ content: toMessage(error) });
        } finally {
          setBusy(false);
        }
      },
    });
    // 阻止 Arco 自动上传，导入完全在前端读文件后走接口
    return false;
  };

  return (
    <Modal
      visible={visible}
      title="学习数据备份"
      style={{ width: 460 }}
      footer={null}
      onCancel={onClose}
    >
      <Typography.Paragraph type="secondary" style={{ fontSize: 13, marginBottom: 16 }}>
        练习进度、错题状态、连续打卡与对话历史都可以带走。文件不含账号与密码，
        因此换设备、换账号或误清浏览器数据后都能用它把进度找回来。
      </Typography.Paragraph>

      <div
        style={{
          padding: "12px 14px",
          borderRadius: "var(--border-radius-md)",
          background: "var(--bg-subtle)",
        }}
      >
        <Typography.Text style={{ fontSize: 13, fontWeight: 600 }}>导出</Typography.Text>
        <Typography.Text
          type="secondary"
          style={{ display: "block", fontSize: 12, margin: "4px 0 10px" }}
        >
          下载一份 JSON 备份文件，请自行妥善保管。
        </Typography.Text>
        <Button
          type="primary"
          className="focus-ring"
          loading={busy}
          icon={<IconDownload />}
          onClick={() => void handleExport()}
        >
          导出备份文件
        </Button>
      </div>

      <div
        style={{
          marginTop: 14,
          padding: "12px 14px",
          borderRadius: "var(--border-radius-md)",
          background: "var(--bg-subtle)",
        }}
      >
        <Typography.Text style={{ fontSize: 13, fontWeight: 600 }}>导入</Typography.Text>
        <Typography.Text
          type="secondary"
          style={{ display: "block", fontSize: 12, margin: "4px 0 10px" }}
        >
          选择备份文件后会先预览条目数并要求确认，导入是合并而非覆盖。
        </Typography.Text>
        <Upload
          accept=".json,application/json"
          showUploadList={false}
          beforeUpload={(file) => {
            void handleImport(file);
            return false;
          }}
        >
          <Button className="focus-ring" disabled={busy} icon={<IconImport />}>
            选择备份文件导入
          </Button>
        </Upload>
      </div>

      <Space size={8} style={{ marginTop: 14 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          同一份文件重复导入不会产生重复记录。
        </Typography.Text>
      </Space>
    </Modal>
  );
}
