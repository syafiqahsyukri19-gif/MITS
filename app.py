from datetime import datetime
import os
from flask import Flask, flash, redirect, render_template, request, url_for
import psycopg2

app = Flask(__name__)
app.secret_key = "ganti_dengan_secret_key_yang_selamat"  # Diperlukan untuk flask flash messages

# Ambil URL dari Environment Variable Render, atau guna URL Supabase secara terus
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:kata_laluan_anda@db.projek-anda.supabase.co:5432/postgres",
)


def get_db_connection():
  conn = psycopg2.connect(DATABASE_URL)
  return conn


def init_db():
  conn = get_db_connection()
  cursor = conn.cursor()

  # 1. Jadual Categories
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    """)

  # 2. Jadual Brands
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS brands (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    """)

  # 3. Jadual Stock Logs
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            item_code TEXT NOT NULL,
            item_type TEXT NOT NULL,
            brand TEXT NOT NULL,
            txn_type TEXT NOT NULL,
            qty INTEGER NOT NULL,
            handled_by TEXT NOT NULL,
            rack_location TEXT
        )
    """)

  # 4. Jadual Items (Barang Aktif)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            item_code TEXT NOT NULL,
            item_type TEXT NOT NULL,
            brand TEXT NOT NULL,
            rack_location TEXT NOT NULL DEFAULT '-',
            PRIMARY KEY (item_code, item_type, brand, rack_location)
        )
    """)

  conn.commit()
  cursor.close()
  conn.close()


# Jalankan fungsi bina jadual semasa mula-mula start
init_db()


@app.route("/")
def dashboard():
  conn = get_db_connection()
  cursor = conn.cursor()

  cursor.execute("SELECT name FROM categories ORDER BY name ASC")
  categories = [row[0] for row in cursor.fetchall()]

  cursor.execute("SELECT name FROM brands ORDER BY name ASC")
  brands = [row[0] for row in cursor.fetchall()]

  # Query Dashboard menggunakan PostgreSQL syntax
  query = """
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
    """
  cursor.execute(query)
  items = cursor.fetchall()

  cursor.close()
  conn.close()

  return render_template(
      "dashboard.html", categories=categories, brands=brands, items=items
  )


@app.route("/add-category", methods=["POST"])
def add_category():
  name = request.form.get("name", "").strip()
  if name:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
      cursor.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
      conn.commit()
      flash(f"Jenis '{name}' berjaya ditambah!", "success")
    except Exception:
      conn.rollback()
      flash(f"Jenis '{name}' sudah wujud!", "danger")
    finally:
      cursor.close()
      conn.close()
  return redirect(url_for("dashboard"))


@app.route("/add-brand", methods=["POST"])
def add_brand():
  name = request.form.get("name", "").strip()
  if name:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
      cursor.execute("INSERT INTO brands (name) VALUES (%s)", (name,))
      conn.commit()
      flash(f"Brand '{name}' berjaya ditambah!", "success")
    except Exception:
      conn.rollback()
      flash(f"Brand '{name}' sudah wujud!", "danger")
    finally:
      cursor.close()
      conn.close()
  return redirect(url_for("dashboard"))


@app.route("/transaction", methods=["POST"])
def add_transaction():
  item_code = request.form.get("item_code", "").strip().upper()
  item_type = request.form.get("item_type")
  brand = request.form.get("brand")
  qty = int(request.form.get("qty", 1))
  txn_type = request.form.get("txn_type")
  handled_by = request.form.get("handled_by", "").strip()
  rack_location = request.form.get("rack_location", "").strip() or "-"

  tarikh_semasa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  conn = get_db_connection()
  cursor = conn.cursor()

  # Masukkan ke dalam jadual items (jika belum ada - PostgreSQL UPSERT syntax)
  cursor.execute(
      """
        INSERT INTO items (item_code, item_type, brand, rack_location)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (item_code, item_type, brand, rack_location) DO NOTHING
    """,
      (item_code, item_type, brand, rack_location),
  )

  cursor.execute(
      """
        INSERT INTO stock_logs (timestamp, item_code, item_type, brand, txn_type, qty, handled_by, rack_location)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """,
      (
          tarikh_semasa,
          item_code,
          item_type,
          brand,
          txn_type,
          qty,
          handled_by,
          rack_location,
      ),
  )

  conn.commit()
  cursor.close()
  conn.close()

  flash("Data pergerakan stok berjaya disimpan!", "success")
  return redirect(url_for("dashboard"))


@app.route("/logs")
def view_logs():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("""
        SELECT l.id, l.timestamp, l.item_code, l.item_type, l.brand, l.txn_type, l.qty, l.handled_by, COALESCE(NULLIF(l.rack_location, ''), '-')
        FROM stock_logs l
        ORDER BY l.id DESC
    """)
  logs = cursor.fetchall()
  cursor.close()
  conn.close()
  return render_template("logs.html", logs=logs)


@app.route("/delete", methods=["POST"])
def delete_item():
  kod = request.form.get("kod")
  jenis = request.form.get("jenis")
  brand = request.form.get("brand")
  rack = request.form.get("rack", "-").strip() or "-"
  handled_by = request.form.get("handled_by", "").strip()

  if not handled_by:
    handled_by = "Pengguna"

  tarikh_semasa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  conn = get_db_connection()
  cursor = conn.cursor()

  # 1. Kira baki stok semasa
  cursor.execute(
      """
        SELECT COALESCE(SUM(CASE WHEN txn_type = 'IN' THEN qty WHEN txn_type = 'OUT' THEN -qty END), 0)
        FROM stock_logs
        WHERE item_code = %s AND item_type = %s AND brand = %s 
          AND COALESCE(NULLIF(REPLACE(rack_location, ' (DIPADAM)', ''), ''), '-') = %s
    """,
      (kod, jenis, brand, rack),
  )

  row = cursor.fetchone()
  baki_stok = row[0] if row else 0

  # 2. Padam item dari senarai aktif (Dashboard)
  cursor.execute(
      """
        DELETE FROM items 
        WHERE item_code = %s AND item_type = %s AND brand = %s 
          AND COALESCE(NULLIF(rack_location, ''), '-') = %s
    """,
      (kod, jenis, brand, rack),
  )

  # 3. Simpan log pemadaman
  rack_log = f"{rack} (DIPADAM)" if rack != "-" else "(DIPADAM)"
  cursor.execute(
      """
        INSERT INTO stock_logs (timestamp, item_code, item_type, brand, txn_type, qty, handled_by, rack_location)
        VALUES (%s, %s, %s, %s, 'OUT', %s, %s, %s)
    """,
      (tarikh_semasa, kod, jenis, brand, baki_stok, handled_by, rack_log),
  )

  conn.commit()
  cursor.close()
  conn.close()

  flash(
      f"Item '{kod}' ({jenis} - {brand}) di lokasi '{rack}' berjaya dipadam oleh"
      f" {handled_by}!",
      "success",
  )
  return redirect(url_for("dashboard"))

@app.route('/edit-stock', methods=['POST'])
def edit_stock():
    try:
        kod = request.form.get('kod')
        jenis = request.form.get('jenis')
        brand = request.form.get('brand')
        rack = request.form.get('rack', '-').strip() or '-'
        
        # 1. Pastikan medan utama tidak kosong
        if not kod or not jenis or not brand:
            flash("Ralat: Maklumat barang tidak lengkap!", "danger")
            return redirect(url_for('dashboard'))

        # 2. Elakkan ValueError jika new_qty kosong
        raw_qty = request.form.get('new_qty', '').strip()
        if not raw_qty.isdigit():
            flash("Ralat: Sila masukkan kuantiti angka yang sah!", "danger")
            return redirect(url_for('dashboard'))
            
        new_qty = int(raw_qty)
        handled_by = request.form.get('handled_by', '').strip() or 'Pengguna'
        new_rack_input = request.form.get('new_rack_location', '').strip()
        
        target_rack = rack
        rack_changed = False
        if (not rack or rack == '-') and new_rack_input:
            target_rack = new_rack_input
            rack_changed = True

        tarikh_semasa = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Dapatkan stok semasa dari log
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN txn_type = 'IN' THEN qty WHEN txn_type = 'OUT' THEN -qty ELSE 0 END), 0)
            FROM stock_logs
            WHERE item_code = %s AND item_type = %s AND brand = %s 
              AND COALESCE(NULLIF(REPLACE(rack_location, ' (DIPADAM)', ''), ''), '-') = %s
        """, (kod, jenis, brand, rack))

        row = cursor.fetchone()
        current_qty = row[0] if row else 0

        diff = new_qty - current_qty

        if rack_changed:
            cursor.execute("""
                INSERT INTO items (item_code, item_type, brand, rack_location)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (item_code, item_type, brand, rack_location) DO NOTHING
            """, (kod, jenis, brand, target_rack))

            cursor.execute("""
                DELETE FROM items 
                WHERE item_code = %s AND item_type = %s AND brand = %s AND rack_location = %s
            """, (kod, jenis, brand, rack))

        if diff != 0 or rack_changed:
            cursor.execute("""
                INSERT INTO stock_logs (timestamp, item_code, item_type, brand, txn_type, qty, handled_by, rack_location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (tarikh_semasa, kod, jenis, brand, 'EDIT', new_qty, handled_by, target_rack))

            conn.commit()
            flash(f"Maklumat untuk '{kod}' berjaya dikemas kini!", "success")
        else:
            flash("Tiada perubahan dibuat pada kuantiti atau lokasi stok.", "info")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Ralat edit_stock: {e}")
        flash("Gagal mengemas kini stok. Sila semak semula input anda.", "danger")

    return redirect(url_for('dashboard'))

if __name__ == "__main__":
  app.run(debug=True, port=5000)
  