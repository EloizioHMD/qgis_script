# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Empacotador de Dados para Entrega Externa
Etapa: 04 - Criação do Projeto QGZ Portátil

Descrição:
    Quarta etapa do Empacotador de Dados para Entrega Externa.

    O script utiliza o pacote criado na Etapa 3 para gerar um novo projeto
    QGIS portátil, armazenado na raiz da pasta de entrega.

    O projeto gerado:

    1. Carrega as tabelas do GeoPackage dados_entrega.gpkg;
    2. Utiliza os nomes originais das camadas no painel Camadas;
    3. Aplica os estilos QML exportados na Etapa 3;
    4. Preserva, quando possível, grupos, ordem e visibilidade;
    5. Preserva o CRS do projeto atual;
    6. Utiliza caminhos relativos;
    7. É salvo em formato QGZ;
    8. É reaberto e validado em uma instância independente;
    9. Não altera o projeto atualmente aberto no QGIS.

Autor: Eloízio Dantas
Data de Criação: 2026-08-28
Versão: 0.4.0

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x
    - Pacote previamente criado pela Etapa 3
    - Arquivo inventario_camadas.csv
    - Arquivo dados/vetores/dados_entrega.gpkg

Premissas e Limitações:
    - As mesmas camadas da Etapa 3 devem permanecer selecionadas.
    - O inventário deve corresponder ao GeoPackage do pacote.
    - Grupos, ordem e visibilidade dependem das camadas ainda existentes
      no projeto atual.
    - Layouts de impressão, temas de mapa, relações, joins, formulários,
      anotações e configurações de plugins ainda não são copiados.
    - Ícones SVG, imagens e fontes externas referenciadas pelos estilos
      podem exigir um módulo adicional.
===============================================================================
"""


# =============================================================================
# 1. IMPORTAÇÕES
# =============================================================================

import csv
import os
import re
import unicodedata

from datetime import datetime

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMessageLog,
    QgsProject,
    QgsVectorLayer
)

from qgis.PyQt.QtCore import Qt

from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout
)

from qgis.utils import iface


# =============================================================================
# 2. CONFIGURAÇÕES
# =============================================================================

VERSAO_SCRIPT = "0.4.0"

NOME_GEOPACKAGE = "dados_entrega.gpkg"
NOME_INVENTARIO = "inventario_camadas.csv"
NOME_LOG = "criacao_projeto_etapa_04.log"


# =============================================================================
# 3. FUNÇÕES DE NOMENCLATURA
# =============================================================================

def remover_acentos(texto):
    """
    Remove acentos utilizando normalização Unicode.
    """

    texto_normalizado = unicodedata.normalize(
        "NFKD",
        str(texto)
    )

    return "".join(
        caractere
        for caractere in texto_normalizado
        if not unicodedata.combining(caractere)
    )


def normalizar_nome(nome, maiusculo=False, limite=70):
    """
    Cria um nome seguro para arquivo ou título.
    """

    nome = remover_acentos(
        nome
    )

    nome = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        nome
    )

    nome = re.sub(
        r"_+",
        "_",
        nome
    )

    nome = nome.strip(
        "_"
    )

    if not nome:

        nome = "PROJETO_QGIS"

    if nome[0].isdigit():

        nome = "PROJETO_" + nome

    if maiusculo:

        nome = nome.upper()

    else:

        nome = nome.lower()

    return nome[:limite].rstrip("_")


def extrair_nome_base_do_pacote(pasta_pacote):
    """
    Tenta obter o nome-base a partir do nome da pasta.

    Exemplo:
        ENTREGA_ARCOS_CAR_20260828_v001
        retorna ARCOS_CAR
    """

    nome_pasta = os.path.basename(
        os.path.normpath(pasta_pacote)
    )

    correspondencia = re.match(
        r"^ENTREGA_(.+)_\d{8}_v\d{3}$",
        nome_pasta,
        flags=re.IGNORECASE
    )

    if correspondencia:

        return normalizar_nome(
            correspondencia.group(1),
            maiusculo=True
        )

    return normalizar_nome(
        nome_pasta,
        maiusculo=True
    )


# =============================================================================
# 4. LOG
# =============================================================================

def registrar_log(caminho_log, mensagem):
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
# 5. LEITURA E VALIDAÇÃO DO PACOTE
# =============================================================================

def localizar_arquivos_pacote(pasta_pacote):
    """
    Monta e valida os caminhos obrigatórios do pacote.
    """

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

    problemas = []

    if not os.path.isfile(caminho_inventario):

        problemas.append(
            f"Inventário não encontrado: {caminho_inventario}"
        )

    if not os.path.isfile(caminho_gpkg):

        problemas.append(
            f"GeoPackage não encontrado: {caminho_gpkg}"
        )

    if not os.path.isdir(pasta_estilos):

        problemas.append(
            f"Pasta de estilos não encontrada: {pasta_estilos}"
        )

    if problemas:

        raise Exception(
            "A pasta selecionada não corresponde a um pacote "
            "válido da Etapa 3.\n\n"
            + "\n".join(
                f"• {problema}"
                for problema in problemas
            )
        )

    if not os.path.isdir(pasta_logs):

        os.makedirs(
            pasta_logs
        )

    return {
        "inventario": caminho_inventario,
        "geopackage": caminho_gpkg,
        "estilos": pasta_estilos,
        "logs": pasta_logs
    }


def ler_inventario(caminho_inventario):
    """
    Lê o inventário produzido na Etapa 3.
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
            "ordem",
            "nome_original",
            "nome_tabela_gpkg",
            "crs",
            "feicoes_exportadas",
            "estilo_qml"
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
                "O inventário não possui todos os campos obrigatórios.\n\n"
                "Campos ausentes:\n"
                + "\n".join(
                    f"• {campo}"
                    for campo in sorted(campos_ausentes)
                )
            )

        for linha in leitor:

            linha["ordem"] = int(
                linha["ordem"]
            )

            linha["feicoes_exportadas"] = int(
                linha["feicoes_exportadas"]
            )

            registros.append(
                linha
            )

    if not registros:

        raise Exception(
            "O inventário não contém registros."
        )

    registros.sort(
        key=lambda registro: registro["ordem"]
    )

    return registros


# =============================================================================
# 6. ÁRVORE DO PROJETO ORIGINAL
# =============================================================================

def obter_caminho_grupo_do_no(no_camada):
    """
    Retorna os grupos ancestrais de um nó de camada.

    Exemplo:
        ["Licenciamento", "Imóveis", "Matrículas"]
    """

    grupos = []

    no_atual = no_camada.parent()

    while no_atual is not None:

        if isinstance(
            no_atual,
            QgsLayerTreeGroup
        ):

            nome_grupo = no_atual.name()

            # O grupo raiz possui nome vazio
            if nome_grupo:

                grupos.append(
                    nome_grupo
                )

        no_atual = no_atual.parent()

    grupos.reverse()

    return grupos


def obter_posicao_arvore(no_camada):
    """
    Retorna uma tupla que representa a posição do nó na árvore.

    A tupla pode ser usada para ordenar camadas conforme sua posição
    visual no painel Camadas.
    """

    posicoes = []

    no_atual = no_camada

    while no_atual.parent() is not None:

        pai = no_atual.parent()

        try:

            indice = pai.children().index(
                no_atual
            )

        except ValueError:

            indice = 0

        posicoes.append(
            indice
        )

        no_atual = pai

    posicoes.reverse()

    return tuple(
        posicoes
    )


def capturar_metadados_arvore(camadas):
    """
    Captura nome, grupos, ordem e visibilidade das camadas selecionadas.
    """

    raiz = QgsProject.instance().layerTreeRoot()

    metadados = []

    for camada in camadas:

        no_camada = raiz.findLayer(
            camada.id()
        )

        if no_camada is None:

            metadados.append({
                "id_original": camada.id(),
                "nome_original": camada.name(),
                "grupos": [],
                "posicao": (999999,),
                "visivel": True,
                "expandido": True
            })

            continue

        metadados.append({
            "id_original": camada.id(),
            "nome_original": camada.name(),
            "grupos": obter_caminho_grupo_do_no(
                no_camada
            ),
            "posicao": obter_posicao_arvore(
                no_camada
            ),
            "visivel": no_camada.itemVisibilityChecked(),
            "expandido": no_camada.isExpanded()
        })

    metadados.sort(
        key=lambda item: item["posicao"]
    )

    return metadados


def associar_inventario_as_camadas(
    metadados_arvore,
    registros_inventario
):
    """
    Associa cada camada selecionada a um registro do inventário.

    A associação é feita pelo nome original e pela ordem de ocorrência.
    Isso também permite tratar nomes repetidos.
    """

    registros_por_nome = {}

    for registro in registros_inventario:

        nome = registro["nome_original"]

        if nome not in registros_por_nome:

            registros_por_nome[nome] = []

        registros_por_nome[nome].append(
            registro
        )

    usados_por_nome = {}

    associacoes = []
    nao_associadas = []

    for metadado in metadados_arvore:

        nome = metadado["nome_original"]

        indice_ocorrencia = usados_por_nome.get(
            nome,
            0
        )

        candidatos = registros_por_nome.get(
            nome,
            []
        )

        if indice_ocorrencia >= len(candidatos):

            nao_associadas.append(
                nome
            )

            continue

        registro = candidatos[
            indice_ocorrencia
        ]

        usados_por_nome[nome] = (
            indice_ocorrencia + 1
        )

        associacao = dict(
            metadado
        )

        associacao.update({
            "registro_inventario": registro,
            "nome_tabela_gpkg":
                registro["nome_tabela_gpkg"],
            "estilo_qml":
                registro.get("estilo_qml", ""),
            "feicoes_exportadas":
                registro["feicoes_exportadas"],
            "crs_inventario":
                registro.get("crs", "")
        })

        associacoes.append(
            associacao
        )

    if nao_associadas:

        raise Exception(
            "Algumas camadas selecionadas não foram localizadas "
            "no inventário da Etapa 3.\n\n"
            + "\n".join(
                f"• {nome}"
                for nome in nao_associadas
            )
            + "\n\nSelecione as mesmas camadas utilizadas "
              "na criação do GeoPackage."
        )

    if len(associacoes) != len(registros_inventario):

        nomes_selecionados = [
            item["nome_original"]
            for item in associacoes
        ]

        inventario_nao_associado = [
            registro["nome_original"]
            for registro in registros_inventario
            if registro["nome_original"]
            not in nomes_selecionados
        ]

        if inventario_nao_associado:

            raise Exception(
                "O inventário possui camadas que não estão selecionadas "
                "no projeto atual.\n\n"
                + "\n".join(
                    f"• {nome}"
                    for nome in inventario_nao_associado
                )
                + "\n\nSelecione todas as camadas utilizadas "
                  "na Etapa 3."
            )

    return associacoes


# =============================================================================
# 7. INTERFACE
# =============================================================================

class JanelaCriacaoProjeto(QDialog):
    """
    Janela de configuração da Etapa 4.
    """

    def __init__(
        self,
        camadas_selecionadas,
        parent=None
    ):

        super().__init__(parent)

        self.camadas = camadas_selecionadas

        self.configurar_janela()
        self.criar_interface()


    def configurar_janela(self):
        """
        Configura a janela.
        """

        self.setWindowTitle(
            "Empacotador de Entrega Externa - Etapa 4"
        )

        self.setMinimumWidth(720)
        self.setMinimumHeight(570)

        self.setWindowModality(
            Qt.ApplicationModal
        )


    def criar_interface(self):
        """
        Cria os componentes da janela.
        """

        layout_principal = QVBoxLayout()

        self.setLayout(
            layout_principal
        )

        apresentacao = QLabel(
            "<b>Etapa 4:</b> criação do projeto QGZ portátil.<br><br>"
            "Selecione a pasta criada e validada na Etapa 3. "
            "O projeto será criado na raiz dessa pasta."
        )

        apresentacao.setWordWrap(True)

        layout_principal.addWidget(
            apresentacao
        )

        # ---------------------------------------------------------------------
        # CAMADAS
        # ---------------------------------------------------------------------

        grupo_camadas = QGroupBox(
            "Camadas atualmente selecionadas"
        )

        layout_camadas = QVBoxLayout()

        grupo_camadas.setLayout(
            layout_camadas
        )

        lista_camadas = QListWidget()

        for camada in self.camadas:

            item = QListWidgetItem(
                camada.name()
            )

            lista_camadas.addItem(
                item
            )

        layout_camadas.addWidget(
            lista_camadas
        )

        layout_camadas.addWidget(
            QLabel(
                f"<b>Total:</b> {len(self.camadas)} camada(s)"
            )
        )

        layout_principal.addWidget(
            grupo_camadas
        )

        # ---------------------------------------------------------------------
        # PACOTE
        # ---------------------------------------------------------------------

        grupo_pacote = QGroupBox(
            "Pacote da Etapa 3"
        )

        layout_pacote = QVBoxLayout()

        grupo_pacote.setLayout(
            layout_pacote
        )

        layout_pacote.addWidget(
            QLabel("Pasta do pacote:")
        )

        layout_selecao = QHBoxLayout()

        self.campo_pacote = QLineEdit()

        self.campo_pacote.setReadOnly(
            True
        )

        self.campo_pacote.setPlaceholderText(
            "Selecione ENTREGA_NOME_DATA_vNNN"
        )

        botao_pacote = QPushButton(
            "Selecionar..."
        )

        botao_pacote.clicked.connect(
            self.selecionar_pacote
        )

        layout_selecao.addWidget(
            self.campo_pacote
        )

        layout_selecao.addWidget(
            botao_pacote
        )

        layout_pacote.addLayout(
            layout_selecao
        )

        layout_principal.addWidget(
            grupo_pacote
        )

        # ---------------------------------------------------------------------
        # NOME DO PROJETO
        # ---------------------------------------------------------------------

        grupo_projeto = QGroupBox(
            "Projeto de entrega"
        )

        layout_projeto = QVBoxLayout()

        grupo_projeto.setLayout(
            layout_projeto
        )

        layout_projeto.addWidget(
            QLabel("Nome do arquivo QGZ:")
        )

        self.campo_nome_qgz = QLineEdit()

        self.campo_nome_qgz.setPlaceholderText(
            "Exemplo: ARCOS_CAR_ENTREGA.qgz"
        )

        layout_projeto.addWidget(
            self.campo_nome_qgz
        )

        layout_principal.addWidget(
            grupo_projeto
        )

        # ---------------------------------------------------------------------
        # REGRAS
        # ---------------------------------------------------------------------

        regras = QLabel(
            "<b>Regras desta etapa:</b><br>"
            "• o projeto atual não será alterado;<br>"
            "• somente as tabelas do GeoPackage serão usadas;<br>"
            "• os estilos QML serão aplicados;<br>"
            "• grupos, ordem e visibilidade serão reproduzidos;<br>"
            "• os caminhos serão gravados como relativos;<br>"
            "• o projeto será reaberto e validado após a gravação."
        )

        regras.setWordWrap(True)

        layout_principal.addWidget(
            regras
        )

        # ---------------------------------------------------------------------
        # BOTÕES
        # ---------------------------------------------------------------------

        caixa_botoes = QDialogButtonBox(
            QDialogButtonBox.Ok
            | QDialogButtonBox.Cancel
        )

        botao_ok = caixa_botoes.button(
            QDialogButtonBox.Ok
        )

        botao_ok.setText(
            "Criar projeto QGZ"
        )

        caixa_botoes.accepted.connect(
            self.validar_e_aceitar
        )

        caixa_botoes.rejected.connect(
            self.reject
        )

        layout_principal.addWidget(
            caixa_botoes
        )


    def selecionar_pacote(self):
        """
        Seleciona a pasta produzida na Etapa 3.
        """

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pacote produzido na Etapa 3",
            os.path.expanduser("~")
        )

        if not pasta:

            return

        try:

            localizar_arquivos_pacote(
                pasta
            )

        except Exception as erro:

            QMessageBox.warning(
                self,
                "Pacote inválido",
                str(erro)
            )

            return

        self.campo_pacote.setText(
            pasta
        )

        nome_base = extrair_nome_base_do_pacote(
            pasta
        )

        self.campo_nome_qgz.setText(
            f"{nome_base}_ENTREGA.qgz"
        )


    def validar_e_aceitar(self):
        """
        Valida a configuração.
        """

        pasta = self.campo_pacote.text().strip()

        if not pasta:

            QMessageBox.warning(
                self,
                "Pacote não informado",
                "Selecione a pasta produzida na Etapa 3."
            )

            return

        try:

            localizar_arquivos_pacote(
                pasta
            )

        except Exception as erro:

            QMessageBox.warning(
                self,
                "Pacote inválido",
                str(erro)
            )

            return

        nome_qgz = self.campo_nome_qgz.text().strip()

        if not nome_qgz:

            QMessageBox.warning(
                self,
                "Nome não informado",
                "Informe o nome do projeto QGZ."
            )

            return

        if not nome_qgz.lower().endswith(".qgz"):

            nome_qgz += ".qgz"

            self.campo_nome_qgz.setText(
                nome_qgz
            )

        nome_sem_extensao = os.path.splitext(
            nome_qgz
        )[0]

        nome_normalizado = normalizar_nome(
            nome_sem_extensao,
            maiusculo=True
        )

        nome_qgz = (
            nome_normalizado + ".qgz"
        )

        self.campo_nome_qgz.setText(
            nome_qgz
        )

        caminho_qgz = os.path.join(
            pasta,
            nome_qgz
        )

        if os.path.exists(caminho_qgz):

            QMessageBox.warning(
                self,
                "Projeto já existente",
                (
                    "Já existe um projeto com esse nome:\n\n"
                    f"{caminho_qgz}\n\n"
                    "Para evitar sobrescrita, informe outro nome."
                )
            )

            return

        self.accept()


    def obter_configuracao(self):
        """
        Retorna a configuração validada.
        """

        pasta = self.campo_pacote.text().strip()

        nome_qgz = self.campo_nome_qgz.text().strip()

        if not nome_qgz.lower().endswith(".qgz"):

            nome_qgz += ".qgz"

        return {
            "pasta_pacote": pasta,
            "nome_qgz": nome_qgz,
            "caminho_qgz": os.path.join(
                pasta,
                nome_qgz
            )
        }


# =============================================================================
# 8. CAMINHOS RELATIVOS
# =============================================================================

def configurar_caminhos_relativos(projeto):
    """
    Configura o projeto para armazenar caminhos relativos.

    Inclui uma alternativa para compatibilidade entre versões do QGIS.
    """

    configurado = False

    try:

        projeto.setFilePathStorage(
            Qgis.FilePathType.Relative
        )

        configurado = True

    except Exception:

        pass

    if not configurado:

        try:

            # Compatibilidade com APIs mais antigas.
            projeto.writeEntry(
                "Paths",
                "/Absolute",
                False
            )

            configurado = True

        except Exception:

            pass

    if not configurado:

        raise Exception(
            "Não foi possível configurar caminhos relativos "
            "no projeto de entrega."
        )


# =============================================================================
# 9. CRIAÇÃO DE GRUPOS
# =============================================================================

def obter_ou_criar_grupo(
    raiz,
    caminho_grupos,
    cache_grupos
):
    """
    Obtém ou cria a sequência de grupos no novo projeto.
    """

    if not caminho_grupos:

        return raiz

    grupo_atual = raiz
    chave_acumulada = []

    for nome_grupo in caminho_grupos:

        chave_acumulada.append(
            nome_grupo
        )

        chave = tuple(
            chave_acumulada
        )

        if chave in cache_grupos:

            grupo_atual = cache_grupos[
                chave
            ]

            continue

        grupo_existente = None

        for filho in grupo_atual.children():

            if (
                isinstance(filho, QgsLayerTreeGroup)
                and filho.name() == nome_grupo
            ):

                grupo_existente = filho
                break

        if grupo_existente is None:

            grupo_existente = grupo_atual.addGroup(
                nome_grupo
            )

        cache_grupos[
            chave
        ] = grupo_existente

        grupo_atual = grupo_existente

    return grupo_atual


# =============================================================================
# 10. CARREGAMENTO E ESTILO
# =============================================================================

def localizar_estilo(
    pasta_pacote,
    caminho_estilo_inventario,
    nome_tabela
):
    """
    Localiza o arquivo QML correspondente.
    """

    candidatos = []

    if caminho_estilo_inventario:

        caminho_normalizado = (
            caminho_estilo_inventario
            .replace("/", os.sep)
            .replace("\\", os.sep)
        )

        candidatos.append(
            os.path.join(
                pasta_pacote,
                caminho_normalizado
            )
        )

    candidatos.append(
        os.path.join(
            pasta_pacote,
            "estilos",
            nome_tabela + ".qml"
        )
    )

    for candidato in candidatos:

        if os.path.isfile(candidato):

            return candidato

    return ""


def aplicar_estilo_qml(camada, caminho_qml):
    """
    Aplica um estilo QML à camada.

    Retorno:
        sucesso;
        mensagem.
    """

    if not caminho_qml:

        return {
            "sucesso": False,
            "mensagem": "Arquivo QML não localizado."
        }

    try:

        resultado = camada.loadNamedStyle(
            caminho_qml
        )

        camada.triggerRepaint()

        mensagem = ""

        sucesso = True

        if isinstance(resultado, tuple):

            if len(resultado) >= 1:

                mensagem = str(
                    resultado[0]
                )

            if len(resultado) >= 2:

                sucesso = bool(
                    resultado[1]
                )

        return {
            "sucesso": sucesso,
            "mensagem": mensagem
        }

    except Exception as erro:

        return {
            "sucesso": False,
            "mensagem": str(erro)
        }


# =============================================================================
# 11. CRIAÇÃO DO PROJETO
# =============================================================================

def criar_projeto_entrega(
    associacoes,
    pasta_pacote,
    caminho_gpkg,
    caminho_qgz,
    caminho_log
):
    """
    Cria o projeto QGZ em uma instância independente de QgsProject.
    """

    projeto_origem = QgsProject.instance()

    projeto_entrega = QgsProject()

    # -------------------------------------------------------------------------
    # CONFIGURAÇÕES BÁSICAS
    # -------------------------------------------------------------------------

    projeto_entrega.setTitle(
        os.path.splitext(
            os.path.basename(caminho_qgz)
        )[0]
    )

    if projeto_origem.crs().isValid():

        projeto_entrega.setCrs(
            projeto_origem.crs()
        )

    configurar_caminhos_relativos(
        projeto_entrega
    )

    # O nome do arquivo precisa ser conhecido antes da gravação,
    # para que o resolvedor calcule os caminhos relativos à raiz.
    projeto_entrega.setFileName(
        caminho_qgz
    )

    raiz_entrega = (
        projeto_entrega.layerTreeRoot()
    )

    cache_grupos = {}

    camadas_criadas = []
    estilos_sucesso = 0
    estilos_falha = 0

    # -------------------------------------------------------------------------
    # CARREGAR AS CAMADAS NA ORDEM DA ÁRVORE ORIGINAL
    # -------------------------------------------------------------------------

    for indice, associacao in enumerate(
        associacoes,
        start=1
    ):

        nome_original = associacao[
            "nome_original"
        ]

        nome_tabela = associacao[
            "nome_tabela_gpkg"
        ]

        # Usa o caminho absoluto durante a montagem.
        # O projeto será serializado com caminho relativo.
        uri = (
            f"{caminho_gpkg}"
            f"|layername={nome_tabela}"
        )

        camada_nova = QgsVectorLayer(
            uri,
            nome_original,
            "ogr"
        )

        if not camada_nova.isValid():

            raise Exception(
                "Não foi possível carregar a tabela do GeoPackage.\n\n"
                f"Camada exibida: {nome_original}\n"
                f"Tabela: {nome_tabela}"
            )

        quantidade_encontrada = (
            camada_nova.featureCount()
        )

        quantidade_esperada = associacao[
            "feicoes_exportadas"
        ]

        if quantidade_encontrada != quantidade_esperada:

            raise Exception(
                f"Contagem divergente para '{nome_original}'.\n\n"
                f"Esperado: {quantidade_esperada}\n"
                f"Encontrado: {quantidade_encontrada}"
            )

        crs_inventario = associacao[
            "crs_inventario"
        ]

        if (
            crs_inventario
            and camada_nova.crs().authid()
            and camada_nova.crs().authid() != crs_inventario
        ):

            raise Exception(
                f"CRS divergente para '{nome_original}'.\n\n"
                f"Inventário: {crs_inventario}\n"
                f"GeoPackage: {camada_nova.crs().authid()}"
            )

        # ---------------------------------------------------------------------
        # APLICAR O ESTILO
        # ---------------------------------------------------------------------

        caminho_qml = localizar_estilo(
            pasta_pacote,
            associacao["estilo_qml"],
            nome_tabela
        )

        resultado_estilo = aplicar_estilo_qml(
            camada_nova,
            caminho_qml
        )

        if resultado_estilo["sucesso"]:

            estilos_sucesso += 1

        else:

            estilos_falha += 1

            registrar_log(
                caminho_log,
                (
                    f"Aviso: estilo não aplicado para "
                    f"'{nome_original}'. "
                    f"{resultado_estilo['mensagem']}"
                )
            )

        # ---------------------------------------------------------------------
        # ADICIONAR SEM INSERÇÃO AUTOMÁTICA NA RAIZ
        # ---------------------------------------------------------------------

        projeto_entrega.addMapLayer(
            camada_nova,
            False
        )

        grupo_destino = obter_ou_criar_grupo(
            raiz_entrega,
            associacao["grupos"],
            cache_grupos
        )

        no_novo = grupo_destino.addLayer(
            camada_nova
        )

        no_novo.setItemVisibilityChecked(
            associacao["visivel"]
        )

        no_novo.setExpanded(
            associacao["expandido"]
        )

        camadas_criadas.append({
            "camada": camada_nova,
            "nome_original": nome_original,
            "nome_tabela": nome_tabela,
            "grupos": associacao["grupos"],
            "visivel": associacao["visivel"],
            "estilo_aplicado":
                resultado_estilo["sucesso"]
        })

        registrar_log(
            caminho_log,
            (
                f"Camada {indice}/{len(associacoes)} adicionada: "
                f"'{nome_original}' -> '{nome_tabela}'."
            )
        )

    # -------------------------------------------------------------------------
    # VARIÁVEIS DE RASTREABILIDADE
    # -------------------------------------------------------------------------

    projeto_entrega.setCustomVariables({
        "modalidade_pacote": "ENTREGA_EXTERNA",
        "versao_empacotador": VERSAO_SCRIPT,
        "data_empacotamento": datetime.now().isoformat(
            timespec="seconds"
        ),
        "quantidade_camadas": len(camadas_criadas),
        "geopackage_relativo":
            "dados/vetores/dados_entrega.gpkg"
    })

    # -------------------------------------------------------------------------
    # GRAVAR
    # -------------------------------------------------------------------------

    sucesso_gravacao = projeto_entrega.write(
        caminho_qgz
    )

    if not sucesso_gravacao:

        raise Exception(
            "QgsProject.write() não conseguiu gravar o projeto QGZ."
        )

    if not os.path.isfile(caminho_qgz):

        raise Exception(
            "A gravação foi concluída, mas o arquivo QGZ "
            "não foi localizado."
        )

    if os.path.getsize(caminho_qgz) == 0:

        raise Exception(
            "O projeto QGZ foi criado com tamanho zero."
        )

    return {
        "projeto": projeto_entrega,
        "camadas": camadas_criadas,
        "estilos_sucesso": estilos_sucesso,
        "estilos_falha": estilos_falha
    }


# =============================================================================
# 12. VALIDAÇÃO DO PROJETO GRAVADO
# =============================================================================

def validar_projeto_qgz(
    caminho_qgz,
    pasta_pacote,
    quantidade_esperada,
    caminho_log
):
    """
    Reabre o projeto em uma instância independente e valida suas camadas.
    """

    projeto_validacao = QgsProject()

    sucesso_leitura = projeto_validacao.read(
        caminho_qgz
    )

    if not sucesso_leitura:

        raise Exception(
            "O projeto QGZ foi criado, mas não pôde ser reaberto."
        )

    camadas = list(
        projeto_validacao.mapLayers().values()
    )

    if len(camadas) != quantidade_esperada:

        raise Exception(
            "A quantidade de camadas do QGZ é divergente.\n\n"
            f"Esperado: {quantidade_esperada}\n"
            f"Encontrado: {len(camadas)}"
        )

    camadas_invalidas = []
    fontes_fora_do_pacote = []
    fontes_nao_relativas = []

    caminho_pacote_real = os.path.realpath(
        pasta_pacote
    )

    for camada in camadas:

        if not camada.isValid():

            camadas_invalidas.append(
                camada.name()
            )

            continue

        fonte = camada.source()

        caminho_fonte = fonte.split(
            "|"
        )[0]

        caminho_fonte_real = os.path.realpath(
            caminho_fonte
        )

        try:

            dentro_do_pacote = (
                os.path.commonpath([
                    caminho_pacote_real,
                    caminho_fonte_real
                ])
                == caminho_pacote_real
            )

        except ValueError:

            dentro_do_pacote = False

        if not dentro_do_pacote:

            fontes_fora_do_pacote.append(
                f"{camada.name()}: {fonte}"
            )

        # A camada reaberta resolve a URI para um caminho absoluto.
        # Para confirmar a serialização relativa, inspecionaremos também
        # o conteúdo interno do QGZ na função seguinte.

    if camadas_invalidas:

        raise Exception(
            "O projeto contém camadas inválidas:\n\n"
            + "\n".join(
                f"• {nome}"
                for nome in camadas_invalidas
            )
        )

    if fontes_fora_do_pacote:

        raise Exception(
            "Algumas camadas do projeto apontam para fora do pacote:\n\n"
            + "\n".join(
                f"• {item}"
                for item in fontes_fora_do_pacote
            )
        )

    registrar_log(
        caminho_log,
        (
            f"Projeto reaberto com sucesso. "
            f"Camadas válidas: {len(camadas)}."
        )
    )

    return {
        "camadas": len(camadas),
        "camadas_invalidas": 0,
        "fontes_fora_do_pacote": 0
    }


# =============================================================================
# 13. INSPEÇÃO DOS CAMINHOS DENTRO DO QGZ
# =============================================================================

def validar_serializacao_relativa_qgz(
    caminho_qgz,
    pasta_pacote
):
    """
    Inspeciona o XML interno do QGZ para confirmar que a fonte do
    GeoPackage não foi armazenada com o caminho absoluto do computador.

    O QGZ é um arquivo ZIP que contém o projeto QGS.
    """

    import zipfile

    if not zipfile.is_zipfile(
        caminho_qgz
    ):

        raise Exception(
            "O arquivo criado não possui uma estrutura QGZ válida."
        )

    with zipfile.ZipFile(
        caminho_qgz,
        "r"
    ) as arquivo_qgz:

        arquivos_qgs = [
            nome
            for nome in arquivo_qgz.namelist()
            if nome.lower().endswith(".qgs")
        ]

        if not arquivos_qgs:

            raise Exception(
                "O arquivo QGZ não contém um projeto QGS interno."
            )

        conteudo = arquivo_qgz.read(
            arquivos_qgs[0]
        ).decode(
            "utf-8",
            errors="replace"
        )

    caminho_absoluto_gpkg = os.path.join(
        pasta_pacote,
        "dados",
        "vetores",
        NOME_GEOPACKAGE
    )

    alternativas_absolutas = {
        caminho_absoluto_gpkg,
        caminho_absoluto_gpkg.replace("\\", "/"),
        caminho_absoluto_gpkg.replace("/", "\\")
    }

    for caminho_absoluto in alternativas_absolutas:

        if caminho_absoluto in conteudo:

            raise Exception(
                "O projeto foi gravado, mas o caminho absoluto "
                "do GeoPackage foi encontrado dentro do QGZ.\n\n"
                "A entrega não seria portátil."
            )

    referencias_relativas = [
        "dados/vetores/dados_entrega.gpkg",
        "dados\\vetores\\dados_entrega.gpkg",
        "./dados/vetores/dados_entrega.gpkg",
        ".\\dados\\vetores\\dados_entrega.gpkg"
    ]

    if not any(
        referencia in conteudo
        for referencia in referencias_relativas
    ):

        raise Exception(
            "Não foi possível confirmar no QGZ a referência relativa "
            "ao arquivo dados_entrega.gpkg."
        )

    return True


# =============================================================================
# 14. PROCESSAMENTO PRINCIPAL
# =============================================================================

try:

    print("")
    print("=" * 80)
    print("EMPACOTADOR DE DADOS PARA ENTREGA EXTERNA")
    print("ETAPA 04 - CRIAÇÃO DO PROJETO QGZ PORTÁTIL")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 14.1. CAMADAS SELECIONADAS
    # -------------------------------------------------------------------------

    camadas_selecionadas = (
        iface.layerTreeView().selectedLayers()
    )

    if not camadas_selecionadas:

        raise Exception(
            "Nenhuma camada foi selecionada.\n\n"
            "Selecione as mesmas camadas utilizadas na Etapa 3 "
            "e execute novamente."
        )

    # -------------------------------------------------------------------------
    # 14.2. JANELA
    # -------------------------------------------------------------------------

    janela = JanelaCriacaoProjeto(
        camadas_selecionadas,
        parent=iface.mainWindow()
    )

    if janela.exec_() != QDialog.Accepted:

        raise InterruptedError(
            "Operação cancelada pelo usuário."
        )

    configuracao = janela.obter_configuracao()

    pasta_pacote = configuracao[
        "pasta_pacote"
    ]

    caminho_qgz = configuracao[
        "caminho_qgz"
    ]

    # -------------------------------------------------------------------------
    # 14.3. LOCALIZAR ARQUIVOS
    # -------------------------------------------------------------------------

    arquivos_pacote = localizar_arquivos_pacote(
        pasta_pacote
    )

    caminho_inventario = arquivos_pacote[
        "inventario"
    ]

    caminho_gpkg = arquivos_pacote[
        "geopackage"
    ]

    caminho_log = os.path.join(
        arquivos_pacote["logs"],
        NOME_LOG
    )

    registrar_log(
        caminho_log,
        (
            "Início da criação do projeto QGZ. "
            f"Versão do script: {VERSAO_SCRIPT}"
        )
    )

    registrar_log(
        caminho_log,
        f"Pacote: {pasta_pacote}"
    )

    registrar_log(
        caminho_log,
        f"Projeto de saída: {caminho_qgz}"
    )

    # -------------------------------------------------------------------------
    # 14.4. LER INVENTÁRIO
    # -------------------------------------------------------------------------

    registros_inventario = ler_inventario(
        caminho_inventario
    )

    registrar_log(
        caminho_log,
        (
            f"Registros no inventário: "
            f"{len(registros_inventario)}"
        )
    )

    # -------------------------------------------------------------------------
    # 14.5. CAPTURAR A ÁRVORE ORIGINAL
    # -------------------------------------------------------------------------

    metadados_arvore = capturar_metadados_arvore(
        camadas_selecionadas
    )

    # -------------------------------------------------------------------------
    # 14.6. ASSOCIAR INVENTÁRIO
    # -------------------------------------------------------------------------

    associacoes = associar_inventario_as_camadas(
        metadados_arvore,
        registros_inventario
    )

    registrar_log(
        caminho_log,
        (
            f"Camadas associadas ao inventário: "
            f"{len(associacoes)}"
        )
    )

    # -------------------------------------------------------------------------
    # 14.7. CRIAR PROJETO
    # -------------------------------------------------------------------------

    resultado_criacao = criar_projeto_entrega(
        associacoes,
        pasta_pacote,
        caminho_gpkg,
        caminho_qgz,
        caminho_log
    )

    # Libera a instância de montagem antes da validação.
    projeto_montagem = resultado_criacao[
        "projeto"
    ]

    projeto_montagem.clear()

    del projeto_montagem

    # -------------------------------------------------------------------------
    # 14.8. VALIDAR PROJETO
    # -------------------------------------------------------------------------

    resultado_validacao = validar_projeto_qgz(
        caminho_qgz,
        pasta_pacote,
        len(associacoes),
        caminho_log
    )

    # -------------------------------------------------------------------------
    # 14.9. VALIDAR CAMINHOS RELATIVOS
    # -------------------------------------------------------------------------

    validar_serializacao_relativa_qgz(
        caminho_qgz,
        pasta_pacote
    )

    registrar_log(
        caminho_log,
        "Caminhos relativos confirmados no conteúdo do QGZ."
    )

    # -------------------------------------------------------------------------
    # 14.10. RESUMO
    # -------------------------------------------------------------------------

    grupos_utilizados = sorted({
        "/".join(associacao["grupos"])
        for associacao in associacoes
        if associacao["grupos"]
    })

    quantidade_com_grupo = sum(
        1
        for associacao in associacoes
        if associacao["grupos"]
    )

    quantidade_sem_grupo = (
        len(associacoes)
        - quantidade_com_grupo
    )

    estilos_sucesso = resultado_criacao[
        "estilos_sucesso"
    ]

    estilos_falha = resultado_criacao[
        "estilos_falha"
    ]

    print("")
    print("=" * 80)
    print("ETAPA 04 CONCLUÍDA")
    print("=" * 80)

    print(
        f"Projeto criado: {caminho_qgz}"
    )

    print(
        f"Camadas no projeto: "
        f"{resultado_validacao['camadas']}"
    )

    print(
        f"Camadas inválidas: "
        f"{resultado_validacao['camadas_invalidas']}"
    )

    print(
        f"Fontes fora do pacote: "
        f"{resultado_validacao['fontes_fora_do_pacote']}"
    )

    print(
        f"Estilos aplicados: "
        f"{estilos_sucesso}/{len(associacoes)}"
    )

    print(
        f"Falhas de estilo: {estilos_falha}"
    )

    print(
        f"Camadas em grupos: {quantidade_com_grupo}"
    )

    print(
        f"Camadas na raiz: {quantidade_sem_grupo}"
    )

    print(
        f"Grupos reproduzidos: {len(grupos_utilizados)}"
    )

    print(
        "Caminhos relativos: CONFIRMADOS"
    )

    print(
        "Projeto original alterado: NÃO"
    )

    print("=" * 80)

    # -------------------------------------------------------------------------
    # 14.11. LOG FINAL
    # -------------------------------------------------------------------------

    registrar_log(
        caminho_log,
        (
            "Projeto QGZ criado e validado. "
            f"Camadas: {len(associacoes)}; "
            f"estilos aplicados: {estilos_sucesso}; "
            f"falhas de estilo: {estilos_falha}; "
            f"grupos: {len(grupos_utilizados)}; "
            "fontes externas: 0; "
            "caminhos relativos: confirmados."
        )
    )

    QgsMessageLog.logMessage(
        (
            f"Etapa 04 concluída; "
            f"projeto: {caminho_qgz}; "
            f"camadas: {len(associacoes)}; "
            f"estilos: {estilos_sucesso}; "
            "caminhos relativos confirmados."
        ),
        "Empacotador de Entrega Externa",
        Qgis.Success
    )

    # -------------------------------------------------------------------------
    # 14.12. MENSAGEM FINAL
    # -------------------------------------------------------------------------

    mensagem_final = (
        "Projeto QGZ criado e validado com sucesso.\n\n"
        f"Projeto:\n{caminho_qgz}\n\n"
        f"Camadas incluídas: {len(associacoes)}\n"
        f"Camadas inválidas: 0\n"
        f"Fontes fora do pacote: 0\n"
        f"Estilos aplicados: "
        f"{estilos_sucesso}/{len(associacoes)}\n"
        f"Grupos reproduzidos: {len(grupos_utilizados)}\n"
        f"Camadas na raiz: {quantidade_sem_grupo}\n\n"
        "Caminhos relativos: confirmados\n"
        "Projeto original alterado: não\n\n"
        "O arquivo QGZ está na raiz da pasta de entrega e "
        "aponta exclusivamente para o GeoPackage interno.\n\n"
        "Recomenda-se abrir o QGZ criado e realizar uma conferência "
        "visual antes do envio externo."
    )

    if estilos_falha > 0:

        mensagem_final += (
            "\n\nAviso:\n"
            f"{estilos_falha} estilo(s) não pôde(ram) ser aplicado(s). "
            "Consulte o log da Etapa 4."
        )

    QMessageBox.information(
        iface.mainWindow(),
        "Projeto de entrega criado",
        mensagem_final
    )


# =============================================================================
# 15. CANCELAMENTO
# =============================================================================

except InterruptedError as erro_cancelamento:

    print("")
    print(str(erro_cancelamento))

    QgsMessageLog.logMessage(
        str(erro_cancelamento),
        "Empacotador de Entrega Externa",
        Qgis.Warning
    )


# =============================================================================
# 16. ERROS
# =============================================================================

except Exception as erro:

    print("")
    print("=" * 80)
    print("ERRO NA ETAPA 04 DO EMPACOTADOR")
    print("=" * 80)
    print(str(erro))
    print("=" * 80)

    # Remove somente o QGZ incompleto criado nesta execução.
    # O GeoPackage e os demais arquivos da Etapa 3 são preservados.

    try:

        if (
            "caminho_qgz" in locals()
            and os.path.isfile(caminho_qgz)
        ):

            os.remove(
                caminho_qgz
            )

            print(
                "O arquivo QGZ incompleto foi removido."
            )

    except Exception as erro_limpeza:

        print(
            "Não foi possível remover o QGZ incompleto: "
            f"{str(erro_limpeza)}"
        )

    try:

        if (
            "caminho_log" in locals()
            and caminho_log
        ):

            registrar_log(
                caminho_log,
                f"ERRO: {str(erro)}"
            )

    except Exception:

        pass

    QgsMessageLog.logMessage(
        str(erro),
        "Empacotador de Entrega Externa",
        Qgis.Critical
    )

    QMessageBox.critical(
        iface.mainWindow(),
        "Erro na criação do QGZ",
        (
            "Não foi possível concluir a criação do projeto "
            "de entrega.\n\n"
            f"Detalhes:\n{str(erro)}\n\n"
            "O GeoPackage, o inventário e os dados da Etapa 3 "
            "não foram modificados."
        )
    )