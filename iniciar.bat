@echo off
cd /d "%~dp0"
title Equilibra
where python >nul 2>nul || (echo Python nao encontrado. Instale o Python 3.12 em python.org e marque "Add python.exe to PATH". & pause & exit /b)
if not exist .venv\Scripts\python.exe (
  echo Preparando o Equilibra pela primeira vez. Isso leva uns 2 minutos...
  python -m venv .venv || (pause & exit /b)
  .venv\Scripts\python -m pip install --disable-pip-version-check -q -r requirements.txt || (echo Falha ao instalar as bibliotecas. & pause & exit /b)
)
set FLASK_ENV=development
set MODO_AVALIACAO=1
set ACESSO_SEM_SENHA=1
set ADMIN_EMAILS=local@equilibra.local
start "" cmd /c "timeout /t 4 >nul & start http://localhost:5000"
echo.
echo Equilibra rodando em http://localhost:5000
echo Para ver o Painel da plataforma, crie a conta com o e-mail admin@equilibra.local
echo Para desligar, feche esta janela.
echo.
.venv\Scripts\python app.py
pause
