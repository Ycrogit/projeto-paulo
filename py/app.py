import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import speech_recognition as sr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detectar_aruco import processar_frame_aruco  # noqa: E402
from processar_voz import processar_comando_navegacao  # noqa: E402

HOST = "0.0.0.0"
PORT = 8000

estado = {
    "modo": "aguardando",
    "status": "Jarvis em prontidao",
    "ultimo_comando": "",
}
estado_lock = threading.Lock()
frame_lock = threading.Lock()
ultimo_jpeg = None


def atualizar_estado(modo, status, comando=""):
    with estado_lock:
        estado["modo"] = modo
        estado["status"] = status
        estado["ultimo_comando"] = comando


def ler_estado():
    with estado_lock:
        return dict(estado)


def gerar_frame_erro(mensagem):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(frame, mensagem, (25, 235), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0, 180, 255), 2, cv2.LINE_AA)
    return frame


def camera_worker():
    global ultimo_jpeg
    captura = cv2.VideoCapture(0)
    captura.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    captura.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cache_objetos = []
    frame_count = 0
    processar_cena_otimizada = None
    dicionario = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    detector = cv2.aruco.ArucoDetector(dicionario, cv2.aruco.DetectorParameters())

    while True:
        sucesso, frame = captura.read()
        if not sucesso:
            processado = gerar_frame_erro("Camera indisponivel")
        else:
            frame_count += 1
            modo = ler_estado()["modo"]
            if modo == "aruco":
                processado = processar_frame_aruco(frame, detector)
            elif modo == "local":
                if processar_cena_otimizada is None:
                    from processar_camera import processar_cena_otimizada

                processado = processar_cena_otimizada(frame, cache_objetos, frame_count)
            else:
                processado = frame

        sucesso, buffer = cv2.imencode(".jpg", processado, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if sucesso:
            with frame_lock:
                ultimo_jpeg = buffer.tobytes()
        time.sleep(0.02)


def resposta_json(handler, status, dados):
    corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(corpo)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(corpo)


class AppHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            resposta_json(self, 200, {"status": "online", **ler_estado()})
            return

        if self.path == "/api/estado":
            resposta_json(self, 200, ler_estado())
            return

        if self.path == "/api/camera.mjpg":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        frame = ultimo_jpeg
                    if frame:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        resposta_json(self, 404, {"erro": "Endpoint nao encontrado."})

    def do_POST(self):
        if self.path == "/api/comando-voz":
            try:
                from processar_voz import capturar_e_transcrever_microfone

                texto = capturar_e_transcrever_microfone()
                comando = processar_comando_navegacao(texto)
                resultado = aplicar_comando(comando)
                resposta_json(self, 200, {"texto": texto, **comando, **resultado})
            except sr.WaitTimeoutError:
                resposta_json(self, 200, {
                    "acao": "SEM_COMANDO",
                    "texto": "",
                    "resposta": "",
                })
            except Exception as erro:
                resposta_json(self, 500, {"erro": f"Falha ao capturar voz: {erro}"})
            return

        if self.path == "/api/comando":
            tamanho = int(self.headers.get("Content-Length", "0"))
            dados = json.loads(self.rfile.read(tamanho) or b"{}")
            comando = processar_comando_navegacao(dados.get("comando", ""))
            resultado = aplicar_comando(comando)
            resposta_json(self, 200, {**comando, **resultado})
            return

        resposta_json(self, 404, {"erro": "Endpoint nao encontrado."})

    def log_message(self, formato, *args):
        print(f"[APP] {self.address_string()} - {formato % args}")


def aplicar_comando(comando):
    acoes = {
        "ABRIR_LEITOR_ARUCO": (
            "aruco", "Leitor ArUco ativo", "Abrindo o leitor ArUco."
        ),
        "ABRIR_PROCESSAMENTO_LOCAL": (
            "local", "Processamento de local ativo", "Averiguando o local."
        ),
    }
    if comando["acao"] == "ATIVAR_JARVIS":
        resposta = "O que deseja?"
        atualizar_estado(ler_estado()["modo"], resposta, comando["texto_original"])
        return {
            "modo": ler_estado()["modo"],
            "status": resposta,
            "resposta": resposta,
            "modulo": "jarvis",
        }

    modo, status, resposta = acoes.get(
        comando["acao"],
        (None, "Comando nao reconhecido", "Nao reconheci esse comando."),
    )
    if modo:
        atualizar_estado(modo, status, comando["texto_original"])
        return {
            "modo": modo,
            "status": status,
            "resposta": resposta,
            "modulo": modo,
        }
    return {
        "modo": ler_estado()["modo"],
        "status": status,
        "resposta": resposta,
        "modulo": "jarvis",
    }


if __name__ == "__main__":
    threading.Thread(target=camera_worker, daemon=True).start()
    servidor = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Passos Contados backend em http://{HOST}:{PORT}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nBackend encerrado.")
    finally:
        servidor.server_close()
