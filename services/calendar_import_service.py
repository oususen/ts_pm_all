# app/services/calendar_import_service.py
import pandas as pd
from datetime import datetime, date
from typing import Tuple
from repository.calendar_repository import CalendarRepository

class CalendarImportService:
    """会社カレンダーExcelインポートサービス"""
    
    def __init__(self, db_manager):
        self.calendar_repo = CalendarRepository(db_manager)
        self.db = db_manager
    
    def import_excel_calendar(self, uploaded_file, overwrite: bool = False) -> Tuple[bool, str]:
        """
        会社カレンダーExcelをインポート
        
        Args:
            uploaded_file: アップロードされたExcelファイル
            overwrite: True=既存データを上書き、False=追加のみ
        
        Returns:
            (成功フラグ, メッセージ)
        """
        try:
            # Excelファイル読み込み
            df = pd.read_excel(uploaded_file, sheet_name=0)
            
            # カラム名を確認
            if '日付' not in df.columns or '状態' not in df.columns:
                return False, "必須カラム（日付、状態）が見つかりません"
            
            # データクレンジング
            df = df.dropna(subset=['日付', '状態'])
            
            # 上書きモードの場合は既存データを削除
            if overwrite:
                self._clear_existing_calendar()
            
            # データ変換とインポート
            imported_count = 0
            skipped_count = 0
            
            for _, row in df.iterrows():
                try:
                    # 日付を変換
                    if isinstance(row['日付'], str):
                        calendar_date = pd.to_datetime(row['日付']).date()
                    elif isinstance(row['日付'], datetime):
                        calendar_date = row['日付'].date()
                    elif isinstance(row['日付'], date):
                        calendar_date = row['日付']
                    else:
                        calendar_date = pd.to_datetime(row['日付']).date()
                    
                    # 状態を判定
                    status = str(row['状態']).strip()
                    is_working = (status == '出')
                    
                    # 曜日を取得（あれば）
                    day_name = row.get('曜日', '')
                    
                    # day_typeを決定
                    if is_working:
                        day_type = '営業日'
                    else:
                        # 曜日から判定
                        if day_name in ['土', '日']:
                            day_type = '休日'
                        else:
                            day_type = '祝日'  # 平日の休みは祝日扱い
                    
                    # データベースに登録
                    success = self._insert_or_update_calendar(
                        calendar_date=calendar_date,
                        day_type=day_type,
                        is_working=is_working,
                        day_name=day_name
                    )
                    
                    if success:
                        imported_count += 1
                    else:
                        skipped_count += 1
                
                except Exception as e:
                    print(f"行スキップ: {e}")
                    skipped_count += 1
                    continue
            
            if imported_count > 0:
                return True, f"✅ {imported_count}件のカレンダーデータをインポートしました（スキップ: {skipped_count}件）"
            else:
                return False, f"❌ インポートに失敗しました（スキップ: {skipped_count}件）"
        
        except Exception as e:
            return False, f"❌ Excelファイル読み込みエラー: {str(e)}"
    
    def _clear_existing_calendar(self):
        """既存カレンダーデータをクリア"""
        session = self.db.get_session()
        try:
            from sqlalchemy import text
            session.execute(text("DELETE FROM company_calendar"))
            session.commit()
            print("✅ 既存カレンダーデータをクリアしました")
        except Exception as e:
            session.rollback()
            print(f"❌ カレンダークリアエラー: {e}")
        finally:
            session.close()
    
    def _insert_or_update_calendar(self, calendar_date: date, day_type: str, 
                                   is_working: bool, day_name: str = None) -> bool:
        """カレンダーデータを登録または更新"""
        session = self.db.get_session()
        try:
            from sqlalchemy import text
            
            query = text("""
                INSERT INTO company_calendar 
                (calendar_date, day_type, day_name, is_working_day)
                VALUES (:date, :day_type, :day_name, :is_working)
                ON DUPLICATE KEY UPDATE
                    day_type = VALUES(day_type),
                    day_name = VALUES(day_name),
                    is_working_day = VALUES(is_working_day)
            """)
            
            session.execute(query, {
                'date': calendar_date,
                'day_type': day_type,
                'day_name': day_name if day_name else None,
                'is_working': is_working
            })
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            print(f"カレンダー登録エラー: {e}")
            return False
        finally:
            session.close()
    
    def export_calendar_to_excel(self, start_date: date, end_date: date) -> pd.DataFrame:
        """
        カレンダーデータをExcel形式で出力
        
        Returns:
            DataFrame
        """
        df = self.calendar_repo.get_calendar_range(start_date, end_date)
        
        if not df.empty:
            # 日本語カラム名に変換
            df['日付'] = df['calendar_date']
            df['状態'] = df['is_working_day'].apply(lambda x: '出' if x else '休')
            df['曜日'] = pd.to_datetime(df['calendar_date']).dt.day_name().map({
                'Monday': '月', 'Tuesday': '火', 'Wednesday': '水',
                'Thursday': '木', 'Friday': '金', 'Saturday': '土', 'Sunday': '日'
            })
            df['区分'] = df['day_type']
            df['名称'] = df['day_name']
            
            return df[['日付', '状態', '曜日', '区分', '名称']]
        
        return pd.DataFrame()
    
    def get_calendar_summary(self, year: int) -> dict:
        """年間カレンダーサマリーを取得"""
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        
        df = self.calendar_repo.get_calendar_range(start_date, end_date)
        
        if df.empty:
            return {
                'total_days': 0,
                'working_days': 0,
                'holidays': 0,
                'working_rate': 0
            }
        
        total_days = len(df)
        working_days = len(df[df['is_working_day'] == True])
        holidays = len(df[df['is_working_day'] == False])
        working_rate = (working_days / total_days * 100) if total_days > 0 else 0
        
        return {
            'total_days': total_days,
            'working_days': working_days,
            'holidays': holidays,
            'working_rate': round(working_rate, 1)
        }