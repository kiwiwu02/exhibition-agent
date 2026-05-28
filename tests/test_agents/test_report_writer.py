"""ReportWriterAgent 新版测试"""
import pytest
from unittest.mock import MagicMock
from src.agents.report_writer import ReportWriterAgent
from src.models import BusinessCard, AgentResult
from src.tools.deep_search import SourceIndex


@pytest.fixture
def agent():
    return ReportWriterAgent()


@pytest.fixture
def sample_card():
    return BusinessCard(
        company_name="Example Corp",
        company_name_en="Example Corporation",
        contact_name="John Smith",
        position="CEO",
        email="john@example.com",
        phone="+1-555-0123",
        address="123 Main St, New York, NY",
        country="USA",
        website="https://example.com",
    )


@pytest.fixture
def sample_results():
    return [
        AgentResult(
            agent_name="basic_info",
            content="公司官网：example.com，域名注册于2010年 [B1]\n\n来源列表（引用时使用方括号中的编号）：\n[B1] https://example.com - Example Corp 官网",
            sources=["https://example.com", "WHOIS:example.com"],
            source_urls=["https://example.com"],
        ),
        AgentResult(
            agent_name="business_legal",
            content="OpenCorporates 查询显示公司状态为 Active [L1]\n\n来源列表（引用时使用方括号中的编号）：\n[L1] https://opencorporates.com - OpenCorporates",
            sources=["https://opencorporates.com"],
            source_urls=["https://opencorporates.com"],
        ),
        AgentResult(
            agent_name="financial_credit",
            content="SEC EDGAR 显示公司有10-K filing [F1]\n\n来源列表（引用时使用方括号中的编号）：\n[F1] https://sec.gov - SEC EDGAR",
            sources=["https://sec.gov"],
            source_urls=["https://sec.gov"],
        ),
        AgentResult(
            agent_name="org_structure",
            content="LinkedIn 显示公司有50-100名员工，CEO: John Smith [O1]\n\n来源列表（引用时使用方括号中的编号）：\n[O1] https://linkedin.com - LinkedIn",
            sources=["https://linkedin.com"],
            source_urls=["https://linkedin.com"],
        ),
        AgentResult(
            agent_name="dynamic_news",
            content="近期新闻：公司获得B轮融资 [N1]\n\n来源列表（引用时使用方括号中的编号）：\n[N1] https://news.example.com - 新闻报道",
            sources=["https://news.example.com"],
            source_urls=["https://news.example.com"],
        ),
        AgentResult(
            agent_name="supply_chain",
            content="Trustpilot 评分 4.2/5 [S1]\n\n来源列表（引用时使用方括号中的编号）：\n[S1] https://trustpilot.com - Trustpilot",
            sources=["https://trustpilot.com"],
            source_urls=["https://trustpilot.com"],
        ),
    ]


@pytest.fixture
def sample_source_index():
    index = SourceIndex()
    index.add_source(url="https://example.com", title="Example Corp", content="官网内容", category="search")
    index.add_source(url="WHOIS:example.com", title="WHOIS 信息", content="域名信息", category="whois")
    index.add_source(url="OpenCorporates", title="OpenCorporates", content="工商信息", category="opencorporates")
    return index


def test_agent_name(agent):
    assert agent.name == "report_writer"


def test_write_report_returns_research_report(agent, sample_card, sample_results, sample_source_index):
    report = agent.write_report(sample_card, sample_results, sample_source_index)
    assert report.company_name == "Example Corp"
    assert report.verified is True
    assert len(report.sources) > 0
    assert report.full_report_content != ""
    assert "Trustpilot 评分 4.2/5" in report.supply_chain


def test_write_report_has_full_content(agent, sample_card, sample_results, sample_source_index):
    report = agent.write_report(sample_card, sample_results, sample_source_index)
    # 完整报告应包含标题
    assert "# Example Corp 公司调研报告" in report.full_report_content
    # sample_results 包含所有维度，应有多个章节
    assert "## 1." in report.full_report_content
    assert "## 参考来源" in report.full_report_content
    # 所有有内容的维度都应该展示
    assert "公司概览与基本面" in report.full_report_content
    assert "规模与健康度" in report.full_report_content
    assert "组织架构" in report.full_report_content
    assert "动态与新闻" in report.full_report_content
    assert "合作案例与行业口碑" in report.full_report_content


def test_categorize_results(agent, sample_results):
    categorized = agent._categorize_results(sample_results)
    assert "basic_info" in categorized
    assert "business_legal" in categorized
    assert "financial_credit" in categorized
    assert "org_structure" in categorized
    assert "dynamic_news" in categorized
    assert "supply_chain" in categorized


def test_collect_sources(agent, sample_results):
    sources = agent._collect_sources(sample_results)
    assert len(sources) > 0
    assert any(s["url"] == "https://example.com" for s in sources)


def test_section_company_overview(agent, sample_card, sample_source_index):
    categorized = {"basic_info": "主营业务：软件开发"}
    prefixed_sources = {"basic_info": {"[B1]": "https://example.com"}}
    content = agent._section_company_overview(sample_card, categorized, prefixed_sources)
    assert "Example Corp" in content
    assert "example.com" in content
    assert "软件开发" in content
    assert "### 基本信息" in content
    assert "### 业务概况" in content


def test_section_health_scale(agent, sample_source_index):
    categorized = {"business_legal": "公司状态Active", "financial_credit": "有10-K filing"}
    prefixed_sources = {}
    content = agent._section_health_scale(categorized, prefixed_sources)
    assert "工商与法律信息" in content
    assert "财务与信用状况" in content


def test_section_confidence_assessment(agent):
    # 有内容的维度才会出现在可信度评估中
    categorized = {"basic_info": "test", "business_legal": "test2"}
    content = agent._section_confidence_assessment(categorized)
    assert "信息可信度评估" in content
    assert "基本信息" in content
    assert "工商法律" in content
    # 没有内容的维度不会出现
    assert "财务信用" not in content


def test_section_confidence_assessment_empty(agent):
    # 所有维度都为空时，整个章节不展示
    categorized = {}
    content = agent._section_confidence_assessment(categorized)
    assert content == ""


def test_section_sales_summary(agent, sample_card):
    categorized = {
        "org_structure": "CEO: John Smith, 50-100 employees",
        "dynamic_news": "公司获得B轮融资",
        "supply_chain": "负面信息：客户投诉"
    }
    content = agent._section_sales_summary(sample_card, categorized, {})
    assert "销售视角摘要" in content
    assert "经营风险提示" in content
    assert "关键决策人" in content
    assert "合作建议" in content


def test_extract_risks(agent):
    categorized = {
        "business_legal": "存在法律诉讼",
        "supply_chain": "负面信息"
    }
    risks = agent._extract_risks(categorized)
    assert len(risks) > 0
    assert any("法律诉讼" in r for r in risks)


def test_extract_decision_makers(agent):
    categorized = {
        "org_structure": "CEO: John Smith\nCTO: Jane Doe\n员工数: 100"
    }
    makers = agent._extract_decision_makers(categorized)
    assert len(makers) > 0


def test_section_references(agent):
    prefixed_sources = {
        "basic_info": {"[B1]": "https://example.com"},
        "business_legal": {"[L1]": "https://opencorporates.com"},
    }
    content = agent._section_references_by_prefix(prefixed_sources)
    assert "[B1]" in content
    assert "https://example.com" in content
    assert "[L1]" in content
    assert "https://opencorporates.com" in content
    assert "基础信息调研" in content
    assert "工商法律调研" in content
    assert "本报告由 AI 自动生成" in content


def test_get_crm_supplements(agent):
    card = BusinessCard(company_name="Test Corp")
    categorized = {"basic_info": "Also known as Test Corp Inc. Based in New York. Website: https://testcorp.com"}
    supplements = agent.get_crm_supplements(card, categorized)
    assert isinstance(supplements, dict)


def test_empty_sections_not_in_report(agent):
    """测试空内容章节不出现在报告中"""
    card = BusinessCard(company_name="Minimal Corp")
    # 只有 basic_info，其他维度为空
    results = [
        AgentResult(agent_name="basic_info", content="主营业务：软件开发"),
    ]
    report = agent.write_report(card, results, None)
    content = report.full_report_content

    # 有内容的章节应该出现
    assert "公司概览与基本面" in content
    # 无内容的章节不应该出现（检查章节标题格式 "## N. 章节名"）
    assert "## 规模与健康度" not in content
    assert "## 组织架构" not in content
    assert "## 动态与新闻" not in content
    assert "## 合作案例与行业口碑" not in content


def test_section_numbering_dynamic(agent):
    """测试章节编号动态调整 - 空章节被跳过，编号连续"""
    card = BusinessCard(company_name="Test Corp")
    # 只有 basic_info 和 dynamic_news，其他维度为空
    results = [
        AgentResult(agent_name="basic_info", content="基础信息内容"),
        AgentResult(agent_name="dynamic_news", content="新闻内容"),
    ]
    report = agent.write_report(card, results, None)
    content = report.full_report_content

    # 有内容的章节编号从1开始连续
    assert "## 1. 公司概览与基本面" in content
    assert "## 2. 动态与新闻" in content
    # 可信度评估（有 basic_info 和 dynamic_news）是第3
    assert "## 3. 信息可信度评估" in content
    # 销售视角（有合作建议）是第4
    assert "## 4. 销售视角摘要" in content
    # CRM补充是第5
    assert "## 5. CRM 字段补充建议" in content
    # 不应有第6个章节
    assert "## 6." not in content


# ========== LLM 集成测试 ==========

def test_llm_summarize_calls_openai(agent, monkeypatch):
    """测试 _llm_summarize 调用 OpenAI SDK"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="总结内容"))]
    mock_client.chat.completions.create.return_value = mock_response

    monkeypatch.setattr("src.agents.report_writer.OpenAI", lambda **kwargs: mock_client)

    result = agent._llm_summarize("测试 prompt")
    assert result == "总结内容"
    mock_client.chat.completions.create.assert_called_once()


def test_llm_summarize_returns_empty_on_failure(agent, monkeypatch):
    """测试 _llm_summarize 失败时返回空字符串"""
    def raise_error(**kwargs):
        raise Exception("API 错误")

    monkeypatch.setattr("src.agents.report_writer.OpenAI", lambda **kwargs: MagicMock(
        chat=MagicMock(completions=MagicMock(create=raise_error))
    ))

    result = agent._llm_summarize("测试 prompt")
    assert result == ""


def test_section_company_overview_uses_llm(agent, sample_card, sample_source_index, monkeypatch):
    """测试公司概览章节使用 LLM 总结"""
    categorized = {"basic_info": "主营业务：软件开发，成立于2010年"}
    prefixed_sources = {}

    # Mock LLM 返回总结内容
    agent._llm_summarize = MagicMock(return_value="- **核心业务**：软件开发\n- **成立时间**：2010年")

    content = agent._section_company_overview(sample_card, categorized, prefixed_sources)
    assert "核心业务" in content
    assert "软件开发" in content
    agent._llm_summarize.assert_called_once()


def test_section_company_overview_fallback_on_llm_failure(agent, sample_card, sample_source_index, monkeypatch):
    """测试 LLM 失败时 fallback 到原始内容"""
    categorized = {"basic_info": "主营业务：软件开发，成立于2010年"}
    prefixed_sources = {}

    # Mock LLM 返回空（失败）
    agent._llm_summarize = MagicMock(return_value="")

    content = agent._section_company_overview(sample_card, categorized, prefixed_sources)
    # fallback 应包含原始内容
    assert "主营业务" in content
    assert "软件开发" in content


def test_section_health_scale_uses_llm(agent, monkeypatch):
    """测试规模与健康度章节使用 LLM 总结"""
    categorized = {"business_legal": "公司状态Active", "financial_credit": "有10-K filing"}
    prefixed_sources = {}

    agent._llm_summarize = MagicMock(return_value="### 工商与法律信息\n\n- 公司状态正常\n\n### 财务与信用状况\n\n- 有定期 filing")

    content = agent._section_health_scale(categorized, prefixed_sources)
    assert "工商与法律信息" in content
    assert "财务与信用状况" in content
    agent._llm_summarize.assert_called_once()


def test_section_org_structure_uses_llm(agent, sample_card, monkeypatch):
    """测试组织架构章节使用 LLM 总结"""
    categorized = {"org_structure": "CEO: John Smith, CTO: Jane Doe"}
    prefixed_sources = {}

    agent._llm_summarize = MagicMock(return_value="- **CEO**：John Smith\n- **CTO**：Jane Doe")

    content = agent._section_org_structure(sample_card, categorized, prefixed_sources)
    assert "CEO" in content
    assert "John Smith" in content
    agent._llm_summarize.assert_called_once()


def test_section_news_dynamics_uses_llm(agent, monkeypatch):
    """测试动态新闻章节使用 LLM 总结"""
    categorized = {"dynamic_news": "公司获得B轮融资5000万美元"}
    prefixed_sources = {}

    agent._llm_summarize = MagicMock(return_value="- **B轮融资**：获得5000万美元投资")

    content = agent._section_news_dynamics(categorized, prefixed_sources)
    assert "B轮融资" in content
    agent._llm_summarize.assert_called_once()


def test_section_reputation_cases_uses_llm(agent, monkeypatch):
    """测试合作案例章节使用 LLM 总结"""
    categorized = {"supply_chain": "Trustpilot评分4.2，客户评价良好"}
    prefixed_sources = {}

    agent._llm_summarize = MagicMock(return_value="- **Trustpilot评分**：4.2/5，客户评价良好")

    content = agent._section_reputation_cases(categorized, prefixed_sources)
    assert "Trustpilot评分" in content
    agent._llm_summarize.assert_called_once()


def test_section_sales_summary_uses_llm(agent, sample_card, monkeypatch):
    """测试销售视角章节使用 LLM 总结"""
    categorized = {
        "org_structure": "CEO: John Smith",
        "dynamic_news": "公司获得B轮融资",
    }
    prefixed_sources = {}

    agent._llm_summarize = MagicMock(return_value="### 经营风险提示\n\n- 无明显风险\n\n### 合作建议\n\n- 建议高层会面")

    content = agent._section_sales_summary(sample_card, categorized, prefixed_sources)
    assert "经营风险提示" in content
    assert "合作建议" in content
    agent._llm_summarize.assert_called_once()


def test_write_report_with_llm(agent, sample_card, sample_results, sample_source_index, monkeypatch):
    """测试完整报告生成使用 LLM"""
    # Mock LLM 返回各章节总结
    def mock_summarize(prompt, max_tokens=2000):
        if "业务概况" in prompt or "核心业务" in prompt:
            return "- **核心业务**：软件开发"
        elif "规模与健康度" in prompt or "工商" in prompt:
            return "### 工商与法律信息\n\n- 状态正常"
        elif "组织架构" in prompt:
            return "- **CEO**：John Smith"
        elif "动态与新闻" in prompt:
            return "- **B轮融资**：获得投资"
        elif "合作案例" in prompt:
            return "- **Trustpilot**：评分4.2"
        elif "销售视角" in prompt:
            return "### 合作建议\n\n- 建议合作"
        return ""

    agent._llm_summarize = mock_summarize

    report = agent.write_report(sample_card, sample_results, sample_source_index)
    assert report.full_report_content != ""
    assert "# Example Corp 公司调研报告" in report.full_report_content
