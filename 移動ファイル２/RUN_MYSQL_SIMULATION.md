# MySQL版シミュレーションの実行方法

## 概要

`test_simulation_mysql.py`は、Streamlitアプリと**同じMySQLデータベース**からデータを取得してシミュレーションを実行します。

これにより、CSVファイルとDBの不一致問題が完全に解決されます。

## 実行方法

### 方法1: PowerShell（推奨）

```powershell
# 仮想環境をアクティベート
& d:/ts_app_claude/venv/Scripts/Activate.ps1

# シミュレーション実行
python test_simulation_mysql.py
```

### 方法2: バッチファイル

```cmd
run_mysql_simulation.bat
```

### 方法3: 直接実行

```bash
# venv環境のPythonを直接指定
d:\ts_app_claude\venv\Scripts\python.exe test_simulation_mysql.py
```

## 実行結果

### コンソール出力
- データベース接続状況
- 読み込んだデータ件数
- 日別の積載計画
- サマリー情報

### ファイル出力
`simulation_mysql_result.txt` - 詳細な計画結果

## データソースの確認

このスクリプトは以下のテーブルからデータを取得します：

1. **delivery_progress** - 納入進度（10/10-10/31の未出荷データ）
2. **products** - 製品マスタ
3. **truck_master** - トラックマスタ
4. **container_capacity** - 容器マスタ
5. **CALENDER** - 会社カレンダー

## トラブルシューティング

### エラー: データがありません

```
⚠️ データがありません！
Streamlitアプリの「CSV受注取込」でデータをインポートしてください
```

**解決方法**:
1. Streamlitアプリを起動: `streamlit run main.py`
2. 「CSV受注取込」タブでCSVをインポート
3. 再度シミュレーションを実行

### エラー: データベース接続失敗

**確認事項**:
- MySQLサーバーが起動しているか
- `config.py`の接続情報が正しいか
- ネットワーク接続が正常か

## CSVファイル版との違い

| 項目 | CSV版 | MySQL版 |
|------|-------|---------|
| データソース | DELIVERY_PROGRESS.csv | MySQLデータベース |
| Streamlitアプリとの一致 | ❌ 不一致の可能性 | ✅ 完全一致 |
| データ更新 | 手動でCSV編集 | Streamlitアプリで自動反映 |
| 推奨用途 | 開発・テスト | 本番運用 |

## 利点

✅ **データの一貫性**: Streamlitアプリと完全に同じデータを使用  
✅ **リアルタイム**: 最新のデータベース状態を反映  
✅ **保守性**: データソースが一元化される  
✅ **正確性**: CSVとDBの不一致による問題がなくなる

## 次のステップ

1. MySQL版シミュレーションを実行
2. `simulation_mysql_result.txt`を確認
3. Streamlitアプリで同じ期間の計画を作成
4. 両方の結果が一致することを確認

一致すれば、データソース問題は完全に解決です！
