from sqlalchemy import create_engine, text

e = create_engine("mysql+pymysql://root@localhost:3306/bi_platform")
with e.begin() as c:
    c.execute(text("DROP TABLE IF EXISTS sales"))
    c.execute(text("DROP TABLE IF EXISTS customers"))
    c.execute(text("DROP TABLE IF EXISTS website_analytics"))
    c.execute(text("DROP TABLE IF EXISTS products"))

    c.execute(text("""
        CREATE TABLE products (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100),
            category VARCHAR(50),
            price DECIMAL(10,0),
            stock INT
        )
    """))

    c.execute(text("""
        INSERT INTO products (name, category, price, stock) VALUES
        ('Mens T-Shirt', 'Clothing', 25000, 50),
        ('Womens Dress', 'Clothing', 45000, 30),
        ('Running Shoes', 'Footwear', 85000, 25),
        ('Leather Bag', 'Accessories', 65000, 15),
        ('Wireless Earbuds', 'Electronics', 35000, 40)
    """))

    c.execute(text("""
        CREATE TABLE sales (
            id INT PRIMARY KEY AUTO_INCREMENT,
            product_id INT,
            quantity INT,
            total DECIMAL(10,0),
            sale_date DATE
        )
    """))

    c.execute(text("""
        INSERT INTO sales (product_id, quantity, total, sale_date) VALUES
        (1, 3, 75000, '2026-07-01'),
        (3, 1, 85000, '2026-07-01'),
        (2, 2, 90000, '2026-07-02'),
        (5, 5, 175000, '2026-07-02'),
        (4, 1, 65000, '2026-07-03')
    """))

print("Your tables restored")
