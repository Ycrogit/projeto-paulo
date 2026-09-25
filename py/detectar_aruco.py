import os

# Suprime avisos de interface Qt/Wayland no Linux
os.environ["QT_QPA_PLATFORM"] = "xcb"

import cv2
import cv2.aruco as aruco
from banco_dados import obter_informacoes_local


def processar_frame_aruco(frame, detector_6x6, detector_4x4, id_ultimo_ref=[None]):
    """
    Processa um frame de vídeo, detecta tags ArUco (4x4 e 6x6) e exibe os dados do banco.
    Totalmente independente do módulo de voz.
    """
    cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 1. Busca tags no padrão 6x6
    cantos, ids, _ = detector_6x6.detectMarkers(cinza)

    # 2. Se não encontrar, busca no padrão 4x4
    if ids is None:
        cantos, ids, _ = detector_4x4.detectMarkers(cinza)

    if ids is None:
        cv2.putText(
            frame,
            "Leitor ArUco Ativo - Buscando Marcadores...",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )
        return frame

    aruco.drawDetectedMarkers(frame, cantos, ids)

    for i in range(len(ids)):
        id_detectado = int(ids[i].item())
        info_local = obter_informacoes_local(id_detectado)

        if info_local:
            nome_exibicao = info_local["nome"].title()

            # Exibe log no terminal apenas ao mudar de marcador
            if id_detectado != id_ultimo_ref[0]:
                id_ultimo_ref[0] = id_detectado

                msg_terminal = f"\n========================================\nLOCAL DETECTADO: {nome_exibicao} (ID: {id_detectado})\nDescrição: {info_local['descricao']}\nSaídas:"
                for sa in info_local["saidas"]:
                    msg_terminal += f"\n  -> Para '{sa['destino'].title()}': {sa['distancia_passos']} passos ({sa['instrucao']})"
                msg_terminal += "\n========================================"
                print(msg_terminal)
        else:
            nome_exibicao = f"ID {id_detectado} (Não cadastrado)"
            if id_detectado != id_ultimo_ref[0]:
                id_ultimo_ref[0] = id_detectado
                print(f"\n[AVISO] ArUco ID {id_detectado} detectado, mas sem cadastro no banco!")

        # Desenha o nome do local sobre a tag no vídeo
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

    return frame