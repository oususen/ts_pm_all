# ティエラ様対応実装完了サマリー

## 実装完了日
2025年（実装日時）

## 概要
久保田様とティエラ様の2社のお客様データを別々のデータベースで管理できるように実装しました。

## 主な変更点

### 1. データベース設定
**ファイル**: [.env](.env)

```env
# 久保田様用データベース
KUBOTA_DB_HOST=localhost
KUBOTA_DB_NAME=kubota_db
KUBOTA_DB_PORT=3306

# ティエラ様用データベース（新規）
TIERA_DB_HOST=localhost
TIERA_DB_NAME=tiera_db
TIERA_DB_PORT=3306

# デフォルト顧客
DEFAULT_CUSTOMER=kubota
```

### 2. データベース管理クラス
**ファイル**: [repository/database_manager.py](repository/database_manager.py)

新規クラス追加:
- `CustomerDatabaseManager`: 複数顧客のDB接続を管理
  - `switch_customer(customer)`: 顧客切り替え
  - `execute_query(query, customer=None)`: 顧客を指定してクエリ実行
  - コンテキストマネージャー対応（自動接続解放）

### 3. ティエラ様専用CSVインポートサービス
**ファイル**: [services/tiera_csv_import_service.py](services/tiera_csv_import_service.py)（新規）

**CSVフォーマット:**
- エンコーディング: CP932
- 列6: 図番（製品コード）
- 列8: 納期（YYYYMMDD形式）
- 列11: 数量
- 列12: 品名（日本語）
- 列13: 品名（英語）

**処理内容:**
1. 図番×納期でグループ化して集計
2. 製品マスタに図番を登録
3. 生産指示データを作成（`production_instructions_detail`）
4. 納入進度データを作成（`delivery_progress`）

### 4. サイドバーUI
**ファイル**: [ui/layouts/sidebar.py](ui/layouts/sidebar.py)

**追加機能:**
- 顧客選択ドロップダウン（久保田 / ティエラ）
- 現在の顧客を表示
- 顧客切り替え時に自動リロード

```python
# session_stateに顧客情報を保存
st.session_state['current_customer'] = 'kubota' or 'tiera'
```

### 5. メインアプリケーション
**ファイル**: [main.py](main.py)

**変更点:**
- `DatabaseManager` → `CustomerDatabaseManager` に変更
- 顧客選択に応じて自動的にDB切り替え

```python
# 顧客選択を反映
if 'current_customer' in st.session_state:
    current_customer = st.session_state['current_customer']
    if self.db.get_current_customer() != current_customer:
        self.db.switch_customer(current_customer)
```

### 6. CSV取り込みページ
**ファイル**: [ui/pages/csv_import_page.py](ui/pages/csv_import_page.py)

**顧客別処理:**
- 久保田様: `CSVImportService`（V2/V3形式、Shift-JIS）
- ティエラ様: `TieraCSVImportService`（図番・納期・数量形式、CP932）

**動的サービス選択:**
```python
customer = st.session_state.get('current_customer', 'kubota')

if customer == 'kubota':
    self.import_service = CSVImportService(self.db_manager)
elif customer == 'tiera':
    self.import_service = TieraCSVImportService(self.db_manager)
```

## 使用方法

### ステップ1: ティエラ様用データベースを作成

```sql
-- データベース作成
CREATE DATABASE tiera_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 久保田様DBと同じテーブル構造をコピー
USE tiera_db;

-- 以下、kubota_dbと同じテーブル作成SQL実行
-- - products
-- - production_instructions_detail
-- - delivery_progress
-- - monthly_summary
-- など
```

### ステップ2: アプリケーション起動

```bash
# 仮想環境をアクティブ化
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# アプリ起動
streamlit run main.py
```

### ステップ3: ログイン後、顧客選択

1. ログイン
2. サイドバーで「顧客選択」ドロップダウンから「ティエラ」を選択
3. 自動的に `tiera_db` に接続される

### ステップ4: CSVファイルをインポート

1. 「CSV受注取込」ページへ移動
2. ティエラ様のCSVファイルをアップロード（CP932エンコーディング）
3. プレビューで内容を確認
4. 「インポート実行」ボタンをクリック

### ステップ5: データ確認

1. 「製品管理」: 図番が登録されていることを確認
2. 「納入進度」: 図番×納期のデータが登録されていることを確認
3. 「配送便計画」: 自動的に積載計画が作成される

## データフロー図

```
┌─────────────────────────────────────────────────┐
│               ユーザーログイン                    │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│   サイドバーで顧客選択: 久保田 / ティエラ          │
│   st.session_state['current_customer'] = ...     │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│      CustomerDatabaseManager                     │
│      - 久保田 → kubota_db                        │
│      - ティエラ → tiera_db                       │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌──────────────┬──────────────────────────────────┐
│ CSV取込      │  データ取得・表示                 │
├──────────────┼──────────────────────────────────┤
│ 久保田様     │  各ページで透過的に               │
│ → Kubota     │  適切なDBからデータ取得           │
│   CSV Service│                                   │
│              │  - 製品管理                       │
│ ティエラ様   │  - 生産計画                       │
│ → Tiera      │  - 配送便計画                     │
│   CSV Service│  - 納入進度                       │
└──────────────┴──────────────────────────────────┘
```

## テーブル構造

### 久保田様とティエラ様で共通のテーブル構造を使用

**主要テーブル:**
- `products`: 製品マスタ（product_code、product_name）
- `production_instructions_detail`: 生産指示詳細
- `delivery_progress`: 納入進度
- `monthly_summary`: 月次サマリー

**データの識別:**
- 久保田様: `order_id` = "ORD-YYYYMMDD-製品コード"
- ティエラ様: `order_id` = "TIERA-YYYYMMDD-図番"

## 注意事項

### 1. データの完全分離
- 久保田様のデータは `kubota_db`
- ティエラ様のデータは `tiera_db`
- 互いに影響しません

### 2. CSVフォーマットの違い
- **久保田様**: V2/V3形式、Shift-JIS、複雑な列構造
- **ティエラ様**: シンプルな図番・納期・数量形式、CP932

### 3. 製品コードの命名
- **久保田様**: 既存の品番体系を使用
- **ティエラ様**: 図番をそのまま製品コードとして使用

### 4. 検査区分
- **久保田様**: N, NS, F, $S など多様な検査区分
- **ティエラ様**: デフォルト "N"（必要に応じて変更可能）

## トラブルシューティング

### 問題1: ティエラ様のデータが表示されない
**解決策**: サイドバーで「ティエラ」が選択されているか確認

### 問題2: CSVインポートエラー
**解決策**:
- エンコーディングを確認（CP932）
- 列数を確認（12列以上必要）
- 日付形式を確認（YYYYMMDD）

### 問題3: データベース接続エラー
**解決策**:
- `.env` ファイルの設定を確認
- `tiera_db` が作成されているか確認
- MySQLサーバーが起動しているか確認

## 今後の拡張

### 顧客追加時の手順
1. `.env` に新規顧客のDB設定を追加
2. `config_all.py` の `build_customer_db_config()` に顧客名を追加
3. `sidebar.py` の `customer_options` に顧客を追加
4. 新規顧客専用の `XXXCSVImportService` を作成
5. `csv_import_page.py` に新規顧客の分岐を追加

### 権限管理
必要に応じて、ユーザーごとにアクセス可能な顧客を制限できます：
- `auth_service` に顧客アクセス権限テーブルを追加
- サイドバーで選択可能な顧客をフィルタリング

## 関連ドキュメント

- [顧客切り替え実装ガイド](CUSTOMER_SWITCHING_GUIDE.md)
- [使用例](example_customer_db_usage.py)
- [設定ファイル](.env)

## 完了したタスク

✅ 1. ティエラ様用DB設定を `.env` に追加
✅ 2. `CustomerDatabaseManager` クラスを作成
✅ 3. `TieraCSVImportService` を実装
✅ 4. サイドバーに顧客選択UIを追加
✅ 5. `main.py` で顧客切り替えを実装
✅ 6. CSV取り込みページを顧客対応に更新

## サポート

問題が発生した場合は、以下を確認してください：
1. データベースが作成されているか
2. `.env` の設定が正しいか
3. 正しいCSVフォーマットか
4. サイドバーで正しい顧客が選択されているか
