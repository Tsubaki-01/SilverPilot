"""
模块名称：utils
功能描述：工具函数子包的初始化模块，对外暴露通用的日志工具函数 get_channel_logger，
         用于创建支持多目录隔离的 logger 实例。
"""

from .log import get_channel_logger

__all__ = ["get_channel_logger"]
