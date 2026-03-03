"""
模块名称：neo4j_extract_relation_subject
功能描述：从 Neo4j 全量导出的 CSV 文件中提取所有唯一的节点标签（Labels）和关系类型（Types），
         并将提取结果保存为 JSON 格式的 Schema 文件，作为知识图谱构建流程的第一步。
"""

import json

import pandas as pd

from silver_pilot.config import config

df = pd.read_csv(config.DATA_DIR / "raw/databases/neo4j/full_export.csv")

unique_labels = df["_labels"].dropna().unique().tolist()
unique_types = df["_type"].dropna().unique().tolist()

data_to_save = {"labels": unique_labels, "types": unique_types}

output_filename = config.DATA_DIR / "processed" / "extract" / "neo4j_schema.json"
with open(output_filename, "w", encoding="utf-8") as f:
    json.dump(data_to_save, f, ensure_ascii=False, indent=4)

print(f"提取完成！文件已保存为: {output_filename}")
