#!/usr/bin/env python3
"""名片处理脚本 - 被cc-connect调用"""
import sys
import os
import json
import logging
from typing import Callable, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')

from src.agent import ExhibitionAgent


def main_with_progress(
    image_path: str,
    text_info: str = "",
    on_progress: Optional[Callable[[str, str], None]] = None,
) -> dict | str:
    if not os.path.exists(image_path):
        return f"错误: 图片不存在 {image_path}"

    def progress(step: str, message: str):
        if on_progress:
            on_progress(step, message)
        print(message)

    try:
        progress("recognize", "📋 正在识别名片信息...")
        agent = ExhibitionAgent()
        result = agent.process_card(image_path, text_info, on_progress=on_progress)

        # 如果需要询问用户重复决策，返回特殊格式以便message_handler解析
        if result.get("action") == "ask_duplicate":
            dup_result = result.get("duplicate_info")
            card = result.get("card")
            pending_data = {
                "card": card,
                "dup_result": dup_result,
            }
            # 将待决策数据序列化到临时文件，供message_handler读取
            pending_file = f"/tmp/pending_dup_{id(card)}.json"
            import pickle
            with open(pending_file, "wb") as f:
                pickle.dump(pending_data, f)

            response = agent.format_response(result)
            # 返回包含 pending 文件路径的特殊格式
            return {"card": response, "__pending_dup_file__": pending_file}

        return agent.format_response(result)
    except Exception as e:
        return f"处理失败: {e}"


def main():
    if len(sys.argv) < 2:
        print("用法: python process_card.py <图片路径> [补充文本]")
        sys.exit(1)

    image_path = sys.argv[1]
    text_info = sys.argv[2] if len(sys.argv) > 2 else ""

    if not os.path.exists(image_path):
        print(f"错误: 图片不存在 {image_path}")
        sys.exit(1)

    agent = ExhibitionAgent()
    result = agent.process_card(image_path, text_info)
    response = agent.format_response(result)
    if isinstance(response, dict):
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(response)

if __name__ == "__main__":
    main()
