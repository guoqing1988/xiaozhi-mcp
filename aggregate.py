from mcp.server.fastmcp import FastMCP

from tools.conversation_dingtalk import register_conversation_tools
from tools.email_qq import register_email_tools
from tools.system import register_system_tools
from tools.web_webpilot import register_web_tools
from tools.amap import register_amap_tools
# from tools.alarm import register_alarm_tools

# 创建MCP服务器
mcp = FastMCP("AggregateMCP")

# 注册所有工具
register_conversation_tools(mcp)
register_email_tools(mcp)
register_system_tools(mcp)
register_web_tools(mcp)
register_amap_tools(mcp)
# register_alarm_tools(mcp)
if __name__ == "__main__":
    mcp.run(transport="stdio")

