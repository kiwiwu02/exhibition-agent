from ..models import BusinessCard, AgentResult


class BaseAgent:
    """Agent基类，所有调研Agent应继承此类"""

    def __init__(self, name: str):
        self.name = name

    def research(self, card: BusinessCard) -> AgentResult:
        """执行调研任务，返回结果。子类应重写此方法以提供具体调研逻辑。"""
        return self._create_result(
            content=f"[{self.name}] 默认调研结果 - 子类应重写此方法",
            sources=[],
            confidence="low"
        )

    def _create_result(self, content: str, sources: list = None, confidence: str = "medium") -> AgentResult:
        """创建标准结果"""
        return AgentResult(
            agent_name=self.name,
            content=content,
            sources=sources or [],
            confidence=confidence
        )
