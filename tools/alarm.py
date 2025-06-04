"""
FastMCP 闹钟工具服务
提供设置、查看和删除闹钟的功能，使用 stdio 模式
符合 MCP 协议标准，支持通知客户端
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alarm-server")

@dataclass
class Alarm:
    """闹钟数据类"""
    id: str
    time: datetime
    message: str
    created_at: datetime
    active: bool = True

class AlarmManager:
    """闹钟管理器"""
    
    def __init__(self, mcp_app):
        self.alarms: Dict[str, Alarm] = {}
        self.alarm_tasks: Dict[str, asyncio.Task] = {}
        self.mcp_app = mcp_app
        
    async def create_alarm(self, alarm_id: str, alarm_time: datetime, message: str = "闹钟时间到！") -> bool:
        """创建新闹钟"""
        if alarm_time <= datetime.now():
            return False
            
        # 如果闹钟已存在，先删除
        if alarm_id in self.alarms:
            await self.delete_alarm(alarm_id)
            
        alarm = Alarm(
            id=alarm_id,
            time=alarm_time,
            message=message,
            created_at=datetime.now()
        )
        
        self.alarms[alarm_id] = alarm
        
        # 创建异步任务等待闹钟时间
        task = asyncio.create_task(self._wait_for_alarm(alarm_id))
        self.alarm_tasks[alarm_id] = task
        
        logger.info(f"创建闹钟 {alarm_id}: {alarm_time}")
        return True
    
    async def _wait_for_alarm(self, alarm_id: str):
        """等待闹钟时间到达"""
        try:
            alarm = self.alarms.get(alarm_id)
            if not alarm:
                return
                
            # 计算等待时间
            wait_seconds = (alarm.time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
                
            # 检查闹钟是否仍然活跃
            if alarm_id in self.alarms and self.alarms[alarm_id].active:
                await self._trigger_alarm(alarm_id)
                
        except asyncio.CancelledError:
            logger.info(f"闹钟 {alarm_id} 被取消")
    
    async def _trigger_alarm(self, alarm_id: str):
        """触发闹钟并通知客户端"""
        alarm = self.alarms.get(alarm_id)
        if not alarm:
            return
            
        logger.info(f"🔔 闹钟 {alarm_id} 触发: {alarm.message}")
        
        # 发送通知到 MCP 客户端
        try:
            # 构造符合 MCP 协议的通知消息
            notification_content = {
                "type": "alarm_triggered",
                "alarm_id": alarm_id,
                "message": alarm.message,
                "triggered_at": datetime.now().isoformat(),
                "original_time": alarm.time.isoformat()
            }
            
            # 如果有活跃的会话，发送通知
            if hasattr(self.mcp_app, '_session') and self.mcp_app._session:
                await self.mcp_app._session.send_notification(
                    method="notifications/alarm_triggered",
                    params=notification_content
                )
            
        except Exception as e:
            logger.error(f"发送闹钟通知失败: {e}")
        
        # 闹钟触发后自动删除
        await self.delete_alarm(alarm_id)
    
    async def delete_alarm(self, alarm_id: str) -> bool:
        """删除闹钟"""
        if alarm_id not in self.alarms:
            return False
            
        # 取消异步任务
        if alarm_id in self.alarm_tasks:
            self.alarm_tasks[alarm_id].cancel()
            del self.alarm_tasks[alarm_id]
            
        # 删除闹钟
        del self.alarms[alarm_id]
        logger.info(f"删除闹钟 {alarm_id}")
        return True
    
    def list_alarms(self) -> List[Dict[str, Any]]:
        """列出所有闹钟"""
        return [
            {
                "id": alarm.id,
                "time": alarm.time.isoformat(),
                "message": alarm.message,
                "created_at": alarm.created_at.isoformat(),
                "active": alarm.active,
                "remaining_seconds": max(0, (alarm.time - datetime.now()).total_seconds())
            }
            for alarm in self.alarms.values()
        ]
    
    def get_alarm(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """获取指定闹钟"""
        alarm = self.alarms.get(alarm_id)
        if not alarm:
            return None
            
        return {
            "id": alarm.id,
            "time": alarm.time.isoformat(),
            "message": alarm.message,
            "created_at": alarm.created_at.isoformat(),
            "active": alarm.active,
            "remaining_seconds": max(0, (alarm.time - datetime.now()).total_seconds())
        }

# 创建 FastMCP 应用
# mcp = FastMCP("Alarm Server")
def register_amap_tools(mcp: FastMCP):
    alarm_manager = AlarmManager(mcp)

    @mcp.tool()
    async def set_alarm(alarm_id: str, time_str: str, message: str = "闹钟时间到！") -> List[TextContent]:
        """
        设置闹钟
        
        Args:
            alarm_id: 闹钟的唯一标识符
            time_str: 闹钟时间，格式：YYYY-MM-DD HH:MM:SS 或 HH:MM:SS（今天）
            message: 闹钟消息（可选）
        
        Returns:
            符合MCP协议的TextContent列表
        """
        try:
            # 解析时间字符串
            if len(time_str.split()) == 1:  # 只有时间，没有日期
                today = datetime.now().date()
                time_part = datetime.strptime(time_str, "%H:%M:%S").time()
                alarm_time = datetime.combine(today, time_part)
                
                # 如果时间已过，设置为明天
                if alarm_time <= datetime.now():
                    alarm_time += timedelta(days=1)
            else:
                alarm_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            
            success = await alarm_manager.create_alarm(alarm_id, alarm_time, message)
            
            if success:
                result_text = f"✅ 闹钟设置成功\n\n" \
                            f"闹钟ID: {alarm_id}\n" \
                            f"触发时间: {alarm_time.strftime('%Y-%m-%d %H:%M:%S')}\n" \
                            f"消息: {message}\n\n" \
                            f"剩余时间: {int((alarm_time - datetime.now()).total_seconds())} 秒"
            else:
                result_text = "❌ 设置失败：时间不能早于当前时间"
                
        except ValueError as e:
            result_text = f"❌ 时间格式错误：{str(e)}\n\n请使用格式：\n- HH:MM:SS（今天）\n- YYYY-MM-DD HH:MM:SS"
        except Exception as e:
            result_text = f"❌ 设置闹钟失败：{str(e)}"
        
        return [TextContent(type="text", text=result_text)]

    @mcp.tool()
    async def list_alarms() -> List[TextContent]:
        """
        列出所有闹钟
        
        Returns:
            符合MCP协议的TextContent列表
        """
        try:
            alarms = alarm_manager.list_alarms()
            
            if not alarms:
                result_text = "📝 当前没有设置任何闹钟"
            else:
                result_text = f"📋 闹钟列表（共 {len(alarms)} 个）\n\n"
                
                for i, alarm in enumerate(alarms, 1):
                    remaining = int(alarm['remaining_seconds'])
                    hours, remainder = divmod(remaining, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    time_left = ""
                    if hours > 0:
                        time_left += f"{hours}小时"
                    if minutes > 0:
                        time_left += f"{minutes}分钟"
                    if seconds > 0 or (hours == 0 and minutes == 0):
                        time_left += f"{seconds}秒"
                    
                    result_text += f"{i}. 【{alarm['id']}】\n" \
                                f"   时间: {datetime.fromisoformat(alarm['time']).strftime('%Y-%m-%d %H:%M:%S')}\n" \
                                f"   消息: {alarm['message']}\n" \
                                f"   剩余: {time_left}\n\n"
                                
        except Exception as e:
            result_text = f"❌ 获取闹钟列表失败：{str(e)}"
        
        return [TextContent(type="text", text=result_text)]

    @mcp.tool()
    async def get_alarm(alarm_id: str) -> List[TextContent]:
        """
        获取指定闹钟信息
        
        Args:
            alarm_id: 闹钟的唯一标识符
        
        Returns:
            符合MCP协议的TextContent列表
        """
        try:
            alarm = alarm_manager.get_alarm(alarm_id)
            
            if alarm:
                remaining = int(alarm['remaining_seconds'])
                hours, remainder = divmod(remaining, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                time_left = ""
                if hours > 0:
                    time_left += f"{hours}小时"
                if minutes > 0:
                    time_left += f"{minutes}分钟"
                if seconds > 0 or (hours == 0 and minutes == 0):
                    time_left += f"{seconds}秒"
                
                result_text = f"🔍 闹钟详情\n\n" \
                            f"ID: {alarm['id']}\n" \
                            f"触发时间: {datetime.fromisoformat(alarm['time']).strftime('%Y-%m-%d %H:%M:%S')}\n" \
                            f"消息: {alarm['message']}\n" \
                            f"创建时间: {datetime.fromisoformat(alarm['created_at']).strftime('%Y-%m-%d %H:%M:%S')}\n" \
                            f"状态: {'激活' if alarm['active'] else '已停用'}\n" \
                            f"剩余时间: {time_left}"
            else:
                result_text = f"❌ 未找到闹钟 '{alarm_id}'"
                
        except Exception as e:
            result_text = f"❌ 获取闹钟失败：{str(e)}"
        
        return [TextContent(type="text", text=result_text)]

    @mcp.tool()
    async def delete_alarm(alarm_id: str) -> List[TextContent]:
        """
        删除指定闹钟
        
        Args:
            alarm_id: 要删除的闹钟标识符
        
        Returns:
            符合MCP协议的TextContent列表
        """
        try:
            success = await alarm_manager.delete_alarm(alarm_id)
            
            if success:
                result_text = f"✅ 闹钟 '{alarm_id}' 已成功删除"
            else:
                result_text = f"❌ 未找到闹钟 '{alarm_id}'"
                
        except Exception as e:
            result_text = f"❌ 删除闹钟失败：{str(e)}"
        
        return [TextContent(type="text", text=result_text)]

    @mcp.tool()
    async def snooze_alarm(alarm_id: str, minutes: int = 5) -> List[TextContent]:
        """
        闹钟贪睡功能
        
        Args:
            alarm_id: 闹钟标识符
            minutes: 贪睡分钟数（默认5分钟）
        
        Returns:
            符合MCP协议的TextContent列表
        """
        try:
            alarm = alarm_manager.get_alarm(alarm_id)
            if not alarm:
                result_text = f"❌ 未找到闹钟 '{alarm_id}'"
            else:
                # 删除原闹钟
                await alarm_manager.delete_alarm(alarm_id)
                
                # 创建新的贪睡闹钟
                new_time = datetime.now() + timedelta(minutes=minutes)
                new_alarm_id = f"{alarm_id}_snooze"
                success = await alarm_manager.create_alarm(
                    new_alarm_id,
                    new_time,
                    f"贪睡闹钟: {alarm['message']}"
                )
                
                if success:
                    result_text = f"😴 闹钟已贪睡 {minutes} 分钟\n\n" \
                                f"新闹钟ID: {new_alarm_id}\n" \
                                f"新触发时间: {new_time.strftime('%Y-%m-%d %H:%M:%S')}"
                else:
                    result_text = "❌ 贪睡设置失败"
                    
        except Exception as e:
            result_text = f"❌ 贪睡操作失败：{str(e)}"
        
        return [TextContent(type="text", text=result_text)]

    # 添加资源提供器，用于提供闹钟状态信息
    @mcp.resource("alarm://status")
    async def get_alarm_status() -> str:
        """提供当前闹钟状态的资源"""
        alarms = alarm_manager.list_alarms()
        status = {
            "total_alarms": len(alarms),
            "active_alarms": len([a for a in alarms if a['active']]),
            "alarms": alarms,
            "server_time": datetime.now().isoformat()
        }
        return json.dumps(status, ensure_ascii=False, indent=2)

# if __name__ == "__main__":
#     # 运行 FastMCP 服务器，使用 stdio 模式
#     mcp.run()