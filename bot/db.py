import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_IDS = [7658392821, 8719531651]

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT UNIQUE NOT NULL,
                    nome TEXT DEFAULT '',
                    saldo NUMERIC(10,2) DEFAULT 0,
                    is_admin BOOLEAN DEFAULT FALSE,
                    ativo BOOLEAN DEFAULT TRUE,
                    criado_em TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS configuracoes (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pool (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    email TEXT NOT NULL,
                    senha TEXT NOT NULL,
                    nome TEXT DEFAULT '',
                    nascimento TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    criado_em TIMESTAMP DEFAULT NOW(),
                    UNIQUE(user_id, email)
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'running',
                    criado_em TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS codigos (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    codigo TEXT NOT NULL,
                    usado BOOLEAN DEFAULT FALSE,
                    criado_em TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS resultados (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    criado_em TIMESTAMP DEFAULT NOW()
                );
            """)
            # Insere preco padrao se nao existir
            cur.execute("""
                INSERT INTO configuracoes (chave, valor)
                VALUES ('preco_por_conta', '1.00')
                ON CONFLICT (chave) DO NOTHING
            """)
            # Garante que admins existem
            for admin_id in ADMIN_IDS:
                cur.execute("""
                    INSERT INTO usuarios (chat_id, nome, is_admin)
                    VALUES (%s, 'Admin', TRUE)
                    ON CONFLICT (chat_id) DO UPDATE SET is_admin = TRUE
                """, (admin_id,))
        conn.commit()

# ==================== USUARIOS ====================
def get_or_create_user(chat_id, nome=''):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE chat_id = %s", (chat_id,))
            user = cur.fetchone()
            if not user:
                cur.execute(
                    "INSERT INTO usuarios (chat_id, nome, is_admin) VALUES (%s, %s, %s) RETURNING *",
                    (chat_id, nome, chat_id in ADMIN_IDS)
                )
                user = cur.fetchone()
            conn.commit()
            return user

def get_user(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios WHERE chat_id = %s", (chat_id,))
            return cur.fetchone()

def is_admin(chat_id):
    return chat_id in ADMIN_IDS

def get_all_users():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM usuarios ORDER BY criado_em DESC")
            return cur.fetchall()

def ajustar_saldo(chat_id, valor):
    """Soma valor ao saldo (pode ser negativo para subtrair)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE usuarios SET saldo = saldo + %s WHERE chat_id = %s RETURNING saldo",
                (valor, chat_id)
            )
            row = cur.fetchone()
        conn.commit()
    return row['saldo'] if row else None

def get_preco():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT valor FROM configuracoes WHERE chave = 'preco_por_conta'")
            row = cur.fetchone()
            return float(row['valor']) if row else 1.0

def set_preco(preco):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE configuracoes SET valor = %s WHERE chave = 'preco_por_conta'",
                (str(preco),)
            )
        conn.commit()

# ==================== POOL ====================
def add_to_pool(user_id, email, senha, nome='', nascimento=''):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO pool (user_id, email, senha, nome, nascimento, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                ON CONFLICT (user_id, email) DO UPDATE
                SET senha=%s, nome=%s, nascimento=%s, status='pending'
            """, (user_id, email, senha, nome, nascimento, senha, nome, nascimento))
        conn.commit()

def get_pool(user_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("SELECT * FROM pool WHERE user_id=%s AND status='pending' ORDER BY criado_em", (user_id,))
            else:
                cur.execute("SELECT * FROM pool WHERE status='pending' ORDER BY user_id, criado_em")
            return cur.fetchall()

def get_pool_all_status(user_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("SELECT * FROM pool WHERE user_id=%s ORDER BY criado_em DESC LIMIT 30", (user_id,))
            else:
                cur.execute("SELECT * FROM pool ORDER BY criado_em DESC LIMIT 50")
            return cur.fetchall()

def update_pool_status(user_id, email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE pool SET status=%s WHERE user_id=%s AND email=%s", (status, user_id, email))
        conn.commit()

def clear_pool(user_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("DELETE FROM pool WHERE user_id=%s", (user_id,))
            else:
                cur.execute("DELETE FROM pool")
        conn.commit()

# ==================== JOBS ====================
def create_job(user_id, chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO jobs (user_id, chat_id, status) VALUES (%s, %s, 'running') RETURNING id",
                (user_id, chat_id)
            )
            job_id = cur.fetchone()['id']
        conn.commit()
    return job_id

def get_active_job(user_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute(
                    "SELECT * FROM jobs WHERE user_id=%s AND status IN ('running','waiting_code') ORDER BY criado_em DESC LIMIT 1",
                    (user_id,)
                )
            else:
                cur.execute("SELECT * FROM jobs WHERE status IN ('running','waiting_code') ORDER BY criado_em DESC LIMIT 1")
            return cur.fetchone()

def get_all_active_jobs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE status IN ('running','waiting_code') ORDER BY criado_em")
            return cur.fetchall()

def finish_job(job_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jobs SET status='done' WHERE id=%s", (job_id,))
        conn.commit()

def cancel_jobs(user_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("UPDATE jobs SET status='cancelado' WHERE user_id=%s AND status IN ('running','waiting_code')", (user_id,))
            else:
                cur.execute("UPDATE jobs SET status='cancelado' WHERE status IN ('running','waiting_code')")
        conn.commit()

def set_waiting_code(chat_id, waiting):
    with get_conn() as conn:
        with conn.cursor() as cur:
            status = 'waiting_code' if waiting else 'running'
            cur.execute(
                "UPDATE jobs SET status=%s WHERE chat_id=%s AND status IN ('running','waiting_code')",
                (status, chat_id)
            )
        conn.commit()

def is_waiting_code(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM jobs WHERE chat_id=%s ORDER BY criado_em DESC LIMIT 1", (chat_id,))
            row = cur.fetchone()
            return row and row['status'] == 'waiting_code'

# ==================== CODIGOS ====================
def save_codigo(chat_id, codigo):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO codigos (chat_id, codigo) VALUES (%s, %s)", (chat_id, codigo))
        conn.commit()

def get_codigo(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM codigos WHERE chat_id=%s AND usado=FALSE ORDER BY criado_em DESC LIMIT 1",
                (chat_id,)
            )
            return cur.fetchone()

def mark_codigo_usado(codigo_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE codigos SET usado=TRUE WHERE id=%s", (codigo_id,))
        conn.commit()

# ==================== RESULTADOS ====================
def log_resultado(user_id, email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO resultados (user_id, email, status) VALUES (%s, %s, %s)", (user_id, email, status))
        conn.commit()

def get_resultados(user_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("SELECT * FROM resultados WHERE user_id=%s ORDER BY criado_em DESC LIMIT 20", (user_id,))
            else:
                cur.execute("SELECT * FROM resultados ORDER BY criado_em DESC LIMIT 50")
            return cur.fetchall()
