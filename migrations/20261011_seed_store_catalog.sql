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

UPDATE products
SET image = CASE LOWER(name)
    WHEN 'modern sofa' THEN 'modern_sofa.jpg'
    WHEN 'luxury sofa' THEN 'luxury_sofa.jpg'
    WHEN 'accent chair' THEN 'accent_chair.jpg'
    WHEN 'coffee table' THEN 'coffee_table.jpg'
    WHEN 'dining table' THEN 'dining_table.jpg'
    WHEN 'dining chair' THEN 'dining_chair.jpg'
    WHEN 'king size bed' THEN 'king_bed.jpg'
    WHEN 'bedside table' THEN 'bedside_table.jpg'
    WHEN 'modern wardrobe' THEN 'wardrobe.jpg'
    WHEN 'modular kitchen' THEN 'modular_kitchen.jpg'
    WHEN 'kitchen cabinet' THEN 'kitchen_cabinet.jpg'
    WHEN 'pendant light' THEN 'pendant_light.jpg'
    WHEN 'floor lamp' THEN 'floor_lamp.jpg'
    WHEN 'Wall Art' THEN 'wall_art.jpg'
    WHEN 'Decorative Mirror' THEN 'decorative_mirror.jpg'
    WHEN 'Indoor Plant' THEN 'indoor_plant.jpg'
END
WHERE (image IS NULL OR image = '')
  AND LOWER(name) IN (
      'modern sofa',
      'luxury sofa',
      'accent chair',
      'coffee table',
      'dining table',
      'dining chair',
      'king size bed',
      'bedside table',
      'modern wardrobe',
      'modular kitchen',
      'kitchen cabinet',
      'pendant light',
      'floor lamp',
      'wall art',
      'decorative mirror',
      'indoor plant'
  );
