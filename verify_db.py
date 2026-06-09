import database as db
db.init_db()
import sqlite3
conn = sqlite3.connect('nutrition.db')
cols = {r[1] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
print('coeff_col:', 'coefficient_proteines' in cols)
print('eau_col:', 'objectif_eau_ml' in cols)
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
print('suivi_eau:', 'suivi_eau' in tables)
conn.close()
