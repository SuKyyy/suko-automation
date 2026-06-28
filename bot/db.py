import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    """Cria as tabelas se não existirem."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pool (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    senha TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    criado_em TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'waiting',
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
                    email TEXT NOT NULL,
                    status TEXT NOT NULL,
                    criado_em TIMESTAMP DEFAULT NOW()
                );
            """)
        conn.commit()

# ==================== POOL ====================
def add_to_pool(email, senha):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pool (email, senha) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING",
                (email, senha)
            )
        conn.commit()

def get_pool():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pool WHERE status = 'pending' ORDER BY criado_em")
            return cur.fetchall()

def update_pool_status(email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE pool SET status = %s WHERE email = %s", (status, email))
        conn.commit()

def clear_pool():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM pool")
        conn.commit()

# ==================== JOBS ====================
def create_job(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO jobs (chat_id, status) VALUES (%s, 'running') RETURNING id",
                (chat_id,)
            )
            job_id = cur.fetchone()["id"]
        conn.commit()
    return job_id

def get_active_job():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE status = 'running' ORDER BY criado_em DESC LIMIT 1")
            return cur.fetchone()

def finish_job(job_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE jobs SET status = 'done' WHERE id = %s", (job_id,))
        conn.commit()

# ==================== CODIGOS ====================
def save_codigo(chat_id, codigo):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO codigos (chat_id, codigo) VALUES (%s, %s)",
                (chat_id, codigo)
            )
        conn.commit()

def get_codigo(chat_id):
    """Pega o código mais recente não usado."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM codigos WHERE chat_id = %s AND usado = FALSE ORDER BY criado_em DESC LIMIT 1",
                (chat_id,)
            )
            return cur.fetchone()

def mark_codigo_usado(codigo_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE codigos SET usado = TRUE WHERE id = %s", (codigo_id,))
        conn.commit()

# ==================== RESULTADOS ====================
def log_resultado(email, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO resultados (email, status) VALUES (%s, %s)",
                (email, status)
            )
        conn.commit()

def get_resultados():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM resultados ORDER BY criado_em DESC LIMIT 20")
            return cur.fetchall()

# ==================== ESTADO WORKER ====================
def set_worker_state(chat_id, waiting_code: bool):
    """Salva estado do worker no DB (esperando código ou não)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (chat_id, status) VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (chat_id, 'waiting_code' if waiting_code else 'running'))
            cur.execute(
                "UPDATE jobs SET status = %s WHERE chat_id = %s AND status IN ('running', 'waiting_code')",
                ('waiting_code' if waiting_code else 'running', chat_id)
            )
        conn.commit()

def is_waiting_code(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM jobs WHERE chat_id = %s ORDER BY criado_em DESC LIMIT 1",
                (chat_id,)
            )
            row = cur.fetchone()
            return row and row["status"] == "waiting_code"
