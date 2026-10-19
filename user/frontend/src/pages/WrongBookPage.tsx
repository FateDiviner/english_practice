import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Empty,
  Message,
  Space,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "@arco-design/web-react";
import {
  IconBulb,
  IconMessage,
  IconPlayArrow,
  IconRefresh,
} from "@arco-design/web-react/icon";
import type { WrongBookItem } from "@/types";
import { fetchWrongBook } from "@/api/practice";
import { usePracticeStore } from "@/stores/practice";
import { useSpeech } from "@/hooks/useSpeech";
import { toMessage } from "@/api/client";
import { writeChatContext } from "@/utils/chatContext";

/** 错题本（生词本）：查看并一键开启错题专项重练 */
export default function WrongBookPage() {
  const navigate = useNavigate();
  const startPractice = usePracticeStore((state) => state.start);
  const { speak, supported } = useSpeech();

  const [items, setItems] = useState<WrongBookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchWrongBook();
      setItems(data.items);
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** 带着这个词与例句跳到伴学页，省去手动描述 */
  const askAbout = (item: WrongBookItem) => {
    writeChatContext({
      word: item.word,
      translation: item.translation,
      phonetic: item.phonetic,
      example: item.example_en,
      source: "wrong_book",
    });
    navigate("/chat");
  };

  // 下架的词不再出题：重练必须落在第一个仍可用的词书上，
  // 否则开局会被后端以 409 拒绝
  const trainable = items.filter((item) => !item.archived);
  const startTarget = trainable[0] ?? null;

  const handleStart = async () => {
    if (!startTarget) return;
    setStarting(true);
    try {
      await startPractice(startTarget.wordbook_id, "wrong_book");
      navigate("/practice");
    } catch (error) {
      Message.error({ content: toMessage(error) });
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="anim-fade-up" style={{ maxWidth: 760, margin: "0 auto" }}>
      <Space
        size={16}
        style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }}
        wrap
      >
        <div>
          <Typography.Title heading={4} style={{ margin: 0 }}>
            我的错题本
          </Typography.Title>
          <Typography.Text type="secondary">
            拼写错误的单词会自动沉淀到这里，订正达标后才会移出
          </Typography.Text>
        </div>
        <Space size={8}>
          <Button
            className="focus-ring"
            icon={<IconRefresh />}
            loading={loading}
            onClick={() => void load()}
          >
            刷新
          </Button>
          <Button
            type="primary"
            className="focus-ring"
            loading={starting}
            disabled={!startTarget}
            icon={<IconPlayArrow />}
            onClick={() => void handleStart()}
          >
            错题专项重练（{trainable.length}）
          </Button>
        </Space>
      </Space>

      <Spin loading={loading} style={{ width: "100%" }}>
        {items.length === 0 && !loading ? (
          <Card className="card">
            <Empty description="错题本还是空的，先去默写几组吧" />
            <div style={{ textAlign: "center", marginTop: 12 }}>
              <Button
                className="focus-ring"
                icon={<IconBulb />}
                onClick={() => navigate("/")}
              >
                前往词书中心
              </Button>
            </div>
          </Card>
        ) : (
          <div style={{ display: "grid", gap: 12 }}>
            {items.map((item) => (
              <Card key={item.word_id} className="card" style={{ padding: "16px 18px" }}>
                <Space
                  size={12}
                  style={{ width: "100%", justifyContent: "space-between" }}
                  align="center"
                  wrap
                >
                  <Space size={12} align="baseline" wrap>
                    <span className="word-display" style={{ fontSize: 26 }}>
                      {item.word}
                    </span>
                    <span className="phonetic-display">{item.phonetic}</span>
                    <Tag color="red" size="small">
                      错 {item.wrong_count} 次
                    </Tag>
                    {item.archived && (
                      <Tag color="gray" size="small">
                        [已下架]
                      </Tag>
                    )}
                  </Space>

                  <Space size={8}>
                    <Button
                      size="small"
                      className="focus-ring"
                      icon={<IconPlayArrow />}
                      onClick={() => {
                        if (supported) void speak(item.word);
                        else Message.info({ content: "当前浏览器不支持语音合成" });
                      }}
                    >
                      发音
                    </Button>
                    <Tooltip content="带上这个词与例句，让 AI 讲解">
                      <Button
                        size="small"
                        className="focus-ring"
                        icon={<IconMessage />}
                        onClick={() => askAbout(item)}
                      >
                        AI 讲解
                      </Button>
                    </Tooltip>
                  </Space>
                </Space>

                <Typography.Text style={{ display: "block", marginTop: 6 }}>
                  {item.translation}
                </Typography.Text>

                <div
                  style={{
                    marginTop: 8,
                    padding: "8px 10px",
                    borderRadius: "var(--border-radius-md)",
                    background: "var(--bg-subtle)",
                  }}
                >
                  <Typography.Text
                    style={{ fontFamily: "var(--font-ipa)", fontSize: 14 }}
                  >
                    {item.example_en}
                  </Typography.Text>
                  <Typography.Text
                    type="secondary"
                    style={{ display: "block", fontSize: 13, marginTop: 2 }}
                  >
                    {item.example_cn}
                  </Typography.Text>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Spin>
    </div>
  );
}
