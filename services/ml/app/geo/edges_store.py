class EdgesStore:
    def __init__(self, parquet_path: str):
        self.parquet_path = parquet_path
        
    def get_comfort_for_nodes(self, node_pairs: list[tuple[int,int]]) -> list[dict]:
        return [{"score": 75.0} for _ in node_pairs]
