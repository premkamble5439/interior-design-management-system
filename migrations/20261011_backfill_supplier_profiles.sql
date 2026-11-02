INSERT INTO suppliers
(
    user_id,
    company_name,
    contact_person,
    phone,
    email,
    address,
    status
)
SELECT
    u.id,
    u.name,
    u.name,
    u.phone,
    u.email,
    u.address,
    'active'
FROM users u
LEFT JOIN suppliers s
    ON s.user_id = u.id
WHERE u.role = 'supplier'
  AND s.id IS NULL;
