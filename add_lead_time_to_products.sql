-- productsテーブルにlead_time_days列を追加
-- リードタイム日数（納品日の何日前に積載するか）
-- デフォルト: 0日（Kubota様のように納品日当日積載）

-- kubota_dbに追加
USE kubota_db;
ALTER TABLE products
ADD COLUMN lead_time_days INT NOT NULL DEFAULT 0
COMMENT 'リードタイム日数（納品日の何日前に積載するか）'
AFTER can_advance;

-- tiera_dbに追加
USE tiera_db;
ALTER TABLE products
ADD COLUMN lead_time_days INT NOT NULL DEFAULT 0
COMMENT 'リードタイム日数（納品日の何日前に積載するか）'
AFTER can_advance;

-- Tiera様の既存製品に一律2日を設定（必要に応じて実行）
-- UPDATE tiera_db.products SET lead_time_days = 2;
