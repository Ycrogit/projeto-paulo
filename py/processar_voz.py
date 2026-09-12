import os
import re
import whisper
import speech_recognition as sr

modelo_whisper = whisper.load_model("base")

def processar_comando_navegacao(texto):
    texto = texto.lower().strip()
    
    if re.search(r"\b(onde|qual local|qual sala|onde e|onde fico)\b.*(estou|to|me encontro)", texto):
        return {"acao": "OBTER_LOCALIZACAO"}

    padrao_rota = r"(?:como (?:ir|chegar)|me (?:leve|guie)|rota|caminho)\s+(?:para|ate|a|na|no)?\s+(.+)"
    match_rota = re.search(padrao_rota, texto)
    
    if match_rota:
        destino = match_rota.group(1).strip()
        return {"acao": "CALCULAR_ROTA", "destino": destino}

    return {"acao": "DESCONHECIDO", "texto_original": texto}

def capturar_e_transcrever_microfone():
    reconhecedor = sr.Recognizer()
    with sr.Microphone() as mic:
        reconhecedor.adjust_for_ambient_noise(mic, duration=1)
        audio = reconhecedor.listen(mic)
        
    caminho_temp = "temp_audio.wav"
    with open(caminho_temp, "wb") as f:
        f.write(audio.get_wav_data())
        
    resultado = modelo_whisper.transcribe(caminho_temp, language="pt")
    
    if os.path.exists(caminho_temp):
        os.remove(caminho_temp)
        
    return resultado["text"]

if __name__ == "__main__":
    try:
        texto_transcrito = capturar_e_transcrever_microfone()
        comando = processar_comando_navegacao(texto_transcrito)
        print(f"Texto: '{texto_transcrito}'")
        print(f"Comando: {comando}")
    except Exception as e:
        print(f"Erro: {e}")