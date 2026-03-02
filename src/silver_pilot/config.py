import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


class Config:
    # 1. 确定当前文件所在目录
    CURRENT_PKG_DIR: Path = Path(__file__).resolve().parent

    # 2. 确定项目根目录
    ROOT_DIR: Path = CURRENT_PKG_DIR.parent.parent

    # 3. 加载根目录下的 .env 文件
    load_dotenv(ROOT_DIR / ".env")

    # 对应你截图里的根目录文件夹
    DATA_DIR: Path = ROOT_DIR / "data"
    FILES_DIR: Path = ROOT_DIR / "files"
    WORKSPACE_DIR: Path = ROOT_DIR / "workspace"
    SCRIPTS_DIR: Path = ROOT_DIR / "scripts"
    TMP_DIR: Path = ROOT_DIR / "tmp"
    LOG_DIR: Path = ROOT_DIR / "logs"

    # --- 环境变量 (带默认值或类型转换) ---
    # 读取你的 API Key 或数据库配置
    # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # DEBUG_MODE = os.getenv("DEBUG", "False").lower() == "true"
    DASHSCOPE_API_KEY: str | None = os.getenv("DASHSCOPE_API_KEY")
    NEO4J_URI: str | None = os.getenv("NEO4J_URI")
    NEO4J_USER: str | None = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD: str | None = os.getenv("NEO4J_PASSWORD")
    MILVUS_HOST: str | None = os.getenv("MILVUS_HOST")
    MILVUS_PORT: str | None = os.getenv("MILVUS_PORT")

    # --- 自动初始化 (可选) ---
    @classmethod
    def check_dirs(cls) -> None:
        """确保关键目录存在，不存在则自动创建"""
        for attr in ["DATA_DIR", "LOG_DIR"]:
            dir_path = getattr(cls, attr)
            dir_path.mkdir(exist_ok=True)  # 不存在则创建，存在则忽略
            print(f"检查/创建目录：{dir_path}")


# 使用 lru_cache 装饰器实现单例模式
# 避免每次导入都重新读取文件，提高性能
@lru_cache
def get_configs() -> Config:
    Config.check_dirs()
    return Config()


config: Config = get_configs()
