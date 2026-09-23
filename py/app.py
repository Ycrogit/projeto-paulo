import os
import base64
import threading
import time
import tempfile
from flask import Flask, Response, jsonify, request, send_from_directory

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None
from banco_dados import inicializar_banco, obter_informacoes_local
from processar_voz import (
    capturar_audio_microfone,
    falar,
    loop_escuta_passiva_jarvis,
    parar_fala,
    processar_comando_navegacao,
    transcrever_audio,
)
from carrinho import descobrir_carrinhos, iniciar_descoberta_em_background, obter_status_carrinhos

# Localiza a pasta da interface HTML/JS
PASTA_INTERFACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../passos_contados_interface/www'))

app = Flask(__name__, static_folder=PASTA_INTERFACE, static_url_path='')


@app.after_request
def permitir_requisicoes_do_aplicativo(resposta):
    origem = request.headers.get('Origin', '')
    if origem in {'http://localhost', 'https://localhost', 'capacitor://localhost'}:
        resposta.headers['Access-Control-Allow-Origin'] = origem
        resposta.headers['Vary'] = 'Origin'
        resposta.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        resposta.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return resposta

ultimo_comando_reconhecido = "NENHUM"
estado_lock = threading.Lock()
modo_camera = "aruco"
ultimo_local_detectado = None
inicializar_banco()


def configurar_modo_camera(acao):
    global modo_camera
    if acao == "ABRIR_LEITOR_ARUCO":
        modo_camera = "aruco"
    elif acao in {"ABRIR_PROCESSAMENTO_LOCAL", "ATIVAR_DISTANCIA_OBJETOS"}:
        modo_camera = "objetos"
    elif acao == "ATIVAR_LEITOR_COMPLETO":
        modo_camera = "completo"


def resposta_para_acao(acao):
    return {
        "ATIVAR_JARVIS": "Bom dia, senhor Stark. Jarvis à disposição.",
        "ABRIR_LEITOR_ARUCO": "Abrindo leitor ArUco e leitura do local.",
        "ABRIR_PROCESSAMENTO_LOCAL": "Averiguando o local e a distância dos objetos.",
        "ATIVAR_DISTANCIA_OBJETOS": "Ativando a distância dos objetos.",
        "ATIVAR_LEITOR_COMPLETO": "Lendo o código ArUco e ativando a distância dos objetos.",
        "OBTER_LOCALIZACAO": "Consultando localização.",
        "PARAR_FALA": "Fala interrompida.",
    }.get(acao, "Comando não reconhecido.")

def callback_voz_recebida(acao):
    global ultimo_comando_reconhecido
    configurar_modo_camera(acao)
    if acao == "PARAR_FALA":
        parar_fala()
    with estado_lock:
        ultimo_comando_reconhecido = acao
    print(f"\n[SISTEMA]: Ação acionada via voz -> {acao}")

@app.route('/')
def servir_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def servir_estaticos(path):
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/comando', methods=['POST'])
def receber_comando_texto():
    dados = request.get_json() or {}
    texto = dados.get('comando') or dados.get('texto', '')
    acao = processar_comando_navegacao(texto)
    configurar_modo_camera(acao)
    if acao == "PARAR_FALA":
        parar_fala()
    return jsonify({
        'status': 'sucesso',
        'acao': acao,
        'texto': texto,
        'resposta': resposta_para_acao(acao),
    })


@app.route('/api/comando-voz', methods=['POST'])
def receber_comando_voz():
    arquivo_audio = request.files.get('audio')
    if arquivo_audio:
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as arquivo_temp:
            arquivo_audio.save(arquivo_temp.name)
            caminho_audio = arquivo_temp.name
        try:
            texto = transcrever_audio(caminho_audio)
        finally:
            os.remove(caminho_audio)
    else:
        texto = capturar_audio_microfone(segundos=5)
    acao = processar_comando_navegacao(texto)
    configurar_modo_camera(acao)
    if acao == "PARAR_FALA":
        parar_fala()
    return jsonify({
        'status': 'sucesso',
        'acao': acao,
        'texto': texto,
        'resposta': resposta_para_acao(acao),
    })


@app.post('/api/processar-frame')
def processar_frame_celular():
    if cv2 is None:
        return jsonify({'erro': 'OpenCV nao esta instalado.'}), 503
    arquivo = request.files.get('frame')
    if arquivo is None:
        return jsonify({'erro': 'Frame da camera nao enviado.'}), 400
    dados = cv2.imdecode(__import__('numpy').frombuffer(arquivo.read(), dtype=__import__('numpy').uint8), cv2.IMREAD_COLOR)
    if dados is None:
        return jsonify({'erro': 'Frame invalido.'}), 400

    modo = request.form.get('modo', modo_camera)
    locais = []
    if modo in {'aruco', 'completo'}:
        import cv2.aruco as aruco
        cinza = cv2.cvtColor(dados, cv2.COLOR_BGR2GRAY)
        detectores = [
            aruco.ArucoDetector(aruco.getPredefinedDictionary(aruco.DICT_6X6_250), aruco.DetectorParameters()),
            aruco.ArucoDetector(aruco.getPredefinedDictionary(aruco.DICT_4X4_50), aruco.DetectorParameters()),
        ]
        cantos, ids, _ = detectores[0].detectMarkers(cinza)
        if ids is None:
            cantos, ids, _ = detectores[1].detectMarkers(cinza)
        if ids is not None:
            aruco.drawDetectedMarkers(dados, cantos, ids)
            for indice, id_array in enumerate(ids):
                id_detectado = int(id_array.item())
                informacao = obter_informacoes_local(id_detectado)
                nome = informacao['nome'].title() if informacao else f'ID {id_detectado}'
                ponto = tuple(cantos[indice][0][0].astype(int))
                cv2.putText(dados, nome, (ponto[0], max(24, ponto[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2, cv2.LINE_AA)
                if informacao:
                    locais.append({'id': id_detectado, 'fala': formatar_informacoes_local(informacao)})
    if modo in {'objetos', 'completo'}:
        from processar_camera import processar_cena_otimizada
        dados = processar_cena_otimizada(dados, [], 2)

    sucesso, buffer = cv2.imencode('.jpg', dados)
    if not sucesso:
        return jsonify({'erro': 'Nao foi possivel codificar o frame.'}), 500
    imagem = base64.b64encode(buffer.tobytes()).decode('ascii')
    return jsonify({'imagem': f'data:image/jpeg;base64,{imagem}', 'locais': locais})


@app.post('/api/parar-fala')
def interromper_fala():
    parar_fala()
    return jsonify({'status': 'sucesso', 'acao': 'PARAR_FALA', 'resposta': 'Fala interrompida.'})


@app.get('/api/health')
def health_check():
    return jsonify({'status': 'online'})


@app.get('/api/carrinho')
def status_carrinho():
    atualizar = request.args.get('atualizar') == '1'
    if atualizar:
        descobrir_carrinhos()
    return jsonify(obter_status_carrinhos())


@app.get('/api/camera.mjpg')
def camera_mjpeg():
    if cv2 is None:
        return jsonify({'erro': 'OpenCV nao esta instalado.'}), 503

    modo = request.args.get('modo', modo_camera)
    captura = cv2.VideoCapture(0)
    if not captura.isOpened():
        captura.release()
        return jsonify({'erro': 'Camera indisponivel.'}), 503

    def gerar_frames():
        global ultimo_local_detectado
        detector = None
        processar_objetos = None
        cache_objetos = []
        frame_count = 0
        if modo in {"aruco", "completo"}:
            import cv2.aruco as aruco
            dicionario = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
            detector = aruco.ArucoDetector(dicionario, aruco.DetectorParameters())
        try:
            while True:
                sucesso, frame = captura.read()
                if not sucesso:
                    break
                frame_count += 1
                if modo in {"objetos", "completo"}:
                    if processar_objetos is None:
                        from processar_camera import processar_cena_otimizada
                        processar_objetos = processar_cena_otimizada
                    frame = processar_objetos(frame, cache_objetos, frame_count)
                if detector is not None:
                    import cv2.aruco as aruco
                    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    cantos, ids, _ = detector.detectMarkers(cinza)
                    if ids is not None:
                        aruco.drawDetectedMarkers(frame, cantos, ids)
                        for indice, id_array in enumerate(ids):
                            id_detectado = int(id_array.item())
                            informacao = obter_informacoes_local(id_detectado)
                            nome = informacao['nome'].title() if informacao else f'ID {id_detectado}'
                            ponto = tuple(cantos[indice][0][0].astype(int))
                            cv2.putText(frame, nome, (ponto[0], max(24, ponto[1] - 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2, cv2.LINE_AA)
                            if informacao and id_detectado != ultimo_local_detectado:
                                ultimo_local_detectado = id_detectado
                                threading.Thread(
                                    target=falar,
                                    args=(formatar_informacoes_local(informacao),),
                                    daemon=True,
                                ).start()
                sucesso, buffer = cv2.imencode('.jpg', frame)
                if sucesso:
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n'
                        + buffer.tobytes()
                        + b'\r\n'
                    )
                time.sleep(0.03)
        finally:
            captura.release()

    return Response(
        gerar_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-cache'},
    )


def formatar_informacoes_local(informacao):
    partes = [f"Você está em {informacao['nome']}. {informacao['descricao'] or ''}".strip()]
    for saida in informacao['saidas']:
        partes.append(
            f"Para {saida['destino']}, são {saida['distancia_passos']} passos. {saida['instrucao'] or ''}".strip()
        )
    return " ".join(partes)

@app.route('/api/status_voz', methods=['GET'])
def obter_status_voz():
    global ultimo_comando_reconhecido
    with estado_lock:
        acao_atual = ultimo_comando_reconhecido
        ultimo_comando_reconhecido = "NENHUM"
    return jsonify({'acao': acao_atual})

if __name__ == '__main__':
    # O APK envia o audio do celular. O microfone do notebook fica opcional.
    if os.getenv("JARVIS_NOTEBOOK_MIC") == "1":
        thread_jarvis = threading.Thread(
            target=loop_escuta_passiva_jarvis,
            args=(callback_voz_recebida,),
            daemon=True,
        )
        thread_jarvis.start()

    print(f"[SERVIDOR] Servindo interface de: {PASTA_INTERFACE}")
    print("[SERVIDOR] Aplicação acessível em: http://localhost:5000")
    iniciar_descoberta_em_background()
    app.run(host='0.0.0.0', port=5000, debug=False)