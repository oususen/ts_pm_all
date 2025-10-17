# app/services/csv_import_service.py
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict

class CSVImportService:
    """CSV受注インポートサービス"""
    
    def __init__(self, db_manager):
        self.db = db_manager
    
    def import_csv_data(self, uploaded_file, 
                       create_progress: bool = True) -> Tuple[bool, str]:
        """CSVファイルからデータを読み込み、データベースにインポート"""
        try:
            # ファイルを読み込み
            df = pd.read_csv(uploaded_file, encoding='shift_jis', dtype=str)
            df = df.fillna('')
            
            # 数値カラムを変換
            for col in ['データＮＯ', '取引先', '収容数', 'リードタイム', '定点日数']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
            # V2行（日付）とV3行（数量）を分離
            v2_rows = df[df['レコード識別'] == 'V2']
            v3_rows = df[df['レコード識別'] == 'V3']
            
            if len(v3_rows) == 0:
                return False, "V3行（数量データ）が見つかりませんでした"
            
            # 製品情報をインポート（新しいproductsテーブルを使用）
            product_ids = self._import_basic_data(v3_rows)
            
            if not product_ids:
                return False, "製品情報のインポートに失敗しました"
            
            # 生産指示データを処理
            success, count = self._process_instruction_data(v2_rows, v3_rows, product_ids)
            
            if not success:
                return False, "データインポートに失敗しました"
            
            # 納入進度データを作成（製品コードで統合）
            if create_progress:
                progress_count = self._create_delivery_progress_consolidated(v2_rows, v3_rows, product_ids)
                return True, f"{count}件の指示データと{progress_count}件の進度データを登録しました"
            else:
                return True, f"{count}件の指示データを登録しました"
        
        except Exception as e:
            error_msg = f"CSVインポートエラー: {str(e)}"
            return False, error_msg
    
    def _import_basic_data(self, df: pd.DataFrame) -> Dict:
        """製品基本情報をインポート（新しいproductsテーブルを使用）"""
        product_ids = {}
        session = self.db.get_session()
        
        try:
            from sqlalchemy import text
            
            for _, row in df.iterrows():
                product_code = row['品番']
                
                # ✅ 1. 新しいproductsテーブルに保存（product_codeのみで識別）
                result = session.execute(text("""
                    SELECT id FROM products 
                    WHERE product_code = :product_code
                """), {'product_code': product_code}).fetchone()
                
                if result:
                    simple_product_id = result[0]
                else:
                    # 新規登録（新しいproductsテーブル）
                    result = session.execute(text("""
                        INSERT INTO products (
                            product_code, product_name, delivery_location,
                            box_type, capacity
                        ) VALUES (
                            :product_code, :product_name, :delivery_location,
                            :box_type, :capacity
                        )
                    """), {
                        'product_code': product_code,
                        'product_name': row['品名'],
                        'delivery_location': row['納入場所'],
                        'box_type': row['箱種'],
                        'capacity': int(row['収容数']) if str(row['収容数']).strip() else 1
                    })
                    simple_product_id = result.lastrowid
                
                # ✅ 2. 既存のproducts_syosaiテーブルにも保存（全データ）
                data_no = int(row['データＮＯ']) if str(row['データＮＯ']).strip() else None
                inspection_category = row['検査区分']
                unique_key = (product_code, inspection_category)
                result = session.execute(text("""
                    SELECT id FROM products_syosai 
                    WHERE product_code = :product_code 
                    AND inspection_category = :inspection_category
                """), {
                    'product_code': product_code,
                    'inspection_category': inspection_category
                }).fetchone()
                
                if not result:
                    # 既存の詳細登録ロジックでproducts_syosaiに保存（全列）
                    sql = text("""
                        INSERT INTO products_syosai (
                            data_no, factory, client_code, calculation_date, production_complete_date,
                            modified_factory, product_category, product_code, ac_code, processing_content,
                            product_name, delivery_location, box_type, capacity, grouping_category,
                            form_category, inspection_category, ordering_category, regular_replenishment_category,
                            lead_time, fixed_point_days, shipping_factory, client_product_code,
                            purchasing_org, item_group, processing_type, inventory_transfer_category,
                            container_width, container_depth, container_height, stackable, can_advance,
                            used_container_id, used_truck_ids
                        ) VALUES (
                            :data_no, :factory, :client_code, :calculation_date, :production_complete_date,
                            :modified_factory, :product_category, :product_code, :ac_code, :processing_content,
                            :product_name, :delivery_location, :box_type, :capacity, :grouping_category,
                            :form_category, :inspection_category, :ordering_category, :regular_replenishment_category,
                            :lead_time, :fixed_point_days, :shipping_factory, :client_product_code,
                            :purchasing_org, :item_group, :processing_type, :inventory_transfer_category,
                            :container_width, :container_depth, :container_height, :stackable, :can_advance,
                            :used_container_id, :used_truck_ids
                        )
                    """)
                    
                    params = {
                        'data_no': int(row['データＮＯ']),
                        'factory': row['工場'],
                        'client_code': int(row['取引先']) if str(row['取引先']).strip() else 0,
                        'calculation_date': self._parse_japanese_date(str(row['計算日'])),
                        'production_complete_date': self._parse_japanese_date(str(row['生産完了日'])),
                        'modified_factory': row['工場（変更対応）'],
                        'product_category': row['品区'],
                        'product_code': product_code,
                        'ac_code': row['A/C'],
                        'processing_content': row['加工内容'],
                        'product_name': row['品名'],
                        'delivery_location': row['納入場所'],
                        'box_type': row['箱種'],
                        'capacity': int(row['収容数']) if str(row['収容数']).strip() else 0,
                        'grouping_category': row['まとめ区分'],
                        'form_category': row['形態区分'],
                        'inspection_category': row['検査区分'],
                        'ordering_category': row['手配区分'],
                        'regular_replenishment_category': row['定期補充区分'],
                        'lead_time': int(row['リードタイム']) if str(row['リードタイム']).strip() else 0,
                        'fixed_point_days': int(row['定点日数']) if str(row['定点日数']).strip() else 0,
                        'shipping_factory': row['出荷工場'],
                        'client_product_code': row['取引先品番'],
                        'purchasing_org': row['購買組織'],
                        'item_group': row['品目グループ'],
                        'processing_type': row['加工区分'],
                        'inventory_transfer_category': row['在庫転送区分'],
                        'container_width': None,
                        'container_depth': None,
                        'container_height': None,
                        'stackable': 1,
                        'can_advance': 0,
                        'used_container_id': None,
                        'used_truck_ids': None
                    }
                    
                    session.execute(sql, params)
                
                # ✅ 3. マッピング（製品コード+検査区分）→ product_id と data_no を保持
                product_ids[unique_key] = {
                    'product_id': simple_product_id,
                    'data_no': data_no
                }
            
            session.commit()
            return product_ids
        
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def _process_instruction_data(self, v2_rows: pd.DataFrame, 
                                  v3_rows: pd.DataFrame, 
                                  product_ids: Dict) -> Tuple[bool, int]:
        """生産指示データを処理"""
        session = self.db.get_session()
        instruction_count = 0
        
        try:
            from sqlalchemy import text
            
            for idx, v3_row in v3_rows.iterrows():
                # ✅ 検査区分を含むユニークキー（マッピング用）
                product_code = v3_row['品番']
                inspection_category = v3_row['検査区分']
                unique_key = (product_code, inspection_category)
                mapping = product_ids.get(unique_key)
                
                if not mapping:
                    continue
                
                product_id = mapping['product_id']
                
                # V2行とマッチング
                v2_match = v2_rows[
                    (v2_rows['データＮＯ'].astype(int) == int(v3_row['データＮＯ'])) & 
                    (v2_rows['品番'].astype(str) == str(v3_row['品番'])) & 
                    (v2_rows['検査区分'].astype(str) == str(v3_row['検査区分']))
                ]
                
                if len(v2_match) == 0:
                    continue
                
                v2_row = v2_match.iloc[0]
                start_month = v3_row['スタート月度']
                
                # 3ヶ月分のデータを処理
                count_first = self._process_month_data(
                    session, product_id, v2_row, v3_row, 'first', 27, 58, start_month
                )
                count_next = self._process_month_data(
                    session, product_id, v2_row, v3_row, 'next', 58, 89, start_month
                )
                count_next_next = self._process_month_data(
                    session, product_id, v2_row, v3_row, 'next_next', 89, 120, start_month
                )
                
                instruction_count += count_first + count_next + count_next_next
            
            session.commit()
            return True, instruction_count
        
        except Exception as e:
            session.rollback()
            return False, 0
        finally:
            session.close()
    
    def _process_month_data(self, session, product_id, v2_row, v3_row, 
                           month_type, start_col, end_col, start_month) -> int:
        """月度ごとのデータを処理"""
        from sqlalchemy import text
        instruction_count = 0
        
        total_col = {
            'first': '初月度（指示）数合計',
            'next': '次月度(指示）数合計',
            'next_next': '次々月度(指示)数合計'
        }[month_type]
        
        total_quantity = int(v3_row[total_col]) if str(v3_row[total_col]).strip() else 0
        
        # 月次サマリー
        session.execute(text("""
            INSERT INTO monthly_summary (product_id, month_type, total_quantity, month_year)
            VALUES (:product_id, :month_type, :total_quantity, :month_year)
            ON DUPLICATE KEY UPDATE total_quantity = VALUES(total_quantity)
        """), {
            'product_id': product_id,
            'month_type': month_type,
            'total_quantity': total_quantity,
            'month_year': start_month
        })
        
        # 日次データ（数量0でも記録するルール）
        day_count = 1
        
        for i in range(start_col, min(end_col, len(v2_row))):
            try:
                date_str = str(v2_row.iloc[i]).strip()
                quantity_str = str(v3_row.iloc[i]).strip()
                
                if not date_str or date_str in ['', 'nan']:
                    continue
                instruction_date = self._parse_japanese_date(date_str)
                if not instruction_date:
                    continue

                quantity = 0
                if quantity_str and quantity_str not in ['nan', '']:
                    try:
                        quantity = int(float(quantity_str))
                    except ValueError:
                        quantity = 0

                # ✅ 数量0でもREPLACEで保持（削除はしない）
                session.execute(text("""
                    REPLACE INTO production_instructions_detail 
                    (product_id, record_type, start_month, total_first_month, 
                    total_next_month, total_next_next_month, instruction_date, 
                    instruction_quantity, month_type, day_number, inspection_category)
                    VALUES (:product_id, :record_type, :start_month, :total_first, 
                    :total_next, :total_next_next, :instruction_date, 
                    :quantity, :month_type, :day_number, :inspection_category)
                """), {
                    'product_id': product_id,
                    'record_type': v3_row['レコード識別'],
                    'start_month': start_month,
                    'total_first': int(v3_row['初月度（指示）数合計']) if str(v3_row['初月度（指示）数合計']).strip() else 0,
                    'total_next': int(v3_row['次月度(指示）数合計']) if str(v3_row['次月度(指示）数合計']).strip() else 0,
                    'total_next_next': int(v3_row['次々月度(指示)数合計']) if str(v3_row['次々月度(指示)数合計']).strip() else 0,
                    'instruction_date': instruction_date,
                    'quantity': quantity,
                    'month_type': month_type,
                    'day_number': day_count,
                    'inspection_category': v3_row['検査区分']
                })
                
                instruction_count += 1
                day_count += 1
            
            except Exception:
                continue
        
        return instruction_count
    
    def _create_delivery_progress_consolidated(self, v2_rows, v3_rows, product_ids) -> int:
        """
        納入進度データを作成（製品コード統合版）
        ✅ 同じ製品コード×日付なら、検査区分が違っても数量を合計して1レコードにする
        ✅ 修正：生産指示データも製品コードベースで集約して重複計上を防ぐ
        """
        session = self.db.get_session()
        progress_count = 0
        
        try:
            from sqlalchemy import text
            
            # ✅ ステップ1: 生産指示データを製品コード×日付で直接集約
            consolidated_instructions = {}
            
            # 全ての生産指示データを製品コードベースで集約
            all_instructions = session.execute(text("""
                SELECT 
                    p.product_code,
                    pid.instruction_date,
                    SUM(pid.instruction_quantity) as total_quantity
                FROM production_instructions_detail pid
                JOIN products p ON pid.product_id = p.id
                GROUP BY p.product_code, pid.instruction_date
                ORDER BY p.product_code, pid.instruction_date
            """)).fetchall()
            
            for instruction in all_instructions:
                product_code = instruction[0]
                instruction_date = instruction[1]
                total_quantity = instruction[2]
                
                key = (product_code, instruction_date)
                consolidated_instructions[key] = total_quantity
            
            # ✅ ステップ2: 代表product_idのマッピングを作成
            product_code_to_id = {}
            for product_key, product_info in product_ids.items():
                product_code, inspection_category = product_key
                if product_code not in product_code_to_id:
                    product_code_to_id[product_code] = product_info
            
            # ✅ ステップ3: 集約したデータをdelivery_progressに登録
            for (product_code, instruction_date), total_quantity in consolidated_instructions.items():
                if product_code not in product_code_to_id:
                    continue
                    
                product_info = product_code_to_id[product_code]
                representative_product_id = product_info['product_id']
                
                # データNOを取得（最初に見つかったもの）
                data_no = product_info.get('data_no')
                
                if data_no is None:
                    continue
                
                # オーダーIDを生成（製品コードベース）
                order_id = f"ORD-{instruction_date.strftime('%Y%m%d')}-{product_code}"
                
                # ✅ 既存チェック（製品コード×日付でユニーク）
                existing = session.execute(text("""
                    SELECT id, order_quantity FROM delivery_progress
                    WHERE order_id = :order_id
                """), {'order_id': order_id}).fetchone()
                
                if existing:
                    # ✅ 既存レコードがあれば常に更新（数量0や同値でも更新）
                    existing_id = existing[0]
                    existing_quantity = existing[1]
                    session.execute(text("""
                        UPDATE delivery_progress
                        SET order_quantity = :new_quantity,
                            notes = :notes
                        WHERE id = :progress_id
                    """), {
                        'progress_id': existing_id,
                        'new_quantity': total_quantity,
                        'notes': f'製品コード: {product_code} (数量更新: {existing_quantity}→{total_quantity})'
                    })
                    progress_count += 1
                else:
                    # ✅ 新規登録
                    session.execute(text("""
                        INSERT INTO delivery_progress
                        (order_id, product_id, order_date, delivery_date, 
                        order_quantity, shipped_quantity, status, 
                        customer_code, customer_name, priority, notes)
                        VALUES
                        (:order_id, :product_id, :order_date, :delivery_date,
                        :order_quantity, 0, '未出荷',
                        :customer_code, :customer_name, 5, :notes)
                    """), {
                        'order_id': order_id,
                        'product_id': representative_product_id,
                        'order_date': instruction_date,
                        'delivery_date': instruction_date,
                        'order_quantity': total_quantity,
                        'customer_code': f'C{data_no:03d}',
                        'customer_name': f'取引先{data_no}',
                        'notes': f'製品コード: {product_code} (検査区分統合済み)'
                    })
                    
                    progress_count += 1
            
            session.commit()
            return progress_count
        
        except Exception as e:
            session.rollback()
            print(f"納入進度作成エラー: {e}")
            import traceback
            traceback.print_exc()
            return 0
        finally:
            session.close()
    
    def _parse_japanese_date(self, date_str: str):
        """和暦日付を西暦に変換（複数フォーマット対応）"""
        if not date_str or date_str == '':
            return None
        
        try:
            # フォーマット1: 5桁数字（例: 50801 → 2025年8月1日）
            if date_str.isdigit() and len(date_str) == 5:
                year_last_digit = int(date_str[0])
                month = int(date_str[1:3])
                day = int(date_str[3:5])
                
                year = 2020 + year_last_digit
                date_obj = datetime(year, month, day)
                return date_obj.date()
            
            # フォーマット2: R06/12/02形式（令和6年12月2日）
            elif date_str.startswith('R'):
                reiwa_year = int(date_str[1:3])
                year = 2018 + reiwa_year
                month_day = date_str[4:]
                date_obj = datetime.strptime(f"{year}/{month_day}", '%Y/%m/%d')
                return date_obj.date()
            
            # フォーマット3: 西暦（YYYY/MM/DD）
            elif '/' in date_str:
                date_obj = datetime.strptime(date_str, '%Y/%m/%d')
                return date_obj.date()
            
            return None
        
        except Exception:
            return None
    
    def get_import_history(self) -> List[Dict]:
        """インポート履歴を取得"""
        session = self.db.get_session()
        try:
            from sqlalchemy import text
            result = session.execute(text("""
                SELECT id, filename, import_date, record_count, status, message
                FROM csv_import_history
                ORDER BY import_date DESC
                LIMIT 50
            """)).fetchall()
            
            return [{'ID': r[0], 'ファイル名': r[1], 'インポート日時': r[2], 
                    '登録件数': r[3], 'ステータス': r[4], 'メッセージ': r[5]} for r in result]
        except Exception:
            return []
        finally:
            session.close()
    
    def log_import_history(self, filename: str, message: str):
        """インポート履歴を記録"""
        session = self.db.get_session()
        try:
            from sqlalchemy import text
            import re
            match = re.search(r'(\d+)件', message)
            record_count = int(match.group(1)) if match else 0
            
            session.execute(text("""
                INSERT INTO csv_import_history 
                (filename, import_date, record_count, status, message)
                VALUES (:filename, :import_date, :record_count, :status, :message)
            """), {
                'filename': filename,
                'import_date': datetime.now(),
                'record_count': record_count,
                'status': '成功',
                'message': message
            })
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()