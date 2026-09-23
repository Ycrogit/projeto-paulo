import os
import re
import shlex
import subprocess
import threading
import unicodedata

modelo_whisper = None
modelo_semantico = None
vetores_intencoes = None
processo_fala = None
fala_lock = threading.Lock()

RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELO_PIPER = os.path.join(RAIZ_PROJETO, "modelos_voz", "pt_BR-faber-medium.onnx")
TAXA_AMOSTRAGEM = 16000
TEMPO_ESPERA_JARVIS = 3
TEMPO_COMANDO_ATIVO = 5
MODELO_WHISPER = os.getenv("JARVIS_WHISPER_MODEL", "tiny")
ESCALA_DURACAO_FALA = 1.18

CONTEXTO_NAVEGACAO = (
    "Comandos do assistente Jarvis: bom dia jarvis, abrir leitor aruco, "
    "ativar distancia de objetos, averiguar local, onde estou, parar."
)

MAPA_INTENCOES = {
    "ABRIR_LEITOR_ARUCO": [
        "abrir leitor de codigo aruco", "ler codigo aruco", 
        "iniciar escaneamento visual", "mostrar leitor"
    ],
    "ABRIR_PROCESSAMENTO_LOCAL": [
        "averiguar local", "descrever o ambiente", 
        "analisar o espaco com a camera", "abrir processamento de local"
    ],
    "ATIVAR_DISTANCIA_OBJETOS": [
        "ativar distancia de objetos", "detectar objetos", "medir distancia",
        "ligar distancia dos objetos", "processar distancia"
    ],
    "ATIVAR_LEITOR_COMPLETO": [
        "ler codigo aruco e ativar distancia", "abrir leitor aruco com distancia",
        "ler aruco e detectar objetos"
    ],
    "OBTER_LOCALIZACAO": [
        "onde eu estou", "qual e a minha localizacao", 
        "me diga onde me encontro", "consultar posicao no mapa"
    ]
}

def carregar_modelos_semanticos():
    global modelo_semantico, vetores_intencoes
    if vetores_intencoes is not None:
        return bool(vetores_intencoes)
    try:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(6)
        modelo_semantico = SentenceTransformer(
            "paraphrase-multilingual-MiniLM-L12-v2",
            local_files_only=True,
        )
        vetores_intencoes = {
            acao: modelo_semantico.encode(exemplos, convert_to_tensor=True)
            for acao, exemplos in MAPA_INTENCOES.items()
        }
        return True
    except Exception as erro:
        print(f"[AVISO VOZ] Modelo semantico indisponivel: {erro}")
        vetores_intencoes = {}
        return False

def parar_fala():
    global processo_fala
    with fala_lock:
        processo = processo_fala
        processo_fala = None
    if processo is not None and processo.poll() is None:
        try:
            processo.terminate()
            processo.wait(timeout=0.3)
        except Exception:
            processo.kill()


def falar(texto):
    global processo_fala
    print(f"\n[JARVIS FALA]: \"{texto}\"")
    if not os.path.exists(MODELO_PIPER):
        return
    try:
        parar_fala()
        texto_shell = shlex.quote(texto)
        modelo_shell = shlex.quote(MODELO_PIPER)
        comando = (
            f"printf '%s' {texto_shell} | "
            f"piper --model {modelo_shell} --length_scale {ESCALA_DURACAO_FALA} --output_raw 2>/dev/null | "
            "(pw-cat -p --rate 22050 --format s16 2>/dev/null || "
            "aplay -D default -r 22050 -f S16_LE -t raw -q 2>/dev/null)"
        )
        processo = subprocess.Popen(
            comando,
            shell=True,
            executable="/bin/bash",
            start_new_session=True,
        )
        with fala_lock:
            processo_fala = processo
        processo.wait()
    except Exception as e:
        print(f"[ERRO AUDIO]: {e}")
    finally:
        with fala_lock:
            processo_fala = None

def normalizar_texto(texto):
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto_limpo)
        if unicodedata.category(c) != 'Mn'
    )

def identificar_intencao_semantica(texto_fala):
    if not texto_fala:
        return "DESCONHECIDO"

    if "bom dia" in texto_fala or "senhor stark" in texto_fala:
        return "ATIVAR_JARVIS"

    acao_direta = identificar_intencao_por_palavras(texto_fala)
    if acao_direta != "DESCONHECIDO":
        return acao_direta

    if not carregar_modelos_semanticos():
        return "DESCONHECIDO"

    from sentence_transformers import util
    vetor_fala = modelo_semantico.encode(texto_fala, convert_to_tensor=True)
    melhor_acao = "DESCONHECIDO"
    maior_pontuacao = 0.0

    for acao, vetores in vetores_intencoes.items():
        similaridades = util.cos_sim(vetor_fala, vetores)
        pontuacao = float(similaridades.max())
        if pontuacao > maior_pontuacao:
            maior_pontuacao = pontuacao
            melhor_acao = acao

    return melhor_acao if maior_pontuacao >= 0.55 else "DESCONHECIDO"


def identificar_intencao_por_palavras(texto_fala):
    if "aruco" in texto_fala and "distancia" in texto_fala:
        return "ATIVAR_LEITOR_COMPLETO"
    regras = {
        "PARAR_FALA": ("pare", "parar", "silencio", "cancelar fala"),
        "ABRIR_LEITOR_ARUCO": ("aruco", "codigo", "leitor"),
        "ABRIR_PROCESSAMENTO_LOCAL": ("averiguar", "ambiente", "processamento", "espaco"),
        "ATIVAR_DISTANCIA_OBJETOS": ("distancia", "objetos", "detectar objetos", "medir"),
        "OBTER_LOCALIZACAO": ("onde estou", "localizacao", "localização"),
    }
    for acao, palavras in regras.items():
        if any(palavra in texto_fala for palavra in palavras):
            return acao
    if "jarvis" in texto_fala or "bom dia" in texto_fala:
        return "ATIVAR_JARVIS"
    return "DESCONHECIDO"

def processar_comando_navegacao(texto_usuario):
    """Função invocada pelo endpoint HTTP no app.py"""
    texto_limpo = normalizar_texto(texto_usuario)
    return identificar_intencao_semantica(texto_limpo)

def transcrever_audio(caminho_temp):
    global modelo_whisper
    try:
        import whisper

        if modelo_whisper is None:
            modelo_whisper = whisper.load_model(MODELO_WHISPER)
        resultado = modelo_whisper.transcribe(
            caminho_temp,
            language="pt",
            fp16=False,
            beam_size=1,
            temperature=0,
            initial_prompt=CONTEXTO_NAVEGACAO,
        )
        return resultado.get("text", "").strip()
    except Exception:
        return ""


def capturar_audio_microfone(segundos=4):
    caminho_temp = "temp_audio.wav"
    try:
        import numpy as np
        import scipy.io.wavfile as wav
        import sounddevice as sd

        dados = sd.rec(int(segundos * TAXA_AMOSTRAGEM), samplerate=TAXA_AMOSTRAGEM, channels=1, dtype='int16')
        sd.wait()
        if np.abs(dados).max() < 300:
            return ""
        wav.write(caminho_temp, TAXA_AMOSTRAGEM, dados)
        return transcrever_audio(caminho_temp)
    except Exception:
        return ""
    finally:
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)

def escutar_comando_ativo():
    falar("O que deseja?")
    texto = capturar_audio_microfone(segundos=TEMPO_COMANDO_ATIVO)
    texto_limpo = normalizar_texto(texto)
    
    if not texto_limpo:
        falar("Não ouvi nada.")
        return "DESCONHECIDO"

    acao = identificar_intencao_semantica(texto_limpo)
    if acao == "PARAR_FALA":
        parar_fala()
    elif acao == "ABRIR_LEITOR_ARUCO":
        falar("Abrindo leitor ArUco.")
    elif acao == "ABRIR_PROCESSAMENTO_LOCAL":
        falar("Averiguando o local.")
    elif acao == "ATIVAR_DISTANCIA_OBJETOS":
        falar("Ativando a distância dos objetos.")
    elif acao == "OBTER_LOCALIZACAO":
        falar("Consultando localização.")
    else:
        falar("Comando não reconhecido.")
    return acao

def loop_escuta_passiva_jarvis(callback_comando):
    falar("Jarvis online e de prontidão.")
    while True:
        try:
            texto = capturar_audio_microfone(segundos=TEMPO_ESPERA_JARVIS)
            texto_limpo = normalizar_texto(texto)
            if not texto_limpo or "comandos do assistente" in texto_limpo:
                continue

            if "jarvis" in texto_limpo:
                acao = escutar_comando_ativo()
                callback_comando(acao)
            elif "pare" in texto_limpo or "parar" in texto_limpo:
                parar_fala()
                callback_comando("PARAR_FALA")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERRO VOZ]: {e}")