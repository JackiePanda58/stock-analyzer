import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger():
    log_dir = "/root/stock-analyzer/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "system_debug.log")

    logger = logging.getLogger("StockAnalyzer")
    # 避免重复绑定 handler
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # 配置文件输出：最大 5MB，保留 3 个旧备份
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # 配置控制台输出
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 日志格式：[时间] [级别] [文件名:行号] - 消息
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

sys_logger = setup_logger()
