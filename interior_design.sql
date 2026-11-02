-- =========================================================
-- INTERIOR DESIGN MANAGEMENT SYSTEM
-- MySQL / XAMPP DATABASE
-- =========================================================

CREATE DATABASE IF NOT EXISTS interior_design
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE interior_design;

SET FOREIGN_KEY_CHECKS = 0;


-- =========================================================
-- USERS
-- =========================================================

DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS carts;
DROP TABLE IF EXISTS project_updates;
DROP TABLE IF EXISTS quotation_items;
DROP TABLE IF EXISTS quotations;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS consultations;
DROP TABLE IF EXISTS supplier_orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS admins;
DROP TABLE IF EXISTS gallery;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS contractors;
DROP TABLE IF EXISTS designers;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS users;


CREATE TABLE users (

    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(100) NOT NULL,

    email VARCHAR(150) NOT NULL UNIQUE,

    phone VARCHAR(20),

    address TEXT,

    password_hash VARCHAR(255) NOT NULL,

    role ENUM(
        'admin',
        'customer',
        'designer',
        'contractor',
        'supplier'
    ) NOT NULL DEFAULT 'customer',

    status ENUM(
        'active',
        'inactive'
    ) NOT NULL DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP

) ENGINE=InnoDB;


-- =========================================================
-- CUSTOMERS
-- =========================================================

CREATE TABLE customers (

    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    full_name VARCHAR(100) NOT NULL,

    email VARCHAR(150) NOT NULL,

    phone VARCHAR(20),

    address TEXT,

    city VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_customer_user

        FOREIGN KEY (user_id)

        REFERENCES users(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- ADMINS
-- =========================================================

CREATE TABLE admins (

    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    admin_name VARCHAR(100) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_admin_user

        FOREIGN KEY (user_id)

        REFERENCES users(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- DESIGNERS
-- =========================================================

CREATE TABLE designers (

    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    full_name VARCHAR(100) NOT NULL,

    specialization VARCHAR(150),

    experience_years INT DEFAULT 0,

    bio TEXT,

    profile_image VARCHAR(255),

    status ENUM(
        'active',
        'inactive'
    ) DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_designer_user

        FOREIGN KEY (user_id)

        REFERENCES users(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- CONTRACTORS
-- =========================================================

CREATE TABLE contractors (

    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    company_name VARCHAR(150) NOT NULL,

    contact_person VARCHAR(100),

    phone VARCHAR(20),

    email VARCHAR(150),

    specialization VARCHAR(150),

    status ENUM(
        'active',
        'inactive'
    ) DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_contractor_user

        FOREIGN KEY (user_id)

        REFERENCES users(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- SUPPLIERS
-- =========================================================

CREATE TABLE suppliers (

    id INT AUTO_INCREMENT PRIMARY KEY,

    user_id INT NOT NULL UNIQUE,

    company_name VARCHAR(150) NOT NULL,

    contact_person VARCHAR(100),

    phone VARCHAR(20),

    email VARCHAR(150),

    address TEXT,

    status ENUM(
        'active',
        'inactive'
    ) DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_supplier_user

        FOREIGN KEY (user_id)

        REFERENCES users(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- SERVICES
-- =========================================================

CREATE TABLE services (

    id INT AUTO_INCREMENT PRIMARY KEY,

    name VARCHAR(150) NOT NULL,

    description TEXT,

    price_from DECIMAL(12,2)
        DEFAULT 0.00,

    image VARCHAR(255),

    is_active TINYINT(1)
        DEFAULT 1,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP

) ENGINE=InnoDB;


-- =========================================================
-- GALLERY
-- =========================================================

CREATE TABLE gallery (

    id INT AUTO_INCREMENT PRIMARY KEY,

    title VARCHAR(150) NOT NULL,

    description TEXT,

    image VARCHAR(255) NOT NULL,

    category VARCHAR(100),

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP

) ENGINE=InnoDB;


-- =========================================================
-- CONSULTATIONS
-- =========================================================

CREATE TABLE consultations (

    id INT AUTO_INCREMENT PRIMARY KEY,

    customer_id INT NOT NULL,

    service_id INT NULL,

    designer_id INT NULL,

    message TEXT,

    preferred_date DATE NULL,

    status ENUM(
        'pending',
        'contacted',
        'confirmed',
        'completed',
        'cancelled'
    ) DEFAULT 'pending',

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_consultation_customer

        FOREIGN KEY (customer_id)

        REFERENCES customers(id)

        ON DELETE CASCADE,

    CONSTRAINT fk_consultation_service

        FOREIGN KEY (service_id)

        REFERENCES services(id)

        ON DELETE SET NULL,

    CONSTRAINT fk_consultation_designer

        FOREIGN KEY (designer_id)

        REFERENCES designers(id)

        ON DELETE SET NULL

) ENGINE=InnoDB;


-- =========================================================
-- APPOINTMENTS
-- =========================================================

CREATE TABLE appointments (

    id INT AUTO_INCREMENT PRIMARY KEY,

    customer_id INT NOT NULL,

    designer_id INT NULL,

    appointment_date DATE NOT NULL,

    appointment_time TIME NOT NULL,

    purpose VARCHAR(255),

    status ENUM(
        'pending',
        'confirmed',
        'completed',
        'cancelled'
    ) DEFAULT 'pending',

    notes TEXT,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_appointment_customer

        FOREIGN KEY (customer_id)

        REFERENCES customers(id)

        ON DELETE CASCADE,

    CONSTRAINT fk_appointment_designer

        FOREIGN KEY (designer_id)

        REFERENCES designers(id)

        ON DELETE SET NULL

) ENGINE=InnoDB;


-- =========================================================
-- PROJECTS
-- =========================================================

CREATE TABLE projects (

    id INT AUTO_INCREMENT PRIMARY KEY,

    customer_id INT NOT NULL,

    designer_id INT NULL,

    contractor_id INT NULL,

    project_name VARCHAR(200) NOT NULL,

    project_type VARCHAR(100),

    description TEXT,

    start_date DATE NULL,

    expected_end_date DATE NULL,

    actual_end_date DATE NULL,

    budget DECIMAL(12,2)
        DEFAULT 0.00,

    status ENUM(
        'new',
        'planning',
        'design',
        'approval',
        'in_progress',
        'on_hold',
        'completed',
        'cancelled'
    ) DEFAULT 'new',

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_project_customer

        FOREIGN KEY (customer_id)

        REFERENCES customers(id)

        ON DELETE CASCADE,

    CONSTRAINT fk_project_designer

        FOREIGN KEY (designer_id)

        REFERENCES designers(id)

        ON DELETE SET NULL,

    CONSTRAINT fk_project_contractor

        FOREIGN KEY (contractor_id)

        REFERENCES contractors(id)

        ON DELETE SET NULL

) ENGINE=InnoDB;


-- =========================================================
-- PROJECT UPDATES
-- =========================================================

CREATE TABLE project_updates (

    id INT AUTO_INCREMENT PRIMARY KEY,

    project_id INT NOT NULL,

    title VARCHAR(200) NOT NULL,

    description TEXT,

    progress_percent
        TINYINT UNSIGNED
        DEFAULT 0,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_update_project

        FOREIGN KEY (project_id)

        REFERENCES projects(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- QUOTATIONS
-- =========================================================

CREATE TABLE quotations (

    id INT AUTO_INCREMENT PRIMARY KEY,

    project_id INT NULL,

    customer_id INT NOT NULL,

    quotation_number VARCHAR(50)
        NOT NULL UNIQUE,

    amount DECIMAL(12,2)
        NOT NULL DEFAULT 0.00,

    tax_amount DECIMAL(12,2)
        DEFAULT 0.00,

    discount_amount DECIMAL(12,2)
        DEFAULT 0.00,

    final_amount DECIMAL(12,2)
        NOT NULL DEFAULT 0.00,

    description TEXT,

    valid_until DATE NULL,

    status ENUM(
        'draft',
        'sent',
        'approved',
        'rejected',
        'expired'
    ) DEFAULT 'draft',

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_quotation_project

        FOREIGN KEY (project_id)

        REFERENCES projects(id)

        ON DELETE SET NULL,

    CONSTRAINT fk_quotation_customer

        FOREIGN KEY (customer_id)

        REFERENCES customers(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- QUOTATION ITEMS
-- =========================================================

CREATE TABLE quotation_items (

    id INT AUTO_INCREMENT PRIMARY KEY,

    quotation_id INT NOT NULL,

    item_name VARCHAR(200) NOT NULL,

    description TEXT,

    quantity INT NOT NULL DEFAULT 1,

    unit_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,

    total_price DECIMAL(12,2) NOT NULL DEFAULT 0.00,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_quotation_item_quotation

        FOREIGN KEY (quotation_id)

        REFERENCES quotations(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- PRODUCTS
-- =========================================================

CREATE TABLE products (

    id INT AUTO_INCREMENT PRIMARY KEY,

    supplier_id INT NULL,

    name VARCHAR(200) NOT NULL,

    description TEXT,

    category VARCHAR(100),

    price DECIMAL(12,2)
        NOT NULL DEFAULT 0.00,

    stock_quantity INT
        NOT NULL DEFAULT 0,

    image VARCHAR(255),

    is_active TINYINT(1)
        DEFAULT 1,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_product_supplier

        FOREIGN KEY (supplier_id)

        REFERENCES suppliers(id)

        ON DELETE SET NULL

) ENGINE=InnoDB;


-- =========================================================
-- CART
-- =========================================================

CREATE TABLE carts (

    id INT AUTO_INCREMENT PRIMARY KEY,

    customer_id INT NOT NULL UNIQUE,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_cart_customer

        FOREIGN KEY (customer_id)

        REFERENCES customers(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- CART ITEMS
-- =========================================================

CREATE TABLE cart_items (

    id INT AUTO_INCREMENT PRIMARY KEY,

    cart_id INT NOT NULL,

    product_id INT NOT NULL,

    quantity INT NOT NULL DEFAULT 1,

    UNIQUE KEY
        unique_cart_product
        (cart_id, product_id),

    CONSTRAINT fk_cart_items_cart

        FOREIGN KEY (cart_id)

        REFERENCES carts(id)

        ON DELETE CASCADE,

    CONSTRAINT fk_cart_items_product

        FOREIGN KEY (product_id)

        REFERENCES products(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- ORDERS
-- =========================================================

CREATE TABLE orders (

    id INT AUTO_INCREMENT PRIMARY KEY,

    customer_id INT NOT NULL,

    total_amount DECIMAL(12,2)
        NOT NULL DEFAULT 0.00,

    shipping_address TEXT,

    status ENUM(
        'placed',
        'processing',
        'shipped',
        'delivered',
        'cancelled'
    ) DEFAULT 'placed',

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_order_customer

        FOREIGN KEY (customer_id)

        REFERENCES customers(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- ORDER ITEMS
-- =========================================================

CREATE TABLE order_items (

    id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,

    product_id INT NULL,

    quantity INT NOT NULL,

    unit_price DECIMAL(12,2)
        NOT NULL,

    CONSTRAINT fk_order_item_order

        FOREIGN KEY (order_id)

        REFERENCES orders(id)

        ON DELETE CASCADE,

    CONSTRAINT fk_order_item_product

        FOREIGN KEY (product_id)

        REFERENCES products(id)

        ON DELETE SET NULL

) ENGINE=InnoDB;


-- =========================================================
-- SUPPLIER RESTOCK ORDERS
-- =========================================================

CREATE TABLE supplier_orders (

    id INT AUTO_INCREMENT PRIMARY KEY,

    supplier_id INT NOT NULL,

    product_id INT NOT NULL,

    customer_order_id INT NULL,

    quantity INT NOT NULL,

    status ENUM(
        'requested',
        'accepted',
        'fulfilled',
        'cancelled'
    ) NOT NULL DEFAULT 'requested',

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_supplier_order_supplier
        FOREIGN KEY (supplier_id)
        REFERENCES suppliers(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_supplier_order_product
        FOREIGN KEY (product_id)
        REFERENCES products(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_supplier_order_customer_order
        FOREIGN KEY (customer_order_id)
        REFERENCES orders(id)
        ON DELETE SET NULL

) ENGINE=InnoDB;


-- =========================================================
-- PAYMENTS
-- =========================================================
-- Existing-database migration (do not re-import this destructive schema):
-- ALTER TABLE payments MODIFY payment_method ENUM(
--     'cash', 'upi', 'card', 'net_banking', 'razorpay'
-- ) DEFAULT 'cash';

CREATE TABLE payments (

    id INT AUTO_INCREMENT PRIMARY KEY,

    order_id INT NOT NULL,

    amount DECIMAL(12,2)
        NOT NULL,

    payment_method ENUM(
        'cash',
        'upi',
        'card',
        'net_banking',
        'razorpay'
    ) DEFAULT 'cash',

    transaction_id VARCHAR(150),

    status ENUM(
        'pending',
        'paid',
        'failed',
        'refunded'
    ) DEFAULT 'pending',

    paid_at DATETIME NULL,

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_payment_order

        FOREIGN KEY (order_id)

        REFERENCES orders(id)

        ON DELETE CASCADE

) ENGINE=InnoDB;


-- =========================================================
-- ADMIN ACCOUNT
-- =========================================================
-- Initial administrator account. The password is stored as a
-- Werkzeug-generated hash; never store the plaintext password here.
-- =========================================================

INSERT INTO users
(
    name,
    email,
    phone,
    address,
    password_hash,
    role,
    status
)

VALUES
(
    'System Administrator',

    'prem54@gmail.com',

    '9999999999',

    'Interior Design System',

    'scrypt:32768:8:1$nGZi2iex38YY4D2k$3acd480fda32c33a780ff0db0c561c5a629e7ebe3eca654a06867b34757601913dbd7454ad7f682b6f939698dfdc75dfca8338b3218d292b34c2e2894c1e9a03',

    'admin',

    'active'
);

INSERT INTO admins (user_id, admin_name)
SELECT id, name
FROM users
WHERE email = 'prem54@gmail.com'
LIMIT 1;


-- =========================================================
-- SERVICES
-- =========================================================

INSERT INTO services
(
    name,
    description,
    price_from,
    image
)

VALUES

(
    'Residential Interior Design',

    'Complete interior design solutions for homes, apartments and villas.',

    50000.00,

    'residential.jpg'
),

(
    'Office Interior Design',

    'Modern and functional office interior design solutions.',

    75000.00,

    'office.jpg'
),

(
    'Modular Kitchen Design',

    'Customized modular kitchen design and planning.',

    60000.00,

    'kitchen.jpg'
),

(
    'Bedroom Interior Design',

    'Comfortable and personalized bedroom interiors.',

    40000.00,

    'bedroom.jpg'
),

(
    'Living Room Design',

    'Elegant living room interior planning and decoration.',

    45000.00,

    'living-room.jpg'
),

(
    '3D Interior Visualization',

    'Realistic 3D interior design visualization before execution.',

    15000.00,

    '3d-design.jpg'
);


-- =========================================================
-- PRODUCTS
-- =========================================================

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


-- =========================================================
-- GALLERY
-- =========================================================

INSERT INTO gallery
(
    title,
    description,
    image,
    category
)

VALUES

(
    'Modern Living Room',

    'Contemporary living room interior.',

    'gallery1.jpg',

    'Living Room'
),

(
    'Luxury Bedroom',

    'Premium bedroom interior.',

    'gallery2.jpg',

    'Bedroom'
),

(
    'Modern Kitchen',

    'Functional modular kitchen.',

    'gallery3.jpg',

    'Kitchen'
),

(
    'Corporate Office',

    'Modern office workspace.',

    'gallery4.jpg',

    'Office'
);


-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX idx_users_role
ON users(role);

CREATE INDEX idx_users_status
ON users(status);

CREATE INDEX idx_projects_status
ON projects(status);

CREATE INDEX idx_appointments_date
ON appointments(appointment_date);

CREATE INDEX idx_quotations_status
ON quotations(status);

CREATE INDEX idx_orders_status
ON orders(status);

CREATE INDEX idx_products_category
ON products(category);


SET FOREIGN_KEY_CHECKS = 1;


-- =========================================================
-- DONE
-- =========================================================