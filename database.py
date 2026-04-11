import sqlite3
from datetime import datetime
from config import DATABASE_PATH


def get_db():
    return sqlite3.connect(DATABASE_PATH, check_same_thread=False)


def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            phone TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS managers (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            user_id INTEGER,
            rub_amount REAL,
            cny_amount REAL,
            rate REAL,
            method TEXT,
            status TEXT DEFAULT 'new',
            manager_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS states (
            user_id INTEGER PRIMARY KEY,
            state TEXT,
            data TEXT
        )
    """)
    
    conn.commit()
    conn.close()


# === USERS ===

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "first_name": row[2], "phone": row[3]}
    return None


def save_user(user_id, username, first_name, phone=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, phone) 
        VALUES (?, ?, ?, COALESCE(?, (SELECT phone FROM users WHERE user_id = ?)))
    """, (user_id, username, first_name, phone, user_id))
    conn.commit()
    conn.close()


def update_phone(user_id, phone):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
    conn.commit()
    conn.close()


# === ORDERS ===

def gen_order_number():
    now = datetime.now()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = date('now')")
    n = c.fetchone()[0] + 1
    conn.close()
    return f"SNG-{now.strftime('%d%m')}-{n:04d}"


def create_order(user_id, rub_amount, cny_amount, rate):
    conn = get_db()
    c = conn.cursor()
    order_number = gen_order_number()
    c.execute("""
        INSERT INTO orders (order_number, user_id, rub_amount, cny_amount, rate, status)
        VALUES (?, ?, ?, ?, ?, 'new')
    """, (order_number, user_id, rub_amount, cny_amount, rate))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return get_order(order_id)


def get_order(order_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT o.*, u.username, u.first_name, u.phone 
        FROM orders o LEFT JOIN users u ON o.user_id = u.user_id 
        WHERE o.id = ?
    """, (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "order_number": row[1], "user_id": row[2],
            "rub_amount": row[3], "cny_amount": row[4], "rate": row[5],
            "method": row[6], "status": row[7], "manager_id": row[8],
            "created_at": row[9], "username": row[10], "first_name": row[11], "phone": row[12]
        }
    return None


def get_user_active_order(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id FROM orders 
        WHERE user_id = ? AND status NOT IN ('completed', 'cancelled')
        ORDER BY id DESC LIMIT 1
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return get_order(row[0])
    return None


def get_new_orders():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM orders WHERE status = 'new' ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [get_order(r[0]) for r in rows]


def get_active_orders():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM orders WHERE status NOT IN ('completed', 'cancelled') ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [get_order(r[0]) for r in rows]


def update_order(order_id, **kwargs):
    conn = get_db()
    c = conn.cursor()
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [order_id]
    c.execute(f"UPDATE orders SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


# === STATES ===

def get_state(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT state, data FROM states WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return (row[0], row[1]) if row else (None, None)


def set_state(user_id, state, data=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO states (user_id, state, data) VALUES (?, ?, ?)", (user_id, state, data))
    conn.commit()
    conn.close()


def clear_state(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM states WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# === MANAGERS ===

def get_managers():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username FROM managers")
    rows = c.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1]} for r in rows]


def get_manager_ids():
    return [m["user_id"] for m in get_managers()]


def add_manager(user_id, username=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO managers (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()


def remove_manager(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM managers WHERE user_id = ?", (user_id,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def is_manager(user_id):
    return user_id in get_manager_ids()


# === SETTINGS ===

def get_setting(key, default=None):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_rate():
    return float(get_setting("rate", "12.85"))


def set_rate(rate):
    set_setting("rate", str(rate))


# === STATS ===

def get_stats():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM orders")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
    completed = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(rub_amount), 0) FROM orders WHERE status = 'completed'")
    total_rub = c.fetchone()[0]
    
    c.execute("SELECT COALESCE(SUM(cny_amount), 0) FROM orders WHERE status = 'completed'")
    total_cny = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status NOT IN ('completed', 'cancelled')")
    active = c.fetchone()[0]
    
    conn.close()
    return {
        "total": total,
        "completed": completed,
        "active": active,
        "total_rub": total_rub,
        "total_cny": total_cny
    }


init_db()
