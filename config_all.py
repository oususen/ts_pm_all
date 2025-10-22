#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
アプリケーション設定・DB接続設定
APP_ENV による本番/開発切り替え
.env の DEV_DB_* / PROD_DB_* に対応
"""

import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込む（プロジェクトルートから）
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / '.env'
load_dotenv(dotenv_path=ENV_PATH, override=True)

# -------------------------
# 環境判定
# -------------------------
APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PROD = APP_ENV == "production"

# -------------------------
# データベース設定
# -------------------------
@dataclass
class DatabaseConfig:
    host: str
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    port: int = 3306
    autocommit: bool = True
    connect_timeout: int = 10
    # プール
    pool_size: int = 10
    pool_min_cached: int = 2
    pool_max_cached: int = 5
    pool_blocking: bool = True
    # 複数DB対応
    is_primary: bool = True  # プライマリかセカンダリか
    priority: int = 1        # 優先度（1が最高）
    name: str = "default"    # DB識別名

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
            "port": self.port,
            "autocommit": self.autocommit,
            "connect_timeout": self.connect_timeout,
        }

    def to_pool_config(self) -> Dict[str, Any]:
        base = self.to_dict()
        base.update({
            "maxconnections": self.pool_size,
            "mincached": self.pool_min_cached,
            "maxcached": self.pool_max_cached,
            "blocking": self.pool_blocking,
        })
        return base


# -------------------------
# アプリケーション設定
# -------------------------
'''
@dataclass
class AppConfig:
    page_title: str = "生産計画管理システム"
    page_icon: str = "🏭"
    layout: str = "wide"
    window_title: str = "生産管理システム"
    window_size: str = "1200x800"
    default_font: str = "Meiryo UI"
    font_size: int = 10
    theme: str = "clam"
    log_file: str = "production_system.log"
    log_level: str = "INFO"
    log_max_size: int = 10  # MB
    log_backup_count: int = 5
    data_directory: str = "data"
    backup_directory: str = "backups"
    export_directory: str = "exports"
'''
@dataclass
class AppConfig:
    """アプリケーション設定"""
    page_title: str = "生産計画管理システム"
    page_icon: str = "🏭"
    layout: str = "wide"
    log_level: str = "INFO"
    window_title: str = "生産管理システム"
    window_size: str = "1200x800"
    default_font: str = "Meiryo UI"
    font_size: int = 10
    theme: str = "clam"
    log_file: str = "production_system.log"
    log_max_size: int = 10  # MB
    log_backup_count: int = 5
    data_directory: str = "data"
    backup_directory: str = "backups"
    export_directory: str = "exports"

# -------------------------
# フォーマット設定
# -------------------------
@dataclass
class FormatConfig:
    date_format: str = "%Y-%m-%d"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    time_format: str = "%H:%M:%S"
    display_date_format: str = "%Y年%m月%d日"
    display_datetime_format: str = "%Y年%m月%d日 %H時%M分"
    number_format: str = "{:,.0f}"
    decimal_format: str = "{:.2f}"


# -------------------------
# セキュリティ設定
# -------------------------
@dataclass
class SecurityConfig:
    password_min_length: int = 8
    password_require_upper: bool = True
    password_require_lower: bool = True
    password_require_digit: bool = True
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5


# -------------------------
# システム設定
# -------------------------
@dataclass
class SystemConfig:
    debug_mode: bool = False
    auto_backup: bool = True
    backup_interval_hours: int = 24
    auto_save_interval_minutes: int = 5
    max_records_per_page: int = 50


# -------------------------
# 複数データベース構成管理
# -------------------------
class MultiDatabaseConfig:
    """複数DB構成の管理クラス（フェイルオーバー対応）"""

    def __init__(self, configs: List[DatabaseConfig]):
        self.configs = sorted(configs, key=lambda x: x.priority)
        self.current_index = 0
        self.auto_failover = os.getenv("DB_AUTO_FAILOVER", "true").lower() == "true"
        self.health_check_interval = int(os.getenv("DB_HEALTH_CHECK_INTERVAL", "30"))
        logging.basicConfig(level=logging.INFO)

    def get_current(self) -> DatabaseConfig:
        """現在アクティブなDB設定を取得"""
        return self.configs[self.current_index]

    def get_all(self) -> List[DatabaseConfig]:
        """全てのDB設定を取得"""
        return self.configs

    def get_primary(self) -> Optional[DatabaseConfig]:
        """プライマリDBを取得"""
        for cfg in self.configs:
            if cfg.is_primary:
                return cfg
        return None

    def get_secondary(self) -> List[DatabaseConfig]:
        """セカンダリDB一覧を取得"""
        return [cfg for cfg in self.configs if not cfg.is_primary]

    def failover(self) -> bool:
        """次のDBにフェイルオーバー"""
        if self.current_index < len(self.configs) - 1:
            old_host = self.get_current().host
            self.current_index += 1
            new_host = self.get_current().host
            logging.warning(f"フェイルオーバー: {old_host} -> {new_host} に切り替えました")
            return True
        logging.error("全てのDBが利用不可です")
        return False

    def reset_to_primary(self):
        """プライマリDBに戻す"""
        if self.current_index != 0:
            logging.info(f"プライマリDB ({self.configs[0].host}) に復帰しました")
        self.current_index = 0

    def is_using_primary(self) -> bool:
        """現在プライマリDBを使用しているか"""
        return self.current_index == 0 and self.configs[0].is_primary


# -------------------------
# 設定生成ロジック
# -------------------------
def build_db_config() -> DatabaseConfig:
    if IS_PROD:
        host = os.getenv("PROD_DB_HOST")
        user = os.getenv("PROD_DB_USER")
        password = os.getenv("PROD_DB_PASSWORD")
        database = os.getenv("PROD_DB_NAME", "kubota_prod")
        port = int(os.getenv("PROD_DB_PORT", "3306"))
        if not all([host, user, password]):
            raise RuntimeError("本番環境では PROD_DB_* をすべて設定してください")
        cfg = DatabaseConfig(host=host, user=user, password=password, database=database,
                             port=port, pool_size=20, pool_min_cached=5)
    else:
        # 開発環境：DEV_DB_* を優先、パスワードのみ PRIMARY_DB_PASSWORD を使用
        host = os.getenv("DEV_DB_HOST", "localhost")
        user = os.getenv("DEV_DB_USER", "root")
        password = os.getenv("PRIMARY_DB_PASSWORD") or os.getenv("DEV_DB_PASSWORD", "")
        database = os.getenv("DEV_DB_NAME", "kubota_db")
        port = int(os.getenv("DEV_DB_PORT", "3306"))
        cfg = DatabaseConfig(host=host, user=user, password=password, database=database, port=port)
    return cfg


def ensure_app_dirs(app_cfg: AppConfig) -> None:
    """アプリ用ディレクトリを作成"""
    for d in (app_cfg.data_directory, app_cfg.backup_directory, app_cfg.export_directory):
        os.makedirs(d, exist_ok=True)


def build_multi_db_config() -> Optional[MultiDatabaseConfig]:
    """複数DB構成を構築（環境変数から）"""
    configs = []

    # プライマリDB設定
    primary_host = os.getenv("PRIMARY_DB_HOST")
    if primary_host:
        configs.append(DatabaseConfig(
            host=primary_host,
            user=os.getenv("PRIMARY_DB_USER", "root"),
            password=os.getenv("PRIMARY_DB_PASSWORD", ""),
            database=os.getenv("PRIMARY_DB_NAME", "kubota_main"),
            port=int(os.getenv("PRIMARY_DB_PORT", "3306")),
            is_primary=True,
            priority=1,
            name="primary"
        ))

    # セカンダリDB設定
    secondary_host = os.getenv("SECONDARY_DB_HOST")
    if secondary_host:
        configs.append(DatabaseConfig(
            host=secondary_host,
            user=os.getenv("SECONDARY_DB_USER", "root"),
            password=os.getenv("SECONDARY_DB_PASSWORD", ""),
            database=os.getenv("SECONDARY_DB_NAME", "kubota_backup"),
            port=int(os.getenv("SECONDARY_DB_PORT", "3306")),
            is_primary=False,
            priority=2,
            name="secondary"
        ))

    # 追加のバックアップDB（オプション）
    tertiary_host = os.getenv("TERTIARY_DB_HOST")
    if tertiary_host:
        configs.append(DatabaseConfig(
            host=tertiary_host,
            user=os.getenv("TERTIARY_DB_USER", "root"),
            password=os.getenv("TERTIARY_DB_PASSWORD", ""),
            database=os.getenv("TERTIARY_DB_NAME", "kubota_backup2"),
            port=int(os.getenv("TERTIARY_DB_PORT", "3306")),
            is_primary=False,
            priority=3,
            name="tertiary"
        ))

    if len(configs) == 0:
        return None

    return MultiDatabaseConfig(configs)


# -------------------------
# インスタンス生成
# -------------------------
DB_CONFIG = build_db_config()
APP_CONFIG = AppConfig()
FORMAT_CONFIG = FormatConfig()
SECURITY_CONFIG = SecurityConfig()
SYSTEM_CONFIG = SystemConfig()

# 複数DB構成（オプション）
MULTI_DB_CONFIG = build_multi_db_config()

# 環境依存の調整
if IS_PROD:
    SYSTEM_CONFIG.debug_mode = False
    APP_CONFIG.log_level = "INFO"
    APP_CONFIG.page_title += " - 本番環境"
else:
    SYSTEM_CONFIG.debug_mode = True
    APP_CONFIG.log_level = "DEBUG"
    APP_CONFIG.page_title += " - 開発環境"

# -------------------------
# 互換用エイリアス
# -------------------------
DB_CONFIG_DICT = DB_CONFIG.to_dict()
def get_db_pool_config() -> Dict[str, Any]:
    return DB_CONFIG.to_pool_config()

# formatconfig 互換
formatconfig = FORMAT_CONFIG
FORMAT_CONFIG_DICT = asdict(FORMAT_CONFIG)
