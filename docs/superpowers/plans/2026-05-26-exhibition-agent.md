# 海外展会线索录入Agent 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个通过飞书群消息接收名片图片，自动识别并录入CRM，同时自动进行公司背调的Agent系统。

**Architecture:** cc-connect桥接飞书和Claude Code，Claude Code作为AI Agent处理名片识别（MiMo-V2.5）、重复检测、CRM读写（Bitable）、背调API调用和报告生成。

**Tech Stack:** cc-connect, Claude Code, MiMo-V2.5, Tavily Search API, 飞书Bitable API, 飞书文档API

---

## Task 1: 验证cc-connect飞书消息收发

**Files:**
- `~/.cc-connect/config.toml`

- [ ] **Step 1: 确认cc-connect配置正确**

```toml
language = "zh"

[log]
level = "info"

[[projects]]
name = "exhibition-agent"

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/Users/kiwimacbook/Desktop/中联创新"
mode = "default"

[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_aa9ecb3fb4b89cb1"
app_secret = "KgT0hRFGus0yIB2xsWCm6cyKnzcT6fih"
```

- [ ] **Step 2: 启动cc-connect**

```bash
unset CLAUDECODE && cc-connect
```

- [ ] **Step 3: 在飞书中测试消息收发**

在飞书中私聊机器人或在群中@机器人，发送"你好"，验证是否收到回复。

- [ ] **Step 4: Commit**

```bash
# 配置已验证，无需代码提交
echo "cc-connect飞书连接验证完成"
```

---

## Task 2: 创建项目基础结构

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `src/models.py`

- [ ] **Step 1: 创建项目目录结构**

```bash
mkdir -p src tests
touch src/__init__.py
```

- [ ] **Step 2: 创建配置文件**

```python
# src/config.py
import os
from dataclasses import dataclass

@dataclass
class MiMoConfig:
    api_base: str = os.getenv("MIMO_API_BASE", "https://api.mimo.ai/v1")
    model: str = os.getenv("MIMO_MODEL", "mimo-v2.5")
    api_key: str = os.getenv("MIMO_API_KEY", "")
    max_tokens: int = 2000
    temperature: float = 0.1

@dataclass
class TavilyConfig:
    api_key: str = os.getenv("TAVILY_API_KEY", "")

@dataclass
class FeishuConfig:
    app_id: str = os.getenv("FEISHU_APP_ID", "cli_aa9ecb3fb4b89cb1")
    app_secret: str = os.getenv("FEISHU_APP_SECRET", "KgT0hRFGus0yIB2xsWCm6cyKnzcT6fih")
    bitable_app_token: str = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
    bitable_table_id: str = os.getenv("FEISHU_BITABLE_TABLE_ID", "")

@dataclass
class Config:
    mimo: MiMoConfig = None
    tavily: TavilyConfig = None
    feishu: FeishuConfig = None
    
    def __post_init__(self):
        self.mimo = self.mimo or MiMoConfig()
        self.tavily = self.tavily or TavilyConfig()
        self.feishu = self.feishu or FeishuConfig()

config = Config()
```

- [ ] **Step 3: 创建数据模型**

```python
# src/models.py
from dataclasses import dataclass, field
from typing import Optional, Dict
from datetime import datetime

@dataclass
class BusinessCard:
    company_name: str = ""
    company_name_en: str = ""
    company_alias: str = ""
    contact_name: str = ""
    position: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    website: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    additional_info: str = ""
    confidence: Dict[str, str] = field(default_factory=dict)

@dataclass
class CRMSession:
    record_id: str = ""
    company_name: str = ""
    contact_name: str = ""
    email: str = ""
    phone: str = ""
    is_duplicate: bool = False
    duplicate_record_id: str = ""
```

- [ ] **Step 4: Commit**

```bash
git add src/__init__.py src/config.py src/models.py
git commit -m "feat: 创建项目基础结构和数据模型"
```

---

## Task 3: 实现MiMo-V2.5名片识别

**Files:**
- Create: `src/card_recognizer.py`
- Create: `tests/test_card_recognizer.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_card_recognizer.py
import pytest
from src.card_recognizer import recognize_business_card

def test_recognize_business_card():
    # 这个测试会失败，因为函数还未实现
    result = recognize_business_card("test_image.jpg")
    assert "company_name" in result
    assert "contact_name" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/kiwimacbook/Desktop/中联创新
python -m pytest tests/test_card_recognizer.py -v
```

预期：FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现名片识别模块**

```python
# src/card_recognizer.py
import base64
import json
import re
from openai import OpenAI
from .config import config
from .models import BusinessCard

RECOGNITION_PROMPT = """
请识别这张名片图片，提取以下字段（JSON格式）：

{
  "company_name": "公司名称",
  "company_name_en": "公司英文名称（如有）",
  "company_alias": "公司别名/缩写（如有）",
  "contact_name": "联系人姓名",
  "position": "职位",
  "email": "邮箱",
  "phone": "电话",
  "address": "完整地址",
  "website": "网站",
  "country": "国家/地区",
  "region": "区域（北美/欧洲/亚太/中东/南美）",
  "city": "城市",
  "additional_info": "其他可见信息",
  "confidence": {
    "company_name": "high/medium/low",
    "contact_name": "high/medium/low",
    "email": "high/medium/low",
    "phone": "high/medium/low"
  }
}

注意事项：
1. 如果字段不清晰或无法识别，置信度设为low
2. 多语言名片请同时提取中英文
3. 电话请保留国际区号
4. 地址请尽可能完整
5. 根据公司名称和地址推断区域（region）
"""

def recognize_business_card(image_path: str) -> BusinessCard:
    """使用MiMo-V2.5识别名片图片"""
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    
    client = OpenAI(
        api_key=config.mimo.api_key,
        base_url=config.mimo.api_base
    )
    
    response = client.chat.completions.create(
        model=config.mimo.model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                    },
                    {"type": "text", "text": RECOGNITION_PROMPT}
                ]
            }
        ],
        max_tokens=config.mimo.max_tokens,
        temperature=config.mimo.temperature
    )
    
    return parse_recognition_result(response.choices[0].message.content)

def parse_recognition_result(result: str) -> BusinessCard:
    """解析AI识别结果"""
    try:
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            data = json.loads(json_match.group())
            return BusinessCard(
                company_name=data.get("company_name", ""),
                company_name_en=data.get("company_name_en", ""),
                company_alias=data.get("company_alias", ""),
                contact_name=data.get("contact_name", ""),
                position=data.get("position", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                address=data.get("address", ""),
                website=data.get("website", ""),
                country=data.get("country", ""),
                region=data.get("region", ""),
                city=data.get("city", ""),
                additional_info=data.get("additional_info", ""),
                confidence=data.get("confidence", {})
            )
    except (json.JSONDecodeError, AttributeError):
        pass
    return BusinessCard()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_card_recognizer.py -v
```

预期：PASS

- [ ] **Step 5: Commit**

```bash
git add src/card_recognizer.py tests/test_card_recognizer.py
git commit -m "feat: 实现MiMo-V2.5名片识别模块"
```

---

## Task 4: 实现重复检测逻辑

**Files:**
- Create: `src/duplicate_checker.py`
- Create: `tests/test_duplicate_checker.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_duplicate_checker.py
import pytest
from src.duplicate_checker import check_duplicate
from src.models import BusinessCard, CRMSession

def test_check_duplicate_no_match():
    new_card = BusinessCard(
        company_name="New Corp",
        email="new@example.com"
    )
    existing_records = [
        CRMSession(company_name="Old Corp", email="old@example.com")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result["is_duplicate"] == False

def test_check_duplicate_email_match():
    new_card = BusinessCard(
        company_name="Tech Corp",
        email="john@techcorp.com"
    )
    existing_records = [
        CRMSession(record_id="123", company_name="Tech Corp", email="john@techcorp.com")
    ]
    result = check_duplicate(new_card, existing_records)
    assert result["is_duplicate"] == True
    assert result["confidence"] == "high"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_duplicate_checker.py -v
```

预期：FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现重复检测模块**

```python
# src/duplicate_checker.py
from difflib import SequenceMatcher
from .models import BusinessCard, CRMSession

def check_duplicate(new_card: BusinessCard, existing_records: list) -> dict:
    """检查新名片是否与现有记录重复"""
    
    # 规则1：邮箱完全匹配（高置信度）
    if new_card.email:
        for record in existing_records:
            if record.email and record.email.lower() == new_card.email.lower():
                return {
                    "is_duplicate": True,
                    "confidence": "high",
                    "matched_record_id": record.record_id,
                    "reason": "邮箱完全匹配"
                }
    
    # 规则2：公司名 + 联系人姓名匹配（中置信度）
    if new_card.company_name and new_card.contact_name:
        for record in existing_records:
            if (record.company_name and record.contact_name and
                similar_ratio(new_card.company_name, record.company_name) > 0.8 and
                similar_ratio(new_card.contact_name, record.contact_name) > 0.8):
                return {
                    "is_duplicate": True,
                    "confidence": "medium",
                    "matched_record_id": record.record_id,
                    "reason": "公司名+联系人匹配"
                }
    
    # 规则3：公司名 + 电话匹配（中置信度）
    if new_card.company_name and new_card.phone:
        for record in existing_records:
            if (record.company_name and record.phone and
                similar_ratio(new_card.company_name, record.company_name) > 0.8 and
                normalize_phone(new_card.phone) == normalize_phone(record.phone)):
                return {
                    "is_duplicate": True,
                    "confidence": "medium",
                    "matched_record_id": record.record_id,
                    "reason": "公司名+电话匹配"
                }
    
    return {"is_duplicate": False}

def similar_ratio(a: str, b: str) -> float:
    """计算字符串相似度"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def normalize_phone(phone: str) -> str:
    """标准化电话号码"""
    import re
    return re.sub(r'[^0-9+]', '', phone)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_duplicate_checker.py -v
```

预期：PASS

- [ ] **Step 5: Commit**

```bash
git add src/duplicate_checker.py tests/test_duplicate_checker.py
git commit -m "feat: 实现重复检测逻辑"
```

---

## Task 5: 实现Tavily背调搜索

**Files:**
- Create: `src/background_checker.py`
- Create: `tests/test_background_checker.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_background_checker.py
import pytest
from src.background_checker import search_company_info

def test_search_company_info():
    result = search_company_info("Apple Inc.", "USA")
    assert "company_name" in result
    assert "basic_info" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_background_checker.py -v
```

预期：FAIL with "ModuleNotFoundError"

- [ ] **Step 3: 实现背调搜索模块**

```python
# src/background_checker.py
import httpx
from .config import config

def search_company_info(company_name: str, country: str = "") -> dict:
    """使用Tavily搜索公司信息"""
    
    search_queries = [
        f"{company_name} company overview business",
        f"{company_name} {country} financial status",
        f"{company_name} leadership team executives",
        f"{company_name} recent news 2024"
    ]
    
    results = {
        "company_name": company_name,
        "basic_info": {},
        "financial_info": {},
        "leadership": {},
        "recent_news": [],
        "sources": []
    }
    
    for query in search_queries:
        search_result = tavily_search(query)
        if search_result:
            results["sources"].extend(search_result.get("sources", []))
            # 根据查询类型分类结果
            if "overview" in query.lower():
                results["basic_info"] = search_result
            elif "financial" in query.lower():
                results["financial_info"] = search_result
            elif "leadership" in query.lower():
                results["leadership"] = search_result
            elif "news" in query.lower():
                results["recent_news"] = search_result.get("results", [])
    
    return results

def tavily_search(query: str) -> dict:
    """调用Tavily搜索API"""
    if not config.tavily.api_key:
        return {}
    
    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config.tavily.api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "max_results": 5
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Tavily搜索失败: {e}")
        return {}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python -m pytest tests/test_background_checker.py -v
```

预期：PASS

- [ ] **Step 5: Commit**

```bash
git add src/background_checker.py tests/test_background_checker.py
git commit -m "feat: 实现Tavily背调搜索模块"
```

---

## Task 6: 创建测试用例文档

**Files:**
- Create: `tests/test_cases.md`

- [ ] **Step 1: 创建测试用例文档**

```markdown
# 海外展会线索录入Agent - 测试用例

## 功能1：名片识别测试用例（4个场景）

### 测试用例1：标准电子名片
- **输入**：标准商务名片图片
- **预期输出**：
  - company_name: Tech Solutions GmbH
  - contact_name: Hans Mueller
  - email: hans.mueller@techsolutions.de
  - country: 德国
- **测试步骤**：
  1. 发送名片图片到飞书群
  2. 等待Agent回复
  3. 检查Bitable中是否新增记录

### 测试用例2：手机拍照名片（倾斜）
- **输入**：手机拍摄的名片，有15度倾斜
- **预期输出**：识别准确率85%+，低置信度字段标注
- **测试步骤**：同上

### 测试用例3：名片+详细文本补充
- **输入**：名片图片 + 文本"这是采购总监，对传感器感兴趣"
- **预期输出**：信息完整整合，提取跟进优先级
- **测试步骤**：同上

### 测试用例4：多语言名片（中英双语）
- **输入**：中英双语名片
- **预期输出**：双语信息完整提取
- **测试步骤**：同上

## 功能2：AI背调测试用例（3个场景）

### 测试用例5：上市公司背调
- **输入**：Apple Inc.
- **预期输出**：信息丰富，财务数据准确
- **测试步骤**：
  1. 录入Apple Inc.名片
  2. 等待背调完成
  3. 检查飞书文档报告

### 测试用例6：中小型私营企业
- **输入**：德国中小型制造企业
- **预期输出**：整合官方注册信息，财务数据有限
- **测试步骤**：同上

### 测试用例7：新兴市场企业
- **输入**：印度初创企业
- **预期输出**：整合区域特定数据源，风险提示
- **测试步骤**：同上
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_cases.md
git commit -m "docs: 添加测试用例文档"
```

---

## 实施顺序

1. Task 1: 验证cc-connect飞书消息收发（已完成）
2. Task 2: 创建项目基础结构
3. Task 3: 实现MiMo-V2.5名片识别
4. Task 4: 实现重复检测逻辑
5. Task 5: 实现Tavily背调搜索
6. Task 6: 创建测试用例文档

## 后续任务（待补充）

- Task 7: 实现Bitable读写
- Task 8: 实现飞书文档报告生成
- Task 9: 集成所有模块
- Task 10: 端到端测试
