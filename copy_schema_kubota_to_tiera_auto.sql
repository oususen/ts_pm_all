-- =====================================
-- kubota_db のスキーマを tiera_db にコピー
-- 自動生成スクリプト
-- データは含まれません（構造のみ）
-- =====================================

-- ステップ1: tiera_db を作成（既に存在する場合はスキップ）
CREATE DATABASE IF NOT EXISTS tiera_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- ステップ2: tiera_db を使用
USE tiera_db;

-- =====================================
-- テーブル構造をコピー
-- =====================================

-- company_calendar テーブル
DROP TABLE IF EXISTS company_calendar;
CREATE TABLE company_calendar LIKE kubota_db.company_calendar;

-- container_capacity テーブル
DROP TABLE IF EXISTS container_capacity;
CREATE TABLE container_capacity LIKE kubota_db.container_capacity;

-- csv_import_history テーブル
DROP TABLE IF EXISTS csv_import_history;
CREATE TABLE csv_import_history LIKE kubota_db.csv_import_history;

-- delivery_progress テーブル
DROP TABLE IF EXISTS delivery_progress;
CREATE TABLE delivery_progress LIKE kubota_db.delivery_progress;

-- loading_plan_detail テーブル
DROP TABLE IF EXISTS loading_plan_detail;
CREATE TABLE loading_plan_detail LIKE kubota_db.loading_plan_detail;

-- loading_plan_edit_history テーブル
DROP TABLE IF EXISTS loading_plan_edit_history;
CREATE TABLE loading_plan_edit_history LIKE kubota_db.loading_plan_edit_history;

-- loading_plan_header テーブル
DROP TABLE IF EXISTS loading_plan_header;
CREATE TABLE loading_plan_header LIKE kubota_db.loading_plan_header;

-- loading_plan_unloaded テーブル
DROP TABLE IF EXISTS loading_plan_unloaded;
CREATE TABLE loading_plan_unloaded LIKE kubota_db.loading_plan_unloaded;

-- loading_plan_versions テーブル
DROP TABLE IF EXISTS loading_plan_versions;
CREATE TABLE loading_plan_versions LIKE kubota_db.loading_plan_versions;

-- loading_plan_warnings テーブル
DROP TABLE IF EXISTS loading_plan_warnings;
CREATE TABLE loading_plan_warnings LIKE kubota_db.loading_plan_warnings;

-- monthly_summary テーブル
DROP TABLE IF EXISTS monthly_summary;
CREATE TABLE monthly_summary LIKE kubota_db.monthly_summary;

-- page_permissions テーブル
DROP TABLE IF EXISTS page_permissions;
CREATE TABLE page_permissions LIKE kubota_db.page_permissions;

-- product_container_mapping テーブル
DROP TABLE IF EXISTS product_container_mapping;
CREATE TABLE product_container_mapping LIKE kubota_db.product_container_mapping;

-- production_constraints テーブル
DROP TABLE IF EXISTS production_constraints;
CREATE TABLE production_constraints LIKE kubota_db.production_constraints;

-- production_instructions_detail テーブル
DROP TABLE IF EXISTS production_instructions_detail;
CREATE TABLE production_instructions_detail LIKE kubota_db.production_instructions_detail;

-- production_plan テーブル
DROP TABLE IF EXISTS production_plan;
CREATE TABLE production_plan LIKE kubota_db.production_plan;

-- products テーブル
DROP TABLE IF EXISTS products;
CREATE TABLE products LIKE kubota_db.products;

-- products_syosai テーブル
DROP TABLE IF EXISTS products_syosai;
CREATE TABLE products_syosai LIKE kubota_db.products_syosai;

-- roles テーブル
DROP TABLE IF EXISTS roles;
CREATE TABLE roles LIKE kubota_db.roles;

-- shipment_records テーブル
DROP TABLE IF EXISTS shipment_records;
CREATE TABLE shipment_records LIKE kubota_db.shipment_records;

-- tab_permissions テーブル
DROP TABLE IF EXISTS tab_permissions;
CREATE TABLE tab_permissions LIKE kubota_db.tab_permissions;

-- transport_constraints テーブル
DROP TABLE IF EXISTS transport_constraints;
CREATE TABLE transport_constraints LIKE kubota_db.transport_constraints;

-- transport_plans テーブル
DROP TABLE IF EXISTS transport_plans;
CREATE TABLE transport_plans LIKE kubota_db.transport_plans;

-- truck_container_rules テーブル
DROP TABLE IF EXISTS truck_container_rules;
CREATE TABLE truck_container_rules LIKE kubota_db.truck_container_rules;

-- truck_master テーブル
DROP TABLE IF EXISTS truck_master;
CREATE TABLE truck_master LIKE kubota_db.truck_master;

-- user_roles テーブル
DROP TABLE IF EXISTS user_roles;
CREATE TABLE user_roles LIKE kubota_db.user_roles;

-- users テーブル
DROP TABLE IF EXISTS users;
CREATE TABLE users LIKE kubota_db.users;

-- v_delivery_progress_summary テーブル
DROP TABLE IF EXISTS v_delivery_progress_summary;
CREATE TABLE v_delivery_progress_summary LIKE kubota_db.v_delivery_progress_summary;

-- v_delivery_progress_with_next_planned テーブル
DROP TABLE IF EXISTS v_delivery_progress_with_next_planned;
CREATE TABLE v_delivery_progress_with_next_planned LIKE kubota_db.v_delivery_progress_with_next_planned;

-- v_loading_plan_with_progress テーブル
DROP TABLE IF EXISTS v_loading_plan_with_progress;
CREATE TABLE v_loading_plan_with_progress LIKE kubota_db.v_loading_plan_with_progress;

-- カレンダー テーブル
DROP TABLE IF EXISTS カレンダー;
CREATE TABLE カレンダー LIKE kubota_db.カレンダー;

-- タンク構成部品表 テーブル
DROP TABLE IF EXISTS タンク構成部品表;
CREATE TABLE タンク構成部品表 LIKE kubota_db.タンク構成部品表;

-- タンク計画 テーブル
DROP TABLE IF EXISTS タンク計画;
CREATE TABLE タンク計画 LIKE kubota_db.タンク計画;

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
