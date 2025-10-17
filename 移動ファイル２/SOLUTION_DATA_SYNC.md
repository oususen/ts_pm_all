# データ同期の解決手順

## 問題の原因

**シミュレーションスクリプトとStreamlitアプリで使用するデータソースが異なる**

- **シミュレーション**: `DELIVERY_PROGRESS.csv` ← データあり ✅
- **Streamlitアプリ**: SQLiteデータベース ← データなし ❌

そのため、Streamlitアプリで計画を作成しても正しい結果が出ません。

## 解決方法

### 方法1: Streamlitアプリの「CSV受注取込」機能を使う（推奨）

1. Streamlitアプリを起動:
   ```bash
   streamlit run main.py
   ```

2. サイドバーから「CSV受注取込」を選択

3. `DELIVERY_PROGRESS.csv`をアップロード

4. 「納入進度も同時作成」にチェック

5. 「インポート実行」ボタンをクリック

6. インポート完了後、「配送便計画」タブで計画を作成

### 方法2: 直接CSVをDBにインポートする（手動）

以下のPythonスクリプトを実行してください：

```python
# quick_sync_csv_to_db.py
import pandas as pd
import sqlite3
from datetime import datetime

# CSVを読み込み
df = pd.read_csv('DELIVERY_PROGRESS.csv')
print(f"CSVレコード数: {len(df)}")

# データベースに接続
conn = sqlite3.connect('production_planning.db')

# delivery_progressテーブルにインポート
# （テーブルが存在しない場合は、まずStreamlitアプリを一度起動してテーブルを作成してください）
df.to_sql('delivery_progress', conn, if_exists='replace', index=False)

# 確認
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM delivery_progress")
count = cursor.fetchone()[0]
print(f"DBレコード数: {count}")

conn.close()
print("✅ 同期完了")
```

## 確認方法

データが正しく同期されたか確認：

```python
# check_sync.py
import sqlite3

conn = sqlite3.connect('production_planning.db')
cursor = conn.cursor()

# 総レコード数
cursor.execute("SELECT COUNT(*) FROM delivery_progress")
total = cursor.fetchone()[0]
print(f"総レコード数: {total}")

# 10/23のデータ
cursor.execute("""
    SELECT COUNT(*), SUM(remaining_quantity)
    FROM delivery_progress
    WHERE delivery_date = '2025-10-23'
""")
result = cursor.fetchone()
print(f"10/23: {result[0]}件, 総数量{result[1]}")

conn.close()
```

期待される結果:
- 総レコード数: 416件（または未出荷のみなら112件）
- 10/23: 8件, 総数量361

## 同期後の作業

1. Streamlitアプリで「配送便計画」を作成
2. CSV出力を実行
3. 新しいCSVで確認:
   - ✅ 10/23にNO_4_10T (ID=10)が含まれている
   - ✅ 「前倒し配送」列が表示されている
   - ✅ シミュレーション結果と一致している

## 今後の運用

データの一貫性を保つため:

1. **データの更新はStreamlitアプリで行う**
   - 「CSV受注取込」機能を使用
   - または「納入進度」ページで直接編集

2. **シミュレーションスクリプトを使う場合**
   - DBからCSVをエクスポートしてから使用
   - または、シミュレーションスクリプトもDBを参照するように修正

3. **定期的なバックアップ**
   - `production_planning.db`を定期的にバックアップ
   - 重要なCSVファイルもバージョン管理
