# -*- coding: utf-8 -*-
"""
===============================================================================
Consultor de Caracterizacao Ambiental
Etapa 03 - Motor de caracterizacao tematica em memoria
Versao: 0.1.0-alpha.4
Autor: Eloizio Dantas

Executa:
- configuracao da area de consulta e de ate tres temas poligonais locais;
- validacao semantica resumida do campo de classe;
- copia ou dissolucao da area de consulta;
- definicao de CRS projetado metrico para calculo;
- intersecao real entre area e camadas tematicas;
- agrupamento e uniao por classe;
- area e percentual por classe;
- cobertura, area sem cobertura e sobreposicao entre classes;
- classificacao de predominancia ou mosaico;
- exibicao dos resultados no console e em tabela de previa.

Nao cria arquivos e nao altera as camadas originais.
===============================================================================
"""

import math
import re
import uuid
from collections import defaultdict
from datetime import datetime

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeatureRequest,
    QgsGeometry, QgsMapLayerType, QgsPointXY, QgsProject, QgsRectangle,
    QgsUnitTypes, QgsWkbTypes
)
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QGroupBox, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QRadioButton, QScrollArea, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget
)
from qgis.utils import iface

VERSAO = "0.1.0-alpha.4"
TEMAS = (("geologia", "Geologia"), ("geomorfologia", "Geomorfologia"), ("pedologia", "Pedologia"))
IDENTIFICADORES = {
    "id", "fid", "gid", "objectid", "object_id", "oid", "pk", "uuid",
    "globalid", "global_id", "codigo", "cod", "id_objeto", "shapeid"
}
TOLERANCIA_AREA_M2 = 1.0
TOLERANCIA_PERCENTUAL = 0.01
LIMITE_AMOSTRA = 10


def camadas_poligonais():
    return sorted([
        c for c in QgsProject.instance().mapLayers().values()
        if c.type() == QgsMapLayerType.VectorLayer and c.isValid()
        and c.isSpatial()
        and QgsWkbTypes.geometryType(c.wkbType()) == QgsWkbTypes.PolygonGeometry
    ], key=lambda c: c.name().lower())


def crs_texto(camada):
    if camada is None or not camada.crs().isValid():
        return "CRS nao identificado"
    return f"{camada.crs().authid()} - {camada.crs().description()}"


def nome_normalizado(nome):
    return re.sub(r"[^a-z0-9]+", "_", str(nome).lower()).strip("_")


def numero_br(valor, casas):
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def geometria_consulta(camada, somente_selecionada):
    feicoes = list(camada.getSelectedFeatures()) if somente_selecionada else list(camada.getFeatures())
    if somente_selecionada and len(feicoes) != 1:
        raise Exception("O modo selecionado exige exatamente uma feicao selecionada.")
    geometrias = []
    for feicao in feicoes:
        geometria = feicao.geometry()
        if geometria is None or geometria.isNull() or geometria.isEmpty():
            raise Exception(f"A area de consulta possui geometria vazia na feicao {feicao.id()}.")
        if not geometria.isGeosValid():
            raise Exception(f"A area de consulta possui geometria invalida na feicao {feicao.id()}.")
        geometrias.append(QgsGeometry(geometria))
    if not geometrias:
        raise Exception("Nao ha geometria disponivel para a area de consulta.")
    resultado = geometrias[0] if len(geometrias) == 1 else QgsGeometry.unaryUnion(geometrias)
    if resultado is None or resultado.isNull() or resultado.isEmpty():
        raise Exception("A consolidacao da area resultou em geometria vazia.")
    if not resultado.isGeosValid():
        raise Exception("A geometria consolidada da area e invalida.")
    return resultado, len(feicoes)


def sugerir_crs_calculo(crs_origem, geometria):
    if not crs_origem.isGeographic():
        try:
            if crs_origem.mapUnits() == QgsUnitTypes.DistanceMeters:
                return QgsCoordinateReferenceSystem(crs_origem), "CRS projetado metrico da area"
        except Exception:
            pass
    crs_geo = QgsCoordinateReferenceSystem("EPSG:4674")
    centro = geometria.centroid()
    if centro.isNull() or centro.isEmpty():
        raise Exception("Nao foi possivel determinar o centro da area.")
    p = centro.asPoint()
    transformacao = QgsCoordinateTransform(crs_origem, crs_geo, QgsProject.instance().transformContext())
    pg = transformacao.transform(QgsPointXY(p))
    lon, lat = pg.x(), pg.y()
    zona = int(math.floor((lon + 180.0) / 6.0) + 1)
    if lat >= 0:
        raise Exception("A sugestao automatica desta etapa cobre apenas o hemisferio Sul.")
    epsg = 31960 + zona
    crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
    if not crs.isValid():
        raise Exception(f"Nao foi possivel criar o CRS SIRGAS 2000 / UTM zona {zona}S.")
    return crs, f"Sugerido pelo centro da area, zona {zona}S"


def transformar_geometria(geometria, origem, destino):
    copia = QgsGeometry(geometria)
    if origem != destino:
        tr = QgsCoordinateTransform(origem, destino, QgsProject.instance().transformContext())
        if copia.transform(tr) != 0:
            raise Exception("Falha na transformacao da geometria.")
    return copia


def analisar_campo(camada, campo):
    indice = camada.fields().indexFromName(campo)
    if indice < 0:
        raise Exception(f"Campo '{campo}' nao encontrado em '{camada.name()}'.")
    total = preenchidos = nulos = 0
    distintos = set()
    for f in camada.getFeatures():
        total += 1
        valor = f[indice]
        if valor is None or str(valor).strip() == "":
            nulos += 1
        else:
            preenchidos += 1
            distintos.add(str(valor).strip())
    razao = len(distintos) / preenchidos if preenchidos else 0.0
    alertas = []
    if nome_normalizado(campo) in IDENTIFICADORES:
        alertas.append("nome tipico de identificador")
    if preenchidos and razao > 0.70:
        alertas.append(f"unicidade elevada ({razao * 100:.1f}%)")
    return {
        "total": total, "preenchidos": preenchidos, "nulos": nulos,
        "distintos": len(distintos), "razao": razao,
        "amostra": sorted(distintos, key=lambda x: x.lower())[:LIMITE_AMOSTRA],
        "alertas": alertas,
        "suspeito": bool(alertas)
    }


def retangulo_no_crs(retangulo, crs_origem, crs_destino):
    if crs_origem == crs_destino:
        return QgsRectangle(retangulo)
    tr = QgsCoordinateTransform(crs_origem, crs_destino, QgsProject.instance().transformContext())
    return tr.transformBoundingBox(retangulo)


def classe_da_feicao(feicao, indice):
    valor = feicao[indice]
    if valor is None or str(valor).strip() == "":
        return "SEM_CLASSE"
    return str(valor).strip()


def uniao_segura(geometrias, contexto):
    if not geometrias:
        return None
    uniao = geometrias[0] if len(geometrias) == 1 else QgsGeometry.unaryUnion(geometrias)
    if uniao is None or uniao.isNull() or uniao.isEmpty():
        raise Exception(f"A uniao geometrica falhou em {contexto}.")
    return uniao


def processar_tema(camada, campo, geometria_area, crs_calculo, area_total_m2):
    """Calcula classes, cobertura e sobreposicao, sem gravar resultados."""
    indice = camada.fields().indexFromName(campo)
    if indice < 0:
        raise Exception(f"Campo '{campo}' nao localizado em '{camada.name()}'.")

    transformacao = QgsCoordinateTransform(camada.crs(), crs_calculo, QgsProject.instance().transformContext())
    bbox_fonte = retangulo_no_crs(geometria_area.boundingBox(), crs_calculo, camada.crs())
    requisicao = QgsFeatureRequest().setFilterRect(bbox_fonte)

    por_classe = defaultdict(list)
    feicoes_intersectantes = 0
    geometrias_invalidas = 0
    falhas_intersecao = 0

    for feicao in camada.getFeatures(requisicao):
        geometria = feicao.geometry()
        if geometria is None or geometria.isNull() or geometria.isEmpty():
            continue
        if not geometria.isGeosValid():
            geometrias_invalidas += 1
            continue
        copia = QgsGeometry(geometria)
        if camada.crs() != crs_calculo and copia.transform(transformacao) != 0:
            falhas_intersecao += 1
            continue
        if not copia.intersects(geometria_area):
            continue
        try:
            recorte = copia.intersection(geometria_area)
        except Exception:
            falhas_intersecao += 1
            continue
        if recorte is None or recorte.isNull() or recorte.isEmpty():
            continue
        area = abs(recorte.area())
        if area <= TOLERANCIA_AREA_M2:
            continue
        feicoes_intersectantes += 1
        por_classe[classe_da_feicao(feicao, indice)].append(recorte)

    resultados = []
    unioes_classes = []
    soma_classes_m2 = 0.0

    for classe, geometrias in por_classe.items():
        uniao_classe = uniao_segura(geometrias, f"classe '{classe}'")
        area_classe = abs(uniao_classe.area())
        if area_classe <= TOLERANCIA_AREA_M2:
            continue
        percentual = area_classe / area_total_m2 * 100.0
        resultados.append({
            "classe": classe,
            "area_m2": area_classe,
            "area_ha": area_classe / 10000.0,
            "percentual": percentual,
            "geometria": uniao_classe,
            "predominante": False,
            "situacao": "SECUNDARIA"
        })
        soma_classes_m2 += area_classe
        unioes_classes.append(uniao_classe)

    if unioes_classes:
        uniao_cobertura = uniao_segura(unioes_classes, "cobertura tematica")
        cobertura_m2 = min(abs(uniao_cobertura.area()), area_total_m2)
    else:
        uniao_cobertura = None
        cobertura_m2 = 0.0

    sem_cobertura_m2 = max(area_total_m2 - cobertura_m2, 0.0)
    sobreposicao_m2 = max(soma_classes_m2 - cobertura_m2, 0.0)
    cobertura_pct = cobertura_m2 / area_total_m2 * 100.0
    sem_cobertura_pct = sem_cobertura_m2 / area_total_m2 * 100.0
    sobreposicao_pct = sobreposicao_m2 / area_total_m2 * 100.0

    if sem_cobertura_m2 > TOLERANCIA_AREA_M2:
        resultados.append({
            "classe": "SEM_COBERTURA",
            "area_m2": sem_cobertura_m2,
            "area_ha": sem_cobertura_m2 / 10000.0,
            "percentual": sem_cobertura_pct,
            "geometria": geometria_area.difference(uniao_cobertura) if uniao_cobertura else QgsGeometry(geometria_area),
            "predominante": False,
            "situacao": "LACUNA"
        })

    classes_validas = [r for r in resultados if r["classe"] != "SEM_COBERTURA"]
    classes_validas.sort(key=lambda r: r["area_m2"], reverse=True)
    if not classes_validas:
        resumo_predominancia = "SEM_COBERTURA"
    else:
        maior = classes_validas[0]
        if cobertura_pct < (100.0 - TOLERANCIA_PERCENTUAL):
            maior["predominante"] = True
            maior["situacao"] = "PREDOMINANTE_NA_AREA_COBERTA"
            resumo_predominancia = f"{maior['classe']} (na area coberta)"
        elif maior["percentual"] > 50.0:
            maior["predominante"] = True
            maior["situacao"] = "PREDOMINANTE"
            resumo_predominancia = maior["classe"]
        else:
            nomes = [r["classe"] for r in classes_validas[:2]]
            resumo_predominancia = "MOSAICO: " + " / ".join(nomes)
            for r in classes_validas[:2]:
                r["situacao"] = "MOSAICO"

    if sobreposicao_m2 > TOLERANCIA_AREA_M2:
        status = "SOBREPOSICAO_DETECTADA"
    elif cobertura_m2 <= TOLERANCIA_AREA_M2:
        status = "SEM_COBERTURA"
    elif sem_cobertura_m2 > TOLERANCIA_AREA_M2:
        status = "COBERTURA_PARCIAL"
    else:
        status = "COBERTURA_COMPLETA"

    resultados.sort(key=lambda r: (r["classe"] == "SEM_COBERTURA", -r["area_m2"]))
    return {
        "resultados": resultados,
        "feicoes_intersectantes": feicoes_intersectantes,
        "geometrias_invalidas_ignoradas": geometrias_invalidas,
        "falhas_intersecao": falhas_intersecao,
        "soma_classes_m2": soma_classes_m2,
        "cobertura_m2": cobertura_m2,
        "cobertura_pct": cobertura_pct,
        "sem_cobertura_m2": sem_cobertura_m2,
        "sem_cobertura_pct": sem_cobertura_pct,
        "sobreposicao_m2": sobreposicao_m2,
        "sobreposicao_pct": sobreposicao_pct,
        "predominancia": resumo_predominancia,
        "status": status
    }


class TemaUI:
    def __init__(self, tema_id, titulo, camadas):
        self.tema_id, self.titulo = tema_id, titulo
        self.grupo = QGroupBox(titulo)
        self.grupo.setCheckable(True)
        self.grupo.setChecked(tema_id == "geologia")
        form = QFormLayout(self.grupo)
        self.camada_cb = QComboBox(); self.camada_cb.addItem("Selecione...", None)
        for c in camadas: self.camada_cb.addItem(c.name(), c.id())
        self.campo_cb = QComboBox(); self.campo_cb.addItem("Selecione a camada primeiro", None); self.campo_cb.setEnabled(False)
        self.fonte = QLineEdit(); self.fonte.setPlaceholderText("Ex.: IBGE/BDIA")
        self.data = QDateEdit(QDate.currentDate()); self.data.setCalendarPopup(True); self.data.setDisplayFormat("dd/MM/yyyy")
        self.escala = QLineEdit(); self.escala.setPlaceholderText("Ex.: 1:250.000")
        form.addRow("Camada:", self.camada_cb); form.addRow("Campo de classe:", self.campo_cb)
        form.addRow("Fonte:", self.fonte); form.addRow("Data-base:", self.data); form.addRow("Escala:", self.escala)
        self.camada_cb.currentIndexChanged.connect(self.atualizar)
    def camada(self):
        cid = self.camada_cb.currentData()
        return QgsProject.instance().mapLayer(cid) if cid else None
    def atualizar(self):
        c = self.camada(); self.campo_cb.clear()
        if c is None:
            self.campo_cb.addItem("Selecione a camada primeiro", None); self.campo_cb.setEnabled(False); return
        self.campo_cb.addItem("Selecione o campo...", None)
        for campo in c.fields(): self.campo_cb.addItem(f"{campo.name()} ({campo.typeName()})", campo.name())
        self.campo_cb.setEnabled(True)


class JanelaResultado(QDialog):
    def __init__(self, plano, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Previa da Caracterizacao Tematica")
        self.resize(920, 620)
        layout = QVBoxLayout(self)
        cabecalho = QLabel(
            f"<b>Consulta:</b> {plano['consulta_id']}<br>"
            f"<b>Area:</b> {numero_br(plano['area_ha'], 4)} ha<br>"
            f"<b>CRS de calculo:</b> {plano['crs_calculo']}"
        )
        cabecalho.setWordWrap(True); layout.addWidget(cabecalho)
        tabela = QTableWidget(0, 6)
        tabela.setHorizontalHeaderLabels(["Tema", "Classe", "Area (ha)", "Percentual", "Situacao", "Status do tema"])
        tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        for tema in plano["temas"]:
            for r in tema["motor"]["resultados"]:
                linha = tabela.rowCount(); tabela.insertRow(linha)
                valores = [tema["tema"], r["classe"], numero_br(r["area_ha"], 4), numero_br(r["percentual"], 2) + "%", r["situacao"], tema["motor"]["status"]]
                for col, valor in enumerate(valores): tabela.setItem(linha, col, QTableWidgetItem(str(valor)))
        tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        tabela.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(tabela)
        resumo = QTextEdit(); resumo.setReadOnly(True)
        linhas = []
        for tema in plano["temas"]:
            m = tema["motor"]
            linhas.append(
                f"{tema['tema']}\n"
                f"  Predominancia: {m['predominancia']}\n"
                f"  Cobertura: {numero_br(m['cobertura_pct'], 2)}%\n"
                f"  Sem cobertura: {numero_br(m['sem_cobertura_m2']/10000.0, 4)} ha\n"
                f"  Sobreposicao: {numero_br(m['sobreposicao_m2']/10000.0, 4)} ha\n"
                f"  Status: {m['status']}\n"
            )
        resumo.setPlainText("\n".join(linhas)); resumo.setMaximumHeight(180); layout.addWidget(resumo)
        botoes = QDialogButtonBox(QDialogButtonBox.Close)
        botoes.rejected.connect(self.reject); botoes.accepted.connect(self.accept); layout.addWidget(botoes)


class JanelaEtapa3(QDialog):
    def __init__(self, camadas, parent=None):
        super().__init__(parent); self.plano = None
        self.setWindowTitle("Consultor Ambiental - Etapa 03"); self.resize(760, 740); self.setWindowModality(Qt.ApplicationModal)
        principal = QVBoxLayout(self)
        intro = QLabel("Configure a area e os temas. O motor calculara classes, areas, percentuais, cobertura, sobreposicao e predominancia somente em memoria.")
        intro.setWordWrap(True); principal.addWidget(intro)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); corpo = QWidget(); base = QVBoxLayout(corpo)
        ga = QGroupBox("Area de consulta"); fa = QFormLayout(ga)
        self.area_cb = QComboBox(); self.area_cb.addItem("Selecione...", None)
        for c in camadas: self.area_cb.addItem(c.name(), c.id())
        self.sel_rb = QRadioButton("Usar uma unica feicao selecionada"); self.todas_rb = QRadioButton("Dissolver todas as feicoes"); self.todas_rb.setChecked(True)
        self.area_info = QLabel("Selecione a area."); self.area_info.setWordWrap(True)
        fa.addRow("Camada:", self.area_cb); fa.addRow("Escopo:", self.sel_rb); fa.addRow("", self.todas_rb); fa.addRow("Situacao:", self.area_info)
        base.addWidget(ga)
        self.temas = []
        for tid, titulo in TEMAS:
            ui = TemaUI(tid, titulo, camadas); self.temas.append(ui); base.addWidget(ui.grupo)
        base.addStretch(1); scroll.setWidget(corpo); principal.addWidget(scroll)
        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("Calcular previa")
        botoes.accepted.connect(self.calcular); botoes.rejected.connect(self.reject); principal.addWidget(botoes)
        self.area_cb.currentIndexChanged.connect(self.atualizar_area); self.preselecionar()
    def area(self):
        cid = self.area_cb.currentData(); return QgsProject.instance().mapLayer(cid) if cid else None
    def preselecionar(self):
        ativa = iface.activeLayer(); idx = self.area_cb.findData(ativa.id()) if ativa else -1
        if idx >= 0: self.area_cb.setCurrentIndex(idx)
        else: self.atualizar_area()
    def atualizar_area(self):
        c = self.area()
        if c is None:
            self.area_info.setText("Selecione a camada da area."); self.sel_rb.setEnabled(False); self.todas_rb.setChecked(True); return
        n = c.selectedFeatureCount(); self.sel_rb.setText(f"Usar uma unica feicao selecionada ({n})"); self.sel_rb.setEnabled(n == 1)
        if n == 1: self.sel_rb.setChecked(True)
        else: self.todas_rb.setChecked(True)
        self.area_info.setText(f"{crs_texto(c)} | {c.featureCount()} feicao(oes)")
    def calcular(self):
        try:
            area = self.area()
            if area is None: raise Exception("Selecione a camada da area de consulta.")
            if not area.crs().isValid(): raise Exception("A area nao possui CRS valido.")
            ativos = [t for t in self.temas if t.grupo.isChecked()]
            if not ativos: raise Exception("Ative pelo menos um tema.")
            geom_orig, n_area = geometria_consulta(area, self.sel_rb.isChecked())
            crs_calc, motivo = sugerir_crs_calculo(area.crs(), geom_orig)
            geom_calc = transformar_geometria(geom_orig, area.crs(), crs_calc)
            area_m2 = abs(geom_calc.area())
            if area_m2 <= TOLERANCIA_AREA_M2: raise Exception("A area de consulta e nula ou muito pequena.")
            consulta_id = "CONS_" + datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6].upper()
            temas_saida = []; avisos = []
            for t in ativos:
                camada = t.camada(); campo = t.campo_cb.currentData()
                if camada is None: raise Exception(f"{t.titulo}: selecione a camada.")
                if not camada.crs().isValid(): raise Exception(f"{t.titulo}: CRS invalido.")
                if not campo: raise Exception(f"{t.titulo}: selecione o campo de classe.")
                if not t.fonte.text().strip(): raise Exception(f"{t.titulo}: informe a fonte.")
                semantica = analisar_campo(camada, campo)
                if semantica["preenchidos"] == 0: raise Exception(f"{t.titulo}: o campo nao possui valores preenchidos.")
                motor = processar_tema(camada, campo, geom_calc, crs_calc, area_m2)
                if semantica["suspeito"]: avisos.append(f"{t.titulo}: campo '{campo}' semanticamente suspeito ({'; '.join(semantica['alertas'])}).")
                if motor["sobreposicao_m2"] > TOLERANCIA_AREA_M2: avisos.append(f"{t.titulo}: sobreposicao interna de {motor['sobreposicao_m2']/10000.0:.4f} ha.")
                if motor["geometrias_invalidas_ignoradas"]: avisos.append(f"{t.titulo}: {motor['geometrias_invalidas_ignoradas']} geometria(s) invalida(s) ignorada(s).")
                temas_saida.append({
                    "tema_id": t.tema_id, "tema": t.titulo, "camada": camada.name(), "campo": campo,
                    "fonte": t.fonte.text().strip(), "data_base": t.data.date().toString("yyyy-MM-dd"),
                    "escala": t.escala.text().strip(), "semantica": semantica, "motor": motor
                })
            self.plano = {
                "consulta_id": consulta_id, "area_camada": area.name(),
                "modo": "FEICAO_SELECIONADA" if self.sel_rb.isChecked() else "DISSOLVER_TODAS",
                "feicoes_area": n_area, "crs_origem": area.crs().authid(), "crs_calculo": crs_calc.authid(),
                "motivo_crs": motivo, "area_m2": area_m2, "area_ha": area_m2/10000.0,
                "area_km2": area_m2/1000000.0, "temas": temas_saida
            }
            if avisos:
                resp = QMessageBox.question(self, "Previa com avisos", "\n".join("- " + a for a in avisos) + "\n\nExibir os resultados mesmo assim?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if resp != QMessageBox.Yes: return
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Falha no motor tematico", str(e))


try:
    print("\n" + "=" * 76)
    print("CONSULTOR DE CARACTERIZACAO AMBIENTAL")
    print("ETAPA 03 - MOTOR DE CARACTERIZACAO TEMATICA")
    print("=" * 76)
    camadas = camadas_poligonais()
    if len(camadas) < 2: raise Exception("Carregue pelo menos duas camadas poligonais validas.")
    janela = JanelaEtapa3(camadas, iface.mainWindow())
    if janela.exec_() != QDialog.Accepted:
        print("Etapa 03 cancelada pelo usuario.")
    else:
        p = janela.plano
        print("\nCARACTERIZACAO TEMATICA CALCULADA")
        print(f"Consulta ID: {p['consulta_id']}")
        print(f"Area: {numero_br(p['area_ha'],4)} ha | CRS: {p['crs_calculo']}")
        for tema in p["temas"]:
            m = tema["motor"]
            print("\n" + "-" * 72)
            print(f"Tema: {tema['tema']} | Campo: {tema['campo']} | Fonte: {tema['fonte']} | Escala: {tema['escala'] or 'NAO INFORMADA'}")
            print(f"Status: {m['status']} | Predominancia: {m['predominancia']}")
            print(f"Cobertura: {numero_br(m['cobertura_pct'],2)}% | Sem cobertura: {numero_br(m['sem_cobertura_m2']/10000.0,4)} ha")
            print(f"Sobreposicao: {numero_br(m['sobreposicao_m2']/10000.0,4)} ha ({numero_br(m['sobreposicao_pct'],2)}%)")
            print(f"Feicoes intersectantes: {m['feicoes_intersectantes']} | Invalidas ignoradas: {m['geometrias_invalidas_ignoradas']}")
            for r in m["resultados"]:
                print(f"  Classe: {r['classe']} | Area: {numero_br(r['area_ha'],4)} ha | Percentual: {numero_br(r['percentual'],2)}% | Situacao: {r['situacao']}")
        previa = JanelaResultado(p, iface.mainWindow())
        previa.exec_()
        QMessageBox.information(iface.mainWindow(), "Etapa 03 concluida", "Caracterizacao calculada somente em memoria. Nenhuma camada foi alterada e nenhum arquivo foi criado.")
except Exception as e:
    print("ERRO: " + str(e))
    QMessageBox.critical(iface.mainWindow(), "Erro na Etapa 03", str(e))
