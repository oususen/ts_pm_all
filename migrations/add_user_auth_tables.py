"""
マイグレーション: ユーザー認証・権限管理テーブル追加

users: ユーザー情報
roles: ロール（役職）定義
user_roles: ユーザーとロールの紐付け
page_permissions: ページごとの閲覧権限
tab_permissions: タブごとの閲覧権限
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repository.database_manager import DatabaseManager
from datetime import datetime
import hashlib
from sqlalchemy import text

def hash_password(password: str) -> str:
    """パスワードをハッシュ化"""
    return hashlib.sha256(password.encode()).hexdigest()

def migrate():
    """マイグレーション実行"""
    db = DatabaseManager()
    session = db.get_session()

    try:
        # 1. usersテーブル作成
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                is_active TINYINT(1) DEFAULT 1,
                is_admin TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                INDEX idx_username (username)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        '''))

        # 2. rolesテーブル作成
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                role_name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_role_name (role_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        '''))

        # 3. user_rolesテーブル作成（多対多リレーション）
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS user_roles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                role_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_role (user_id, role_id),
                INDEX idx_user_id (user_id),
                INDEX idx_role_id (role_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        '''))

        # 4. page_permissionsテーブル作成
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS page_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                role_id INT NOT NULL,
                page_name VARCHAR(255) NOT NULL,
                can_view TINYINT(1) DEFAULT 1,
                can_edit TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_role_page (role_id, page_name),
                INDEX idx_role_id (role_id),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        '''))

        # 5. tab_permissionsテーブル作成
        session.execute(text('''
            CREATE TABLE IF NOT EXISTS tab_permissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                role_id INT NOT NULL,
                page_name VARCHAR(255) NOT NULL,
                tab_name VARCHAR(255) NOT NULL,
                can_view TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_role_page_tab (role_id, page_name, tab_name),
                INDEX idx_role_page (role_id, page_name),
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        '''))

        # デフォルトロール作成
        default_roles = [
            ('管理者', '全ての機能にアクセス可能'),
            ('生産管理者', '生産計画・製造工程の管理'),
            ('配送管理者', '配送便計画・納入進度の管理'),
            ('閲覧者', '全画面の閲覧のみ可能')
        ]

        for role_name, description in default_roles:
            session.execute(text('''
                INSERT IGNORE INTO roles (role_name, description)
                VALUES (:role_name, :description)
            '''), {'role_name': role_name, 'description': description})

        # デフォルト管理者ユーザー作成（username: admin, password: admin123）
        admin_password = hash_password('admin123')
        session.execute(text('''
            INSERT IGNORE INTO users (username, password_hash, full_name, is_admin)
            VALUES (:username, :password_hash, :full_name, :is_admin)
        '''), {'username': 'admin', 'password_hash': admin_password, 'full_name': '管理者', 'is_admin': 1})

        # 管理者ロールを管理者ユーザーに割り当て
        session.execute(text('''
            INSERT IGNORE INTO user_roles (user_id, role_id)
            SELECT u.id, r.id
            FROM users u, roles r
            WHERE u.username = 'admin' AND r.role_name = '管理者'
        '''))

        # デフォルトページ権限設定
        pages = [
            'ダッシュボード',
            'CSV受注取込',
            '製品管理',
            '制限設定',
            '生産計画',
            '配送便計画',
            '納入進度',
            '📅 会社カレンダー',
            'ユーザー管理'
        ]

        # 管理者: 全ページ閲覧・編集可能
        for page in pages:
            session.execute(text('''
                INSERT IGNORE INTO page_permissions (role_id, page_name, can_view, can_edit)
                SELECT id, :page_name, 1, 1 FROM roles WHERE role_name = '管理者'
            '''), {'page_name': page})

        # 生産管理者: 生産関連ページのみ
        production_pages = ['ダッシュボード', '製品管理', '生産計画', '制限設定']
        for page in production_pages:
            session.execute(text('''
                INSERT IGNORE INTO page_permissions (role_id, page_name, can_view, can_edit)
                SELECT id, :page_name, 1, 1 FROM roles WHERE role_name = '生産管理者'
            '''), {'page_name': page})

        # 配送管理者: 配送関連ページのみ
        transport_pages = ['ダッシュボード', '配送便計画', '納入進度', '📅 会社カレンダー']
        for page in transport_pages:
            session.execute(text('''
                INSERT IGNORE INTO page_permissions (role_id, page_name, can_view, can_edit)
                SELECT id, :page_name, 1, 1 FROM roles WHERE role_name = '配送管理者'
            '''), {'page_name': page})

        # 閲覧者: 全ページ閲覧のみ
        for page in pages:
            if page != 'ユーザー管理':  # ユーザー管理は閲覧不可
                session.execute(text('''
                    INSERT IGNORE INTO page_permissions (role_id, page_name, can_view, can_edit)
                    SELECT id, :page_name, 1, 0 FROM roles WHERE role_name = '閲覧者'
                '''), {'page_name': page})

        # タブ権限のデフォルト設定（生産計画画面の例）
        production_tabs = [
            ('生産計画', '📊 計画シミュレーション'),
            ('生産計画', '📝 生産計画管理'),
            ('生産計画', '🔧 製造工程（加工対象）')
        ]

        for page_name, tab_name in production_tabs:
            # 管理者と生産管理者は全タブ閲覧可能
            for role in ['管理者', '生産管理者']:
                session.execute(text('''
                    INSERT IGNORE INTO tab_permissions (role_id, page_name, tab_name, can_view)
                    SELECT id, :page_name, :tab_name, 1 FROM roles WHERE role_name = :role_name
                '''), {'page_name': page_name, 'tab_name': tab_name, 'role_name': role})

        session.commit()
        print("✅ ユーザー認証・権限管理テーブルを作成しました")
        print("✅ デフォルト管理者ユーザー: admin / admin123")

    except Exception as e:
        session.rollback()
        print(f"❌ マイグレーションエラー: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        session.close()

def rollback():
    """ロールバック"""
    db = DatabaseManager()
    session = db.get_session()

    try:
        # 外部キー制約を一時的に無効化
        session.execute(text('SET FOREIGN_KEY_CHECKS = 0'))

        session.execute(text('DROP TABLE IF EXISTS tab_permissions'))
        session.execute(text('DROP TABLE IF EXISTS page_permissions'))
        session.execute(text('DROP TABLE IF EXISTS user_roles'))
        session.execute(text('DROP TABLE IF EXISTS roles'))
        session.execute(text('DROP TABLE IF EXISTS users'))

        # 外部キー制約を再度有効化
        session.execute(text('SET FOREIGN_KEY_CHECKS = 1'))

        session.commit()
        print("✅ ユーザー認証・権限管理テーブルを削除しました")

    except Exception as e:
        session.rollback()
        print(f"❌ ロールバックエラー: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        session.close()

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback()
    else:
        migrate()
