# app/services/tiera_kakutei_csv_import_service.py
import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict
from sqlalchemy import text

class TieraKakuteiCSVImportService:
    """ティエラ様確定CSV専用インポートサービス

    フォーマット（Y55形式）:
    - エンコーディング: CP932
    - 列11: 図番（製品コード）
    - 列13: 納期（YYYYMMDD形式）
    - 列16: 数量
    - 列46: 品名（日本語）
    - 列47: 品名（英語）
    """

    # 列インデックス定義
    COL_DRAWING_NO = 11      # 図番
    COL_DELIVERY_DATE = 13   # 納期
    COL_QUANTITY = 16        # 数量
    COL_PRODUCT_NAME_JP = 46  # 品名（日本語）
    COL_PRODUCT_NAME_EN = 47  # 品名（英語）

    def __init__(self, db_manager):
        self.db = db_manager

    def import_csv_data(self, uploaded_file,
                       create_progress: bool = True) -> Tuple[bool, str]:
        """ティエラ様確定CSVファイルからデータを読み込み、データベースにインポート"""
        try:
            # CP932エンコーディングで読み込み
            df = pd.read_csv(uploaded_file, encoding='cp932', dtype=str)
            df = df.fillna('')

            print(f"📊 読み込み行数: {len(df)}")
            print(f"📊 列数: {len(df.columns)}")

            # 列名を取得（インデックスで参照するため、列名確認用）
            column_names = df.columns.tolist()

            # 必要な列が存在するか確認
            if len(column_names) < 47:
                return False, f"列数が不足しています（必要: 47列以上、実際: {len(column_names)}列）"

            # 図番列名を取得（文字化け対策）
            drawing_col = column_names[self.COL_DRAWING_NO]
            delivery_col = column_names[self.COL_DELIVERY_DATE]
            quantity_col = column_names[self.COL_QUANTITY]
            product_name_jp_col = column_names[self.COL_PRODUCT_NAME_JP]
            product_name_en_col = column_names[self.COL_PRODUCT_NAME_EN]

            print(f"📌 図番列: {drawing_col}")
            print(f"📌 納期列: {delivery_col}")
            print(f"📌 数量列: {quantity_col}")

            # データをグループ化（図番 × 納期 ごとに集約）
            grouped_data = self._group_by_product_and_date(
                df,
                drawing_col,
                delivery_col,
                quantity_col,
                product_name_jp_col,
                product_name_en_col
            )

            if not grouped_data:
                return False, "有効なデータが見つかりませんでした"

            # 製品情報をインポート
            product_ids = self._import_products(grouped_data)

            if not product_ids:
                return False, "製品情報のインポートに失敗しました"

            # 生産指示データを作成
            instruction_count = self._create_production_instructions(grouped_data, product_ids)

            # 納入進度データを作成
            if create_progress:
                progress_count = self._create_delivery_progress(grouped_data, product_ids)
                return True, f"[確定CSV] {instruction_count}件の指示データと{progress_count}件の進度データを登録しました"
            else:
                return True, f"[確定CSV] {instruction_count}件の指示データを登録しました"

        except Exception as e:
            error_msg = f"確定CSVインポートエラー: {str(e)}"
            import traceback
            traceback.print_exc()
            return False, error_msg

    def _group_by_product_and_date(self, df: pd.DataFrame,
                                   drawing_col: str,
                                   delivery_col: str,
                                   quantity_col: str,
                                   product_name_jp_col: str,
                                   product_name_en_col: str) -> List[Dict]:
        """図番と納期でグループ化して集計"""
        grouped_data = []

        for _, row in df.iterrows():
            drawing_no = str(row[drawing_col]).strip()
            delivery_date_str = str(row[delivery_col]).strip()
            quantity_str = str(row[quantity_col]).strip()
            product_name_jp = str(row[product_name_jp_col]).strip()
            product_name_en = str(row[product_name_en_col]).strip()

            # 'nan' を空文字列に変換
            if product_name_jp == 'nan' or not product_name_jp:
                product_name_jp = ''
            if product_name_en == 'nan' or not product_name_en:
                product_name_en = ''

            # 空行スキップ
            if not drawing_no or drawing_no == 'nan':
                continue

            if not delivery_date_str or delivery_date_str == 'nan':
                continue

            # 日付をパース
            delivery_date = self._parse_date(delivery_date_str)
            if not delivery_date:
                continue

            # 数量をパース
            try:
                quantity = int(float(quantity_str)) if quantity_str and quantity_str != 'nan' else 0
            except:
                quantity = 0

            # 数量0はスキップ
            if quantity <= 0:
                continue

            grouped_data.append({
                'drawing_no': drawing_no,
                'product_name_jp': product_name_jp,
                'product_name_en': product_name_en,
                'delivery_date': delivery_date,
                'quantity': quantity
            })

        # 図番 × 納期 で集約
        aggregated = {}
        for item in grouped_data:
            key = (item['drawing_no'], item['delivery_date'])
            if key not in aggregated:
                aggregated[key] = {
                    'drawing_no': item['drawing_no'],
                    'product_name_jp': item['product_name_jp'],
                    'product_name_en': item['product_name_en'],
                    'delivery_date': item['delivery_date'],
                    'quantity': 0
                }
            aggregated[key]['quantity'] += item['quantity']

        result = list(aggregated.values())
        print(f"✅ グループ化後: {len(result)}件のユニークデータ（確定CSV）")
        return result

    def _import_products(self, grouped_data: List[Dict]) -> Dict:
        """製品マスタに登録"""
        product_ids = {}
        session = self.db.get_session()

        try:
            # ユニークな図番を抽出
            unique_products = {}
            for item in grouped_data:
                drawing_no = item['drawing_no']
                if drawing_no not in unique_products:
                    unique_products[drawing_no] = {
                        'product_name_jp': item['product_name_jp'],
                        'product_name_en': item['product_name_en']
                    }

            print(f"📦 製品数（確定CSV）: {len(unique_products)}")

            for drawing_no, product_info in unique_products.items():
                # 既存チェック
                result = session.execute(text("""
                    SELECT id FROM products
                    WHERE product_code = :product_code
                """), {'product_code': drawing_no}).fetchone()

                if result:
                    product_id = result[0]
                    print(f"  ✓ 既存製品: {drawing_no} (ID: {product_id})")
                else:
                    # 新規登録
                    # 製品名を決定（優先順位: 日本語名 > 英語名 > 図番）
                    product_name = product_info['product_name_jp']
                    if not product_name:
                        product_name = product_info['product_name_en']
                    if not product_name:
                        product_name = drawing_no

                    result = session.execute(text("""
                        INSERT INTO products (
                            product_code, product_name, delivery_location,
                            box_type, capacity
                        ) VALUES (
                            :product_code, :product_name, :delivery_location,
                            :box_type, :capacity
                        )
                    """), {
                        'product_code': drawing_no,
                        'product_name': product_name,
                        'delivery_location': 'ティエラ様（確定）',
                        'box_type': '',
                        'capacity': 1
                    })
                    product_id = result.lastrowid
                    print(f"  + 新規製品: {drawing_no} [{product_name}] (ID: {product_id})")

                product_ids[drawing_no] = product_id

            session.commit()
            return product_ids

        except Exception as e:
            session.rollback()
            print(f"❌ 製品登録エラー: {e}")
            raise e
        finally:
            session.close()

    def _create_production_instructions(self, grouped_data: List[Dict],
                                       product_ids: Dict) -> int:
        """生産指示データを作成"""
        session = self.db.get_session()
        instruction_count = 0

        try:
            for item in grouped_data:
                drawing_no = item['drawing_no']
                delivery_date = item['delivery_date']
                quantity = item['quantity']

                product_id = product_ids.get(drawing_no)
                if not product_id:
                    continue

                # 月情報を計算
                year_month = delivery_date.strftime('%Y%m')

                # 生産指示データを登録
                session.execute(text("""
                    REPLACE INTO production_instructions_detail
                    (product_id, record_type, start_month, instruction_date,
                    instruction_quantity, month_type, day_number, inspection_category)
                    VALUES (:product_id, :record_type, :start_month, :instruction_date,
                    :quantity, :month_type, :day_number, :inspection_category)
                """), {
                    'product_id': product_id,
                    'record_type': 'TIERA_KAKUTEI',  # 確定CSVであることを示す
                    'start_month': year_month,
                    'instruction_date': delivery_date,
                    'quantity': quantity,
                    'month_type': 'first',
                    'day_number': delivery_date.day,
                    'inspection_category': 'N'
                })

                instruction_count += 1

            session.commit()
            print(f"✅ 生産指示登録（確定CSV）: {instruction_count}件")
            return instruction_count

        except Exception as e:
            session.rollback()
            print(f"❌ 生産指示登録エラー: {e}")
            return 0
        finally:
            session.close()

    def _create_delivery_progress(self, grouped_data: List[Dict],
                                  product_ids: Dict) -> int:
        """納入進度データを作成"""
        session = self.db.get_session()
        progress_count = 0

        try:
            for item in grouped_data:
                drawing_no = item['drawing_no']
                delivery_date = item['delivery_date']
                quantity = item['quantity']

                product_id = product_ids.get(drawing_no)
                if not product_id:
                    continue

                # オーダーIDを生成（確定CSV用）
                order_id = f"TIERA-KAKUTEI-{delivery_date.strftime('%Y%m%d')}-{drawing_no}"

                # 既存チェック
                existing = session.execute(text("""
                    SELECT id, order_quantity FROM delivery_progress
                    WHERE order_id = :order_id
                """), {'order_id': order_id}).fetchone()

                if existing:
                    # 更新
                    session.execute(text("""
                        UPDATE delivery_progress
                        SET order_quantity = :new_quantity,
                            notes = :notes
                        WHERE id = :progress_id
                    """), {
                        'progress_id': existing[0],
                        'new_quantity': quantity,
                        'notes': f'ティエラ様図番（確定）: {drawing_no} (更新)'
                    })
                else:
                    # 新規登録
                    session.execute(text("""
                        INSERT INTO delivery_progress
                        (order_id, product_id, order_date, delivery_date,
                        order_quantity, shipped_quantity, status,
                        customer_code, customer_name, priority, notes)
                        VALUES
                        (:order_id, :product_id, :order_date, :delivery_date,
                        :order_quantity, 0, '未出荷',
                        :customer_code, :customer_name, 3, :notes)
                    """), {
                        'order_id': order_id,
                        'product_id': product_id,
                        'order_date': delivery_date,
                        'delivery_date': delivery_date,
                        'order_quantity': quantity,
                        'customer_code': 'TIERA_K',
                        'customer_name': 'ティエラ様（確定）',
                        'notes': f'図番: {drawing_no} (確定CSV)'
                    })

                progress_count += 1

            session.commit()
            print(f"✅ 納入進度登録（確定CSV）: {progress_count}件")
            return progress_count

        except Exception as e:
            session.rollback()
            print(f"❌ 納入進度登録エラー: {e}")
            return 0
        finally:
            session.close()

    def _parse_date(self, date_str: str):
        """日付文字列をパース（YYYYMMDD形式）"""
        if not date_str or date_str == '':
            return None

        try:
            # YYYYMMDD形式（例: 20251031）
            if len(date_str) == 8 and date_str.isdigit():
                year = int(date_str[0:4])
                month = int(date_str[4:6])
                day = int(date_str[6:8])
                return datetime(year, month, day).date()

            return None

        except Exception:
            return None

    def get_import_history(self) -> List[Dict]:
        """インポート履歴を取得"""
        session = self.db.get_session()
        try:
            result = session.execute(text("""
                SELECT id, filename, import_date, record_count, status, message
                FROM csv_import_history
                WHERE message LIKE '%確定CSV%'
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
                'message': f"[ティエラ様・確定CSV] {message}"
            })
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
