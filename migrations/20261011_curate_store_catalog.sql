UPDATE products
SET is_active = 0
WHERE LOWER(name) IN (
    'modern lounge chair',
    'designer table lamp',
    'wooden coffee table',
    'decorative wall panel',
    'ergonomic office chair',
    'modern office desk',
    'office bookshelf',
    'modern tv unit',
    'modern bookshelf',
    'designer cushion set',
    'ceramic decorative vase'
);

INSERT INTO products
(
    name,
    description,
    category,
    price,
    stock_quantity,
    image
)
SELECT
    seed.name,
    seed.description,
    seed.category,
    seed.price,
    seed.stock_quantity,
    seed.image
FROM (
    SELECT 'Modern Sofa' AS name, 'Comfortable contemporary sofa for a modern living room.' AS description, 'Living Room' AS category, 45000.00 AS price, 8 AS stock_quantity, 'modern_sofa.jpg' AS image
    UNION ALL SELECT 'Luxury Sofa', 'Premium upholstered sofa with a refined finish.', 'Living Room', 65000.00, 5, 'luxury_sofa.jpg'
    UNION ALL SELECT 'Accent Chair', 'Statement chair suited to living rooms and reading corners.', 'Living Room', 12000.00, 10, 'accent_chair.jpg'
    UNION ALL SELECT 'Coffee Table', 'Minimal coffee table with a warm wood finish.', 'Living Room', 8999.00, 12, 'coffee_table.jpg'
    UNION ALL SELECT 'Dining Table', 'Solid-style dining table for everyday meals and gatherings.', 'Dining Room', 28500.00, 6, 'dining_table.jpg'
    UNION ALL SELECT 'Dining Chair', 'Comfortable dining chair with a clean contemporary profile.', 'Dining Room', 6500.00, 18, 'dining_chair.jpg'
    UNION ALL SELECT 'King Size Bed', 'Spacious upholstered king bed for a calm bedroom.', 'Bedroom', 52000.00, 4, 'king_bed.jpg'
    UNION ALL SELECT 'Bedside Table', 'Compact bedside table with useful storage.', 'Bedroom', 7500.00, 10, 'bedside_table.jpg'
    UNION ALL SELECT 'Modern Wardrobe', 'Modern wardrobe with a simple, versatile finish.', 'Bedroom', 38500.00, 5, 'wardrobe.jpg'
    UNION ALL SELECT 'Modular Kitchen', 'Flexible modular kitchen cabinetry for modern homes.', 'Kitchen', 125000.00, 2, 'modular_kitchen.jpg'
    UNION ALL SELECT 'Kitchen Cabinet', 'Practical kitchen cabinet with a contemporary look.', 'Kitchen', 15999.00, 7, 'kitchen_cabinet.jpg'
    UNION ALL SELECT 'Pendant Light', 'Decorative pendant light for dining and living spaces.', 'Lighting', 4999.00, 20, 'pendant_light.jpg'
    UNION ALL SELECT 'Floor Lamp', 'Elegant floor lamp for a softly lit reading corner.', 'Lighting', 7499.00, 9, 'floor_lamp.jpg'
    UNION ALL SELECT 'Wall Art', 'A decorative wall art piece to add character to a room.', 'Decor', 2499.00, 25, 'wall_art.jpg'
    UNION ALL SELECT 'Decorative Mirror', 'A decorative mirror that brightens and opens up a room.', 'Decor', 5999.00, 12, 'decorative_mirror.jpg'
    UNION ALL SELECT 'Indoor Plant', 'Low-maintenance indoor greenery for a fresh interior.', 'Decor', 1999.00, 30, 'indoor_plant.jpg'
) AS seed
WHERE NOT EXISTS (
    SELECT 1
    FROM products existing
    WHERE LOWER(existing.name) = LOWER(seed.name)
);

UPDATE products AS product
JOIN (
    SELECT 'Modern Sofa' AS name, 'Living Room' AS category, 'modern_sofa.jpg' AS image
    UNION ALL SELECT 'Luxury Sofa', 'Living Room', 'luxury_sofa.jpg'
    UNION ALL SELECT 'Accent Chair', 'Living Room', 'accent_chair.jpg'
    UNION ALL SELECT 'Coffee Table', 'Living Room', 'coffee_table.jpg'
    UNION ALL SELECT 'Dining Table', 'Dining Room', 'dining_table.jpg'
    UNION ALL SELECT 'Dining Chair', 'Dining Room', 'dining_chair.jpg'
    UNION ALL SELECT 'King Size Bed', 'Bedroom', 'king_bed.jpg'
    UNION ALL SELECT 'Bedside Table', 'Bedroom', 'bedside_table.jpg'
    UNION ALL SELECT 'Modern Wardrobe', 'Bedroom', 'wardrobe.jpg'
    UNION ALL SELECT 'Modular Kitchen', 'Kitchen', 'modular_kitchen.jpg'
    UNION ALL SELECT 'Kitchen Cabinet', 'Kitchen', 'kitchen_cabinet.jpg'
    UNION ALL SELECT 'Pendant Light', 'Lighting', 'pendant_light.jpg'
    UNION ALL SELECT 'Floor Lamp', 'Lighting', 'floor_lamp.jpg'
    UNION ALL SELECT 'Wall Art', 'Decor', 'wall_art.jpg'
    UNION ALL SELECT 'Decorative Mirror', 'Decor', 'decorative_mirror.jpg'
    UNION ALL SELECT 'Indoor Plant', 'Decor', 'indoor_plant.jpg'
) AS catalog
    ON LOWER(product.name) = LOWER(catalog.name)
SET product.category = catalog.category,
    product.image = catalog.image,
    product.is_active = 1;
