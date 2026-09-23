import subprocess
import sys
import os

# Importa o módulo de voz que está na mesma pasta py/
from processar_voz import loop_escuta_passiva_jarvis, falar

processo_camera_ativo = None

def fechar_camera_anterior():
    """Garante que a câmera seja liberada antes de abrir outro módulo."""
    global processo_camera_ativo
    if processo_camera_ativo is not None:
        print("[SISTEMA] Encerrando visualização de câmera anterior...")
        processo_camera_ativo.terminate()
        processo_camera_ativo.wait()
        processo_camera_ativo = None

def executar_modulo_visao(script_nome, nome_aba):
    """
    Simula a navegação para a aba 'Mapa' e abre a visualização da câmera no visor.
    """
    global processo_camera_ativo
    fechar_camera_anterior()

    # Como o main.py agora está no diretório py/, busca os scripts no mesmo diretório
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_script = os.path.join(diretorio_atual, script_nome)
    
    if not os.path.exists(caminho_script):
        falar(f"Erro: O módulo {script_nome} não foi encontrado no diretório py.")
        print(f"[ERRO] Arquivo não localizado: {caminho_script}")
        return

    print(f"\n[FRONT-END] Redirecionando para a Aba: '{nome_aba}'")
    print(f"[BACK-END] Executando processo da câmera: {caminho_script}")

    # Executa o script em um subprocesso independente sem travar o loop de voz
    processo_camera_ativo = subprocess.Popen([sys.executable, caminho_script])

def gerenciar_comandos(acao):
    """Direciona os comandos reconhecidos por voz para as telas/módulos corretos."""
    if acao == "ABRIR_LEITOR_ARUCO":
        # Vai para a aba Mapa e executa o leitor ArUco
        executar_modulo_visao("detectar_aruco.py", nome_aba="MAPA - Visor ArUco")

    elif acao == "ABRIR_PROCESSAMENTO_LOCAL":
        # Vai para a aba Mapa e executa o processamento 3D/Segmentação
        executar_modulo_visao("processar_camera.py", nome_aba="MAPA - Processamento Local")

    elif acao == "OBTER_LOCALIZACAO":
        print("[SISTEMA] Consultando SQLite...")

if __name__ == "__main__":
    print("==================================================")
    print("   ASSISTENTE VISUAL JARVIS - SISTEMA INTEGRADO   ")
    print("==================================================")
    
    try:
        # Inicia a escuta passiva em primeiro plano
        loop_escuta_passiva_jarvis(gerenciar_comandos)
    except KeyboardInterrupt:
        fechar_camera_anterior()
        print("\n[SISTEMA] Encerrando aplicação...")