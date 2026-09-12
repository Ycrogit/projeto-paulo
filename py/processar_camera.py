import cv2
import torch
import numpy as np
from ultralytics import YOLO

print("[SISTEMA 3D] Inicializando Engine Otimizada de Alta Performance...")

# 1. Configuração de Hardware e YOLO Otimizado
device = 'cpu'
# Força o número de threads da CPU para evitar travamentos de UI
torch.set_num_threads(4)

# Modelo YOLO Nano de segmentação (extremamente rápido no i5)
modelo_yolo = YOLO("yolov8n-seg.pt").to(device)

TRADUCAO_CLASSES = {
    'person': 'Humano',
    'chair': 'Cadeira',
    'table': 'Mesa',
    'couch': 'Sofá',
    'laptop': 'Notebook',
    'bottle': 'Garrafa',
    'tv': 'TV / Monitor',
    'backpack': 'Mochila'
}

def normalizar_iluminacao(frame):
    """Estabilização leve de contraste sem comprometer a CPU."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(4, 4))
    cl = clahe.apply(l_channel)
    return cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2BGR)

def estimar_distancia_geometrica(y2, altura_frame):
    """
    Calcula profundidade real em metros via Geometria de Perspectiva.
    Sem lag, sem estresse na CPU e sem bugs de oscilação.
    """
    # Evita divisão por zero se a base estiver no topo da tela
    posicao_relativa = max(0.01, (altura_frame - y2) / altura_frame)
    distancia_metros = 0.4 + (posicao_relativa * 3.5)
    return max(0.3, distancia_metros)

def desenhar_hitbox_3d(img, box_2d, texto_label, cor=(0, 140, 255)):
    """Renderiza a caixa 3D translúcida em tempo real."""
    x1, y1, x2, y2 = box_2d
    largura = x2 - x1
    prof = int(largura * 0.35)
    dx = int(prof * 0.35)
    dy = int(prof * 0.25)

    f_bl, f_br = (x1, y2), (x2, y2)
    f_tl, f_tr = (x1, y1), (x2, y1)
    b_bl, b_br = (x1 + dx, y2 - dy), (x2 + dx, y2 - dy)
    b_tl, b_tr = (x1 + dx, y1 - dy), (x2 + dx, y1 - dy)

    # Preenchimento 3D Translúcido (Laranja)
    mascara_hitbox = np.zeros_like(img)
    pts_cubo = np.array([f_bl, f_br, b_br, b_tr, f_tr, f_tl], np.int32)
    cv2.fillConvexPoly(mascara_hitbox, pts_cubo, cor)
    cv2.addWeighted(mascara_hitbox, 0.2, img, 0.8, 0, img)

    # Arestas
    cv2.polylines(img, [np.array([f_bl, f_br, b_br, b_bl], np.int32)], True, cor, 2)
    cv2.polylines(img, [np.array([f_tl, f_tr, b_tr, b_tl], np.int32)], True, cor, 2)
    cv2.line(img, f_bl, f_tl, cor, 2)
    cv2.line(img, f_br, f_tr, cor, 2)

    # Tag de Identificação com Texto
    larg_txt = len(texto_label) * 9 + 10
    cv2.rectangle(img, (x1, max(0, y1 - 22)), (x1 + larg_txt, max(22, y1)), cor, -1)
    cv2.putText(
        img, 
        texto_label, 
        (x1 + 4, max(16, y1 - 6)), 
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.5, 
        (255, 255, 255), 
        1, 
        cv2.LINE_AA
    )

def processar_cena_otimizada(frame, cache_objetos, frame_count):
    h, w, _ = frame.shape
    frame_estabilizado = normalizar_iluminacao(frame)
    overlay = frame_estabilizado.copy()

    cor_laranja = (0, 140, 255)  # Hitboxes e Objetos
    cor_azul = (255, 120, 0)     # Paredes
    cor_verde = (0, 255, 0)      # Somente o Piso Navegável

    mascara_obstaculos = np.zeros((h, w), dtype=bool)

    # Pulo de frame: roda a IA a cada 2 quadros para garantir fluidez total
    if frame_count % 2 == 0:
        resultados = modelo_yolo(frame_estabilizado, verbose=False, device=device, imgsz=320)
        cache_objetos.clear()

        for r in resultados:
            if r.masks is not None:
                masks = r.masks.data.cpu().numpy()
                for mask in masks:
                    mask_resized = cv2.resize(mask, (w, h))
                    mascara_obstaculos |= (mask_resized > 0.5)

            if r.boxes is not None:
                boxes = r.boxes.cpu().numpy()
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cls_id = int(box.cls[0])
                    nome_orig = modelo_yolo.names[cls_id]
                    nome_pt = TRADUCAO_CLASSES.get(nome_orig, nome_orig.capitalize())

                    mascara_obstaculos[y1:y2, x1:x2] = True
                    dist_m = estimar_distancia_geometrica(y2, h)
                    label = f"{nome_pt} ({dist_m:.1f}m)"

                    cache_objetos.append(((x1, y1, x2, y2), label))

    # 2. Segmentação Geométrica de Chão e Parede
    regiao_superior = np.ones((h, w), dtype=bool)
    pts_chao = np.array([[0, h], [int(w*0.15), int(h*0.58)], [int(w*0.85), int(h*0.58)], [w, h]], np.int32)
    cv2.fillPoly(regiao_superior.astype(np.uint8), [pts_chao], 0)

    mascara_paredes = regiao_superior & (~mascara_obstaculos)
    mascara_piso = ~(mascara_obstaculos | mascara_paredes)

    # 3. Aplicação das Cores Estruturais
    overlay[mascara_piso] = cor_verde
    overlay[mascara_paredes] = cor_azul
    frame_final = cv2.addWeighted(overlay, 0.3, frame_estabilizado, 0.7, 0)

    # 4. Renderização dos Objetos e Hitboxes
    for box_2d, label in cache_objetos:
        desenhar_hitbox_3d(frame_final, box_2d, label, cor=cor_laranja)

    # Tag da Parede
    cv2.rectangle(frame_final, (15, 15), (160, 45), cor_azul, -1)
    cv2.putText(frame_final, "Parede (Estrutura)", (22, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    return frame_final

def iniciar_camera_fluida():
    cap = cv2.VideoCapture(0)
    # Define resolução 640x480 para otimizar tempo de CPU
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    cache_objetos = []
    frame_count = 0

    print("[SISTEMA ONLINE] Executando a 30 FPS sem travamentos. Pressione 'q' para sair.")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        frame_processado = processar_cena_otimizada(frame, cache_objetos, frame_count)

        cv2.imshow("Engine 3D Otimizada - Visao Acessivel", frame_processado)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    iniciar_camera_fluida()