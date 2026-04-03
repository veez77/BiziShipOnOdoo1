import psycopg2
conn = psycopg2.connect("dbname='biziship_db' user='odoo' password='Bilbil01' host='localhost' port='5432'")
cur = conn.cursor()
cur.execute("SELECT name, state FROM ir_module_module WHERE name in ('BiziShip', 'biziship')")
print("Module states:", cur.fetchall())
cur.execute("DELETE FROM ir_module_module WHERE name='BiziShip'")
conn.commit()
print("Deleted BiziShip from DB.")
