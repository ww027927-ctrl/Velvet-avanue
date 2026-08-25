from flask import Flask,render_template,request,jsonify
from werkzeug.security import generate_password_hash,check_password_hash
import secrets
from config import SECRET_KEY
from database.database import get_connection,init_database
from services.auth import current_user,login_user,logout_user,role_required
from services.ai import ai_parse_request
from services.shopping import search_products,recommendation_text

app=Flask(__name__);app.secret_key=SECRET_KEY

@app.context_processor
def context():return {"current_user":current_user()}

@app.get("/")
def home():return render_template("index.html")

@app.get("/api/me")
def me():return jsonify({"success":True,"user":current_user()})

@app.post("/api/register")
def register():
    d=request.get_json(silent=True) or {}
    name=str(d.get("name","")).strip();email=str(d.get("email","")).strip().lower()
    pw=str(d.get("password",""));role=d.get("role","buyer")
    if not name or not email or len(pw)<6:return jsonify({"success":False,"message":"Data akun tidak lengkap."}),400
    if role not in ("buyer","seller"):return jsonify({"success":False,"message":"Role tidak valid."}),400
    conn=get_connection()
    try:
        cur=conn.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",(name,email,generate_password_hash(pw),role))
        uid=cur.lastrowid
        if role=="seller":
            conn.execute("INSERT INTO stores(seller_id,name,description) VALUES(?,?,?)",(uid,str(d.get("store_name","")).strip() or f"Toko {name}",str(d.get("store_description","")).strip()))
        conn.commit();user=conn.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    except Exception:
        conn.rollback();conn.close();return jsonify({"success":False,"message":"Email sudah digunakan atau data tidak valid."}),400
    conn.close();login_user(user);return jsonify({"success":True,"user":dict(user)})

@app.post("/api/login")
def login():
    d=request.get_json(silent=True) or {};email=str(d.get("email","")).strip().lower();pw=str(d.get("password",""))
    conn=get_connection();u=conn.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone();conn.close()
    if not u or not check_password_hash(u["password_hash"],pw):return jsonify({"success":False,"message":"Email atau password salah."}),401
    login_user(u);return jsonify({"success":True,"user":dict(u)})

@app.post("/api/logout")
def logout():logout_user();return jsonify({"success":True})

@app.post("/api/ai/search")
def ai_search():
    d=request.get_json(silent=True) or {};text=str(d.get("query","")).strip()
    if not text:return jsonify({"success":False,"message":"Permintaan kosong."}),400
    c,source=ai_parse_request(text);products=search_products(c)
    return jsonify({"success":True,"ai_source":source,"criteria":c,"recommendation":recommendation_text(products,c),"products":products})

@app.get("/api/products")
def products():
    c={"category":request.args.get("category"),"brand":request.args.get("brand"),"size":request.args.get("size"),
       "max_price":int(request.args["max_price"]) if request.args.get("max_price") else None,
       "min_rating":float(request.args["min_rating"]) if request.args.get("min_rating") else None,
       "sort":request.args.get("sort","best_match")}
    return jsonify({"success":True,"products":search_products(c)})

@app.get("/api/stores/<int:sid>")
def store(sid):
    conn=get_connection()
    s=conn.execute("""SELECT s.*,u.name seller_name FROM stores s JOIN users u ON u.id=s.seller_id WHERE s.id=?""",(sid,)).fetchone()
    if not s:conn.close();return jsonify({"success":False,"message":"Toko tidak ditemukan."}),404
    p=conn.execute("SELECT * FROM products WHERE store_id=? AND status='active' ORDER BY id DESC",(sid,)).fetchall()
    conn.close();return jsonify({"success":True,"store":dict(s),"products":[dict(x) for x in p]})

@app.post("/api/seller/products")
@role_required("seller")
def create_product():
    u=current_user();d=request.get_json(silent=True) or {}
    try:price=int(d["price"]);stock=int(d["stock"])
    except:return jsonify({"success":False,"message":"Harga/stok harus angka."}),400
    conn=get_connection();store=conn.execute("SELECT * FROM stores WHERE seller_id=?",(u["id"],)).fetchone()
    cat=conn.execute("SELECT id FROM categories WHERE name=?",(str(d.get("category","")).strip().lower(),)).fetchone()
    if not store or not cat:conn.close();return jsonify({"success":False,"message":"Toko atau kategori tidak ditemukan."}),400
    cur=conn.execute("""INSERT INTO products(seller_id,store_id,category_id,name,description,brand,price,discount_percent,stock,size,color,weight_gram,sku,image_url)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(u["id"],store["id"],cat["id"],d["name"],d.get("description",""),str(d.get("brand","")).lower(),price,float(d.get("discount_percent",0) or 0),stock,d.get("size",""),d.get("color",""),int(d.get("weight_gram",0) or 0),d.get("sku",""),d.get("image_url","")))
    conn.commit();p=conn.execute("SELECT * FROM products WHERE id=?",(cur.lastrowid,)).fetchone();conn.close()
    return jsonify({"success":True,"product":dict(p)})

@app.get("/api/seller/products")
@role_required("seller")
def seller_products():
    u=current_user();conn=get_connection();p=conn.execute("SELECT p.*,c.name category_name FROM products p LEFT JOIN categories c ON c.id=p.category_id WHERE p.seller_id=? ORDER BY p.id DESC",(u["id"],)).fetchall();conn.close()
    return jsonify({"success":True,"products":[dict(x) for x in p]})

def cart_for(conn,buyer):
    x=conn.execute("SELECT * FROM carts WHERE buyer_id=?",(buyer,)).fetchone()
    if x:return x
    cur=conn.execute("INSERT INTO carts(buyer_id) VALUES(?)",(buyer,))
    return conn.execute("SELECT * FROM carts WHERE id=?",(cur.lastrowid,)).fetchone()

@app.get("/api/cart")
@role_required("buyer")
def cart():
    u=current_user();conn=get_connection()
    rows=conn.execute("""SELECT ci.product_id,ci.quantity,p.name,p.price,p.stock,s.name store_name,p.price*ci.quantity subtotal
    FROM carts c JOIN cart_items ci ON ci.cart_id=c.id JOIN products p ON p.id=ci.product_id JOIN stores s ON s.id=p.store_id WHERE c.buyer_id=?""",(u["id"],)).fetchall()
    conn.close();return jsonify({"success":True,"items":[dict(x) for x in rows],"total":sum(x["subtotal"] for x in rows)})

@app.post("/api/cart/items")
@role_required("buyer")
def add_cart():
    u=current_user();d=request.get_json(silent=True) or {}
    try:pid=int(d["product_id"]);qty=int(d.get("quantity",1))
    except:return jsonify({"success":False,"message":"Produk/jumlah tidak valid."}),400
    conn=get_connection();p=conn.execute("SELECT * FROM products WHERE id=? AND status='active'",(pid,)).fetchone()
    if not p:conn.close();return jsonify({"success":False,"message":"Produk tidak ditemukan."}),404
    c=cart_for(conn,u["id"]);old=conn.execute("SELECT * FROM cart_items WHERE cart_id=? AND product_id=?",(c["id"],pid)).fetchone()
    total=qty+(old["quantity"] if old else 0)
    if total>p["stock"]:conn.close();return jsonify({"success":False,"message":"Stok tidak cukup."}),400
    if old:conn.execute("UPDATE cart_items SET quantity=? WHERE id=?",(total,old["id"]))
    else:conn.execute("INSERT INTO cart_items(cart_id,product_id,quantity) VALUES(?,?,?)",(c["id"],pid,qty))
    conn.commit();conn.close();return cart()

@app.patch("/api/cart/items/<int:pid>")
@role_required("buyer")
def update_cart(pid):
    u=current_user();d=request.get_json(silent=True) or {};qty=int(d.get("quantity",0));conn=get_connection();c=conn.execute("SELECT id FROM carts WHERE buyer_id=?",(u["id"],)).fetchone()
    if c:
        if qty<=0:conn.execute("DELETE FROM cart_items WHERE cart_id=? AND product_id=?",(c["id"],pid))
        else:conn.execute("UPDATE cart_items SET quantity=? WHERE cart_id=? AND product_id=?",(qty,c["id"],pid))
    conn.commit();conn.close();return cart()

@app.delete("/api/cart/items/<int:pid>")
@role_required("buyer")
def remove_cart(pid):
    u=current_user();conn=get_connection();c=conn.execute("SELECT id FROM carts WHERE buyer_id=?",(u["id"],)).fetchone()
    if c:conn.execute("DELETE FROM cart_items WHERE cart_id=? AND product_id=?",(c["id"],pid));conn.commit()
    conn.close();return cart()

@app.post("/api/addresses")
@role_required("buyer")
def address():
    u=current_user();d=request.get_json(silent=True) or {}
    conn=get_connection()
    if d.get("is_default"):conn.execute("UPDATE addresses SET is_default=0 WHERE buyer_id=?",(u["id"],))
    cur=conn.execute("""INSERT INTO addresses(buyer_id,recipient_name,phone,address,city,postal_code,is_default)
    VALUES(?,?,?,?,?,?,?)""",(u["id"],d["recipient_name"],d["phone"],d["address"],d.get("city",""),d.get("postal_code",""),int(bool(d.get("is_default")))))
    conn.commit();a=conn.execute("SELECT * FROM addresses WHERE id=?",(cur.lastrowid,)).fetchone();conn.close();return jsonify({"success":True,"address":dict(a)})

@app.get("/api/addresses")
@role_required("buyer")
def addresses():
    u=current_user();conn=get_connection();a=conn.execute("SELECT * FROM addresses WHERE buyer_id=? ORDER BY is_default DESC,id DESC",(u["id"],)).fetchall();conn.close();return jsonify({"success":True,"addresses":[dict(x) for x in a]})

@app.post("/api/orders")
@role_required("buyer")
def order():
    u=current_user();d=request.get_json(silent=True) or {};conn=get_connection()
    a=conn.execute("SELECT * FROM addresses WHERE id=? AND buyer_id=?",(d.get("address_id"),u["id"])).fetchone()
    c=conn.execute("SELECT * FROM carts WHERE buyer_id=?",(u["id"],)).fetchone()
    if not a or not c:conn.close();return jsonify({"success":False,"message":"Alamat atau cart tidak ditemukan."}),400
    items=conn.execute("""SELECT ci.*,p.name,p.price,p.stock,p.seller_id,p.store_id FROM cart_items ci JOIN products p ON p.id=ci.product_id WHERE ci.cart_id=?""",(c["id"],)).fetchall()
    if not items:conn.close();return jsonify({"success":False,"message":"Cart kosong."}),400
    total=sum(i["price"]*i["quantity"] for i in items)
    if any(i["quantity"]>i["stock"] for i in items):conn.close();return jsonify({"success":False,"message":"Stok berubah dan tidak mencukupi."}),400
    code="VA-"+secrets.token_hex(4).upper()
    cur=conn.execute("""INSERT INTO orders(order_code,buyer_id,total_price,recipient_name,phone,address) VALUES(?,?,?,?,?,?)""",(code,u["id"],total,a["recipient_name"],a["phone"],a["address"]))
    oid=cur.lastrowid
    conn.executemany("""INSERT INTO order_items(order_id,seller_id,store_id,product_id,product_name,quantity,unit_price,subtotal) VALUES(?,?,?,?,?,?,?,?)""",[(oid,i["seller_id"],i["store_id"],i["product_id"],i["name"],i["quantity"],i["price"],i["price"]*i["quantity"]) for i in items])
    for i in items:conn.execute("UPDATE products SET stock=stock-? WHERE id=?",(i["quantity"],i["product_id"]))
    conn.execute("DELETE FROM cart_items WHERE cart_id=?",(c["id"],));conn.commit();o=conn.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone();conn.close()
    return jsonify({"success":True,"order":dict(o)})

@app.get("/api/orders")
@role_required("buyer")
def orders():
    u=current_user();conn=get_connection();o=conn.execute("SELECT * FROM orders WHERE buyer_id=? ORDER BY id DESC",(u["id"],)).fetchall();conn.close();return jsonify({"success":True,"orders":[dict(x) for x in o]})

@app.get("/api/seller/orders")
@role_required("seller")
def seller_orders():
    u=current_user();conn=get_connection();o=conn.execute("""SELECT o.*,oi.product_name,oi.quantity FROM orders o JOIN order_items oi ON oi.order_id=o.id WHERE oi.seller_id=? ORDER BY o.id DESC""",(u["id"],)).fetchall();conn.close();return jsonify({"success":True,"orders":[dict(x) for x in o]})

@app.get("/api/admin/overview")
@role_required("admin")
def admin_overview():
    conn=get_connection()
    data={
        "buyers":conn.execute("SELECT COUNT(*) FROM users WHERE role='buyer'").fetchone()[0],
        "sellers":conn.execute("SELECT COUNT(*) FROM users WHERE role='seller'").fetchone()[0],
        "products":conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "orders":conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "gmv":conn.execute("SELECT COALESCE(SUM(total_price),0) FROM orders").fetchone()[0],
        "open_reports":conn.execute("SELECT COUNT(*) FROM reports WHERE status='open'").fetchone()[0]
    }
    conn.close();return jsonify({"success":True,"data":data})

@app.post("/api/reviews")
@role_required("buyer")
def review():
    u=current_user();d=request.get_json(silent=True) or {}
    conn=get_connection()
    item=conn.execute("""SELECT oi.* FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.id=? AND o.buyer_id=?""",(d.get("order_item_id"),u["id"])).fetchone()
    if not item:conn.close();return jsonify({"success":False,"message":"Order item tidak valid."}),403
    try:
        conn.execute("""INSERT INTO reviews(buyer_id,product_id,order_item_id,product_rating,seller_rating,shipping_rating,comment)
        VALUES(?,?,?,?,?,?,?)""",(u["id"],item["product_id"],item["id"],int(d["product_rating"]),int(d["seller_rating"]),int(d["shipping_rating"]),d.get("comment","")))
        st=conn.execute("SELECT AVG(product_rating) avg,COUNT(*) n FROM reviews WHERE product_id=?",(item["product_id"],)).fetchone()
        conn.execute("UPDATE products SET rating=?,rating_count=? WHERE id=?",(round(st["avg"] or 0,2),st["n"],item["product_id"]))
        conn.commit()
    except Exception:
        conn.rollback();conn.close();return jsonify({"success":False,"message":"Review sudah ada atau tidak valid."}),400
    conn.close();return jsonify({"success":True})

if __name__=="__main__":
    init_database()
    app.run(debug=True)
