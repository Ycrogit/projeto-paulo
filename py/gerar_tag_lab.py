import cv2
import numpy as np

# Instancia o dicionário ArUco
dicionario_aruco = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

# Configura o ID 10 para o Laboratório de Informática
ID_LAB_INFORMATICA = 10
TAMANHO_PIXELS = 400

# Gera a imagem diretamente através do método do objeto dicionário
imagem_tag = dicionario_aruco.generateImageMarker(ID_LAB_INFORMATICA, TAMANHO_PIXELS)

# Adiciona uma borda branca (margem de segurança para leitura)
imagem_com_borda = cv2.copyMakeBorder(
    imagem_tag, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=[255, 255, 255]
)

# Salva o arquivo final
caminho_arquivo = "aruco_lab_informatica_id10.png"
cv2.imwrite(caminho_arquivo, imagem_com_borda)

print(f"[SUCESSO] Tag ArUco do Laboratório de Informática (ID {ID_LAB_INFORMATICA}) gerada em: {caminho_arquivo}")
