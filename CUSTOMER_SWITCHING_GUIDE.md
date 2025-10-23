# 顧客別データベース切り替え実装ガイド

## 概要

このアプリケーションは複数の顧客（久保田様、ティエラ様）のデータを別々のデータベースで管理できます。

## アーキテクチャ

```
┌─────────────┐
│  ログイン    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 顧客選択UI   │ ← サイドバーで切り替え
└──────┬──────┘
       │
       ▼
┌──────────────────────────────┐
│ CustomerDatabaseManager      │ ← データベース自動切り替え
├──────────────┬───────────────┤
│ kubota_db    │  tiera_db     │
└──────────────┴───────────────┘
       │              │
       ▼              ▼
┌──────────────┬───────────────┐
│ Kubota       │  Tiera        │
│ CSV Service  │  CSV Service  │ ← 顧客別CSV処理
└──────────────┴───────────────┘
```

## データフロー

### 1. アプリ起動時
```python
# main.py
class ProductionPlanningApp:
    def __init__(self):
        # ❌ 古い方法（単一DB）
        # self.db = DatabaseManager()

        # ✅ 新しい方法（複数DB対応）
        self.db = CustomerDatabaseManager()
        # デフォルト顧客（kubota）で初期化される
```

### 2. 顧客選択
```python
# サイドバーで顧客を選択
selected_customer = st.selectbox(
    "顧客選択",
    ["久保田", "ティエラ"],
    key="customer_selector"
)

# session_stateに保存
st.session_state['current_customer'] = 'kubota' if selected_customer == "久保田" else 'tiera'

# データベースマネージャーに反映
db.switch_customer(st.session_state['current_customer'])
```

### 3. CSV取り込み
```python
# CSV取り込みページで顧客に応じたサービスを使用
customer = st.session_state.get('current_customer', 'kubota')

if customer == 'kubota':
    service = KubotaCSVImportService(db)
elif customer == 'tiera':
    service = TieraCSVImportService(db)

# CSVファイルを処理
service.import_csv_data(uploaded_file)
```

### 4. データ取得
```python
# 自動的に現在の顧客のDBからデータ取得
df = db.execute_query("SELECT * FROM products")

# または明示的に顧客を指定
df_kubota = db.execute_query("SELECT * FROM products", customer="kubota")
df_tiera = db.execute_query("SELECT * FROM products", customer="tiera")
```

## 実装ファイル構成

```
ts_pm_all/
├── .env                              # 顧客別DB設定
│   ├── KUBOTA_DB_* (久保田用)
│   └── TIERA_DB_* (ティエラ用)
│
├── config_all.py                     # DB設定関数
│   ├── build_customer_db_config()    # 顧客別設定取得
│   └── get_default_customer()        # デフォルト顧客取得
│
├── repository/
│   └── database_manager.py           # DB接続管理
│       ├── DatabaseManager           # 既存（単一DB用）
│       └── CustomerDatabaseManager   # 新規（複数DB用）★
│
├── services/
│   ├── csv_import_service.py        # 既存（久保田用）
│   ├── kubota_csv_import_service.py # 久保田用（リネーム）★
│   └── tiera_csv_import_service.py  # ティエラ用（新規）★
│
├── ui/
│   ├── layouts/
│   │   └── sidebar.py               # サイドバー（顧客選択UI追加）★
│   │
│   └── pages/
│       └── csv_import_page.py       # CSV取り込み画面（顧客対応）★
│
└── main.py                          # メインアプリ（DB切り替え対応）★
```

★ = 修正が必要なファイル

## 実装手順

### ステップ1: サイドバーに顧客選択UIを追加
**ファイル**: `ui/layouts/sidebar.py`

```python
def create_sidebar(auth_service=None):
    with st.sidebar:
        # ロゴ・タイトル表示
        st.title("🏭 生産計画")

        # ✅ 顧客選択追加
        st.markdown("---")
        st.subheader("🏢 顧客選択")

        customer_options = {
            "久保田": "kubota",
            "ティエラ": "tiera"
        }

        # session_stateから現在の顧客を取得
        current = st.session_state.get('current_customer', 'kubota')
        current_display = "久保田" if current == "kubota" else "ティエラ"

        selected = st.selectbox(
            "顧客を選択",
            list(customer_options.keys()),
            index=list(customer_options.keys()).index(current_display),
            key="customer_selector"
        )

        # 顧客が変更されたら更新
        new_customer = customer_options[selected]
        if new_customer != st.session_state.get('current_customer'):
            st.session_state['current_customer'] = new_customer
            st.rerun()

        st.info(f"現在: **{selected}様**")
        st.markdown("---")

        # 既存のページメニュー
        # ...
```

### ステップ2: main.pyでCustomerDatabaseManagerを使用
**ファイル**: `main.py`

```python
from repository.database_manager import CustomerDatabaseManager  # 変更

class ProductionPlanningApp:
    def __init__(self):
        # ✅ CustomerDatabaseManagerに変更
        self.db = CustomerDatabaseManager()

        # 他は既存のまま
        self.production_service = ProductionService(self.db)
        # ...

    def run(self):
        # ...認証処理...

        # ✅ 顧客選択を反映
        if 'current_customer' in st.session_state:
            self.db.switch_customer(st.session_state['current_customer'])

        # 既存のページ表示処理
        # ...
```

### ステップ3: 顧客別CSVサービスを作成
**新規ファイル**: `services/tiera_csv_import_service.py`

```python
import pandas as pd
from typing import Tuple

class TieraCSVImportService:
    """ティエラ様専用CSVインポートサービス"""

    def __init__(self, db_manager):
        self.db = db_manager

    def import_csv_data(self, uploaded_file) -> Tuple[bool, str]:
        """
        ティエラ様のCSVフォーマットでデータをインポート

        ※ 列名と形式が久保田様と異なるため、
        　 ティエラ様独自の処理を実装します
        """
        try:
            # ティエラ様のCSVフォーマットに合わせて読み込み
            # 例: UTF-8エンコーディング、列名が異なる、など
            df = pd.read_csv(uploaded_file, encoding='utf-8')

            # ティエラ様独自の列名マッピング
            # TODO: 実際の列名に合わせて調整
            column_mapping = {
                'ティエラの製品コード列': 'product_code',
                'ティエラの製品名列': 'product_name',
                # ... 他の列マッピング
            }

            df = df.rename(columns=column_mapping)

            # ティエラ様のデータ処理ロジック
            count = self._process_tiera_data(df)

            return True, f"{count}件のデータを登録しました"

        except Exception as e:
            return False, f"エラー: {str(e)}"

    def _process_tiera_data(self, df: pd.DataFrame) -> int:
        """ティエラ様のデータ処理"""
        # TODO: ティエラ様独自の処理を実装
        pass
```

### ステップ4: CSV取り込みページを更新
**ファイル**: `ui/pages/csv_import_page.py`

```python
class CSVImportPage:
    def __init__(self, db_manager, auth_service=None):
        self.db = db_manager
        self.auth_service = auth_service

        # ✅ 顧客別サービスを動的に選択
        self.import_service = None  # 後で選択

    def show(self):
        st.title("📥 受注CSVインポート")

        # ✅ 現在の顧客を取得
        customer = st.session_state.get('current_customer', 'kubota')

        # ✅ 顧客に応じたサービスを選択
        if customer == 'kubota':
            from services.csv_import_service import CSVImportService
            self.import_service = CSVImportService(self.db)
            st.info("📋 久保田様用CSVフォーマット（V2/V3形式、Shift-JIS）")
        elif customer == 'tiera':
            from services.tiera_csv_import_service import TieraCSVImportService
            self.import_service = TieraCSVImportService(self.db)
            st.info("📋 ティエラ様用CSVフォーマット（独自形式）")

        # 既存のタブ表示
        tab1, tab2, tab3 = st.tabs([...])
        # ...
```

## テスト方法

### 1. データベース作成
```sql
-- ティエラ様用DBを作成
CREATE DATABASE tiera_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 久保田様と同じテーブル構造をコピー
-- （テーブル名は同じでOK）
USE tiera_db;
-- テーブル作成SQL実行...
```

### 2. 動作確認
```
1. アプリ起動
2. ログイン
3. サイドバーで「ティエラ」を選択
4. CSV受注取込ページへ移動
5. ティエラ様のCSVファイルをアップロード
6. データがtiera_dbに保存されることを確認
7. サイドバーで「久保田」に切り替え
8. データがkubota_dbから取得されることを確認
```

## よくある質問

### Q: テーブル名は同じでも大丈夫？
**A**: はい、データベースが異なれば（kubota_db と tiera_db）、同じテーブル名を使用できます。

### Q: 顧客を切り替えた時、データはどうなる？
**A**: `CustomerDatabaseManager` が自動的に適切なDBに接続するので、それぞれの顧客のデータが表示されます。

### Q: CSV形式が全く違う場合は？
**A**: 顧客ごとに別々のCSVサービスクラスを作成し、それぞれ独自の処理を実装します。

### Q: 既存のkubotaデータは影響を受ける？
**A**: いいえ、既存のkubota_dbはそのまま使用でき、影響を受けません。

## 注意事項

1. **データの分離**: 顧客データは完全に分離されています
2. **CSV形式**: 各顧客専用のCSVサービスを使用してください
3. **権限管理**: 必要に応じてユーザーごとに顧客アクセス権限を設定できます
4. **パフォーマンス**: CustomerDatabaseManagerは接続をキャッシュするので効率的です
