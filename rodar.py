"""Roda o Equilibra no seu computador. Uso: dois cliques neste arquivo, ou  python rodar.py"""
import os, subprocess, sys, threading, time, venv, webbrowser

PASTA = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(PASTA, ".venv")
PY = os.path.join(VENV, "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")

if not os.path.exists(PY):
    print("Preparando o Equilibra pela primeira vez (uns 2 minutos)...")
    venv.create(VENV, with_pip=True)
    subprocess.check_call([PY, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", os.path.join(PASTA, "requirements.txt")])

os.environ.update(FLASK_ENV="development", MODO_AVALIACAO="1", ACESSO_SEM_SENHA="1", ADMIN_EMAILS="local@equilibra.local")
threading.Thread(target=lambda: (time.sleep(4), webbrowser.open("http://localhost:5000")), daemon=True).start()
print("\nEquilibra rodando em http://localhost:5000  ·  para desligar, feche esta janela ou aperte Ctrl+C\n")
try:
    subprocess.call([PY, os.path.join(PASTA, "app.py")], cwd=PASTA)
except KeyboardInterrupt:
    pass
