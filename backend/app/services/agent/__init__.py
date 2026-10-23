"""智能伴学辅导体 Agent 包：Router + Skill 路由分发架构。"""

from app.services.agent.intent import Intent
from app.services.agent.service import AgentService, get_agent_service

__all__ = ["AgentService", "Intent", "get_agent_service"]
