# セットアップガイド - ユーザー認証機能（MySQL版）

## 📋 クイックスタート

### 1️⃣ マイグレーション実行

```bash
cd d:\ts_pm_a
python migrations/add_user_auth_tables.py
```

### 2️⃣ アプリ起動

```bash
streamlit run main.py
```

### 3️⃣ ログイン

- **URL**: http://localhost:8501
- **ユーザー名**: `admin`
- **パスワード**: `admin123`

---

## ✅ 実装された機能

### ユーザー認証
- ✅ ログイン/ログアウト
- ✅ パスワードハッシュ化（SHA-256）
- ✅ セッション管理

### ロールベースのアクセス制御
- ✅ **4つのデフォルトロール**
  - 管理者（全機能）
  - 生産管理者（生産関連のみ）
  - 配送管理者（配送関連のみ）
  - 閲覧者（全画面閲覧のみ）

- ✅ **ページレベル権限**
  - 各ページの閲覧/編集権限を個別設定

- ✅ **タブレベル権限**
  - 生産計画画面の3つのタブを個別制御可能

### ユーザー管理画面
- ✅ ユーザー登録・編集・削除
- ✅ ロール割り当て
- ✅ パスワード変更

---

## 🗂️ データベーステーブル（MySQL）

```sql
-- ユーザー情報
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    is_active TINYINT(1) DEFAULT 1,
    is_admin TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL
);

-- ロール定義
CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT
);

-- ユーザー×ロール
CREATE TABLE user_roles (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

-- ページ権限
CREATE TABLE page_permissions (
    role_id INT NOT NULL,
    page_name VARCHAR(255) NOT NULL,
    can_view TINYINT(1) DEFAULT 1,
    can_edit TINYINT(1) DEFAULT 0,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

-- タブ権限
CREATE TABLE tab_permissions (
    role_id INT NOT NULL,
    page_name VARCHAR(255) NOT NULL,
    tab_name VARCHAR(255) NOT NULL,
    can_view TINYINT(1) DEFAULT 1,
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
```

---

## 📁 追加されたファイル

| ファイル | 説明 |
|---------|------|
| `migrations/add_user_auth_tables.py` | MySQL用マイグレーション |
| `services/auth_service.py` | 認証サービス |
| `ui/pages/login_page.py` | ログイン画面 |
| `ui/pages/user_management_page.py` | ユーザー管理画面 |
| `ui/layouts/sidebar.py` | サイドバー（権限対応版） |
| `main.py` | メインアプリ（認証統合済み） |

---

## 🎯 使い方の例

### 例1: 新しい「生産管理者」ユーザーを作成

1. 管理者でログイン
2. サイドバー → **ユーザー管理**
3. **➕ 新規登録**タブ
4. ユーザー情報を入力して登録
5. **🎭 ロール管理**タブ
6. ユーザーに「生産管理者」ロールを割り当て
7. ログアウトして新ユーザーでログイン
8. → ダッシュボード、製品管理、生産計画、制限設定のみアクセス可能

### 例2: タブレベルで権限を制限

MySQLで直接設定:

```sql
-- 「製造工程」タブを管理者のみに制限
-- 他のロールからは削除
DELETE FROM tab_permissions
WHERE page_name = '生産計画'
  AND tab_name = '🔧 製造工程（加工対象）'
  AND role_id != 1;  -- 1 = 管理者
```

---

## ⚠️ 重要な注意点

### セキュリティ

1. **初回ログイン後、必ず管理者パスワードを変更してください**
   - ユーザー管理 → ユーザー一覧 → admin を選択 → 新しいパスワード入力

2. **本番環境では強力なパスワードを使用**
   - 最低8文字以上
   - 英数字＋記号を組み合わせ

3. **config.pyのパスワードを保護**
   - `.gitignore`に追加
   - 環境変数の使用を推奨

### データベース

- MySQLサーバーが起動していることを確認
- `kubota_db`データベースが存在することを確認
- 必要に応じてバックアップを取得

---

## 🔧 トラブルシューティング

### ログインできない

```sql
-- ユーザー確認
SELECT * FROM users WHERE username = 'admin';

-- パスワードリセット（MySQLで直接実行）
UPDATE users
SET password_hash = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
WHERE username = 'admin';
-- 新しいパスワードは空文字列になります。ログイン後すぐに変更してください。
```

### マイグレーション失敗

```bash
# ロールバック
python migrations/add_user_auth_tables.py rollback

# 再実行
python migrations/add_user_auth_tables.py
```

### テーブルが作成されない

```sql
-- MySQLで手動確認
SHOW TABLES LIKE '%user%';
SHOW TABLES LIKE '%role%';
SHOW TABLES LIKE '%permission%';
```

---

## 🎉 完了！

ユーザー認証・権限管理機能が正常に動作します。

詳細なドキュメントは **[USER_AUTH_README.md](USER_AUTH_README.md)** を参照してください。
