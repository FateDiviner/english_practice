"""把两条 AI 链路的执行过程一步步打印出来。

这个脚本是"学习用的望远镜"，不是业务代码：
- 只调用项目里已有的类，不复制逻辑
- 不连数据库、不连真实模型、不写任何数据
- 每一步都打印，你按顺序往下看就能看到跨文件调用

运行方式（在 backend 目录下）：
    .venv/Scripts/python.exe -m scripts.trace_flow
"""

import asyncio
from datetime import datetime, timedelta

from app.services.agent.client import MockLLMClient
from app.services.agent.heuristics import keyword_classify
from app.services.agent.intent import Intent
from app.services.agent.router import IntentRouter
from app.services.agent.service import AgentService
from app.services.agent.skills import SkillContext, build_default_registry
from app.services.profile.agents import build_default_agents
from app.services.profile.blackboard import (
    Blackboard,
    PracticeSessionSnapshot,
    WordProgressSnapshot,
    WrongWordSnapshot,
)
from app.services.profile.controller import BlackboardController
from app.services.profile.service import assemble_profile_report


def line(title):
    """打印一条分隔线，让输出分段好读。"""
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)


# ---------------------------------------------------------------------------
# 第一部分：学生端对话链路（Router + Skill）
# ---------------------------------------------------------------------------


async def trace_agent():
    """照着 api/v1/agent.py -> service.py -> router.py -> skills -> client.py 的顺序走一遍。"""

    # 这三行是"组装零件"，对应 service.py 里的 get_agent_service()。
    # 区别是这里固定用 MockLLMClient，保证不联网、结果稳定。
    llm = MockLLMClient()
    skills = build_default_registry()
    router = IntentRouter(llm, skills)
    service = AgentService(router=router, skills=skills, llm=llm)

    message = "apple 什么意思"

    line("第一部分：学生端对话链路")
    print("模拟用户输入：", message)

    # --- 第 1 步：关键词分类 ---
    line("【第 1 步】关键词分类  (app/services/agent/heuristics.py 第 54 行)")
    fast_intent = keyword_classify(message)
    print("分类结果：", fast_intent)
    print("是否 GENERAL：", fast_intent == Intent.GENERAL)
    print()
    print("说明：如果不是 GENERAL，Router 会直接采纳这个结果，完全跳过模型。")

    # --- 第 2 步：路由决策 ---
    line("【第 2 步】路由决策  (app/services/agent/router.py 第 144 行 decide)")
    decision = await router.decide(message)
    print("最终意图 intent：", decision.intent)
    print("对应技能 skill：", decision.skill)
    print("置信度 confidence：", decision.confidence)
    print("是否用了兜底 fallback_used：", decision.fallback_used)
    print("路由理由 reason：", decision.reason)
    print()
    print("候选排行（从高到低）：")
    for item in decision.candidates:
        print("   意图=%-15s 技能=%-15s 分数=%s" % (item.intent.value, item.skill, item.score))

    # --- 第 3 步：构造消息 ---
    line("【第 3 步】构造发给模型的消息  (app/services/agent/skills/base.py 第 26 行)")
    skill = skills.get(decision.intent)
    messages = skill.build_messages(message, SkillContext())
    for index, item in enumerate(messages, start=1):
        preview = item.content.replace("\n", " ")[:150]
        print("消息 %d  角色=%s" % (index, item.role))
        print("        内容=%s" % preview)

    # --- 第 4 步：模型流式输出 ---
    line("【第 4 步】模型流式输出  (app/services/agent/client.py 第 58 行)")
    chunks = []
    async for chunk in llm.stream(messages):
        chunks.append(chunk)
    print("一共收到 %d 个片段" % len(chunks))
    print("前 12 个片段：", chunks[:12])
    print()
    print("拼接后的完整回复：")
    print("".join(chunks))

    # --- 第 5 步：SSE 事件 ---
    line("【第 5 步】SSE 事件序列  (app/services/agent/service.py 第 56 行)")
    delta_count = 0
    async for event, payload in service.stream_events(message):
        if event == "delta":
            delta_count += 1
            continue
        print("事件名：", event)
        for key, value in payload.items():
            if key == "candidates":
                print("    candidates = %d 项" % len(value))
            else:
                print("    %s = %s" % (key, value))
    print("    （中间省略 delta 事件 %d 个）" % delta_count)

    # --- 额外：几个不同输入的路由结果对比 ---
    line("【补充】不同输入会被分到哪个技能")
    examples = [
        "帮我翻译这句话：I love learning English.",
        "过去完成时的用法是什么",
        "我想练口语，点餐场景",
        "今天天气怎么样",
    ]
    for text in examples:
        result = await router.decide(text)
        print("%-34s -> 关键词=%-15s 路由=%-15s 分数=%s"
              % (text, keyword_classify(text).value, result.skill, result.confidence))


# ---------------------------------------------------------------------------
# 第二部分：管理端学情画像链路（Blackboard 四个专家）
# ---------------------------------------------------------------------------


def build_demo_blackboard():
    """手工造一个用户的学习数据，代替数据库查询（对应 collect_blackboard）。"""

    now = datetime(2026, 10, 28, 20, 0, 0)

    # 每个参数依次是：
    # 词ID、拼写、掌握等级(0新词/1学习中/2已掌握)、答对次数、答错次数、上次结果、上次练习时间
    word_progress = [
        WordProgressSnapshot(1, "apple", 2, 12, 1, "correct", now - timedelta(days=1)),
        WordProgressSnapshot(2, "banana", 1, 6, 3, "wrong", now - timedelta(days=2)),
        WordProgressSnapshot(3, "necessary", 0, 2, 5, "wrong", now - timedelta(days=2)),
        WordProgressSnapshot(4, "environment", 0, 1, 4, "wrong", now - timedelta(days=4)),
        WordProgressSnapshot(5, "beautiful", 1, 5, 2, "correct", now - timedelta(days=3)),
        WordProgressSnapshot(6, "knowledge", 0, 0, 3, "wrong", now - timedelta(days=5)),
    ]

    # 词ID、拼写、答错次数、是否已解决、最后一次答错时间
    wrong_words = [
        WrongWordSnapshot(3, "necessary", 5, False, now - timedelta(days=2)),
        WrongWordSnapshot(4, "environment", 4, False, now - timedelta(days=4)),
        WrongWordSnapshot(6, "knowledge", 3, True, now - timedelta(days=5)),
        WrongWordSnapshot(2, "banana", 2, False, now - timedelta(days=2)),
    ]

    # 会话ID、开始时间、结束时间、总题数、答对数、状态
    practice_sessions = [
        PracticeSessionSnapshot(1, now - timedelta(days=1, hours=3),
                                now - timedelta(days=1, hours=2, minutes=40), 20, 16, "completed"),
        PracticeSessionSnapshot(2, now - timedelta(days=2, hours=4),
                                now - timedelta(days=2, hours=3, minutes=35), 15, 9, "completed"),
        PracticeSessionSnapshot(3, now - timedelta(days=4, hours=2),
                                now - timedelta(days=4, hours=1, minutes=50), 25, 17, "completed"),
        PracticeSessionSnapshot(4, now - timedelta(days=9, hours=5),
                                now - timedelta(days=9, hours=4, minutes=30), 10, 8, "completed"),
    ]

    return Blackboard(
        user_id=1,
        username="demo",
        user_created_at=now - timedelta(days=30),
        word_progress=word_progress,
        wrong_words=wrong_words,
        practice_sessions=practice_sessions,
    )


async def trace_profile():
    """照着 service.py -> controller.py -> agents.py 的顺序走一遍。"""

    blackboard = build_demo_blackboard()

    # 传 None 表示"不接大模型"，四个专家只做确定性统计。
    # 真实环境是 build_default_agents(get_llm_client())。
    agents = build_default_agents(None)
    controller = BlackboardController()

    line("第二部分：管理端学情画像链路")
    print("说明：这里传入 llm=None，所以只看得到 Python 算出来的草稿结果。")

    # --- 第 1 步：黑板上的原始数据 ---
    line("【第 1 步】黑板装载原始数据  (blackboard.py 第 169 行 collect_blackboard)")
    print("学习记录：%d 条" % len(blackboard.word_progress))
    print("错词：%d 条" % len(blackboard.wrong_words))
    print("练习会话：%d 条" % len(blackboard.practice_sessions))
    print("数据指纹：%s..." % blackboard.fingerprint()[:16])

    # --- 第 2 步：Controller 调度 ---
    line("【第 2 步】Controller 调度四个专家  (controller.py 第 85 行 solve)")
    result = await controller.solve(blackboard, agents)
    print("实际执行顺序：", blackboard.trace)
    print("预期顺序：     ", ["data", "habit", "diagnosis", "planner"])
    print("迭代次数：", result.iterations)
    print("是否全部完成：", result.solved)
    print("平均置信度：", result.confidence)
    print("缺失的专家：", result.missing_sources)
    print()
    print("说明：顺序不是写死的，是 select_next_ks 按优先级算出来的。")

    # --- 第 3 步：每个专家的产出 ---
    line("【第 3 步】四个专家各自的结论  (agents.py)")
    for key in blackboard.trace:
        output = blackboard.artifacts[key]
        print()
        print("[%s]  来源=%s  置信度=%s" % (key, output.source, output.confidence))
        print("    摘要：%s" % output.summary)
        print("    标签：%s" % output.tags)
        if getattr(output, "metrics", None):
            pairs = [(item.label, item.score) for item in output.metrics]
            print("    指标：%s" % pairs)
        if getattr(output, "highlights", None):
            print("    亮点：%s" % output.highlights)
        if getattr(output, "risks", None):
            print("    风险：%s" % output.risks)

    # --- 第 4 步：组装最终报告 ---
    line("【第 4 步】组装最终报告  (profile/service.py 第 61 行)")
    report = assemble_profile_report(blackboard)
    print("标题：", report.summary.headline)
    print("等级：", report.summary.level)
    print("置信度：", report.summary.confidence)
    print("标签：", report.summary.tags)
    print("亮点：", report.summary.highlights)
    print("风险：", report.summary.risks)
    print("专家顺序：", report.agent_sequence)


def main():
    asyncio.run(trace_agent())
    asyncio.run(trace_profile())
    print()
    print("全部结束。")


if __name__ == "__main__":
    main()
