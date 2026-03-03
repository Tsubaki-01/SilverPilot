"""
模块名称: huatuo_dlq_recovery.py
功能描述: 银发守护项目 - 死信队列 (DLQ) 数据清洗与补偿入库脚本
处理逻辑: 读取 DLQ 文件 -> 诊断超长字符 -> 强制安全截断 -> 重新向量化 -> 重新入库
"""

import json
import os
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from FlagEmbedding import FlagModel
from silver_pilot.dao.milvus_dao import MilvusManager

# ================= 导入项目配置与基建 =================
from silver_pilot.config import config
from silver_pilot.utils.log import LogManager

# 初始化日志
LOG_FILE_DIR: Path = config.LOG_DIR / "pipeline_logs"
log_manager = LogManager(LOG_FILE_DIR, "DLQRecovery")
logger = log_manager.get_logger()
# ===================================================


class DLQRecoveryPipeline:
    def __init__(self, collection_name: str = "medical_qa_lite", batch_size: int = 500) -> None:
        self.batch_size: int = batch_size
        self.vector_dim: int = 1024

        # 1. 连接 Milvus (无需重新建表，直接复用已有表)
        self.db_manager = MilvusManager(collection_name=collection_name)

        # 2. 延迟加载 Embedding 模型
        self.embed_model: FlagModel | None = None

        # 3. 截断安全阈值 (Milvus schema 限制 4000，预留 10 个字符 buffer)
        self.MAX_ANSWER_LEN = 3990
        self.MAX_QUESTION_LEN = 990

    def _load_model(self) -> None:
        """加载 BGE-M3 模型"""
        if self.embed_model is None:
            import torch

            if not torch.cuda.is_available():
                logger.warning("未检测到 GPU，将使用 CPU 运行修复程序。")
            logger.info("⏳ 正在加载 BAAI/bge-m3 Embedding 模型...")
            self.embed_model = FlagModel("BAAI/bge-m3", use_fp16=torch.cuda.is_available())
            logger.success("✅ 模型加载完毕！")

    def run_recovery(self) -> None:
        """核心修复流：读取 DLQ -> 截断 -> 向量化 -> 入库"""
        dlq_file_path = config.DATA_DIR / "huatuo_dlq.jsonl"

        if not dlq_file_path.exists():
            logger.info("🎉 未发现 DLQ 文件，暂无需要补偿的数据。")
            return

        logger.info(f"🛠️ 开始解析死信文件: {dlq_file_path}")

        # 1. 展平提取所有数据
        recovery_items: list[dict[str, Any]] = []
        with open(dlq_file_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    # 从 DLQ 记录中提取原始批次数据
                    batch_data = record.get("data", [])
                    # 兼容之前你原本的 original_data 结构，如果你存的是 batch 列表就直接 extend
                    if isinstance(batch_data, list):
                        recovery_items.extend(batch_data)
                except json.JSONDecodeError:
                    logger.error("DLQ 文件某行 JSON 解析失败，已跳过。")

        total_records = len(recovery_items)
        if total_records == 0:
            logger.warning("DLQ 文件中没有提取到有效数据。")
            return

        logger.info(f"🔍 共提取出 {total_records} 条待修复数据，准备执行清洗与截断策略...")
        self._load_model()

        success_count = 0

        # 2. 分批重试入库
        for i in range(0, total_records, self.batch_size):
            batch_items = recovery_items[i : i + self.batch_size]

            # --- 核心清洗逻辑：防御性截断 ---
            for item in batch_items:
                # 修复 answer 超长
                if len(item["answer_text"]) > self.MAX_ANSWER_LEN:
                    logger.debug(f"✂️ 截断超长 Answer (ID: {item.get('qa_id')}) - 原长度: {len(item['answer_text'])}")
                    item["answer_text"] = item["answer_text"][: self.MAX_ANSWER_LEN] + "..."

                # 修复 question 超长 (以防万一)
                if len(item["question_text"]) > self.MAX_QUESTION_LEN:
                    item["question_text"] = item["question_text"][: self.MAX_QUESTION_LEN] + "..."

            # 3. 重新向量化 (加上你的日志黑洞)
            instruction = "为这个医学问题生成表示，用于检索相关的专业解答："
            queries = [f"{instruction}{item['question_text']}" for item in batch_items]

            with open(os.devnull, "w") as devnull:
                with redirect_stdout(devnull), redirect_stderr(devnull):
                    assert self.embed_model is not None
                    embeddings = self.embed_model.encode(queries)

            vector_list = [emb.tolist() for emb in embeddings]

            # 4. 组装实体并插入
            entities = [
                [item["qa_id"] for item in batch_items],
                [item["question_text"] for item in batch_items],
                [item["answer_text"] for item in batch_items],
                [item["score"] for item in batch_items],
                [item["department"] for item in batch_items],
                [item["source"] for item in batch_items],
                vector_list,
            ]

            try:
                self.db_manager.insert_data(entities)
                success_count += len(batch_items)
                logger.info(f"✅ 补偿进度: {success_count}/{total_records} 条")
            except Exception as e:
                logger.error(f"❌ 补偿失败 (批次 {i}): {e}")

        # 5. 善后处理：备份已处理的 DLQ 文件
        backup_path = config.DATA_DIR / f"huatuo_dlq_processed_{int(time.time())}.jsonl"
        os.rename(dlq_file_path, backup_path)
        logger.success("-" * 40)
        logger.success(f"🎊 补偿入库全部完成！共成功挽救了 {success_count} 条数据。")
        logger.success(f"📦 原 DLQ 文件已备份至: {backup_path}")
        logger.success("-" * 40)


if __name__ == "__main__":
    recovery = DLQRecoveryPipeline(batch_size=512)
    recovery.run_recovery()
