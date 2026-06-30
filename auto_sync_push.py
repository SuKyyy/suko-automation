import os
import time
import shutil
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==================== CONFIGURAÇÕES (NÃO MEXA) ====================
DRIVE_FOLDER = r"G:\Meu Drive\suko-automation-main"
REPO_FOLDER  = r"C:\Users\Admin\Desktop\Claude ACC SuKo"

IGNORAR = {".git", "__pycache__", ".idea", "node_modules", ".venv", "venv", "auto_sync_push.py", "run_auto_sync.bat"}
EXTENSOES_PERMITIDAS = {".py", ".txt", ".md", ".env", ".bat", ".sh", ".json", ".yaml", ".yml"}

class ChangeHandler(FileSystemEventHandler):
    def __init__(self):
        self.ultima_mudanca = 0
        self.arquivos_pendentes = set()

    def on_modified(self, event):
        if event.is_directory: return
        self.processar(event.src_path)

    def on_created(self, event):
        if event.is_directory: return
        self.processar(event.src_path)

    def processar(self, caminho):
        nome = os.path.basename(caminho)
        if any(ign in caminho for ign in IGNORAR): return
        if not any(nome.endswith(ext) for ext in EXTENSOES_PERMITIDAS): return

        self.arquivos_pendentes.add(caminho)
        self.ultima_mudanca = time.time()

def sincronizar_e_push():
    print("\n[SYNC] Alteração detectada no Drive. Sincronizando...")

    for arquivo in list(handler.arquivos_pendentes):
        try:
            nome = os.path.basename(arquivo)
            destino = os.path.join(REPO_FOLDER, nome)
            shutil.copy2(arquivo, destino)
            print(f"[SYNC] Copiado: {nome}")
        except Exception as e:
            print(f"[ERRO] Falha ao copiar {arquivo}: {e}")

    handler.arquivos_pendentes.clear()

    try:
        os.chdir(REPO_FOLDER)
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            print("[INFO] Nada novo para commitar.")
            return

        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Auto sync from Google Drive"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("[✅] Commit + Push realizado com sucesso!")
    except Exception as e:
        print(f"[ERRO] Falha no git: {e}")

if __name__ == "__main__":
    print("=== Auto Sync + Push iniciado ===")
    print(f"Monitorando: {DRIVE_FOLDER}")
    print(f"Repositório: {REPO_FOLDER}\n")

    global handler
    handler = ChangeHandler()
    observer = Observer()
    observer.schedule(handler, DRIVE_FOLDER, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
            if handler.arquivos_pendentes and (time.time() - handler.ultima_mudanca > 4):
                sincronizar_e_push()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()