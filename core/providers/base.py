class Provider:
    """所有数据源的统一接口。provider 自身无状态(enabled/interval 覆盖由 Hub 持有)。"""

    id: str = ""

    def topics(self) -> list[str]:
        raise NotImplementedError

    def default_interval(self, topic: str) -> float:
        raise NotImplementedError

    def poll(self, topic: str) -> dict:
        raise NotImplementedError
