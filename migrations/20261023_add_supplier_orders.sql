USE interior_design;

CREATE TABLE IF NOT EXISTS supplier_orders (
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
