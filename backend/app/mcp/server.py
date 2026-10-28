from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.mcp.auth import McpAuthMiddleware
from app.mcp.tools_import import register_import_tools
from app.mcp.tools_read import register_read_tools
from app.mcp.tools_write import register_write_tools

INSTRUCTIONS = """这是英语默写平台的管理端 MCP 服务。
只读工具可以直接查询数据；所有增删改只能通过 propose_* 工具提交申请，
必须由管理员在管理端「MCP 审批」页面确认后才会执行。
可以先用 get_change_request 或 list_change_requests 跟踪申请状态。"""


def create_mcp_server() -> MCPServer:
    server = MCPServer(
        name="english-practice-admin",
        instructions=INSTRUCTIONS,
        version="0.1.0",
    )
    register_read_tools(server)
    register_write_tools(server)
    register_import_tools(server)
    return server


def build_mcp_app(server: MCPServer) -> McpAuthMiddleware:
    app = server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return McpAuthMiddleware(app)
