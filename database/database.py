import sqlite3
from config import DATABASE
from werkzeug.security import generate_password_hash

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('buyer','seller','admin')),
        verified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS stores(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        logo_url TEXT DEFAULT '',
        rating REAL NOT NULL DEFAULT 0,
        rating_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'active',
        verified INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(seller_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER NOT NULL,
        store_id INTEGER NOT NULL,
        category_id INTEGER,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        brand TEXT DEFAULT '',
        price INTEGER NOT NULL,
        discount_percent REAL NOT NULL DEFAULT 0,
        stock INTEGER NOT NULL DEFAULT 0,
        rating REAL NOT NULL DEFAULT 0,
        rating_count INTEGER NOT NULL DEFAULT 0,
        size TEXT DEFAULT '',
        color TEXT DEFAULT '',
        weight_gram INTEGER NOT NULL DEFAULT 0,
        sku TEXT DEFAULT '',
        image_url TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(seller_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE CASCADE,
        FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS addresses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        recipient_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT DEFAULT '',
        postal_code TEXT DEFAULT '',
        is_default INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(buyer_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS carts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL UNIQUE,
        FOREIGN KEY(buyer_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS cart_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cart_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        UNIQUE(cart_id, product_id),
        FOREIGN KEY(cart_id) REFERENCES carts(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT NOT NULL UNIQUE,
        buyer_id INTEGER NOT NULL,
        total_price INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        payment_status TEXT NOT NULL DEFAULT 'unpaid',
        shipping_status TEXT NOT NULL DEFAULT 'not_shipped',
        recipient_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(buyer_id) REFERENCES users(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        seller_id INTEGER NOT NULL,
        store_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price INTEGER NOT NULL,
        subtotal INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY(seller_id) REFERENCES users(id) ON DELETE RESTRICT,
        FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE RESTRICT,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        order_item_id INTEGER NOT NULL,
        product_rating INTEGER NOT NULL CHECK(product_rating BETWEEN 1 AND 5),
        seller_rating INTEGER NOT NULL CHECK(seller_rating BETWEEN 1 AND 5),
        shipping_rating INTEGER NOT NULL CHECK(shipping_rating BETWEEN 1 AND 5),
        comment TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(buyer_id, order_item_id),
        FOREIGN KEY(buyer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY(order_item_id) REFERENCES order_items(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    categories = ["sepatu","baju","kaos","celana","jaket","tas","jam","hp","laptop","headset","televisi","aksesoris"]
    cur.executemany("INSERT OR IGNORE INTO categories(name) VALUES(?)", [(x,) for x in categories])

    demo = [
        ("Demo Buyer","buyer@example.com","buyer123","buyer"),
        ("Demo Seller A","seller1@example.com","seller123","seller"),
        ("Demo Seller B","seller2@example.com","seller123","seller"),
        ("Platform Admin","admin@example.com","admin123","admin"),
    ]
    for name,email,password,role in demo:
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO users(name,email,password_hash,role,verified) VALUES(?,?,?,?,?)",
                (name,email,generate_password_hash(password),role,1)
            )

    for email,name,desc in [
        ("seller1@example.com","Velocity Sports","Perlengkapan olahraga dan sepatu pilihan."),
        ("seller2@example.com","Urban Gear","Fashion dan lifestyle pilihan.")
    ]:
        seller = cur.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        cur.execute("SELECT id FROM stores WHERE seller_id=?", (seller["id"],))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO stores(seller_id,name,description,verified) VALUES(?,?,?,1)",
                (seller["id"],name,desc)
            )

    if cur.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        cats = {r["name"]:r["id"] for r in cur.execute("SELECT * FROM categories")}
        s1 = cur.execute("SELECT id FROM users WHERE email='seller1@example.com'").fetchone()["id"]
        s2 = cur.execute("SELECT id FROM users WHERE email='seller2@example.com'").fetchone()["id"]
        st1 = cur.execute("SELECT id FROM stores WHERE seller_id=?", (s1,)).fetchone()["id"]
        st2 = cur.execute("SELECT id FROM stores WHERE seller_id=?", (s2,)).fetchone()["id"]

        seed = [
            (s1,st1,cats["sepatu"],"Nike Revolution 7","Sepatu lari ringan untuk aktivitas harian.","nike",799000,0,20,4.8,120,"42","Hitam",650,"NK-R7-42-BLK"),
            (s2,st2,cats["sepatu"],"Nike Revolution 7","Pilihan harga kompetitif dari seller lain.","nike",749000,0,12,4.6,82,"42","Putih",650,"NK-R7-42-WHT"),
            (s1,st1,cats["sepatu"],"Nike Revolution 7 Premium","Pilihan dengan rating tinggi.","nike",829000,0,8,4.9,210,"42","Hitam",680,"NK-R7-P-42"),
            (s2,st2,cats["sepatu"],"Nike Air Max","Sepatu lifestyle nyaman.","nike",950000,10,6,4.8,156,"42","Hitam",720,"NAM-42-BLK"),
            (s1,st1,cats["sepatu"],"Adidas Runfalcon","Sepatu lari ringan.","adidas",699000,0,18,4.7,94,"42","Biru",620,"AR-42-BLU"),
            (s2,st2,cats["laptop"],"ASUS Vivobook 16","Laptop demo untuk coding dan produktivitas.","asus",11999000,0,5,4.8,61,"16GB","Silver",1800,"ASV16-16")
        ]
        cur.executemany("""
            INSERT INTO products(
                seller_id,store_id,category_id,name,description,brand,price,
                discount_percent,stock,rating,rating_count,size,color,weight_gram,sku
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, seed)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_database()
    print("Database siap.")
