import os
import re
import torch
import whisper
import speech_recognition as sr

torch.set_num_threads(6)

modelo_whisper = whisper.load_model("small")

CONTEXTO_NAVEGACAO = (
    "Navegação interna para deficientes visuais. Comandos: onde estou, "
    "como chegar, me leve até a biblioteca, qual sala, banheiro, elevador, bloco A."
)

def processar_comando_navegacao(texto):
    texto = texto.lower().strip()
    texto_limpo = re.sub(r'[^\w\s]', '', texto)

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

    with sr.Microphone() as mic:
        print("\n[VOZ] Calibrando ruído de fundo...")
        reconhecedor.adjust_for_ambient_noise(mic, duration=1.0)
        print("[VOZ] Pode falar o seu comando agora!")
        audio = reconhecedor.listen(mic, timeout=5, phrase_time_limit=7)

    caminho_temp = "temp_audio.wav"
    with open(caminho_temp, "wb") as f:
        f.write(audio.get_wav_data())

    print("[WHISPER] Transcrevendo comando...")
    resultado = modelo_whisper.transcribe(
        caminho_temp,
        language="pt",
        fp16=False,
        initial_prompt=CONTEXTO_NAVEGACAO,
        beam_size=5
    )

    if os.path.exists(caminho_temp):
        os.remove(caminho_temp)

    return resultado["text"].strip()

if __name__ == "__main__":
    try:
        texto = capturar_e_transcrever_microfone()
        comando = processar_comando_navegacao(texto)
        print(f"\n[TEXTO TRANSCRITO]: \"{texto}\"")
        print(f"[COMANDO ESTRUTURADO]: {comando}")
    except Exception as e:
        print(f"\n[ERRO]: {e}")