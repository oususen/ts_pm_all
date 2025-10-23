# app/repository/database_manager.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config_all import DB_CONFIG, build_customer_db_config, get_default_customer, DatabaseConfig
import pandas as pd
from typing import Optional

class DatabaseManager:
    """SQLAlchemy を使ったデータベース接続管理"""

    def __init__(self):
        # DB_CONFIG から接続情報を取得
        user = DB_CONFIG.user
        password = DB_CONFIG.password
        host = DB_CONFIG.host
        port = DB_CONFIG.port
        dbname = DB_CONFIG.database

        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"
        self.engine = create_engine(db_url, echo=False, future=True)

        # セッションファクトリ（scoped_sessionでスレッドセーフ）
        self.SessionLocal = scoped_session(sessionmaker(bind=self.engine, autocommit=False, autoflush=False))

    def get_session(self):
        """新しいセッションを取得"""
        return self.SessionLocal()

    def close(self):
        """セッションと接続を閉じる"""
        self.SessionLocal.remove()
        self.engine.dispose()
# repository/database_manager.py の execute_query メソッド修正

    def execute_query(self, query: str, params=None):
        """クエリ実行 - 修正版"""
        try:
            with self.Session() as session:
                print(f"🔍 デバッグ: クエリ実行: {query[:100]}...")
                print(f"🔍 デバッグ: パラメータ: {params}")
                
                if params:
                    # ✅ 辞書形式のパラメータを使用
                    result = session.execute(text(query), params)
                else:
                    # ✅ パラメータなし
                    result = session.execute(text(query))
                
                # ✅ 結果を辞書のリストで返す
                rows = [dict(row._mapping) for row in result]
                print(f"🔍 デバッグ: 取得行数: {len(rows)}")
                return rows
                
        except Exception as e:
            print(f"❌ クエリ実行エラー: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            return []    
    def execute_query(self, query, params=None):
        """
        SELECTクエリを実行してDataFrameを返す
        
        Args:
            query: SQL文字列
            params: パラメータ（辞書、リスト、またはタプル）
        
        Returns:
            pd.DataFrame: 結果のDataFrame
        """
        session = self.get_session()
        
        try:
            if params:
                # パラメータをそのまま渡す（辞書、リスト、タプルどれでもOK）
                if isinstance(params, (list, tuple)):
                    # リスト/タプルの場合はそのまま
                    result = session.execute(text(query), params)
                else:
                    # 辞書の場合もそのまま
                    result = session.execute(text(query), params)
            else:
                result = session.execute(text(query))
            
            # 結果をDataFrameに変換
            rows = result.fetchall()
            
            if rows:
                columns = result.keys()
                df = pd.DataFrame(rows, columns=columns)
            else:
                df = pd.DataFrame()
            
            return df
            
        except Exception as e:
            print(f"クエリ実行エラー: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
        finally:
            session.close()

#ここ以下は削除　いまはテスト用
    def execute_non_query(self, query: str, params=None):
        """INSERT/UPDATE/DELETEクエリを実行"""
        session = self.get_session()
        try:
            if params:
                session.execute(text(query), params)
            else:
                session.execute(text(query))
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"❌ クエリ実行エラー: {e}")
            print(f"Query: {query}")
            print(f"Params: {params}")
        finally:
            session.close()


class CustomerDatabaseManager:
    """
    顧客別データベース接続管理クラス

    複数の顧客（kubota, tiera）のデータベースを管理し、
    顧客を切り替えてクエリを実行できます。

    使用例:
        # デフォルト顧客で初期化
        db = CustomerDatabaseManager()

        # 久保田様のデータ取得
        df_kubota = db.execute_query("SELECT * FROM products", customer="kubota")

        # ティエラ様のデータ取得
        df_tiera = db.execute_query("SELECT * FROM products", customer="tiera")

        # 顧客を切り替え
        db.switch_customer("tiera")
        df = db.execute_query("SELECT * FROM orders")
    """

    def __init__(self, customer: Optional[str] = None):
        """
        初期化

        Args:
            customer: 顧客名 ('kubota' または 'tiera')。未指定の場合はDEFAULT_CUSTOMERを使用
        """
        self._managers = {}  # 顧客名 -> DatabaseManagerインスタンス
        self._current_customer = customer or get_default_customer()

        # 現在の顧客用のマネージャーを初期化
        self._get_or_create_manager(self._current_customer)

    def _create_manager_from_config(self, db_config: DatabaseConfig) -> 'DatabaseManager':
        """
        DatabaseConfigから新しいDatabaseManagerを作成

        Args:
            db_config: データベース設定

        Returns:
            DatabaseManager: 新しいマネージャーインスタンス
        """
        # 一時的にグローバルのDB_CONFIGを置き換える代わりに、
        # 直接エンジンを作成する
        class TempManager:
            def __init__(self, config):
                user = config.user
                password = config.password
                host = config.host
                port = config.port
                dbname = config.database

                db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"
                self.engine = create_engine(db_url, echo=False, future=True)
                self.SessionLocal = scoped_session(sessionmaker(bind=self.engine, autocommit=False, autoflush=False))

            def get_session(self):
                return self.SessionLocal()

            def close(self):
                self.SessionLocal.remove()
                self.engine.dispose()

            def execute_query(self, query, params=None):
                """SELECTクエリを実行してDataFrameを返す"""
                session = self.get_session()
                try:
                    if params:
                        if isinstance(params, (list, tuple)):
                            result = session.execute(text(query), params)
                        else:
                            result = session.execute(text(query), params)
                    else:
                        result = session.execute(text(query))

                    rows = result.fetchall()
                    if rows:
                        columns = result.keys()
                        df = pd.DataFrame(rows, columns=columns)
                    else:
                        df = pd.DataFrame()
                    return df
                except Exception as e:
                    print(f"クエリ実行エラー: {e}")
                    print(f"Query: {query}")
                    print(f"Params: {params}")
                    import traceback
                    traceback.print_exc()
                    return pd.DataFrame()
                finally:
                    session.close()

            def execute_non_query(self, query: str, params=None):
                """INSERT/UPDATE/DELETEクエリを実行"""
                session = self.get_session()
                try:
                    if params:
                        session.execute(text(query), params)
                    else:
                        session.execute(text(query))
                    session.commit()
                except Exception as e:
                    session.rollback()
                    print(f"❌ クエリ実行エラー: {e}")
                    print(f"Query: {query}")
                    print(f"Params: {params}")
                finally:
                    session.close()

        return TempManager(db_config)

    def _get_or_create_manager(self, customer: str) -> 'DatabaseManager':
        """
        顧客用のDatabaseManagerを取得または作成

        Args:
            customer: 顧客名

        Returns:
            DatabaseManager: 顧客用のマネージャー
        """
        if customer not in self._managers:
            config = build_customer_db_config(customer)
            self._managers[customer] = self._create_manager_from_config(config)
            print(f"✅ {customer.upper()}用データベース接続を確立: {config.database}")

        return self._managers[customer]

    def switch_customer(self, customer: str):
        """
        現在の顧客を切り替え

        Args:
            customer: 顧客名 ('kubota' または 'tiera')
        """
        customer = customer.lower()
        if customer not in ["kubota", "tiera"]:
            raise ValueError(f"未対応の顧客名: {customer}")

        self._current_customer = customer
        # 必要に応じてマネージャーを作成
        self._get_or_create_manager(customer)
        print(f"🔄 顧客を切り替えました: {customer.upper()}")

    def get_current_customer(self) -> str:
        """現在の顧客名を取得"""
        return self._current_customer

    def get_session(self):
        """
        現在の顧客用のセッションを取得

        既存のサービスクラス（auth_service等）との互換性のため

        Returns:
            セッションオブジェクト
        """
        manager = self._get_or_create_manager(self._current_customer)
        return manager.get_session()

    def execute_query(self, query: str, params=None, customer: Optional[str] = None):
        """
        SELECTクエリを実行してDataFrameを返す

        Args:
            query: SQL文字列
            params: パラメータ（辞書、リスト、またはタプル）
            customer: 顧客名（未指定の場合は現在の顧客）

        Returns:
            pd.DataFrame: 結果のDataFrame
        """
        target_customer = customer or self._current_customer
        manager = self._get_or_create_manager(target_customer)
        return manager.execute_query(query, params)

    def execute_non_query(self, query: str, params=None, customer: Optional[str] = None):
        """
        INSERT/UPDATE/DELETEクエリを実行

        Args:
            query: SQL文字列
            params: パラメータ（辞書、リスト、またはタプル）
            customer: 顧客名（未指定の場合は現在の顧客）
        """
        target_customer = customer or self._current_customer
        manager = self._get_or_create_manager(target_customer)
        return manager.execute_non_query(query, params)

    def close(self, customer: Optional[str] = None):
        """
        データベース接続を閉じる

        Args:
            customer: 顧客名（未指定の場合は全ての接続を閉じる）
        """
        if customer:
            if customer in self._managers:
                self._managers[customer].close()
                del self._managers[customer]
                print(f"🔒 {customer.upper()}のデータベース接続を閉じました")
        else:
            # 全ての接続を閉じる
            for cust, manager in self._managers.items():
                manager.close()
                print(f"🔒 {cust.upper()}のデータベース接続を閉じました")
            self._managers.clear()

    def __enter__(self):
        """コンテキストマネージャー対応"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー対応 - 終了時に全接続を閉じる"""
        self.close()

