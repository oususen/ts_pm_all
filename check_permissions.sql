-- ページ権限の確認
SELECT
    r.id as role_id,
    r.role_name,
    pp.page_name,
    pp.can_view,
    pp.can_edit
FROM roles r
LEFT JOIN page_permissions pp ON r.id = pp.role_id
ORDER BY r.id, pp.page_name;

-- タブ権限の確認
SELECT
    r.id as role_id,
    r.role_name,
    tp.page_name,
    tp.tab_name,
    tp.can_view
FROM roles r
LEFT JOIN tab_permissions tp ON r.id = tp.role_id
ORDER BY r.id, tp.page_name, tp.tab_name;

-- ロール一覧
SELECT * FROM roles;
