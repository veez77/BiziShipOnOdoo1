import psycopg2

try:
    conn = psycopg2.connect(
        dbname='biziship_db', 
        user='odoo', 
        password='Bilbil01', 
        host='localhost'
    )
    cur = conn.cursor()
    
    # 1. DELETE ANY attachment named icon.png related to our app
    # This targets Odoo's internal cache of module icons
    cur.execute("""
        DELETE FROM ir_attachment 
        WHERE (name = 'icon.png' OR url LIKE '%/static/description/icon.png')
        AND (res_model = 'ir.module.module' OR url LIKE '%BiziShip%')
    """)
    attachments_deleted = cur.rowcount
    
    # 2. Reset the module record's icon_file field (if it exists)
    try:
        cur.execute("UPDATE ir_module_module SET icon = '/BiziShip/static/description/icon.png' WHERE name = 'BiziShip'")
        module_updated = cur.rowcount
    except Exception:
        module_updated = "Error updating icon field"
        conn.rollback()
        conn = psycopg2.connect(dbname='biziship_db', user='odoo', password='Bilbil01', host='localhost')
        cur = conn.cursor()

    conn.commit()
    
    print(f"Cleanup Successful!")
    print(f"- Deleted persistent attachments: {attachments_deleted} row(s)")
    print(f"- Module record refresh: {module_updated}")
    print("\nNext step: Restart Odoo and 'Upgrade' the BiziShip module one last time.")
    
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
