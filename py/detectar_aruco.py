import cv2
import cv2.aruco as aruco
from banco_dados import obter_informacoes_local


def iniciar_detector(fonte_video=0):
    dicionario = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parametros = aruco.DetectorParameters()
    detector = aruco.ArucoDetector(dicionario, parametros)

    cap = cv2.VideoCapture(fonte_video)

    if not cap.isOpened():
        print(f"Erro ao abrir a fonte de vídeo: {fonte_video}")
        return

    id_ultimo_detectado = None
    print("Iniciando leitor ArUco conectado ao SQLite. Pressione 'q' para sair.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Falha ao capturar o frame da câmera.")
            break

        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cantos, ids, _ = detector.detectMarkers(cinza)

        if ids is not None:
            aruco.drawDetectedMarkers(frame, cantos, ids)

            for i in range(len(ids)):
                id_detectado = int(ids[i].item())

                # Consulta os dados completos diretamente do Banco SQLite
                info_local = obter_informacoes_local(id_detectado)

                if info_local:
                    nome_exibicao = info_local["nome"].title()

                    # Imprime detalhes no terminal apenas quando mudar de tag
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
                        print(f"\n[AVISO] ArUco ID {id_detectado} detectado, mas sem cadastro no banco!")

                # Desenha o nome do local sobre a tag no feed de vídeo
                canto_superior = tuple(cantos[i][0][0].astype(int))
                cv2.putText(
                    frame,
                    nome_exibicao,
                    (canto_superior[0], canto_superior[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )

        cv2.imshow("Passos Contados - Integrado com SQLite", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    iniciar_detector(0)