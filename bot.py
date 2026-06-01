"""
🏪 KIYIM DO'KON BOT — bitta fayl
Kategoriyalar: Erkaklar kiyimi | Ayollar kiyimi | Poyabzal
Admin panel: mahsulot qo'shish/o'chirish, buyurtma boshqaruvi
"""
import os, sys, json, math, sqlite3
import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)

# ══════════════════════════════════════════════════════
#  ⚙️  SOZLAMALAR
# ══════════════════════════════════════════════════════
BOT_TOKEN  = os.environ.get("BOT_TOKEN", "8994441380:AAGlT8IxUSsEWv8MeRPfUNeSOv1O-KdqylA")
ADMIN_IDS  = [int(x) for x in os.environ.get("123456789", "5830170101").split(",")]
SHOP_NAME  = os.environ.get("SHOP_NAME", "KiyimShop")
CURRENCY   = "so'm"
SUPPORT    = os.environ.get("SUPPORT", "@nokta_shop_admin")
DELIVERY_PRICE     = 15_000
FREE_DELIVERY_FROM = 500_000
PER_PAGE           = 5
PROMO_CODES        = {"YANGI10": 10, "SALE20": 20, "VIP30": 30}

CATEGORIES = {
    1: ("👔", "Erkaklar kiyimi"),
    2: ("👗", "Ayollar kiyimi"),
    3: ("👟", "Poyabzal"),
}

# ══════════════════════════════════════════════════════
#  🗄️  DATABASE
# ══════════════════════════════════════════════════════
DB = "shop.db"

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    db = conn(); c = db.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        uid INTEGER PRIMARY KEY, username TEXT, fullname TEXT, phone TEXT,
        joined TEXT DEFAULT(datetime('now')),
        total_orders INTEGER DEFAULT 0, total_spent INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cat_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        desc TEXT DEFAULT '',
        price INTEGER NOT NULL,
        old_price INTEGER DEFAULT 0,
        sizes TEXT DEFAULT '',
        colors TEXT DEFAULT '',
        photo_id TEXT DEFAULT '',
        stock INTEGER DEFAULT 999,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT(datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS wishlist(
        uid INTEGER, pid INTEGER, PRIMARY KEY(uid,pid))""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid INTEGER, items TEXT, subtotal INTEGER,
        discount INTEGER DEFAULT 0, delivery INTEGER DEFAULT 0,
        address TEXT, phone TEXT, status TEXT DEFAULT 'new',
        promo TEXT DEFAULT '', note TEXT DEFAULT '',
        created_at TEXT DEFAULT(datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid INTEGER, pid INTEGER, oid INTEGER,
        stars INTEGER, text TEXT,
        created_at TEXT DEFAULT(datetime('now')))""")
    db.commit(); db.close()

def fmt(n): return f"{n:,} {CURRENCY}".replace(",", " ")

# Users
def db_upsert(uid, uname, fname):
    db = conn()
    db.execute("INSERT INTO users(uid,username,fullname) VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET username=excluded.username,fullname=excluded.fullname", (uid,uname,fname))
    db.commit(); db.close()
def db_user(uid):
    db = conn(); r = db.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone(); db.close()
    return dict(r) if r else None
def db_set_phone(uid, phone):
    db = conn(); db.execute("UPDATE users SET phone=? WHERE uid=?", (phone,uid)); db.commit(); db.close()
def db_all_uids():
    db = conn(); r = db.execute("SELECT uid FROM users").fetchall(); db.close()
    return [x[0] for x in r]

# Products
def db_products(cat_id=None, search=None, offset=0, limit=PER_PAGE):
    w = ["active=1"]; p = []
    if cat_id: w.append("cat_id=?"); p.append(cat_id)
    if search: w.append("name LIKE ?"); p.append(f"%{search}%")
    db = conn()
    r = db.execute(f"SELECT * FROM products WHERE {' AND '.join(w)} ORDER BY id DESC LIMIT ? OFFSET ?", p+[limit,offset]).fetchall()
    db.close(); return [dict(x) for x in r]
def db_count(cat_id=None, search=None):
    w = ["active=1"]; p = []
    if cat_id: w.append("cat_id=?"); p.append(cat_id)
    if search: w.append("name LIKE ?"); p.append(f"%{search}%")
    db = conn(); n = db.execute(f"SELECT COUNT(*) FROM products WHERE {' AND '.join(w)}", p).fetchone()[0]; db.close()
    return n
def db_product(pid):
    db = conn(); r = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone(); db.close()
    return dict(r) if r else None
def db_add_product(cat_id, name, desc, price, old_price, sizes, colors, photo_id, stock):
    db = conn(); c = db.cursor()
    c.execute("INSERT INTO products(cat_id,name,desc,price,old_price,sizes,colors,photo_id,stock) VALUES(?,?,?,?,?,?,?,?,?)",
              (cat_id,name,desc,price,old_price,sizes,colors,photo_id,stock))
    pid = c.lastrowid; db.commit(); db.close(); return pid
def db_del_product(pid):
    db = conn(); db.execute("UPDATE products SET active=0 WHERE id=?", (pid,)); db.commit(); db.close()
def db_all_products_admin(cat_id=None):
    db = conn()
    if cat_id:
        r = db.execute("SELECT * FROM products WHERE cat_id=? ORDER BY active DESC,id DESC", (cat_id,)).fetchall()
    else:
        r = db.execute("SELECT * FROM products ORDER BY active DESC,id DESC LIMIT 50").fetchall()
    db.close(); return [dict(x) for x in r]

# Wishlist
def db_toggle_wish(uid, pid):
    db = conn()
    ex = db.execute("SELECT 1 FROM wishlist WHERE uid=? AND pid=?", (uid,pid)).fetchone()
    if ex: db.execute("DELETE FROM wishlist WHERE uid=? AND pid=?", (uid,pid)); added=False
    else: db.execute("INSERT OR IGNORE INTO wishlist VALUES(?,?)", (uid,pid)); added=True
    db.commit(); db.close(); return added
def db_wish(uid):
    db = conn()
    r = db.execute("SELECT p.* FROM products p JOIN wishlist w ON w.pid=p.id WHERE w.uid=? AND p.active=1", (uid,)).fetchall()
    db.close(); return [dict(x) for x in r]
def db_in_wish(uid, pid):
    db = conn(); r = db.execute("SELECT 1 FROM wishlist WHERE uid=? AND pid=?", (uid,pid)).fetchone(); db.close()
    return bool(r)

# Orders
ORDER_ST = {
    "new":("🆕","Yangi"), "confirmed":("✅","Tasdiqlandi"),
    "preparing":("🔧","Tayyorlanmoqda"), "delivering":("🚚","Yetkazilmoqda"),
    "delivered":("🎉","Yetkazildi"), "cancelled":("❌","Bekor qilindi"),
}
def db_create_order(uid, items, subtotal, discount, delivery, address, phone, promo, note):
    db = conn(); c = db.cursor()
    c.execute("INSERT INTO orders(uid,items,subtotal,discount,delivery,address,phone,promo,note) VALUES(?,?,?,?,?,?,?,?,?)",
              (uid,json.dumps(items),subtotal,discount,delivery,address,phone,promo,note))
    oid = c.lastrowid
    db.execute("UPDATE users SET total_orders=total_orders+1,total_spent=total_spent+? WHERE uid=?", (subtotal,uid))
    db.commit(); db.close(); return oid
def db_orders(uid, limit=10):
    db = conn(); r = db.execute("SELECT * FROM orders WHERE uid=? ORDER BY created_at DESC LIMIT ?", (uid,limit)).fetchall(); db.close()
    return [dict(x) for x in r]
def db_order(oid):
    db = conn(); r = db.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone(); db.close()
    return dict(r) if r else None
def db_set_status(oid, status):
    db = conn(); db.execute("UPDATE orders SET status=? WHERE id=?", (status,oid)); db.commit(); db.close()
def db_all_orders(status=None):
    db = conn()
    if status: r = db.execute("SELECT * FROM orders WHERE status=? ORDER BY created_at DESC LIMIT 30", (status,)).fetchall()
    else: r = db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 30").fetchall()
    db.close(); return [dict(x) for x in r]
def db_stats():
    db = conn()
    s = {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "orders": db.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "new": db.execute("SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0],
        "today": db.execute("SELECT COUNT(*) FROM orders WHERE date(created_at)=date('now')").fetchone()[0],
        "revenue": db.execute("SELECT COALESCE(SUM(subtotal-discount),0) FROM orders WHERE status!='cancelled'").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0],
    }
    db.close(); return s

# Reviews
def db_add_review(uid, pid, oid, stars, text):
    db = conn()
    db.execute("INSERT OR IGNORE INTO reviews(uid,pid,oid,stars,text) VALUES(?,?,?,?,?)", (uid,pid,oid,stars,text))
    db.commit(); db.close()
def db_reviews(pid, limit=5):
    db = conn()
    r = db.execute("SELECT r.*,u.fullname FROM reviews r JOIN users u ON u.uid=r.uid WHERE r.pid=? ORDER BY r.created_at DESC LIMIT ?", (pid,limit)).fetchall()
    db.close(); return [dict(x) for x in r]

# ══════════════════════════════════════════════════════
#  🛒  SAVATCHA
# ══════════════════════════════════════════════════════
_carts = {}
_promos = {}

def c_get(uid): return _carts.setdefault(uid, {})
def c_add(uid, pid):
    p = db_product(pid)
    if not p or not p["active"] or p["stock"] <= 0: return False
    c_get(uid)[str(pid)] = min(c_get(uid).get(str(pid),0)+1, p["stock"]); return True
def c_inc(uid, pid): p=db_product(pid); s=p["stock"] if p else 999; c_get(uid)[str(pid)]=min(c_get(uid).get(str(pid),0)+1,s)
def c_dec(uid, pid):
    s=str(pid); c=c_get(uid)
    if c.get(s,0)>1: c[s]-=1
    else: c.pop(s,None)
def c_rm(uid, pid): c_get(uid).pop(str(pid),None)
def c_clear(uid): _carts[uid]={}; _promos.pop(uid,None)
def c_qty(uid, pid): return c_get(uid).get(str(pid),0)
def c_empty(uid): return not bool(c_get(uid))
def c_items(uid):
    res={}
    for pid,q in c_get(uid).items():
        p=db_product(int(pid))
        if p: res[pid]=(p["name"],p["price"],q)
    return res
def c_sub(uid):
    t=0
    for pid,q in c_get(uid).items():
        p=db_product(int(pid))
        if p: t+=p["price"]*q
    return t
def c_apply_promo(uid, code):
    pct=PROMO_CODES.get(code.upper().strip())
    if pct: _promos[uid]={"code":code.upper(),"pct":pct}; return pct
    return None
def c_promo(uid): return _promos.get(uid)
def c_totals(uid):
    sub=c_sub(uid); pr=c_promo(uid)
    disc=round(sub*pr["pct"]/100) if pr else 0
    after=sub-disc
    deliv=0 if after>=FREE_DELIVERY_FROM else DELIVERY_PRICE
    return {"sub":sub,"disc":disc,"deliv":deliv,"grand":after+deliv}
def c_summary(uid):
    items=c_items(uid)
    if not items: return "🛒 Savatcha bo'sh"
    t=c_totals(uid); pr=c_promo(uid)
    lines=["🛒 *Savatcha:*\n"]
    for pid,(name,price,q) in items.items():
        lines.append(f"  • {name} × {q} = *{fmt(price*q)}*")
    lines.append(f"\n💰 Jami: {fmt(t['sub'])}")
    if t["disc"]: lines.append(f"🏷️ Chegirma (-{pr['pct']}%): *-{fmt(t['disc'])}*")
    lines.append(f"🚚 Yetkazish: {'*Bepul* 🎁' if t['deliv']==0 else fmt(t['deliv'])}")
    lines.append(f"\n💳 *To'lash kerak: {fmt(t['grand'])}*")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════
#  🔄  STATES
# ══════════════════════════════════════════════════════
_st = {}
# Mijoz states
S_SEARCH="search"; S_PHONE="phone"; S_ADDRESS="address"; S_NOTE="note"
S_PROMO="promo"; S_REVIEW="review"
# Admin states
A_NAME="a_name"; A_DESC="a_desc"; A_PRICE="a_price"; A_OLD_PRICE="a_old_price"
A_SIZES="a_sizes"; A_COLORS="a_colors"; A_STOCK="a_stock"; A_PHOTO="a_photo"
A_BROADCAST="a_broadcast"

def st_set(uid, s, **d): _st[uid]={"s":s,"d":d}
def st_get(uid): return _st.get(uid,{}).get("s")
def st_dat(uid): return _st.get(uid,{}).get("d",{})
def st_clr(uid): _st.pop(uid,None)
def st_upd(uid, **kw):
    if uid not in _st: _st[uid]={"s":None,"d":{}}
    _st[uid]["d"].update(kw)

# ══════════════════════════════════════════════════════
#  ⌨️  KLAVIATURALAR
# ══════════════════════════════════════════════════════
def kb_main(uid):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🏪 Katalog"), KeyboardButton("🔍 Qidirish"))
    kb.row(KeyboardButton("🛒 Savatcha"), KeyboardButton("❤️ Sevimlilar"))
    kb.row(KeyboardButton("📦 Buyurtmalarim"), KeyboardButton("👤 Profilim"))
    kb.add(KeyboardButton("📞 Aloqa"))
    return kb

def kb_admin():
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Statistika"), KeyboardButton("📦 Buyurtmalar"))
    kb.row(KeyboardButton("➕ Mahsulot qo'shish"), KeyboardButton("📋 Mahsulotlar"))
    kb.row(KeyboardButton("📢 Xabar yuborish"), KeyboardButton("🏪 Do'konga o'tish"))
    return kb

def kb_phone():
    kb=ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Raqamimni yuborish",request_contact=True))
    kb.add(KeyboardButton("🔙 Bekor qilish"))
    return kb

def kb_loc():
    kb=ReplyKeyboardMarkup(resize_keyboard=True,one_time_keyboard=True)
    kb.add(KeyboardButton("📍 Joylashuvimni yuborish",request_location=True))
    kb.add(KeyboardButton("✏️ Manzilni yozaman"))
    kb.add(KeyboardButton("🔙 Bekor qilish"))
    return kb

def kb_cats():
    kb=InlineKeyboardMarkup(row_width=1)
    for cid,(em,nm) in CATEGORIES.items():
        kb.add(InlineKeyboardButton(f"{em} {nm}", callback_data=f"cat:{cid}:0"))
    kb.add(InlineKeyboardButton("🔥 Ommabop", callback_data="cat:0:0"))
    return kb

def kb_prods(prods, cat_id, page, total):
    kb=InlineKeyboardMarkup(row_width=1)
    for p in prods:
        disc=""
        if p.get("old_price") and p["old_price"]>p["price"]:
            pct=round((p["old_price"]-p["price"])/p["old_price"]*100); disc=f" 🏷-{pct}%"
        warn=" ⚠️az" if 0<p["stock"]<=5 else (" ❌" if p["stock"]==0 else "")
        kb.add(InlineKeyboardButton(f"{p['name']} — {fmt(p['price'])}{disc}{warn}", callback_data=f"prod:{p['id']}"))
    tp=math.ceil(total/PER_PAGE)
    if tp>1:
        nav=[]
        if page>0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"cat:{cat_id}:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{tp}", callback_data="noop"))
        if page<tp-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"cat:{cat_id}:{page+1}"))
        kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Kategoriyalar", callback_data="back:cats"))
    return kb

def kb_prod(p, qty, in_wish):
    kb=InlineKeyboardMarkup()
    pid=p["id"]
    if qty==0:
        if p["stock"]>0: kb.add(InlineKeyboardButton("🛒 Savatchaga qo'shish", callback_data=f"cadd:{pid}"))
        else: kb.add(InlineKeyboardButton("❌ Sotib bo'lindi", callback_data="noop"))
    else:
        kb.row(InlineKeyboardButton("➖",callback_data=f"cdec:{pid}"),
               InlineKeyboardButton(f"🛒 {qty} ta",callback_data="noop"),
               InlineKeyboardButton("➕",callback_data=f"cinc:{pid}"))
    h="❤️ Sevimlilardan o'chirish" if in_wish else "🤍 Sevimlilarga qo'shish"
    kb.add(InlineKeyboardButton(h, callback_data=f"wish:{pid}"))
    kb.add(InlineKeyboardButton("💬 Sharhlar", callback_data=f"revs:{pid}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data=f"cat:{p['cat_id']}:0"))
    return kb

def kb_cart_inline(items, t):
    kb=InlineKeyboardMarkup(row_width=3)
    for pid,(name,price,q) in items.items():
        kb.add(InlineKeyboardButton(f"🗑 {name[:18]} ×{q}", callback_data=f"crm:{pid}"))
        kb.row(InlineKeyboardButton("➖",callback_data=f"cdec:{pid}"),
               InlineKeyboardButton(f"{q}",callback_data="noop"),
               InlineKeyboardButton("➕",callback_data=f"cinc:{pid}"))
    kb.add(InlineKeyboardButton("🏷️ Promo kod", callback_data="promo"))
    kb.add(InlineKeyboardButton("🗑️ Savatchani tozalash", callback_data="cclear"))
    kb.add(InlineKeyboardButton(f"✅ Buyurtma — {fmt(t['grand'])}", callback_data="checkout"))
    return kb

def kb_delivery():
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚚 Yetkazib berish", callback_data="dlv:courier"))
    kb.add(InlineKeyboardButton("🏪 O'zim olib ketaman", callback_data="dlv:pickup"))
    kb.add(InlineKeyboardButton("🔙 Savatchaga", callback_data="back:cart"))
    return kb

def kb_note():
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➡️ Izohsiz davom etish", callback_data="no_note"))
    return kb

def kb_confirm():
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm"))
    kb.add(InlineKeyboardButton("✏️ O'zgartirish", callback_data="back:cart"))
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_order"))
    return kb

def kb_orders_list(orders):
    kb=InlineKeyboardMarkup()
    for o in orders:
        e,l=ORDER_ST.get(o["status"],("📦",o["status"]))
        kb.add(InlineKeyboardButton(f"{e} #{o['id']} {fmt(o['subtotal'])} — {l}", callback_data=f"ord:{o['id']}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back:main"))
    return kb

def kb_ord_detail(order):
    kb=InlineKeyboardMarkup()
    if order["status"]=="new": kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data=f"ocancel:{order['id']}"))
    if order["status"]=="delivered": kb.add(InlineKeyboardButton("⭐ Baho berish", callback_data=f"rate:{order['id']}"))
    kb.add(InlineKeyboardButton("🔄 Qayta buyurtma", callback_data=f"reord:{order['id']}"))
    kb.add(InlineKeyboardButton("🔙 Buyurtmalar", callback_data="back:orders"))
    return kb

def kb_stars(oid, pid):
    kb=InlineKeyboardMarkup(row_width=5)
    kb.add(*[InlineKeyboardButton(f"{i}⭐", callback_data=f"stars:{oid}:{pid}:{i}") for i in range(1,6)])
    kb.add(InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip_rev"))
    return kb

def kb_revs(pid, page, total):
    kb=InlineKeyboardMarkup()
    tp=math.ceil(total/5) if total else 1
    if tp>1:
        nav=[]
        if page>0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"revs:{pid}:{page-1}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{tp}", callback_data="noop"))
        if page<tp-1: nav.append(InlineKeyboardButton("➡️", callback_data=f"revs:{pid}:{page+1}"))
        kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Mahsulotga", callback_data=f"prod:{pid}"))
    return kb

def kb_admin_orders_filter():
    kb=InlineKeyboardMarkup(row_width=2)
    btns=[InlineKeyboardButton(f"{e} {l}", callback_data=f"aord:{s}") for s,(e,l) in ORDER_ST.items()]
    btns.append(InlineKeyboardButton("📋 Hammasi", callback_data="aord:all"))
    kb.add(*btns); return kb

def kb_admin_order(oid, cur):
    kb=InlineKeyboardMarkup(row_width=2)
    btns=[InlineKeyboardButton(f"{e} {l}", callback_data=f"ast:{oid}:{s}")
          for s,(e,l) in ORDER_ST.items() if s!=cur]
    kb.add(*btns); return kb

def kb_admin_cats():
    kb=InlineKeyboardMarkup(row_width=1)
    for cid,(em,nm) in CATEGORIES.items():
        kb.add(InlineKeyboardButton(f"{em} {nm}", callback_data=f"acat:{cid}"))
    return kb

def kb_admin_prods(prods):
    kb=InlineKeyboardMarkup(row_width=1)
    for p in prods:
        status="✅" if p["active"] else "❌"
        kb.add(InlineKeyboardButton(f"{status} {p['name']} — {fmt(p['price'])}", callback_data=f"aprod:{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back:admin"))
    return kb

def kb_admin_prod_detail(pid, active):
    kb=InlineKeyboardMarkup()
    if active: kb.add(InlineKeyboardButton("🗑️ O'chirish", callback_data=f"adel:{pid}"))
    else: kb.add(InlineKeyboardButton("♻️ Tiklash", callback_data=f"arestore:{pid}"))
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back:prods"))
    return kb

def kb_skip_photo():
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⏭ Rasmsiz qo'shish", callback_data="skip_photo"))
    return kb

def kb_skip_old_price():
    kb=InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⏭ Chegirmasiz", callback_data="skip_old_price"))
    return kb

# ══════════════════════════════════════════════════════
#  🤖  BOT
# ══════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

def is_admin(uid): return uid in ADMIN_IDS

def go_main(chat_id, uid, text="👋 Asosiy menyu:"):
    bot.send_message(chat_id, text, reply_markup=kb_admin() if is_admin(uid) else kb_main(uid))

def prod_text(p):
    em,cn=CATEGORIES.get(p["cat_id"],("📦",""))
    lines=[f"{em} *{p['name']}*"]
    if p.get("old_price") and p["old_price"]>p["price"]:
        pct=round((p["old_price"]-p["price"])/p["old_price"]*100)
        lines.append(f"💰 Narx: *{fmt(p['price'])}* ~~{fmt(p['old_price'])}~~ 🏷️ -{pct}%")
    else: lines.append(f"💰 Narx: *{fmt(p['price'])}*")
    if p.get("sizes"): lines.append(f"📏 O'lchamlar: {p['sizes']}")
    if p.get("colors"): lines.append(f"🎨 Ranglar: {p['colors']}")
    if p.get("desc"): lines.append(f"\n📝 {p['desc']}")
    if p["stock"]==0: lines.append("❌ *Sotib bo'lindi*")
    elif p["stock"]<=5: lines.append(f"⚠️ Qoldi: *{p['stock']} ta*")
    return "\n".join(lines)

def send_prod(chat_id, uid, p, mid=None):
    text=prod_text(p); qty=c_qty(uid,p["id"]); in_w=db_in_wish(uid,p["id"])
    markup=kb_prod(p,qty,in_w)
    if p.get("photo_id"):
        try:
            if mid:
                try: bot.delete_message(chat_id,mid)
                except: pass
            bot.send_photo(chat_id,p["photo_id"],caption=text,reply_markup=markup)
            return
        except: pass
    if mid:
        try: bot.edit_message_text(text,chat_id,mid,reply_markup=markup); return
        except: pass
    bot.send_message(chat_id,text,reply_markup=markup)

def show_cat(msg, cat_id, page=0):
    if cat_id==0:
        prods=db_products(offset=page*PER_PAGE,limit=PER_PAGE); total=db_count()
        title="🔥 Barcha mahsulotlar"
    else:
        em,nm=CATEGORIES.get(cat_id,("📦",""))
        prods=db_products(cat_id=cat_id,offset=page*PER_PAGE,limit=PER_PAGE); total=db_count(cat_id=cat_id)
        title=f"{em} {nm}"
    if not prods:
        try: bot.edit_message_text(f"{title}\n\n😔 Hozircha mahsulot yo'q.",msg.chat.id,msg.id,reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙",callback_data="back:cats")))
        except: bot.send_message(msg.chat.id,f"{title}\n\n😔 Hozircha mahsulot yo'q.")
        return
    text=f"*{title}* — {total} ta"
    try: bot.edit_message_text(text,msg.chat.id,msg.id,reply_markup=kb_prods(prods,cat_id,page,total))
    except: bot.send_message(msg.chat.id,text,reply_markup=kb_prods(prods,cat_id,page,total))

def refresh_cart(chat_id, uid, mid=None):
    if c_empty(uid):
        text="🛒 Savatcha bo'sh.\n\nKatalogdan mahsulot tanlang!"; markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🏪 Katalog",callback_data="back:cats"))
        if mid:
            try: bot.edit_message_text(text,chat_id,mid,reply_markup=markup); return
            except: pass
        bot.send_message(chat_id,text,reply_markup=markup); return
    items=c_items(uid); t=c_totals(uid); text=c_summary(uid)
    if mid:
        try: bot.edit_message_text(text,chat_id,mid,reply_markup=kb_cart_inline(items,t)); return
        except: pass
    bot.send_message(chat_id,text,reply_markup=kb_cart_inline(items,t))

def ask_phone_or_note(chat_id, uid):
    u=db_user(uid)
    if not u or not u.get("phone"):
        st_upd(uid,next="note"); bot.send_message(chat_id,"📱 *Telefon raqamingizni yuboring:*",reply_markup=kb_phone())
    else: bot.send_message(chat_id,"📝 *Izoh qo'shmoqchimisiz?*\n_(masalan: rang, o'lcham)_",reply_markup=kb_note())

def show_confirm(chat_id, uid):
    d=st_dat(uid); u=db_user(uid); t=c_totals(uid); items=c_items(uid); pr=c_promo(uid)
    lines=["✅ *Buyurtmani tasdiqlang:*\n","*Mahsulotlar:*"]
    for pid,(name,price,q) in items.items(): lines.append(f"  • {name} × {q} = {fmt(price*q)}")
    lines.append(f"\n💰 {fmt(t['sub'])}")
    if t["disc"]: lines.append(f"🏷️ -{fmt(t['disc'])}")
    lines.append(f"🚚 {fmt(t['deliv'])}")
    lines.append(f"💳 *{fmt(t['grand'])}*")
    lines.append(f"\n📍 {d.get('address','—')}")
    lines.append(f"📱 {d.get('phone') or (u.get('phone') if u else '—')}")
    if d.get("note"): lines.append(f"📝 {d['note']}")
    bot.send_message(chat_id,"\n".join(lines),reply_markup=kb_confirm())

def place_order(chat_id, uid):
    d=st_dat(uid); u=db_user(uid); t=c_totals(uid); items=c_items(uid); pr=c_promo(uid)
    phone=d.get("phone") or (u.get("phone","") if u else "")
    idict={pid:q for pid,(_,_,q) in items.items()}
    oid=db_create_order(uid,idict,t["sub"],t["disc"],t["deliv"],d.get("address",""),phone,pr["code"] if pr else "",d.get("note",""))
    order=db_order(oid); fname=u["fullname"] if u else str(uid)
    for aid in ADMIN_IDS:
        try: bot.send_message(aid,f"🆕 *Yangi buyurtma #{oid}!*\n\n{order_card(order,admin=True)}\n👤 [{fname}](tg://user?id={uid})",reply_markup=kb_admin_order(oid,"new"))
        except: pass
    c_clear(uid); st_clr(uid)
    bot.send_message(chat_id,f"🎉 *Buyurtma #{oid} qabul qilindi!*\n\n💳 *{fmt(t['grand'])}*\n\nTez orada bog'lanamiz! 🙏",reply_markup=kb_main(uid))

def order_card(order, admin=False):
    items=json.loads(order["items"])
    e,l=ORDER_ST.get(order["status"],("📦",order["status"]))
    lines=[f"📦 *#{order['id']}*  {e} {l}",f"📅 {order['created_at'][:16]}\n","*Mahsulotlar:*"]
    for pid,q in items.items():
        p=db_product(int(pid))
        if p: lines.append(f"  • {p['name']} ×{q} = {fmt(p['price']*q)}")
    grand=order["subtotal"]-order["discount"]+order["delivery"]
    lines.append(f"\n💰 {fmt(order['subtotal'])}")
    if order["discount"]: lines.append(f"🏷️ -{fmt(order['discount'])}")
    lines.append(f"🚚 {fmt(order['delivery'])}")
    lines.append(f"💳 *{fmt(grand)}*")
    if order.get("address"): lines.append(f"\n📍 {order['address']}")
    if order.get("phone"): lines.append(f"📱 {order['phone']}")
    if order.get("note"): lines.append(f"📝 {order['note']}")
    if admin: lines.append(f"\n🆔 `{order['uid']}`")
    return "\n".join(lines)

def notify_admin(text):
    for aid in ADMIN_IDS:
        try: bot.send_message(aid,text)
        except: pass

# ══════════════════════════════════════════════════════
#  📩  HANDLERLAR — MIJOZ
# ══════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def on_start(msg):
    uid=msg.from_user.id
    db_upsert(uid,msg.from_user.username or "",f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip())
    st_clr(uid)
    go_main(msg.chat.id,uid,f"Salom, *{msg.from_user.first_name}*! 👋\n\n🏪 *{SHOP_NAME}* ga xush kelibsiz!")

@bot.message_handler(commands=["cancel"])
def on_cancel(msg): st_clr(msg.from_user.id); go_main(msg.chat.id,msg.from_user.id,"❌ Bekor qilindi.")

@bot.message_handler(commands=["admin"])
def on_admin_cmd(msg):
    if is_admin(msg.from_user.id):
        go_main(msg.chat.id,msg.from_user.id,"🔑 *Admin panel*")

@bot.message_handler(func=lambda m: m.text=="🏪 Katalog" or m.text=="🏪 Do'konga o'tish")
def on_catalog(msg):
    st_clr(msg.from_user.id)
    bot.send_message(msg.chat.id,"📂 *Kategoriyani tanlang:*",reply_markup=kb_cats())

@bot.message_handler(func=lambda m: m.text=="🔍 Qidirish")
def on_search_start(msg):
    st_set(msg.from_user.id,S_SEARCH); bot.send_message(msg.chat.id,"🔍 Mahsulot nomini kiriting:")

@bot.message_handler(func=lambda m: m.text=="🛒 Savatcha")
def on_cart(msg): refresh_cart(msg.chat.id,msg.from_user.id)

@bot.message_handler(func=lambda m: m.text=="❤️ Sevimlilar")
def on_wish(msg):
    uid=msg.from_user.id; items=db_wish(uid)
    if not items: bot.send_message(msg.chat.id,"🤍 Sevimlilar bo'sh."); return
    kb=InlineKeyboardMarkup()
    for p in items: kb.add(InlineKeyboardButton(f"{p['name']} — {fmt(p['price'])}",callback_data=f"prod:{p['id']}"))
    bot.send_message(msg.chat.id,f"❤️ *Sevimlilar* ({len(items)} ta):",reply_markup=kb)

@bot.message_handler(func=lambda m: m.text=="📦 Buyurtmalarim")
def on_orders(msg):
    uid=msg.from_user.id; orders=db_orders(uid)
    if not orders: bot.send_message(msg.chat.id,"📦 Hali buyurtma yo'q."); return
    bot.send_message(msg.chat.id,f"📦 *Buyurtmalaringiz* ({len(orders)} ta):",reply_markup=kb_orders_list(orders))

@bot.message_handler(func=lambda m: m.text=="👤 Profilim")
def on_profile(msg):
    uid=msg.from_user.id; u=db_user(uid)
    if not u: return
    bot.send_message(msg.chat.id,
        f"👤 *Profil*\n\n🆔 `{uid}`\n👤 {u['fullname']}\n"
        f"📱 {u.get('phone') or 'Kiritilmagan'}\n📅 {u['joined'][:10]}\n\n"
        f"📦 Buyurtmalar: *{u['total_orders']}*\n💰 Jami: *{fmt(u['total_spent'])}*",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("📱 Telefon o'zgartirish",callback_data="chphone")))

@bot.message_handler(func=lambda m: m.text=="📞 Aloqa")
def on_contact(msg):
    bot.send_message(msg.chat.id,f"📞 *Aloqa*\n\n💬 {SUPPORT}\n📱 +998 90 123 45 67\n🕐 9:00—22:00")

# ══════════════════════════════════════════════════════
#  📩  HANDLERLAR — ADMIN
# ══════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: m.text=="📊 Statistika" and is_admin(m.from_user.id))
def on_stats(msg):
    s=db_stats()
    bot.send_message(msg.chat.id,
        f"📊 *Statistika*\n\n"
        f"👥 Foydalanuvchilar: *{s['users']}*\n"
        f"🛍️ Mahsulotlar: *{s['products']}*\n"
        f"📦 Jami buyurtmalar: *{s['orders']}*\n"
        f"🆕 Yangi (kutilmoqda): *{s['new']}*\n"
        f"📅 Bugun: *{s['today']}*\n"
        f"💰 Jami daromad: *{fmt(s['revenue'])}*")

@bot.message_handler(func=lambda m: m.text=="📦 Buyurtmalar" and is_admin(m.from_user.id))
def on_admin_orders(msg):
    bot.send_message(msg.chat.id,"📦 *Qaysi status?*",reply_markup=kb_admin_orders_filter())

@bot.message_handler(func=lambda m: m.text=="📋 Mahsulotlar" and is_admin(m.from_user.id))
def on_admin_prods_menu(msg):
    bot.send_message(msg.chat.id,"📋 *Qaysi kategoriya?*",reply_markup=kb_admin_cats())

@bot.message_handler(func=lambda m: m.text=="📢 Xabar yuborish" and is_admin(m.from_user.id))
def on_broadcast_start(msg):
    st_set(msg.from_user.id,A_BROADCAST)
    bot.send_message(msg.chat.id,"📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:\n_(/cancel — bekor qilish)_")

@bot.message_handler(func=lambda m: m.text=="➕ Mahsulot qo'shish" and is_admin(m.from_user.id))
def on_add_prod_start(msg):
    bot.send_message(msg.chat.id,"*Qaysi kategoriyaga qo'shamiz?*",reply_markup=kb_admin_cats())

# ══════════════════════════════════════════════════════
#  📲  CONTACT & LOCATION
# ══════════════════════════════════════════════════════
@bot.message_handler(content_types=["contact"])
def on_contact_msg(msg):
    uid=msg.from_user.id; phone=msg.contact.phone_number
    db_set_phone(uid,phone); st_upd(uid,phone=phone)
    d=st_dat(uid)
    if d.get("context")=="profile":
        st_clr(uid); bot.send_message(msg.chat.id,f"✅ Telefon yangilandi: {phone}",reply_markup=kb_main(uid))
    elif d.get("next")=="note":
        bot.send_message(msg.chat.id,"📝 *Izoh qo'shmoqchimisiz?*",reply_markup=kb_note())
    else:
        bot.send_message(msg.chat.id,f"✅ Raqam saqlandi.",reply_markup=kb_main(uid))

@bot.message_handler(content_types=["location"])
def on_location(msg):
    uid=msg.from_user.id
    if st_get(uid)==S_ADDRESS:
        st_upd(uid,address=f"📍 {msg.location.latitude:.4f},{msg.location.longitude:.4f}")
        ask_phone_or_note(msg.chat.id,uid)

@bot.message_handler(content_types=["photo"])
def on_photo(msg):
    uid=msg.from_user.id
    if st_get(uid)==A_PHOTO and is_admin(uid):
        photo_id=msg.photo[-1].file_id; st_upd(uid,photo_id=photo_id)
        _finish_add_product(msg.chat.id,uid)

# ══════════════════════════════════════════════════════
#  📝  MATN XABARLARI (state asosida)
# ══════════════════════════════════════════════════════
@bot.message_handler(content_types=["text"])
def on_text(msg):
    uid=msg.from_user.id; txt=msg.text.strip(); state=st_get(uid)

    # Mijoz states
    if state==S_SEARCH:
        st_clr(uid); total=db_count(search=txt)
        if total==0: bot.send_message(msg.chat.id,f"😔 *'{txt}'* bo'yicha topilmadi.",reply_markup=kb_cats()); return
        prods=db_products(search=txt,limit=PER_PAGE)
        bot.send_message(msg.chat.id,f"🔍 *'{txt}'* — {total} ta:",reply_markup=kb_prods(prods,0,0,total))

    elif state==S_PROMO:
        st_clr(uid); pct=c_apply_promo(uid,txt)
        bot.send_message(msg.chat.id,f"✅ *-{pct}%* chegirma! 🎉" if pct else "❌ Promo kod noto'g'ri.")
        refresh_cart(msg.chat.id,uid)

    elif state==S_ADDRESS:
        if txt in("🔙 Bekor qilish","/cancel"): st_clr(uid); refresh_cart(msg.chat.id,uid); return
        if txt=="✏️ Manzilni yozaman": bot.send_message(msg.chat.id,"📍 Manzilingizni yozing:"); return
        st_upd(uid,address=txt); ask_phone_or_note(msg.chat.id,uid)

    elif state==S_NOTE:
        if txt in("🔙 Bekor qilish","/cancel"): st_clr(uid); refresh_cart(msg.chat.id,uid); return
        st_upd(uid,note=txt); show_confirm(msg.chat.id,uid)

    elif state==S_REVIEW:
        d=st_dat(uid); db_add_review(uid,d["pid"],d["oid"],d["stars"],txt); st_clr(uid)
        bot.send_message(msg.chat.id,"⭐ Sharh uchun rahmat! 🙏",reply_markup=kb_main(uid) if not is_admin(uid) else kb_admin())

    # Admin states
    elif state==A_NAME and is_admin(uid):
        st_upd(uid,name=txt); st_set(uid,A_DESC,**st_dat(uid))
        bot.send_message(msg.chat.id,"📝 *Tavsif* kiriting:\n_(o'tkazib yuborish uchun — tugatish)_",
                         reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⏭ Tasvirsiz",callback_data="skip_desc")))

    elif state==A_DESC and is_admin(uid):
        st_upd(uid,desc=txt); st_set(uid,A_PRICE,**st_dat(uid))
        bot.send_message(msg.chat.id,"💰 *Narx* kiriting (so'mda, faqat raqam):")

    elif state==A_PRICE and is_admin(uid):
        try:
            price=int(txt.replace(" ","").replace(",",""))
            st_upd(uid,price=price); st_set(uid,A_OLD_PRICE,**st_dat(uid))
            bot.send_message(msg.chat.id,"💰 *Eski narx* (chegirma uchun):",reply_markup=kb_skip_old_price())
        except: bot.send_message(msg.chat.id,"❌ Faqat raqam kiriting:")

    elif state==A_OLD_PRICE and is_admin(uid):
        try:
            old=int(txt.replace(" ","").replace(",",""))
            st_upd(uid,old_price=old); st_set(uid,A_SIZES,**st_dat(uid))
            bot.send_message(msg.chat.id,"📏 *O'lchamlar* kiriting:\n_(masalan: XS, S, M, L, XL yoki 38, 39, 40, 41)_\n_(o'tkazish uchun tugatish)_",
                             reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⏭ O'lchamsiz",callback_data="skip_sizes")))
        except: bot.send_message(msg.chat.id,"❌ Faqat raqam kiriting:")

    elif state==A_SIZES and is_admin(uid):
        st_upd(uid,sizes=txt); st_set(uid,A_COLORS,**st_dat(uid))
        bot.send_message(msg.chat.id,"🎨 *Ranglar* kiriting:\n_(masalan: Qora, Oq, Ko'k)_",
                         reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⏭ Rangsiz",callback_data="skip_colors")))

    elif state==A_COLORS and is_admin(uid):
        st_upd(uid,colors=txt); st_set(uid,A_STOCK,**st_dat(uid))
        bot.send_message(msg.chat.id,"📦 *Ombordagi miqdor* kiriting (faqat raqam):")

    elif state==A_STOCK and is_admin(uid):
        try:
            stock=int(txt.replace(" ",""))
            st_upd(uid,stock=stock); st_set(uid,A_PHOTO,**st_dat(uid))
            bot.send_message(msg.chat.id,"🖼️ *Mahsulot rasmini* yuboring:",reply_markup=kb_skip_photo())
        except: bot.send_message(msg.chat.id,"❌ Faqat raqam kiriting:")

    elif state==A_BROADCAST and is_admin(uid):
        st_clr(uid); users=db_all_uids(); sent=0
        for user_id in users:
            try: bot.send_message(user_id,f"📢 *{SHOP_NAME}:*\n\n{txt}"); sent+=1
            except: pass
        bot.send_message(msg.chat.id,f"✅ *{sent}* ta foydalanuvchiga yuborildi.",reply_markup=kb_admin())

def _finish_add_product(chat_id, uid, photo_id=""):
    d=st_dat(uid)
    if not photo_id: photo_id=d.get("photo_id","")
    pid=db_add_product(
        cat_id=d.get("cat_id",1),
        name=d.get("name",""),
        desc=d.get("desc",""),
        price=d.get("price",0),
        old_price=d.get("old_price",0),
        sizes=d.get("sizes",""),
        colors=d.get("colors",""),
        photo_id=photo_id,
        stock=d.get("stock",999),
    )
    st_clr(uid)
    em,cn=CATEGORIES.get(d.get("cat_id",1),("📦",""))
    p=db_product(pid)
    bot.send_message(chat_id,f"✅ *Mahsulot qo'shildi!*\n\n{prod_text(p)}\n\n🆔 ID: `{pid}`",reply_markup=kb_admin())

# ══════════════════════════════════════════════════════
#  📲  CALLBACK HANDLERLAR
# ══════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data=="noop")
def cb_noop(call): bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data=="back:cats")
def cb_backcats(call):
    bot.answer_callback_query(call.id)
    try: bot.edit_message_text("📂 *Kategoriyani tanlang:*",call.message.chat.id,call.message.id,reply_markup=kb_cats())
    except: bot.send_message(call.message.chat.id,"📂 *Kategoriyani tanlang:*",reply_markup=kb_cats())

@bot.callback_query_handler(func=lambda c: c.data=="back:main")
def cb_backmain(call): bot.answer_callback_query(call.id); go_main(call.message.chat.id,call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data=="back:cart")
def cb_backcart(call): bot.answer_callback_query(call.id); refresh_cart(call.message.chat.id,call.from_user.id,call.message.id)

@bot.callback_query_handler(func=lambda c: c.data=="back:orders")
def cb_backorders(call):
    bot.answer_callback_query(call.id); uid=call.from_user.id; orders=db_orders(uid)
    if not orders: bot.edit_message_text("📦 Buyurtma yo'q.",call.message.chat.id,call.message.id); return
    bot.edit_message_text(f"📦 *Buyurtmalaringiz* ({len(orders)} ta):",call.message.chat.id,call.message.id,reply_markup=kb_orders_list(orders))

@bot.callback_query_handler(func=lambda c: c.data=="back:admin")
def cb_backadmin(call): bot.answer_callback_query(call.id); go_main(call.message.chat.id,call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data=="back:prods")
def cb_backprods(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("📋 *Qaysi kategoriya?*",call.message.chat.id,call.message.id,reply_markup=kb_admin_cats())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cat:"))
def cb_cat(call):
    _,cat_id,page=call.data.split(":"); bot.answer_callback_query(call.id)
    show_cat(call.message,int(cat_id),int(page))

@bot.callback_query_handler(func=lambda c: c.data.startswith("prod:"))
def cb_prod(call):
    pid=int(call.data.split(":")[1]); uid=call.from_user.id; p=db_product(pid)
    if not p: bot.answer_callback_query(call.id,"Topilmadi"); return
    bot.answer_callback_query(call.id)
    send_prod(call.message.chat.id,uid,p,call.message.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cadd:"))
def cb_cadd(call):
    pid=int(call.data.split(":")[1]); uid=call.from_user.id; ok=c_add(uid,pid)
    bot.answer_callback_query(call.id,"✅ Qo'shildi!" if ok else "❌ Sotib bo'lindi")
    p=db_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),db_in_wish(uid,pid)))
        except:
            try: bot.edit_message_caption(caption=prod_text(p),chat_id=call.message.chat.id,message_id=call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),db_in_wish(uid,pid)))
            except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("cinc:"))
def cb_cinc(call):
    pid=int(call.data.split(":")[1]); uid=call.from_user.id; c_inc(uid,pid); bot.answer_callback_query(call.id)
    p=db_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),db_in_wish(uid,pid)))
        except:
            try: bot.edit_message_caption(caption=prod_text(p),chat_id=call.message.chat.id,message_id=call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),db_in_wish(uid,pid)))
            except: refresh_cart(call.message.chat.id,uid,call.message.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cdec:"))
def cb_cdec(call):
    pid=int(call.data.split(":")[1]); uid=call.from_user.id; c_dec(uid,pid); bot.answer_callback_query(call.id)
    p=db_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),db_in_wish(uid,pid)))
        except:
            try: bot.edit_message_caption(caption=prod_text(p),chat_id=call.message.chat.id,message_id=call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),db_in_wish(uid,pid)))
            except: refresh_cart(call.message.chat.id,uid,call.message.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("crm:"))
def cb_crm(call):
    c_rm(call.from_user.id,call.data.split(":")[1]); bot.answer_callback_query(call.id,"🗑️ O'chirildi")
    refresh_cart(call.message.chat.id,call.from_user.id,call.message.id)

@bot.callback_query_handler(func=lambda c: c.data=="cclear")
def cb_cclear(call):
    c_clear(call.from_user.id); bot.answer_callback_query(call.id,"🗑️ Tozalandi")
    refresh_cart(call.message.chat.id,call.from_user.id,call.message.id)

@bot.callback_query_handler(func=lambda c: c.data=="promo")
def cb_promo(call):
    st_set(call.from_user.id,S_PROMO); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"🏷️ Promo kodingizni kiriting:")

@bot.callback_query_handler(func=lambda c: c.data=="checkout")
def cb_checkout(call):
    uid=call.from_user.id
    if c_empty(uid): bot.answer_callback_query(call.id,"Savatcha bo'sh!",show_alert=True); return
    bot.answer_callback_query(call.id); st_set(uid,S_ADDRESS)
    bot.send_message(call.message.chat.id,"🚚 *Yetkazib berish usuli:*",reply_markup=kb_delivery())

@bot.callback_query_handler(func=lambda c: c.data.startswith("dlv:"))
def cb_dlv(call):
    uid=call.from_user.id; method=call.data.split(":")[1]; bot.answer_callback_query(call.id)
    if method=="back": refresh_cart(call.message.chat.id,uid,call.message.id); return
    st_set(uid,S_ADDRESS,method=method)
    if method=="courier":
        bot.send_message(call.message.chat.id,"📍 *Yetkazib berish manzilini kiriting:*",reply_markup=kb_loc())
    else:
        st_upd(uid,address="O'zimiz olib ketamiz"); ask_phone_or_note(call.message.chat.id,uid)

@bot.callback_query_handler(func=lambda c: c.data=="no_note")
def cb_nonote(call):
    st_upd(call.from_user.id,note=""); bot.answer_callback_query(call.id)
    show_confirm(call.message.chat.id,call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data=="confirm")
def cb_confirm(call): bot.answer_callback_query(call.id); place_order(call.message.chat.id,call.from_user.id)

@bot.callback_query_handler(func=lambda c: c.data=="cancel_order")
def cb_cancel_ord(call):
    st_clr(call.from_user.id); bot.answer_callback_query(call.id,"Bekor qilindi")
    go_main(call.message.chat.id,call.from_user.id,"❌ Bekor qilindi.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("wish:"))
def cb_wish(call):
    pid=int(call.data.split(":")[1]); uid=call.from_user.id; added=db_toggle_wish(uid,pid)
    bot.answer_callback_query(call.id,"❤️ Qo'shildi!" if added else "🤍 O'chirildi")
    p=db_product(pid)
    if p:
        try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),added))
        except:
            try: bot.edit_message_caption(caption=prod_text(p),chat_id=call.message.chat.id,message_id=call.message.id,reply_markup=kb_prod(p,c_qty(uid,pid),added))
            except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("revs:"))
def cb_revs(call):
    parts=call.data.split(":"); pid=int(parts[1]); page=int(parts[2]) if len(parts)>2 else 0
    bot.answer_callback_query(call.id); p=db_product(pid)
    if not p: return
    revs=db_reviews(pid)
    if not revs: text=f"💬 *{p['name']}* uchun hali sharh yo'q."
    else:
        text=f"💬 *{p['name']}* sharhlari\n\n"
        for r in revs:
            text+=f"{'⭐'*r['stars']} *{r['fullname']}*\n"
            if r.get("text"): text+=f"_{r['text']}_\n"
            text+=f"📅 {r['created_at'][:10]}\n\n"
    total_revs=len(db_reviews(pid,limit=100))
    try: bot.edit_message_text(text,call.message.chat.id,call.message.id,reply_markup=kb_revs(pid,page,total_revs))
    except: bot.send_message(call.message.chat.id,text,reply_markup=kb_revs(pid,page,total_revs))

@bot.callback_query_handler(func=lambda c: c.data.startswith("ord:"))
def cb_ord(call):
    oid=int(call.data.split(":")[1]); order=db_order(oid); bot.answer_callback_query(call.id)
    if not order: return
    try: bot.edit_message_text(order_card(order),call.message.chat.id,call.message.id,reply_markup=kb_ord_detail(order))
    except: bot.send_message(call.message.chat.id,order_card(order),reply_markup=kb_ord_detail(order))

@bot.callback_query_handler(func=lambda c: c.data.startswith("ocancel:"))
def cb_ocancel(call):
    oid=int(call.data.split(":")[1]); order=db_order(oid)
    if order and order["status"]=="new":
        db_set_status(oid,"cancelled"); bot.answer_callback_query(call.id,"❌ Bekor qilindi")
        notify_admin(f"❌ Buyurtma #{oid} bekor qilindi (mijoz tomonidan)")
        try: bot.edit_message_text(order_card(db_get_order(oid)),call.message.chat.id,call.message.id,reply_markup=kb_ord_detail(db_order(oid)))
        except: pass
    else: bot.answer_callback_query(call.id,"Bekor qilib bo'lmaydi",show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("reord:"))
def cb_reord(call):
    oid=int(call.data.split(":")[1]); order=db_order(oid); uid=call.from_user.id
    if order:
        for pid,q in json.loads(order["items"]).items():
            for _ in range(q): c_add(uid,int(pid))
        bot.answer_callback_query(call.id,"✅ Savatchaga qo'shildi!")
        refresh_cart(call.message.chat.id,uid)
    else: bot.answer_callback_query(call.id,"Topilmadi")

@bot.callback_query_handler(func=lambda c: c.data.startswith("rate:"))
def cb_rate(call):
    oid=int(call.data.split(":")[1]); order=db_order(oid)
    if not order: bot.answer_callback_query(call.id); return
    items=json.loads(order["items"]); pid=int(list(items.keys())[0]); p=db_product(pid)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,f"⭐ *{p['name']}* ga baho bering:",reply_markup=kb_stars(oid,pid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("stars:"))
def cb_stars(call):
    _,oid,pid,stars=call.data.split(":"); uid=call.from_user.id
    st_set(uid,S_REVIEW,oid=int(oid),pid=int(pid),stars=int(stars)); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,f"{'⭐'*int(stars)} Sharhingizni yozing:\n_(/cancel — o'tkazib yuborish)_")

@bot.callback_query_handler(func=lambda c: c.data=="skip_rev")
def cb_skiprev(call): st_clr(call.from_user.id); bot.answer_callback_query(call.id,"O'tkazildi"); bot.send_message(call.message.chat.id,"Rahmat! 🙏")

@bot.callback_query_handler(func=lambda c: c.data=="chphone")
def cb_chphone(call):
    st_set(call.from_user.id,S_PHONE,context="profile"); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"📱 Yangi raqamingizni yuboring:",reply_markup=kb_phone())

# Admin callbacks
@bot.callback_query_handler(func=lambda c: c.data.startswith("aord:") and is_admin(c.from_user.id))
def cb_aord(call):
    status=call.data.split(":")[1]; bot.answer_callback_query(call.id)
    orders=db_all_orders(None if status=="all" else status)
    if not orders: bot.edit_message_text("📦 Buyurtmalar yo'q.",call.message.chat.id,call.message.id); return
    bot.edit_message_text(f"📦 *Buyurtmalar* ({len(orders)} ta):",call.message.chat.id,call.message.id,reply_markup=kb_orders_list(orders))

@bot.callback_query_handler(func=lambda c: c.data.startswith("ast:") and is_admin(c.from_user.id))
def cb_ast(call):
    _,oid,status=call.data.split(":"); oid=int(oid)
    db_set_status(oid,status); bot.answer_callback_query(call.id,"✅ Yangilandi")
    order=db_order(oid); e,l=ORDER_ST.get(status,("📦",status))
    try: bot.send_message(order["uid"],f"{e} *Buyurtma #{oid}:* *{l}*\n\nBuyurtmalarim bo'limida ko'ring.")
    except: pass
    try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_admin_order(oid,status))
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("acat:") and is_admin(c.from_user.id))
def cb_acat(call):
    cat_id=int(call.data.split(":")[1]); uid=call.from_user.id; bot.answer_callback_query(call.id)
    state=st_get(uid)
    # Admin mahsulot qo'shish
    if state is None or state in (A_NAME,A_DESC,A_PRICE,A_OLD_PRICE,A_SIZES,A_COLORS,A_STOCK,A_PHOTO) or True:
        # Agar xozir mahsulot qo'shish jarayonida bo'lmasa — kategoriya listini ko'rsat
        d=st_dat(uid)
        if d.get("adding"):
            st_upd(uid,cat_id=cat_id); st_set(uid,A_NAME,**st_dat(uid))
            em,nm=CATEGORIES.get(cat_id,("📦",""))
            try: bot.edit_message_text(f"{em} *{nm}* kategoriyasi\n\n*Mahsulot nomini* kiriting:",call.message.chat.id,call.message.id)
            except: bot.send_message(call.message.chat.id,f"{em} *{nm}* kategoriyasi\n\n*Mahsulot nomini* kiriting:")
        else:
            # Mahsulotlar ro'yxati
            prods=db_all_products_admin(cat_id)
            em,nm=CATEGORIES.get(cat_id,("📦",""))
            if not prods:
                try: bot.edit_message_text(f"{em} *{nm}*\n\n😔 Mahsulot yo'q.",call.message.chat.id,call.message.id,reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙",callback_data="back:admin")))
                except: bot.send_message(call.message.chat.id,f"{em} *{nm}*\n\n😔 Mahsulot yo'q.")
                return
            try: bot.edit_message_text(f"{em} *{nm}* — {len(prods)} ta mahsulot:",call.message.chat.id,call.message.id,reply_markup=kb_admin_prods(prods))
            except: bot.send_message(call.message.chat.id,f"{em} *{nm}* — {len(prods)} ta mahsulot:",reply_markup=kb_admin_prods(prods))

@bot.message_handler(func=lambda m: m.text=="➕ Mahsulot qo'shish" and is_admin(m.from_user.id))
def on_add_prod(msg):
    uid=msg.from_user.id; st_set(uid,A_NAME,adding=True)
    bot.send_message(msg.chat.id,"*Qaysi kategoriyaga?*",reply_markup=kb_admin_cats())

@bot.callback_query_handler(func=lambda c: c.data.startswith("aprod:") and is_admin(c.from_user.id))
def cb_aprod(call):
    pid=int(call.data.split(":")[1]); p=db_product(pid); bot.answer_callback_query(call.id)
    if not p: return
    status_str = '✅ Aktiv' if p['active'] else "❌ O'chirilgan"
    text = prod_text(p) + f"\n\n🆔 ID: `{pid}`\nStatus: {status_str}\n📦 Ombor: {p['stock']} ta"
    if p.get("photo_id"):
        try: bot.send_photo(call.message.chat.id,p["photo_id"],caption=text,reply_markup=kb_admin_prod_detail(pid,p["active"])); return
        except: pass
    try: bot.edit_message_text(text,call.message.chat.id,call.message.id,reply_markup=kb_admin_prod_detail(pid,p["active"]))
    except: bot.send_message(call.message.chat.id,text,reply_markup=kb_admin_prod_detail(pid,p["active"]))

@bot.callback_query_handler(func=lambda c: c.data.startswith("adel:") and is_admin(c.from_user.id))
def cb_adel(call):
    pid=int(call.data.split(":")[1]); db_del_product(pid); bot.answer_callback_query(call.id,"🗑️ O'chirildi")
    try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_admin_prod_detail(pid,False))
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("arestore:") and is_admin(c.from_user.id))
def cb_arestore(call):
    pid=int(call.data.split(":")[1])
    db=conn(); db.execute("UPDATE products SET active=1 WHERE id=?", (pid,)); db.commit(); db.close()
    bot.answer_callback_query(call.id,"♻️ Tiklandi")
    try: bot.edit_message_reply_markup(call.message.chat.id,call.message.id,reply_markup=kb_admin_prod_detail(pid,True))
    except: pass

# Skip callbacks for admin product add
@bot.callback_query_handler(func=lambda c: c.data=="skip_desc" and is_admin(c.from_user.id))
def cb_skip_desc(call):
    uid=call.from_user.id; st_upd(uid,desc=""); st_set(uid,A_PRICE,**st_dat(uid)); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"💰 *Narx* kiriting (so'mda, faqat raqam):")

@bot.callback_query_handler(func=lambda c: c.data=="skip_old_price" and is_admin(c.from_user.id))
def cb_skip_op(call):
    uid=call.from_user.id; st_upd(uid,old_price=0); st_set(uid,A_SIZES,**st_dat(uid)); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"📏 *O'lchamlar* kiriting:",
                     reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⏭ O'lchamsiz",callback_data="skip_sizes")))

@bot.callback_query_handler(func=lambda c: c.data=="skip_sizes" and is_admin(c.from_user.id))
def cb_skip_sizes(call):
    uid=call.from_user.id; st_upd(uid,sizes=""); st_set(uid,A_COLORS,**st_dat(uid)); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"🎨 *Ranglar* kiriting:",
                     reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⏭ Rangsiz",callback_data="skip_colors")))

@bot.callback_query_handler(func=lambda c: c.data=="skip_colors" and is_admin(c.from_user.id))
def cb_skip_colors(call):
    uid=call.from_user.id; st_upd(uid,colors=""); st_set(uid,A_STOCK,**st_dat(uid)); bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,"📦 *Ombordagi miqdor* kiriting:")

@bot.callback_query_handler(func=lambda c: c.data=="skip_photo" and is_admin(c.from_user.id))
def cb_skip_photo(call):
    uid=call.from_user.id; bot.answer_callback_query(call.id); _finish_add_product(call.message.chat.id,uid,"")

# ══════════════════════════════════════════════════════
#  ▶️  ISHGA TUSHIRISH
# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    print(f"✅ {SHOP_NAME} ishga tushdi! Admin: {ADMIN_IDS}")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
