import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "kunci_rahsia_multitronik"
DB_NAME = "inventory.db"

def init_sqlite_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            item_code TEXT NOT NULL,
            item_type TEXT NOT NULL,
            brand TEXT NOT NULL,
            txn_type TEXT CHECK(txn_type IN ('IN', 'OUT')) NOT NULL,
            qty INTEGER NOT NULL,
            handled_by TEXT NOT NULL,
            rack_location TEXT
        )
    ''')

    # Re-create jadual items untuk barang AKTIF sahaja (Primary Key termasuk lokasi rak)
    cursor.execute("DROP TABLE IF EXISTS items")
    cursor.execute('''
        CREATE TABLE items (
            item_code TEXT NOT NULL,
            item_type TEXT NOT NULL,
            brand TEXT NOT NULL,
            rack_location TEXT NOT NULL DEFAULT '-',
            PRIMARY KEY (item_code, item_type, brand, rack_location)
        )
    ''')

    # Pembersihan Automatik: Hanya masukkan item AKTIF dari stock_logs ke dalam items
    cursor.execute('''
        INSERT OR IGNORE INTO items (item_code, item_type, brand, rack_location)
        SELECT 
            l.item_code,
            l.item_type,
            l.brand,
            COALESCE(NULLIF(REPLACE(l.rack_location, ' (DIPADAM)', ''), ''), '-') AS rack
        FROM stock_logs l
        GROUP BY l.item_code, l.item_type, l.brand, COALESCE(NULLIF(REPLACE(l.rack_location, ' (DIPADAM)', ''), ''), '-')
        HAVING MAX(CASE WHEN l.rack_location LIKE '%(DIPADAM)%' THEN 1 ELSE 0 END) = 0
           AND SUM(CASE WHEN l.txn_type = 'IN' THEN l.qty WHEN l.txn_type = 'OUT' THEN -l.qty END) > 0
    ''')

    conn.commit()
    conn.close()

init_sqlite_db()

@app.route('/')
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM categories ORDER BY name ASC")
    categories = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT name FROM brands ORDER BY name ASC")
    brands = [row[0] for row in cursor.fetchall()]

    # Query Dashboard: Hanya ambil item AKTIF dari jadual items
    query = '''
        SELECT 
            i.item_code, 
            i.item_type,
            i.brand,
            COALESCE(NULLIF(i.rack_location, ''), '-') AS rack, 
            COALESCE(SUM(CASE WHEN l.txn_type = 'IN' THEN l.qty WHEN l.txn_type = 'OUT' THEN -l.qty END), 0) AS current_stock
        FROM items i
        LEFT JOIN stock_logs l 
            ON i.item_code = l.item_code 
           AND i.item_type = l.item_type 
           AND i.brand = l.brand
           AND COALESCE(NULLIF(REPLACE(l.rack_location, ' (DIPADAM)', ''), ''), '-') = COALESCE(NULLIF(i.rack_location, ''), '-')
        GROUP BY i.item_code, i.item_type, i.brand, COALESCE(NULLIF(i.rack_location, ''), '-')
        ORDER BY i.item_code ASC
    '''
    cursor.execute(query)
    items = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', categories=categories, brands=brands, items=items)

@app.route('/add-category', methods=['POST'])
def add_category():
    name = request.form.get('name', '').strip()
    if name:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            conn.commit()
            flash(f"Jenis '{name}' berjaya ditambah!", "success")
        except sqlite3.IntegrityError:
            flash(f"Jenis '{name}' sudah wujud!", "danger")
        finally:
            conn.close()
    return redirect(url_for('dashboard'))

@app.route('/add-brand', methods=['POST'])
def add_brand():
    name = request.form.get('name', '').strip()
    if name:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO brands (name) VALUES (?)", (name,))
            conn.commit()
            flash(f"Brand '{name}' berjaya ditambah!", "success")
        except sqlite3.IntegrityError:
            flash(f"Brand '{name}' sudah wujud!", "danger")
        finally:
            conn.close()
    return redirect(url_for('dashboard'))

@app.route('/transaction', methods=['POST'])
def add_transaction():
    item_code = request.form.get('item_code', '').strip().upper()
    item_type = request.form.get('item_type')
    brand = request.form.get('brand')
    qty = int(request.form.get('qty', 1))
    txn_type = request.form.get('txn_type')
    handled_by = request.form.get('handled_by', '').strip()
    rack_location = request.form.get('rack_location', '').strip() or '-'

    tarikh_semasa = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Masukkan ke dalam jadual items (jika belum ada)
    cursor.execute('''
        INSERT OR IGNORE INTO items (item_code, item_type, brand, rack_location)
        VALUES (?, ?, ?, ?)
    ''', (item_code, item_type, brand, rack_location))

    cursor.execute('''
        INSERT INTO stock_logs (timestamp, item_code, item_type, brand, txn_type, qty, handled_by, rack_location)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (tarikh_semasa, item_code, item_type, brand, txn_type, qty, handled_by, rack_location))

    conn.commit()
    conn.close()

    flash("Data pergerakan stok berjaya disimpan!", "success")
    return redirect(url_for('dashboard'))

@app.route('/logs')
def view_logs():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT l.id, l.timestamp, l.item_code, l.item_type, l.brand, l.txn_type, l.qty, l.handled_by, COALESCE(NULLIF(l.rack_location, ''), '-')
        FROM stock_logs l
        ORDER BY l.id DESC
    ''')
    logs = cursor.fetchall()
    conn.close()
    return render_template('logs.html', logs=logs)

@app.route('/delete', methods=['POST'])
def delete_item():
    kod = request.form.get('kod')
    jenis = request.form.get('jenis')
    brand = request.form.get('brand')
    rack = request.form.get('rack', '-').strip() or '-'
    handled_by = request.form.get('handled_by', '').strip()

    if not handled_by:
        handled_by = "Pengguna"

    tarikh_semasa = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Kira baki stok semasa khusus untuk item dan lokasi rak ini
    cursor.execute('''
        SELECT COALESCE(SUM(CASE WHEN txn_type = 'IN' THEN qty WHEN txn_type = 'OUT' THEN -qty END), 0)
        FROM stock_logs
        WHERE item_code = ? AND item_type = ? AND brand = ? 
          AND COALESCE(NULLIF(REPLACE(rack_location, ' (DIPADAM)', ''), ''), '-') = ?
    ''', (kod, jenis, brand, rack))
    
    row = cursor.fetchone()
    baki_stok = row[0] if row else 0

    # 2. Padam item dari senarai aktif (Dashboard)
    cursor.execute('''
        DELETE FROM items 
        WHERE item_code = ? AND item_type = ? AND brand = ? 
          AND COALESCE(NULLIF(rack_location, ''), '-') = ?
    ''', (kod, jenis, brand, rack))

    # 3. Simpan log pemadaman ke dalam stock_logs
    rack_log = f"{rack} (DIPADAM)" if rack != '-' else "(DIPADAM)"
    cursor.execute('''
        INSERT INTO stock_logs (timestamp, item_code, item_type, brand, txn_type, qty, handled_by, rack_location)
        VALUES (?, ?, ?, ?, 'OUT', ?, ?, ?)
    ''', (tarikh_semasa, kod, jenis, brand, baki_stok, handled_by, rack_log))
    
    conn.commit()
    conn.close()

    flash(f"Item '{kod}' ({jenis} - {brand}) di lokasi '{rack}' berjaya dipadam oleh {handled_by}!", "success")
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)