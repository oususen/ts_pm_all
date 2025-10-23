# app/services/auth_service.py
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import text
import pandas as pd
import logging

# ロガー設定
logger = logging.getLogger(__name__)

class AuthService:
    """認証・権限管理サービス"""

    def __init__(self, db_manager):
        self.db = db_manager

    @staticmethod
    def hash_password(password: str) -> str:
        """パスワードをハッシュ化"""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """ユーザー認証"""
        session = self.db.get_session()

        try:
            password_hash = self.hash_password(password)

            query = text("""
                SELECT id, username, full_name, email, is_active, is_admin
                FROM users
                WHERE username = :username AND password_hash = :password_hash
            """)

            result = session.execute(query, {
                'username': username,
                'password_hash': password_hash
            }).fetchone()

            if result:
                if not result[4]:  # is_active check
                    return None

                # 最終ログイン時刻を更新
                update_query = text("""
                    UPDATE users
                    SET last_login = :now
                    WHERE id = :user_id
                """)
                session.execute(update_query, {
                    'now': datetime.now(),
                    'user_id': result[0]
                })
                session.commit()

                return {
                    'id': result[0],
                    'username': result[1],
                    'full_name': result[2],
                    'email': result[3],
                    'is_active': result[4],
                    'is_admin': result[5]
                }

            return None

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_user_roles(self, user_id: int) -> List[str]:
        """ユーザーのロール一覧を取得"""
        session = self.db.get_session()

        try:
            query = text("""
                SELECT r.role_name
                FROM roles r
                JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = :user_id
            """)

            result = session.execute(query, {'user_id': user_id}).fetchall()
            return [row[0] for row in result]

        finally:
            session.close()

    def get_user_pages(self, user_id: int) -> List[Dict[str, Any]]:
        """ユーザーがアクセスできるページ一覧を取得"""
        session = self.db.get_session()

        try:
            # 管理者は全ページアクセス可能
            is_admin_query = text("""
                SELECT is_admin FROM users WHERE id = :user_id
            """)
            is_admin = session.execute(is_admin_query, {'user_id': user_id}).scalar()

            if is_admin:
                # 全ページ返す
                return [
                    {'page_name': 'ダッシュボード', 'can_view': True, 'can_edit': True},
                    {'page_name': 'CSV受注取込', 'can_view': True, 'can_edit': True},
                    {'page_name': '製品管理', 'can_view': True, 'can_edit': True},
                    {'page_name': '製品群管理', 'can_view': True, 'can_edit': True},
                    {'page_name': '制限設定', 'can_view': True, 'can_edit': True},
                    {'page_name': '生産計画', 'can_view': True, 'can_edit': True},
                    {'page_name': '配送便計画', 'can_view': True, 'can_edit': True},
                    {'page_name': '納入進度', 'can_view': True, 'can_edit': True},
                    {'page_name': '📅 会社カレンダー', 'can_view': True, 'can_edit': True},
                    {'page_name': 'ユーザー管理', 'can_view': True, 'can_edit': True}
                ]

            query = text("""
                SELECT DISTINCT pp.page_name, pp.can_view, pp.can_edit
                FROM page_permissions pp
                JOIN user_roles ur ON pp.role_id = ur.role_id
                WHERE ur.user_id = :user_id AND pp.can_view = 1
            """)

            result = session.execute(query, {'user_id': user_id}).fetchall()

            pages = []
            for row in result:
                pages.append({
                    'page_name': row[0],
                    'can_view': bool(row[1]),
                    'can_edit': bool(row[2])
                })

            return pages

        finally:
            session.close()

    def get_user_tabs(self, user_id: int, page_name: str) -> List[str]:
        """ユーザーが特定のページで閲覧できるタブ一覧を取得"""
        session = self.db.get_session()

        try:
            # 管理者は全タブアクセス可能
            is_admin_query = text("""
                SELECT is_admin FROM users WHERE id = :user_id
            """)
            is_admin = session.execute(is_admin_query, {'user_id': user_id}).scalar()

            if is_admin:
                return []  # 空リストは全タブアクセス可能を意味する

            query = text("""
                SELECT DISTINCT tp.tab_name
                FROM tab_permissions tp
                JOIN user_roles ur ON tp.role_id = ur.role_id
                WHERE ur.user_id = :user_id
                  AND tp.page_name = :page_name
                  AND tp.can_view = 1
            """)

            result = session.execute(query, {
                'user_id': user_id,
                'page_name': page_name
            }).fetchall()

            return [row[0] for row in result]

        finally:
            session.close()

    def can_access_page(self, user_id: int, page_name: str) -> bool:
        """ページアクセス権限チェック"""
        pages = self.get_user_pages(user_id)
        return any(p['page_name'] == page_name and p['can_view'] for p in pages)

    def can_edit_page(self, user_id: int, page_name: str) -> bool:
        """ページ編集権限チェック"""
        pages = self.get_user_pages(user_id)
        return any(p['page_name'] == page_name and p['can_edit'] for p in pages)

    def can_access_tab(self, user_id: int, page_name: str, tab_name: str) -> bool:
        """タブアクセス権限チェック"""
        tabs = self.get_user_tabs(user_id, page_name)
        # 空リスト（管理者）または指定タブが含まれている場合はTrue
        return len(tabs) == 0 or tab_name in tabs

    def can_edit_tab(self, user_id: int, page_name: str, tab_name: str) -> bool:
        """タブ編集権限チェック"""
        session = self.db.get_session()

        try:
            # 管理者は全タブ編集可能
            is_admin_query = text("""
                SELECT is_admin FROM users WHERE id = :user_id
            """)
            is_admin = session.execute(is_admin_query, {'user_id': user_id}).scalar()

            if is_admin:
                return True

            # タブ編集権限をチェック
            query = text("""
                SELECT tp.can_edit
                FROM tab_permissions tp
                JOIN user_roles ur ON tp.role_id = ur.role_id
                WHERE ur.user_id = :user_id
                  AND tp.page_name = :page_name
                  AND tp.tab_name = :tab_name
                  AND tp.can_edit = 1
                LIMIT 1
            """)

            result = session.execute(query, {
                'user_id': user_id,
                'page_name': page_name,
                'tab_name': tab_name
            }).scalar()

            return bool(result)

        finally:
            session.close()

    # ユーザー管理機能
    def create_user(self, username: str, password: str, full_name: str,
                    email: str = None, is_admin: bool = False) -> int:
        """ユーザー作成"""
        session = self.db.get_session()

        try:
            password_hash = self.hash_password(password)

            query = text("""
                INSERT INTO users (username, password_hash, full_name, email, is_admin)
                VALUES (:username, :password_hash, :full_name, :email, :is_admin)
            """)

            result = session.execute(query, {
                'username': username,
                'password_hash': password_hash,
                'full_name': full_name,
                'email': email,
                'is_admin': is_admin
            })

            session.commit()
            return result.lastrowid

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_all_users(self) -> pd.DataFrame:
        """全ユーザー取得"""
        session = self.db.get_session()

        try:
            query = text("""
                SELECT id, username, full_name, email, is_active, is_admin,
                       created_at, last_login
                FROM users
                ORDER BY id
            """)

            result = session.execute(query).fetchall()

            if result:
                df = pd.DataFrame(result, columns=[
                    'id', 'username', 'full_name', 'email',
                    'is_active', 'is_admin', 'created_at', 'last_login'
                ])
                return df
            else:
                return pd.DataFrame()

        finally:
            session.close()

    def update_user(self, user_id: int, update_data: Dict[str, Any]) -> bool:
        """ユーザー情報更新"""
        session = self.db.get_session()

        try:
            # パスワード変更の場合はハッシュ化
            if 'password' in update_data:
                update_data['password_hash'] = self.hash_password(update_data['password'])
                del update_data['password']

            # 動的にUPDATE文を構築
            set_clause = ', '.join([f"{key} = :{key}" for key in update_data.keys()])
            update_data['user_id'] = user_id
            update_data['updated_at'] = datetime.now()

            query = text(f"""
                UPDATE users
                SET {set_clause}, updated_at = :updated_at
                WHERE id = :user_id
            """)

            session.execute(query, update_data)
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def delete_user(self, user_id: int) -> bool:
        """ユーザー削除"""
        session = self.db.get_session()

        try:
            query = text("DELETE FROM users WHERE id = :user_id")
            session.execute(query, {'user_id': user_id})
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def assign_role(self, user_id: int, role_id: int) -> bool:
        """ユーザーにロールを割り当て"""
        session = self.db.get_session()

        try:
            query = text("""
                INSERT IGNORE INTO user_roles (user_id, role_id)
                VALUES (:user_id, :role_id)
            """)

            session.execute(query, {
                'user_id': user_id,
                'role_id': role_id
            })
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def remove_role(self, user_id: int, role_id: int) -> bool:
        """ユーザーからロールを削除"""
        session = self.db.get_session()

        try:
            query = text("""
                DELETE FROM user_roles
                WHERE user_id = :user_id AND role_id = :role_id
            """)

            session.execute(query, {
                'user_id': user_id,
                'role_id': role_id
            })
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_all_roles(self) -> pd.DataFrame:
        """全ロール取得"""
        session = self.db.get_session()

        try:
            query = text("""
                SELECT id, role_name, description
                FROM roles
                ORDER BY id
            """)

            result = session.execute(query).fetchall()

            if result:
                return pd.DataFrame(result, columns=['id', 'role_name', 'description'])
            else:
                return pd.DataFrame()

        finally:
            session.close()

    # ページ権限管理
    def get_page_permissions(self, role_id: int) -> pd.DataFrame:
        """ロールのページ権限を取得"""
        session = self.db.get_session()

        try:
            query = text("""
                SELECT page_name, can_view, can_edit
                FROM page_permissions
                WHERE role_id = :role_id
                ORDER BY page_name
            """)

            result = session.execute(query, {'role_id': role_id}).fetchall()

            if result:
                return pd.DataFrame(result, columns=['page_name', 'can_view', 'can_edit'])
            else:
                return pd.DataFrame()

        finally:
            session.close()

    def set_page_permission(self, role_id: int, page_name: str, can_view: bool, can_edit: bool) -> bool:
        """ページ権限を設定"""
        session = self.db.get_session()

        try:
            logger.info(f"[set_page_permission] role_id={role_id}, page_name={page_name}, can_view={can_view}, can_edit={can_edit}")

            # 既存の権限を削除してから挿入
            delete_query = text("""
                DELETE FROM page_permissions
                WHERE role_id = :role_id AND page_name = :page_name
            """)
            result = session.execute(delete_query, {'role_id': role_id, 'page_name': page_name})
            logger.debug(f"[set_page_permission] 削除件数: {result.rowcount}")

            # 新しい権限を挿入
            insert_query = text("""
                INSERT INTO page_permissions (role_id, page_name, can_view, can_edit)
                VALUES (:role_id, :page_name, :can_view, :can_edit)
            """)
            can_view_int = 1 if can_view else 0
            can_edit_int = 1 if can_edit else 0
            logger.debug(f"[set_page_permission] INSERT VALUES: role_id={role_id}, page_name={page_name}, can_view={can_view_int}, can_edit={can_edit_int}")

            result = session.execute(insert_query, {
                'role_id': role_id,
                'page_name': page_name,
                'can_view': can_view_int,
                'can_edit': can_edit_int
            })
            logger.debug(f"[set_page_permission] 挿入件数: {result.rowcount}")

            session.commit()
            logger.info(f"[set_page_permission] コミット成功")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"[set_page_permission] エラー: {e}")
            raise e
        finally:
            session.close()

    def delete_page_permission(self, role_id: int, page_name: str) -> bool:
        """ページ権限を削除"""
        session = self.db.get_session()

        try:
            logger.debug(f"[delete_page_permission] role_id={role_id}, page_name={page_name}")
            query = text("""
                DELETE FROM page_permissions
                WHERE role_id = :role_id AND page_name = :page_name
            """)
            result = session.execute(query, {'role_id': role_id, 'page_name': page_name})
            logger.debug(f"[delete_page_permission] 削除件数: {result.rowcount}")
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"[delete_page_permission] エラー: {e}")
            raise e
        finally:
            session.close()

    # タブ権限管理
    def get_tab_permissions(self, role_id: int, page_name: str = None) -> pd.DataFrame:
        """ロールのタブ権限を取得"""
        session = self.db.get_session()

        try:
            if page_name:
                query = text("""
                    SELECT page_name, tab_name, can_view, can_edit
                    FROM tab_permissions
                    WHERE role_id = :role_id AND page_name = :page_name
                    ORDER BY page_name, tab_name
                """)
                result = session.execute(query, {'role_id': role_id, 'page_name': page_name}).fetchall()
            else:
                query = text("""
                    SELECT page_name, tab_name, can_view, can_edit
                    FROM tab_permissions
                    WHERE role_id = :role_id
                    ORDER BY page_name, tab_name
                """)
                result = session.execute(query, {'role_id': role_id}).fetchall()

            if result:
                return pd.DataFrame(result, columns=['page_name', 'tab_name', 'can_view', 'can_edit'])
            else:
                return pd.DataFrame()

        finally:
            session.close()

    def set_tab_permission(self, role_id: int, page_name: str, tab_name: str, can_view: bool, can_edit: bool = False) -> bool:
        """タブ権限を設定"""
        session = self.db.get_session()

        try:
            logger.info(f"[set_tab_permission] role_id={role_id}, page_name={page_name}, tab_name={tab_name}, can_view={can_view}, can_edit={can_edit}")

            # 既存の権限を削除してから挿入
            delete_query = text("""
                DELETE FROM tab_permissions
                WHERE role_id = :role_id AND page_name = :page_name AND tab_name = :tab_name
            """)
            result = session.execute(delete_query, {
                'role_id': role_id,
                'page_name': page_name,
                'tab_name': tab_name
            })
            logger.debug(f"[set_tab_permission] 削除件数: {result.rowcount}")

            # 新しい権限を挿入
            insert_query = text("""
                INSERT INTO tab_permissions (role_id, page_name, tab_name, can_view, can_edit)
                VALUES (:role_id, :page_name, :tab_name, :can_view, :can_edit)
            """)
            can_view_int = 1 if can_view else 0
            can_edit_int = 1 if can_edit else 0
            logger.debug(f"[set_tab_permission] INSERT VALUES: role_id={role_id}, page_name={page_name}, tab_name={tab_name}, can_view={can_view_int}, can_edit={can_edit_int}")

            result = session.execute(insert_query, {
                'role_id': role_id,
                'page_name': page_name,
                'tab_name': tab_name,
                'can_view': can_view_int,
                'can_edit': can_edit_int
            })
            logger.debug(f"[set_tab_permission] 挿入件数: {result.rowcount}")

            session.commit()
            logger.info(f"[set_tab_permission] コミット成功")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"[set_tab_permission] エラー: {e}")
            raise e
        finally:
            session.close()

    def delete_tab_permission(self, role_id: int, page_name: str, tab_name: str) -> bool:
        """タブ権限を削除"""
        session = self.db.get_session()

        try:
            logger.debug(f"[delete_tab_permission] role_id={role_id}, page_name={page_name}, tab_name={tab_name}")
            query = text("""
                DELETE FROM tab_permissions
                WHERE role_id = :role_id AND page_name = :page_name AND tab_name = :tab_name
            """)
            result = session.execute(query, {
                'role_id': role_id,
                'page_name': page_name,
                'tab_name': tab_name
            })
            logger.debug(f"[delete_tab_permission] 削除件数: {result.rowcount}")
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"[delete_tab_permission] エラー: {e}")
            raise e
        finally:
            session.close()
