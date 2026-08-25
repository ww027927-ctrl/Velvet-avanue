import re
from database.database import get_connection

CATEGORIES = ["sepatu","baju","kaos","celana","jaket","tas","jam","hp","handphone","smartphone","laptop","headset","televisi","tv","aksesoris"]
BRANDS = ["nike","adidas","puma","apple","samsung","xiaomi","oppo","vivo","lenovo","asus","acer","sony"]

def parse_request(text):
    t=text.lower().strip()
    r={"original_request":text,"category":None,"brand":None,"size":None,"max_price":None,"min_rating":None,"sort":"best_match"}
    for x in CATEGORIES:
        if re.search(r"\b"+re.escape(x)+r"\b",t):
            r["category"]="hp" if x in ("handphone","smartphone") else ("televisi" if x=="tv" else x); break
    for x in BRANDS:
        if re.search(r"\b"+re.escape(x)+r"\b",t):
            r["brand"]=x; break
    m=re.search(r"(?:ukuran|size)\s*(\d+(?:\.\d+)?)",t)
    if m:r["size"]=m.group(1)
    m=re.search(r"(?:maksimal|max|dibawah|di bawah|budget|bujet)\s*(?:rp\s*)?([\d.,]+)\s*(juta|jt|ribu|rb)?",t)
    if m:
        n=int(m.group(1).replace(".","").replace(",","")); u=m.group(2)
        if u in ("juta","jt"): n*=1000000
        elif u in ("ribu","rb"): n*=1000
        r["max_price"]=n
    m=re.search(r"(?:rating|minimal rating|rating minimal)\s*(\d+(?:[.,]\d+)?)",t)
    if m:r["min_rating"]=float(m.group(1).replace(",","."))
    if any(x in t for x in ("termurah","paling murah","harga terendah")):r["sort"]="cheapest"
    elif any(x in t for x in ("rating tertinggi","rating terbaik","paling bagus")):r["sort"]="highest_rating"
    return r

def score_product(p,c):
    score=0; reasons=[]
    if c["category"]:score+=30;reasons.append("kategori sesuai")
    if c["brand"]:
        if p["brand"].lower()==c["brand"]:score+=20;reasons.append("brand sesuai")
        else:score-=30
    if c["size"]:
        if p["size"]==c["size"]:score+=15;reasons.append("ukuran sesuai")
        else:score-=20
    if c["max_price"] is not None:
        if p["price"]<=c["max_price"]:score+=15;reasons.append("sesuai budget")
        else:score-=40
    if c["min_rating"] is not None:
        if p["rating"]>=c["min_rating"]:score+=15;reasons.append("rating memenuhi")
        else:score-=35
    score+=min(p["rating"],5)
    if p["stock"]>0:score+=5;reasons.append("stok tersedia")
    else:score-=100
    if p["store_verified"]:score+=5;reasons.append("seller terverifikasi")
    return round(score,2),reasons

def search_products(c,limit=40):
    conn=get_connection()
    q="""SELECT p.*,s.name store_name,s.rating store_rating,s.rating_count store_rating_count,
    s.verified store_verified,u.name seller_name,c.name category_name
    FROM products p JOIN stores s ON s.id=p.store_id JOIN users u ON u.id=p.seller_id
    LEFT JOIN categories c ON c.id=p.category_id
    WHERE p.status='active' AND p.stock>0"""
    params=[]
    if c.get("category"):q+=" AND c.name=?";params.append(c["category"])
    if c.get("brand"):q+=" AND lower(p.brand)=?";params.append(c["brand"].lower())
    if c.get("size"):q+=" AND p.size=?";params.append(c["size"])
    if c.get("max_price") is not None:q+=" AND p.price<=?";params.append(c["max_price"])
    if c.get("min_rating") is not None:q+=" AND p.rating>=?";params.append(c["min_rating"])
    q+=" LIMIT ?";params.append(limit)
    rows=[dict(x) for x in conn.execute(q,params).fetchall()]
    conn.close()
    for p in rows:p["match_score"],p["match_reasons"]=score_product(p,c)
    if c.get("sort")=="cheapest":rows.sort(key=lambda x:(x["price"],-x["match_score"],-x["rating"]))
    elif c.get("sort")=="highest_rating":rows.sort(key=lambda x:(-x["rating"],-x["match_score"],x["price"]))
    else:rows.sort(key=lambda x:(-x["match_score"],-x["rating"],x["price"]))
    return rows

def recommendation_text(products,c):
    if not products:return "Belum ada produk yang memenuhi kriteria. Coba longgarkan budget, ukuran, brand, atau rating."
    p=products[0]
    why=", ".join(p["match_reasons"][:6])
    if c.get("sort")=="cheapest":
        return f"Pilihan utama: {p['name']} dari {p['store_name']} karena menjadi opsi termurah yang memenuhi filter. {why}."
    return f"Pilihan utama: {p['name']} dari {p['store_name']} karena memiliki kecocokan terbaik. {why}."
