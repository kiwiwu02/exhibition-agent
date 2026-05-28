# src/feishu_doc.py
import httpx
import logging
from typing import Optional
from .config import config

logger = logging.getLogger(__name__)

class FeishuDocClient:
    """飞书文档客户端"""

    def __init__(self):
        self.app_id = config.feishu.app_id
        self.app_secret = config.feishu.app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self.tenant_token = None

    def _get_tenant_token(self) -> str:
        """获取tenant_access_token"""
        if self.tenant_token:
            return self.tenant_token

        try:
            response = httpx.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            self.tenant_token = data.get("tenant_access_token")
            return self.tenant_token
        except Exception as e:
            logger.error(f"获取tenant_token失败: {e}")
            raise

    def _get_headers(self) -> dict:
        """获取请求头"""
        token = self._get_tenant_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def create_document(self, title: str, content: str) -> Optional[str]:
        """创建飞书文档并返回文档链接"""
        try:
            # 创建文档
            response = httpx.post(
                f"{self.base_url}/docx/v1/documents",
                headers=self._get_headers(),
                json={"title": title}
            )
            response.raise_for_status()
            data = response.json()
            # 飞书API返回格式: data.document.document_id
            document_id = data.get("data", {}).get("document", {}).get("document_id")

            if not document_id:
                logger.error("创建文档失败：未获取到document_id")
                return None

            # 写入内容
            self._write_document_content(document_id, content)

            doc_url = f"https://feishu.cn/docx/{document_id}"
            logger.info(f"创建文档成功: {doc_url}")
            return doc_url

        except Exception as e:
            logger.error(f"创建文档失败: {e}")
            return None

    def _write_document_content(self, document_id: str, content: str):
        """写入文档内容 - 解析markdown并创建飞书原生块"""
        try:
            # 获取文档根block_id
            response = httpx.get(
                f"{self.base_url}/docx/v1/documents/{document_id}/blocks/{document_id}",
                headers=self._get_headers()
            )
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"获取文档block失败: {data.get('msg')}")
                return

            # 解析markdown并创建飞书块
            children = self._parse_markdown_to_blocks(content)

            if children:
                # 分批写入，每批最多50个块
                batch_size = 50
                for i in range(0, len(children), batch_size):
                    batch = children[i:i+batch_size]

                    # 清理每个块的内容
                    cleaned_batch = []
                    for block in batch:
                        cleaned_block = self._clean_block_content(block)
                        if cleaned_block:
                            cleaned_batch.append(cleaned_block)

                    if not cleaned_batch:
                        continue

                    # 批量写入 blocks
                    response = httpx.post(
                        f"{self.base_url}/docx/v1/documents/{document_id}/blocks/{document_id}/children",
                        headers=self._get_headers(),
                        json={"children": cleaned_batch, "index": i}
                    )
                    data = response.json()

                    if data.get("code") != 0:
                        logger.error(f"写入文档内容失败: {data.get('msg')}")
                        # 如果失败，尝试逐个写入
                        for block in cleaned_batch:
                            try:
                                response = httpx.post(
                                    f"{self.base_url}/docx/v1/documents/{document_id}/blocks/{document_id}/children",
                                    headers=self._get_headers(),
                                    json={"children": [block], "index": i}
                                )
                                data = response.json()
                                if data.get("code") != 0:
                                    logger.error(f"写入单个块失败: {data.get('msg')}")
                            except Exception as e:
                                logger.error(f"写入单个块异常: {e}")
                    else:
                        logger.info(f"文档内容写入成功，共{len(cleaned_batch)}个块")

        except Exception as e:
            logger.error(f"写入文档内容异常: {e}")

    def _clean_block_content(self, block: dict) -> dict:
        """清理块内容，移除可能导致验证失败的字符"""
        if "text" in block:
            elements = block["text"].get("elements", [])
            for element in elements:
                if "text_run" in element:
                    content = element["text_run"].get("content", "")
                    # 移除或替换可能导致问题的字符
                    content = content.replace('\x00', '')  # 移除空字符
                    content = content.replace('\r', '')  # 移除回车
                    content = content.replace('\t', ' ')  # 替换制表符为空格
                    # 限制单个文本块的长度
                    if len(content) > 2000:
                        content = content[:2000] + "..."
                    element["text_run"]["content"] = content
        return block

    def _parse_markdown_to_blocks(self, content: str) -> list:
        """将markdown解析为飞书文档块"""
        import re
        blocks = []
        lines = content.split('\n')
        consecutive_empty = 0

        for line in lines:
            raw_line = line
            line = line.strip()

            # 连续空行最多产生一个段落间距（不加块，靠飞书默认行距）
            if not line:
                consecutive_empty += 1
                continue
            consecutive_empty = 0

            # 标题块 - 使用飞书原生 heading 块
            if line.startswith('### '):
                blocks.append(self._create_heading_block(line[4:], level=3))
            elif line.startswith('## '):
                blocks.append(self._create_heading_block(line[3:], level=2))
            elif line.startswith('# '):
                blocks.append(self._create_heading_block(line[2:], level=1))
            # 无序列表项
            elif re.match(r'^[-*]\s+', line):
                text = re.sub(r'^[-*]\s+', '', line)
                blocks.append(self._create_bullet_block(text))
            # 有序列表项
            elif re.match(r'^\d+\.\s+', line):
                text = re.sub(r'^\d+\.\s+', '', line)
                blocks.append(self._create_ordered_block(text))
            # 分割线
            elif line == '---':
                blocks.append(self._create_divider_block())
            # 引用块（> 开头）
            elif line.startswith('> '):
                blocks.append(self._create_quote_block(line[2:]))
            # 普通文本
            else:
                blocks.append(self._create_text_block(line))

        return blocks

    def _parse_inline_format(self, text: str) -> list:
        """解析内联格式（**bold**、[text](url)）为飞书 text_run 元素列表"""
        import re
        elements = []
        # 匹配 **bold** 和 [text](url) 标记
        pattern = r'\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)]+)\)'
        last_end = 0

        for match in re.finditer(pattern, text):
            # 添加匹配前的普通文本
            if match.start() > last_end:
                plain = text[last_end:match.start()]
                if plain:
                    elements.append({"text_run": {"content": plain}})

            if match.group(1):
                # 粗体文本
                bold_text = match.group(1)
                elements.append({
                    "text_run": {
                        "content": bold_text,
                        "text_element_style": {"bold": True}
                    }
                })
            elif match.group(2) and match.group(3):
                # 链接文本
                link_text = match.group(2)
                link_url = match.group(3)
                elements.append({
                    "text_run": {
                        "content": link_text,
                        "text_element_style": {
                            "link": {"url": link_url}
                        }
                    }
                })
            last_end = match.end()

        # 添加剩余的普通文本
        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                elements.append({"text_run": {"content": remaining}})

        # 如果没有任何匹配，返回整段文本
        if not elements:
            elements.append({"text_run": {"content": text}})

        return elements

    def _create_heading_block(self, text: str, level: int = 2) -> dict:
        """创建飞书原生标题块"""
        # heading1=block_type 3, heading2=4, heading3=5
        block_type = level + 2
        heading_key = f"heading{level}"
        elements = self._parse_inline_format(text)
        return {
            "block_type": block_type,
            heading_key: {"elements": elements}
        }

    def _create_bullet_block(self, text: str) -> dict:
        """创建飞书原生无序列表块"""
        elements = self._parse_inline_format(text)
        return {
            "block_type": 12,
            "bullet": {"elements": elements}
        }

    def _create_ordered_block(self, text: str) -> dict:
        """创建飞书原生有序列表块"""
        elements = self._parse_inline_format(text)
        return {
            "block_type": 13,
            "ordered": {"elements": elements}
        }

    def _create_quote_block(self, text: str) -> dict:
        """创建飞书原生引用块"""
        elements = self._parse_inline_format(text)
        return {
            "block_type": 19,
            "quote": {"elements": elements}
        }

    def _create_divider_block(self) -> dict:
        """创建飞书原生分割线块"""
        return {
            "block_type": 22,
            "divider": {}
        }

    def _create_text_block(self, text: str) -> dict:
        """创建文本块，支持内联粗体"""
        elements = self._parse_inline_format(text)
        return {
            "block_type": 2,
            "text": {"elements": elements}
        }

    def generate_report(self, company_name: str, report_data: dict) -> Optional[str]:
        """生成调研报告文档"""
        title = f"{company_name} 公司调研报告"

        # 构建报告内容
        content = f"""# {company_name} 公司调研报告

## 基本信息
- 公司名称：{company_name}
- 国家/地区：{report_data.get('country', '未知')}
- 城市：{report_data.get('city', '未知')}

## 基本面与赛道定位
- 主营业务：{report_data.get('main_business', '待补充')}
- 行业地位：{report_data.get('industry_position', '待补充')}

## 规模与健康度
- 公司规模：{report_data.get('company_size', '待补充')}
- 信用评级：{report_data.get('credit_rating', '待评估')}

## 近期动态
{report_data.get('recent_news', '暂无近期动态')}

## 信息来源
{report_data.get('sources', '暂无信息来源')}

## 信息可信度
- 基本信息：★★★★☆
- 财务信息：★★☆☆☆
- 人员信息：★★★☆☆
"""

        return self.create_document(title, content)

    def generate_research_report(self, company_name: str, report_data: dict) -> Optional[str]:
        """生成调研报告文档（使用 ReportWriterAgent 生成的完整 markdown）"""
        title = f"{company_name} 公司调研报告"

        # 优先使用 ReportWriterAgent 生成的完整报告内容
        content = report_data.get('full_report_content', '')

        # fallback: 如果没有完整内容，使用各维度拼接
        if not content:
            content = self._build_fallback_content(company_name, report_data)

        return self.create_document(title, content)

    def _build_fallback_content(self, company_name: str, report_data: dict) -> str:
        """构建 fallback 报告内容（当 full_report_content 为空时）"""
        sources = report_data.get('sources', [])
        numbered_sources = "\n".join(sources[:15])

        sections = []
        sections.append(f"# {company_name} 公司调研报告\n")

        dims = [
            ("1. 基础信息", "basic_info"),
            ("2. 工商法律信息", "business_track"),
            ("3. 财务信用信息", "financial_health"),
            ("4. 组织架构", "org_structure"),
            ("5. 动态新闻", "news_reputation"),
            ("6. 供应链与口碑", "supply_chain"),
            ("7. 销售机会评估", "sales_opportunity"),
        ]
        for title, key in dims:
            val = report_data.get(key, '暂无信息')
            sections.append(f"## {title}\n{val}\n")

        if numbered_sources:
            sections.append(f"## 参考来源\n{numbered_sources}\n")

        sections.append("---\n*本报告由AI自动生成，信息仅供参考，请以实际调查为准。*")
        return "\n".join(sections)
