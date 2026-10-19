-- Jadual 1: Maklumat Alat Ganti (Master Data)
CREATE TABLE IF NOT EXISTS items (
    item_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    rack_location TEXT NOT NULL,
    min_stock INTEGER DEFAULT 3
);

-- Jadual 2: Log Pergerakan Stok (Audit Trail untuk Tracking)
CREATE TABLE IF NOT EXISTS stock_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    item_code TEXT NOT NULL,
    txn_type TEXT CHECK(txn_type IN ('IN', 'OUT')) NOT NULL,
    qty INTEGER NOT NULL,
    job_id TEXT,               -- No. Job Repair / PO
    handled_by TEXT NOT NULL,  -- Nama Teknisi / Staf
    remarks TEXT,
    FOREIGN KEY(item_code) REFERENCES items(item_code)
);