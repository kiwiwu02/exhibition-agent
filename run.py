#!/usr/bin/env python3
"""启动飞书名片处理机器人服务"""
import logging
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


if __name__ == "__main__":
    uvicorn.run(
        "src.feishu_bot.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
