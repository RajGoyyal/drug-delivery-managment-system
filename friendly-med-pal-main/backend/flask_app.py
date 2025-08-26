import sqlite3
from pathlib import Path
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

DB_PATH = Path(__file__).resolve().parent / 'drug_delivery.db'

app = Flask(__name__, static_folder=str(Path(__file__).resolve().parent.parent), static_url_path='')
CORS(app)

ALLOWED_STATUSES = {"pending","delivered","missed","cancelled"}

# --- DB helpers -------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn

SCHEMA_CREATED = False

def init_db():
    global SCHEMA_CREATED
    if SCHEMA_CREATED:
        return
    conn = get_conn()
    with conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, age INTEGER, contact TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS drugs(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, dosage TEXT NOT NULL, frequency TEXT NOT NULL, stock INTEGER NOT NULL DEFAULT 0, reorder_level INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS delivery_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER NOT NULL, drug_id INTEGER NOT NULL, delivery_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','delivered','missed','cancelled')), FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE, FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE)""")
        # inventory tables
        conn.execute("""CREATE TABLE IF NOT EXISTS inventory_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, drug_id INTEGER NOT NULL, delta INTEGER NOT NULL, reason TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS drug_batches(id INTEGER PRIMARY KEY AUTOINCREMENT, drug_id INTEGER NOT NULL, batch_no TEXT, isbn TEXT, producer TEXT, transporter TEXT, mfg_date TEXT, exp_date TEXT, quantity INTEGER NOT NULL CHECK(quantity>0), notes TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS drug_removals(id INTEGER PRIMARY KEY AUTOINCREMENT, drug_id INTEGER NOT NULL, batch_no TEXT, reason TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0), notes TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(drug_id) REFERENCES drugs(id) ON DELETE CASCADE)""")
    conn.close()
    SCHEMA_CREATED = True

init_db()

# --- Utility ----------------------------------------------------------------

def row_list(cur):
    return [dict(r) for r in cur.fetchall()]

# --- Patients ---------------------------------------------------------------
@app.get('/api/patients')
def list_patients():
    conn=get_conn(); cur=conn.execute('SELECT id,name,age,contact FROM patients ORDER BY id'); data=row_list(cur); conn.close(); return jsonify(data)

@app.post('/api/patients')
def create_patient():
    payload=request.get_json(force=True)
    name=payload.get('name','').strip(); age=payload.get('age'); contact=payload.get('contact')
    if not name: return jsonify({'detail':'name required'}),400
    conn=get_conn();
    with conn:
        cur=conn.execute('INSERT INTO patients(name,age,contact) VALUES(?,?,?)',(name,age,contact))
        new_id=cur.lastrowid
    conn.close(); return jsonify({'id':new_id}),201

# --- Drugs ------------------------------------------------------------------
@app.get('/api/drugs')
def list_drugs():
    conn=get_conn(); cur=conn.execute('SELECT id,name,dosage,frequency,stock,reorder_level FROM drugs ORDER BY id'); data=row_list(cur); conn.close(); return jsonify(data)

@app.post('/api/drugs')
def create_drug():
    p=request.get_json(force=True); name=p.get('name','').strip(); dosage=p.get('dosage','').strip(); freq=p.get('frequency','').strip()
    if not (name and dosage and freq): return jsonify({'detail':'fields required'}),400
    stock=p.get('stock',0) or 0; reorder=p.get('reorder_level',0) or 0
    conn=get_conn();
    with conn:
        cur=conn.execute('INSERT INTO drugs(name,dosage,frequency,stock,reorder_level) VALUES(?,?,?,?,?)',(name,dosage,freq,stock,reorder))
        new_id=cur.lastrowid
    conn.close(); return jsonify({'id':new_id}),201

@app.patch('/api/drugs/<int:drug_id>')
def update_drug(drug_id):
    p=request.get_json(force=True)
    allowed=['name','dosage','frequency','stock','reorder_level']
    sets=[]; vals=[]
    for k in allowed:
        if k in p and p[k] is not None:
            sets.append(f"{k}=?"); vals.append(p[k])
    if not sets: return jsonify({'updated':0})
    vals.append(drug_id)
    conn=get_conn();
    with conn:
        cur=conn.execute(f"UPDATE drugs SET {', '.join(sets)} WHERE id=?", vals)
        updated=cur.rowcount
    conn.close(); return jsonify({'updated':updated})

@app.delete('/api/drugs/<int:drug_id>')
def delete_drug(drug_id):
    conn=get_conn();
    with conn:
        cur=conn.execute('DELETE FROM drugs WHERE id=?',(drug_id,))
        deleted=cur.rowcount
    conn.close();
    if not deleted: return jsonify({'detail':'Not found'}),404
    return jsonify({'deleted':True})

# --- Deliveries -------------------------------------------------------------
@app.get('/api/deliveries')
def list_deliveries():
    conn=get_conn(); cur=conn.execute("SELECT id, patient_id, drug_id, delivery_date AS scheduled_for, status, 1 AS quantity, NULL AS notes FROM delivery_logs ORDER BY id DESC"); data=row_list(cur); conn.close(); return jsonify(data)

@app.post('/api/deliveries')
def create_delivery():
    p=request.get_json(force=True)
    patient_id=p.get('patient_id'); drug_id=p.get('drug_id'); delivery_date=p.get('delivery_date'); status=p.get('status','pending')
    if status not in ALLOWED_STATUSES: return jsonify({'detail':'bad status'}),400
    try: date.fromisoformat(delivery_date)
    except Exception: return jsonify({'detail':'bad date'}),400
    conn=get_conn();
    with conn:
        cur=conn.execute('INSERT INTO delivery_logs(patient_id,drug_id,delivery_date,status) VALUES(?,?,?,?)',(patient_id,drug_id,delivery_date,status))
        new_id=cur.lastrowid
    conn.close(); return jsonify({'id':new_id}),201

@app.patch('/api/deliveries/<int:delivery_id>/status')
def update_delivery_status(delivery_id):
    p=request.get_json(force=True); status=p.get('status')
    if status not in ALLOWED_STATUSES: return jsonify({'detail':'bad status'}),400
    conn=get_conn();
    with conn:
        cur=conn.execute('UPDATE delivery_logs SET status=? WHERE id=?',(status,delivery_id))
        if cur.rowcount==0:
            conn.close(); return jsonify({'detail':'Not found'}),404
    conn.close(); return jsonify({'ok':True})

@app.delete('/api/deliveries/<int:delivery_id>')
def delete_delivery(delivery_id):
    conn=get_conn();
    with conn:
        cur=conn.execute('DELETE FROM delivery_logs WHERE id=?',(delivery_id,))
        deleted=cur.rowcount
    conn.close();
    if not deleted: return jsonify({'detail':'Not found'}),404
    return jsonify({'deleted':True})

# --- Inventory --------------------------------------------------------------
@app.get('/api/inventory/summary')
def inventory_summary():
    conn=get_conn();
    cur=conn.execute("SELECT id,name,dosage,frequency,stock,reorder_level,0 AS pending_quantity,NULL AS daily_avg,NULL AS days_supply FROM drugs ORDER BY name")
    data=row_list(cur); conn.close(); return jsonify(data)

@app.get('/api/inventory/transactions')
def inventory_transactions():
    limit=int(request.args.get('limit',300))
    conn=get_conn(); cur=conn.execute('SELECT id,drug_id,delta,reason,created_at FROM inventory_transactions ORDER BY id DESC LIMIT ?',(limit,)); data=row_list(cur); conn.close(); return jsonify(data)

@app.post('/api/inventory/adjust')
def inventory_adjust():
    p=request.get_json(force=True); drug_id=p.get('drug_id'); delta=int(p.get('delta',0)); reason=p.get('reason','manual')
    if not delta: return jsonify({'detail':'delta required'}),400
    conn=get_conn();
    with conn:
        cur=conn.execute('SELECT stock FROM drugs WHERE id=?',(drug_id,)); row=cur.fetchone()
        if not row: conn.close(); return jsonify({'detail':'drug not found'}),404
        new_stock=max(0,(row[0] or 0)+delta)
        conn.execute('UPDATE drugs SET stock=? WHERE id=?',(new_stock,drug_id))
        conn.execute('INSERT INTO inventory_transactions(drug_id,delta,reason) VALUES(?,?,?)',(drug_id,delta,reason))
    conn.close(); return jsonify({'ok':True})

@app.post('/api/drug_batches')
def create_batch():
    p=request.get_json(force=True)
    drug_id=p.get('drug_id'); qty=int(p.get('quantity',0));
    if qty<=0: return jsonify({'detail':'quantity must be positive'}),400
    conn=get_conn();
    with conn:
        conn.execute('INSERT INTO drug_batches(drug_id,batch_no,isbn,producer,transporter,mfg_date,exp_date,quantity,notes) VALUES(?,?,?,?,?,?,?,?,?)',(
            drug_id,p.get('batch_no'),p.get('isbn'),p.get('producer'),p.get('transporter'),p.get('mfg_date'),p.get('exp_date'),qty,p.get('notes')
        ))
        conn.execute('UPDATE drugs SET stock=COALESCE(stock,0)+? WHERE id=?',(qty,drug_id))
        conn.execute('INSERT INTO inventory_transactions(drug_id,delta,reason) VALUES(?,?,?)',(drug_id,qty,f"batch:{p.get('batch_no') or ''}"))
    conn.close(); return jsonify({'ok':True}),201

@app.get('/api/drug_batches')
def list_batches():
    drug_id=request.args.get('drug_id'); params=[]; where=''
    if drug_id:
        where=' WHERE drug_id=?'; params.append(drug_id)
    limit=int(request.args.get('limit',200))
    params.append(limit)
    conn=get_conn(); cur=conn.execute('SELECT id,drug_id,batch_no,isbn,producer,transporter,mfg_date,exp_date,quantity,notes,created_at FROM drug_batches'+where+' ORDER BY id DESC LIMIT ?',params); data=row_list(cur); conn.close(); return jsonify(data)

@app.post('/api/drug_removals')
def create_removal():
    p=request.get_json(force=True); drug_id=p.get('drug_id'); qty=int(p.get('quantity',0)); reason=p.get('reason','').strip()
    if qty<=0: return jsonify({'detail':'quantity must be positive'}),400
    if not reason: return jsonify({'detail':'reason required'}),400
    conn=get_conn();
    with conn:
        cur=conn.execute('SELECT stock FROM drugs WHERE id=?',(drug_id,)); row=cur.fetchone()
        if not row: conn.close(); return jsonify({'detail':'drug not found'}),404
        new_stock=max(0,(row[0] or 0)-qty)
        conn.execute('UPDATE drugs SET stock=? WHERE id=?',(new_stock,drug_id))
        conn.execute('INSERT INTO drug_removals(drug_id,batch_no,reason,quantity,notes) VALUES(?,?,?,?,?)',(drug_id,p.get('batch_no'),reason,qty,p.get('notes')))
        conn.execute('INSERT INTO inventory_transactions(drug_id,delta,reason) VALUES(?,?,?)',(drug_id,-qty,f'remove:{reason}'))
    conn.close(); return jsonify({'ok':True}),201

@app.get('/api/drug_removals')
def list_removals():
    drug_id=request.args.get('drug_id'); params=[]; where=''
    if drug_id:
        where=' WHERE drug_id=?'; params.append(drug_id)
    limit=int(request.args.get('limit',200)); params.append(limit)
    conn=get_conn(); cur=conn.execute('SELECT id,drug_id,batch_no,reason,quantity,notes,created_at FROM drug_removals'+where+' ORDER BY id DESC LIMIT ?',params); data=row_list(cur); conn.close(); return jsonify(data)

# --- Stats / Health ---------------------------------------------------------
@app.get('/api/stats')
def stats():
    conn=get_conn(); cur=conn.execute('SELECT COUNT(*) FROM patients'); patients=cur.fetchone()[0]
    cur=conn.execute('SELECT COUNT(*) FROM drugs'); drugs=cur.fetchone()[0]
    today=date.today().isoformat()
    cur=conn.execute("SELECT COUNT(*) FROM delivery_logs WHERE status='pending'"); pending=cur.fetchone()[0]
    cur=conn.execute("SELECT COUNT(*) FROM delivery_logs WHERE status='delivered' AND delivery_date=?",(today,)); completed=cur.fetchone()[0]
    cur=conn.execute("SELECT COUNT(*) FROM delivery_logs WHERE status='missed'"); missed=cur.fetchone()[0]
    cur=conn.execute("SELECT COUNT(*) FROM delivery_logs WHERE status='pending' AND delivery_date>=?",(today,)); upcoming=cur.fetchone()[0]
    conn.close()
    return jsonify({
        'totalPatients':patients,
        'totalDrugs':drugs,
        'pendingDeliveries':pending,
        'completedToday':completed,
        'missedDeliveries':missed,
        'upcomingDeliveries':upcoming
    })

@app.get('/api/health')
def health():
    return jsonify({'status':'ok','time': datetime.utcnow().isoformat()})

# --- SPA index passthrough --------------------------------------------------
@app.get('/')
def root():
    """Serve built frontend if present, else fallback to original index.html at repo root."""
    repo_root = Path(__file__).resolve().parent.parent
    dist_index = repo_root / 'dist' / 'index.html'
    if dist_index.exists():
        return send_from_directory(dist_index.parent, 'index.html')
    return send_from_directory(repo_root, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
