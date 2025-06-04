import schedule
import time
from datetime import datetime
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from openai import OpenAI
from typing import Dict, Any

# API配置
BASE_URL = "https://api.moonshot.cn/v1"

# 配置日志
def setup_logger():
    # 创建logs目录
    os.makedirs('logs', exist_ok=True)
    
    # 配置日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置文件处理器（每个文件最大10MB，保留5个备份文件）
    file_handler = RotatingFileHandler(
        'logs/news_collector.log',
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 获取logger实例
    logger = logging.getLogger('NewsCollector')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 创建logger实例
logger = setup_logger()

def load_api_key():
    try:
        with open('API_KEY', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.error("找不到API_KEY文件，请确保API_KEY文件存在于当前目录")
        raise Exception("找不到API_KEY文件，请确保API_KEY文件存在于当前目录")
    except Exception as e:
        logger.error(f"读取API_KEY时发生错误: {str(e)}")
        raise Exception(f"读取API_KEY时发生错误: {str(e)}")

def search_impl(arguments: Dict[str, Any]) -> Any:
    """
    搜索工具的实现，直接返回参数给 Moonshot AI 处理
    """
    return arguments

def get_news_with_search(client: OpenAI, date_str: str) -> str:
    """
    使用联网搜索功能获取新闻
    """
    messages = [
        {
            "role": "system",
            "content": "你是一个专业的科技新闻编辑，善于搜索和整理最新的科技新闻。请确保新闻的真实性和时效性，并以markdown格式输出内容。"
        },
        {
            "role": "user",
            "content": f"请搜索并汇总{date_str}的科技技术以及计算机编程相关的热点新闻。要求：\n1. 使用搜索工具查询最新新闻，必须是当天发布的新闻\n2. 新闻内容详细清晰，并给出新闻引用链接\n3. 按照重要性排序，最好能够汇总10个左右的热点新闻\n4. 使用markdown格式输出，包含标题、简介和来源链接"
        }
    ]

    while True:
        completion = client.chat.completions.create(
            model="moonshot-v1-128k",
            messages=messages,
            temperature=0.3,
            tools=[
                {
                    "type": "builtin_function",
                    "function": {
                        "name": "$web_search",
                    },
                }
            ]
        )
        
        choice = completion.choices[0]
        
        if choice.finish_reason == "tool_calls":
            messages.append(choice.message)
            
            for tool_call in choice.message.tool_calls:
                tool_call_arguments = json.loads(tool_call.function.arguments)
                if tool_call.function.name == "$web_search":
                    tool_result = search_impl(tool_call_arguments)
                else:
                    tool_result = f"Error: unable to find tool by name '{tool_call.function.name}'"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": json.dumps(tool_result)
                })
        else:
            return choice.message.content

def get_news():
    # 获取当前日期和时间
    today = datetime.now()
    date_str = today.strftime('%Y年%m月%d日')
    time_str = today.strftime('%H:%M:%S')
    
    logger.info(f"当前时间: {date_str} {time_str}")
    logger.info(f"开始获取{date_str}的新闻")
    
    try:
        # 初始化OpenAI客户端
        client = OpenAI(
            api_key=load_api_key(),
            base_url=BASE_URL
        )
        
        logger.info("开始搜索新闻")
        news_content = get_news_with_search(client, date_str)
        
        # 创建保存路径
        save_dir = f"../content/posts/{today.year}/{today.month:02d}"
        os.makedirs(save_dir, exist_ok=True)
        
        # 创建markdown文件内容
        markdown_content = f"""---
title: {date_str}科技新闻
date: {today.strftime('%Y-%m-%d')}
categories: ['科技']
---

{news_content}
"""
        
        # 保存文件
        file_path = f"{save_dir}/{today.strftime('%Y-%m-%d')}-news.md"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
            
        logger.info(f"新闻已成功保存到: {file_path}")
        
    except Exception as e:
        logger.error(f"获取新闻时发生错误: {str(e)}", exc_info=True)

def main():
    logger.info("新闻收集程序启动")
    # 设置每天23:50运行
    schedule.every().day.at("23:50").do(get_news)
    
    # 程序启动时先执行一次
    logger.info("执行首次新闻收集")
    get_news()
    
    # 保持程序运行
    logger.info("进入定时任务循环")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 