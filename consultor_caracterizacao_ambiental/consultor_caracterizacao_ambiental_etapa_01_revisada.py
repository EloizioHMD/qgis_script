# -*- coding: utf-8 -*-
"""
Consultor de Caracterizacao Ambiental
Etapa 01 revisada: configuracao e validacao inicial
Versao: 0.1.0-alpha.2
Autor: Eloizio Dantas

Correcao UX:
- preseleciona a camada ativa quando ela for poligonal;
- mostra orientacao imediatamente quando nenhuma area estiver escolhida;
- desabilita o modo "uma feicao" quando a quantidade selecionada for diferente de 1;
- usa janela rolavel para evitar botoes fora da tela;
- diferencia Cancelar de erro de validacao;
- nao cria nem altera arquivos.
"""

from qgis.core import QgsMapLayerType, QgsProject, QgsWkbTypes
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QMessageBox, QRadioButton, QScrollArea, QVBoxLayout,
    QWidget
)
from qgis.utils import iface

VERSAO = "0.1.0-alpha.2"
TEMAS = (("geologia", "Geologia"), ("geomorfologia", "Geomorfologia"), ("pedologia", "Pedologia"))


def camadas_poligonais():
    resultado = []
    for camada in QgsProject.instance().mapLayers().values():
        if (camada.type() == QgsMapLayerType.VectorLayer and camada.isValid()
                and camada.isSpatial()
                and QgsWkbTypes.geometryType(camada.wkbType()) == QgsWkbTypes.PolygonGeometry):
            resultado.append(camada)
    return sorted(resultado, key=lambda c: c.name().lower())


def crs_texto(camada):
    if camada is None or not camada.crs().isValid():
        return "CRS nao identificado"
    return f"{camada.crs().authid()} - {camada.crs().description()}"


def contar_problemas(camada, selecionadas=False):
    vazias = invalidas = 0
    feicoes = camada.getSelectedFeatures() if selecionadas else camada.getFeatures()
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
    def __init__(self, tema_id, titulo, camadas):
        self.tema_id = tema_id
        self.titulo = titulo
        self.grupo = QGroupBox(titulo)
        self.grupo.setCheckable(True)
        self.grupo.setChecked(tema_id == "geologia")
        form = QFormLayout(self.grupo)

        self.combo_camada = QComboBox()
        self.combo_camada.addItem("Selecione uma camada...", None)
        for camada in camadas:
            self.combo_camada.addItem(camada.name(), camada.id())

        self.combo_campo = QComboBox()
        self.combo_campo.addItem("Selecione uma camada primeiro", None)
        self.combo_campo.setEnabled(False)
        self.fonte = QLineEdit()
        self.fonte.setPlaceholderText("Ex.: IBGE/BDIA ou levantamento interno")
        self.data_base = QDateEdit(QDate.currentDate())
        self.data_base.setCalendarPopup(True)
        self.data_base.setDisplayFormat("dd/MM/yyyy")
        self.escala = QLineEdit()
        self.escala.setPlaceholderText("Ex.: 1:250.000")
        self.crs = QLabel("CRS nao definido")
        self.crs.setWordWrap(True)

        form.addRow("Camada tematica:", self.combo_camada)
        form.addRow("Campo de classe:", self.combo_campo)
        form.addRow("Fonte:", self.fonte)
        form.addRow("Data-base:", self.data_base)
        form.addRow("Escala:", self.escala)
        form.addRow("CRS:", self.crs)
        self.combo_camada.currentIndexChanged.connect(self.atualizar)

    def camada(self):
        cid = self.combo_camada.currentData()
        return QgsProject.instance().mapLayer(cid) if cid else None

    def atualizar(self):
        camada = self.camada()
        self.combo_campo.clear()
        if camada is None:
            self.combo_campo.addItem("Selecione uma camada primeiro", None)
            self.combo_campo.setEnabled(False)
            self.crs.setText("CRS nao definido")
            return
        self.combo_campo.addItem("Selecione o campo...", None)
        for campo in camada.fields():
            self.combo_campo.addItem(f"{campo.name()} ({campo.typeName()})", campo.name())
        self.combo_campo.setEnabled(True)
        self.crs.setText(crs_texto(camada))

    def resultado(self):
        if not self.grupo.isChecked():
            return None
        camada = self.camada()
        return {
            "tema_id": self.tema_id, "tema": self.titulo,
            "camada_id": camada.id(), "camada_nome": camada.name(),
            "campo_classe": self.combo_campo.currentData(),
            "fonte": self.fonte.text().strip(),
            "data_base": self.data_base.date().toString("yyyy-MM-dd"),
            "escala": self.escala.text().strip(), "crs": camada.crs().authid()
        }


class JanelaConsultor(QDialog):
    def __init__(self, camadas, parent=None):
        super().__init__(parent)
        self.camadas = camadas
        self.cancelamento_explicito = False
        self.setWindowTitle("Consultor Ambiental - Etapa 01 revisada")
        self.resize(720, 720)
        self.setWindowModality(Qt.ApplicationModal)

        principal = QVBoxLayout(self)
        orientacao = QLabel(
            "<b>1.</b> Escolha a area de consulta. "
            "<b>2.</b> Ative e configure pelo menos um tema. "
            "<b>3.</b> Clique em Validar configuracao."
        )
        orientacao.setWordWrap(True)
        principal.addWidget(orientacao)

        self.estado = QLabel("Selecione a camada da area de consulta.")
        self.estado.setWordWrap(True)
        self.estado.setStyleSheet("QLabel { color: #b00020; font-weight: bold; padding: 6px; }")
        principal.addWidget(self.estado)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        conteudo = QWidget()
        corpo = QVBoxLayout(conteudo)

        grupo_area = QGroupBox("Area de consulta")
        form_area = QFormLayout(grupo_area)
        self.combo_area = QComboBox()
        self.combo_area.addItem("Selecione a camada...", None)
        for camada in camadas:
            self.combo_area.addItem(camada.name(), camada.id())
        self.radio_sel = QRadioButton("Usar uma unica feicao selecionada")
        self.radio_todas = QRadioButton("Dissolver todas as feicoes")
        self.radio_todas.setChecked(True)
        self.info_crs = QLabel("CRS nao definido")
        self.info_crs.setWordWrap(True)
        form_area.addRow("Camada:", self.combo_area)
        form_area.addRow("Escopo:", self.radio_sel)
        form_area.addRow("", self.radio_todas)
        form_area.addRow("CRS:", self.info_crs)
        corpo.addWidget(grupo_area)

        self.blocos = []
        for tema_id, titulo in TEMAS:
            bloco = BlocoTema(tema_id, titulo, camadas)
            self.blocos.append(bloco)
            corpo.addWidget(bloco.grupo)
        corpo.addStretch(1)
        scroll.setWidget(conteudo)
        principal.addWidget(scroll)

        self.botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.botoes.button(QDialogButtonBox.Ok).setText("Validar configuracao")
        self.botoes.accepted.connect(self.validar)
        self.botoes.rejected.connect(self.cancelar)
        principal.addWidget(self.botoes)

        self.combo_area.currentIndexChanged.connect(self.atualizar_area)
        self.preselecionar_ativa()

    def cancelar(self):
        self.cancelamento_explicito = True
        self.reject()

    def camada_area(self):
        cid = self.combo_area.currentData()
        return QgsProject.instance().mapLayer(cid) if cid else None

    def preselecionar_ativa(self):
        ativa = iface.activeLayer()
        if ativa is not None:
            indice = self.combo_area.findData(ativa.id())
            if indice >= 0:
                self.combo_area.setCurrentIndex(indice)
                return
        self.atualizar_area()

    def atualizar_area(self):
        camada = self.camada_area()
        if camada is None:
            self.info_crs.setText("CRS nao definido")
            self.estado.setText("Selecione a camada da area de consulta.")
            self.radio_sel.setEnabled(False)
            self.radio_todas.setChecked(True)
            return
        self.info_crs.setText(crs_texto(camada))
        n = camada.selectedFeatureCount()
        self.radio_sel.setText(f"Usar uma unica feicao selecionada ({n} selecionada(s))")
        self.radio_sel.setEnabled(n == 1)
        if n == 1:
            self.radio_sel.setChecked(True)
            self.estado.setText("Area de consulta definida. Configure pelo menos um tema.")
            self.estado.setStyleSheet("QLabel { color: #176b2c; font-weight: bold; padding: 6px; }")
        else:
            self.radio_todas.setChecked(True)
            self.estado.setText(
                "Area definida. Como nao ha exatamente uma feicao selecionada, "
                "sera usado o modo Dissolver todas as feicoes."
            )
            self.estado.setStyleSheet("QLabel { color: #8a5a00; font-weight: bold; padding: 6px; }")

    def validar(self):
        erros, avisos = [], []
        area = self.camada_area()
        if area is None:
            self.estado.setText("Selecione a camada da area de consulta antes de continuar.")
            QMessageBox.warning(self, "Area de consulta nao selecionada", "Selecione a camada da area de consulta.")
            self.combo_area.setFocus()
            return
        if not area.crs().isValid():
            erros.append("A area de consulta nao possui CRS valido.")
        if self.radio_sel.isChecked() and area.selectedFeatureCount() != 1:
            erros.append("Selecione exatamente uma feicao ou use Dissolver todas.")
        vazias, invalidas = contar_problemas(area, self.radio_sel.isChecked())
        if vazias: erros.append(f"A area possui {vazias} geometria(s) vazia(s).")
        if invalidas: erros.append(f"A area possui {invalidas} geometria(s) invalida(s).")

        ativos = [b for b in self.blocos if b.grupo.isChecked()]
        if not ativos:
            erros.append("Ative pelo menos um tema ambiental.")
        for b in ativos:
            camada = b.camada()
            if camada is None:
                erros.append(f"{b.titulo}: selecione a camada tematica.")
                continue
            if not camada.crs().isValid(): erros.append(f"{b.titulo}: CRS invalido.")
            if not b.combo_campo.currentData(): erros.append(f"{b.titulo}: selecione o campo de classe.")
            if not b.fonte.text().strip(): erros.append(f"{b.titulo}: informe a fonte.")
            if not b.escala.text().strip(): avisos.append(f"{b.titulo}: escala nao informada.")
            v, i = contar_problemas(camada)
            if v: avisos.append(f"{b.titulo}: {v} geometria(s) vazia(s).")
            if i: erros.append(f"{b.titulo}: {i} geometria(s) invalida(s).")
            if area.crs().isValid() and camada.crs().isValid() and not area.extent().intersects(camada.extent()):
                avisos.append(f"{b.titulo}: extensoes sem intersecao aparente.")

        if erros:
            QMessageBox.critical(self, "Configuracao invalida", "Corrija:\n\n" + "\n".join(f"- {e}" for e in erros))
            return
        if avisos:
            resp = QMessageBox.question(self, "Configuracao com avisos", "\n".join(f"- {a}" for a in avisos) + "\n\nContinuar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if resp != QMessageBox.Yes: return
        self.accept()

    def resultado(self):
        area = self.camada_area()
        return {
            "versao": VERSAO,
            "area": {"camada_nome": area.name(), "crs": area.crs().authid(),
                     "modo": "FEICAO_SELECIONADA" if self.radio_sel.isChecked() else "DISSOLVER_TODAS"},
            "temas": [b.resultado() for b in self.blocos if b.grupo.isChecked()]
        }


try:
    print("\n" + "=" * 76)
    print("CONSULTOR DE CARACTERIZACAO AMBIENTAL")
    print("ETAPA 01 REVISADA - CONFIGURACAO E VALIDACAO")
    print("=" * 76)
    camadas = camadas_poligonais()
    if len(camadas) < 2:
        raise Exception("Carregue pelo menos duas camadas poligonais validas.")
    janela = JanelaConsultor(camadas, iface.mainWindow())
    resultado = janela.exec_()
    if resultado != QDialog.Accepted:
        if janela.cancelamento_explicito:
            print("Configuracao cancelada pelo usuario.")
        else:
            print("Janela fechada sem validar a configuracao.")
    else:
        plano = janela.resultado()
        print("\nPLANO VALIDADO")
        print(f"Area: {plano['area']['camada_nome']}")
        print(f"CRS: {plano['area']['crs']}")
        print(f"Modo: {plano['area']['modo']}")
        for tema in plano["temas"]:
            print(f"Tema: {tema['tema']} | Camada: {tema['camada_nome']} | Campo: {tema['campo_classe']} | Fonte: {tema['fonte']} | Escala: {tema['escala'] or 'NAO INFORMADA'}")
        QMessageBox.information(iface.mainWindow(), "Plano validado", "Configuracao validada. Nenhuma camada foi alterada e nenhum arquivo foi criado.")
except Exception as erro:
    print("ERRO: " + str(erro))
    QMessageBox.critical(iface.mainWindow(), "Erro no Consultor Ambiental", str(erro))
