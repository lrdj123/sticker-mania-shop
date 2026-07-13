import os
import sqlite3
import uuid
import logging
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'sticker_mania_secret_2026')

DB_PATH = os.path.join(os.path.dirname(__file__), 'sticker_mania.db')

# ─── STICKERS ─────────────────────────────────────────────────
STICKERS = [
    {'id': 'man_01', 'nome': 'Dança Feliz',   'gratis': 5},
    {'id': 'man_02', 'nome': 'Groove Master',  'gratis': 5},
    {'id': 'man_03', 'nome': 'Festa Total',    'gratis': 5},
    {'id': 'man_04', 'nome': 'Rei da Pista',   'gratis': 5},
    {'id': 'man_05', 'nome': 'Vibe Noturna',   'gratis': 5},
    {'id': 'man_06', 'nome': 'Estilo Livre',   'gratis': 5},
    {'id': 'man_07', 'nome': 'Mestre do Flow', 'gratis': 5},
    {'id': 'man_08', 'nome': 'Lenda Urbana',   'gratis': 5},
]

PACOTES = {
    'completo':  {'nome': 'Pacote Completo',  'preco': 5, 'descricao': 'Todos os 8 stickers animados!'},
    'premium':   {'nome': 'Pacote Premium',   'preco': 7, 'descricao': 'Todos os stickers + prioridade em novos lançamentos'},
    'personalizado': {'nome': 'Pacote Personalizado', 'preco': 10, 'descricao': 'Todos os stickers + 1 sticker personalizado do seu vídeo'},
}

PIX_CODIGO = '00020101021126580014BR.GOV.BCB.PIX013654956a7e-2d21-4c81-9839-2e24c3d6ba625204000053039865802BR5915Lucas Rodrigues6009SAO PAULO62080504daqr6304B6A9'
CODIGO_SEGURANCA = 'SM-LUCAS-2026'

# ─── BANCO ────────────────────────────────────────────────────
def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
            email TEXT PRIMARY KEY,
            apelido TEXT NOT NULL,
            criado_em TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sticker_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            sticker_id TEXT NOT NULL,
            usos_restantes INTEGER DEFAULT 5,
            comprado INTEGER DEFAULT 0,
            UNIQUE(email, sticker_id)
        );
        CREATE TABLE IF NOT EXISTS pagamentos (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            pacote TEXT NOT NULL,
            valor REAL NOT NULL,
            status TEXT DEFAULT 'pendente',
            criado_em TEXT DEFAULT (datetime('now')),
            pago_em TEXT
        );
    ''')
    conn.commit()
    conn.close()

init_db()

# ─── ROTAS ────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('loja'))
    return render_template('login.html')

@app.route('/entrar', methods=['POST'])
def entrar():
    email = request.form.get('email', '').strip().lower()
    apelido = request.form.get('apelido', '').strip()
    if not email or '@' not in email:
        return render_template('login.html', erro='E-mail inválido')
    if not apelido:
        apelido = email.split('@')[0]
    
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO usuarios (email, apelido) VALUES (?, ?)", (email, apelido))
    conn.commit()
    conn.close()
    
    session['email'] = email
    session['apelido'] = apelido
    return redirect(url_for('loja'))

@app.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('index'))

@app.route('/loja')
def loja():
    if 'email' not in session:
        return redirect(url_for('index'))
    return render_template('loja.html', stickers=STICKERS, pacotes=PACOTES)

# ─── API ──────────────────────────────────────────────────────

@app.route('/api/meus_stickers')
def api_meus_stickers():
    email = session.get('email', '')
    if not email:
        return jsonify({'error': 'Não logado'}), 401
    
    conn = get_db()
    rows = conn.execute(
        "SELECT sticker_id, usos_restantes, comprado FROM sticker_usage WHERE email=?",
        (email,)
    ).fetchall()
    conn.close()
    
    dados = {}
    for r in rows:
        dados[r['sticker_id']] = {
            'usos_restantes': r['usos_restantes'],
            'comprado': bool(r['comprado'])
        }
    
    return jsonify({'stickers': dados, 'email': email})

@app.route('/api/sticker/status/<sticker_id>')
def api_sticker_status(sticker_id):
    email = session.get('email', '')
    if not email:
        return jsonify({'error': 'Não logado'}), 401
    
    sticker_info = next((s for s in STICKERS if s['id'] == sticker_id), None)
    if not sticker_info:
        return jsonify({'error': 'Sticker não encontrado'}), 404
    
    conn = get_db()
    row = conn.execute(
        "SELECT usos_restantes, comprado FROM sticker_usage WHERE email=? AND sticker_id=?",
        (email, sticker_id)
    ).fetchone()
    conn.close()
    
    if row:
        return jsonify({
            'sticker_id': sticker_id,
            'comprado': bool(row['comprado']),
            'usos_restantes': row['usos_restantes']
        })
    
    return jsonify({
        'sticker_id': sticker_id,
        'comprado': False,
        'usos_restantes': sticker_info['gratis']
    })

@app.route('/api/usar/<sticker_id>', methods=['POST'])
def api_usar_sticker(sticker_id):
    """Registra um uso. Retorna se pode usar ou não."""
    email = session.get('email', '')
    if not email:
        return jsonify({'error': 'Não logado'}), 401
    
    sticker_info = next((s for s in STICKERS if s['id'] == sticker_id), None)
    if not sticker_info:
        return jsonify({'error': 'Sticker inválido'}), 404
    
    conn = get_db()
    row = conn.execute(
        "SELECT usos_restantes, comprado FROM sticker_usage WHERE email=? AND sticker_id=?",
        (email, sticker_id)
    ).fetchone()
    
    if row and row['comprado']:
        conn.close()
        return jsonify({'pode_usar': True, 'ilimitado': True})
    
    usos = row['usos_restantes'] if row else sticker_info['gratis']
    
    if usos > 0:
        conn.execute('''
            INSERT INTO sticker_usage (email, sticker_id, usos_restantes, comprado)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(email, sticker_id) DO UPDATE SET usos_restantes = usos_restantes - 1
        ''', (email, sticker_id, sticker_info['gratis']))
        conn.commit()
        conn.close()
        return jsonify({'pode_usar': True, 'ilimitado': False, 'usos_restantes': usos - 1})
    
    conn.close()
    return jsonify({'pode_usar': False, 'motivo': 'acabou', 'usos_restantes': 0})

@app.route('/api/comprar/<pacote>', methods=['POST'])
def api_comprar(pacote):
    email = session.get('email', '')
    if not email:
        return jsonify({'error': 'Não logado'}), 401
    
    if pacote not in PACOTES:
        return jsonify({'error': 'Pacote inválido'}), 400
    
    info = PACOTES[pacote]
    pagamento_id = str(uuid.uuid4())[:8].upper()
    
    conn = get_db()
    conn.execute(
        "INSERT INTO pagamentos (id, email, pacote, valor, status) VALUES (?, ?, ?, ?, 'pendente')",
        (pagamento_id, email, pacote, info['preco'])
    )
    conn.commit()
    conn.close()
    
    return jsonify({
        'ok': True,
        'pagamento_id': pagamento_id,
        'pacote': pacote,
        'valor': info['preco'],
        'pix_codigo': PIX_CODIGO
    })

@app.route('/api/webhook/pago', methods=['POST'])
def api_webhook_pago():
    """WEBHOOK: chamado quando PIX é confirmado"""
    data = request.get_json() or {}
    if data.get('codigo') != CODIGO_SEGURANCA:
        return jsonify({'error': 'Não autorizado'}), 403
    
    email = data.get('email', '')
    pagamento_id = data.get('pagamento_id', '')
    
    if not email:
        return jsonify({'error': 'E-mail obrigatório'}), 400
    
    conn = get_db()
    
    # Se veio ID de pagamento, marca como pago
    if pagamento_id:
        conn.execute(
            "UPDATE pagamentos SET status='pago', pago_em=datetime('now') WHERE id=? AND email=?",
            (pagamento_id, email)
        )
    
    # Libera todos os stickers
    for s in STICKERS:
        conn.execute('''
            INSERT INTO sticker_usage (email, sticker_id, usos_restantes, comprado)
            VALUES (?, ?, 0, 1)
            ON CONFLICT(email, sticker_id) DO UPDATE SET comprado=1
        ''', (email, s['id']))
    
    conn.commit()
    conn.close()
    
    logger.info(f"🎉 Stickers liberados para {email} (pagamento {pagamento_id})")
    return jsonify({'ok': True, 'email': email, 'stickers': len(STICKERS)})

@app.route('/api/liberar_manual', methods=['POST'])
def api_liberar_manual():
    """Liberação manual com código de segurança"""
    if 'email' not in session:
        return jsonify({'error': 'Não logado'}), 401
    
    data = request.get_json() or {}
    if data.get('codigo') != CODIGO_SEGURANCA:
        return jsonify({'error': 'Código inválido'}), 403
    
    email = session['email']
    conn = get_db()
    for s in STICKERS:
        conn.execute('''
            INSERT INTO sticker_usage (email, sticker_id, usos_restantes, comprado)
            VALUES (?, ?, 0, 1)
            ON CONFLICT(email, sticker_id) DO UPDATE SET comprado=1
        ''', (email, s['id']))
    conn.commit()
    conn.close()
    
    return jsonify({'ok': True, 'email': email, 'stickers': len(STICKERS)})

# ─── ARQUIVOS ESTÁTICOS ──────────────────────────────────────

@app.route('/static/stickers/<path:nome>')
def sticker_file(nome):
    return send_from_directory('static/stickers', nome)

# ─── PORTA ────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)