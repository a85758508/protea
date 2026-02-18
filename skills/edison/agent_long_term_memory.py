import time
import json
import math
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LongTermMemory")

class LongTermMemory:
    """
    Agent Long-Term Memory: 长期记忆模块。
    支持记忆存储、语义检索（模拟）、遗忘曲线、优先级排序。
    """
    def __init__(self, storage_path: str = "/home/ubuntu/memory.json"):
        self.storage_path = storage_path
        self.memories: List[Dict[str, Any]] = self._load_memories()
        self.forgetting_rate = 0.1  # 遗忘率
        self.priority_threshold = 0.5  # 优先级阈值

    def _load_memories(self) -> List[Dict[str, Any]]:
        """从文件加载记忆"""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_memories(self):
        """保存记忆到文件"""
        with open(self.storage_path, 'w') as f:
            json.dump(self.memories, f, indent=4)

    def memorize(self, content: str, category: str = "general", priority: float = 1.0):
        """存储新记忆"""
        memory_item = {
            "id": len(self.memories) + 1,
            "content": content,
            "category": category,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "access_count": 1,
            "salience": priority  # 显著性
        }
        self.memories.append(memory_item)
        self._save_memories()
        logger.info(f"New memory stored: {content[:30]}...")

    def _calculate_retention(self, memory: Dict[str, Any]) -> float:
        """基于艾宾浩斯遗忘曲线计算记忆保留率"""
        created_at = datetime.fromisoformat(memory["created_at"])
        elapsed_hours = (datetime.now() - created_at).total_seconds() / 3600
        # R = e^(-t/S), 其中 S 是记忆强度
        strength = memory["salience"] * (1 + math.log(memory["access_count"]))
        retention = math.exp(-elapsed_hours * self.forgetting_rate / strength)
        return retention

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """语义检索（此处模拟为关键词匹配 + 优先级排序）"""
        results = []
        for memory in self.memories:
            # 模拟语义匹配：检查关键词
            relevance = 1.0 if query.lower() in memory["content"].lower() else 0.0
            retention = self._calculate_retention(memory)
            
            # 综合评分：相关性 * 保留率 * 原始优先级
            score = relevance * retention * memory["priority"]
            
            if score > 0.1:
                results.append((score, memory))
                # 更新访问信息
                memory["last_accessed"] = datetime.now().isoformat()
                memory["access_count"] += 1
        
        # 按评分降序排列
        results.sort(key=lambda x: x[0], reverse=True)
        self._save_memories()
        return [item[1] for item in results[:top_k]]

    def cleanup_forgotten_memories(self):
        """清理遗忘的记忆（保留率低于阈值且优先级不高的记忆）"""
        initial_count = len(self.memories)
        self.memories = [
            m for m in self.memories 
            if self._calculate_retention(m) > 0.05 or m["priority"] > self.priority_threshold
        ]
        removed_count = initial_count - len(self.memories)
        if removed_count > 0:
            self._save_memories()
            logger.info(f"Cleaned up {removed_count} forgotten memories.")

# 示例用法
if __name__ == "__main__":
    ltm = LongTermMemory()
    # ltm.memorize("User prefers dark mode for UI.", category="preferences", priority=0.9)
    # results = ltm.retrieve("dark mode")
    # print(results)
