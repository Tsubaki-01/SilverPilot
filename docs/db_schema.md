# Milvus 数据库设计文档

## 概述

本集合（Collection）主要用于存储和检索 **Huatuo26M-Lite 医疗问答库** 的数据。通过对医疗问题进行向量化处理，支持基于语义相似度的高效问答检索。

- **集合名称 (Collection Name):** `medical_qa_lite`
- **集合描述 (Description):** Huatuo26M-Lite 医疗问答库
- **核心检索字段:** `question_vector` (用于向量相似度搜索)

------

## 字段设计 (Schema)

以下是 `medical_qa_lite` 集合的具体字段结构定义：

| **字段名称 (Field Name)** | **数据类型 (Data Type)** | **长度/维度限制**  | **约束与属性 (Attributes)**            | **字段说明 (Description)**                            |
| ------------------------- | ------------------------ | ------------------ | -------------------------------------- | ----------------------------------------------------- |
| **`qa_id`**               | `INT64`                  | -                  | **主键 (Primary Key)** `auto_id=False` | 问答对的全局唯一标识 ID。由外部系统指定，不自动生成。 |
| **`question_text`**       | `VARCHAR`                | `max_length: 1000` | -                                      | 医疗问题纯文本内容。                                  |
| **`answer_text`**         | `VARCHAR`                | `max_length: 4000` | -                                      | 对应的医疗回答纯文本内容。                            |
| **`score`**               | `INT16`                  | -                  | -                                      | 该问答对的评分或质量权重。                            |
| **`department`**          | `VARCHAR`                | `max_length: 100`  | -                                      | 相关的医疗科室（如：内科、儿科、皮肤科等）。          |
| **`source`**              | `VARCHAR`                | `max_length: 100`  | -                                      | 数据来源标记（如网站名、具体子数据集等）。            |
| **`question_vector`**     | `FLOAT_VECTOR`           | `dim: vector_dim`* | **索引字段 (Index)**                   | 问题文本 (`question_text`) 转换后的浮点型特征向量。   |

> **注\*：** `question_vector` 的具体维度 (`vector_dim`) 取决于项目中使用的 Embedding 模型的输出维度（例如：BGE模型常为 768 或 1024，OpenAI 常用 1536）。请确保写入数据时的向量维度与建表时注入的 `self.vector_dim` 保持一致。

------

## 索引配置 (Index)

- **目标字段:** `question_vector`
- **说明:** 系统默认会在 `question_vector` 字段上构建向量索引，以加速大规模医疗数据下的 相似度检索。
