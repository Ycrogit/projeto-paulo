import os
import cv2
import cv2.aruco as aruco


def criar_marcador_com_rotulo(
    id_marcador, texto_local, nome_arquivo="aruco_biblioteca.png"
):
    dicionario = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    tamanho_aruco = 300

    # 1. Gera o marcador ArUco puro
    imagem_aruco = aruco.generateImageMarker(
        dicionario, id_marcador, tamanho_aruco
    )

    # 2. Adiciona uma borda branca com espaço para texto na parte inferior
    altura_texto = 60
    imagem_com_rotulo = cv2.copyMakeBorder(
        imagem_aruco,
        top=20,
        bottom=altura_texto,
        left=20,
        right=20,
        borderType=cv2.BORDER_CONSTANT,
        value=[255, 255, 255],
    )

    # 3. Desenha o texto do local na parte inferior
    fonte = cv2.FONT_HERSHEY_SIMPLEX
    escala = 0.8
    espessura = 2
    cor = (0, 0, 0)

    tamanho_texto = cv2.getTextSize(texto_local, fonte, escala, espessura)[0]
    pos_x = (imagem_com_rotulo.shape[1] - tamanho_texto[0]) // 2
    pos_y = imagem_com_rotulo.shape[0] - 20

    cv2.putText(
        imagem_com_rotulo,
        texto_local,
        (pos_x, pos_y),
        fonte,
        escala,
        cor,
        espessura,
    )

    # 4. Salva o arquivo na pasta 'marcadores/'
    pasta_saida = "marcadores"
    os.makedirs(pasta_saida, exist_ok=True)
    caminho_final = os.path.join(pasta_saida, nome_arquivo)
    cv2.imwrite(caminho_final, imagem_com_rotulo)

    print(
        f"Marcador para '{texto_local}' (ID {id_marcador}) gerado em: {caminho_final}"
    )


if __name__ == "__main__":
    # Definindo ID 1 para a Biblioteca
    criar_marcador_com_rotulo(
        id_marcador=1,
        texto_local="Biblioteca",
        nome_arquivo="aruco_id1_biblioteca.png",
    )