import os
import re
import torch
import whisper
import speech_recognition as sr
import unicodedata

# Otimização de processamento para CPU Intel i5
torch.set_num_threads(6)

print("[WHISPER] Carregando modelo Whisper Small...")
modelo_whisper = whisper.load_model("small")

CONTEXTO_NAVEGACAO = (
    "Navegação interna para deficientes visuais. Comandos: onde estou, "
    "como chegar, me leve até a biblioteca, qual sala, banheiro, elevador, bloco A."
)

def processar_comando_navegacao(texto):
    if not texto:
        return {"acao": "SEM_AUDIO", "texto_original": ""}

    texto = texto.lower().strip()
    texto_limpo = re.sub(r'[^\w\s]', '', texto)
    texto_limpo = ''.join(
        caractere
        for caractere in unicodedata.normalize('NFD', texto_limpo)
        if unicodedata.category(caractere) != 'Mn'
    )

    if re.search(r'\bjarvis\b', texto_limpo):
        return {
            "acao": "ATIVAR_JARVIS",
            "resposta": "O que deseja?",
            "texto_original": texto,
        }

    if re.fullmatch(r'abrir leitor aruco', texto_limpo):
        return {
            "acao": "ABRIR_LEITOR_ARUCO",
            "resposta": "Abrindo o leitor ArUco.",
            "texto_original": texto,
        }

    if re.fullmatch(r'averiguar local', texto_limpo):
        return {
            "acao": "ABRIR_PROCESSAMENTO_LOCAL",
            "resposta": "Averiguando o local.",
            "texto_original": texto,
        }

    if re.search(r"\b(onde|qual local|qual sala|onde e|onde fico)\b.*(estou|to|me encontro)", texto_limpo):
        return {"acao": "OBTER_LOCALIZACAO", "texto_original": texto}

    padrao_rota = r"(?:como (?:ir|chegar)|me (?:leve|guie)|rota|caminho)\s+(?:para|ate|a|na|no)?\s+(.+)"
    match_rota = re.search(padrao_rota, texto_limpo)

    if match_rota:
        destino = match_rota.group(1).strip()
        return {"acao": "CALCULAR_ROTA", "destino": destino, "texto_original": texto}

    return {"acao": "DESCONHECIDO", "texto_original": texto}

def capturar_e_transcrever_microfone():
    reconhecedor = sr.Recognizer()
    reconhecedor.dynamic_energy_threshold = True
    reconhecedor.pause_threshold = 0.8
    reconhecedor.energy_threshold = 300  # Evita acionamentos acidentais com silêncio

    caminho_temp = "temp_audio.wav"

    try:
        with sr.Microphone() as mic:
            print("\n[VOZ] Calibrando ruído de fundo...")
            reconhecedor.adjust_for_ambient_noise(mic, duration=0.8)
            print("[VOZ] Pode falar o seu comando agora!")
            
            # Limite de espera para captura de voz
            audio = reconhecedor.listen(mic, timeout=5, phrase_time_limit=7)

        wav_data = audio.get_wav_data()

        # Proteção contra erro de Tensor de 0 elementos no Whisper:
        # Se o buffer gravado for menor que 4KB, descarta pois é apenas silêncio/ruído mínimo
        if len(wav_data) < 4096:
            print("[VOZ] Áudio inaudível ou muito curto capturado. Descartando...")
            return ""

        with open(caminho_temp, "wb") as f:
            f.write(wav_data)

        print("[WHISPER] Transcrevendo comando...")
        resultado = modelo_whisper.transcribe(
            caminho_temp,
            language="pt",
            fp16=False,
            initial_prompt=CONTEXTO_NAVEGACAO,
            beam_size=5
        )

        return resultado.get("text", "").strip()

    except sr.WaitTimeoutError:
        print("[VOZ] Tempo esgotado: Nenhum áudio detectado no microfone.")
        return ""
    except Exception as e:
        print(f"[ERRO WHISPER]: Falha ao processar áudio - {e}")
        return ""
    finally:
        # Garante a remoção do áudio temporário após a transcrição
        if os.path.exists(caminho_temp):
            os.remove(caminho_temp)

if __name__ == "__main__":
    try:
        texto = capturar_e_transcrever_microfone()
        if texto:
            comando = processar_comando_navegacao(texto)
            print(f"\n[TEXTO TRANSCRITO]: \"{texto}\"")
            print(f"[COMANDO ESTRUTURADO]: {comando}")
        else:
            print("\n[SISTEMA]: Nenhum comando de voz foi capturado.")
    except Exception as e:
        print(f"\n[ERRO GERAL]: {e}")