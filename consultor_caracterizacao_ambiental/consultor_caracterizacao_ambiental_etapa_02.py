# -*- coding: utf-8 -*-
"""
===============================================================================
Consultor de Caracterizacao Ambiental
Etapa 02 - Validacao semantica e preparacao espacial
Versao: 0.1.0-alpha.3
Autor: Eloizio Dantas

Executa:
- selecao da area e de ate tres temas vetoriais poligonais locais;
- validacao geometrica e semantica do campo de classe;
- alerta para campos identificadores, como OBJECTID, FID e GID;
- amostra de valores distintos e razao de unicidade;
- copia ou dissolucao da area, sem alterar a origem;
- definicao automatica e visivel do CRS projetado de calculo;
- transformacao apenas da copia da geometria;
- calculo da area-base em m2, ha e km2;
- geracao de consulta_id;
- verificacao geometrica real de cobertura de cada tema.

Nao cria arquivos e nao altera camadas.
===============================================================================
"""

import math
import re
import uuid
from datetime import datetime

from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry,
    QgsMapLayerType, QgsPointXY, QgsProject, QgsUnitTypes, QgsWkbTypes
)
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QMessageBox, QRadioButton, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget
)
from qgis.utils import iface

VERSAO = "0.1.0-alpha.3"
TEMAS = (("geologia", "Geologia"), ("geomorfologia", "Geomorfologia"), ("pedologia", "Pedologia"))
NOMES_IDENTIFICADORES = {
    "id", "fid", "gid", "objectid", "object_id", "oid", "pk", "uuid",
    "globalid", "global_id", "codigo", "cod", "id_objeto", "shapeid"
}
LIMITE_AMOSTRA = 10


def camadas_poligonais():
    return sorted([
        c for c in QgsProject.instance().mapLayers().values()
        if c.type() == QgsMapLayerType.VectorLayer and c.isValid() and c.isSpatial()
        and QgsWkbTypes.geometryType(c.wkbType()) == QgsWkbTypes.PolygonGeometry
    ], key=lambda c: c.name().lower())


def crs_texto(c):
    return f"{c.crs().authid()} - {c.crs().description()}" if c and c.crs().isValid() else "CRS nao identificado"


def campo_normalizado(nome):
    return re.sub(r"[^a-z0-9]+", "_", str(nome).lower()).strip("_")


def geometria_area(camada, somente_selecionada):
    """Copia e, quando necessario, dissolve a area sem alterar a origem."""
    feicoes = list(camada.getSelectedFeatures()) if somente_selecionada else list(camada.getFeatures())
    if somente_selecionada and len(feicoes) != 1:
        raise Exception("O modo selecionado exige exatamente uma feicao selecionada.")
    geometrias = []
    for f in feicoes:
        g = f.geometry()
        if g is None or g.isNull() or g.isEmpty():
            raise Exception(f"A area de consulta contem geometria vazia na feicao {f.id()}.")
        try:
            if not g.isGeosValid():
                raise Exception(f"A area de consulta contem geometria invalida na feicao {f.id()}.")
        except AttributeError:
            pass
        geometrias.append(QgsGeometry(g))
    if not geometrias:
        raise Exception("Nao ha geometria disponivel para formar a area de consulta.")
    resultado = geometrias[0] if len(geometrias) == 1 else QgsGeometry.unaryUnion(geometrias)
    if resultado is None or resultado.isNull() or resultado.isEmpty():
        raise Exception("A uniao das geometrias resultou em uma area vazia.")
    try:
        if not resultado.isGeosValid():
            raise Exception("A geometria consolidada da area de consulta e invalida.")
    except AttributeError:
        pass
    return resultado, len(feicoes)


def sugerir_crs_calculo(crs_origem, geometria_origem):
    """Mantem CRS projetado em metros ou sugere SIRGAS 2000 / UTM Sul."""
    if crs_origem.isValid() and crs_origem.isGeographic() is False:
        try:
            if crs_origem.mapUnits() == QgsUnitTypes.DistanceMeters:
                return QgsCoordinateReferenceSystem(crs_origem), "CRS projetado metrico da area de consulta"
        except Exception:
            pass
    crs_geo = QgsCoordinateReferenceSystem("EPSG:4674")
    centro = geometria_origem.centroid()
    if centro.isNull() or centro.isEmpty():
        raise Exception("Nao foi possivel determinar o centro da area para sugerir o CRS.")
    ponto = centro.asPoint()
    transf = QgsCoordinateTransform(crs_origem, crs_geo, QgsProject.instance().transformContext())
    p_geo = transf.transform(QgsPointXY(ponto))
    lon, lat = p_geo.x(), p_geo.y()
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise Exception("As coordenadas transformadas para SIRGAS 2000 sao invalidas.")
    zona = int(math.floor((lon + 180.0) / 6.0) + 1)
    if lat >= 0:
        raise Exception("A sugestao automatica desta versao cobre apenas o hemisferio Sul.")
    epsg = 31960 + zona
    crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
    if not crs.isValid():
        raise Exception(f"Nao foi possivel criar o CRS SIRGAS 2000 / UTM zona {zona}S.")
    return crs, f"Sugerido pelo centro da area: longitude {lon:.6f}, latitude {lat:.6f}, zona {zona}S"


def transformar_geometria(geometria, crs_origem, crs_destino):
    copia = QgsGeometry(geometria)
    if crs_origem != crs_destino:
        t = QgsCoordinateTransform(crs_origem, crs_destino, QgsProject.instance().transformContext())
        retorno = copia.transform(t)
        if retorno != 0:
            raise Exception("Falha ao transformar a geometria para o CRS de calculo.")
    return copia


def analisar_campo(camada, nome_campo):
    """Avalia se o campo se comporta como classe ou identificador."""
    idx = camada.fields().indexFromName(nome_campo)
    if idx < 0:
        raise Exception(f"O campo '{nome_campo}' nao existe na camada '{camada.name()}'.")
    total = preenchidos = nulos = 0
    distintos = set()
    for f in camada.getFeatures():
        total += 1
        valor = f[idx]
        if valor is None or str(valor).strip() == "":
            nulos += 1
            continue
        preenchidos += 1
        distintos.add(str(valor).strip())
    razao = len(distintos) / preenchidos if preenchidos else 0.0
    suspeitas = []
    if campo_normalizado(nome_campo) in NOMES_IDENTIFICADORES:
        suspeitas.append("O nome do campo e tipico de identificador.")
    if preenchidos and razao > 0.70:
        suspeitas.append(f"A razao de unicidade e alta ({razao * 100:.1f}%).")
    if preenchidos == 0:
        suspeitas.append("O campo nao possui valores preenchidos.")
    valores = sorted(distintos, key=lambda x: x.lower())[:LIMITE_AMOSTRA]
    return {
        "total": total, "preenchidos": preenchidos, "nulos": nulos,
        "distintos": len(distintos), "razao_unicidade": razao,
        "amostra": valores, "suspeitas": suspeitas,
        "provavel_identificador": bool(suspeitas and (razao > 0.70 or campo_normalizado(nome_campo) in NOMES_IDENTIFICADORES))
    }


def cobertura_real(camada_tema, geometria_area_calc, crs_calc):
    """Verifica intersecao geometrica real, transformando o tema para o CRS de calculo."""
    t = QgsCoordinateTransform(camada_tema.crs(), crs_calc, QgsProject.instance().transformContext())
    encontradas = 0
    for f in camada_tema.getFeatures():
        g = f.geometry()
        if g is None or g.isNull() or g.isEmpty():
            continue
        copia = QgsGeometry(g)
        if camada_tema.crs() != crs_calc:
            if copia.transform(t) != 0:
                continue
        if copia.intersects(geometria_area_calc):
            encontradas += 1
    return encontradas


class TemaUI:
    def __init__(self, tema_id, titulo, camadas):
        self.tema_id, self.titulo = tema_id, titulo
        self.grupo = QGroupBox(titulo); self.grupo.setCheckable(True); self.grupo.setChecked(tema_id == "geologia")
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
        cid = self.camada_cb.currentData(); return QgsProject.instance().mapLayer(cid) if cid else None
    def atualizar(self):
        c = self.camada(); self.campo_cb.clear()
        if c is None:
            self.campo_cb.addItem("Selecione a camada primeiro", None); self.campo_cb.setEnabled(False); return
        self.campo_cb.addItem("Selecione o campo...", None)
        for f in c.fields(): self.campo_cb.addItem(f"{f.name()} ({f.typeName()})", f.name())
        self.campo_cb.setEnabled(True)


class JanelaEtapa2(QDialog):
    def __init__(self, camadas, parent=None):
        super().__init__(parent); self.camadas = camadas; self.plano = None
        self.setWindowTitle("Consultor Ambiental - Etapa 02"); self.resize(760, 760); self.setWindowModality(Qt.ApplicationModal)
        principal = QVBoxLayout(self)
        intro = QLabel("Selecione a area e os temas. O script avaliara o campo de classe, preparara uma copia da geometria e calculara a area-base.")
        intro.setWordWrap(True); principal.addWidget(intro)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); conteudo = QWidget(); corpo = QVBoxLayout(conteudo)
        ga = QGroupBox("Area de consulta"); fa = QFormLayout(ga)
        self.area_cb = QComboBox(); self.area_cb.addItem("Selecione...", None)
        for c in camadas: self.area_cb.addItem(c.name(), c.id())
        self.sel_rb = QRadioButton("Usar uma unica feicao selecionada"); self.todas_rb = QRadioButton("Dissolver todas as feicoes"); self.todas_rb.setChecked(True)
        self.area_info = QLabel("Selecione a area."); self.area_info.setWordWrap(True)
        fa.addRow("Camada:", self.area_cb); fa.addRow("Escopo:", self.sel_rb); fa.addRow("", self.todas_rb); fa.addRow("Situacao:", self.area_info)
        corpo.addWidget(ga)
        self.temas=[]
        for tid,titulo in TEMAS:
            ui=TemaUI(tid,titulo,camadas); self.temas.append(ui); corpo.addWidget(ui.grupo)
        corpo.addStretch(1); scroll.setWidget(conteudo); principal.addWidget(scroll)
        self.saida = QTextEdit(); self.saida.setReadOnly(True); self.saida.setMaximumHeight(190); self.saida.setPlaceholderText("O diagnostico aparecera aqui apos a validacao.")
        principal.addWidget(self.saida)
        botoes=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); botoes.button(QDialogButtonBox.Ok).setText("Preparar e validar")
        botoes.accepted.connect(self.validar); botoes.rejected.connect(self.reject); principal.addWidget(botoes)
        self.area_cb.currentIndexChanged.connect(self.atualizar_area); self.preselecionar()
    def area(self):
        cid=self.area_cb.currentData(); return QgsProject.instance().mapLayer(cid) if cid else None
    def preselecionar(self):
        ativa=iface.activeLayer(); idx=self.area_cb.findData(ativa.id()) if ativa else -1
        if idx>=0:self.area_cb.setCurrentIndex(idx)
        else:self.atualizar_area()
    def atualizar_area(self):
        c=self.area()
        if c is None:
            self.area_info.setText("Selecione a camada da area de consulta."); self.sel_rb.setEnabled(False); self.todas_rb.setChecked(True); return
        n=c.selectedFeatureCount(); self.sel_rb.setText(f"Usar uma unica feicao selecionada ({n})"); self.sel_rb.setEnabled(n==1)
        if n==1:self.sel_rb.setChecked(True)
        else:self.todas_rb.setChecked(True)
        self.area_info.setText(f"{crs_texto(c)} | {c.featureCount()} feicao(oes)")
    def validar(self):
        try:
            area=self.area()
            if area is None: raise Exception("Selecione a camada da area de consulta.")
            if not area.crs().isValid(): raise Exception("A area nao possui CRS valido.")
            ativos=[t for t in self.temas if t.grupo.isChecked()]
            if not ativos: raise Exception("Ative pelo menos um tema.")
            g_orig,n_feicoes=geometria_area(area,self.sel_rb.isChecked())
            crs_calc,motivo=sugerir_crs_calculo(area.crs(),g_orig)
            g_calc=transformar_geometria(g_orig,area.crs(),crs_calc)
            area_m2=abs(g_calc.area())
            if not math.isfinite(area_m2) or area_m2<=0: raise Exception("A area calculada e nula ou invalida.")
            consulta_id="CONS_"+datetime.now().strftime("%Y%m%d_%H%M%S_")+uuid.uuid4().hex[:6].upper()
            resultados=[]; avisos=[]; linhas=[]
            for t in ativos:
                c=t.camada(); campo=t.campo_cb.currentData()
                if c is None: raise Exception(f"{t.titulo}: selecione a camada.")
                if not c.crs().isValid(): raise Exception(f"{t.titulo}: CRS invalido.")
                if not campo: raise Exception(f"{t.titulo}: selecione o campo de classe.")
                if not t.fonte.text().strip(): raise Exception(f"{t.titulo}: informe a fonte.")
                analise=analisar_campo(c,campo); inter=cobertura_real(c,g_calc,crs_calc)
                if analise["preenchidos"]==0: raise Exception(f"{t.titulo}: o campo '{campo}' nao possui valores.")
                if analise["provavel_identificador"]:
                    avisos.append(f"{t.titulo}: '{campo}' parece identificador. Revise a escolha.")
                if analise["nulos"]: avisos.append(f"{t.titulo}: {analise['nulos']} valor(es) nulo(s).")
                if inter==0: avisos.append(f"{t.titulo}: nenhuma feicao intercepta geometricamente a area.")
                resultados.append({"tema":t.titulo,"camada":c.name(),"campo":campo,"fonte":t.fonte.text().strip(),"data_base":t.data.date().toString("yyyy-MM-dd"),"escala":t.escala.text().strip(),"analise":analise,"feicoes_intersectantes":inter})
                amostra=", ".join(analise["amostra"]) or "sem valores"
                linhas.append(f"{t.titulo}: campo={campo}; distintos={analise['distintos']}; unicidade={analise['razao_unicidade']*100:.1f}%; nulos={analise['nulos']}; intersecoes={inter}; amostra={amostra}")
            self.plano={"consulta_id":consulta_id,"area_camada":area.name(),"modo":"FEICAO_SELECIONADA" if self.sel_rb.isChecked() else "DISSOLVER_TODAS","feicoes_area":n_feicoes,"crs_origem":area.crs().authid(),"crs_calculo":crs_calc.authid(),"motivo_crs":motivo,"area_m2":area_m2,"area_ha":area_m2/10000.0,"area_km2":area_m2/1000000.0,"temas":resultados}
            texto=f"Consulta: {consulta_id}\nArea: {area_m2/10000.0:.4f} ha\nCRS calculo: {crs_calc.authid()}\n"+"\n".join(linhas)
            self.saida.setPlainText(texto)
            if avisos:
                resp=QMessageBox.question(self,"Validacao com avisos","\n".join("- "+a for a in avisos)+"\n\nAceitar mesmo assim?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
                if resp!=QMessageBox.Yes:return
            self.accept()
        except Exception as e:
            QMessageBox.critical(self,"Falha na validacao",str(e))


try:
    print("\n"+"="*76); print("CONSULTOR DE CARACTERIZACAO AMBIENTAL"); print("ETAPA 02 - VALIDACAO SEMANTICA E PREPARACAO ESPACIAL"); print("="*76)
    camadas=camadas_poligonais()
    if len(camadas)<2: raise Exception("Carregue pelo menos duas camadas poligonais validas.")
    janela=JanelaEtapa2(camadas,iface.mainWindow())
    if janela.exec_()!=QDialog.Accepted:
        print("Etapa 02 cancelada pelo usuario.")
    else:
        p=janela.plano
        print("\nAREA DE CONSULTA PREPARADA")
        print(f"Consulta ID: {p['consulta_id']}")
        print(f"Camada: {p['area_camada']}")
        print(f"Modo: {p['modo']} | Feicoes utilizadas: {p['feicoes_area']}")
        print(f"CRS origem: {p['crs_origem']}")
        print(f"CRS calculo: {p['crs_calculo']} | {p['motivo_crs']}")
        print(f"Area: {p['area_m2']:.3f} m2 | {p['area_ha']:.4f} ha | {p['area_km2']:.3f} km2")
        for t in p["temas"]:
            a=t["analise"]
            print(f"Tema: {t['tema']} | Campo: {t['campo']} | Distintos: {a['distintos']} | Unicidade: {a['razao_unicidade']*100:.1f}% | Nulos: {a['nulos']} | Feicoes intersectantes: {t['feicoes_intersectantes']}")
            print("  Amostra: "+(", ".join(a["amostra"]) or "sem valores"))
            for s in a["suspeitas"]: print("  Aviso: "+s)
        QMessageBox.information(iface.mainWindow(),"Etapa 02 concluida",f"Area preparada e validada.\n\nConsulta: {p['consulta_id']}\nArea: {p['area_ha']:.4f} ha\nCRS de calculo: {p['crs_calculo']}\n\nNenhuma camada foi alterada e nenhum arquivo foi criado.")
except Exception as e:
    print("ERRO: "+str(e)); QMessageBox.critical(iface.mainWindow(),"Erro na Etapa 02",str(e))
