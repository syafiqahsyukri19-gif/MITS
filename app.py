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

    # Primary Key gabungan (item_code + item_type + brand)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_code TEXT NOT NULL,
            item_type TEXT NOT NULL,
            brand TEXT NOT NULL,
            rack_location TEXT,
            PRIMARY KEY (item_code, item_type, brand)
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

    # Query Stok - Diasingkan mengikut Kod, Jenis & Brand
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
        GROUP BY i.item_code, i.item_type, i.brand
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
    rack_location = request.form.get('rack_location', '').strip()

    tarikh_semasa = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO items (item_code, item_type, brand, rack_location)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(item_code, item_type, brand) DO UPDATE SET
            rack_location = CASE WHEN excluded.rack_location != '' THEN excluded.rack_location ELSE items.rack_location END
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
    handled_by = request.form.get('handled_by', '').strip()

    if not handled_by:
        handled_by = "Pengguna"

    tarikh_semasa = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Dapatkan baki stok semasa dan lokasi rak asal sebelum item dipadam
    cursor.execute('''
        SELECT 
            COALESCE(SUM(CASE WHEN l.txn_type = 'IN' THEN l.qty WHEN l.txn_type = 'OUT' THEN -l.qty END), 0) AS current_stock,
            COALESCE(NULLIF(i.rack_location, ''), '-') AS rack
        FROM items i
        LEFT JOIN stock_logs l 
            ON i.item_code = l.item_code 
           AND i.item_type = l.item_type 
           AND i.brand = l.brand
        WHERE i.item_code = ? AND i.item_type = ? AND i.brand = ?
        GROUP BY i.item_code, i.item_type, i.brand
    ''', (kod, jenis, brand))
    
    row = cursor.fetchone()
    baki_stok = row[0] if row else 0
    rack_asal = row[1] if (row and row[1]) else '-'

    # 2. Padam item dari senarai aktif (Dashboard)
    cursor.execute('''
        DELETE FROM items 
        WHERE item_code = ? AND item_type = ? AND brand = ?
    ''', (kod, jenis, brand))

    # 3. Simpan log transaksi pemadaman dengan tanda (DIPADAM) pada rak
    rack_log = f"{rack_asal} (DIPADAM)"
    cursor.execute('''
        INSERT INTO stock_logs (timestamp, item_code, item_type, brand, txn_type, qty, handled_by, rack_location)
        VALUES (?, ?, ?, ?, 'OUT', ?, ?, ?)
    ''', (tarikh_semasa, kod, jenis, brand, baki_stok, handled_by, rack_log))
    
    conn.commit()
    conn.close()

    flash(f"Item '{kod}' ({jenis} - {brand}) berjaya dipadam oleh {handled_by}!", "success")
    return redirect(url_for('dashboard'))

# Pastikan ini sentiasa berada di bahagian PALING BAWAH
if __name__ == '__main__':
    app.run(debug=True, port=5000)