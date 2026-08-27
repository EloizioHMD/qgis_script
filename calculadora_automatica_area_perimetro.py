# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Calculadora Automática de Área e Perímetro

Descrição:
    Script independente para QGIS que calcula área e perímetro de uma camada
    vetorial poligonal ativa.

    O usuário pode escolher:

    1. Criar um novo arquivo GeoPackage, preservando a camada original;
    2. Modificar diretamente a camada ativa.

    Também é possível escolher:

    - área em metros quadrados;
    - área em hectares;
    - área em quilômetros quadrados;
    - perímetro em metros;
    - perímetro em quilômetros;
    - todas as feições;
    - somente as feições selecionadas.

    As medições são realizadas com QgsDistanceArea, utilizando:

    - CRS declarado na camada;
    - contexto de transformação do projeto;
    - medição elipsoidal;
    - elipsoide GRS80.

    Este script não depende do Seletor Automático de UTM e não identifica
    ou configura fusos UTM.

Autor: Eloízio Dantas
Data de Criação: 2026-08-27
Versão: 1.1.0

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x
    - Entrada: Polígono ou Multipolígono
    - Saída segura: GeoPackage
    - Método: medição elipsoidal
    - Elipsoide: GRS80

Premissas e Limitações:
    - O CRS da camada deve estar corretamente definido.
    - A ferramenta não corrige geometrias inválidas.
    - A precisão decimal não representa a acurácia espacial da fonte.
    - A soma dos perímetros individuais não equivale necessariamente ao
      perímetro externo de uma geometria dissolvida.
===============================================================================
"""


# =============================================================================
# 1. IMPORTAÇÕES
# =============================================================================

import os
import re

from qgis.core import (
    QgsDistanceArea,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsMapLayerType,
    QgsMessageLog,
    QgsProject,
    QgsUnitTypes,
    QgsVectorDataProvider,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
    Qgis
)

from qgis.PyQt.QtCore import (
    Qt,
    QVariant
)

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QMessageBox,
    QRadioButton,
    QVBoxLayout
)

from qgis.utils import iface


# =============================================================================
# 2. CONFIGURAÇÕES FIXAS
# =============================================================================

PRECISOES = {
    "area_m2": 3,
    "area_ha": 4,
    "area_km2": 3,
    "perim_m": 0,
    "perim_km": 3
}


ROTULOS = {
    "area_m2": "Área em metros quadrados",
    "area_ha": "Área em hectares",
    "area_km2": "Área em quilômetros quadrados",
    "perim_m": "Perímetro em metros",
    "perim_km": "Perímetro em quilômetros"
}


ORDEM_CAMPOS = [
    "area_m2",
    "area_ha",
    "area_km2",
    "perim_m",
    "perim_km"
]


# =============================================================================
# 3. JANELA DE CONFIGURAÇÃO
# =============================================================================

class JanelaConfiguracao(QDialog):
    """
    Popup para selecionar unidades, feições e modo de saída.
    """

    def __init__(
        self,
        nome_camada,
        quantidade_selecionada,
        parent=None
    ):

        super().__init__(parent)

        self.nome_camada = nome_camada
        self.quantidade_selecionada = quantidade_selecionada

        self.configurar_janela()
        self.criar_interface()


    # -------------------------------------------------------------------------
    # 3.1. CONFIGURAR A JANELA
    # -------------------------------------------------------------------------

    def configurar_janela(self):

        self.setWindowTitle(
            "Calculadora de Área e Perímetro"
        )

        self.setMinimumWidth(540)

        self.setWindowModality(
            Qt.ApplicationModal
        )


    # -------------------------------------------------------------------------
    # 3.2. CRIAR A INTERFACE
    # -------------------------------------------------------------------------

    def criar_interface(self):

        layout_principal = QVBoxLayout()

        self.setLayout(
            layout_principal
        )

        # ---------------------------------------------------------------------
        # APRESENTAÇÃO
        # ---------------------------------------------------------------------

        texto_apresentacao = QLabel(
            f"<b>Camada ativa:</b> {self.nome_camada}<br><br>"
            "Selecione as unidades, o conjunto de feições e "
            "o modo de saída."
        )

        texto_apresentacao.setWordWrap(True)

        layout_principal.addWidget(
            texto_apresentacao
        )

        # ---------------------------------------------------------------------
        # UNIDADES DE ÁREA
        # ---------------------------------------------------------------------

        grupo_area = QGroupBox(
            "Unidades de área"
        )

        layout_area = QVBoxLayout()

        grupo_area.setLayout(
            layout_area
        )

        self.check_area_m2 = QCheckBox(
            "Metros quadrados, m²"
        )

        self.check_area_ha = QCheckBox(
            "Hectares, ha"
        )

        self.check_area_km2 = QCheckBox(
            "Quilômetros quadrados, km²"
        )

        self.check_area_ha.setChecked(True)

        layout_area.addWidget(
            self.check_area_m2
        )

        layout_area.addWidget(
            self.check_area_ha
        )

        layout_area.addWidget(
            self.check_area_km2
        )

        layout_principal.addWidget(
            grupo_area
        )

        # ---------------------------------------------------------------------
        # UNIDADES DE PERÍMETRO
        # ---------------------------------------------------------------------

        grupo_perimetro = QGroupBox(
            "Unidades de perímetro"
        )

        layout_perimetro = QVBoxLayout()

        grupo_perimetro.setLayout(
            layout_perimetro
        )

        self.check_perim_m = QCheckBox(
            "Metros, m"
        )

        self.check_perim_km = QCheckBox(
            "Quilômetros, km"
        )

        self.check_perim_km.setChecked(True)

        layout_perimetro.addWidget(
            self.check_perim_m
        )

        layout_perimetro.addWidget(
            self.check_perim_km
        )

        layout_principal.addWidget(
            grupo_perimetro
        )

        # ---------------------------------------------------------------------
        # FEIÇÕES
        # ---------------------------------------------------------------------

        grupo_feicoes = QGroupBox(
            "Feições que serão calculadas"
        )

        layout_feicoes = QVBoxLayout()

        grupo_feicoes.setLayout(
            layout_feicoes
        )

        self.radio_todas = QRadioButton(
            "Todas as feições da camada"
        )

        self.radio_selecionadas = QRadioButton(
            (
                "Somente as feições selecionadas "
                f"({self.quantidade_selecionada})"
            )
        )

        self.radio_todas.setChecked(True)

        if self.quantidade_selecionada == 0:

            self.radio_selecionadas.setEnabled(False)

            self.radio_selecionadas.setToolTip(
                "A camada não possui feições selecionadas."
            )

        layout_feicoes.addWidget(
            self.radio_todas
        )

        layout_feicoes.addWidget(
            self.radio_selecionadas
        )

        layout_principal.addWidget(
            grupo_feicoes
        )

        # ---------------------------------------------------------------------
        # MODO DE SAÍDA
        # ---------------------------------------------------------------------

        grupo_saida = QGroupBox(
            "Destino dos resultados"
        )

        layout_saida = QVBoxLayout()

        grupo_saida.setLayout(
            layout_saida
        )

        self.radio_novo_arquivo = QRadioButton(
            "Criar um novo arquivo GeoPackage, recomendado"
        )

        self.radio_modificar = QRadioButton(
            "Modificar diretamente a camada selecionada"
        )

        # Opção segura selecionada por padrão
        self.radio_novo_arquivo.setChecked(True)

        self.radio_modificar.setToolTip(
            "Cria ou atualiza campos diretamente na camada ativa."
        )

        layout_saida.addWidget(
            self.radio_novo_arquivo
        )

        layout_saida.addWidget(
            self.radio_modificar
        )

        layout_principal.addWidget(
            grupo_saida
        )

        # ---------------------------------------------------------------------
        # PRECISÕES
        # ---------------------------------------------------------------------

        grupo_precisao = QGroupBox(
            "Precisão aplicada automaticamente"
        )

        layout_precisao = QVBoxLayout()

        grupo_precisao.setLayout(
            layout_precisao
        )

        texto_precisao = QLabel(
            "Área em metros quadrados: "
            "<b>3 casas decimais</b><br>"
            "Área em hectares: "
            "<b>4 casas decimais</b><br>"
            "Área em quilômetros quadrados: "
            "<b>3 casas decimais</b><br>"
            "Perímetro em metros: "
            "<b>0 casas decimais</b><br>"
            "Perímetro em quilômetros: "
            "<b>3 casas decimais</b>"
        )

        texto_precisao.setWordWrap(True)

        layout_precisao.addWidget(
            texto_precisao
        )

        layout_principal.addWidget(
            grupo_precisao
        )

        # ---------------------------------------------------------------------
        # MÉTODO
        # ---------------------------------------------------------------------

        informacao = QLabel(
            "<i>Método de medição: elipsoidal, com o elipsoide GRS80. "
            "A opção de modificar a camada ativa exige permissão de gravação "
            "e confirmação adicional.</i>"
        )

        informacao.setWordWrap(True)

        layout_principal.addWidget(
            informacao
        )

        # ---------------------------------------------------------------------
        # BOTÕES
        # ---------------------------------------------------------------------

        self.caixa_botoes = QDialogButtonBox(
            QDialogButtonBox.Ok |
            QDialogButtonBox.Cancel
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


    # -------------------------------------------------------------------------
    # 3.3. VALIDAR
    # -------------------------------------------------------------------------

    def validar_e_aceitar(self):

        alguma_unidade = any([
            self.check_area_m2.isChecked(),
            self.check_area_ha.isChecked(),
            self.check_area_km2.isChecked(),
            self.check_perim_m.isChecked(),
            self.check_perim_km.isChecked()
        ])

        if not alguma_unidade:

            QMessageBox.warning(
                self,
                "Nenhuma unidade selecionada",
                (
                    "Selecione pelo menos uma unidade "
                    "de área ou de perímetro."
                )
            )

            return

        self.accept()


    # -------------------------------------------------------------------------
    # 3.4. OBTER OPÇÕES
    # -------------------------------------------------------------------------

    def obter_opcoes(self):

        return {
            "area_m2": self.check_area_m2.isChecked(),
            "area_ha": self.check_area_ha.isChecked(),
            "area_km2": self.check_area_km2.isChecked(),
            "perim_m": self.check_perim_m.isChecked(),
            "perim_km": self.check_perim_km.isChecked(),
            "somente_selecionadas":
                self.radio_selecionadas.isChecked(),
            "criar_novo":
                self.radio_novo_arquivo.isChecked(),
            "modificar_camada":
                self.radio_modificar.isChecked()
        }


# =============================================================================
# 4. FUNÇÕES AUXILIARES
# =============================================================================

def obter_campos_escolhidos(opcoes):

    return [
        campo
        for campo in ORDEM_CAMPOS
        if opcoes[campo]
    ]


def configurar_medidor(camada):

    medidor = QgsDistanceArea()

    medidor.setSourceCrs(
        camada.crs(),
        QgsProject.instance().transformContext()
    )

    medidor.setEllipsoid(
        "GRS80"
    )

    if not medidor.willUseEllipsoid():

        raise Exception(
            "Não foi possível ativar a medição elipsoidal "
            "com o elipsoide GRS80."
        )

    return medidor


def medir_geometria(
    medidor,
    geometria
):
    """
    Calcula área em m² e perímetro em m.
    """

    area = medidor.measureArea(
        geometria
    )

    perimetro = medidor.measurePerimeter(
        geometria
    )

    area_m2 = medidor.convertAreaMeasurement(
        area,
        QgsUnitTypes.AreaSquareMeters
    )

    perimetro_m = medidor.convertLengthMeasurement(
        perimetro,
        QgsUnitTypes.DistanceMeters
    )

    return (
        abs(float(area_m2)),
        abs(float(perimetro_m))
    )


def calcular_valores(
    area_m2,
    perimetro_m,
    campos_escolhidos
):
    """
    Retorna os valores calculados já arredondados.
    """

    valores = {}

    if "area_m2" in campos_escolhidos:

        valores["area_m2"] = round(
            area_m2,
            PRECISOES["area_m2"]
        )

    if "area_ha" in campos_escolhidos:

        valores["area_ha"] = round(
            area_m2 / 10000.0,
            PRECISOES["area_ha"]
        )

    if "area_km2" in campos_escolhidos:

        valores["area_km2"] = round(
            area_m2 / 1000000.0,
            PRECISOES["area_km2"]
        )

    if "perim_m" in campos_escolhidos:

        valores["perim_m"] = round(
            perimetro_m,
            PRECISOES["perim_m"]
        )

    if "perim_km" in campos_escolhidos:

        valores["perim_km"] = round(
            perimetro_m / 1000.0,
            PRECISOES["perim_km"]
        )

    return valores


def obter_feicoes(
    camada,
    somente_selecionadas
):

    if somente_selecionadas:

        return (
            list(camada.getSelectedFeatures()),
            "somente feições selecionadas"
        )

    return (
        list(camada.getFeatures()),
        "todas as feições"
    )


def formatar_numero_br(
    valor,
    casas
):

    texto = f"{valor:,.{casas}f}"

    texto = texto.replace(
        ",",
        "TEMP"
    )

    texto = texto.replace(
        ".",
        ","
    )

    texto = texto.replace(
        "TEMP",
        "."
    )

    return texto


def normalizar_nome_camada(nome):

    nome = re.sub(
        r"[^A-Za-z0-9_]+",
        "_",
        nome
    )

    nome = nome.strip("_")

    if not nome:

        nome = "resultado_calculado"

    if nome[0].isdigit():

        nome = "camada_" + nome

    return nome[:60]


def corrigir_extensao_gpkg(caminho):

    if not caminho.lower().endswith(".gpkg"):

        caminho += ".gpkg"

    return caminho


def nome_campo_unico(
    nome_base,
    nomes_existentes
):

    if nome_base not in nomes_existentes:

        return nome_base

    contador = 2

    while True:

        nome_teste = f"{nome_base}_{contador}"

        if nome_teste not in nomes_existentes:

            return nome_teste

        contador += 1


# =============================================================================
# 5. MODO A: CRIAR NOVO GEOPACKAGE
# =============================================================================

def criar_novo_geopackage(
    camada_origem,
    feicoes_origem,
    campos_escolhidos,
    medidor
):
    """
    Cria um novo GeoPackage, sem alterar a camada original.
    """

    nome_sugerido = (
        f"{normalizar_nome_camada(camada_origem.name())}"
        "_calculado.gpkg"
    )

    caminho_inicial = os.path.join(
        os.path.expanduser("~"),
        nome_sugerido
    )

    caminho_saida, _ = QFileDialog.getSaveFileName(
        iface.mainWindow(),
        "Salvar resultado em novo GeoPackage",
        caminho_inicial,
        "GeoPackage (*.gpkg)"
    )

    if not caminho_saida:

        raise InterruptedError(
            "Operação cancelada na seleção do arquivo."
        )

    caminho_saida = corrigir_extensao_gpkg(
        caminho_saida
    )

    if os.path.exists(caminho_saida):

        raise Exception(
            "O arquivo selecionado já existe.\n\n"
            "Para proteger dados existentes, escolha outro nome."
        )

    # -------------------------------------------------------------------------
    # COPIAR CAMPOS ORIGINAIS
    # -------------------------------------------------------------------------

    campos_saida = QgsFields()

    for campo_original in camada_origem.fields():

        campos_saida.append(
            QgsField(campo_original)
        )

    nomes_existentes = set(
        campos_saida.names()
    )

    mapa_campos = {}

    # -------------------------------------------------------------------------
    # ADICIONAR CAMPOS CALCULADOS
    # -------------------------------------------------------------------------

    for nome_logico in campos_escolhidos:

        nome_real = nome_campo_unico(
            nome_logico,
            nomes_existentes
        )

        campos_saida.append(
            QgsField(
                nome_real,
                QVariant.Double,
                "double",
                20,
                PRECISOES[nome_logico]
            )
        )

        nomes_existentes.add(
            nome_real
        )

        mapa_campos[nome_logico] = nome_real

    # -------------------------------------------------------------------------
    # CRIAR CAMADA TEMPORÁRIA
    # -------------------------------------------------------------------------

    tipo_wkb = QgsWkbTypes.displayString(
        camada_origem.wkbType()
    )

    uri = (
        f"{tipo_wkb}"
        f"?crs={camada_origem.crs().authid()}"
    )

    nome_camada_saida = normalizar_nome_camada(
        f"{camada_origem.name()}_calculado"
    )

    camada_temporaria = QgsVectorLayer(
        uri,
        nome_camada_saida,
        "memory"
    )

    if not camada_temporaria.isValid():

        raise Exception(
            "Não foi possível criar a camada temporária."
        )

    provedor = camada_temporaria.dataProvider()

    lista_campos = [
        QgsField(campo)
        for campo in campos_saida
    ]

    if not provedor.addAttributes(lista_campos):

        raise Exception(
            "Não foi possível criar os campos da saída."
        )

    camada_temporaria.updateFields()

    indices = {
        campo_logico:
            camada_temporaria.fields().indexFromName(nome_real)
        for campo_logico, nome_real in mapa_campos.items()
    }

    feicoes_saida = []

    total_area_m2 = 0.0
    total_perimetro_m = 0.0

    calculadas = 0
    vazias = 0
    invalidas = 0
    erros = 0

    # -------------------------------------------------------------------------
    # PROCESSAR FEIÇÕES
    # -------------------------------------------------------------------------

    for feicao_origem in feicoes_origem:

        geometria = feicao_origem.geometry()

        if (
            geometria is None
            or geometria.isNull()
            or geometria.isEmpty()
        ):

            vazias += 1
            continue

        if not geometria.isGeosValid():

            invalidas += 1

        try:

            area_m2, perimetro_m = medir_geometria(
                medidor,
                geometria
            )

        except Exception:

            erros += 1
            continue

        valores = calcular_valores(
            area_m2,
            perimetro_m,
            campos_escolhidos
        )

        atributos = list(
            feicao_origem.attributes()
        )

        while len(atributos) < len(
            camada_temporaria.fields()
        ):

            atributos.append(None)

        for campo_logico, valor in valores.items():

            atributos[
                indices[campo_logico]
            ] = valor

        feicao_saida = QgsFeature(
            camada_temporaria.fields()
        )

        feicao_saida.setGeometry(
            geometria
        )

        feicao_saida.setAttributes(
            atributos
        )

        feicoes_saida.append(
            feicao_saida
        )

        total_area_m2 += area_m2
        total_perimetro_m += perimetro_m

        calculadas += 1

    if calculadas == 0:

        raise Exception(
            "Nenhuma feição pôde ser calculada."
        )

    if not provedor.addFeatures(feicoes_saida):

        raise Exception(
            "Não foi possível adicionar as feições "
            "à camada temporária."
        )

    camada_temporaria.updateExtents()

    # -------------------------------------------------------------------------
    # GRAVAR GEOPACKAGE
    # -------------------------------------------------------------------------

    opcoes_gravacao = (
        QgsVectorFileWriter.SaveVectorOptions()
    )

    opcoes_gravacao.driverName = "GPKG"
    opcoes_gravacao.fileEncoding = "UTF-8"
    opcoes_gravacao.layerName = nome_camada_saida
    opcoes_gravacao.actionOnExistingFile = (
        QgsVectorFileWriter.CreateOrOverwriteFile
    )

    resultado = QgsVectorFileWriter.writeAsVectorFormatV3(
        camada_temporaria,
        caminho_saida,
        QgsProject.instance().transformContext(),
        opcoes_gravacao
    )

    if resultado[0] != QgsVectorFileWriter.NoError:

        mensagem = (
            resultado[1]
            if len(resultado) > 1
            else "Erro não identificado."
        )

        raise Exception(
            "Não foi possível gravar o GeoPackage.\n\n"
            f"Detalhes: {mensagem}"
        )

    # -------------------------------------------------------------------------
    # CARREGAR RESULTADO
    # -------------------------------------------------------------------------

    uri_resultado = (
        f"{caminho_saida}"
        f"|layername={nome_camada_saida}"
    )

    camada_resultado = QgsVectorLayer(
        uri_resultado,
        nome_camada_saida,
        "ogr"
    )

    if not camada_resultado.isValid():

        raise Exception(
            "O arquivo foi gravado, mas não pôde ser carregado."
        )

    QgsProject.instance().addMapLayer(
        camada_resultado
    )

    # Copiar estilo
    try:

        camada_resultado.setRenderer(
            camada_origem.renderer().clone()
        )

        camada_resultado.setOpacity(
            camada_origem.opacity()
        )

        camada_resultado.triggerRepaint()

    except Exception:

        print(
            "Aviso: o estilo não pôde ser copiado integralmente."
        )

    return {
        "modo": "Novo GeoPackage",
        "destino": caminho_saida,
        "camada_resultado": nome_camada_saida,
        "mapa_campos": mapa_campos,
        "calculadas": calculadas,
        "vazias": vazias,
        "invalidas": invalidas,
        "erros": erros,
        "area_total_m2": total_area_m2,
        "perimetro_total_m": total_perimetro_m
    }


# =============================================================================
# 6. MODO B: MODIFICAR CAMADA ATIVA
# =============================================================================

def modificar_camada_ativa(
    camada,
    feicoes,
    campos_escolhidos,
    medidor
):
    """
    Cria ou atualiza campos diretamente na camada ativa.

    A função verifica as capacidades reais do provedor de dados
    antes de tentar criar campos ou alterar atributos.

    Quando a camada já está em modo de edição, as alterações permanecem
    pendentes para que o usuário possa salvá-las ou descartá-las manualmente.

    Quando a camada não está em edição, o script inicia a edição e salva
    automaticamente ao final.
    """

    # -------------------------------------------------------------------------
    # 1. OBTER O PROVEDOR E SUAS CAPACIDADES
    # -------------------------------------------------------------------------

    provedor = camada.dataProvider()
    capacidades = provedor.capabilities()

    # -------------------------------------------------------------------------
    # 2. IDENTIFICAR CAMPOS AUSENTES E EXISTENTES
    # -------------------------------------------------------------------------

    campos_ausentes = [
        nome_campo
        for nome_campo in campos_escolhidos
        if camada.fields().indexFromName(nome_campo) == -1
    ]

    campos_existentes = [
        nome_campo
        for nome_campo in campos_escolhidos
        if camada.fields().indexFromName(nome_campo) != -1
    ]

    # -------------------------------------------------------------------------
    # 3. VALIDAR A CRIAÇÃO DE NOVOS CAMPOS
    # -------------------------------------------------------------------------

    if campos_ausentes:

        permite_adicionar_campos = bool(
            capacidades
            & QgsVectorDataProvider.AddAttributes
        )

        if not permite_adicionar_campos:

            raise Exception(
                "A fonte da camada não permite criar novos campos.\n\n"
                "Campos que precisariam ser criados:\n"
                + "\n".join(
                    f"• {campo}"
                    for campo in campos_ausentes
                )
                + "\n\nUse a opção de criar um novo GeoPackage."
            )

    # -------------------------------------------------------------------------
    # 4. VALIDAR A ALTERAÇÃO DE ATRIBUTOS
    # -------------------------------------------------------------------------

    permite_alterar_atributos = bool(
        capacidades
        & QgsVectorDataProvider.ChangeAttributeValues
    )

    if not permite_alterar_atributos:

        raise Exception(
            "A fonte da camada não permite modificar atributos.\n\n"
            "Isso pode ocorrer com camadas remotas, arquivos protegidos "
            "ou fontes abertas somente para leitura.\n\n"
            "Use a opção de criar um novo GeoPackage."
        )

    # -------------------------------------------------------------------------
    # 5. PREPARAR A MENSAGEM DE CONFIRMAÇÃO
    # -------------------------------------------------------------------------

    if campos_existentes:

        texto_campos_existentes = "\n".join(
            f"• {campo}"
            for campo in campos_existentes
        )

    else:

        texto_campos_existentes = (
            "Nenhum campo existente será sobrescrito."
        )

    if campos_ausentes:

        texto_campos_ausentes = "\n".join(
            f"• {campo}"
            for campo in campos_ausentes
        )

    else:

        texto_campos_ausentes = (
            "Nenhum campo novo será criado."
        )

    resposta = QMessageBox.question(
        iface.mainWindow(),
        "Confirmar modificação da camada",
        (
            "Você escolheu modificar diretamente a camada ativa.\n\n"
            f"Camada:\n{camada.name()}\n\n"
            "Campos existentes que serão atualizados:\n"
            f"{texto_campos_existentes}\n\n"
            "Campos que serão criados:\n"
            f"{texto_campos_ausentes}\n\n"
            "Esta operação altera os atributos da camada atual.\n"
            "Recomenda-se possuir uma cópia de segurança.\n\n"
            "Deseja continuar?"
        ),
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No
    )

    if resposta != QMessageBox.Yes:

        raise InterruptedError(
            "Modificação da camada cancelada pelo usuário."
        )

    # -------------------------------------------------------------------------
    # 6. VERIFICAR O ESTADO DE EDIÇÃO
    # -------------------------------------------------------------------------

    camada_ja_estava_editando = camada.isEditable()

    if not camada_ja_estava_editando:

        if not camada.startEditing():

            raise Exception(
                "Não foi possível iniciar a edição da camada.\n\n"
                "Use a opção de criar um novo GeoPackage."
            )

    # -------------------------------------------------------------------------
    # 7. CRIAR UM COMANDO DE EDIÇÃO
    # -------------------------------------------------------------------------
    #
    # Esse agrupamento permite que as modificações apareçam como uma única
    # operação no histórico de desfazer do QGIS.
    # -------------------------------------------------------------------------

    comando_edicao_iniciado = False

    try:

        camada.beginEditCommand(
            "Calcular área e perímetro"
        )

        comando_edicao_iniciado = True

        # ---------------------------------------------------------------------
        # 8. CRIAR OS CAMPOS AUSENTES
        # ---------------------------------------------------------------------

        for nome_campo in campos_ausentes:

            campo_novo = QgsField(
                nome_campo,
                QVariant.Double,
                "double",
                20,
                PRECISOES[nome_campo]
            )

            sucesso_campo = camada.addAttribute(
                campo_novo
            )

            if not sucesso_campo:

                raise Exception(
                    f"Não foi possível criar o campo "
                    f"'{nome_campo}'."
                )

        camada.updateFields()

        # ---------------------------------------------------------------------
        # 9. LOCALIZAR OS ÍNDICES DOS CAMPOS
        # ---------------------------------------------------------------------

        indices = {}

        for nome_campo in campos_escolhidos:

            indice = camada.fields().indexFromName(
                nome_campo
            )

            if indice == -1:

                raise Exception(
                    f"O campo '{nome_campo}' não foi localizado "
                    "após a preparação da tabela."
                )

            indices[nome_campo] = indice

        # ---------------------------------------------------------------------
        # 10. INICIALIZAR CONTADORES E TOTAIS
        # ---------------------------------------------------------------------

        total_area_m2 = 0.0
        total_perimetro_m = 0.0

        calculadas = 0
        vazias = 0
        invalidas = 0
        erros = 0

        # ---------------------------------------------------------------------
        # 11. CALCULAR E GRAVAR OS VALORES
        # ---------------------------------------------------------------------

        for feicao in feicoes:

            geometria = feicao.geometry()

            # -----------------------------------------------------------------
            # IGNORAR GEOMETRIAS VAZIAS
            # -----------------------------------------------------------------

            if (
                geometria is None
                or geometria.isNull()
                or geometria.isEmpty()
            ):

                vazias += 1
                continue

            # -----------------------------------------------------------------
            # REGISTRAR GEOMETRIAS INVÁLIDAS
            # -----------------------------------------------------------------

            if not geometria.isGeosValid():

                invalidas += 1

            # -----------------------------------------------------------------
            # MEDIR A GEOMETRIA
            # -----------------------------------------------------------------

            try:

                area_m2, perimetro_m = medir_geometria(
                    medidor,
                    geometria
                )

            except Exception as erro_medicao:

                erros += 1

                print(
                    f"Erro na feição {feicao.id()}: "
                    f"{str(erro_medicao)}"
                )

                continue

            # -----------------------------------------------------------------
            # CONVERTER E ARREDONDAR OS VALORES
            # -----------------------------------------------------------------

            valores = calcular_valores(
                area_m2,
                perimetro_m,
                campos_escolhidos
            )

            # -----------------------------------------------------------------
            # GRAVAR OS ATRIBUTOS
            # -----------------------------------------------------------------

            for nome_campo, valor in valores.items():

                sucesso_atributo = camada.changeAttributeValue(
                    feicao.id(),
                    indices[nome_campo],
                    valor
                )

                if not sucesso_atributo:

                    raise Exception(
                        "Não foi possível gravar o campo "
                        f"'{nome_campo}' na feição "
                        f"{feicao.id()}."
                    )

            total_area_m2 += area_m2
            total_perimetro_m += perimetro_m

            calculadas += 1

        # ---------------------------------------------------------------------
        # 12. VALIDAR O RESULTADO
        # ---------------------------------------------------------------------

        if calculadas == 0:

            raise Exception(
                "Nenhuma feição pôde ser calculada.\n\n"
                "Verifique o CRS e as geometrias da camada."
            )

        # ---------------------------------------------------------------------
        # 13. FINALIZAR O COMANDO DE EDIÇÃO
        # ---------------------------------------------------------------------

        camada.endEditCommand()

        comando_edicao_iniciado = False

        # ---------------------------------------------------------------------
        # 14. SALVAR OU MANTER AS ALTERAÇÕES PENDENTES
        # ---------------------------------------------------------------------

        if not camada_ja_estava_editando:

            sucesso_commit = camada.commitChanges()

            if not sucesso_commit:

                erros_commit = "\n".join(
                    camada.commitErrors()
                )

                raise Exception(
                    "Não foi possível salvar as alterações.\n\n"
                    f"Detalhes:\n{erros_commit}"
                )

            situacao_gravacao = (
                "Alterações salvas automaticamente"
            )

        else:

            situacao_gravacao = (
                "Alterações mantidas no modo de edição. "
                "Use Salvar Edições no QGIS para confirmá-las."
            )

        camada.updateFields()
        camada.triggerRepaint()

        # ---------------------------------------------------------------------
        # 15. RETORNAR O RESUMO
        # ---------------------------------------------------------------------

        return {
            "modo": "Modificação da camada ativa",
            "destino": camada.source(),
            "camada_resultado": camada.name(),
            "mapa_campos": {
                campo: campo
                for campo in campos_escolhidos
            },
            "calculadas": calculadas,
            "vazias": vazias,
            "invalidas": invalidas,
            "erros": erros,
            "area_total_m2": total_area_m2,
            "perimetro_total_m": total_perimetro_m,
            "situacao_gravacao": situacao_gravacao
        }

    except Exception:

        # ---------------------------------------------------------------------
        # CANCELAR O COMANDO DE EDIÇÃO EM CASO DE ERRO
        # ---------------------------------------------------------------------

        if comando_edicao_iniciado:

            camada.destroyEditCommand()

        # ---------------------------------------------------------------------
        # REVERTER SOMENTE SE O SCRIPT INICIOU A EDIÇÃO
        # ---------------------------------------------------------------------

        if (
            not camada_ja_estava_editando
            and camada.isEditable()
        ):

            camada.rollBack()

        raise
        

# =============================================================================
# 7. PROCESSAMENTO PRINCIPAL
# =============================================================================

try:

    print("")
    print("=" * 74)
    print("CALCULADORA AUTOMÁTICA DE ÁREA E PERÍMETRO")
    print("=" * 74)

    # -------------------------------------------------------------------------
    # 7.1. CAMADA ATIVA
    # -------------------------------------------------------------------------

    camada = iface.activeLayer()

    if camada is None:

        raise Exception(
            "Nenhuma camada está ativa.\n\n"
            "Selecione uma camada poligonal."
        )

    if camada.type() != QgsMapLayerType.VectorLayer:

        raise Exception(
            f"A camada '{camada.name()}' não é vetorial."
        )

    # -------------------------------------------------------------------------
    # 7.2. TIPO DE GEOMETRIA
    # -------------------------------------------------------------------------

    if (
        QgsWkbTypes.geometryType(camada.wkbType())
        != QgsWkbTypes.PolygonGeometry
    ):

        raise Exception(
            f"A camada '{camada.name()}' não é poligonal.\n\n"
            "A ferramenta aceita polígonos e multipolígonos."
        )

    # -------------------------------------------------------------------------
    # 7.3. CRS
    # -------------------------------------------------------------------------

    if not camada.crs().isValid():

        raise Exception(
            f"A camada '{camada.name()}' não possui CRS válido."
        )

    # -------------------------------------------------------------------------
    # 7.4. FEIÇÕES
    # -------------------------------------------------------------------------

    if camada.featureCount() == 0:

        raise Exception(
            f"A camada '{camada.name()}' não possui feições."
        )

    # -------------------------------------------------------------------------
    # 7.5. ABRIR POPUP
    # -------------------------------------------------------------------------

    janela = JanelaConfiguracao(
        nome_camada=camada.name(),
        quantidade_selecionada=(
            camada.selectedFeatureCount()
        ),
        parent=iface.mainWindow()
    )

    if janela.exec_() != QDialog.Accepted:

        raise InterruptedError(
            "Operação cancelada pelo usuário."
        )

    opcoes = janela.obter_opcoes()

    campos_escolhidos = obter_campos_escolhidos(
        opcoes
    )

    # -------------------------------------------------------------------------
    # 7.6. OBTER FEIÇÕES
    # -------------------------------------------------------------------------

    feicoes, escopo = obter_feicoes(
        camada,
        opcoes["somente_selecionadas"]
    )

    if not feicoes:

        raise Exception(
            "Nenhuma feição está disponível para processamento."
        )

    # -------------------------------------------------------------------------
    # 7.7. CONFIGURAR MEDIÇÃO
    # -------------------------------------------------------------------------

    medidor = configurar_medidor(
        camada
    )

    print("")
    print(f"Camada: {camada.name()}")
    print(f"CRS: {camada.crs().authid()}")
    print("Método: medição elipsoidal")
    print("Elipsoide: GRS80")
    print(f"Escopo: {escopo}")
    print(
        "Campos: "
        + ", ".join(campos_escolhidos)
    )

    # -------------------------------------------------------------------------
    # 7.8. EXECUTAR O MODO ESCOLHIDO
    # -------------------------------------------------------------------------

    if opcoes["criar_novo"]:

        resultado = criar_novo_geopackage(
            camada,
            feicoes,
            campos_escolhidos,
            medidor
        )

    else:

        resultado = modificar_camada_ativa(
            camada,
            feicoes,
            campos_escolhidos,
            medidor
        )

    # -------------------------------------------------------------------------
    # 7.9. PREPARAR RESUMO
    # -------------------------------------------------------------------------

    area_total_m2 = resultado["area_total_m2"]
    area_total_ha = area_total_m2 / 10000.0
    area_total_km2 = area_total_m2 / 1000000.0

    perimetro_total_m = resultado["perimetro_total_m"]
    perimetro_total_km = perimetro_total_m / 1000.0

    texto_campos = "\n".join(
        (
            f"• {resultado['mapa_campos'][campo]}: "
            f"{ROTULOS[campo]}"
        )
        for campo in campos_escolhidos
    )

    # -------------------------------------------------------------------------
    # 7.10. CONSOLE
    # -------------------------------------------------------------------------

    print("")
    print("-" * 74)
    print("RESULTADO")
    print("-" * 74)
    print(f"Modo: {resultado['modo']}")
    print(f"Camada: {resultado['camada_resultado']}")
    print(f"Destino: {resultado['destino']}")
    print(f"Feições calculadas: {resultado['calculadas']}")
    print(
        f"Área total: "
        f"{formatar_numero_br(area_total_m2, 3)} m²"
    )
    print(
        f"Área total: "
        f"{formatar_numero_br(area_total_ha, 4)} ha"
    )
    print(
        f"Área total: "
        f"{formatar_numero_br(area_total_km2, 3)} km²"
    )
    print(
        f"Perímetro somado: "
        f"{formatar_numero_br(perimetro_total_m, 0)} m"
    )
    print(
        f"Perímetro somado: "
        f"{formatar_numero_br(perimetro_total_km, 3)} km"
    )
    print(f"Geometrias vazias: {resultado['vazias']}")
    print(f"Geometrias inválidas: {resultado['invalidas']}")
    print(f"Erros de medição: {resultado['erros']}")
    print("-" * 74)

    # -------------------------------------------------------------------------
    # 7.11. LOG
    # -------------------------------------------------------------------------

    mensagem_log = (
        f"Calculadora concluída; "
        f"modo: {resultado['modo']}; "
        f"camada: {camada.name()}; "
        f"destino: {resultado['destino']}; "
        f"escopo: {escopo}; "
        f"feições: {resultado['calculadas']}; "
        f"CRS: {camada.crs().authid()}; "
        f"método: elipsoidal; "
        f"elipsoide: GRS80; "
        f"campos: {', '.join(campos_escolhidos)}; "
        f"área: {area_total_ha:.4f} ha; "
        f"perímetro: {perimetro_total_km:.3f} km."
    )

    QgsMessageLog.logMessage(
        mensagem_log,
        "Calculadora de Área e Perímetro",
        Qgis.Info
    )

    # -------------------------------------------------------------------------
    # 7.12. MENSAGEM FINAL
    # -------------------------------------------------------------------------

    mensagem_final = (
        "Cálculo concluído com sucesso.\n\n"
        f"Modo:\n{resultado['modo']}\n\n"
        f"Camada:\n{resultado['camada_resultado']}\n\n"
        f"Feições calculadas: {resultado['calculadas']}\n"
        f"Escopo: {escopo}\n\n"
        "Método:\n"
        "Medição elipsoidal, elipsoide GRS80\n\n"
        "Área total das feições processadas:\n"
        f"{formatar_numero_br(area_total_m2, 3)} m²\n"
        f"{formatar_numero_br(area_total_ha, 4)} ha\n"
        f"{formatar_numero_br(area_total_km2, 3)} km²\n\n"
        "Soma dos perímetros individuais:\n"
        f"{formatar_numero_br(perimetro_total_m, 0)} m\n"
        f"{formatar_numero_br(perimetro_total_km, 3)} km\n\n"
        f"Campos calculados:\n{texto_campos}\n\n"
        f"Destino:\n{resultado['destino']}"
    )

    if resultado["modo"] == "Novo GeoPackage":

        mensagem_final += (
            "\n\nA camada original não foi modificada."
        )

    else:

        mensagem_final += (
            "\n\nA camada ativa foi modificada diretamente."
        )

    if "situacao_gravacao" in resultado:

        mensagem_final += (
            "\n\nSituação da gravação:\n"
            f"{resultado['situacao_gravacao']}"
        )

    if (
        resultado["vazias"] > 0
        or resultado["invalidas"] > 0
        or resultado["erros"] > 0
    ):

        mensagem_final += (
            "\n\nAvisos:\n"
            f"• Geometrias vazias: {resultado['vazias']}\n"
            f"• Geometrias inválidas: {resultado['invalidas']}\n"
            f"• Erros de medição: {resultado['erros']}"
        )

    QMessageBox.information(
        iface.mainWindow(),
        "Cálculo concluído",
        mensagem_final
    )


# =============================================================================
# 8. CANCELAMENTO
# =============================================================================

except InterruptedError as erro_cancelamento:

    print("")
    print(str(erro_cancelamento))

    QgsMessageLog.logMessage(
        str(erro_cancelamento),
        "Calculadora de Área e Perímetro",
        Qgis.Warning
    )


# =============================================================================
# 9. ERROS
# =============================================================================

except Exception as erro:

    print("")
    print("=" * 74)
    print("ERRO NA CALCULADORA DE ÁREA E PERÍMETRO")
    print("=" * 74)
    print(str(erro))
    print("=" * 74)

    QgsMessageLog.logMessage(
        str(erro),
        "Calculadora de Área e Perímetro",
        Qgis.Critical
    )

    QMessageBox.critical(
        iface.mainWindow(),
        "Erro no cálculo",
        (
            "Não foi possível concluir o processamento.\n\n"
            f"Detalhes:\n{str(erro)}"
        )
    )
