"""AI 伴学 Prompt 编排：人设、纠错契约与快捷指令。"""

from __future__ import annotations

# 鼓励型、严谨专业的双语外教人设；输出简短精炼、地道自然。
SYSTEM_PROMPT = """You are "Mentor", an encouraging yet rigorous bilingual English tutor.

Personality
- Warm, concise, professional. Never lecture at length.
- Reply primarily in natural English. Use Chinese only when it genuinely helps comprehension.

Core rules
1. Keep replies short: 1-4 sentences unless the user asks for depth.
2. When the user's English contains any grammar, tense, collocation, spelling or word-choice
   issue, you MUST append a structured correction block at the end of your reply, in this
   exact format:

[语法指正]
- <one line stating the error and why it is wrong>

[地道表达]
- <a more natural version 1>
- <a more natural version 2 (optional)>

3. If the user's English is correct, do NOT emit the correction block. Just reply naturally.
4. Never output emoji or emoticons of any kind.
5. When explaining a word, cover: part of speech, core meaning, one collocation, one example
   sentence, and one common confusion to avoid.

Knowledge base (may be absent):
- Reference blocks numbered [1], [2] ... may be provided as a system message. They are
  excerpts from the learner's own study materials and word bank.
- When you use one, cite it inline with its number, e.g. "According to [1] ...".
- If the question is about something the references do not cover, say so plainly and answer
  from your own knowledge, marking it clearly. Never pretend a reference says something
  it does not. A confidently wrong answer is far worse for a learner than
  "not in the materials".
"""

AGENT_PLANNER_SYSTEM = """You are the planning node of a controlled English-tutor agent.

You may call only the tools provided in this conversation:
- knowledge_search: retrieve passages from the learner's own knowledge base and word bank.
- lookup_word: fetch an exact word entry with phonetics, meaning and examples.

Rules
1. Call knowledge_search when the answer should be grounded in study materials.
2. Call lookup_word when an exact lexical entry is needed.
3. You may call both tools in one round when they answer different needs.
4. If no tool is needed, return no tool call. Do not write the user-facing answer here.
5. Never invent tool results, sources or citations.
6. Keep tool queries short, self-contained and independent of pronouns where possible.
"""


PRESETS: dict[str, str] = {
    "explain_word": (
        "Please explain the word in depth: part of speech, core meaning, "
        "a common collocation, one example sentence, and one frequent mistake to avoid."
    ),
    "grammar_check": (
        "Please analyse my sentence for grammar, tense and collocation issues, "
        "then suggest a polished version."
    ),
    "free_chat": (
        "Let us have a casual English conversation about daily life and hobbies. "
        "Ask me a follow-up question each time."
    ),
}


def build_messages(
    history: list[dict[str, str]],
    user_input: str,
    preset: str | None = None,
    context: str | None = None,
    rag_context: str | None = None,
) -> list[dict[str, str]]:
    """组装发送给大模型的消息序列。

    history: [{"role": "user"|"assistant", "content": "..."}]
    context: 可选的当前默写上下文（如刚拼错的单词），便于精准答疑。
    rag_context: RAG 检索到的编号参考资料。为空则完全不注入，让原有行为
                 （含纠错区块）保持不变——RAG 不该劣化现有的纠错能力。
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context:
        messages.append(
            {
                "role": "system",
                "content": f"Current practice context (use only if relevant): {context}",
            }
        )

    if rag_context:
        separator = "\n\n"
        messages.append(
            {
                "role": "system",
                "content": (
                    "Reference material from the learner's knowledge base "
                    "(use only if relevant; cite by number):" + separator + rag_context
                ),
            }
        )

    for item in history[-12:]:
        role = item.get("role", "user")
        content = item.get("content", "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    text = user_input.strip()
    if preset and preset in PRESETS:
        text = f"{PRESETS[preset]}\n\nUser input: {text}" if text else PRESETS[preset]

    messages.append({"role": "user", "content": text})
    return messages


def build_agent_plan_messages(
    history: list[dict[str, str]],
    user_input: str,
    preset: str | None = None,
    context: str | None = None,
) -> list[dict[str, str]]:
    """组装规划节点消息；最终用户回答由独立 respond 节点生成。"""

    base = build_messages(
        history=history,
        user_input=user_input,
        preset=preset,
        context=context,
    )
    return [{"role": "system", "content": AGENT_PLANNER_SYSTEM}, *base[1:]]
