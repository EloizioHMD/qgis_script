# -*- coding: utf-8 -*-
'''Gerador de Mapa Interativo QGIS v0.0.3.1

Gera um unico arquivo HTML para compartilhamento e exploracao de composicoes
vetoriais do projeto QGIS por usuarios nao especialistas.

Inclui:
- formulario de identificacao da publicacao;
- versao do mapa, data de referencia e responsavel tecnico;
- escopo: selecionadas, visiveis ou todas as camadas vetoriais;
- classificacao: publico, uso interno, confidencial ou restrito;
- aviso inicial de confidencialidade;
- abas Camadas, Detalhes e Sobre;
- metadados automaticos do projeto e da exportacao;
- identidade visual corporativa;
- nenhum recurso de download.

Aviso: os vetores e todos os atributos das camadas escolhidas ficam incorporados
no HTML. Esta versao nao oferece autenticacao nem impede extracao tecnica.
'''

import datetime
import html
import json
import os
import tempfile
import webbrowser

from qgis.core import (
    Qgis, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry,
    QgsMapLayerType, QgsProject, QgsWkbTypes
)
from qgis.PyQt.QtCore import QDate, Qt
from qgis.PyQt.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QRadioButton, QTextEdit, QVBoxLayout
)
from qgis.utils import iface

VERSAO_GERADOR = "0.0.3.1"
LOGO_URL = "https://cimentonacional.com.br/wp-content/uploads/2025/06/cropped-logo-cimento-nacional.png"
CORES_CAMADAS = ["#0071AE", "#05A8FF", "#0D3862", "#D1D1D1"]

TEXTOS_SIGILO = {
    "PUBLICO": {
        "rotulo": "Uso publico",
        "texto": "Este mapa foi preparado para consulta publica. As informacoes devem ser interpretadas conforme as fontes, datas, escalas e limitacoes declaradas na aba Sobre."
    },
    "INTERNO": {
        "rotulo": "Uso interno",
        "texto": "Este mapa interativo destina-se exclusivamente ao uso interno e aos usuarios autorizados. Nao redistribua, publique ou utilize seu conteudo fora da finalidade informada sem autorizacao do responsavel."
    },
    "CONFIDENCIAL": {
        "rotulo": "Confidencial",
        "texto": "Este mapa interativo destina-se exclusivamente aos usuarios autorizados e pode conter informacoes corporativas, confidenciais ou dados pessoais. E proibida a reproducao, distribuicao, publicacao, extracao ou utilizacao para finalidade diferente da autorizada. Caso tenha recebido este arquivo por engano, exclua-o e comunique imediatamente ao remetente."
    },
    "RESTRITO": {
        "rotulo": "Restrito",
        "texto": "Conteudo restrito. O acesso e o uso deste mapa sao permitidos somente aos destinatarios expressamente autorizados. Nao copie, encaminhe, publique, extraia ou reutilize as informacoes sem autorizacao formal. Caso tenha recebido o arquivo indevidamente, exclua-o e comunique ao remetente."
    },
}


def valor_json_seguro(valor):
    if valor is None or str(valor) == "NULL":
        return None
    if isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, (datetime.date, datetime.datetime, datetime.time)):
        return valor.isoformat()
    if hasattr(valor, "toString"):
        try:
            return valor.toString()
        except Exception:
            pass
    return str(valor)


def cor_da_camada(camada, indice):
    cor = CORES_CAMADAS[indice % len(CORES_CAMADAS)]
    try:
        renderer = camada.renderer()
        simbolo = renderer.symbol() if renderer and hasattr(renderer, "symbol") else None
        if simbolo and simbolo.color().isValid():
            cor = simbolo.color().name()
    except Exception:
        pass
    return cor


def tipo_geometria(camada):
    tipo = QgsWkbTypes.geometryType(camada.wkbType())
    if tipo == QgsWkbTypes.PointGeometry:
        return "Point"
    if tipo == QgsWkbTypes.LineGeometry:
        return "LineString"
    if tipo == QgsWkbTypes.PolygonGeometry:
        return "Polygon"
    return "Unknown"


def no_camada(projeto, camada):
    return projeto.layerTreeRoot().findLayer(camada.id())


def camada_visivel(projeto, camada):
    no = no_camada(projeto, camada)
    return no.itemVisibilityChecked() if no else True


def posicao_arvore(projeto, camada):
    no = no_camada(projeto, camada)
    posicoes = []
    while no is not None and no.parent() is not None:
        pai = no.parent()
        try:
            posicoes.append(pai.children().index(no))
        except ValueError:
            posicoes.append(0)
        no = pai
    return tuple(reversed(posicoes))


def camadas_por_escopo(escopo):
    projeto = QgsProject.instance()
    todas = [
        c for c in projeto.mapLayers().values()
        if c.type() == QgsMapLayerType.VectorLayer and c.isSpatial()
    ]
    if escopo == "SELECIONADAS":
        ids = {c.id() for c in iface.layerTreeView().selectedLayers()}
        escolhidas = [c for c in todas if c.id() in ids]
    elif escopo == "VISIVEIS":
        escolhidas = [c for c in todas if camada_visivel(projeto, c)]
    else:
        escolhidas = todas
    return sorted(escolhidas, key=lambda c: posicao_arvore(projeto, c))


def qgis_versao():
    try:
        return Qgis.QGIS_VERSION
    except Exception:
        return "Nao identificada"


class JanelaConfiguracao(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        projeto = QgsProject.instance()
        nome_projeto = os.path.splitext(os.path.basename(projeto.fileName()))[0] if projeto.fileName() else "Projeto QGIS"
        self.setWindowTitle("Gerador de Mapa Interativo QGIS v0.0.3.1")
        self.resize(700, 680)
        self.setWindowModality(Qt.ApplicationModal)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Configure a identificacao e o publico do mapa. O arquivo HTML incorporara "
            "as geometrias e todos os atributos das camadas escolhidas."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("QLabel { padding: 8px; background: #E8F6FD; color: #0D3862; border-left: 4px solid #0071AE; }")
        layout.addWidget(intro)

        grupo_id = QGroupBox("Identificacao da publicacao")
        form = QFormLayout(grupo_id)
        self.titulo = QLineEdit("Mapa Interativo Ambiental e Fundiario")
        self.subtitulo = QLineEdit(nome_projeto)
        self.descricao = QTextEdit()
        self.descricao.setMaximumHeight(85)
        self.descricao.setPlaceholderText("Objetivo, abrangencia e orientacao de uso do mapa.")
        self.unidade = QLineEdit()
        self.unidade.setPlaceholderText("Unidade, empreendimento ou local")
        self.processo = QLineEdit()
        self.processo.setPlaceholderText("Projeto, processo ou referencia")
        self.responsavel = QLineEdit("Eloizio Henrique de Medeiros Dantas")
        self.funcao = QLineEdit("Analista Licenciamento Ambiental Pl")
        self.area_responsavel = QLineEdit("Meio Ambiente")
        self.versao_mapa = QLineEdit("v001")
        self.data_referencia = QDateEdit(QDate.currentDate())
        self.data_referencia.setCalendarPopup(True)
        self.data_referencia.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Titulo*:", self.titulo)
        form.addRow("Subtitulo:", self.subtitulo)
        form.addRow("Descricao:", self.descricao)
        form.addRow("Unidade / empreendimento:", self.unidade)
        form.addRow("Projeto / processo:", self.processo)
        form.addRow("Responsavel tecnico*:", self.responsavel)
        form.addRow("Cargo / funcao:", self.funcao)
        form.addRow("Area responsavel:", self.area_responsavel)
        form.addRow("Versao do mapa*:", self.versao_mapa)
        form.addRow("Data de referencia*:", self.data_referencia)
        layout.addWidget(grupo_id)

        grupo_publicacao = QGroupBox("Conteudo e classificacao")
        form_pub = QFormLayout(grupo_publicacao)
        self.rb_selecionadas = QRadioButton("Somente camadas selecionadas no painel")
        self.rb_visiveis = QRadioButton("Somente camadas visiveis")
        self.rb_todas = QRadioButton("Todas as camadas vetoriais")
        self.rb_selecionadas.setChecked(True)
        form_pub.addRow("Escopo:", self.rb_selecionadas)
        form_pub.addRow("", self.rb_visiveis)
        form_pub.addRow("", self.rb_todas)
        self.sigilo = QComboBox()
        self.sigilo.addItem("Uso publico", "PUBLICO")
        self.sigilo.addItem("Uso interno", "INTERNO")
        self.sigilo.addItem("Confidencial", "CONFIDENCIAL")
        self.sigilo.addItem("Restrito", "RESTRITO")
        self.sigilo.setCurrentIndex(2)
        form_pub.addRow("Classificacao*:", self.sigilo)
        layout.addWidget(grupo_publicacao)

        grupo_saida = QGroupBox("Arquivo de saida")
        linha_saida = QHBoxLayout(grupo_saida)
        self.saida = QLineEdit(os.path.join(tempfile.gettempdir(), "mapa_interativo_qgis.html"))
        botao_saida = QPushButton("Selecionar...")
        botao_saida.clicked.connect(self.escolher_saida)
        linha_saida.addWidget(self.saida)
        linha_saida.addWidget(botao_saida)
        layout.addWidget(grupo_saida)

        self.resumo = QLabel()
        self.resumo.setWordWrap(True)
        self.resumo.setStyleSheet("QLabel { color: #0D3862; padding: 7px; }")
        layout.addWidget(self.resumo)
        self.rb_selecionadas.toggled.connect(self.atualizar_resumo)
        self.rb_visiveis.toggled.connect(self.atualizar_resumo)
        self.rb_todas.toggled.connect(self.atualizar_resumo)

        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("Gerar mapa interativo")
        botoes.accepted.connect(self.validar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)
        self.atualizar_resumo()

    def escopo(self):
        if self.rb_selecionadas.isChecked():
            return "SELECIONADAS"
        if self.rb_visiveis.isChecked():
            return "VISIVEIS"
        return "TODAS"

    def escolher_saida(self):
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar mapa interativo", self.saida.text(), "Arquivo HTML (*.html)"
        )
        if caminho:
            if not caminho.lower().endswith(".html"):
                caminho += ".html"
            self.saida.setText(caminho)

    def atualizar_resumo(self):
        camadas = camadas_por_escopo(self.escopo())
        feicoes = sum(c.featureCount() for c in camadas if c.isValid())
        self.resumo.setText(
            f"Previa: {len(camadas)} camada(s) vetorial(is), aproximadamente {feicoes} feicao(oes). "
            "Todos os respectivos campos serao incorporados nesta versao."
        )

    def validar(self):
        erros = []
        if not self.titulo.text().strip():
            erros.append("Informe o titulo.")
        if not self.responsavel.text().strip():
            erros.append("Informe o responsavel tecnico.")
        if not self.versao_mapa.text().strip():
            erros.append("Informe a versao do mapa.")
        if not self.saida.text().strip():
            erros.append("Defina o arquivo de saida.")
        camadas = camadas_por_escopo(self.escopo())
        if not camadas:
            erros.append("O escopo escolhido nao possui camadas vetoriais espaciais.")
        if erros:
            QMessageBox.warning(self, "Configuracao incompleta", "\n".join("- " + e for e in erros))
            return
        aviso = (
            "O HTML incorporara as geometrias e todos os atributos das camadas escolhidas. "
            "Remover botoes de download nao impede extracao tecnica dos dados.\n\n"
            "Confirme que o conteudo esta autorizado para o publico selecionado."
        )
        resposta = QMessageBox.question(
            self, "Revisao de compartilhamento", aviso,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if resposta == QMessageBox.Yes:
            self.accept()

    def configuracao(self):
        return {
            "titulo": self.titulo.text().strip(),
            "subtitulo": self.subtitulo.text().strip(),
            "descricao": self.descricao.toPlainText().strip(),
            "unidade": self.unidade.text().strip(),
            "processo": self.processo.text().strip(),
            "responsavel": self.responsavel.text().strip(),
            "funcao": self.funcao.text().strip(),
            "area_responsavel": self.area_responsavel.text().strip(),
            "versao_mapa": self.versao_mapa.text().strip(),
            "data_referencia": self.data_referencia.date().toString("dd/MM/yyyy"),
            "classificacao": self.sigilo.currentData(),
            "escopo": self.escopo(),
            "saida": os.path.abspath(self.saida.text().strip()),
        }


def exportar(config):
    projeto = QgsProject.instance()
    camadas = camadas_por_escopo(config["escopo"])
    crs_web = QgsCoordinateReferenceSystem("EPSG:4326")
    web_layers = []
    ignoradas = []

    for indice, camada in enumerate(camadas):
        if not camada.isValid() or not camada.crs().isValid():
            ignoradas.append(camada.name())
            continue
        transformacao = QgsCoordinateTransform(camada.crs(), crs_web, projeto.transformContext())
        campos = [f.name() for f in camada.fields()]
        features = []
        vazias = 0
        for feat in camada.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isNull() or geom.isEmpty():
                vazias += 1
                continue
            copia = QgsGeometry(geom)
            try:
                if camada.crs() != crs_web and copia.transform(transformacao) != 0:
                    vazias += 1
                    continue
                geom_json = json.loads(copia.asJson())
            except Exception:
                vazias += 1
                continue
            props = {campo: valor_json_seguro(feat[campo]) for campo in campos}
            features.append({"type": "Feature", "geometry": geom_json, "properties": props})
        web_layers.append({
            "id": "layer_" + str(len(web_layers)),
            "name": camada.name(),
            "color": cor_da_camada(camada, indice),
            "geom_type": tipo_geometria(camada),
            "visible": camada_visivel(projeto, camada),
            "feature_count": len(features),
            "empty_count": vazias,
            "source_crs": camada.crs().authid(),
            "data": {"type": "FeatureCollection", "features": features},
        })

    if not web_layers:
        raise Exception("Nenhuma camada valida foi exportada.")

    data_geracao = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    projeto_nome = os.path.basename(projeto.fileName()) if projeto.fileName() else "Projeto nao salvo"
    metadados = {
        **config,
        "data_geracao": data_geracao,
        "versao_gerador": VERSAO_GERADOR,
        "qgis": qgis_versao(),
        "projeto": projeto_nome,
        "crs_projeto": projeto.crs().authid() if projeto.crs().isValid() else "Nao identificado",
        "quantidade_camadas": len(web_layers),
        "quantidade_feicoes": sum(c["feature_count"] for c in web_layers),
        "classificacao_rotulo": TEXTOS_SIGILO[config["classificacao"]]["rotulo"],
        "aviso_sigilo": TEXTOS_SIGILO[config["classificacao"]]["texto"],
        "camadas_ignoradas": ignoradas,
    }

    dados_json = json.dumps(web_layers, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    meta_json = json.dumps(metadados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    template = r'''<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>:root{--w:#fff;--b:#0071AE;--n:#0D3862;--g:#D1D1D1;--c:#05A8FF}*{box-sizing:border-box}html,body{height:100%;margin:0;font-family:Arial,sans-serif}body{overflow:hidden;background:#f4f7f9;color:var(--n)}header{height:80px;background:var(--w);border-bottom:4px solid var(--b);display:flex;align-items:center;justify-content:space-between;padding:8px 22px;box-shadow:0 2px 10px #0d386229;z-index:1001;position:relative}.brand{display:flex;align-items:center;gap:18px;min-width:0}.brand img{width:178px;max-height:50px;object-fit:contain}.headcopy{border-left:1px solid var(--g);padding-left:18px;min-width:0}.headcopy h1{margin:0;font-size:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.headcopy p{margin:3px 0 0;color:#637887;font-size:12px}.headmeta{text-align:right}.badge{display:inline-block;padding:5px 9px;border-radius:999px;background:#e8f6fd;color:var(--b);font-size:11px;font-weight:bold}.version{font-size:10px;color:#637887;margin-top:5px}.app{display:flex;height:calc(100vh - 80px)}aside{width:350px;min-width:350px;background:var(--n);color:var(--w);display:flex;flex-direction:column;z-index:1000}.tabs{display:flex;border-bottom:1px solid #ffffff26}.tab{flex:1;border:0;background:transparent;color:var(--g);padding:14px 5px;cursor:pointer;font-weight:bold;font-size:11px;text-transform:uppercase;border-bottom:3px solid transparent}.tab.active{color:var(--w);border-bottom-color:var(--c);background:#05a8ff17}.panel{flex:1;overflow:auto;padding:16px}.hidden{display:none}.section{font-size:11px;font-weight:bold;color:var(--g);text-transform:uppercase;letter-spacing:.7px;margin-bottom:12px}.card{background:#ffffff14;border:1px solid #ffffff26;border-radius:9px;padding:12px;margin-bottom:10px}.row{display:flex;gap:9px;align-items:flex-start}.row input{accent-color:var(--c)}.sw{width:13px;height:13px;border-radius:50%;border:1px solid var(--w);flex:none}.copy{flex:1;min-width:0}.lname{font-size:13px;font-weight:bold;overflow-wrap:anywhere}.meta{font-size:10px;color:var(--g);margin-top:4px}.zoom{border:1px solid #ffffff4d;background:transparent;color:var(--w);border-radius:6px;padding:5px 7px;cursor:pointer}.opacity{display:flex;gap:8px;align-items:center;color:var(--g);font-size:10px;margin-top:10px}.opacity input{width:100%;accent-color:var(--c)}main{flex:1;position:relative;min-width:0}#map{height:100%;width:100%;background:var(--g)}.mapbadge{position:absolute;z-index:700;left:12px;bottom:12px;background:#fffffff2;color:var(--n);border-left:4px solid var(--c);padding:7px 10px;border-radius:5px;font-size:10px}.empty{color:var(--g);font-style:italic;font-size:13px;padding:14px;border:1px solid #ffffff26;border-radius:8px}.detailtitle{color:var(--c);font-size:11px;font-weight:bold;text-transform:uppercase;margin-bottom:10px}.attrs{width:100%;border-collapse:collapse;font-size:11px}.attrs td{padding:8px;border-bottom:1px solid #ffffff1f;vertical-align:top;overflow-wrap:anywhere}.attrs td:first-child{width:42%;color:var(--g);font-weight:bold;background:#00000014}.about h3{color:var(--c);font-size:12px;margin:15px 0 5px}.about p,.about li{font-size:12px;line-height:1.45;color:#eef5f8}.about dl{font-size:11px}.about dt{color:var(--g);font-weight:bold;margin-top:8px}.about dd{margin:2px 0 0;overflow-wrap:anywhere}.modal{position:fixed;inset:0;background:#0d3862e8;z-index:5000;display:flex;align-items:center;justify-content:center;padding:20px}.modalbox{max-width:620px;background:var(--w);border-radius:12px;box-shadow:0 20px 50px #0008;overflow:hidden}.modaltitle{background:var(--n);color:var(--w);padding:18px 22px;font-size:18px;font-weight:bold;border-bottom:4px solid var(--c)}.modalbody{padding:22px;color:#263f51;line-height:1.55;font-size:14px}.modalclass{display:inline-block;background:#e8f6fd;color:var(--b);padding:5px 9px;border-radius:99px;font-size:11px;font-weight:bold;margin-bottom:12px}.modalactions{display:flex;justify-content:flex-end;gap:10px;padding:0 22px 22px}.btn{border:0;border-radius:7px;padding:10px 14px;cursor:pointer;font-weight:bold}.primary{background:var(--b);color:var(--w)}.secondary{background:var(--g);color:var(--n)}@media(max-width:840px){aside{width:295px;min-width:295px}.brand img{width:120px}.headcopy p,.headmeta{display:none}}</style></head>
<body><div id="conf-modal" class="modal"><div class="modalbox"><div class="modaltitle"><i class="fa-solid fa-shield-halved"></i> Aviso de confidencialidade</div><div class="modalbody"><div id="modal-class" class="modalclass"></div><div id="modal-text"></div><p><strong>Ao continuar, o usuario declara estar ciente dessas condicoes.</strong></p></div><div class="modalactions"><button class="btn secondary" onclick="closeMap()">Fechar mapa</button><button class="btn primary" onclick="acceptNotice()">Estou ciente e desejo continuar</button></div></div></div>
<header><div class="brand"><img src="__LOGO__" alt="Cimento Nacional" referrerpolicy="no-referrer"><div class="headcopy"><h1 id="map-title"></h1><p id="map-subtitle"></p></div></div><div class="headmeta"><div id="class-badge" class="badge"></div><div id="map-version" class="version"></div></div></header>
<div class="app"><aside><div class="tabs"><button id="tab-layers" class="tab active" onclick="switchTab('layers')"><i class="fa-solid fa-layer-group"></i> Camadas</button><button id="tab-details" class="tab" onclick="switchTab('details')"><i class="fa-solid fa-circle-info"></i> Detalhes</button><button id="tab-about" class="tab" onclick="switchTab('about')"><i class="fa-solid fa-circle-question"></i> Sobre</button></div><div id="content-layers" class="panel"><div class="section">Camadas vetoriais</div><div id="layers-list"></div></div><div id="content-details" class="panel hidden"><div class="section">Atributos da feicao</div><div id="feature-info" class="empty">Clique em uma feicao para consultar seus atributos.</div></div><div id="content-about" class="panel hidden about"></div></aside><main><div id="map"></div><div class="mapbadge">Visualizacao: WGS 84, EPSG:4326</div><div id="map-tile-warning" style="display:none;position:absolute;z-index:710;left:12px;bottom:45px;background:#FFF3CD;color:#664D03;border-left:4px solid #F59E0B;padding:8px 10px;border-radius:5px;font-size:11px;box-shadow:0 2px 8px rgba(13,56,98,.2)"></div></main></div>
<script>const layersData=__DATA__,metadata=__META__;let map;const leafletLayers={};
function esc(v){return v===null||v===undefined||v===''?'-':String(v)}
function init(){document.getElementById('map-title').textContent=metadata.titulo;document.getElementById('map-subtitle').textContent=metadata.subtitulo;document.getElementById('class-badge').textContent=metadata.classificacao_rotulo;document.getElementById('map-version').textContent=metadata.versao_mapa+' | Referencia: '+metadata.data_referencia;document.getElementById('modal-class').textContent=metadata.classificacao_rotulo;document.getElementById('modal-text').textContent=metadata.aviso_sigilo;renderAbout();map=L.map('map').setView([-14,-52],4);const esriStreet=L.tileLayer(
'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
{attribution:'Tiles &copy; Esri',maxZoom:19,crossOrigin:true}
).addTo(map);
const esriImagery=L.tileLayer(
'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
{attribution:'Tiles &copy; Esri',maxZoom:19,crossOrigin:true}
);
const esriTopo=L.tileLayer(
'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
{attribution:'Tiles &copy; Esri',maxZoom:19,crossOrigin:true}
);
[
 [esriStreet,'Mapa viario'],
 [esriImagery,'Imagem de satelite'],
 [esriTopo,'Mapa topografico']
].forEach(([camada,nome])=>{
 camada.on('tileerror',evento=>{
   console.warn('Falha ao carregar mapa-base:',nome,evento.coords);
   const aviso=document.getElementById('map-tile-warning');
   if(aviso){aviso.style.display='block';aviso.textContent='Mapa-base parcialmente indisponivel. As camadas do projeto continuam acessiveis.';}
 });
});
L.control.layers(
 {'Mapa viario':esriStreet,'Imagem de satelite':esriImagery,'Mapa topografico':esriTopo},
 null,
 {position:'topright',collapsed:true}
).addTo(map);
map.on('baselayerchange',evento=>{
 const aviso=document.getElementById('map-tile-warning');
 if(aviso){aviso.style.display='none';}
});const bounds=L.featureGroup();layersData.forEach(d=>{const o=.38,l=L.geoJSON(d.data,{style:()=>styleFor(d,o),pointToLayer:(f,ll)=>L.circleMarker(ll,styleFor(d,o)),onEachFeature:(f,x)=>x.on('click',()=>showDetails(f.properties||{},d.name))});leafletLayers[d.id]={layer:l,data:d,opacity:o};if(d.visible)l.addTo(map);bounds.addLayer(l)});if(bounds.getLayers().length&&bounds.getBounds().isValid())map.fitBounds(bounds.getBounds(),{padding:[30,30]});renderControls()}
function styleFor(d,o){if(d.geom_type==='Point')return{radius:6,color:'#fff',weight:1.5,fillColor:d.color,fillOpacity:o};if(d.geom_type==='LineString')return{color:d.color,weight:3,opacity:Math.min(1,o+.35)};return{color:d.color,weight:2,opacity:Math.min(1,o+.35),fillColor:d.color,fillOpacity:o}}
function renderControls(){const c=document.getElementById('layers-list');layersData.forEach(d=>{const x=document.createElement('div');x.className='card';x.innerHTML=`<div class="row"><input type="checkbox" ${d.visible?'checked':''} onchange="toggleLayer('${d.id}',this.checked)"><span class="sw" style="background:${d.color}"></span><div class="copy"><div class="lname"></div><div class="meta">${d.feature_count} feicao(oes) | ${d.source_crs}</div></div><button class="zoom" onclick="zoomLayer('${d.id}')"><i class="fa-solid fa-magnifying-glass-plus"></i></button></div><div class="opacity"><span>Opacidade</span><input type="range" min="0" max="1" step=".05" value=".38" oninput="changeOpacity('${d.id}',this.value)"></div>`;x.querySelector('.lname').textContent=d.name;c.appendChild(x)})}
function toggleLayer(id,v){const x=leafletLayers[id];v?x.layer.addTo(map):map.removeLayer(x.layer)}function zoomLayer(id){const b=leafletLayers[id].layer.getBounds();if(b.isValid())map.fitBounds(b,{padding:[25,25]})}function changeOpacity(id,v){const x=leafletLayers[id];x.opacity=Number(v);x.layer.eachLayer(s=>{if(s.setStyle)s.setStyle(styleFor(x.data,x.opacity))})}
function showDetails(props,name){switchTab('details');const c=document.getElementById('feature-info');c.className='';c.innerHTML='';const t=document.createElement('div');t.className='detailtitle';t.textContent=name;c.appendChild(t);const table=document.createElement('table');table.className='attrs';const body=document.createElement('tbody');Object.entries(props).forEach(([k,v])=>{const tr=document.createElement('tr'),a=document.createElement('td'),b=document.createElement('td');a.textContent=k;b.textContent=esc(v);tr.append(a,b);body.appendChild(tr)});table.appendChild(body);c.appendChild(table)}
function renderAbout(){const c=document.getElementById('content-about');c.innerHTML='';const h=document.createElement('div');h.className='section';h.textContent='Identificacao do mapa';c.appendChild(h);const intro=document.createElement('p');intro.textContent=metadata.descricao||'Mapa interativo gerado a partir de composicao do QGIS.';c.appendChild(intro);const dl=document.createElement('dl');[['Titulo',metadata.titulo],['Subtitulo',metadata.subtitulo],['Unidade',metadata.unidade],['Projeto / processo',metadata.processo],['Responsavel tecnico',metadata.responsavel],['Cargo / funcao',metadata.funcao],['Area responsavel',metadata.area_responsavel],['Versao do mapa',metadata.versao_mapa],['Data de referencia',metadata.data_referencia],['Gerado em',metadata.data_geracao],['Projeto QGIS',metadata.projeto],['CRS do projeto',metadata.crs_projeto],['Versao do QGIS',metadata.qgis],['Versao do gerador',metadata.versao_gerador],['Classificacao',metadata.classificacao_rotulo],['Mapas-base','Esri World Street Map; Esri World Imagery; Esri World Topographic Map'],['Camadas',metadata.quantidade_camadas],['Feicoes',metadata.quantidade_feicoes]].forEach(([k,v])=>{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=esc(v);dl.append(dt,dd)});c.appendChild(dl);const hh=document.createElement('h3');hh.textContent='Aviso e limitacoes';c.appendChild(hh);const p=document.createElement('p');p.textContent=metadata.aviso_sigilo+' Este arquivo representa uma versao congelada das informacoes na data indicada. O zoom nao aumenta a precisao das fontes. Os dados incorporados podem ser tecnicamente extraidos do HTML.';c.appendChild(p)}
function switchTab(tab){['layers','details','about'].forEach(x=>{document.getElementById('content-'+x).classList.toggle('hidden',x!==tab);document.getElementById('tab-'+x).classList.toggle('active',x===tab)})}function acceptNotice(){document.getElementById('conf-modal').style.display='none';setTimeout(()=>map.invalidateSize(),50)}function closeMap(){document.body.innerHTML='<div style="font-family:Arial;padding:40px;color:#0D3862"><h2>Visualizacao encerrada</h2><p>Feche esta aba do navegador.</p></div>'}window.onload=init;</script></body></html>'''

    conteudo = (template.replace("__TITLE__", html.escape(config["titulo"], quote=True))
                         .replace("__LOGO__", LOGO_URL)
                         .replace("__DATA__", dados_json)
                         .replace("__META__", meta_json))
    os.makedirs(os.path.dirname(config["saida"]), exist_ok=True)
    with open(config["saida"], "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)
    return metadados


try:
    print("\n" + "=" * 76)
    print("GERADOR DE MAPA INTERATIVO QGIS")
    print("VERSAO " + VERSAO_GERADOR)
    print("=" * 76)
    janela = JanelaConfiguracao(iface.mainWindow())
    if janela.exec_() != QDialog.Accepted:
        print("Geracao cancelada pelo usuario.")
    else:
        config = janela.configuracao()
        metadados = exportar(config)
        tamanho_mb = os.path.getsize(config["saida"]) / (1024 * 1024)
        print("MAPA INTERATIVO GERADO COM SUCESSO")
        print("Arquivo: " + config["saida"])
        print("Camadas: " + str(metadados["quantidade_camadas"]))
        print("Feicoes: " + str(metadados["quantidade_feicoes"]))
        print("Classificacao: " + metadados["classificacao_rotulo"])
        print("Tamanho: {:.2f} MB".format(tamanho_mb))
        print("=" * 76)
        webbrowser.open_new_tab("file:///" + config["saida"].replace("\\", "/"))
        QMessageBox.information(
            iface.mainWindow(), "Mapa interativo gerado",
            "Arquivo criado com sucesso.\n\n" + config["saida"] +
            "\n\nCamadas: {}\nFeicoes: {}\nTamanho: {:.2f} MB\nClassificacao: {}".format(
                metadados["quantidade_camadas"], metadados["quantidade_feicoes"],
                tamanho_mb, metadados["classificacao_rotulo"])
        )
except Exception as erro:
    print("ERRO: " + str(erro))
    QMessageBox.critical(iface.mainWindow(), "Erro no gerador", str(erro))
