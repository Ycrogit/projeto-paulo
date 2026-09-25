import os
import sys
import urllib.request
import cv2
import numpy as np
from ultralytics import YOLO

from detectar_aruco import processar_frame_aruco

os.environ["QT_QPA_PLATFORM"] = "xcb"

# IP Base do ESP32-CAM na rede local
ESP32_IP = "10.139.102.118"

# Lista de rotas padrão para captura de imagens
ENDPOINTS_TESTE = [
    f"http://{ESP32_IP}/jpg",
    f"http://{ESP32_IP}/capture",
    f"http://{ESP32_IP}:81/stream",
    f"http://{ESP32_IP}/stream",
    f"http://{ESP32_IP}/"
]


def carregar_modelo_yolo():
    """Carrega o modelo YOLO v8 otimizado para detecção."""
    print("[YOLO] Carregando modelo de detecção de objetos...")
    try:
        # 'yolov8s.pt' (Small) oferece maior precisão/reconhecimento que o Nano sem perder velocidade no CPU
        modelo = YOLO("yolov8s.pt")
        print("[YOLO] Modelo aprimorado carregado com sucesso!")
        return modelo
    except Exception as e:
        print(f"[ERRO YOLO] Falha ao carregar o modelo: {e}")
        return None


def desenhar_caixa_3d(img, pt1, pt2, cor=(0, 255, 0), espessura=2, profundidade_fator=0.3):
    """
    Desenha um cuboide/caixa 3D projetada sobre um objeto detectado.
    Calcula a perspectiva frontal e traseira criando o efeito de profundidade 3D.
    """
    x1, y1 = pt1
    x2, y2 = pt2
    largura = x2 - x1
    altura = y2 - y1

    # Deslocamento em pixels para projetar a profundidade no espaço 3D (para cima e para a direita)
    dx = int(largura * profundidade_fator)
    dy = int(altura * profundidade_fator)

    # Face Frontal (Caixa 2D padrão)
    p1 = (x1, y1)
    p2 = (x2, y1)
    p3 = (x2, y2)
    p4 = (x1, y2)

    # Face Traseira (Projetada no espaço)
    p1_t = (x1 + dx, y1 - dy)
    p2_t = (x2 + dx, y1 - dy)
    p3_t = (x2 + dx, y2 - dy)
    p4_t = (x1 + dx, y2 - dy)

    # Desenha a face traseira
    cv2.line(img, p1_t, p2_t, cor, 1, cv2.LINE_AA)
    cv2.line(img, p2_t, p3_t, cor, 1, cv2.LINE_AA)
    cv2.line(img, p3_t, p4_t, cor, 1, cv2.LINE_AA)
    cv2.line(img, p4_t, p1_t, cor, 1, cv2.LINE_AA)

    # Desenha as arestas de conexão 3D
    cv2.line(img, p1, p1_t, cor, espessura, cv2.LINE_AA)
    cv2.line(img, p2, p2_t, cor, espessura, cv2.LINE_AA)
    cv2.line(img, p3, p3_t, cor, espessura, cv2.LINE_AA)
    cv2.line(img, p4, p4_t, cor, espessura, cv2.LINE_AA)

    # Desenha a face frontal em destaque
    cv2.rectangle(img, p1, p3, cor, espessura, cv2.LINE_AA)


def testar_e_obter_endpoint_valido(timeout=2):
    """Testa cada rota conhecida do ESP32-CAM até obter uma imagem válida."""
    print(f"[CÂMARA] Procurando resposta do ESP32-CAM no IP {ESP32_IP}...")
    
    for url in ENDPOINTS_TESTE:
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resposta:
                if resposta.status == 200:
                    dados_bytes = resposta.read(100000)
                    img_np = np.frombuffer(dados_bytes, dtype=np.uint8)
                    frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
                    
                    if frame is not None and frame.size > 0:
                        print(f"[CÂMARA] SUCESSO: ESP32-CAM respondendo na rota: {url}")
                        return url
        except Exception:
            continue
            
    return None


def capturar_frame_http(url, timeout=2):
    """Realiza a requisição direta de imagem do ESP32-CAM."""
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resposta:
            if resposta.status == 200:
                img_np = np.array(bytearray(resposta.read()), dtype=np.uint8)
                frame = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
                if frame is not None and frame.size > 0:
                    return True, frame
    except Exception:
        pass
    return False, None


def inicializar_detectores_aruco():
    dict_6x6 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    dict_4x4 = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    parametros = cv2.aruco.DetectorParameters()
    detector_6x6 = cv2.aruco.ArucoDetector(dict_6x6, parametros)
    detector_4x4 = cv2.aruco.ArucoDetector(dict_4x4, parametros)

    return detector_6x6, detector_4x4


def iniciar_captura_processada():
    url_ativa = testar_e_obter_endpoint_valido()

    if not url_ativa:
        print(f"[ERRO CRÍTICO] O ESP32-CAM ({ESP32_IP}) não foi localizado. Execução encerrada.")
        sys.exit(0)

    modelo_yolo = carregar_modelo_yolo()
    detector_6x6, detector_4x4 = inicializar_detectores_aruco()

    print("\n[SISTEMA ATIVO] Visão 3D + YOLO Aprimorado + ArUco no ESP32-CAM.")
    print("Pressione 'q' na janela para encerrar.\n")

    id_ultimo_ref = [None]

    while True:
        ret, frame = capturar_frame_http(url_ativa)

        if not ret or frame is None:
            print("[AVISO] Sinal perdido com o ESP32-CAM. Re-testando conexão...")
            url_ativa = testar_e_obter_endpoint_valido()
            if not url_ativa:
                print("[ERRO] Conexão com ESP32-CAM encerrada.")
                break
            continue

        # --- APRIMORAMENTO DE IMAGEM ---
        # Filtro Bilateral para reduzir ruído de transmissão sem borrar as bordas dos objetos/tags
        frame_otimizado = cv2.bilateralFilter(frame, d=5, sigmaColor=50, sigmaSpace=50)

        # --- 1º PASSO: Detecção ArUco ---
        frame_processado = processar_frame_aruco(
            frame_otimizado, detector_6x6, detector_4x4, id_ultimo_ref
        )

        # --- 2º PASSO: Detecção 3D YOLO Aprimorada ---
        if modelo_yolo is not None:
            # Roda inferência com limiar de confiança otimizado (45%) e resolução aumentada (imgsz=640)
            resultados = modelo_yolo(frame_processado, conf=0.45, imgsz=640, verbose=False)
            
            for resultado in resultados:
                boxes = resultado.boxes
                for box in boxes:
                    # Coordenadas do objeto
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    confianca = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    nome_classe = modelo_yolo.names[cls_id]

                    # Projetar elemento em 3D
                    desenhar_caixa_3d(
                        frame_processado, 
                        (x1, y1), 
                        (x2, y2), 
                        cor=(0, 255, 127), 
                        espessura=2, 
                        profundidade_fator=0.25
                    )

                    # Rótulo estilizado
                    texto_rotulo = f"{nome_classe.upper()} {int(confianca * 100)}%"
                    (tx_largura, tx_altura), _ = cv2.getTextSize(
                        texto_rotulo, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
                    )
                    
                    # Fundo escuro para destacar o texto da detecção
                    cv2.rectangle(
                        frame_processado, 
                        (x1, y1 - tx_altura - 8), 
                        (x1 + tx_largura + 6, y1), 
                        (0, 0, 0), 
                        -1
                    )
                    
                    cv2.putText(
                        frame_processado, 
                        texto_rotulo, 
                        (x1 + 3, y1 - 4), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, 
                        (0, 255, 255), 
                        1, 
                        cv2.LINE_AA
                    )

        # Exibição do feed 3D final
        cv2.imshow("Passos Contados - ESP32-CAM (Visão 3D + ArUco)", frame_processado)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    iniciar_captura_processada()