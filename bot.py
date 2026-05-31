"""
🏪 DO'KON BOT — bitta fayl, circular import yo'q
pip install pyTelegramBotAPI
"""
import os, sys, json, math, sqlite3
from datetime import datetime
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

# ══════════════════════════════════════════════
#  ⚙️ SOZLAMALAR
# ══════════════════════════════════════════════
BOT_TOKEN  = os.environ.get("8994441380:AAGlT8IxUSsEWv8MeRPfUNeSOv1O-KdqylA", "TOKEN_HERE")
ADMIN_IDS  = [int(os.environ.get("5830170101", "123456789"))]
SHOP_NAME  = "NOKTA SHOP"
CURRENCY   = "so'm"
SUPPORT    = "@nokta_shop_admin"
DELIVERY_PRICE      = 0
FREE_DELIVERY_FROM  = 0
PRODUCTS_PER_PAGE   = 6
PROMO_CODES = {"YANGI10": 10, "SALE20": 20, "VIP30": 30}

# ══════════════════════════════════════════════
#  🗄️ MA'LUMOTLAR BAZASI
# ══════════════════════════════════════════════
DB_PATH = "shop.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, phone TEXT,
        joined_at TEXT DEFAULT(datetime('now')), is_banned INTEGER DEFAULT 0,
        total_orders INTEGER DEFAULT 0, total_spent INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, emoji TEXT DEFAULT'📦', is_active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, description TEXT,
        price INTEGER, old_price INTEGER DEFAULT 0, emoji TEXT DEFAULT'📦',
        stock INTEGER DEFAULT 999, is_active INTEGER DEFAULT 1, is_popular INTEGER DEFAULT 0,
        rating REAL DEFAULT 0.0, review_count INTEGER DEFAULT 0, sold_count INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS wishlist(
        user_id INTEGER, product_id INTEGER, PRIMARY KEY(user_id,product_id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT, total INTEGER,
        delivery INTEGER DEFAULT 0, promo_code TEXT, discount INTEGER DEFAULT 0,
        address TEXT, phone TEXT, status TEXT DEFAULT'new', note TEXT,
        created_at TEXT DEFAULT(datetime('now')), updated_at TEXT DEFAULT(datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER,
        order_id INTEGER, rating INTEGER, text TEXT, created_at TEXT DEFAULT(datetime('now')))""")
    conn.commit()
    _seed(c, conn); conn.close()

def _seed(c, conn):
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] > 0: return
    cats = [("Erkaklar kiyimi","👔"),("Ayollar kiyimi","👗"),("Poyabzal","👟"),
            ("Aksessuarlar","⌚"),("Elektronika","📱"),("Sport","⚽")]
    c.executemany("INSERT INTO categories(name,emoji) VALUES(?,?)", cats)
    prods = [
        (1,"Nike Polo Shirt","100% paxta. O'lcham: S-XXL. Rang: oq, qora, ko'k",320000,380000,"👕",50,1),
        (1,"Levi's 511 Jeans","Slim fit. O'lcham: 28-36. Classic blue",680000,0,"👖",30,1),
        (1,"Adidas Hoodie","Fleece. O'lcham: S-XL. Navy blue",420000,500000,"🧥",25,0),
        (2,"Zara Blouse","Yengil. O'lcham: XS-L. Pastel rang",280000,0,"👚",40,1),
        (2,"H&M Summer Dress","Chit. O'lcham: XS-XL. Gul naqshli",350000,420000,"👗",20,0),
        (3,"Nike Air Max 270","Original. O'lcham: 39-45. Qora/oq",950000,1100000,"👟",15,1),
        (3,"Adidas Ultra Boost","Running. O'lcham: 38-46. Oq",880000,0,"👟",12,0),
        (3,"New Balance 574","Suede. O'lcham: 38-44. Kulrang",720000,850000,"👟",18,1),
        (4,"Casio G-Shock","Su o'tkazmas. Batareya 10 yil",650000,0,"⌚",8,1),
        (4,"Ray-Ban Wayfarer","UV400 himoya. Polarized",480000,580000,"🕶️",20,0),
        (5,"Samsung Galaxy Buds","ANC. 30 soat batareya",850000,950000,"🎧",10,1),
        (5,"Xiaomi Power Bank","20000mAh. 65W tez zaryad",280000,0,"🔋",35,0),
        (6,"Nike Dri-FIT","Sport. Namlik shimuvchi",210000,250000,"👕",60,0),
        (6,"Adidas Training Bag","35L. Noutbuk cho'ntak",380000,0,"🎒",15,0),
    ]
    c.executemany("INSERT INTO products(category_id,name,description,price,old_price,emoji,stock,is_popular) VALUES(?,?,?,?,?,?,?,?)", prods)
    conn.commit()

def fmt(amount):
    return f"{amount:,} {CURRENCY}".replace(",", " ")

def db_upsert_user(uid, uname, fname):
    c = get_conn()
    c.execute("INSERT INTO users(user_id,username,full_name) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,full_name=excluded.full_name", (uid,uname,fname))
    c.commit(); c.close()

def db_get_user(uid):
    c = get_conn(); r = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone(); c.close()
    return dict(r) if r else None

def db_set_phone(uid, phone):
    c = get_conn(); c.execute("UPDATE users SET phone=? WHERE user_id=?", (phone,uid)); c.commit(); c.close()

def db_all_users():
    c = get_conn(); r = c.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall(); c.close()
    return [x[0] for x in r]

def db_get_cats():
    c = get_conn(); r = c.execute("SELECT * FROM categories WHERE is_active=1").fetchall(); c.close()
    return [dict(x) for x in r]

def db_get_products(cat_id=None, search=None, popular=False, offset=0, limit=6):
    where = ["p.is_active=1"]; params = []
    if cat_id: where.append("p.category_id=?"); params.append(cat_id)
    if search: where.append("p.name LIKE ?"); params.append(f"%{search}%")
    if popular: where.append("p.is_popular=1")
    sql = f"SELECT p.*,c.name as cat_name,c.emoji as cat_emoji FROM products p JOIN categories c ON c.id=p.category_id WHERE {' AND '.join(where)} ORDER BY p.is_popular DESC,p.sold_count DESC LIMIT ? OFFSET ?"
    c = get_conn(); r = c.execute(sql, params+[limit,offset]).fetchall(); c.close()
    return [dict(x) for x in r]

def db_count_products(cat_id=None, search=None, popular=False):
    where = ["is_active=1"]; params = []
    if cat_id: where.append("category_id=?"); params.append(cat_id)
    if search: where.append("name LIKE ?"); params.append(f"%{search}%")
    if popular: where.append("is_popular=1")
    c = get_conn(); n = c.execute(f"SELECT COUNT(*) FROM products WHERE {' AND '.join(where)}", params).fetchone()[0]; c.close()
    return n

def db_get_product(pid):
    c = get_conn()
    r = c.execute("SELECT p.*,c.name as cat_name FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?", (pid,)).fetchone()
    c.close(); return dict(r) if r else None

def db_toggle_wish(uid, pid):
    c = get_conn()
    ex = c.execute("SELECT 1 FROM wishlist WHERE user_id=? AND product_id=?", (uid,pid)).fetchone()
    if ex: c.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?", (uid,pid)); added=False
    else: c.execute("INSERT OR IGNORE INTO wishlist VALUES(?,?)", (uid,pid)); added=True
    c.commit(); c.close(); return added

def db_get_wish(uid):
    c = get_conn()
    r = c.execute("SELECT p.* FROM products p JOIN wishlist w ON w.product_id=p.id WHERE w.user_id=? AND p.is_active=1", (uid,)).fetchall()
    c.close(); return [dict(x) for x in r]

def db_in_wish(uid, pid):
    c = get_conn(); r = c.execute("SELECT 1 FROM wishlist WHERE user_id=? AND product_id=?", (uid,pid)).fetchone(); c.close(); return bool(r)

ORDER_STATUSES = {
    "new":("🆕","Yangi"), "confirmed":("✅","Tasdiqlandi"),
    "preparing":("🔧","Tayyorlanmoqda"), "delivering":("🚚","Yetkazilmoqda"),
    "delivered":("🎉","Yetkazildi"), "cancelled":("❌","Bekor qilindi"),
}

def db_create_order(uid, items, total, delivery, address, phone, promo_code="", discount=0, note=""):
    c = get_conn(); cur = c.cursor()
    cur.execute("INSERT INTO orders(user_id,items,total,delivery,address,phone,promo_code,discount,note) VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, json.dumps(items, ensure_ascii=False), total, delivery, address, phone, promo_code, discount, note))
    oid = cur.lastrowid
    c.execute("UPDATE users SET total_orders=total_orders+1,total_spent=total_spent+? WHERE user_id=?", (total,uid))
    for pid, qty in items.items():
        c.execute("UPDATE products SET sold_count=sold_count+? WHERE id=?", (qty, int(pid)))
    c.commit(); c.close(); return oid

def db_get_orders(uid, limit=10):
    c = get_conn(); r = c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (uid,limit)).fetchall(); c.close()
    return [dict(x) for x in r]

def db_get_order(oid):
    c = get_conn(); r = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone(); c.close()
    return dict(r) if r else None

def db_update_status(oid, status):
    c = get_conn(); c.execute("UPDATE orders SET status=?,updated_at=datetime('now') WHERE id=?", (status,oid)); c.commit(); c.close()

def db_all_orders(status=None, limit=20):
    c = get_conn()
    if status: r = c.execute("SELECT * FROM orders WHERE status=? ORDER BY created_at DESC LIMIT ?", (status,limit)).fetchall()
    else: r = c.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    c.close(); return [dict(x) for x in r]

def db_add_review(uid, pid, oid, rating, text):
    c = get_conn()
    c.execute("INSERT OR IGNORE INTO reviews(user_id,product_id,order_id,rating,text) VALUES(?,?,?,?,?)", (uid,pid,oid,rating,text))
    row = c.execute("SELECT AVG(rating),COUNT(*) FROM reviews WHERE product_id=?", (pid,)).fetchone()
    c.execute("UPDATE products SET rating=?,review_count=? WHERE id=?", (round(row[0],1),row[1],pid))
    c.commit(); c.close()

def db_get_reviews(pid, limit=5):
    c = get_conn()
    r = c.execute("SELECT r.*,u.full_name FROM reviews r JOIN users u ON u.user_id=r.user_id WHERE r.product_id=? ORDER BY r.created_at DESC LIMIT ?", (pid,limit)).fetchall()
    c.close(); return [dict(x) for x in r]

def db_stats():
    c = get_conn()
    s = {
        "users": c.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "orders": c.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "revenue": c.execute("SELECT COALESCE(SUM(total),0) FROM orders WHERE status!='cancelled'").fetchone()[0],
        "new_orders": c.execute("SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0],
        "today": c.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0],
    }
    c.close(); return s

# ══════════════════════════════════════════════
#  🛒 SAVATCHA
# ══════════════════════════════════════════════
_carts = {}
_promos = {}

def cart_get(uid): return _carts.setdefault(uid, {})
def cart_add(uid, pid):
    pid = str(pid); p = db_get_product(int(pid))
    if not p or p["stock"] <= 0: return False
    cart_get(uid)[pid] = min(cart_get(uid).get(pid,0)+1, p["stock"]); return True
def cart_inc(uid, pid):
    pid = str(pid); p = db_get_product(int(pid))
    if p: cart_get(uid)[pid] = min(cart_get(uid).get(pid,0)+1, p["stock"])
def cart_dec(uid, pid):
    pid = str(pid); c = cart_get(uid)
    if c.get(pid,0) > 1: c[pid] -= 1
    else: c.pop(pid, None)
def cart_rm(uid, pid): cart_get(uid).pop(str(pid), None)
def cart_clear(uid): _carts[uid] = {}; _promos.pop(uid, None)
def cart_qty(uid, pid): return cart_get(uid).get(str(pid), 0)
def cart_empty(uid): return not bool(cart_get(uid))

def cart_items(uid):
    result = {}
    for pid, q in cart_get(uid).items():
        p = db_get_product(int(pid))
        if p: result[pid] = (p["name"], p["price"], q)
    return result

def cart_subtotal(uid):
    total = 0
    for pid, q in cart_get(uid).items():
        p = db_get_product(int(pid))
        if p: total += p["price"] * q
    return total

def cart_apply_promo(uid, code):
    code = code.upper().strip()
    pct = PROMO_CODES.get(code)
    if pct: _promos[uid] = {"code": code, "discount": pct}; return pct
    return None

def cart_promo(uid): return _promos.get(uid)

def cart_totals(uid):
    sub = cart_subtotal(uid); promo = cart_promo(uid)
    discount = round(sub * promo["discount"] / 100) if promo else 0
    after = sub - discount
    delivery = 0 if after >= FREE_DELIVERY_FROM else DELIVERY_PRICE
    return {"subtotal": sub, "discount": discount, "delivery": delivery, "grand": after + delivery}

def cart_summary(uid):
    items = cart_items(uid)
    if not items: return "🛒 Savatcha bo'sh"
    t = cart_totals(uid); promo = cart_promo(uid)
    lines = ["🛒 *Savatchangizdagi mahsulotlar:*\n"]
    for pid, (name, price, q) in items.items():
        lines.append(f"  • {name} × {q} = *{fmt(price*q)}*")
    lines.append(f"\n📦 Jami: {fmt(t['subtotal'])}")
    if t["discount"]: lines.append(f"🏷️ Chegirma ({promo['code']} -{promo['discount']}%): *-{fmt(t['discount'])}*")
    lines.append(f"🚚 Yetkazish: {'*Bepul* 🎁' if t['delivery']==0 else fmt(t['delivery'])}")
    lines.append(f"\n💰 *To'lash kerak: {fmt(t['grand'])}*")
    return "\n".join(lines)

# ══════════════════════════════════════════════
#  🔄 STATE MACHINE
# ══════════════════════════════════════════════
_states = {}
WAIT_PHONE="wait_phone"; WAIT_ADDRESS="wait_address"; WAIT_NOTE="wait_note"
WAIT_SEARCH="wait_search"; WAIT_PROMO="wait_promo"
WAIT_REVIEW="wait_review"; WAIT_BROADCAST="wait_broadcast"

def st_set(uid, state, **data): _states[uid] = {"state": state, "data": data}
def st_get(uid): return _states.get(uid, {}).get("state")
def st_data(uid): return _states.get(uid, {}).get("data", {})
def st_clear(uid): _states.pop(uid, None)
def st_update(uid, **kw):
    if uid not in _states: _states[uid] = {"state": None, "data": {}}
    _states[uid]["data"].update(kw)

# ══════════════════════════════════════════════
#  ⌨️ KLAVIATURALAR
# ══════════════════════════════════════════════
def kb_main(uid):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🏪 Katalog"), KeyboardButton("🔍 Qidirish"))
    kb.row(KeyboardButton("🛒 Savatcha"), KeyboardButton("❤️ Sevimlilar"))
    kb.row(KeyboardButton("📦 Buyurtmalarim"), KeyboardButton("👤 Profilim"))
    kb.row(KeyboardButton("📞 Aloqa"), KeyboardButton("ℹ️ Yordam"))
    if uid in ADMIN_IDS:
        kb.row(KeyboardButton("📊 Statistika"), KeyboardButton("📋 Buyurtmalar"))
        kb.add(KeyboardButton("📢 Xabar yuborish"))
    return kb

def kb_phone():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Raqamimni yuborish", request_contact=True))
    kb.add(KeyboardButton("🔙 Bekor qilish"))
    return kb

def kb_location():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📍 Joylashuvimni yuborish", request_location=True))
    kb.add(KeyboardButton("✏️ Manzilni qo'lda kiritish"))
    kb.add(KeyboardButton("🔙 Bekor qilish"))
    return kb

def kb_cats(cats):
    kb = InlineKeyboardMarkup(row_width=2)
    btns = [InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"cat:{c['id']}") for c in cats]
    kb.add(*btns)
    kb.add(InlineKeyboardButton("🔥 Ommabop", callback_data="popular:0"))
    return kb

def kb_products(products, page, total, back_data):
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        disc = ""
        if p.get("old_price") and p["old_price"] > p["price"]:
            pct = round((p["old_price"]-p["price"])/p["old_price"]*100)
            disc = f" 🏷-{pct}%"
        warn = " ⚠️az" if 0 < p["stock"] <= 5 else ""
        kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} — {fmt(p['price'])}{disc}{warn}", callback_data=f"prod:{p['id']}"))
    total_pages = math.ceil(total / PRODUCTS_PER_PAGE)
    if total_pages > 1:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"{back_data}:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"{back_data}:{page+1}"))
        kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Kategoriyalar", callback_data="back:cats"))
    return kb

def kb_product(p, qty, in_wish):
    kb = InlineKeyboardMarkup()
    pid = p["id"]
    if qty == 0:
        if p["stock"] > 0: kb.add(InlineKeyboardButton("🛒 Savatchaga qo'shish", callback_data=f"cart_add:{pid}"))
        else: kb.add(InlineKeyboardButton("❌ Sotib bo'lindi", callback_data="noop"))
    else:
        kb.row(InlineKeyboardButton("➖", callback_data=f"cart_dec:{pid}"),
               InlineKeyboardButton(f"🛒 {qty} ta", callback_data="noop"),
               InlineKeyboardButton("➕", callback_data=f"cart_inc:{pid}"))
    heart = "❤️ Sevimlilardan olib tashlash" if in_wish else "🤍 Sevimlilarga qo'shish"
    kb.add(InlineKeyboardButton(heart, callback_data=f"wish:{pid}"))
    kb.add(InlineKeyboardButton("💬 Sharhlar", callback_data=f"reviews:{pid}:0"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data=f"prod_back:{p['category_id']}"))
    return kb

def kb_cart(items, t):
    kb = InlineKeyboardMarkup(row_width=3)
    for pid, (name, price, q) in items.items():
        kb.add(InlineKeyboardButton(f"🗑 {name[:20]} x{q}", callback_data=f"cart_rm:{pid}"))
        kb.row(InlineKeyboardButton("➖", callback_data=f"cart_dec:{pid}"),
               InlineKeyboardButton(f"{q} ta", callback_data="noop"),
               InlineKeyboardButton("➕", callback_data=f"cart_inc:{pid}"))
    kb.add(InlineKeyboardButton("🏷️ Promo kod", callback_data="promo:enter"))
    kb.add(InlineKeyboardButton("🗑️ Tozalash", callback_data="cart_clear"))
    kb.add(InlineKeyboardButton(f"✅ Buyurtma berish — {fmt(t['grand'])}", callback_data="checkout:start"))
    return kb

def kb_delivery():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚚 Yetkazib berish", callback_data="delivery:courier"))
    kb.add(InlineKeyboardButton("🏪 O'zimiz olib ketamiz", callback_data="delivery:pickup"))
    kb.add(InlineKeyboardButton("🔙 Savatchaga qaytish", callback_data="back:cart"))
    return kb

def kb_note():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➡️ Izohsiz davom etish", callback_data="order:no_note"))
    return kb

def kb_confirm():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Tasdiqlash", callback_data="order:confirm"))
    kb.add(InlineKeyboardButton("✏️ O'zgartirish", callback_data="order:edit"))
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="order:cancel_pre"))
    return kb

def kb_orders(orders):
    kb = InlineKeyboardMarkup()
    for o in orders:
        e, l = ORDER_STATUSES.get(o["status"], ("📦", o["status"]))
        kb.add(InlineKeyboardButton(f"{e} #{o['id']} — {fmt(o['total'])} ({l})", callback_data=f"order_view:{o['id']}"))
    kb.add(InlineKeyboardButton("🔙 Bosh menyu", callback_data="back:main"))
    return kb

def kb_order_detail(order):
    kb = InlineKeyboardMarkup()
    if order["status"] == "new": kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data=f"order_cancel:{order['id']}"))
    if order["status"] == "delivered": kb.add(InlineKeyboardButton("⭐ Baho berish", callback_data=f"rate_order:{order['id']}"))
    kb.add(InlineKeyboardButton("🔄 Qayta buyurtma", callback_data=f"reorder:{order['id']}"))
    kb.add(InlineKeyboardButton("🔙 Buyurtmalar", callback_data="back:orders"))
    return kb

def kb_rating(order_id, product_id):
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(*[InlineKeyboardButton(f"{i}⭐", callback_data=f"review_rate:{order_id}:{product_id}:{i}") for i in range(1,6)])
    kb.add(InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data=f"review_skip:{order_id}"))
    return kb

def kb_reviews(pid, page, total):
    kb = InlineKeyboardMarkup()
    per = 5; total_pages = math.ceil(total/per) if total else 1
    if total_pages > 1:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"reviews:{pid}:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"reviews:{pid}:{page+1}"))
        if nav: kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Mahsulotga qaytish", callback_data=f"prod:{pid}"))
    return kb

def kb_admin_order(order_id, cur_status):
    kb = InlineKeyboardMarkup(row_width=2)
    btns = [InlineKeyboardButton(f"{e} {l}", callback_data=f"adm_status:{order_id}:{s}")
            for s,(e,l) in ORDER_STATUSES.items() if s != cur_status]
    kb.add(*btns); return kb

def kb_admin_filter():
    kb = InlineKeyboardMarkup(row_width=2)
    btns = [InlineKeyboardButton(f"{e} {l}", callback_data=f"adm_orders:{s}") for s,(e,l) in ORDER_STATUSES.items()]
    btns.append(InlineKeyboardButton("📋 Hammasi", callback_data="adm_orders:all"))
    kb.add(*btns); return kb

def kb_profile():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📱 Telefon o'zgartirish", callback_data="profile:phone"))
    kb.add(InlineKeyboardButton("❤️ Sevimlilarim", callback_data="back:wish"))
    kb.add(InlineKeyboardButton("📦 Buyurtmalarim", callback_data="back:orders"))
    return kb

# ══════════════════════════════════════════════
#  🤖 BOT
# ══════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

def is_admin(uid): return uid in ADMIN_IDS

def send_main(chat_id, uid, text="Asosiy menyu:"):
    bot.send_message(chat_id, text, reply_markup=kb_main(uid))

def fmt_product(p):
    lines = [f"{p['emoji']} *{p['name']}*"]
    if p.get("old_price") and p["old_price"] > p["price"]:
        pct = round((p["old_price"]-p["price"])/p["old_price"]*100)
        lines.append(f"💰 Narx: *{fmt(p['price'])}* ~~{fmt(p['old_price'])}~~ 🏷️ -{pct}%")
    else:
        lines.append(f"💰 Narx: *{fmt(p['price'])}*")
    if p.get("description"): lines.append(f"\n📝 {p['description']}")
    if p["stock"] == 0: lines.append("❌ *Sotib bo'lindi*")
    elif p["stock"] <= 5: lines.append(f"⚠️ Qoldi: *{p['stock']} ta*")
    if p.get("review_count",0) > 0:
        lines.append(f"\n{'⭐'*round(p['rating'])} {p['rating']}/5 ({p['review_count']} sharh)")
    if p.get("sold_count",0) > 0: lines.append(f"📦 {p['sold_count']} ta sotilgan")
    return "\n".join(lines)

def notify_admin(text):
    for aid in ADMIN_IDS:
        try: bot.send_message(aid, text)
        except: pass

def order_card(order, for_admin=False):
    items = json.loads(order["items"])
    e, l = ORDER_STATUSES.get(order["status"], ("📦", order["status"]))
    lines = [f"📦 *Buyurtma #{order['id']}*\n", f"Status: {e} *{l}*", f"📅 {order['created_at'][:16]}\n", "*Mahsulotlar:*"]
    for pid, qty in items.items():
        p = db_get_product(int(pid))
        if p: lines.append(f"  • {p['emoji']} {p['name']} × {qty} = {fmt(p['price']*qty)}")
    lines.append(f"\n💰 {fmt(order['total'])}")
    if order.get("discount"): lines.append(f"🏷️ -{fmt(order['discount'])}")
    lines.append(f"🚚 {fmt(order['delivery'])}")
    grand = order["total"] - (order.get("discount") or 0) + order["delivery"]
    lines.append(f"💳 *{fmt(grand)}*")
    if order.get("address"): lines.append(f"\n📍 {order['address']}")
    if order.get("phone"): lines.append(f"📱 {order['phone']}")
    if order.get("note"): lines.append(f"📝 {order['note']}")
    if for_admin: lines.append(f"\n👤 `{order['user_id']}`")
    return "\n".join(lines)

def show_products(message, cat_id=None, popular=False, search=None, page=0, title=None):
    per = PRODUCTS_PER_PAGE
    products = db_get_products(cat_id=cat_id, popular=popular, search=search, offset=page*per, limit=per)
    total = db_count_products(cat_id=cat_id, popular=popular, search=search)
    if not products:
        try: bot.edit_message_text("😔 Mahsulot topilmadi.", message.chat.id, message.id,
                                   reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙", callback_data="back:cats")))
        except: bot.send_message(message.chat.id, "😔 Mahsulot topilmadi.")
        return
    if not title:
        cats = db_get_cats()
        cat = next((c for c in cats if c["id"] == cat_id), None)
        title = f"{cat['emoji']} {cat['name']}" if cat else "Mahsulotlar"
    back_data = f"cat:{cat_id}" if cat_id else ("popular" if popular else f"search:{search}")
    text = f"*{title}* — {total} ta mahsulot"
    try: bot.edit_message_text(text, message.chat.id, message.id, reply_markup=kb_products(products, page, total, back_data))
    except: bot.send_message(message.chat.id, text, reply_markup=kb_products(products, page, total, back_data))

def refresh_cart(chat_id, uid, mid=None):
    if cart_empty(uid):
        text = "🛒 Savatchangiz bo'sh.\n\nKatalogdan mahsulot tanlang!"
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🏪 Katalog", callback_data="back:cats"))
        if mid:
            try: bot.edit_message_text(text, chat_id, mid, reply_markup=markup); return
            except: pass
        bot.send_message(chat_id, text, reply_markup=markup); return
    items = cart_items(uid); t = cart_totals(uid)
    text = cart_summary(uid); markup = kb_cart(items, t)
    if mid:
        try: bot.edit_message_text(text, chat_id, mid, reply_markup=markup); return
        except: pass
    bot.send_message(chat_id, text, reply_markup=markup)

def ask_phone_or_note(chat_id, uid):
    user = db_get_user(uid)
    if not user or not user.get("phone"):
        st_update(uid, next_step="note")
        bot.send_message(chat_id, "📱 *Telefon raqamingizni yuboring:*", reply_markup=kb_phone())
    else:
        bot.send_message(chat_id, "📝 *Izoh qo'shmoqchimisiz?*\n_(masalan: rang, o'lcham)_", reply_markup=kb_note())

def show_order_confirm(chat_id, uid):
    data = st_data(uid); user = db_get_user(uid); t = cart_totals(uid)
    items = cart_items(uid); promo = cart_promo(uid)
    lines = ["✅ *Buyurtmani tasdiqlang:*\n", "*Mahsulotlar:*"]
    for pid, (name, price, q) in items.items():
        lines.append(f"  • {name} × {q} = {fmt(price*q)}")
    lines.append(f"\n💰 {fmt(t['subtotal'])}")
    if t["discount"]: lines.append(f"🏷️ -{fmt(t['discount'])}")
    lines.append(f"🚚 {fmt(t['delivery'])}")
    lines.append(f"💳 *{fmt(t['grand'])}*")
    lines.append(f"\n📍 {data.get('address','—')}")
    lines.append(f"📱 {data.get('phone') or (user.get('phone') if user else '—')}")
    if data.get("note"): lines.append(f"📝 {data['note']}")
    bot.send_message(chat_id, "\n".join(lines), reply_markup=kb_confirm())

def place_order(chat_id, uid):
    data = st_data(uid); user = db_get_user(uid)
    items = cart_items(uid); t = cart_totals(uid); promo = cart_promo(uid)
    phone = data.get("phone") or (user.get("phone","") if user else "")
    items_dict = {pid: q for pid,(_,_,q) in items.items()}
    oid = db_create_order(uid, items_dict, t["subtotal"], t["delivery"],
                          data.get("address",""), phone,
                          promo["code"] if promo else "", t["discount"], data.get("note",""))
    order = db_get_order(oid)
    fname = user["full_name"] if user else str(uid)
    for aid in ADMIN_IDS:
        try: bot.send_message(aid, f"🆕 *Yangi buyurtma!*\n\n{order_card(order, for_admin=True)}\n\n👤 [{fname}](tg://user?id={uid})",
                              reply_markup=kb_admin_order(oid, "new"))
        except: pass
    cart_clear(uid); st_clear(uid)
    bot.send_message(chat_id,
        f"🎉 *Buyurtmangiz qabul qilindi!*\n\n📦 Buyurtma: *#{oid}*\n💰 *{fmt(t['grand'])}*\n\nOperator tez orada bog'lanadi 🙏",
        reply_markup=kb_main(uid))

# ══════════════════════════════════════════════
#  📩 HANDLERLAR
# ══════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def on_start(msg):
    uid = msg.from_user.id
    db_upsert_user(uid, msg.from_user.username or "", f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip())
    st_clear(uid)
    send_main(msg.chat.id, uid,
        f"Assalomu alaykum, *{msg.from_user.first_name}*! 👋\n\n"
        f"🏪 *{SHOP_NAME}* ga xush kelibsiz!\n\n"
        "🏪 Katalog • 🔍 Qidirish • 🛒 Savatcha\n❤️ Sevimlilar • 📦 Buyurtmalar • 👤 Profil")

@bot.message_handler(commands=["cancel"])
def on_cancel(msg):
    st_clear(msg.from_user.id); send_main(msg.chat.id, msg.from_user.id, "❌ Bekor qilindi.")

@bot.message_handler(commands=["skip"])
def on_skip(msg):
    uid = msg.from_user.id
    if st_get(uid) == WAIT_REVIEW:
        d = st_data(uid); db_add_review(uid, d["pid"], d["oid"], d["rating"], ""); st_clear(uid)
        bot.send_message(msg.chat.id, "✅ Baholandi! Rahmat! 🙏")

@bot.message_handler(func=lambda m: m.text == "🏪 Katalog")
def on_catalog(msg):
    st_clear(msg.from_user.id)
    bot.send_message(msg.chat.id, "📂 *Kategoriyani tanlang:*", reply_markup=kb_cats(db_get_cats()))

@bot.message_handler(func=lambda m: m.text == "🔍 Qidirish")
def on_search(msg):
    st_set(msg.from_user.id, WAIT_SEARCH)
    bot.send_message(msg.chat.id, "🔍 Mahsulot nomini kiriting:")

@bot.message_handler(func=lambda m: m.text == "🛒 Savatcha")
def on_cart(msg): refresh_cart(msg.chat.id, msg.from_user.id)

@bot.message_handler(func=lambda m: m.text == "❤️ Sevimlilar")
def on_wish(msg):
    uid = msg.from_user.id; items = db_get_wish(uid)
    if not items: bot.send_message(msg.chat.id, "🤍 Sevimlilar bo'sh.\n\nMahsulot sahifasida 🤍 tugmasini bosing!"); return
    kb = InlineKeyboardMarkup()
    for p in items: kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} — {fmt(p['price'])}", callback_data=f"prod:{p['id']}"))
    bot.send_message(msg.chat.id, f"❤️ *Sevimlilaringiz* ({len(items)} ta):", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📦 Buyurtmalarim")
def on_orders(msg):
    uid = msg.from_user.id; orders = db_get_orders(uid)
    if not orders: bot.send_message(msg.chat.id, "📦 Hali buyurtma bermagansiz."); return
    bot.send_message(msg.chat.id, f"📦 *Buyurtmalaringiz* ({len(orders)} ta):", reply_markup=kb_orders(orders))

@bot.message_handler(func=lambda m: m.text == "👤 Profilim")
def on_profile(msg):
    uid = msg.from_user.id; user = db_get_user(uid)
    if not user: return
    bot.send_message(msg.chat.id,
        f"👤 *Profilingiz*\n\n🆔 `{uid}`\n👤 {user['full_name']}\n"
        f"📱 {user.get('phone') or 'Kiritilmagan'}\n📅 {user['joined_at'][:10]}\n\n"
        f"📦 Buyurtmalar: *{user['total_orders']}*\n💰 Jami: *{fmt(user['total_spent'])}*\n❤️ Sevimlilar: *{len(db_get_wish(uid))}* ta",
        reply_markup=kb_profile())

@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def on_contact(msg):
    bot.send_message(msg.chat.id, f"📞 *Biz bilan bog'laning:*\n\n💬 {SUPPORT}\n📱 +998 90 123 45 67\n🕐 9:00—22:00")

@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def on_help(msg):
    bot.send_message(msg.chat.id,
        f"ℹ️ *Yordam*\n\n🏪 Katalog • 🔍 Qidirish\n🛒 Savatcha • ❤️ Sevimlilar\n📦 Buyurtmalar • 👤 Profil\n\n❓ {SUPPORT}")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.from_user.id in ADMIN_IDS)
def on_stats(msg):
    s = db_stats()
    bot.send_message(msg.chat.id,
        f"📊 *Statistika*\n\n👥 Foydalanuvchilar: *{s['users']}*\n📦 Buyurtmalar: *{s['orders']}*\n"
        f"🆕 Yangi: *{s['new_orders']}*\n📅 Bugun: *{s['today']}*\n💰 Daromad: *{fmt(s['revenue'])}*")

@bot.message_handler(func=lambda m: m.text == "📋 Buyurtmalar" and m.from_user.id in ADMIN_IDS)
def on_admin_orders(msg):
    bot.send_message(msg.chat.id, "📋 *Qaysi status?*", reply_markup=kb_admin_filter())

@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish" and m.from_user.id in ADMIN_IDS)
def on_broadcast(msg):
    st_set(msg.from_user.id, WAIT_BROADCAST)
    bot.send_message(msg.chat.id, "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")

@bot.message_handler(content_types=["contact"])
def on_contact_msg(msg):
    uid = msg.from_user.id; phone = msg.contact.phone_number
    db_set_phone(uid, phone); st_update(uid, phone=phone)
    d = st_data(uid)
    if d.get("context") == "profile":
        st_clear(uid); bot.send_message(msg.chat.id, f"✅ Telefon yangilandi: {phone}", reply_markup=kb_main(uid))
    elif d.get("next_step") == "note":
        bot.send_message(msg.chat.id, "📝 *Izoh qo'shmoqchimisiz?*", reply_markup=kb_note())
    else:
        bot.send_message(msg.chat.id, f"✅ Raqam saqlandi: {phone}", reply_markup=kb_main(uid))

@bot.message_handler(content_types=["location"])
def on_location(msg):
    uid = msg.from_user.id
    if st_get(uid) == WAIT_ADDRESS:
        st_update(uid, address=f"📍 {msg.location.latitude:.4f}, {msg.location.longitude:.4f}")
        ask_phone_or_note(msg.chat.id, uid)

@bot.message_handler(content_types=["text"])
def on_text(msg):
    uid = msg.from_user.id; text = msg.text.strip(); state = st_get(uid)
    if state == WAIT_SEARCH:
        st_clear(uid); total = db_count_products(search=text)
        if total == 0: bot.send_message(msg.chat.id, f"😔 *'{text}'* bo'yicha hech narsa topilmadi.", reply_markup=kb_cats(db_get_cats())); return
        bot.send_message(msg.chat.id, f"🔍 *'{text}'* — {total} ta natija:",
                         reply_markup=kb_products(db_get_products(search=text, limit=PRODUCTS_PER_PAGE), 0, total, f"search:{text}"))
    elif state == WAIT_PROMO:
        st_clear(uid); pct = cart_apply_promo(uid, text)
        bot.send_message(msg.chat.id, f"✅ Promo kod! *-{pct}%* 🎉" if pct else "❌ Promo kod noto'g'ri.")
        refresh_cart(msg.chat.id, uid)
    elif state == WAIT_ADDRESS:
        if text == "🔙 Bekor qilish": st_clear(uid); refresh_cart(msg.chat.id, uid); return
        if text == "✏️ Manzilni qo'lda kiritish": bot.send_message(msg.chat.id, "📍 Manzilingizni kiriting:"); return
        st_update(uid, address=text); ask_phone_or_note(msg.chat.id, uid)
    elif state == WAIT_NOTE:
        if text == "🔙 Bekor qilish": st_clear(uid); refresh_cart(msg.chat.id, uid); return
        st_update(uid, note=text); show_order_confirm(msg.chat.id, uid)
    elif state == WAIT_REVIEW:
        d = st_data(uid); db_add_review(uid, d["pid"], d["oid"], d["rating"], text); st_clear(uid)
        bot.send_message(msg.chat.id, "⭐ Sharhingiz uchun rahmat! 🙏", reply_markup=kb_main(uid))
    elif state == WAIT_BROADCAST and is_admin(uid):
        st_clear(uid); users = db_all_users(); sent = 0
        for user_id in users:
            try: bot.send_message(user_id, f"📢 *{SHOP_NAME}:*\n\n{text}"); sent += 1
            except: pass
        bot.send_message(msg.chat.id, f"✅ *{sent}* foydalanuvchiga yuborildi.")

# ══════════════════════════════════════════════
#  📲 CALLBACK HANDLERLAR
# ══════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "noop")
def cb_noop(call): bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "back:cats")
def cb_back_cats(call):
    bot.answer_callback_query(call.id)
    try: bot.edit_message_text("📂 *Kategoriyani tanlang:*", call.message.chat.id, call.message.id, reply_markup=kb_cats(db_get_cats()))
    except: bot.send_message(call.message.chat.id, "📂 *Kategoriyani tanlang:*", reply_markup=kb_cats(db_get_cats()))

@bot.callback_query_handler(func=lambda c: c.data == "back:main")
def cb_back_main(call): bot.answer_callback_query(call.id); send_main(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data == "back:cart")
def cb_back_cart(call): bot.answer_callback_query(call.id); refresh_cart(call.message.chat.id, call.from_user.id, call.message.id)

@bot.callback_query_handler(func=lambda c: c.data == "back:orders")
def cb_back_orders(call):
    bot.answer_callback_query(call.id); uid = call.from_user.id; orders = db_get_orders(uid)
    if not orders: bot.edit_message_text("📦 Buyurtma yo'q.", call.message.chat.id, call.message.id); return
    bot.edit_message_text(f"📦 *Buyurtmalaringiz* ({len(orders)} ta):", call.message.chat.id, call.message.id, reply_markup=kb_orders(orders))

@bot.callback_query_handler(func=lambda c: c.data == "back:wish")
def cb_back_wish(call):
    bot.answer_callback_query(call.id); uid = call.from_user.id; items = db_get_wish(uid)
    if not items: bot.edit_message_text("🤍 Sevimlilar bo'sh.", call.message.chat.id, call.message.id); return
    kb = InlineKeyboardMarkup()
    for p in items: kb.add(InlineKeyboardButton(f"{p['emoji']} {p['name']} — {fmt(p['price'])}", callback_data=f"prod:{p['id']}"))
    bot.edit_message_text(f"❤️ *Sevimlilaringiz* ({len(items)} ta):", call.message.chat.id, call.message.id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat:"))
def cb_cat(call):
    bot.answer_callback_query(call.id); parts = call.data.split(":")
    cat_id = int(parts[1]); page = int(parts[2]) if len(parts) > 2 else 0
    show_products(call.message, cat_id=cat_id, page=page)

@bot.callback_query_handler(func=lambda c: c.data.startswith("popular:"))
def cb_popular(call):
    bot.answer_callback_query(call.id)
    show_products(call.message, popular=True, page=int(call.data.split(":")[1]), title="🔥 Ommabop")

@bot.callback_query_handler(func=lambda c: c.data.startswith("prod:"))
def cb_prod(call):
    pid = int(call.data.split(":")[1]); uid = call.from_user.id; p = db_get_product(pid)
    if not p: bot.answer_callback_query(call.id, "Topilmadi"); return
    bot.answer_callback_query(call.id); text = fmt_product(p)
    try: bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb_product(p, cart_qty(uid,pid), db_in_wish(uid,pid)))
    except: bot.send_message(call.message.chat.id, text, reply_markup=kb_product(p, cart_qty(uid,pid), db_in_wish(uid,pid)))

@bot.callback_query_handler(func=lambda c: c.data.startswith("prod_back:"))
def cb_prod_back(call):
    bot.answer_callback_query(call.id); show_products(call.message, cat_id=int(call.data.split(":")[1]), page=0)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cart_add:"))
def cb_cart_add(call):
    pid = int(call.data.split(":")[1]); uid = call.from_user.id; ok = cart_add(uid, pid)
    bot.answer_callback_query(call.id, "✅ Savatchaga qo'shildi!" if ok else "❌ Sotib bo'lindi")
    p = db_get_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=kb_product(p, cart_qty(uid,pid), db_in_wish(uid,pid)))
        except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("cart_inc:"))
def cb_cart_inc(call):
    pid = int(call.data.split(":")[1]); uid = call.from_user.id; cart_inc(uid, pid); bot.answer_callback_query(call.id)
    p = db_get_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=kb_product(p, cart_qty(uid,pid), db_in_wish(uid,pid)))
        except: refresh_cart(call.message.chat.id, uid, call.message.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cart_dec:"))
def cb_cart_dec(call):
    pid = int(call.data.split(":")[1]); uid = call.from_user.id; cart_dec(uid, pid); bot.answer_callback_query(call.id)
    p = db_get_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=kb_product(p, cart_qty(uid,pid), db_in_wish(uid,pid)))
        except: refresh_cart(call.message.chat.id, uid, call.message.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cart_rm:"))
def cb_cart_rm(call):
    cart_rm(call.from_user.id, call.data.split(":")[1]); bot.answer_callback_query(call.id, "🗑️ O'chirildi")
    refresh_cart(call.message.chat.id, call.from_user.id, call.message.id)

@bot.callback_query_handler(func=lambda c: c.data == "cart_clear")
def cb_cart_clear(call):
    cart_clear(call.from_user.id); bot.answer_callback_query(call.id, "🗑️ Tozalandi")
    refresh_cart(call.message.chat.id, call.from_user.id, call.message.id)

@bot.callback_query_handler(func=lambda c: c.data == "promo:enter")
def cb_promo(call):
    st_set(call.from_user.id, WAIT_PROMO); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🏷️ Promo kodingizni kiriting:")

@bot.callback_query_handler(func=lambda c: c.data == "checkout:start")
def cb_checkout(call):
    uid = call.from_user.id
    if cart_empty(uid): bot.answer_callback_query(call.id, "Savatcha bo'sh!", show_alert=True); return
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "🚚 *Yetkazib berish usuli:*", reply_markup=kb_delivery())

@bot.callback_query_handler(func=lambda c: c.data.startswith("delivery:"))
def cb_delivery_cb(call):
    uid = call.from_user.id; method = call.data.split(":")[1]; bot.answer_callback_query(call.id)
    if method == "back": refresh_cart(call.message.chat.id, uid, call.message.id); return
    st_set(uid, WAIT_ADDRESS, method=method)
    if method == "courier":
        bot.send_message(call.message.chat.id, "📍 *Yetkazib berish manzilini kiriting:*", reply_markup=kb_location())
    else:
        st_update(uid, address="O'zimiz olib ketamiz"); ask_phone_or_note(call.message.chat.id, uid)

@bot.callback_query_handler(func=lambda c: c.data == "order:no_note")
def cb_no_note(call):
    st_update(call.from_user.id, note=""); bot.answer_callback_query(call.id)
    show_order_confirm(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data == "order:confirm")
def cb_confirm(call): bot.answer_callback_query(call.id); place_order(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data == "order:edit")
def cb_edit(call): bot.answer_callback_query(call.id); refresh_cart(call.message.chat.id, call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data == "order:cancel_pre")
def cb_cancel_pre(call):
    st_clear(call.from_user.id); bot.answer_callback_query(call.id, "Bekor qilindi")
    send_main(call.message.chat.id, call.from_user.id, "❌ Bekor qilindi.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("order_view:"))
def cb_order_view(call):
    oid = int(call.data.split(":")[1]); order = db_get_order(oid); bot.answer_callback_query(call.id)
    if not order: return
    text = order_card(order)
    try: bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb_order_detail(order))
    except: bot.send_message(call.message.chat.id, text, reply_markup=kb_order_detail(order))

@bot.callback_query_handler(func=lambda c: c.data.startswith("order_cancel:"))
def cb_order_cancel(call):
    oid = int(call.data.split(":")[1]); order = db_get_order(oid)
    if order and order["status"] == "new":
        db_update_status(oid, "cancelled"); bot.answer_callback_query(call.id, "❌ Bekor qilindi")
        notify_admin(f"❌ Buyurtma #{oid} bekor qilindi")
        try: bot.edit_message_text(order_card(db_get_order(oid)), call.message.chat.id, call.message.id, reply_markup=kb_order_detail(db_get_order(oid)))
        except: pass
    else: bot.answer_callback_query(call.id, "Bekor qilib bo'lmaydi", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("reorder:"))
def cb_reorder(call):
    oid = int(call.data.split(":")[1]); order = db_get_order(oid); uid = call.from_user.id
    if order:
        for pid, qty in json.loads(order["items"]).items():
            for _ in range(qty): cart_add(uid, int(pid))
        bot.answer_callback_query(call.id, "✅ Savatchaga qo'shildi!")
        refresh_cart(call.message.chat.id, uid)
    else: bot.answer_callback_query(call.id, "Topilmadi")

@bot.callback_query_handler(func=lambda c: c.data.startswith("wish:"))
def cb_wish(call):
    pid = int(call.data.split(":")[1]); uid = call.from_user.id; added = db_toggle_wish(uid, pid)
    bot.answer_callback_query(call.id, "❤️ Qo'shildi!" if added else "🤍 O'chirildi")
    p = db_get_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=kb_product(p, cart_qty(uid,pid), added))
        except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("reviews:"))
def cb_reviews(call):
    parts = call.data.split(":"); pid = int(parts[1]); page = int(parts[2])
    bot.answer_callback_query(call.id); p = db_get_product(pid)
    if not p: return
    reviews = db_get_reviews(pid)
    if not reviews: text = f"💬 *{p['name']}* uchun hali sharh yo'q."
    else:
        text = f"💬 *{p['name']}*\n{'⭐'*round(p['rating'])} {p['rating']}/5\n\n"
        for r in reviews:
            text += f"{'⭐'*r['rating']} *{r['full_name']}*\n"
            if r.get("text"): text += f"_{r['text']}_\n"
            text += f"📅 {r['created_at'][:10]}\n\n"
    try: bot.edit_message_text(text, call.message.chat.id, call.message.id, reply_markup=kb_reviews(pid, page, p["review_count"]))
    except: bot.send_message(call.message.chat.id, text, reply_markup=kb_reviews(pid, page, p["review_count"]))

@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_order:"))
def cb_rate(call):
    oid = int(call.data.split(":")[1]); order = db_get_order(oid)
    if not order: bot.answer_callback_query(call.id); return
    items = json.loads(order["items"]); pid = int(list(items.keys())[0])
    p = db_get_product(pid); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"⭐ *{p['name']}* ga baho bering:", reply_markup=kb_rating(oid, pid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("review_rate:"))
def cb_review_rate(call):
    _, oid, pid, rating = call.data.split(":"); uid = call.from_user.id
    st_set(uid, WAIT_REVIEW, oid=int(oid), pid=int(pid), rating=int(rating)); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"{'⭐'*int(rating)} Sharhingizni yozing:\n_(/skip — o'tkazib yuborish)_")

@bot.callback_query_handler(func=lambda c: c.data.startswith("review_skip:"))
def cb_review_skip(call):
    st_clear(call.from_user.id); bot.answer_callback_query(call.id, "O'tkazib yuborildi")
    bot.send_message(call.message.chat.id, "Rahmat! 🙏")

@bot.callback_query_handler(func=lambda c: c.data == "profile:phone")
def cb_profile_phone(call):
    st_set(call.from_user.id, WAIT_PHONE, context="profile"); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "📱 Yangi raqamingizni yuboring:", reply_markup=kb_phone())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_orders:") and c.from_user.id in ADMIN_IDS)
def cb_adm_orders(call):
    status = call.data.split(":")[1]; bot.answer_callback_query(call.id)
    orders = db_all_orders(status=None if status=="all" else status)
    if not orders: bot.edit_message_text("📋 Buyurtmalar yo'q.", call.message.chat.id, call.message.id); return
    bot.edit_message_text(f"📋 *Buyurtmalar* ({len(orders)} ta):", call.message.chat.id, call.message.id, reply_markup=kb_orders(orders))

@bot.callback_query_handler(func=lambda c: c.data.startswith("adm_status:") and c.from_user.id in ADMIN_IDS)
def cb_adm_status(call):
    _, oid, new_status = call.data.split(":"); oid = int(oid)
    db_update_status(oid, new_status); bot.answer_callback_query(call.id, "✅ Status yangilandi")
    order = db_get_order(oid); e, l = ORDER_STATUSES.get(new_status, ("📦", new_status))
    try: bot.send_message(order["user_id"], f"{e} *Buyurtma #{oid}:* *{l}*\n\n📦 Buyurtmalarim bo'limida ko'ring.")
    except: pass
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=kb_admin_order(oid, new_status))
    except: pass

# ══════════════════════════════════════════════
#  ▶️ ISHGA TUSHIRISH
# ══════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    print(f"✅ {SHOP_NAME} boti ishga tushdi!")
    print(f"📋 Admin IDs: {ADMIN_IDS}")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
