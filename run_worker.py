import subprocess
import sys

if __name__ == "__main__":
    print("Iniciando SuKo Worker...\n")
    try:
        subprocess.run([sys.executable, "-m", "bot.worker"], check=True)
    except KeyboardInterrupt:
        print("\nWorker finalizado pelo usuário.")
    except Exception as e:
        print(f"Erro ao executar worker: {e}")
        input("Pressione Enter para sair...")