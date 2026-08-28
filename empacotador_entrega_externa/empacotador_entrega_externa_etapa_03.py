# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Empacotador de Dados para Entrega Externa
Etapa: 03 - Conversão para GeoPackage e Inventário Preliminar

Descrição:
    Terceira etapa do desenvolvimento do Empacotador de Dados para Entrega
    Externa.

    O script:

    1. Obtém as camadas vetoriais selecionadas no painel Camadas;
    2. Solicita o nome do pacote e a pasta de destino;
    3. Cria uma pasta de montagem temporária;
    4. Remove feições sem geometria somente da cópia;
    5. Preserva atributos, CRS, geometria e dimensão Z;
    6. Converte todas as camadas para um único GeoPackage;
    7. Cria nomes internos padronizados e únicos;
    8. Reabre e valida cada tabela gravada;
    9. Salva o estilo de cada camada em arquivo QML;
    10. Gera um inventário CSV;
    11. Publica a pasta somente após a validação das camadas.

    As camadas e os arquivos de origem nunca são modificados.

    Nesta etapa, o projeto QGZ ainda não é criado.

Autor: Eloízio Dantas
Data de Criação: 2026-08-28
Versão: 0.3.1

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x
    - Camadas de entrada: vetoriais e espaciais
    - Formato de saída: GeoPackage
    - Codificação: UTF-8

Premissas e Limitações:
    - As camadas devem possuir CRS válido.
    - Camadas sem geometria não são processadas nesta etapa.
    - Feições sem geometria são ignoradas somente na cópia de entrega.
    - Geometrias inválidas são preservadas e registradas.
    - Joins não são materializados nesta etapa.
    - Campos sensíveis ainda não são removidos.
    - O QGZ será criado em uma etapa posterior.
===============================================================================
"""


# =============================================================================
# 1. IMPORTAÇÕES
# =============================================================================

import csv
import os
import re
import shutil
import unicodedata

from datetime import datetime

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsMapLayerType,
    QgsMessageLog,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
    Qgis
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

VERSAO_SCRIPT = "0.3.1"

NOME_GEOPACKAGE = "dados_entrega.gpkg"
NOME_INVENTARIO = "inventario_camadas.csv"
NOME_LOG = "empacotamento_etapa_03.log"

MAXIMO_NOME_TABELA = 60


CAMPOS_INVENTARIO = [
    "ordem",
    "status",
    "nome_original",
    "nome_tabela_gpkg",
    "tipo_geometria",
    "possui_z",
    "possui_m",
    "crs",
    "crs_descricao",
    "provedor_origem",
    "fonte_origem",
    "quantidade_campos",
    "feicoes_origem",
    "feicoes_exportadas",
    "feicoes_vazias_ignoradas",
    "ids_vazios_origem",
    "geometrias_invalidas",
    "estilo_qml",
    "estilo_exportado",
    "acao_geometrias_vazias",
    "campos_renomeados",
    "chave_primaria_gpkg",
    "observacoes"
]


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


def normalizar_nome(nome, maiusculo=False, limite=60):
    """
    Cria um nome seguro para pasta, arquivo ou tabela.

    Exemplos:
        Área do Imóvel -> area_do_imovel
        2024-01-22 Reserva Legal -> reserva_legal
    """

    nome = remover_acentos(
        nome
    )

    # Remove uma data inicial no padrão AAAA-MM-DD
    nome = re.sub(
        r"^\s*\d{4}[-_]\d{2}[-_]\d{2}[-_\s]*",
        "",
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

        nome = "camada"

    if nome[0].isdigit():

        nome = "camada_" + nome

    if maiusculo:

        nome = nome.upper()

    else:

        nome = nome.lower()

    return nome[:limite].rstrip("_")


def normalizar_nome_pacote(nome):
    """
    Cria o nome-base do pacote em letras maiúsculas.
    """

    return normalizar_nome(
        nome,
        maiusculo=True,
        limite=70
    )


def obter_nome_base_projeto():
    """
    Obtém um nome sugerido a partir do projeto atual.
    """

    caminho_projeto = QgsProject.instance().fileName()

    if caminho_projeto:

        nome_arquivo = os.path.basename(
            caminho_projeto
        )

        nome_sem_extensao = os.path.splitext(
            nome_arquivo
        )[0]

        return normalizar_nome_pacote(
            nome_sem_extensao
        )

    return "PROJETO_QGIS"


def criar_nome_tabela_unico(
    nome_original,
    nomes_utilizados
):
    """
    Cria um nome único para uma tabela do GeoPackage.
    """

    nome_base = normalizar_nome(
        nome_original,
        maiusculo=False,
        limite=MAXIMO_NOME_TABELA
    )

    nome_candidato = nome_base
    contador = 2

    while nome_candidato.lower() in nomes_utilizados:

        sufixo = f"_{contador:02d}"

        tamanho_base = (
            MAXIMO_NOME_TABELA
            - len(sufixo)
        )

        nome_candidato = (
            nome_base[:tamanho_base].rstrip("_")
            + sufixo
        )

        contador += 1

    nomes_utilizados.add(
        nome_candidato.lower()
    )

    return nome_candidato


# =============================================================================
# 4. VERSIONAMENTO
# =============================================================================

def calcular_proxima_versao(
    pasta_destino,
    nome_base
):
    """
    Localiza a primeira versão disponível no destino.

    Exemplo:
        ENTREGA_ARCOS_CAR_20260828_v001
        ENTREGA_ARCOS_CAR_20260828_v002
    """

    data_execucao = datetime.now().strftime(
        "%Y%m%d"
    )

    contador = 1

    while True:

        versao = f"v{contador:03d}"

        nome_pasta = (
            f"ENTREGA_{nome_base}_"
            f"{data_execucao}_{versao}"
        )

        caminho_pasta = os.path.join(
            pasta_destino,
            nome_pasta
        )

        caminho_temporario = (
            caminho_pasta
            + "_EM_MONTAGEM"
        )

        if (
            not os.path.exists(caminho_pasta)
            and not os.path.exists(caminho_temporario)
        ):

            return {
                "versao": versao,
                "nome_pasta": nome_pasta,
                "caminho_final": caminho_pasta,
                "caminho_temporario": caminho_temporario
            }

        contador += 1


# =============================================================================
# 5. INTERFACE
# =============================================================================

class JanelaConversaoGeoPackage(QDialog):
    """
    Janela da Etapa 3.
    """

    def __init__(
        self,
        camadas,
        parent=None
    ):

        super().__init__(parent)

        self.camadas = camadas

        self.configurar_janela()
        self.criar_interface()


    def configurar_janela(self):
        """
        Configura a janela.
        """

        self.setWindowTitle(
            "Empacotador de Entrega Externa - Etapa 3"
        )

        self.setMinimumWidth(700)
        self.setMinimumHeight(590)

        self.setWindowModality(
            Qt.ApplicationModal
        )


    def criar_interface(self):
        """
        Cria os componentes da interface.
        """

        layout_principal = QVBoxLayout()

        self.setLayout(
            layout_principal
        )

        apresentacao = QLabel(
            "<b>Etapa 3:</b> conversão das camadas vetoriais "
            "para um único GeoPackage.<br><br>"
            "Feições sem geometria serão ignoradas somente na cópia. "
            "As fontes originais não serão modificadas."
        )

        apresentacao.setWordWrap(True)

        layout_principal.addWidget(
            apresentacao
        )

        # ---------------------------------------------------------------------
        # CAMADAS
        # ---------------------------------------------------------------------

        grupo_camadas = QGroupBox(
            "Camadas vetoriais selecionadas"
        )

        layout_camadas = QVBoxLayout()

        grupo_camadas.setLayout(
            layout_camadas
        )

        self.lista_camadas = QListWidget()

        for camada in self.camadas:

            crs = (
                camada.crs().authid()
                if camada.crs().isValid()
                else "CRS inválido"
            )

            tipo = QgsWkbTypes.displayString(
                camada.wkbType()
            )

            texto = (
                f"{camada.name()} | "
                f"{tipo} | "
                f"{crs} | "
                f"{camada.featureCount()} registro(s)"
            )

            item = QListWidgetItem(
                texto
            )

            item.setToolTip(
                camada.source()
            )

            self.lista_camadas.addItem(
                item
            )

        layout_camadas.addWidget(
            self.lista_camadas
        )

        resumo = QLabel(
            f"<b>Total:</b> {len(self.camadas)} camada(s)"
        )

        layout_camadas.addWidget(
            resumo
        )

        layout_principal.addWidget(
            grupo_camadas
        )

        # ---------------------------------------------------------------------
        # IDENTIFICAÇÃO
        # ---------------------------------------------------------------------

        grupo_identificacao = QGroupBox(
            "Identificação do pacote"
        )

        layout_identificacao = QVBoxLayout()

        grupo_identificacao.setLayout(
            layout_identificacao
        )

        layout_identificacao.addWidget(
            QLabel("Nome-base da entrega:")
        )

        self.campo_nome = QLineEdit()

        self.campo_nome.setText(
            obter_nome_base_projeto()
        )

        layout_identificacao.addWidget(
            self.campo_nome
        )

        layout_identificacao.addWidget(
            QLabel("Pasta de destino:")
        )

        layout_destino = QHBoxLayout()

        self.campo_destino = QLineEdit()

        self.campo_destino.setReadOnly(
            True
        )

        self.campo_destino.setPlaceholderText(
            "Selecione a pasta que receberá o pacote"
        )

        self.botao_destino = QPushButton(
            "Selecionar..."
        )

        self.botao_destino.clicked.connect(
            self.selecionar_destino
        )

        layout_destino.addWidget(
            self.campo_destino
        )

        layout_destino.addWidget(
            self.botao_destino
        )

        layout_identificacao.addLayout(
            layout_destino
        )

        layout_principal.addWidget(
            grupo_identificacao
        )

        # ---------------------------------------------------------------------
        # REGRAS
        # ---------------------------------------------------------------------

        grupo_regras = QGroupBox(
            "Regras fixas desta etapa"
        )

        layout_regras = QVBoxLayout()

        grupo_regras.setLayout(
            layout_regras
        )

        texto_regras = QLabel(
            "• Um único GeoPackage para todas as camadas<br>"
            "• CRS original preservado por tabela<br>"
            "• Dimensões Z e M preservadas<br>"
            "• Feições sem geometria ignoradas somente na cópia<br>"
            "• Geometrias inválidas preservadas e registradas<br>"
            "• Estilos exportados em QML<br>"
            "• Inventário CSV gerado automaticamente<br>"
            "• Nenhuma sobrescrita de pacote anterior"
        )

        texto_regras.setWordWrap(True)

        layout_regras.addWidget(
            texto_regras
        )

        layout_principal.addWidget(
            grupo_regras
        )

        aviso = QLabel(
            "<i>O projeto QGZ será criado em uma etapa posterior, "
            "depois da validação deste GeoPackage.</i>"
        )

        aviso.setWordWrap(True)

        layout_principal.addWidget(
            aviso
        )

        # ---------------------------------------------------------------------
        # BOTÕES
        # ---------------------------------------------------------------------

        self.caixa_botoes = QDialogButtonBox(
            QDialogButtonBox.Ok
            | QDialogButtonBox.Cancel
        )

        botao_ok = self.caixa_botoes.button(
            QDialogButtonBox.Ok
        )

        botao_ok.setText(
            "Criar GeoPackage"
        )

        self.caixa_botoes.accepted.connect(
            self.validar_e_aceitar
        )

        self.caixa_botoes.rejected.connect(
            self.reject
        )

        layout_principal.addWidget(
            self.caixa_botoes
        )


    def selecionar_destino(self):
        """
        Abre o seletor de pasta.
        """

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino",
            os.path.expanduser("~")
        )

        if pasta:

            self.campo_destino.setText(
                pasta
            )


    def validar_e_aceitar(self):
        """
        Valida o nome e o destino.
        """

        nome = self.campo_nome.text().strip()

        if not nome:

            QMessageBox.warning(
                self,
                "Nome não informado",
                "Informe o nome-base da entrega."
            )

            return

        destino = self.campo_destino.text().strip()

        if not destino:

            QMessageBox.warning(
                self,
                "Destino não informado",
                "Selecione a pasta de destino."
            )

            return

        if not os.path.isdir(destino):

            QMessageBox.warning(
                self,
                "Destino inválido",
                "A pasta de destino não existe."
            )

            return

        if not os.access(destino, os.W_OK):

            QMessageBox.warning(
                self,
                "Destino sem permissão",
                (
                    "A pasta de destino não permite gravação."
                )
            )

            return

        self.accept()


    def obter_configuracao(self):
        """
        Retorna as configurações.
        """

        return {
            "nome_base": normalizar_nome_pacote(
                self.campo_nome.text()
            ),
            "pasta_destino": (
                self.campo_destino.text().strip()
            )
        }


# =============================================================================
# 6. LOG
# =============================================================================

def registrar_log(
    caminho_log,
    mensagem
):
    """
    Grava uma linha no arquivo de log e no console.
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
# 7. CRIAÇÃO DA CAMADA FILTRADA
# =============================================================================

def criar_nome_campo_unico(
    nome_base,
    nomes_utilizados
):
    """
    Cria um nome de campo único, considerando maiúsculas
    e minúsculas como equivalentes.
    """

    nome_candidato = nome_base
    contador = 2

    while nome_candidato.lower() in nomes_utilizados:

        nome_candidato = (
            f"{nome_base}_{contador}"
        )

        contador += 1

    nomes_utilizados.add(
        nome_candidato.lower()
    )

    return nome_candidato


def preparar_campos_para_geopackage(
    camada_origem
):
    """
    Prepara os campos da camada para exportação ao GeoPackage.

    O nome 'fid' é reservado ou interpretado pelo driver como
    identificador interno da feição. Caso exista na camada original,
    ele será renomeado na cópia para 'fid_orig'.

    Outros campos permanecem com seus nomes originais, desde que não
    provoquem duplicidade depois da normalização.

    Retorno:
        lista_campos:
            Campos preparados para a camada temporária.

        mapeamento_campos:
            Lista com nome original, nome de saída e motivo da alteração.
    """

    lista_campos = []
    mapeamento_campos = []
    nomes_utilizados = set()

    for campo_original in camada_origem.fields():

        nome_original = campo_original.name()
        nome_normalizado = nome_original.lower().strip()

        # -----------------------------------------------------------------
        # TRATAR O CAMPO FID
        # -----------------------------------------------------------------

        if nome_normalizado == "fid":

            nome_saida = criar_nome_campo_unico(
                "fid_orig",
                nomes_utilizados
            )

            motivo = (
                "Campo 'fid' renomeado para evitar conflito "
                "com a chave primária do GeoPackage."
            )

        else:

            nome_saida = criar_nome_campo_unico(
                nome_original,
                nomes_utilizados
            )

            if nome_saida != nome_original:

                motivo = (
                    "Campo renomeado para evitar duplicidade."
                )

            else:

                motivo = ""

        # -----------------------------------------------------------------
        # COPIAR TODAS AS PROPRIEDADES DO CAMPO
        # -----------------------------------------------------------------

        campo_saida = QgsField(
            campo_original
        )

        campo_saida.setName(
            nome_saida
        )

        lista_campos.append(
            campo_saida
        )

        mapeamento_campos.append({
            "nome_original": nome_original,
            "nome_saida": nome_saida,
            "tipo_original": campo_original.typeName(),
            "motivo": motivo
        })

    return {
        "campos": lista_campos,
        "mapeamento": mapeamento_campos
    }


def criar_camada_sem_geometrias_vazias(
    camada_origem,
    nome_tabela
):
    """
    Cria uma camada temporária contendo somente feições com geometria.

    Também prepara os nomes dos campos para compatibilidade com
    GeoPackage. O campo 'fid', quando existente, é preservado com
    o nome 'fid_orig'.

    A camada original não é modificada.

    Retorno:
        camada;
        feições de origem;
        feições exportadas;
        feições vazias;
        IDs vazios;
        geometrias inválidas;
        campos renomeados.
    """

    # ---------------------------------------------------------------------
    # 1. OBTER O TIPO GEOMÉTRICO E O CRS
    # ---------------------------------------------------------------------

    tipo_wkb = QgsWkbTypes.displayString(
        camada_origem.wkbType()
    )

    crs_authid = camada_origem.crs().authid()

    uri = (
        f"{tipo_wkb}"
        f"?crs={crs_authid}"
    )

    # ---------------------------------------------------------------------
    # 2. CRIAR A CAMADA TEMPORÁRIA
    # ---------------------------------------------------------------------

    camada_saida = QgsVectorLayer(
        uri,
        nome_tabela,
        "memory"
    )

    if not camada_saida.isValid():

        raise Exception(
            "Não foi possível criar a camada temporária "
            f"para '{camada_origem.name()}'."
        )

    provedor_saida = (
        camada_saida.dataProvider()
    )

    # ---------------------------------------------------------------------
    # 3. PREPARAR OS CAMPOS
    # ---------------------------------------------------------------------

    resultado_campos = preparar_campos_para_geopackage(
        camada_origem
    )

    campos_preparados = resultado_campos[
        "campos"
    ]

    mapeamento_campos = resultado_campos[
        "mapeamento"
    ]

    if campos_preparados:

        if not provedor_saida.addAttributes(
            campos_preparados
        ):

            raise Exception(
                "Não foi possível copiar os campos da camada "
                f"'{camada_origem.name()}'."
            )

    camada_saida.updateFields()

    # ---------------------------------------------------------------------
    # 4. REGISTRAR CAMPOS RENOMEADOS
    # ---------------------------------------------------------------------

    campos_renomeados = []

    for mapeamento in mapeamento_campos:

        if (
            mapeamento["nome_original"]
            != mapeamento["nome_saida"]
        ):

            campos_renomeados.append(
                (
                    f"{mapeamento['nome_original']} -> "
                    f"{mapeamento['nome_saida']}"
                )
            )

            print(
                "Campo ajustado para GeoPackage: "
                f"{mapeamento['nome_original']} -> "
                f"{mapeamento['nome_saida']}"
            )

    # ---------------------------------------------------------------------
    # 5. ANALISAR E COPIAR AS FEIÇÕES
    # ---------------------------------------------------------------------

    feicoes_saida = []

    quantidade_origem = 0
    quantidade_exportada = 0
    quantidade_vazia = 0
    quantidade_invalida = 0

    ids_vazios = []

    for feicao_origem in camada_origem.getFeatures():

        quantidade_origem += 1

        geometria = feicao_origem.geometry()

        # -----------------------------------------------------------------
        # IGNORAR FEIÇÕES SEM GEOMETRIA
        # -----------------------------------------------------------------

        if (
            geometria is None
            or geometria.isNull()
            or geometria.isEmpty()
        ):

            quantidade_vazia += 1

            ids_vazios.append(
                str(feicao_origem.id())
            )

            continue

        # -----------------------------------------------------------------
        # REGISTRAR GEOMETRIAS INVÁLIDAS
        # -----------------------------------------------------------------

        try:

            if not geometria.isGeosValid():

                quantidade_invalida += 1

        except Exception:

            pass

        # -----------------------------------------------------------------
        # CRIAR A FEIÇÃO DE SAÍDA
        # -----------------------------------------------------------------
        #
        # Como apenas o nome do campo foi alterado, a ordem dos atributos
        # permanece exatamente a mesma da camada original.
        # -----------------------------------------------------------------

        feicao_saida = QgsFeature(
            camada_saida.fields()
        )

        feicao_saida.setGeometry(
            geometria
        )

        feicao_saida.setAttributes(
            list(feicao_origem.attributes())
        )

        feicoes_saida.append(
            feicao_saida
        )

        quantidade_exportada += 1

    # ---------------------------------------------------------------------
    # 6. VALIDAR SE EXISTEM FEIÇÕES EXPORTÁVEIS
    # ---------------------------------------------------------------------

    if quantidade_exportada == 0:

        raise Exception(
            f"A camada '{camada_origem.name()}' não possui "
            "nenhuma feição com geometria para exportação."
        )

    # ---------------------------------------------------------------------
    # 7. ADICIONAR AS FEIÇÕES À CAMADA TEMPORÁRIA
    # ---------------------------------------------------------------------

    if not provedor_saida.addFeatures(
        feicoes_saida
    ):

        raise Exception(
            "Não foi possível adicionar as feições filtradas "
            f"da camada '{camada_origem.name()}'."
        )

    camada_saida.updateExtents()

    # ---------------------------------------------------------------------
    # 8. RETORNAR RESULTADOS E AUDITORIA
    # ---------------------------------------------------------------------

    return {
        "camada": camada_saida,
        "feicoes_origem": quantidade_origem,
        "feicoes_exportadas": quantidade_exportada,
        "feicoes_vazias": quantidade_vazia,
        "ids_vazios": ids_vazios,
        "geometrias_invalidas": quantidade_invalida,
        "campos_renomeados": campos_renomeados,
        "mapeamento_campos": mapeamento_campos
    }

# =============================================================================
# 8. GRAVAÇÃO NO GEOPACKAGE
# =============================================================================

def gravar_camada_geopackage(
    camada,
    caminho_gpkg,
    nome_tabela,
    primeira_camada
):
    """
    Grava uma camada no GeoPackage.

    A primeira camada cria o arquivo.
    As camadas seguintes criam ou substituem somente a respectiva tabela.
    """

    opcoes = QgsVectorFileWriter.SaveVectorOptions()

    opcoes.driverName = "GPKG"
    opcoes.fileEncoding = "UTF-8"
    opcoes.layerName = nome_tabela

    # O GeoPackage utilizará uma chave primária própria.
    # Isso evita conflito com atributos provenientes da fonte.

    opcoes.layerOptions = [
    "FID=gpkg_fid"
    ]

    if primeira_camada:

        opcoes.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile
        )

    else:

        opcoes.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteLayer
        )

    resultado = QgsVectorFileWriter.writeAsVectorFormatV3(
        camada,
        caminho_gpkg,
        QgsProject.instance().transformContext(),
        opcoes
    )

    codigo_erro = resultado[0]

    mensagem_erro = ""

    if len(resultado) > 1:

        mensagem_erro = str(
            resultado[1]
        )

    if codigo_erro != QgsVectorFileWriter.NoError:

        raise Exception(
            f"Falha ao gravar a tabela '{nome_tabela}'.\n\n"
            f"Detalhes: {mensagem_erro}"
        )


def validar_tabela_gravada(
    caminho_gpkg,
    nome_tabela,
    quantidade_esperada,
    crs_esperado
):
    """
    Reabre uma tabela do GeoPackage e valida a contagem e o CRS.
    """

    uri = (
        f"{caminho_gpkg}"
        f"|layername={nome_tabela}"
    )

    camada_validacao = QgsVectorLayer(
        uri,
        nome_tabela,
        "ogr"
    )

    if not camada_validacao.isValid():

        raise Exception(
            f"A tabela '{nome_tabela}' foi gravada, "
            "mas não pôde ser reaberta."
        )

    quantidade_encontrada = (
        camada_validacao.featureCount()
    )

    if quantidade_encontrada != quantidade_esperada:

        raise Exception(
            f"Contagem divergente na tabela '{nome_tabela}'.\n\n"
            f"Esperado: {quantidade_esperada}\n"
            f"Encontrado: {quantidade_encontrada}"
        )

    crs_encontrado = (
        camada_validacao.crs().authid()
    )

    if (
        crs_esperado
        and crs_encontrado
        and crs_encontrado != crs_esperado
    ):

        raise Exception(
            f"CRS divergente na tabela '{nome_tabela}'.\n\n"
            f"Esperado: {crs_esperado}\n"
            f"Encontrado: {crs_encontrado}"
        )

    return camada_validacao


# =============================================================================
# 9. EXPORTAÇÃO DO ESTILO
# =============================================================================

def exportar_estilo_qml(
    camada_origem,
    pasta_estilos,
    nome_tabela
):
    """
    Salva o estilo da camada em arquivo QML.

    Retorno:
        caminho relativo;
        sucesso;
        observação.
    """

    nome_arquivo = (
        nome_tabela + ".qml"
    )

    caminho_qml = os.path.join(
        pasta_estilos,
        nome_arquivo
    )

    try:

        resultado = camada_origem.saveNamedStyle(
            caminho_qml
        )

        # Algumas versões retornam uma tupla.
        # Outras podem retornar apenas uma string de mensagem.

        mensagem = ""

        sucesso = os.path.exists(
            caminho_qml
        )

        if isinstance(resultado, tuple):

            if len(resultado) > 0:

                mensagem = str(
                    resultado[0]
                )

            if len(resultado) > 1:

                try:

                    sucesso = bool(
                        resultado[1]
                    ) and sucesso

                except Exception:

                    pass

        elif resultado:

            mensagem = str(
                resultado
            )

        caminho_relativo = os.path.join(
            "estilos",
            nome_arquivo
        ).replace("\\", "/")

        return {
            "caminho_relativo": caminho_relativo,
            "sucesso": sucesso,
            "observacao": mensagem
        }

    except Exception as erro:

        return {
            "caminho_relativo": "",
            "sucesso": False,
            "observacao": str(erro)
        }


# =============================================================================
# 10. INVENTÁRIO
# =============================================================================

def escrever_inventario(
    caminho_inventario,
    registros
):
    """
    Gera o inventário CSV usando UTF-8 com BOM e ponto e vírgula.

    O BOM facilita a abertura correta no Excel.
    O ponto e vírgula é adequado ao padrão regional brasileiro.
    """

    with open(
        caminho_inventario,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as arquivo:

        escritor = csv.DictWriter(
            arquivo,
            fieldnames=CAMPOS_INVENTARIO,
            delimiter=";",
            extrasaction="ignore"
        )

        escritor.writeheader()

        for registro in registros:

            escritor.writerow(
                registro
            )


# =============================================================================
# 11. VALIDAÇÕES INICIAIS
# =============================================================================

def validar_camadas_selecionadas(
    camadas
):
    """
    Valida se todas as camadas são vetoriais, espaciais e possuem CRS.
    """

    problemas = []

    for camada in camadas:

        if camada.type() != QgsMapLayerType.VectorLayer:

            problemas.append(
                f"{camada.name()}: não é uma camada vetorial."
            )

            continue

        if not camada.isSpatial():

            problemas.append(
                f"{camada.name()}: tabela sem geometria."
            )

        if not camada.isValid():

            problemas.append(
                f"{camada.name()}: camada inválida."
            )

        if not camada.crs().isValid():

            problemas.append(
                f"{camada.name()}: CRS ausente ou inválido."
            )

        try:

            if len(camada.vectorJoins()) > 0:

                problemas.append(
                    f"{camada.name()}: possui join ativo."
                )

        except Exception:

            pass

        if camada.isEditable():

            problemas.append(
                f"{camada.name()}: está em modo de edição."
            )

    return problemas


# =============================================================================
# 12. PROCESSAMENTO PRINCIPAL
# =============================================================================

try:

    print("")
    print("=" * 80)
    print("EMPACOTADOR DE DADOS PARA ENTREGA EXTERNA")
    print("ETAPA 03 - CONVERSÃO PARA GEOPACKAGE")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # 12.1. CAMADAS SELECIONADAS
    # -------------------------------------------------------------------------

    camadas_selecionadas = (
        iface.layerTreeView().selectedLayers()
    )

    if not camadas_selecionadas:

        raise Exception(
            "Nenhuma camada foi selecionada.\n\n"
            "Selecione as camadas vetoriais no painel Camadas "
            "e execute novamente."
        )

    # -------------------------------------------------------------------------
    # 12.2. VALIDAÇÃO INICIAL
    # -------------------------------------------------------------------------

    problemas = validar_camadas_selecionadas(
        camadas_selecionadas
    )

    if problemas:

        texto_problemas = "\n".join(
            f"• {problema}"
            for problema in problemas[:15]
        )

        if len(problemas) > 15:

            texto_problemas += (
                f"\n• ... e mais "
                f"{len(problemas) - 15} ocorrência(s)."
            )

        raise Exception(
            "As camadas selecionadas apresentam ocorrências "
            "que impedem esta etapa:\n\n"
            f"{texto_problemas}\n\n"
            "Salve as edições, remova joins ou ajuste a seleção "
            "antes de continuar."
        )

    # -------------------------------------------------------------------------
    # 12.3. JANELA DE CONFIGURAÇÃO
    # -------------------------------------------------------------------------

    janela = JanelaConversaoGeoPackage(
        camadas=camadas_selecionadas,
        parent=iface.mainWindow()
    )

    if janela.exec_() != QDialog.Accepted:

        raise InterruptedError(
            "Operação cancelada pelo usuário."
        )

    configuracao = janela.obter_configuracao()

    nome_base = configuracao["nome_base"]
    pasta_destino = configuracao["pasta_destino"]

    # -------------------------------------------------------------------------
    # 12.4. VERSIONAMENTO
    # -------------------------------------------------------------------------

    versionamento = calcular_proxima_versao(
        pasta_destino,
        nome_base
    )

    caminho_final = (
        versionamento["caminho_final"]
    )

    caminho_temporario = (
        versionamento["caminho_temporario"]
    )

    # -------------------------------------------------------------------------
    # 12.5. CONTAR FEIÇÕES VAZIAS PARA AVISO
    # -------------------------------------------------------------------------

    total_vazias_preliminar = 0

    for camada in camadas_selecionadas:

        for feicao in camada.getFeatures():

            geometria = feicao.geometry()

            if (
                geometria is None
                or geometria.isNull()
                or geometria.isEmpty()
            ):

                total_vazias_preliminar += 1

    if total_vazias_preliminar > 0:

        resposta = QMessageBox.question(
            iface.mainWindow(),
            "Feições sem geometria",
            (
                f"Foram localizadas {total_vazias_preliminar} "
                "feições sem geometria.\n\n"
                "Essas feições não serão incluídas no GeoPackage "
                "de entrega.\n\n"
                "As fontes originais não serão modificadas e as "
                "ocorrências serão registradas no inventário.\n\n"
                "Deseja continuar?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if resposta != QMessageBox.Yes:

            raise InterruptedError(
                "Empacotamento cancelado pelo usuário."
            )

    # -------------------------------------------------------------------------
    # 12.6. CRIAR ESTRUTURA TEMPORÁRIA
    # -------------------------------------------------------------------------

    os.makedirs(
        caminho_temporario
    )

    pasta_dados = os.path.join(
        caminho_temporario,
        "dados"
    )

    pasta_vetores = os.path.join(
        pasta_dados,
        "vetores"
    )

    pasta_estilos = os.path.join(
        caminho_temporario,
        "estilos"
    )

    pasta_logs = os.path.join(
        caminho_temporario,
        "logs"
    )

    os.makedirs(
        pasta_vetores
    )

    os.makedirs(
        pasta_estilos
    )

    os.makedirs(
        pasta_logs
    )

    caminho_gpkg = os.path.join(
        pasta_vetores,
        NOME_GEOPACKAGE
    )

    caminho_inventario = os.path.join(
        caminho_temporario,
        NOME_INVENTARIO
    )

    caminho_log = os.path.join(
        pasta_logs,
        NOME_LOG
    )

    registrar_log(
        caminho_log,
        (
            "Início do empacotamento. "
            f"Versão do script: {VERSAO_SCRIPT}"
        )
    )

    registrar_log(
        caminho_log,
        f"Pacote: {versionamento['nome_pasta']}"
    )

    registrar_log(
        caminho_log,
        (
            f"Camadas selecionadas: "
            f"{len(camadas_selecionadas)}"
        )
    )

    # -------------------------------------------------------------------------
    # 12.7. EXPORTAR CAMADAS
    # -------------------------------------------------------------------------

    nomes_utilizados = set()
    inventario = []

    primeira_camada = True

    total_feicoes_origem = 0
    total_feicoes_exportadas = 0
    total_feicoes_vazias = 0
    total_geometrias_invalidas = 0
    total_estilos_exportados = 0

    for ordem, camada_origem in enumerate(
        camadas_selecionadas,
        start=1
    ):

        registrar_log(
            caminho_log,
            (
                f"Processando {ordem}/"
                f"{len(camadas_selecionadas)}: "
                f"{camada_origem.name()}"
            )
        )

        nome_tabela = criar_nome_tabela_unico(
            camada_origem.name(),
            nomes_utilizados
        )

        observacoes = []

        resultado_filtragem = (
            criar_camada_sem_geometrias_vazias(
                camada_origem,
                nome_tabela
            )
        )

        camada_exportacao = (
            resultado_filtragem["camada"]
        )

        # ---------------------------------------------------------------------
        # GRAVAR
        # ---------------------------------------------------------------------

        gravar_camada_geopackage(
            camada_exportacao,
            caminho_gpkg,
            nome_tabela,
            primeira_camada
        )

        primeira_camada = False

        # ---------------------------------------------------------------------
        # VALIDAR
        # ---------------------------------------------------------------------

        camada_validada = validar_tabela_gravada(
            caminho_gpkg,
            nome_tabela,
            resultado_filtragem[
                "feicoes_exportadas"
            ],
            camada_origem.crs().authid()
        )

        # ---------------------------------------------------------------------
        # ESTILO
        # ---------------------------------------------------------------------

        resultado_estilo = exportar_estilo_qml(
            camada_origem,
            pasta_estilos,
            nome_tabela
        )

        if resultado_estilo["sucesso"]:

            total_estilos_exportados += 1

        else:

            observacoes.append(
                "O estilo QML não pôde ser exportado."
            )

        # ---------------------------------------------------------------------
        # STATUS
        # ---------------------------------------------------------------------

        if (
            resultado_filtragem["feicoes_vazias"] > 0
            or resultado_filtragem[
                "geometrias_invalidas"
            ] > 0
            or resultado_filtragem[
                "campos_renomeados"
            ]
            or not resultado_estilo["sucesso"]
        ):

            status = "SUCESSO_COM_AVISO"

        else:

            status = "SUCESSO"

        if resultado_filtragem["feicoes_vazias"] > 0:

            observacoes.append(
                (
                    f"{resultado_filtragem['feicoes_vazias']} "
                    "feição(ões) sem geometria não foi(ram) "
                    "incluída(s) na cópia."
                )
            )

        if resultado_filtragem["geometrias_invalidas"] > 0:

            observacoes.append(
                (
                    f"{resultado_filtragem['geometrias_invalidas']} "
                    "geometria(s) inválida(s) foi(ram) preservada(s)."
                )
            )
        
        if resultado_filtragem["campos_renomeados"]:
            
            observacoes.append(
                (
                    "Campos renomeados para compatibilidade: "
                    + ", ".join(
                        resultado_filtragem[
                            "campos_renomeados"
                            ]
                    )
                    + "."
                )
            )

        try:

            possui_z = QgsWkbTypes.hasZ(
                camada_origem.wkbType()
            )

        except Exception:

            possui_z = False

        try:

            possui_m = QgsWkbTypes.hasM(
                camada_origem.wkbType()
            )

        except Exception:

            possui_m = False

        registro = {
            "ordem": ordem,
            "status": status,
            "nome_original": camada_origem.name(),
            "nome_tabela_gpkg": nome_tabela,
            "tipo_geometria": (
                QgsWkbTypes.displayString(
                    camada_origem.wkbType()
                )
            ),
            "possui_z": "SIM" if possui_z else "NAO",
            "possui_m": "SIM" if possui_m else "NAO",
            "crs": camada_origem.crs().authid(),
            "crs_descricao": (
                camada_origem.crs().description()
            ),
            "provedor_origem": (
                camada_origem.providerType()
            ),
            "fonte_origem": camada_origem.source(),
            "quantidade_campos": (
                len(camada_origem.fields())
            ),
            "feicoes_origem": (
                resultado_filtragem[
                    "feicoes_origem"
                ]
            ),
            "feicoes_exportadas": (
                resultado_filtragem[
                    "feicoes_exportadas"
                ]
            ),
            "feicoes_vazias_ignoradas": (
                resultado_filtragem[
                    "feicoes_vazias"
                ]
            ),
            "ids_vazios_origem": ",".join(
                resultado_filtragem[
                    "ids_vazios"
                ]
            ),
            "geometrias_invalidas": (
                resultado_filtragem[
                    "geometrias_invalidas"
                ]
            ),
            "estilo_qml": (
                resultado_estilo[
                    "caminho_relativo"
                ]
            ),
            "estilo_exportado": (
                "SIM"
                if resultado_estilo["sucesso"]
                else "NAO"
            ),
            "acao_geometrias_vazias": (
                "IGNORADAS_NA_COPIA"
                if resultado_filtragem[
                    "feicoes_vazias"
                ] > 0
                else "NAO_APLICAVEL"
            ),
            "campos_renomeados": "; ".join(
                resultado_filtragem[
                    "campos_renomeados"
                    ]
            ),
            "chave_primaria_gpkg": "gpkg_fid",
            "observacoes": " ".join(
                observacoes
            )
        }

        inventario.append(
            registro
        )

        total_feicoes_origem += (
            resultado_filtragem[
                "feicoes_origem"
            ]
        )

        total_feicoes_exportadas += (
            resultado_filtragem[
                "feicoes_exportadas"
            ]
        )

        total_feicoes_vazias += (
            resultado_filtragem[
                "feicoes_vazias"
            ]
        )

        total_geometrias_invalidas += (
            resultado_filtragem[
                "geometrias_invalidas"
            ]
        )

        registrar_log(
            caminho_log,
            (
                f"Tabela '{nome_tabela}' validada. "
                f"Origem: "
                f"{resultado_filtragem['feicoes_origem']}; "
                f"exportadas: "
                f"{resultado_filtragem['feicoes_exportadas']}; "
                f"vazias ignoradas: "
                f"{resultado_filtragem['feicoes_vazias']}."
            )
        )

        del camada_validada
        del camada_exportacao

    # -------------------------------------------------------------------------
    # 12.8. INVENTÁRIO
    # -------------------------------------------------------------------------

    escrever_inventario(
        caminho_inventario,
        inventario
    )

    if not os.path.exists(
        caminho_inventario
    ):

        raise Exception(
            "O inventário não foi criado."
        )

    if os.path.getsize(
        caminho_inventario
    ) == 0:

        raise Exception(
            "O inventário foi criado, mas está vazio."
        )

    # -------------------------------------------------------------------------
    # 12.9. VALIDAÇÕES FINAIS
    # -------------------------------------------------------------------------

    if not os.path.exists(
        caminho_gpkg
    ):

        raise Exception(
            "O GeoPackage não foi localizado após a exportação."
        )

    if os.path.getsize(
        caminho_gpkg
    ) == 0:

        raise Exception(
            "O GeoPackage foi criado, mas possui tamanho zero."
        )

    if len(inventario) != len(
        camadas_selecionadas
    ):

        raise Exception(
            "A quantidade de tabelas inventariadas não corresponde "
            "à quantidade de camadas selecionadas."
        )

    registrar_log(
        caminho_log,
        (
            "Conversão concluída. "
            f"Camadas: {len(inventario)}; "
            f"feições de origem: {total_feicoes_origem}; "
            f"feições exportadas: {total_feicoes_exportadas}; "
            f"vazias ignoradas: {total_feicoes_vazias}; "
            f"inválidas preservadas: "
            f"{total_geometrias_invalidas}; "
            f"estilos exportados: "
            f"{total_estilos_exportados}."
        )
    )

    # -------------------------------------------------------------------------
    # 12.10. PUBLICAÇÃO ATÔMICA
    # -------------------------------------------------------------------------

    os.rename(
        caminho_temporario,
        caminho_final
    )

    caminho_gpkg_final = os.path.join(
        caminho_final,
        "dados",
        "vetores",
        NOME_GEOPACKAGE
    )

    caminho_inventario_final = os.path.join(
        caminho_final,
        NOME_INVENTARIO
    )

    # -------------------------------------------------------------------------
    # 12.11. CONSOLE
    # -------------------------------------------------------------------------

    print("")
    print("=" * 80)
    print("ETAPA 03 CONCLUÍDA")
    print("=" * 80)

    print(
        f"Pacote: {caminho_final}"
    )

    print(
        f"GeoPackage: {caminho_gpkg_final}"
    )

    print(
        f"Inventário: {caminho_inventario_final}"
    )

    print(
        f"Camadas exportadas: {len(inventario)}"
    )

    print(
        f"Feições de origem: {total_feicoes_origem}"
    )

    print(
        f"Feições exportadas: {total_feicoes_exportadas}"
    )

    print(
        f"Feições vazias ignoradas: {total_feicoes_vazias}"
    )

    print(
        "Geometrias inválidas preservadas: "
        f"{total_geometrias_invalidas}"
    )

    print(
        f"Estilos exportados: "
        f"{total_estilos_exportados}/"
        f"{len(inventario)}"
    )

    print("=" * 80)

    # -------------------------------------------------------------------------
    # 12.12. MENSAGEM FINAL
    # -------------------------------------------------------------------------

    mensagem_final = (
        "GeoPackage de entrega criado e validado.\n\n"
        f"Pacote:\n{caminho_final}\n\n"
        f"Camadas exportadas: {len(inventario)}\n"
        f"Feições de origem: {total_feicoes_origem}\n"
        f"Feições exportadas: {total_feicoes_exportadas}\n"
        f"Feições vazias ignoradas: {total_feicoes_vazias}\n"
        "Geometrias inválidas preservadas: "
        f"{total_geometrias_invalidas}\n"
        f"Estilos exportados: "
        f"{total_estilos_exportados}/{len(inventario)}\n\n"
        "Arquivos criados:\n"
        f"• dados/vetores/{NOME_GEOPACKAGE}\n"
        f"• {NOME_INVENTARIO}\n"
        f"• estilos/*.qml\n"
        f"• logs/{NOME_LOG}\n\n"
        "As camadas originais não foram modificadas.\n\n"
        "O projeto QGZ ainda não foi criado nesta etapa."
    )

    QMessageBox.information(
        iface.mainWindow(),
        "Conversão concluída",
        mensagem_final
    )

    QgsMessageLog.logMessage(
        (
            f"Etapa 03 concluída; "
            f"pacote: {caminho_final}; "
            f"camadas: {len(inventario)}; "
            f"feições exportadas: "
            f"{total_feicoes_exportadas}; "
            f"vazias ignoradas: "
            f"{total_feicoes_vazias}."
        ),
        "Empacotador de Entrega Externa",
        Qgis.Success
    )


# =============================================================================
# 13. CANCELAMENTO
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
# 14. ERROS
# =============================================================================

except Exception as erro:

    print("")
    print("=" * 80)
    print("ERRO NA ETAPA 03 DO EMPACOTADOR")
    print("=" * 80)
    print(str(erro))
    print("=" * 80)

    # Remove somente a pasta temporária incompleta.
    # Uma pasta final validada nunca é removida.

    try:

        if (
            "caminho_temporario" in locals()
            and os.path.isdir(caminho_temporario)
        ):

            shutil.rmtree(
                caminho_temporario
            )

            print(
                "A pasta temporária incompleta foi removida."
            )

    except Exception as erro_limpeza:

        print(
            "Não foi possível remover a pasta temporária: "
            f"{str(erro_limpeza)}"
        )

    QgsMessageLog.logMessage(
        str(erro),
        "Empacotador de Entrega Externa",
        Qgis.Critical
    )

    QMessageBox.critical(
        iface.mainWindow(),
        "Erro na conversão",
        (
            "Não foi possível concluir a criação do GeoPackage.\n\n"
            f"Detalhes:\n{str(erro)}\n\n"
            "As camadas originais não foram modificadas."
        )
    )