import logging
import requests
import os
import random
from mcp.server.fastmcp import FastMCP
from markitdown import MarkItDown

logger = logging.getLogger('news_tools')

WEB_WEBPILOT_APIKEY = os.environ.get("WEB_WEBPILOT_APIKEY")
API_URL = "https://gpts.webpilot.ai/api/read"

# 新闻来源字典，包含名称和对应的API ID
NEWS_SOURCES = {
    "thepaper": "澎湃新闻",
    "baidu": "百度热搜",
    "cls-depth": "财联社",
}

# 动态生成新闻源描述
def generate_news_sources_description():
    sources_desc = []
    for source_id, source_name in NEWS_SOURCES.items():
        sources_desc.append(f"{source_name}({source_id})")
    return "、".join(sources_desc)

def register_news_tools(mcp: FastMCP):
    @mcp.tool()
    def fetch_news_from_api(source: str = "thepaper") -> dict:
        """获取今天的新闻，可以指定新闻源，如果没有指定，默认从澎湃新闻获取。
        
        Args:
            source (str): 新闻源名称，可选值为：{generate_news_sources_description()}
            
        Returns:
            dict: 包含成功状态、新闻列表
        """
        try:
            api_url = f"https://newsnow.busiyi.world/api/s?id={source}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()

            data = response.json()

            if "items" in data:
                return {
                    "success": True,
                    "result": data["items"]
                }
            else:
                logger.error(f"获取新闻API响应格式错误: {data}")
                return {
                    "success": False,
                    "error": "获取新闻API响应格式错误"
                }

        except Exception as e:
            logger.error(f"获取新闻API失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    @mcp.tool()
    def fetch_news_detail(url: str) -> dict:
        """获取URL对应的新闻详情页内容并使用MarkItDown清理HTML
        Args:
            url (str): 新闻详情页URL
            
        Returns:
            dict: 包含成功状态、清理后的新闻内容
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            # 使用MarkItDown清理HTML内容
            md = MarkItDown(enable_plugins=False)
            result = md.convert(response)

            # 获取清理后的文本内容
            clean_text = result.text_content

            # 如果清理后的内容为空，返回提示信息
            if not clean_text or len(clean_text.strip()) == 0:
                logger.warning(f"清理后的新闻内容为空: {url}")
                return {"success": False, "error": "无法解析新闻详情内容，可能是网站结构特殊或内容受限。"}
            logger.info(f"获取新闻详情成功: {url}")
            logger.info(f"新闻详情: {clean_text}")
            return {
                "success": True,
                "result": clean_text
            }
        except Exception as e:
            logger.error(f"获取新闻详情失败: {e}")
            return {"success": False, "error": str(e)}
        
    @mcp.tool()
    def get_news_from_newsnow(source: str = "thepaper", detail: bool = False, lang: str = "zh_CN"
    ) -> dict:
        """获取新闻并随机选择一条进行播报，如果没有指定，默认从澎湃新闻获取。用户可以要求获取详细内容，此时会获取新闻的详细内容。

        Args:
            source (str): 新闻源名称，可选值为：{generate_news_sources_description()}
            detail (bool): 是否获取新闻详情
            lang (str): 语言，可选值为：zh_CN、en_US
        
        Returns:
            dict: 包含成功状态、新闻报告
        """
        try:
            # 否则，获取新闻列表并随机选择一条
            # 验证新闻源是否有效，如果无效则使用默认源
            if source not in NEWS_SOURCES:
                logger.warning(f"无效的新闻源: {source}，使用默认源thepaper")
                source = "thepaper"

            source_name = NEWS_SOURCES.get(source, "澎湃新闻")
            logger.info(f"获取新闻: 新闻源={source}({source_name})")

            # 获取新闻列表
            news_items = fetch_news_from_api( source)
            if not news_items:
                return {
                    "success": False,
                    "error": f"抱歉，未能从{source_name}获取到新闻信息，请稍后再试或尝试其他新闻源。"
                }

            # 随机选择一条新闻
            selected_news = random.choice(news_items)

            # 构建新闻报告
            news_report = (
                f"根据下列数据，用{lang}回应用户的新闻查询请求：\n\n"
                f"新闻标题: {selected_news['title']}\n"
                f"新闻链接: {selected_news['url']}\n"
                # f"新闻来源: {source_name}\n"
                f"(请以自然、流畅的方式向用户播报这条新闻标题，"
                f"提示用户可以要求获取详细内容，此时调用获取新闻的详细内容工具（fetch_news_detail）获取新闻的详细内容。)"
            )

            return {
                "success": True,
                "result": news_report
            }

        except Exception as e:
            logger.error(f"获取新闻出错: {e}")
            return {
                "success": False,
                "error": f"抱歉，获取新闻时发生错误，请稍后再试。{e}"
            }