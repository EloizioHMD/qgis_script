# -*- coding: utf-8 -*-
'''Gerador de Geoportal QGIS v0.0.2.

Alteracoes principais:
- identidade visual Cimento Nacional;
- logo remoto no cabecalho;
- remocao integral do download GeoJSON;
- preservacao da visibilidade das camadas;
- consulta de atributos, opacidade e zoom por camada.
'''
import datetime
import html
import json
import os
import tempfile
import webbrowser

from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsGeometry,
    QgsMapLayerType, QgsProject, QgsWkbTypes
)

VERSAO = "0.0.2"
LOGO_URL = "https://cimentonacional.com.br/wp-content/uploads/2025/06/cropped-logo-cimento-nacional.png"
CORES_CAMADAS = ["#0071AE", "#05A8FF", "#0D3862", "#D1D1D1"]


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


def visivel_no_projeto(projeto, camada):
    no = projeto.layerTreeRoot().findLayer(camada.id())
    return no.itemVisibilityChecked() if no else True


def export_qgis_to_webgis(output_filepath=None, title="SIG Ambiental & Fundiario - Export QGIS", open_browser=True):
    projeto = QgsProject.instance()
    crs_web = QgsCoordinateReferenceSystem("EPSG:4326")
    camadas_web = []

    print("\n" + "=" * 76)
    print("GERADOR DE GEOPORTAL QGIS")
    print("VERSAO " + VERSAO)
    print("=" * 76)

    for indice, camada in enumerate(projeto.mapLayers().values()):
        if camada.type() != QgsMapLayerType.VectorLayer:
            continue
        if not camada.isValid() or not camada.isSpatial() or not camada.crs().isValid():
            print("AVISO: camada ignorada: " + camada.name())
            continue

        transformacao = QgsCoordinateTransform(camada.crs(), crs_web, projeto.transformContext())
        campos = [campo.name() for campo in camada.fields()]
        feicoes = []
        ignoradas = 0

        for feicao in camada.getFeatures():
            geometria = feicao.geometry()
            if geometria is None or geometria.isNull() or geometria.isEmpty():
                ignoradas += 1
                continue
            copia = QgsGeometry(geometria)
            try:
                if camada.crs() != crs_web and copia.transform(transformacao) != 0:
                    ignoradas += 1
                    continue
                geom_json = json.loads(copia.asJson())
            except Exception:
                ignoradas += 1
                continue
            atributos = {nome: valor_json_seguro(feicao[nome]) for nome in campos}
            feicoes.append({"type": "Feature", "geometry": geom_json, "properties": atributos})

        camadas_web.append({
            "id": "layer_" + str(len(camadas_web)),
            "name": camada.name(),
            "color": cor_da_camada(camada, indice),
            "geom_type": tipo_geometria(camada),
            "visible": visivel_no_projeto(projeto, camada),
            "feature_count": len(feicoes),
            "source_crs": camada.crs().authid(),
            "data": {"type": "FeatureCollection", "features": feicoes},
        })
        print("OK: {}: {} feicao(oes); {} ignorada(s).".format(camada.name(), len(feicoes), ignoradas))

    if not camadas_web:
        raise Exception("Nenhuma camada vetorial espacial valida foi encontrada.")

    if not output_filepath:
        output_filepath = os.path.join(tempfile.gettempdir(), "geoportal_qgis_export.html")
    output_filepath = os.path.abspath(output_filepath)
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    dados_json = json.dumps(camadas_web, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    titulo = html.escape(title, quote=True)

    template = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{--white:#FFFFFF;--blue:#0071AE;--navy:#0D3862;--gray:#D1D1D1;--cyan:#05A8FF;--bg:#F4F7F9}
*{box-sizing:border-box}html,body{height:100%;margin:0;font-family:Arial,Helvetica,sans-serif}body{overflow:hidden;background:var(--bg);color:var(--navy)}
header{height:74px;background:var(--white);border-bottom:4px solid var(--blue);display:flex;align-items:center;justify-content:space-between;padding:8px 22px;box-shadow:0 2px 10px rgba(13,56,98,.16);position:relative;z-index:1001}
.brand{display:flex;align-items:center;gap:18px;min-width:0}.brand img{width:178px;max-height:50px;object-fit:contain}.title{border-left:1px solid var(--gray);padding-left:18px;min-width:0}.title h1{margin:0;font-size:18px;color:var(--navy);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.title p{margin:3px 0 0;color:#637887;font-size:12px}.pill{background:#E8F6FD;color:var(--blue);border:1px solid #A9DFF6;border-radius:999px;padding:7px 11px;font-size:12px;font-weight:bold}
.app{display:flex;height:calc(100vh - 74px)}aside{width:340px;min-width:340px;background:var(--navy);color:var(--white);display:flex;flex-direction:column;z-index:1000;box-shadow:3px 0 12px rgba(13,56,98,.2)}
.tabs{display:flex;border-bottom:1px solid rgba(255,255,255,.15)}.tab{flex:1;border:0;background:transparent;color:var(--gray);padding:14px 8px;cursor:pointer;font-size:12px;font-weight:bold;text-transform:uppercase;border-bottom:3px solid transparent}.tab.active{color:var(--white);border-bottom-color:var(--cyan);background:rgba(5,168,255,.09)}
.panel{flex:1;overflow-y:auto;padding:16px}.hidden{display:none}.section{font-size:11px;font-weight:bold;color:var(--gray);text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px}.card{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:9px;padding:12px;margin-bottom:10px}.row{display:flex;align-items:flex-start;gap:9px}.row input{accent-color:var(--cyan)}.swatch{width:13px;height:13px;border-radius:50%;border:1px solid var(--white);flex:0 0 auto}.copy{flex:1;min-width:0}.name{font-size:13px;font-weight:bold;overflow-wrap:anywhere}.meta{font-size:10px;color:var(--gray);margin-top:4px}.zoom{border:1px solid rgba(255,255,255,.3);background:transparent;color:var(--white);border-radius:6px;padding:5px 7px;cursor:pointer}.zoom:hover{background:var(--blue)}.opacity{display:flex;gap:8px;align-items:center;color:var(--gray);font-size:10px;margin-top:10px}.opacity input{width:100%;accent-color:var(--cyan)}
main{flex:1;position:relative;min-width:0}#map{height:100%;width:100%;background:var(--gray)}.badge{position:absolute;z-index:700;left:12px;bottom:12px;background:rgba(255,255,255,.95);color:var(--navy);border-left:4px solid var(--cyan);padding:7px 10px;border-radius:5px;font-size:10px;box-shadow:0 2px 8px rgba(13,56,98,.2)}
.empty{color:var(--gray);font-style:italic;font-size:13px;padding:14px;border:1px solid rgba(255,255,255,.15);border-radius:8px}.details-title{color:var(--cyan);font-size:11px;font-weight:bold;text-transform:uppercase;margin-bottom:10px}.attrs{width:100%;border-collapse:collapse;font-size:11px}.attrs td{padding:8px;border-bottom:1px solid rgba(255,255,255,.12);vertical-align:top;overflow-wrap:anywhere}.attrs td:first-child{width:42%;color:var(--gray);font-weight:bold;background:rgba(0,0,0,.08)}
@media(max-width:820px){header{height:70px;padding:8px 12px}.brand img{width:125px}.title{padding-left:10px}.title h1{font-size:14px}.title p,.pill{display:none}.app{height:calc(100vh - 70px)}aside{width:290px;min-width:290px}}
</style>
</head>
<body>
<header><div class="brand"><img src="__LOGO__" alt="Cimento Nacional" referrerpolicy="no-referrer"><div class="title"><h1>__TITLE__</h1><p>Geoportal gerado automaticamente a partir do projeto QGIS</p></div></div><div class="pill"><i class="fa-solid fa-map-location-dot"></i> Consulta territorial</div></header>
<div class="app"><aside><div class="tabs"><button id="tab-layers" class="tab active" onclick="switchTab('layers')"><i class="fa-solid fa-layer-group"></i> Camadas</button><button id="tab-details" class="tab" onclick="switchTab('details')"><i class="fa-solid fa-circle-info"></i> Detalhes</button></div><div id="content-layers" class="panel"><div class="section">Camadas vetoriais</div><div id="layers-list"></div></div><div id="content-details" class="panel hidden"><div class="section">Atributos da feicao selecionada</div><div id="feature-info" class="empty">Clique em uma feicao no mapa para consultar seus atributos.</div></div></aside><main><div id="map"></div><div class="badge">CRS de visualizacao: WGS 84, EPSG:4326</div></main></div>
<script>
const layersData=__DATA__;
const map=L.map('map').setView([-14,-52],4), leafletLayers={};
const osm=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OpenStreetMap contributors',maxZoom:19});
const esri=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{attribution:'Tiles &copy; Esri',maxZoom:19}).addTo(map);
L.control.layers({'Satelite, Esri':esri,'OpenStreetMap':osm},null,{position:'topright'}).addTo(map);
const boundsGroup=L.featureGroup();
function styleFor(d,o){if(d.geom_type==='Point')return{radius:6,color:'#FFFFFF',weight:1.5,fillColor:d.color,fillOpacity:o};if(d.geom_type==='LineString')return{color:d.color,weight:3,opacity:Math.min(1,o+.35)};return{color:d.color,weight:2,opacity:Math.min(1,o+.35),fillColor:d.color,fillOpacity:o}}
layersData.forEach(d=>{const o=.38;const layer=L.geoJSON(d.data,{style:()=>styleFor(d,o),pointToLayer:(f,ll)=>L.circleMarker(ll,styleFor(d,o)),onEachFeature:(f,l)=>l.on('click',()=>showDetails(f.properties||{},d.name))});leafletLayers[d.id]={layer:layer,data:d,opacity:o};if(d.visible)layer.addTo(map);boundsGroup.addLayer(layer)});
if(boundsGroup.getLayers().length&&boundsGroup.getBounds().isValid())map.fitBounds(boundsGroup.getBounds(),{padding:[30,30]});
function renderControls(){const c=document.getElementById('layers-list');c.innerHTML='';layersData.forEach(d=>{const card=document.createElement('div');card.className='card';card.innerHTML=`<div class="row"><input type="checkbox" ${d.visible?'checked':''} onchange="toggleLayer('${d.id}',this.checked)"><span class="swatch" style="background:${d.color}"></span><div class="copy"><div class="name"></div><div class="meta">${d.feature_count} feicao(oes) | ${d.source_crs}</div></div><button class="zoom" onclick="zoomLayer('${d.id}')" title="Aproximar"><i class="fa-solid fa-magnifying-glass-plus"></i></button></div><div class="opacity"><span>Opacidade</span><input type="range" min="0" max="1" step=".05" value=".38" oninput="changeOpacity('${d.id}',this.value)"></div>`;card.querySelector('.name').textContent=d.name;c.appendChild(card)})}
function toggleLayer(id,v){const x=leafletLayers[id];v?x.layer.addTo(map):map.removeLayer(x.layer)}
function zoomLayer(id){const b=leafletLayers[id].layer.getBounds();if(b.isValid())map.fitBounds(b,{padding:[25,25]})}
function changeOpacity(id,v){const x=leafletLayers[id];x.opacity=Number(v);x.layer.eachLayer(s=>{if(s.setStyle)s.setStyle(styleFor(x.data,x.opacity))})}
function showDetails(props,name){switchTab('details');const c=document.getElementById('feature-info');c.className='';c.innerHTML='';const t=document.createElement('div');t.className='details-title';t.textContent=name;c.appendChild(t);const table=document.createElement('table');table.className='attrs';const body=document.createElement('tbody');Object.entries(props).forEach(([k,v])=>{const tr=document.createElement('tr'),a=document.createElement('td'),b=document.createElement('td');a.textContent=k;b.textContent=(v===null||v==='')?'-':String(v);tr.append(a,b);body.appendChild(tr)});table.appendChild(body);c.appendChild(table)}
function switchTab(tab){const a=tab==='layers';document.getElementById('content-layers').classList.toggle('hidden',!a);document.getElementById('content-details').classList.toggle('hidden',a);document.getElementById('tab-layers').classList.toggle('active',a);document.getElementById('tab-details').classList.toggle('active',!a)}
renderControls();
</script>
</body>
</html>'''
    conteudo = (template.replace("__TITLE__", titulo)
                         .replace("__LOGO__", LOGO_URL)
                         .replace("__DATA__", dados_json))
    with open(output_filepath, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)

    print("=" * 76)
    print("GEOPORTAL EXPORTADO COM SUCESSO")
    print("Camadas exportadas: " + str(len(camadas_web)))
    print("Arquivo: " + output_filepath)
    print("Download GeoJSON: removido nesta versao")
    print("=" * 76)

    if open_browser:
        webbrowser.open_new_tab("file:///" + output_filepath.replace("\\", "/"))
    return output_filepath


export_qgis_to_webgis(title="SIG Ambiental & Fundiario - Export QGIS")
