import os

# Suprime avisos do Qt/Wayland no Linux Fedora
os.environ["QT_QPA_PLATFORM"] = "xcb"

import cv2
import cv2.aruco as aruco
from banco_dados import obter_informacoes_local


def processar_frame_aruco(frame, detector_6x6, detector_4x4):
    """
    Processa um único frame (útil para integração com o Flask/WebRTC)
    buscando tags tanto no dicionário 6x6 quanto no 4x4.
    """
    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Tenta detectar no padrão 6x6 primeiro
    cantos, ids, _ = detector_6x6.detectMarkers(cinza)

    # Se não encontrar, tenta no padrão 4x4
    if ids is None:
        cantos, ids, _ = detector_4x4.detectMarkers(cinza)

    if ids is None:
        cv2.putText(
            frame,
            "Leitor ArUco ativo - nenhuma tag detectada",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    cv2.aruco.drawDetectedMarkers(frame, cantos, ids)
    for indice, id_array in enumerate(ids):
        id_detectado = int(id_array.item())
        informacao = obter_informacoes_local(id_detectado)
        nome = informacao["nome"].title() if informacao else f"ID {id_detectado}"
        ponto = tuple(cantos[indice][0][0].astype(int))
        cv2.putText(
            frame,
            nome,
            (ponto[0], max(24, ponto[1] - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
    return frame


def iniciar_detector(fonte_video=0):
    """
    Loop principal de visão computacional em tempo real via Webcam.
    """
    # Dicionários suportados (Biblioteca usa 4x4, Laboratório usa 6x6)
    dict_6x6 = aruco.getPredefinedDictionary(aruco.DICT_6X6_250)
    dict_4x4 = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)

    parametros = aruco.DetectorParameters()
    detector_6x6 = aruco.ArucoDetector(dict_6x6, parametros)
    detector_4x4 = aruco.ArucoDetector(dict_4x4, parametros)

    cap = cv2.VideoCapture(fonte_video)

    if not cap.isOpened():
        print(f"Erro ao abrir a fonte de vídeo: {fonte_video}")
        return

    id_ultimo_detectado = None
    print("Iniciando leitor ArUco multi-dicionário (4x4 e 6x6). Pressione 'q' para sair.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Falha ao capturar o frame da câmera.")
            break

        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1º Teste: Tenta detectar marcadores 6x6 (Laboratório ID 10)
        cantos, ids, _ = detector_6x6.detectMarkers(cinza)

        # 2º Teste: Se não achar, tenta marcadores 4x4 (Biblioteca ID 1)
        if ids is None:
            cantos, ids, _ = detector_4x4.detectMarkers(cinza)

        if ids is not None:
            aruco.drawDetectedMarkers(frame, cantos, ids)

            for i in range(len(ids)):
                id_detectado = int(ids[i].item())

                # Consulta dados no SQLite (passos_contados.db)
                info_local = obter_informacoes_local(id_detectado)

                if info_local:
                    nome_exibicao = info_local["nome"].title()

                    # Exibe no terminal apenas quando mudar de tag
                    if id_detectado != id_ultimo_detectado:
                        id_ultimo_detectado = id_detectado
                        print(f"\n========================================")
                        print(
                            f"LOCAL DETECTADO: {nome_exibicao} (ID: {id_detectado})"
                        )
                        print(f"Descrição: {info_local['descricao']}")
                        print("Saídas/Corredores Conectados:")
                        for sa in info_local["saidas"]:
                            print(
                                f"  -> Para '{sa['destino'].title()}': {sa['distancia_passos']} passos ({sa['instrucao']})"
                            )
                        print(f"========================================")
                else:
                    nome_exibicao = f"ID {id_detectado} (Não cadastrado)"
                    if id_detectado != id_ultimo_detectado:
                        id_ultimo_detectado = id_detectado
                        print(
                            f"\n[AVISO] ArUco ID {id_detectado} detectado, mas sem cadastro no banco!"
                        )

                # Desenha o nome do local acima da tag na imagem
                canto_superior = tuple(cantos[i][0][0].astype(int))
                cv2.putText(
                    frame,
                    nome_exibicao,
                    (canto_superior[0], max(24, canto_superior[1] - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

        cv2.imshow("Passos Contados - Integrado com SQLite", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    iniciar_detector(0)