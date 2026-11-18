from flask import Flask, jsonify, request, render_template, send_file, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, csv, io, re, secrets
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "poultrycare.db")
app = Flask(__name__)
SECRET_FILE = os.path.join(BASE_DIR, "instance_secret.key")
if os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, "r", encoding="utf-8") as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(app.secret_key)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=60*60*24*14)

@app.before_request
def require_login():
    path = request.path
    public_paths = {"/login", "/api/health", "/api/auth/login", "/api/auth/signup", "/favicon.ico"}
    if path in public_paths or path.startswith("/static/"):
        return None
    if path.startswith("/api/") and not session.get("user_id"):
        return jsonify(error="Please sign in to access PoultryCare"), 401
    if path == "/" and not session.get("user_id"):
        return redirect(url_for("login_page"))
    return None

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS houses (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL,
          birds INTEGER NOT NULL DEFAULT 0, feed REAL NOT NULL DEFAULT 0,
          temperature REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
          id INTEGER PRIMARY KEY AUTOINCREMENT, house_id INTEGER NOT NULL,
          record_type TEXT NOT NULL CHECK(record_type IN ('eggs','deaths','feed')),
          good INTEGER DEFAULT 0, cracked INTEGER DEFAULT 0, dirty INTEGER DEFAULT 0,
          broken INTEGER DEFAULT 0, quantity REAL DEFAULT 0, notes TEXT DEFAULT '',
          recorded_at TEXT NOT NULL, FOREIGN KEY(house_id) REFERENCES houses(id)
        );
        CREATE INDEX IF NOT EXISTS idx_records_date ON records(recorded_at);
        CREATE TABLE IF NOT EXISTS checklist (
          key TEXT PRIMARY KEY, done INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expenses (
          id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, amount REAL NOT NULL,
          description TEXT DEFAULT '', spent_on TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customers (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sales (
          id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, item TEXT NOT NULL,
          quantity REAL NOT NULL, unit_price REAL NOT NULL, paid REAL NOT NULL DEFAULT 0,
          sold_on TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(customer_id) REFERENCES customers(id)
        );
        CREATE TABLE IF NOT EXISTS health_observations (
          id INTEGER PRIMARY KEY AUTOINCREMENT, house_id INTEGER NOT NULL, bird_count INTEGER DEFAULT 1,
          symptoms TEXT NOT NULL, action_taken TEXT DEFAULT '', observed_on TEXT NOT NULL,
          follow_up TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(house_id) REFERENCES houses(id)
        );
        """)
        count = c.execute("SELECT COUNT(*) n FROM houses").fetchone()["n"]
        if count == 0:
            now = datetime.now().isoformat(timespec="seconds")
            c.executemany("INSERT INTO houses(id,name,type,birds,feed,temperature,created_at) VALUES(?,?,?,?,?,?,?)", [
                (1,"House 1 Layers","Layer",1000,38,27,now),
                (2,"House 2 Broilers","Broiler",500,120,29,now),
                (3,"House 3 Kienyeji","Kienyeji",750,210,26,now)])
            # Clearly labelled demo records to make the dashboard resemble the provided prototype.
            today = date.today().isoformat()
            c.executemany("""INSERT INTO records(house_id,record_type,good,cracked,dirty,broken,quantity,notes,recorded_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", [
                (1,"eggs",795,8,6,3,0,"Initial demonstration values",today+"T08:00:00"),
                (2,"deaths",0,0,0,0,6,"Initial demonstration values",today+"T08:00:00"),
                (3,"deaths",0,0,0,0,1,"Initial demonstration values",today+"T08:00:00")])

def rowdict(r):
    return dict(r)

def state_payload(c):
    houses=[]
    for h in c.execute("SELECT * FROM houses ORDER BY id"):
        eggs = c.execute("""SELECT COALESCE(SUM(good+cracked+dirty+broken),0) n FROM records
            WHERE house_id=? AND record_type='eggs' AND date(recorded_at)=date('now','localtime')""",(h["id"],)).fetchone()["n"]
        deaths = c.execute("""SELECT COALESCE(SUM(quantity),0) n FROM records
            WHERE house_id=? AND record_type='deaths' AND date(recorded_at)=date('now','localtime')""",(h["id"],)).fetchone()["n"]
        # Seven recent daily egg/death totals for the prototype's mini charts.
        series=[]
        for offset in range(6,-1,-1):
            val=c.execute("""SELECT COALESCE(SUM(CASE WHEN record_type='eggs' THEN good+cracked+dirty+broken
                WHEN record_type='deaths' THEN quantity ELSE 0 END),0) n FROM records
                WHERE house_id=? AND date(recorded_at)=date('now','localtime',?)""",(h["id"],f"-{offset} day")).fetchone()["n"]
            series.append(val)
        houses.append({"id":h["id"],"name":h["name"],"type":h["type"],"birds":h["birds"],
          "eggs":int(eggs),"deaths":int(deaths),"avg":1,"feed":h["feed"],"use":0,
          "temp":h["temperature"],"series":series})
    checks=[r["key"] for r in c.execute("SELECT key FROM checklist WHERE done=1")]
    return {"houses":houses,"checks":checks}

@app.get("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("login.html")

@app.get("/")
def index():
    return render_template("index.html", current_user=session.get("user_name", "Farm user"))

@app.post("/api/auth/signup")
def signup():
    d = request.get_json(silent=True) or {}
    name = str(d.get("name", "")).strip()
    email = str(d.get("email", "")).strip().lower()
    password = str(d.get("password", ""))
    if len(name) < 2:
        return jsonify(error="Please enter your name."), 400
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Your password must contain at least 8 characters."), 400
    with db() as c:
        try:
            cur = c.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), datetime.now().isoformat(timespec="seconds")))
        except sqlite3.IntegrityError:
            return jsonify(error="An account with this email already exists."), 409
        session.clear(); session.permanent = True
        session["user_id"] = cur.lastrowid; session["user_name"] = name
    return jsonify(message="Account created", name=name), 201

@app.post("/api/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    email = str(d.get("email", "")).strip().lower()
    password = str(d.get("password", ""))
    with db() as c:
        user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Email or password is incorrect."), 401
    session.clear(); session.permanent = True
    session["user_id"] = user["id"]; session["user_name"] = user["name"]
    return jsonify(message="Signed in", name=user["name"])

@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(message="Signed out")

@app.get("/api/health")
def health():
    return jsonify({"status":"ok","service":"PoultryCare API","database":"SQLite","time":datetime.now().isoformat(timespec="seconds")})

@app.get("/api/state")
def get_state():
    with db() as c:
        return jsonify(state_payload(c))

@app.get("/api/houses")
def list_houses():
    with db() as c:
        return jsonify([rowdict(r) for r in c.execute("SELECT * FROM houses ORDER BY id")])

@app.post("/api/houses")
def create_house():
    data=request.get_json(silent=True) or {}
    name=str(data.get("name","")).strip()
    typ=str(data.get("type","")).strip()
    try:
        birds=int(data.get("birds",0)); feed=float(data.get("feed",0)); temp=float(data.get("temperature",0))
    except (TypeError,ValueError):
        return jsonify(error="birds, feed and temperature must be numbers"),400
    if not name or not typ or birds<1 or feed<0 or temp<0:
        return jsonify(error="Provide name, type, positive bird count, and non-negative feed/temperature"),400
    with db() as c:
        cur=c.execute("INSERT INTO houses(name,type,birds,feed,temperature,created_at) VALUES(?,?,?,?,?,?)",
                      (name,typ,birds,feed,temp,datetime.now().isoformat(timespec="seconds")))
        return jsonify(id=cur.lastrowid,message="House created"),201

@app.post("/api/records")
def create_record():
    data=request.get_json(silent=True) or {}
    try:
        house_id=int(data["house_id"]); kind=str(data["record_type"])
        good=int(data.get("good",0)); cracked=int(data.get("cracked",0)); dirty=int(data.get("dirty",0)); broken=int(data.get("broken",0))
        quantity=float(data.get("quantity",0))
    except (KeyError,TypeError,ValueError):
        return jsonify(error="Invalid or missing record fields"),400
    if kind not in ("eggs","deaths","feed"):
        return jsonify(error="record_type must be eggs, deaths, or feed"),400
    if min(good,cracked,dirty,broken,quantity)<0:
        return jsonify(error="Counts and quantities cannot be negative"),400
    with db() as c:
        h=c.execute("SELECT * FROM houses WHERE id=?",(house_id,)).fetchone()
        if not h: return jsonify(error="House not found"),404
        if kind=="eggs" and h["type"].lower() not in ("layer","kienyeji"):
            return jsonify(error="Egg records are only supported for laying flocks"),400
        if kind=="deaths" and (quantity<1 or quantity>h["birds"]):
            return jsonify(error=f"Deaths must be between 1 and {h['birds']}"),400
        if kind=="eggs" and good+cracked+dirty+broken<1:
            return jsonify(error="Enter at least one egg count"),400
        if kind=="feed":
            c.execute("UPDATE houses SET feed=? WHERE id=?",(quantity,house_id))
        c.execute("""INSERT INTO records(house_id,record_type,good,cracked,dirty,broken,quantity,notes,recorded_at)
          VALUES(?,?,?,?,?,?,?,?,?)""",(house_id,kind,good,cracked,dirty,broken,quantity,str(data.get("notes",""))[:1000],datetime.now().isoformat(timespec="seconds")))
        return jsonify(message="Record saved",**state_payload(c)),201

@app.get("/api/records")
def list_records():
    kind=request.args.get("type")
    limit=min(max(request.args.get("limit",100,type=int),1),1000)
    with db() as c:
        sql="""SELECT r.*,h.name AS house_name FROM records r JOIN houses h ON h.id=r.house_id"""
        args=[]
        if kind:
            sql+=" WHERE r.record_type=?"; args.append(kind)
        sql+=" ORDER BY r.recorded_at DESC,r.id DESC LIMIT ?"; args.append(limit)
        return jsonify([rowdict(r) for r in c.execute(sql,args)])

@app.post("/api/checklist")
def update_checklist():
    data=request.get_json(silent=True) or {}; key=str(data.get("key","")).strip()
    if not key or len(key)>100: return jsonify(error="A valid checklist key is required"),400
    done=1 if data.get("done") else 0
    with db() as c:
        c.execute("""INSERT INTO checklist(key,done,updated_at) VALUES(?,?,?)
          ON CONFLICT(key) DO UPDATE SET done=excluded.done,updated_at=excluded.updated_at""",
          (key,done,datetime.now().isoformat(timespec="seconds")))
        checks=[r["key"] for r in c.execute("SELECT key FROM checklist WHERE done=1")]
        return jsonify(checks=checks)

@app.post("/api/expenses")
def create_expense():
    d=request.get_json(silent=True) or {}
    try: amount=float(d.get("amount",0))
    except (ValueError,TypeError): return jsonify(error="amount must be numeric"),400
    category=str(d.get("category","")).strip(); description=str(d.get("description","")).strip()
    if not category or amount<=0: return jsonify(error="category and positive amount are required"),400
    spent_on=str(d.get("spent_on",date.today().isoformat()))
    with db() as c:
        cur=c.execute("INSERT INTO expenses(category,amount,description,spent_on,created_at) VALUES(?,?,?,?,?)",
          (category,amount,description[:1000],spent_on,datetime.now().isoformat(timespec="seconds")))
        return jsonify(id=cur.lastrowid,message="Expense saved"),201

@app.get("/api/expenses")
def list_expenses():
    with db() as c: return jsonify([rowdict(r) for r in c.execute("SELECT * FROM expenses ORDER BY spent_on DESC,id DESC")])

@app.post("/api/customers")
def create_customer():
    d=request.get_json(silent=True) or {}; name=str(d.get("name","")).strip(); phone=str(d.get("phone","")).strip()
    if not name: return jsonify(error="Customer name is required"),400
    with db() as c:
        cur=c.execute("INSERT INTO customers(name,phone,created_at) VALUES(?,?,?)",(name,phone[:40],datetime.now().isoformat(timespec="seconds")))
        return jsonify(id=cur.lastrowid,message="Customer saved"),201

@app.get("/api/customers")
def list_customers():
    with db() as c: return jsonify([rowdict(r) for r in c.execute("SELECT * FROM customers ORDER BY name")])

@app.post("/api/sales")
def create_sale():
    d=request.get_json(silent=True) or {}
    try:
        customer_id=d.get("customer_id"); customer_id=int(customer_id) if customer_id not in (None,"") else None
        quantity=float(d.get("quantity",0)); unit_price=float(d.get("unit_price",0)); paid=float(d.get("paid",0))
    except (ValueError,TypeError): return jsonify(error="Quantity, unit_price and paid must be numeric"),400
    item=str(d.get("item","")).strip()
    if not item or quantity<=0 or unit_price<0 or paid<0 or paid>quantity*unit_price:
        return jsonify(error="Provide item, positive quantity and valid price/payment values"),400
    with db() as c:
        if customer_id and not c.execute("SELECT 1 FROM customers WHERE id=?",(customer_id,)).fetchone():
            return jsonify(error="Customer not found"),404
        cur=c.execute("INSERT INTO sales(customer_id,item,quantity,unit_price,paid,sold_on,notes) VALUES(?,?,?,?,?,?,?)",
          (customer_id,item,quantity,unit_price,paid,str(d.get("sold_on",date.today().isoformat())),str(d.get("notes",""))[:1000]))
        return jsonify(id=cur.lastrowid,total=round(quantity*unit_price,2),balance=round(quantity*unit_price-paid,2),message="Sale saved"),201

@app.get("/api/sales")
def list_sales():
    with db() as c:
        return jsonify([rowdict(r) for r in c.execute("""SELECT s.*,c.name customer_name,
          ROUND(s.quantity*s.unit_price,2) total,ROUND(s.quantity*s.unit_price-s.paid,2) balance
          FROM sales s LEFT JOIN customers c ON c.id=s.customer_id ORDER BY sold_on DESC,s.id DESC""")])

@app.post("/api/health-records")
def create_health_record():
    d=request.get_json(silent=True) or {}
    try: house_id=int(d.get("house_id")); birds=int(d.get("bird_count",1))
    except (ValueError,TypeError): return jsonify(error="house_id and bird_count must be integers"),400
    symptoms=str(d.get("symptoms","")).strip()
    if not symptoms or birds<1: return jsonify(error="Symptoms/observation and positive bird count are required"),400
    with db() as c:
        if not c.execute("SELECT 1 FROM houses WHERE id=?",(house_id,)).fetchone(): return jsonify(error="House not found"),404
        cur=c.execute("""INSERT INTO health_observations(house_id,bird_count,symptoms,action_taken,observed_on,follow_up,created_at)
          VALUES(?,?,?,?,?,?,?)""",(house_id,birds,symptoms,str(d.get("action_taken",""))[:1000],str(d.get("observed_on",date.today().isoformat())),str(d.get("follow_up",""))[:1000],datetime.now().isoformat(timespec="seconds")))
        return jsonify(id=cur.lastrowid,message="Health observation saved. This is recordkeeping, not a diagnosis."),201

@app.get("/api/health-records")
def list_health_records():
    with db() as c:
        return jsonify([rowdict(r) for r in c.execute("""SELECT v.*,h.name house_name FROM health_observations v
          JOIN houses h ON h.id=v.house_id ORDER BY observed_on DESC,v.id DESC""")])

@app.get("/api/reports/daily.csv")
def daily_report():
    with db() as c:
        rows=c.execute("""SELECT date(recorded_at) date,h.name house_name,
          SUM(CASE WHEN record_type='eggs' THEN good ELSE 0 END) good_eggs,
          SUM(CASE WHEN record_type='eggs' THEN cracked ELSE 0 END) cracked_eggs,
          SUM(CASE WHEN record_type='eggs' THEN dirty ELSE 0 END) dirty_eggs,
          SUM(CASE WHEN record_type='eggs' THEN broken ELSE 0 END) broken_eggs,
          SUM(CASE WHEN record_type='deaths' THEN quantity ELSE 0 END) deaths
          FROM records r JOIN houses h ON h.id=r.house_id GROUP BY date(recorded_at),h.id ORDER BY date DESC,h.id""").fetchall()
    out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(["date","house","good_eggs","cracked_eggs","dirty_eggs","broken_eggs","deaths"])
    for r in rows: writer.writerow(list(r))
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")),mimetype="text/csv",as_attachment=True,download_name="poultrycare_daily_report.csv")

@app.errorhandler(404)
def not_found(_): return jsonify(error="Endpoint not found"),404

@app.errorhandler(500)
def server_error(_): return jsonify(error="Internal server error"),500

init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
