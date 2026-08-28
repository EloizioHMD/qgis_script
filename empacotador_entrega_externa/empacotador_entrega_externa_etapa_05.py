# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Empacotador de Dados para Entrega Externa
Etapa: 05 - Manifesto, Integridade e Fechamento do Pacote

Descrição:
    Quinta etapa do Empacotador de Dados para Entrega Externa.

    O script recebe uma pasta produzida pelas Etapas 3 e 4 e executa:

    1. Validação da estrutura obrigatória;
    2. Leitura do inventário;
    3. Leitura e validação do projeto QGZ;
    4. Verificação das camadas do projeto;
    5. Verificação de fontes apontando para dentro do pacote;
    6. Conferência das tabelas do GeoPackage;
    7. Geração de hashes SHA-256;
    8. Geração do manifesto_pacote.json;
    9. Geração do LEIA-ME.txt;
    10. Geração do verificacao_integridade.sha256;
    11. Geração do PACOTE_VALIDADO.txt.

    Nenhuma camada, geometria ou atributo é alterado.

Autor: Eloízio Dantas
Data de Criação: 2026-08-28
Versão: 0.5.0

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x
    - Pacote criado pelas Etapas 3 e 4
    - Projeto QGZ na raiz
    - Inventário CSV
    - GeoPackage dados_entrega.gpkg

Premissas e Limitações:
    - O pacote deve conter exatamente um projeto QGZ na raiz.
    - O script não avalia a autorização jurídica de compartilhamento.
    - O hash demonstra integridade de arquivo, não autenticidade jurídica.
    - A validação estrutural não substitui conferência visual.
===============================================================================
"""


# =============================================================================
# 1. IMPORTAÇÕES
# =============================================================================

import csv
import hashlib
import json
import os
import platform
import tempfile
import zipfile

from datetime import datetime

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog,
    QgsProject,
    QgsVectorLayer
)

from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QMessageBox
)

from qgis.utils import iface


# =============================================================================
# 2. CONFIGURAÇÕES
# =============================================================================

VERSAO_SCRIPT = "0.5.0"

NOME_INVENTARIO = "inventario_camadas.csv"
NOME_GEOPACKAGE = "dados_entrega.gpkg"

NOME_MANIFESTO = "manifesto_pacote.json"
NOME_HASHES = "verificacao_integridade.sha256"
NOME_LEIA_ME = "LEIA-ME.txt"
NOME_VALIDACAO = "PACOTE_VALIDADO.txt"
NOME_LOG = "fechamento_pacote_etapa_05.log"

ARQUIVOS_GERADOS_NESTA_ETAPA = {
    NOME_MANIFESTO,
    NOME_HASHES,
    NOME_LEIA_ME,
    NOME_VALIDACAO
}


# =============================================================================
# 3. FUNÇÕES DE DATA E CAMINHO
# =============================================================================

def agora_iso():
    """
    Retorna data e hora local em formato ISO.
    """

    return datetime.now().astimezone().isoformat(
        timespec="seconds"
    )


def caminho_relativo(
    caminho,
    pasta_raiz
):
    """
    Retorna caminho relativo com barras padronizadas.
    """

    return os.path.relpath(
        caminho,
        pasta_raiz
    ).replace(
        "\\",
        "/"
    )


def caminho_esta_dentro(
    caminho,
    pasta_raiz
):
    """
    Verifica se um caminho está contido na pasta do pacote.
    """

    caminho_real = os.path.realpath(
        caminho
    )

    pasta_real = os.path.realpath(
        pasta_raiz
    )

    try:

        return os.path.commonpath([
            caminho_real,
            pasta_real
        ]) == pasta_real

    except ValueError:

        return False


# =============================================================================
# 4. LOG
# =============================================================================

def registrar_log(
    caminho_log,
    mensagem
):
    """
    Registra uma linha no console e no arquivo de log.
    """

    data_hora = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    linha = (
        f"[{data_hora}] {mensagem}"
    )

    print(
        linha
    )

    with open(
        caminho_log,
        "a",
        encoding="utf-8"
    ) as arquivo:

        arquivo.write(
            linha + "\n"
        )


# =============================================================================
# 5. LOCALIZAÇÃO DOS ARQUIVOS
# =============================================================================

def localizar_estrutura_pacote(
    pasta_pacote
):
    """
    Localiza e valida os arquivos fundamentais do pacote.
    """

    if not os.path.isdir(
        pasta_pacote
    ):

        raise Exception(
            "A pasta selecionada não existe."
        )

    caminho_inventario = os.path.join(
        pasta_pacote,
        NOME_INVENTARIO
    )

    caminho_gpkg = os.path.join(
        pasta_pacote,
        "dados",
        "vetores",
        NOME_GEOPACKAGE
    )

    pasta_estilos = os.path.join(
        pasta_pacote,
        "estilos"
    )

    pasta_logs = os.path.join(
        pasta_pacote,
        "logs"
    )

    projetos_qgz = [
        os.path.join(
            pasta_pacote,
            nome
        )
        for nome in os.listdir(pasta_pacote)
        if (
            nome.lower().endswith(".qgz")
            and os.path.isfile(
                os.path.join(
                    pasta_pacote,
                    nome
                )
            )
        )
    ]

    problemas = []

    if not os.path.isfile(
        caminho_inventario
    ):

        problemas.append(
            f"Inventário ausente: {NOME_INVENTARIO}"
        )

    if not os.path.isfile(
        caminho_gpkg
    ):

        problemas.append(
            "GeoPackage ausente: "
            "dados/vetores/dados_entrega.gpkg"
        )

    if not os.path.isdir(
        pasta_estilos
    ):

        problemas.append(
            "Pasta de estilos ausente."
        )

    if len(projetos_qgz) == 0:

        problemas.append(
            "Nenhum projeto QGZ foi localizado na raiz."
        )

    if len(projetos_qgz) > 1:

        problemas.append(
            "Existe mais de um projeto QGZ na raiz."
        )

    if problemas:

        raise Exception(
            "A estrutura do pacote está incompleta:\n\n"
            + "\n".join(
                f"• {problema}"
                for problema in problemas
            )
        )

    if not os.path.isdir(
        pasta_logs
    ):

        os.makedirs(
            pasta_logs
        )

    return {
        "pasta_pacote": pasta_pacote,
        "inventario": caminho_inventario,
        "geopackage": caminho_gpkg,
        "estilos": pasta_estilos,
        "logs": pasta_logs,
        "qgz": projetos_qgz[0],
        "manifesto": os.path.join(
            pasta_pacote,
            NOME_MANIFESTO
        ),
        "hashes": os.path.join(
            pasta_pacote,
            NOME_HASHES
        ),
        "leia_me": os.path.join(
            pasta_pacote,
            NOME_LEIA_ME
        ),
        "validacao": os.path.join(
            pasta_pacote,
            NOME_VALIDACAO
        )
    }


# =============================================================================
# 6. LEITURA DO INVENTÁRIO
# =============================================================================

def inteiro_seguro(
    valor,
    padrao=0
):
    """
    Converte valores textuais para inteiro.
    """

    try:

        return int(
            str(valor).strip()
        )

    except Exception:

        return padrao


def ler_inventario(
    caminho_inventario
):
    """
    Lê o inventário CSV da Etapa 3.
    """

    registros = []

    with open(
        caminho_inventario,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo:

        leitor = csv.DictReader(
            arquivo,
            delimiter=";"
        )

        campos_obrigatorios = {
            "nome_original",
            "nome_tabela_gpkg",
            "crs",
            "feicoes_origem",
            "feicoes_exportadas",
            "feicoes_vazias_ignoradas",
            "geometrias_invalidas"
        }

        campos_encontrados = set(
            leitor.fieldnames or []
        )

        campos_ausentes = (
            campos_obrigatorios
            - campos_encontrados
        )

        if campos_ausentes:

            raise Exception(
                "O inventário não contém todos os campos "
                "obrigatórios:\n\n"
                + "\n".join(
                    f"• {campo}"
                    for campo in sorted(
                        campos_ausentes
                    )
                )
            )

        for linha in leitor:

            registros.append(
                linha
            )

    if not registros:

        raise Exception(
            "O inventário está vazio."
        )

    return registros


def resumir_inventario(
    registros
):
    """
    Consolida os indicadores do inventário.
    """

    total_origem = sum(
        inteiro_seguro(
            registro.get(
                "feicoes_origem"
            )
        )
        for registro in registros
    )

    total_exportadas = sum(
        inteiro_seguro(
            registro.get(
                "feicoes_exportadas"
            )
        )
        for registro in registros
    )

    total_vazias = sum(
        inteiro_seguro(
            registro.get(
                "feicoes_vazias_ignoradas"
            )
        )
        for registro in registros
    )

    total_invalidas = sum(
        inteiro_seguro(
            registro.get(
                "geometrias_invalidas"
            )
        )
        for registro in registros
    )

    crs_encontrados = sorted({
        registro.get(
            "crs",
            ""
        ).strip()
        for registro in registros
        if registro.get(
            "crs",
            ""
        ).strip()
    })

    geometrias = sorted({
        registro.get(
            "tipo_geometria",
            ""
        ).strip()
        for registro in registros
        if registro.get(
            "tipo_geometria",
            ""
        ).strip()
    })

    campos_renomeados = []

    for registro in registros:

        texto = registro.get(
            "campos_renomeados",
            ""
        ).strip()

        if texto:

            campos_renomeados.append({
                "camada": registro.get(
                    "nome_original",
                    ""
                ),
                "alteracoes": texto
            })

    return {
        "camadas": len(registros),
        "feicoes_origem": total_origem,
        "feicoes_exportadas": total_exportadas,
        "feicoes_vazias_ignoradas": total_vazias,
        "geometrias_invalidas": total_invalidas,
        "crs": crs_encontrados,
        "tipos_geometria": geometrias,
        "campos_renomeados": campos_renomeados
    }


# =============================================================================
# 7. VALIDAÇÃO DO PROJETO QGZ
# =============================================================================

def validar_estrutura_zip_qgz(
    caminho_qgz
):
    """
    Confirma que o arquivo é um QGZ válido e contém um QGS.
    """

    if not zipfile.is_zipfile(
        caminho_qgz
    ):

        raise Exception(
            "O arquivo QGZ não possui uma estrutura ZIP válida."
        )

    with zipfile.ZipFile(
        caminho_qgz,
        "r"
    ) as arquivo:

        projetos_internos = [
            nome
            for nome in arquivo.namelist()
            if nome.lower().endswith(
                ".qgs"
            )
        ]

    if not projetos_internos:

        raise Exception(
            "O QGZ não contém um arquivo QGS interno."
        )

    return projetos_internos[0]


def validar_projeto(
    caminho_qgz,
    pasta_pacote,
    quantidade_esperada
):
    """
    Reabre o QGZ e valida suas camadas e fontes.
    """

    projeto = QgsProject()

    if not projeto.read(
        caminho_qgz
    ):

        raise Exception(
            "O QGZ não pôde ser lido pelo QGIS."
        )

    camadas = list(
        projeto.mapLayers().values()
    )

    if len(camadas) != quantidade_esperada:

        raise Exception(
            "A quantidade de camadas do projeto diverge "
            "do inventário.\n\n"
            f"Inventário: {quantidade_esperada}\n"
            f"Projeto: {len(camadas)}"
        )

    invalidas = []
    fontes_fora = []
    fontes_ausentes = []
    detalhes_camadas = []

    for camada in camadas:

        fonte = camada.source()
        caminho_fonte = fonte.split(
            "|"
        )[0]

        valida = camada.isValid()
        dentro_pacote = caminho_esta_dentro(
            caminho_fonte,
            pasta_pacote
        )

        existe = os.path.exists(
            caminho_fonte
        )

        if not valida:

            invalidas.append(
                camada.name()
            )

        if not dentro_pacote:

            fontes_fora.append({
                "camada": camada.name(),
                "fonte": fonte
            })

        if not existe:

            fontes_ausentes.append({
                "camada": camada.name(),
                "fonte": fonte
            })

        detalhes_camadas.append({
            "nome": camada.name(),
            "valida": valida,
            "crs": camada.crs().authid(),
            "fonte_relativa": caminho_relativo(
                caminho_fonte,
                pasta_pacote
            ) if dentro_pacote else fonte,
            "feicoes": (
                camada.featureCount()
                if isinstance(
                    camada,
                    QgsVectorLayer
                )
                else None
            )
        })

    projeto.clear()

    if invalidas:

        raise Exception(
            "O QGZ possui camadas inválidas:\n\n"
            + "\n".join(
                f"• {nome}"
                for nome in invalidas
            )
        )

    if fontes_fora:

        raise Exception(
            "O QGZ possui fontes apontando para fora "
            "do pacote:\n\n"
            + "\n".join(
                (
                    f"• {item['camada']}: "
                    f"{item['fonte']}"
                )
                for item in fontes_fora
            )
        )

    if fontes_ausentes:

        raise Exception(
            "O QGZ referencia fontes inexistentes:\n\n"
            + "\n".join(
                (
                    f"• {item['camada']}: "
                    f"{item['fonte']}"
                )
                for item in fontes_ausentes
            )
        )

    return {
        "quantidade_camadas": len(camadas),
        "camadas_invalidas": len(invalidas),
        "fontes_fora_pacote": len(fontes_fora),
        "fontes_ausentes": len(fontes_ausentes),
        "camadas": detalhes_camadas
    }


# =============================================================================
# 8. VALIDAÇÃO DO GEOPACKAGE
# =============================================================================

def validar_geopackage(
    caminho_gpkg,
    registros_inventario
):
    """
    Reabre cada tabela do GeoPackage e compara sua contagem.
    """

    tabelas_validadas = []
    erros = []

    for registro in registros_inventario:

        nome_tabela = registro[
            "nome_tabela_gpkg"
        ]

        nome_original = registro[
            "nome_original"
        ]

        quantidade_esperada = inteiro_seguro(
            registro[
                "feicoes_exportadas"
            ]
        )

        uri = (
            f"{caminho_gpkg}"
            f"|layername={nome_tabela}"
        )

        camada = QgsVectorLayer(
            uri,
            nome_original,
            "ogr"
        )

        if not camada.isValid():

            erros.append(
                f"{nome_tabela}: tabela inválida."
            )

            continue

        quantidade_encontrada = (
            camada.featureCount()
        )

        if quantidade_encontrada != quantidade_esperada:

            erros.append(
                (
                    f"{nome_tabela}: esperado "
                    f"{quantidade_esperada}, encontrado "
                    f"{quantidade_encontrada}."
                )
            )

            continue

        tabelas_validadas.append({
            "nome_tabela": nome_tabela,
            "nome_exibido": nome_original,
            "feicoes": quantidade_encontrada,
            "crs": camada.crs().authid()
        })

    if erros:

        raise Exception(
            "Foram encontradas divergências no GeoPackage:\n\n"
            + "\n".join(
                f"• {erro}"
                for erro in erros
            )
        )

    return {
        "tabelas_validadas": len(
            tabelas_validadas
        ),
        "tabelas": tabelas_validadas
    }


# =============================================================================
# 9. LEVANTAMENTO DOS ARQUIVOS
# =============================================================================

def listar_arquivos_do_pacote(
    pasta_pacote,
    excluir_gerados=True
):
    """
    Lista os arquivos regulares do pacote.

    Durante o cálculo inicial, exclui os arquivos gerados nesta etapa
    para evitar hash circular do arquivo de hashes ou do manifesto.
    """

    arquivos = []

    for raiz, diretorios, nomes in os.walk(
        pasta_pacote
    ):

        # Ignora caches e diretórios temporários.
        diretorios[:] = [
            diretorio
            for diretorio in diretorios
            if diretorio not in {
                "__pycache__",
                ".git",
                ".qgis"
            }
        ]

        for nome in nomes:

            if (
                excluir_gerados
                and nome in ARQUIVOS_GERADOS_NESTA_ETAPA
            ):

                continue

            caminho = os.path.join(
                raiz,
                nome
            )

            if os.path.isfile(
                caminho
            ):

                arquivos.append(
                    caminho
                )

    arquivos.sort(
        key=lambda caminho: caminho_relativo(
            caminho,
            pasta_pacote
        ).lower()
    )

    return arquivos


# =============================================================================
# 10. HASH SHA-256
# =============================================================================

def calcular_sha256(
    caminho_arquivo,
    tamanho_bloco=1024 * 1024
):
    """
    Calcula SHA-256 sem carregar o arquivo inteiro na memória.
    """

    objeto_hash = hashlib.sha256()

    with open(
        caminho_arquivo,
        "rb"
    ) as arquivo:

        while True:

            bloco = arquivo.read(
                tamanho_bloco
            )

            if not bloco:

                break

            objeto_hash.update(
                bloco
            )

    return objeto_hash.hexdigest()


def gerar_registros_hash(
    arquivos,
    pasta_pacote
):
    """
    Calcula hash, tamanho e caminho relativo.
    """

    registros = []

    for indice, caminho in enumerate(
        arquivos,
        start=1
    ):

        relativo = caminho_relativo(
            caminho,
            pasta_pacote
        )

        print(
            f"Calculando hash {indice}/"
            f"{len(arquivos)}: {relativo}"
        )

        registros.append({
            "arquivo": relativo,
            "sha256": calcular_sha256(
                caminho
            ),
            "tamanho_bytes": os.path.getsize(
                caminho
            )
        })

    return registros


def escrever_arquivo_hashes(
    caminho_saida,
    registros_hash
):
    """
    Escreve arquivo no formato convencional:
    hash  caminho_relativo
    """

    with open(
        caminho_saida,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as arquivo:

        for registro in registros_hash:

            arquivo.write(
                f"{registro['sha256']}  "
                f"{registro['arquivo']}\n"
            )


# =============================================================================
# 11. MANIFESTO JSON
# =============================================================================

def obter_versao_qgis():
    """
    Obtém a versão do QGIS com compatibilidade entre APIs.
    """

    try:

        return Qgis.QGIS_VERSION

    except Exception:

        try:

            return QgsApplication.qgisVersion()

        except Exception:

            return "Não identificada"


def criar_manifesto(
    pasta_pacote,
    estrutura,
    resumo_inventario,
    validacao_projeto,
    validacao_gpkg,
    registros_hash
):
    """
    Monta o manifesto técnico do pacote.
    """

    tamanho_total = sum(
        registro["tamanho_bytes"]