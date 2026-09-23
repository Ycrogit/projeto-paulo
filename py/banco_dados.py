import os
import sqlite3

RAIZ_PROJETO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BANCO_PATH = os.path.join(RAIZ_PROJETO, "passos_contados.db")


def conectar():
    conexao = sqlite3.connect(BANCO_PATH)
    conexao.execute("PRAGMA foreign_keys = ON;")
    return conexao


def inicializar_banco():
    with conectar() as conexao:
        cursor = conexao.cursor()

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS locais (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT
        );
        """
        )

        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS conexoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origem_id INTEGER NOT NULL,
            destino_id INTEGER NOT NULL,
            distancia_passos INTEGER NOT NULL,
            orientacao TEXT,
            FOREIGN KEY (origem_id) REFERENCES locais (id) ON DELETE CASCADE,
            FOREIGN KEY (destino_id) REFERENCES locais (id) ON DELETE CASCADE
        );
        """
        )
    print("Estrutura do banco verificada/inicializada.")


# --- GERENCIAMENTO DE LOCAIS (NÓS / ARUCOS) ---


def adicionar_local(id_aruco, nome, descricao=""):
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute(
            """
            INSERT INTO locais (id, nome, descricao) 
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET nome=excluded.nome, descricao=excluded.descricao;
        """,
            (id_aruco, nome.lower().strip(), descricao),
        )
    print(f"Local '{nome}' (ID {id_aruco}) salvo/atualizado com sucesso.")


def remover_local(id_aruco):
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM locais WHERE id = ?;", (id_aruco,))
    print(f"Local ID {id_aruco} e suas conexões foram removidos.")


def listar_locais():
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute("SELECT id, nome, descricao FROM locais ORDER BY id;")
        return cursor.fetchall()


def buscar_id_por_nome(nome_busca):
    nome_limpo = nome_busca.lower().strip()
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT id FROM locais WHERE nome LIKE ?;", (f"%{nome_limpo}%",)
        )
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None


# --- GERENCIAMENTO DE CONEXÕES (CORREDORES / ARESTAS) ---


def adicionar_conexao(
    origem_id, destino_id, distancia_passos, orientacao="", bidirecional=True
):
    with conectar() as conexao:
        cursor = conexao.cursor()

        cursor.execute(
            """
            INSERT INTO conexoes (origem_id, destino_id, distancia_passos, orientacao)
            VALUES (?, ?, ?, ?);
        """,
            (origem_id, destino_id, distancia_passos, orientacao),
        )

        if bidirecional:
            cursor.execute(
                """
                INSERT INTO conexoes (origem_id, destino_id, distancia_passos, orientacao)
                VALUES (?, ?, ?, ?);
            """,
                (
                    destino_id,
                    origem_id,
                    distancia_passos,
                    f"Retorno: {orientacao}",
                ),
            )
    print(
        f"Conexão criada entre ID {origem_id} e ID {destino_id} ({distancia_passos} passos)."
    )


def remover_conexao(id_conexao):
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM conexoes WHERE id = ?;", (id_conexao,))
    print(f"Conexão ID {id_conexao} removida.")


def listar_conexoes():
    with conectar() as conexao:
        cursor = conexao.cursor()
        query = """
            SELECT c.id, l1.nome, l2.nome, c.distancia_passos, c.orientacao
            FROM conexoes c
            JOIN locais l1 ON c.origem_id = l1.id
            JOIN locais l2 ON c.destino_id = l2.id;
        """
        cursor.execute(query)
        return cursor.fetchall()


# --- MÉTODOS DE SUPORTE PARA VISÃO E DIJKSTRA ---


def carregar_mapa_locais():
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute("SELECT id, nome FROM locais;")
        return {id_local: nome for id_local, nome in cursor.fetchall()}


def carregar_grafo_conexoes():
    with conectar() as conexao:
        cursor = conexao.cursor()
        cursor.execute(
            "SELECT origem_id, destino_id, distancia_passos, orientacao FROM conexoes;"
        )
        linhas = cursor.fetchall()

    grafo = {}
    for origem, destino, peso, instrucao in linhas:
        if origem not in grafo:
            grafo[origem] = []
        grafo[origem].append(
            {"destino": destino, "peso": peso, "instrucao": instrucao}
        )
    return grafo


def obter_informacoes_local(id_aruco):
    with conectar() as conexao:
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT id, nome, descricao FROM locais WHERE id = ?;", (id_aruco,)
        )
        local = cursor.fetchone()

        if not local:
            return None

        query_conexoes = """
            SELECT l.nome, c.distancia_passos, c.orientacao 
            FROM conexoes c
            JOIN locais l ON c.destino_id = l.id
            WHERE c.origem_id = ?;
        """
        cursor.execute(query_conexoes, (id_aruco,))
        conexoes = cursor.fetchall()

        return {
            "id": local[0],
            "nome": local[1],
            "descricao": local[2],
            "saidas": [
                {
                    "destino": c[0],
                    "distancia_passos": c[1],
                    "instrucao": c[2],
                }
                for c in conexoes
            ],
        }


if __name__ == "__main__":
    inicializar_banco()

    # Povoamento dos nós
    adicionar_local(0, "Entrada Principal", "Portão de acesso")
    adicionar_local(1, "Biblioteca", "Setor de livros")
    adicionar_local(10, "Laboratorio de Informatica", "Espaço com computadores e bancadas")

    # Mapeamento dos caminhos
    adicionar_conexao(
        origem_id=0,
        destino_id=1,
        distancia_passos=15,
        orientacao="Siga em frente pelo corredor principal",
        bidirecional=True,
    )
    adicionar_conexao(
        origem_id=1,
        destino_id=10,
        distancia_passos=10,
        orientacao="Vire à esquerda",
        bidirecional=True,
    )

    print("\n--- LOCAIS CADASTRADOS ---")
    for loc in listar_locais():
        print(loc)

    print("\n--- CORREDORES MAPEADOS ---")
    for con in listar_conexoes():
        print(con)
        