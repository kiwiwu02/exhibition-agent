# 海外展会线索录入 Agent

面向海外展会场景的智能 CRM 系统。销售在展会现场发送名片图片，系统自动完成 OCR 识别、重复检测、多维度背调、报告生成，全流程 < 3 分钟。

## 功能亮点

- **名片智能识别** — 基于 Qwen3.5-omni 多模态 LLM，支持中/英/日/韩多语言名片，图片直接理解
- **文本补充解析** — 支持图片+文字同时发送，正则+LLM 双层提取，名片缺失信息可由用户文字补全
- **智能重复检测** — 邮箱/公司名+联系人/电话多规则匹配，支持合并或新建
- **公司名自动发现** — 域名 WHOIS 反查、网页爬取、LinkedIn 搜索等 5 级策略
- **多 Agent 并行背调** — 6 个专业 Agent 并行调研（基础信息、工商法律、财务信用、组织架构、动态新闻、供应链口碑），15+ 数据源
- **交叉验证** — 名片信息与调研数据多源对比，不一致时高亮提示
- **自动报告生成** — 飞书文档 8 章节结构化报告，带引用体系
- **CRM 自动补全** — 自动识别 Bitable 缺失字段并从调研结果中填写

## 技术架构

### 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        飞书机器人 (WebSocket)                      │
│  接收名片图片 + 文本 → MessageHandler 路由分发                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ExhibitionAgent (主流程)                        │
│                                                                   │
│  1. 名片 OCR 识别 (Qwen3.5-omni 多模态)                           │
│     └─ 文本补充合并 (正则 + LLM 双层解析)                           │
│  2. 智能重复检测 (邮箱/公司名+联系人/电话 多规则)                     │
│     ├─ 合并 → 补充已有记录                                         │
│     └─ 新建 → 创建 Bitable 记录                                    │
│  3. 公司名自动发现 (域名WHOIS/网页爬取/LinkedIn/搜索 5级策略)         │
│  4. 已知信息后处理校正 (如三星电子职位自动修正)                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SupervisorAgent (调研调度)                       │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Group 1: 基础信息 (串行执行)                               │     │
│  │   BasicInfoAgent — WHOIS / Wayback / Google Maps /       │     │
│  │                    LinkedIn / 深度搜索                     │     │
│  └──────────────────────────┬──────────────────────────────┘     │
│                              │                                    │
│  ┌──────────────────────────▼──────────────────────────────┐     │
│  │ Group 2: 专项调研 (5个Agent并行, ThreadPoolExecutor)       │     │
│  │   BusinessLegalAgent   — OpenCorporates / 法律风险        │     │
│  │   FinancialCreditAgent — SEC EDGAR / yfinance / 财务     │     │
│  │   OrgStructureAgent    — 组织架构 / 管理层 / 招聘          │     │
│  │   DynamicNewsAgent     — 新闻动态 / 行业趋势              │     │
│  │   SupplyChainAgent     — 供应链 / 口碑 / 负面信息          │     │
│  └──────────────────────────┬──────────────────────────────┘     │
│                              │                                    │
│  ┌──────────────────────────▼──────────────────────────────┐     │
│  │ Group 3: 后处理                                           │     │
│  │   CrossValidationAgent — 多源交叉验证 (名片 vs 调研)      │     │
│  │   CRMSupplementAgent   — Bitable 缺失字段自动补全         │     │
│  │   ReportWriterAgent    — 飞书文档 8章节结构化报告生成      │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        输出                                      │
│  • 飞书卡片回复 (即时)                                            │
│  • Bitable CRM 记录 (自动写入/更新)                               │
│  • 飞书文档调研报告 (异步生成, 完成后通知)                          │
└─────────────────────────────────────────────────────────────────┘
```

### 数据源

| Agent | 数据源 |
|-------|--------|
| BasicInfoAgent | WHOIS、Wayback Machine、Google Maps、LinkedIn、DuckDuckGo |
| BusinessLegalAgent | OpenCorporates、各国工商官网、法律风险数据库 |
| FinancialCreditAgent | SEC EDGAR、yfinance、各国年报平台 |
| OrgStructureAgent | LinkedIn、CorporationWiki、公司官网 |
| DynamicNewsAgent | Google News RSS、公司官网新闻、LinkedIn 动态 |
| SupplyChainAgent | Trustpilot、Sitejabber、海关公开数据 |

### 技术栈

| 组件 | 技术 |
|------|------|
| LLM | Qwen3.5-omni (阿里云百炼) |
| 搜索引擎 | Tavily + DuckDuckGo |
| 飞书集成 | lark-oapi SDK (WebSocket) |
| CRM | 飞书 Bitable 多维表格 |
| 文档生成 | 飞书 Docx API |
| Web 框架 | FastAPI + Uvicorn |
| 并行执行 | Python ThreadPoolExecutor |
| 数据模型 | Python dataclass |

## 部署

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env  # 填入你的 API Key

# 启动服务
python run.py
```

## 环境变量

参见 `.env.example`，需要配置以下变量：

| 变量 | 说明 |
|------|------|
| `MIMO_API_KEY` | 阿里云百炼 API Key |
| `MIMO_MODEL` | 模型名称（默认 qwen3.5-omni-flash-2026-03-15） |
| `TAVILY_API_KEY` | Tavily 搜索 API Key |
| `FEISHU_APP_ID` | 飞书应用 App ID |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_BITABLE_APP_TOKEN` | 飞书多维表格 App Token |
| `FEISHU_BITABLE_TABLE_ID` | 飞书多维表格 Table ID |
