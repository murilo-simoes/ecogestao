PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('gestor','operador','consulta'))
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sectors (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS partners (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, contact TEXT NOT NULL DEFAULT '',
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS records (
 id INTEGER PRIMARY KEY, metric TEXT NOT NULL CHECK(metric IN ('agua','energia','residuos')),
 date TEXT NOT NULL, quantity REAL NOT NULL CHECK(quantity > 0),
 sector_id INTEGER NOT NULL REFERENCES sectors(id), partner_id INTEGER REFERENCES partners(id),
 waste_type TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 created_by INTEGER NOT NULL REFERENCES users(id),
 CHECK((metric='residuos' AND partner_id IS NOT NULL AND waste_type<>'' AND destination<>'')
 OR (metric<>'residuos' AND partner_id IS NULL AND waste_type='' AND destination=''))
);
CREATE INDEX IF NOT EXISTS records_period ON records(date, sector_id, metric);
CREATE TABLE IF NOT EXISTS goals (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, metric TEXT NOT NULL CHECK(metric IN ('agua','energia','residuos')),
 sector_id INTEGER NOT NULL REFERENCES sectors(id), start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 limit_value REAL NOT NULL CHECK(limit_value>0), CHECK(start_date<=end_date)
);
CREATE TABLE IF NOT EXISTS actions (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
 sector_id INTEGER NOT NULL REFERENCES sectors(id), owner_id INTEGER NOT NULL REFERENCES users(id),
 due_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('aberta','em_andamento','concluida')),
 evidence TEXT NOT NULL DEFAULT '', completed_at TEXT,
 CHECK(status<>'concluida' OR (evidence<>'' AND completed_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), timestamp TEXT NOT NULL,
 operation TEXT NOT NULL, entity TEXT NOT NULL, entity_id INTEGER NOT NULL,
 before_json TEXT, after_json TEXT
);
