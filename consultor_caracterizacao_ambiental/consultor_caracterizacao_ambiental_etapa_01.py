# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Consultor de Caracterizacao Ambiental
Etapa: 01 - Configuracao e validacao inicial
Versao: 0.1.0-alpha.1
Autor: Eloizio Dantas

Objetivo:
    Validar a interface e as entradas do MVP 0.1.0 antes de executar qualquer
    intersecao ou gravacao. Esta etapa trabalha somente com camadas locais ou
    ja carregadas no projeto QGIS.

Escopo desta etapa:
    - selecionar uma camada poligonal de consulta;
    - escolher uma unica feicao selecionada ou dissolver todas as feicoes;
    - configurar ate tres temas: Geologia, Geomorfologia e Pedologia;
    - selecionar o campo de classe de cada tema;
    - registrar fonte, data-base e escala;
    - validar CRS, geometria, campo e intersecao de extensoes;
    - mostrar o plano de consulta no console e em popup.

Esta etapa NAO:
    - acessa internet ou geosservicos;
    - calcula intersecoes, areas ou percentuais;
    - altera camadas;
    - cria GeoPackage ou relatorio.
===============================================================================
"""

from datetime import date

from qgis.core import QgsMapLayerType, QgsProject, QgsWkbTypes
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QLabel, QLineEdit, QMessageBox,
    QRadioButton, QVBoxLayout
)
from qgis.utils import iface

VERSAO = "0.1.0-alpha.1"
TEMAS = (
    ("geologia", "Geologia"),
    ("geomorfologia", "Geomorfologia"),
    ("pedologia", "Pedologia"),
)


def camadas_poligonais_validas():
    """Retorna camadas vetoriais poligonais validas carregadas no projeto."""
    saida = []
    for camada in QgsProject.instance().mapLayers().values():
        if (
            camada.type() == QgsMapLayerType.VectorLayer
            and camada.isValid()
            and camada.isSpatial()
            and QgsWkbTypes.geometryType(camada.wkbType())
                == QgsWkbTypes.PolygonGeometry
        ):
            saida.append(camada)
    return sorted(saida, key=lambda c: c.name().lower())


def texto_crs(camada):
    if camada is None or not camada.crs().isValid():
        return "CRS nao identificado"
    return f"{camada.crs().authid()} - {camada.crs().description()}"


def contar_geometrias_problematicas(camada, somente_selecionadas=False):
    """Conta geometrias vazias e invalidas sem modificar a camada."""
    vazias = 0
    invalidas = 0
    feicoes = (
        camada.getSelectedFeatures()
        if somente_selecionadas
        else camada.getFeatures()
    )
    for feicao in feicoes:
        geometria = feicao.geometry()
        if geometria is None or geometria.isNull() or geometria.isEmpty():
            vazias += 1
            continue
        try:
            if not geometria.isGeosValid():
                invalidas += 1
        except Exception:
            pass
    return vazias, invalidas


class BlocoTema:
    """Controles de configuracao de um tema ambiental."""

    def __init__(self, tema_id, titulo, camadas, dialogo):
        self.tema_id = tema_id
        self.titulo = titulo
        self.dialogo = dialogo
        self.grupo = QGroupBox(titulo)
        self.grupo.setCheckable(True)
        self.grupo.setChecked(True)
        formulario = QFormLayout(self.grupo)

        self.combo_camada = QComboBox()
        self.combo_camada.addItem("Selecione uma camada...", None)
        for camada in camadas:
            self.combo_camada.addItem(camada.name(), camada.id())

        self.combo_campo = QComboBox()
        self.combo_campo.addItem("Selecione uma camada primeiro", None)
        self.combo_campo.setEnabled(False)

        self.campo_fonte = QLineEdit()
        self.campo_fonte.setPlaceholderText(
            "Ex.: IBGE/BDIA ou levantamento interno"
        )

        self.data_base = QDateEdit()
        self.data_base.setCalendarPopup(True)
        self.data_base.setDisplayFormat("dd/MM/yyyy")
        self.data_base.setDate(QDate.currentDate())

        self.campo_escala = QLineEdit()
        self.campo_escala.setPlaceholderText("Ex.: 1:250.000")

        self.rotulo_crs = QLabel("CRS nao definido")
        self.rotulo_crs.setWordWrap(True)

        formulario.addRow("Camada tematica:", self.combo_camada)
        formulario.addRow("Campo de classe:", self.combo_campo)
        formulario.addRow("Fonte:", self.campo_fonte)
        formulario.addRow("Data-base:", self.data_base)
        formulario.addRow("Escala:", self.campo_escala)
        formulario.addRow("CRS:", self.rotulo_crs)

        self.combo_camada.currentIndexChanged.connect(self.atualizar_campos)

    def camada(self):
        camada_id = self.combo_camada.currentData()
        return QgsProject.instance().mapLayer(camada_id) if camada_id else None

    def atualizar_campos(self):
        camada = self.camada()
        self.combo_campo.clear()
        if camada is None:
            self.combo_campo.addItem("Selecione uma camada primeiro", None)
            self.combo_campo.setEnabled(False)
            self.rotulo_crs.setText("CRS nao definido")
            return
        self.combo_campo.addItem("Selecione o campo...", None)
        for campo in camada.fields():
            self.combo_campo.addItem(
                f"{campo.name()} ({campo.typeName()})",
                campo.name()
            )
        self.combo_campo.setEnabled(True)
        self.rotulo_crs.setText(texto_crs(camada))

    def configuracao(self):
        if not self.grupo.isChecked():
            return None
        camada = self.camada()
        return {
            "tema_id": self.tema_id,
            "tema": self.titulo,
            "camada_id": camada.id(),
            "camada_nome": camada.name(),
            "campo_classe": self.combo_campo.currentData(),
            "fonte": self.campo_fonte.text().strip(),
            "data_base": self.data_base.date().toString("yyyy-MM-dd"),
            "escala": self.campo_escala.text().strip(),
            "crs": camada.crs().authid(),
        }


class JanelaConsultor(QDialog):
    def __init__(self, camadas, parent=None):
        super().__init__(parent)
        self.camadas = camadas
        self.setWindowTitle(
            "Consultor de Caracterizacao Ambiental - Configuracao"
        )
        self.setMinimumWidth(680)
        self.setWindowModality(Qt.ApplicationModal)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "<b>MVP 0.1.0:</b> caracterizacao de um poligono com ate tres "
            "temas vetoriais locais: Geologia, Geomorfologia e Pedologia."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        grupo_area = QGroupBox("Area de consulta")
        form_area = QFormLayout(grupo_area)
        self.combo_area = QComboBox()
        self.combo_area.addItem("Selecione a camada...", None)
        for camada in camadas:
            self.combo_area.addItem(camada.name(), camada.id())
        self.rotulo_area_crs = QLabel("CRS nao definido")
        self.rotulo_area_crs.setWordWrap(True)
        self.radio_selecionada = QRadioButton(
            "Usar uma unica feicao selecionada"
        )
        self.radio_todas = QRadioButton(
            "Dissolver todas as feicoes da camada"
        )
        self.radio_selecionada.setChecked(True)
        form_area.addRow("Camada:", self.combo_area)
        form_area.addRow("Escopo:", self.radio_selecionada)
        form_area.addRow("", self.radio_todas)
        form_area.addRow("CRS:", self.rotulo_area_crs)
        layout.addWidget(grupo_area)

        self.blocos = []
        for tema_id, titulo in TEMAS:
            bloco = BlocoTema(tema_id, titulo, camadas, self)
            self.blocos.append(bloco)
            layout.addWidget(bloco.grupo)

        aviso = QLabel(
            "<i>Nesta etapa nenhuma camada sera alterada e nenhum arquivo "
            "sera criado. O objetivo e validar entradas e metadados.</i>"
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)

        botoes = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        botoes.button(QDialogButtonBox.Ok).setText("Validar configuracao")
        botoes.accepted.connect(self.validar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)
        self.combo_area.currentIndexChanged.connect(self.atualizar_area)

    def camada_area(self):
        camada_id = self.combo_area.currentData()
        return QgsProject.instance().mapLayer(camada_id) if camada_id else None

    def atualizar_area(self):
        camada = self.camada_area()
        self.rotulo_area_crs.setText(texto_crs(camada))
        if camada is not None:
            n = camada.selectedFeatureCount()
            self.radio_selecionada.setText(
                f"Usar uma unica feicao selecionada ({n} selecionada(s))"
            )

    def validar(self):
        erros = []
        avisos = []
        area = self.camada_area()
        if area is None:
            erros.append("Selecione a camada da area de consulta.")
        else:
            if not area.crs().isValid():
                erros.append("A area de consulta nao possui CRS valido.")
            if self.radio_selecionada.isChecked():
                if area.selectedFeatureCount() != 1:
                    erros.append(
                        "O modo selecionado exige exatamente uma feicao "
                        "selecionada na camada de consulta."
                    )
            vazias, invalidas = contar_geometrias_problematicas(
                area,
                self.radio_selecionada.isChecked()
            )
            if vazias:
                erros.append(
                    f"A area de consulta possui {vazias} geometria(s) vazia(s)."
                )
            if invalidas:
                erros.append(
                    f"A area de consulta possui {invalidas} geometria(s) invalida(s)."
                )

        ativos = [b for b in self.blocos if b.grupo.isChecked()]
        if not ativos:
            erros.append("Ative pelo menos um tema ambiental.")

        for bloco in ativos:
            camada = bloco.camada()
            prefixo = bloco.titulo
            if camada is None:
                erros.append(f"{prefixo}: selecione a camada tematica.")
                continue
            if area is not None and camada.id() == area.id():
                avisos.append(
                    f"{prefixo}: a camada tematica e a mesma area de consulta."
                )
            if not camada.crs().isValid():
                erros.append(f"{prefixo}: a camada nao possui CRS valido.")
            if not bloco.combo_campo.currentData():
                erros.append(f"{prefixo}: selecione o campo de classe.")
            if not bloco.campo_fonte.text().strip():
                erros.append(f"{prefixo}: informe a fonte.")
            if not bloco.campo_escala.text().strip():
                avisos.append(f"{prefixo}: escala nao informada.")
            vazias, invalidas = contar_geometrias_problematicas(camada)
            if vazias:
                avisos.append(f"{prefixo}: {vazias} geometria(s) vazia(s).")
            if invalidas:
                erros.append(f"{prefixo}: {invalidas} geometria(s) invalida(s).")
            if area is not None and not area.extent().intersects(camada.extent()):
                avisos.append(
                    f"{prefixo}: as extensoes nao se interceptam; o resultado "
                    "provavelmente sera sem cobertura."
                )

        if erros:
            QMessageBox.critical(
                self,
                "Configuracao invalida",
                "Corrija os itens abaixo:\n\n" +
                "\n".join(f"- {erro}" for erro in erros)
            )
            return
        if avisos:
            resposta = QMessageBox.question(
                self,
                "Configuracao com avisos",
                "Avisos encontrados:\n\n" +
                "\n".join(f"- {aviso}" for aviso in avisos) +
                "\n\nDeseja aceitar a configuracao?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if resposta != QMessageBox.Yes:
                return
        self.accept()

    def resultado(self):
        area = self.camada_area()
        return {
            "versao": VERSAO,
            "area": {
                "camada_id": area.id(),
                "camada_nome": area.name(),
                "crs": area.crs().authid(),
                "modo": (
                    "FEICAO_SELECIONADA"
                    if self.radio_selecionada.isChecked()
                    else "DISSOLVER_TODAS"
                ),
                "feicoes_selecionadas": area.selectedFeatureCount(),
                "feicoes_totais": area.featureCount(),
            },
            "temas": [
                bloco.configuracao()
                for bloco in self.blocos
                if bloco.grupo.isChecked()
            ]
        }


try:
    print("\n" + "=" * 76)
    print("CONSULTOR DE CARACTERIZACAO AMBIENTAL")
    print("ETAPA 01 - CONFIGURACAO E VALIDACAO")
    print("=" * 76)

    camadas = camadas_poligonais_validas()
    if len(camadas) < 2:
        raise Exception(
            "Carregue pelo menos duas camadas poligonais validas: uma area "
            "de consulta e uma camada tematica."
        )

    janela = JanelaConsultor(camadas, iface.mainWindow())
    if janela.exec_() != QDialog.Accepted:
        raise InterruptedError("Configuracao cancelada pelo usuario.")

    plano = janela.resultado()
    print("\nPLANO DE CONSULTA VALIDADO")
    print(f"Versao: {plano['versao']}")
    print(f"Area: {plano['area']['camada_nome']}")
    print(f"CRS: {plano['area']['crs']}")
    print(f"Modo: {plano['area']['modo']}")
    print("Temas:")
    for tema in plano["temas"]:
        print(
            f"  - {tema['tema']}: camada='{tema['camada_nome']}', "
            f"campo='{tema['campo_classe']}', fonte='{tema['fonte']}', "
            f"data='{tema['data_base']}', escala='{tema['escala'] or 'NAO INFORMADA'}'"
        )

    resumo = "\n".join(
        f"- {t['tema']}: {t['camada_nome']} / {t['campo_classe']}"
        for t in plano["temas"]
    )
    QMessageBox.information(
        iface.mainWindow(),
        "Plano de consulta validado",
        "Configuracao validada com sucesso.\n\n"
        f"Area: {plano['area']['camada_nome']}\n"
        f"CRS: {plano['area']['crs']}\n"
        f"Modo: {plano['area']['modo']}\n\n"
        f"Temas:\n{resumo}\n\n"
        "Nenhuma camada foi alterada e nenhum arquivo foi criado."
    )

except InterruptedError as erro:
    print(str(erro))
except Exception as erro:
    print("\nERRO: " + str(erro))
    QMessageBox.critical(
        iface.mainWindow(),
        "Erro no Consultor Ambiental",
        str(erro)
    )
