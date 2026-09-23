import json
import os
import socket
import threading
import time


PORTA_DESCOBERTA = int(os.getenv("CARRINHO_DISCOVERY_PORT", "4210"))
INTERVALO_DESCOBERTA = float(os.getenv("CARRINHO_DISCOVERY_INTERVAL", "10"))
MENSAGEM_DESCOBERTA = b"PASSOS_CONTADOS_DISCOVER\n"

_lock = threading.Lock()
_carrinhos = {}


def _normalizar_resposta(dados, endereco):
    if not isinstance(dados, dict):
        return None
    tipo = str(dados.get("tipo", "")).lower()
    if tipo and tipo not in {"esp32-carrinho", "carrinho-esp32"}:
        return None
    ip = dados.get("ip") or endereco[0]
    porta = int(dados.get("porta", 80))
    return {
        "id": str(dados.get("id") or dados.get("nome") or ip),
        "nome": str(dados.get("nome", "Carrinho ESP32")),
        "ip": ip,
        "porta": porta,
        "tipo": "esp32-carrinho",
        "ultimo_contato": time.time(),
    }


def descobrir_carrinhos(timeout=1.0):
    encontrados = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        sock.sendto(MENSAGEM_DESCOBERTA, ("255.255.255.255", PORTA_DESCOBERTA))
        while True:
            try:
                resposta, endereco = sock.recvfrom(2048)
            except socket.timeout:
                break
            try:
                dados = json.loads(resposta.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            carrinho = _normalizar_resposta(dados, endereco)
            if carrinho:
                encontrados[carrinho["id"]] = carrinho

    with _lock:
        _carrinhos.clear()
        _carrinhos.update(encontrados)
        return list(_carrinhos.values())


def obter_status_carrinhos():
    with _lock:
        carrinhos = list(_carrinhos.values())
    return {"conectado": bool(carrinhos), "carrinhos": carrinhos}


def iniciar_descoberta_em_background():
    def loop():
        while True:
            try:
                descobrir_carrinhos()
            except OSError as erro:
                print(f"[CARRINHO] Falha na descoberta: {erro}")
            time.sleep(INTERVALO_DESCOBERTA)

    threading.Thread(target=loop, name="descoberta-carrinho", daemon=True).start()