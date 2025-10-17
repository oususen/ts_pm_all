# app/repository/database_manager.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config import DB_CONFIG
import pandas as pd

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
   
    