"""
タブ権限テーブルにcan_editカラムを追加するマイグレーション
"""
import sys
import os

# Windows環境でUTF-8出力を有効にする
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repository.database_manager import DatabaseManager
from sqlalchemy import text

def migrate():
    """マイグレーション実行"""
    db = DatabaseManager()
    session = db.get_session()

    try:
        print("=" * 60)
        print("マイグレーション開始: tab_permissionsにcan_editカラム追加")
        print("=" * 60)

        # 1. can_editカラムを追加
        print("\n1. can_editカラムを追加中...")
        session.execute(text("""
            ALTER TABLE tab_permissions
            ADD COLUMN can_edit TINYINT(1) NOT NULL DEFAULT 0
        """))
        print("✓ can_editカラムを追加しました")

        # 2. 既存データのcan_editをcan_viewと同じ値に設定（デフォルト動作）
        print("\n2. 既存データのcan_editをcan_viewと同じ値に設定中...")
        session.execute(text("""
            UPDATE tab_permissions
            SET can_edit = can_view
        """))
        print("✓ 既存データを更新しました")

        session.commit()
        print("\n" + "=" * 60)
        print("マイグレーション完了！")
        print("=" * 60)

    except Exception as e:
        session.rollback()
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
