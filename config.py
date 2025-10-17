# app/config.py
import os
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class DatabaseConfig:
    """データベース接続設定"""
    host: str = 'localhost'
    user: str = 'root'
    password: str = 'daisoseisanka1470-3#'
    database: str = 'kubota_db'
    charset: str = 'utf8mb4'
    port: int = 3306
    autocommit: bool = True
    connect_timeout: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'user': self.user,
            'password': self.password,
            'database': self.database,
            'charset': self.charset,
            'port': self.port,
            'autocommit': self.autocommit,
            'connect_timeout': self.connect_timeout
        }

@dataclass
class AppConfig:
    """アプリケーション設定"""
    page_title: str = "生産計画管理システム"
    page_icon: str = "🏭"
    layout: str = "wide"

# 設定インスタンス
DB_CONFIG = DatabaseConfig()
APP_CONFIG = AppConfig()




