# app/repository/calendar_repository.py
from sqlalchemy import text
from datetime import date, timedelta
from typing import List, Dict, Optional
import pandas as pd

class CalendarRepository:
    """会社カレンダーリポジトリ"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def is_working_day(self, target_date: date) -> bool:
        """指定日が営業日かチェック"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT is_working_day 
                FROM company_calendar 
                WHERE calendar_date = :target_date
            """)
            
            result = session.execute(query, {'target_date': target_date}).fetchone()
            
            if result:
                return bool(result[0])
            
            # カレンダーに未登録の場合は土日をチェック
            weekday = target_date.weekday()
            return weekday not in [5, 6]  # 土日以外は営業日とみなす
        
        finally:
            session.close()
    
    def get_next_working_day(self, target_date: date, skip_days: int = 1) -> date:
        """次の営業日を取得"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT calendar_date 
                FROM company_calendar 
                WHERE calendar_date > :target_date 
                  AND is_working_day = TRUE
                ORDER BY calendar_date
                LIMIT :skip_days
            """)
            
            result = session.execute(query, {
                'target_date': target_date,
                'skip_days': skip_days
            }).fetchall()
            
            if result and len(result) >= skip_days:
                return result[skip_days - 1][0]
            
            # フォールバック: カレンダー未登録の場合
            current = target_date + timedelta(days=1)
            found_days = 0
            
            while found_days < skip_days:
                if self.is_working_day(current):
                    found_days += 1
                    if found_days == skip_days:
                        return current
                current += timedelta(days=1)
            
            return current
        
        finally:
            session.close()
    
    def get_working_days_between(self, start_date: date, end_date: date) -> List[date]:
        """期間内の営業日リストを取得"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT calendar_date 
                FROM company_calendar 
                WHERE calendar_date BETWEEN :start_date AND :end_date
                  AND is_working_day = TRUE
                ORDER BY calendar_date
            """)
            
            result = session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()
            
            return [row[0] for row in result]
        
        finally:
            session.close()
    
    def get_calendar_range(self, start_date: date, end_date: date) -> pd.DataFrame:
        """期間のカレンダー情報を取得"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT 
                    calendar_date,
                    day_type,
                    day_name,
                    is_working_day,
                    notes
                FROM company_calendar 
                WHERE calendar_date BETWEEN :start_date AND :end_date
                ORDER BY calendar_date
            """)
            
            result = session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            })
            
            rows = result.fetchall()
            if rows:
                return pd.DataFrame(rows, columns=result.keys())
            else:
                return pd.DataFrame()
        
        finally:
            session.close()
    
    def add_holiday(self, target_date: date, day_type: str, day_name: str = None, notes: str = None) -> bool:
        """休日を追加"""
        session = self.db.get_session()
        try:
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, day_name, is_working_day, notes)
                VALUES (:date, :day_type, :day_name, FALSE, :notes)
                ON DUPLICATE KEY UPDATE
                    day_type = VALUES(day_type),
                    day_name = VALUES(day_name),
                    is_working_day = FALSE,
                    notes = VALUES(notes)
            """)
            
            session.execute(query, {
                'date': target_date,
                'day_type': day_type,
                'day_name': day_name,
                'notes': notes
            })
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"休日追加エラー: {e}")
            return False
        finally:
            session.close()
    
    def add_working_day(self, target_date: date, notes: str = None) -> bool:
        """営業日を追加（休日の振替など）"""
        session = self.db.get_session()
        try:
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, is_working_day, notes)
                VALUES (:date, '営業日', TRUE, :notes)
                ON DUPLICATE KEY UPDATE
                    day_type = '営業日',
                    is_working_day = TRUE,
                    notes = VALUES(notes)
            """)
            
            session.execute(query, {
                'date': target_date,
                'notes': notes
            })
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"営業日追加エラー: {e}")
            return False
        finally:
            session.close()
    
    def delete_calendar_date(self, target_date: date) -> bool:
        """カレンダーから日付を削除"""
        session = self.db.get_session()
        try:
            query = text("""
                DELETE FROM company_calendar 
                WHERE calendar_date = :date
            """)
            
            session.execute(query, {'date': target_date})
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"日付削除エラー: {e}")
            return False
        finally:
            session.close()
    
    def bulk_import_holidays(self, holidays: List[Dict]) -> int:
        """休日を一括インポート"""
        session = self.db.get_session()
        imported_count = 0
        
        try:
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, day_name, is_working_day, notes)
                VALUES (:date, :day_type, :day_name, FALSE, :notes)
                ON DUPLICATE KEY UPDATE
                    day_type = VALUES(day_type),
                    day_name = VALUES(day_name),
                    is_working_day = FALSE
            """)
            
            for holiday in holidays:
                session.execute(query, {
                    'date': holiday['date'],
                    'day_type': holiday.get('day_type', '祝日'),
                    'day_name': holiday.get('day_name'),
                    'notes': holiday.get('notes')
                })
                imported_count += 1
            
            session.commit()
            return imported_count
        
        except Exception as e:
            session.rollback()
            print(f"一括インポートエラー: {e}")
            return 0
        finally:
            session.close()

    """会社カレンダーリポジトリ"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def is_working_day(self, target_date: date) -> bool:
        """指定日が営業日かチェック"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT is_working_day 
                FROM company_calendar 
                WHERE calendar_date = :target_date
            """)
            
            result = session.execute(query, {'target_date': target_date}).fetchone()
            
            if result:
                return bool(result[0])
            
            # カレンダーに未登録の場合は土日をチェック
            weekday = target_date.weekday()
            return weekday not in [5, 6]  # 土日以外は営業日とみなす
        
        finally:
            session.close()
    
    def get_next_working_day(self, target_date: date, skip_days: int = 1) -> date:
        """次の営業日を取得"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT calendar_date 
                FROM company_calendar 
                WHERE calendar_date > :target_date 
                  AND is_working_day = TRUE
                ORDER BY calendar_date
                LIMIT :skip_days
            """)
            
            result = session.execute(query, {
                'target_date': target_date,
                'skip_days': skip_days
            }).fetchall()
            
            if result and len(result) >= skip_days:
                return result[skip_days - 1][0]
            
            # フォールバック: カレンダー未登録の場合
            current = target_date + timedelta(days=1)
            found_days = 0
            
            while found_days < skip_days:
                if self.is_working_day(current):
                    found_days += 1
                    if found_days == skip_days:
                        return current
                current += timedelta(days=1)
            
            return current
        
        finally:
            session.close()
    
    def get_working_days_between(self, start_date: date, end_date: date) -> List[date]:
        """期間内の営業日リストを取得"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT calendar_date 
                FROM company_calendar 
                WHERE calendar_date BETWEEN :start_date AND :end_date
                  AND is_working_day = TRUE
                ORDER BY calendar_date
            """)
            
            result = session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            }).fetchall()
            
            return [row[0] for row in result]
        
        finally:
            session.close()
    
    def get_calendar_range(self, start_date: date, end_date: date) -> pd.DataFrame:
        """期間のカレンダー情報を取得"""
        session = self.db.get_session()
        try:
            query = text("""
                SELECT 
                    calendar_date,
                    day_type,
                    day_name,
                    is_working_day,
                    notes
                FROM company_calendar 
                WHERE calendar_date BETWEEN :start_date AND :end_date
                ORDER BY calendar_date
            """)
            
            result = session.execute(query, {
                'start_date': start_date,
                'end_date': end_date
            })
            
            return pd.DataFrame(result.fetchall(), columns=result.keys())
        
        finally:
            session.close()
    
    def add_holiday(self, target_date: date, day_type: str, day_name: str = None, notes: str = None) -> bool:
        """休日を追加"""
        session = self.db.get_session()
        try:
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, day_name, is_working_day, notes)
                VALUES (:date, :day_type, :day_name, FALSE, :notes)
                ON DUPLICATE KEY UPDATE
                    day_type = VALUES(day_type),
                    day_name = VALUES(day_name),
                    is_working_day = FALSE,
                    notes = VALUES(notes)
            """)
            
            session.execute(query, {
                'date': target_date,
                'day_type': day_type,
                'day_name': day_name,
                'notes': notes
            })
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"休日追加エラー: {e}")
            return False
        finally:
            session.close()
    
    def add_working_day(self, target_date: date, notes: str = None) -> bool:
        """営業日を追加（休日の振替など）"""
        session = self.db.get_session()
        try:
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, is_working_day, notes)
                VALUES (:date, '営業日', TRUE, :notes)
                ON DUPLICATE KEY UPDATE
                    day_type = '営業日',
                    is_working_day = TRUE,
                    notes = VALUES(notes)
            """)
            
            session.execute(query, {
                'date': target_date,
                'notes': notes
            })
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"営業日追加エラー: {e}")
            return False
        finally:
            session.close()
    
    def delete_calendar_date(self, target_date: date) -> bool:
        """カレンダーから日付を削除"""
        session = self.db.get_session()
        try:
            query = text("""
                DELETE FROM company_calendar 
                WHERE calendar_date = :date
            """)
            
            session.execute(query, {'date': target_date})
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"日付削除エラー: {e}")
            return False
        finally:
            session.close()
    
    def bulk_import_holidays(self, holidays: List[Dict]) -> int:
        """休日を一括インポート"""
        session = self.db.get_session()
        imported_count = 0
        
        try:
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, day_name, is_working_day, notes)
                VALUES (:date, :day_type, :day_name, FALSE, :notes)
                ON DUPLICATE KEY UPDATE
                    day_type = VALUES(day_type),
                    day_name = VALUES(day_name),
                    is_working_day = FALSE
            """)
            
            for holiday in holidays:
                session.execute(query, {
                    'date': holiday['date'],
                    'day_type': holiday.get('day_type', '祝日'),
                    'day_name': holiday.get('day_name'),
                    'notes': holiday.get('notes')
                })
                imported_count += 1
            
            session.commit()
            return imported_count
        
        except Exception as e:
            session.rollback()
            print(f"一括インポートエラー: {e}")
            return 0
        finally:
            session.close()