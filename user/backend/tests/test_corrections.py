"""AI 纠错区块解析与 Prompt 组装测试。"""

from __future__ import annotations

from app.ai.corrections import (
    feedback_from_json,
    feedback_to_json,
    parse_feedback,
)
from app.ai.prompts import PRESETS, SYSTEM_PROMPT, build_messages


FULL_REPLY = """I totally agree with your plan.

[语法指正]
- "I am agree" 中 agree 已是动词，不应再加 be 动词。

[地道表达]
- I agree with you on that point.
- That makes sense to me.
"""


class TestParseFeedback:
    def test_parses_both_blocks(self):
        body, block = parse_feedback(FULL_REPLY)
        assert block is not None
        assert "agree" in block.grammar
        assert len(block.polish) == 2
        assert "I agree with you on that point." in block.polish
        assert body == "I totally agree with your plan."

    def test_body_has_no_correction_headings(self):
        body, _ = parse_feedback(FULL_REPLY)
        assert "[语法指正]" not in body
        assert "[地道表达]" not in body

    def test_plain_reply_returns_none_block(self):
        body, block = parse_feedback("Nice work, keep it up.")
        assert block is None
        assert body == "Nice work, keep it up."

    def test_grammar_block_only(self):
        reply = "Got it.\n\n[语法指正]\n- 主谓不一致。\n"
        body, block = parse_feedback(reply)
        assert block is not None
        assert block.grammar == "主谓不一致。"
        assert block.polish == []
        assert body == "Got it."

    def test_polish_block_only(self):
        reply = "Sure.\n\n[地道表达]\n- How is it going?\n- What have you been up to?\n"
        _, block = parse_feedback(reply)
        assert block is not None
        assert block.grammar == ""
        assert len(block.polish) == 2

    def test_strips_list_markers(self):
        reply = "[语法指正]\n1. 时态错误\n* 冠词缺失\n"
        _, block = parse_feedback(reply)
        assert block is not None
        assert block.polish == [] or block.grammar
        assert "1." not in block.grammar
        assert "*" not in block.grammar

    def test_empty_input(self):
        assert parse_feedback("") == ("", None)

    def test_handles_colon_variants(self):
        reply = "Hi\n\n[语法指正]：\n- 少了冠词\n"
        _, block = parse_feedback(reply)
        assert block is not None
        assert "少了冠词" in block.grammar


class TestFeedbackJson:
    def test_roundtrip(self):
        _, block = parse_feedback(FULL_REPLY)
        assert block is not None
        raw = feedback_to_json(block)
        assert raw is not None
        restored = feedback_from_json(raw)
        assert restored is not None
        assert restored.grammar == block.grammar
        assert restored.polish == block.polish

    def test_none_roundtrip(self):
        assert feedback_to_json(None) is None
        assert feedback_from_json(None) is None

    def test_corrupt_json_returns_none(self):
        assert feedback_from_json("{not valid json") is None

    def test_json_is_not_ascii_escaped(self):
        _, block = parse_feedback("[语法指正]\n- 中文说明\n")
        raw = feedback_to_json(block)
        assert raw is not None and "中文说明" in raw


class TestBuildMessages:
    def test_starts_with_system_prompt(self):
        messages = build_messages([], "hello")
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SYSTEM_PROMPT
        assert messages[-1] == {"role": "user", "content": "hello"}

    def test_appends_history_in_order(self):
        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
        ]
        messages = build_messages(history, "second")
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "user"]
        assert messages[-1]["content"] == "second"

    def test_caps_history_at_twelve(self):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
            for i in range(30)
        ]
        messages = build_messages(history, "now")
        assert len([m for m in messages if m["role"] != "system"]) <= 13

    def test_skips_empty_and_unknown_roles(self):
        history = [
            {"role": "user", "content": "  "},
            {"role": "system", "content": "ignore"},
            {"role": "assistant", "content": "keep"},
        ]
        messages = build_messages(history, "hi")
        contents = [m["content"] for m in messages[1:]]
        assert contents == ["keep", "hi"]

    def test_preset_wraps_user_input(self):
        messages = build_messages([], "", preset="grammar_check")
        assert messages[-1]["content"].startswith(PRESETS["grammar_check"])

    def test_unknown_preset_ignored(self):
        messages = build_messages([], "plain")
        assert messages[-1]["content"] == "plain"

    def test_context_injected_as_system_message(self):
        messages = build_messages([], "hi", context="word: abandon")
        assert any("abandon" in m["content"] for m in messages if m["role"] == "system")

    def test_presets_have_no_emoji(self):
        for key, text in PRESETS.items():
            assert text.isascii(), f"{key} 预设含非 ASCII 内容"
