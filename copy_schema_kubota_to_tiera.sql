-- =====================================
-- kubota_db のスキーマを tiera_db にコピー
-- データは含まれません（構造のみ）
-- =====================================

-- ステップ1: tiera_db を作成（既に存在する場合はスキップ）
CREATE DATABASE IF NOT EXISTS tiera_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- ステップ2: tiera_db を使用
USE tiera_db;

-- =====================================
-- 以下、kubota_db のテーブル構造をコピー
-- =====================================

-- products テーブル
DROP TABLE IF EXISTS products;
CREATE TABLE products LIKE kubota_db.products;

-- products_syosai テーブル
DROP TABLE IF EXISTS products_syosai;
CREATE TABLE products_syosai LIKE kubota_db.products_syosai;

-- production_instructions_detail テーブル
DROP TABLE IF EXISTS production_instructions_detail;
CREATE TABLE production_instructions_detail LIKE kubota_db.production_instructions_detail;

-- monthly_summary テーブル
DROP TABLE IF EXISTS monthly_summary;
CREATE TABLE monthly_summary LIKE kubota_db.monthly_summary;

-- delivery_progress テーブル
DROP TABLE IF EXISTS delivery_progress;
CREATE TABLE delivery_progress LIKE kubota_db.delivery_progress;

-- planned_shipments テーブル
DROP TABLE IF EXISTS planned_shipments;
CREATE TABLE planned_shipments LIKE kubota_db.planned_shipments;

-- csv_import_history テーブル
DROP TABLE IF EXISTS csv_import_history;
CREATE TABLE csv_import_history LIKE kubota_db.csv_import_history;

-- users テーブル（必要に応じて）
-- DROP TABLE IF EXISTS users;
-- CREATE TABLE users LIKE kubota_db.users;

-- roles テーブル（必要に応じて）
-- DROP TABLE IF EXISTS roles;
-- CREATE TABLE roles LIKE kubota_db.roles;

-- user_roles テーブル（必要に応じて）
-- DROP TABLE IF EXISTS user_roles;
-- CREATE TABLE user_roles LIKE kubota_db.user_roles;

-- user_page_permissions テーブル（必要に応じて）
-- DROP TABLE IF EXISTS user_page_permissions;
-- CREATE TABLE user_page_permissions LIKE kubota_db.user_page_permissions;

-- company_calendar テーブル（必要に応じて）
-- DROP TABLE IF EXISTS company_calendar;
-- CREATE TABLE company_calendar LIKE kubota_db.company_calendar;

-- =====================================
-- 確認
-- =====================================
SHOW TABLES;

SELECT
    TABLE_NAME as 'テーブル名',
    TABLE_ROWS as '行数',
    CREATE_TIME as '作成日時'
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'tiera_db'
ORDER BY TABLE_NAME;
