# -*- coding: utf-8 -*-
import datetime,html,json,os,re,tempfile,webbrowser
from qgis.core import Qgis,QgsCoordinateReferenceSystem,QgsCoordinateTransform,QgsGeometry,QgsMapLayerType,QgsProject,QgsWkbTypes
from qgis.PyQt.QtCore import QDate,Qt
from qgis.PyQt.QtWidgets import QCheckBox,QComboBox,QDateEdit,QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QRadioButton,QTableWidget,QTableWidgetItem,QTextEdit,QVBoxLayout
from qgis.utils import iface
VERSAO="0.0.4.1";LOGO="https://cimentonacional.com.br/wp-content/uploads/2025/06/cropped-logo-cimento-nacional.png";CORES=["#0071AE","#05A8FF","#0D3862","#D1D1D1"];SENS=("cpf","cnpj","rg","proprietario","titular","telefone","celular","email","endereco","contato","senha","token")
SIG={"PUBLICO":("Uso publico","Mapa preparado para consulta publica."),"INTERNO":("Uso interno","Mapa destinado ao uso interno e a usuarios autorizados."),"CONFIDENCIAL":("Confidencial","Mapa destinado exclusivamente a usuarios autorizados e pode conter informacoes confidenciais ou dados pessoais. Nao reproduza, distribua ou publique sem autorizacao."),"RESTRITO":("Restrito","Conteudo restrito aos destinatarios expressamente autorizados.")}
def norm(s):return re.sub(r"[^a-z0-9]+","_",str(s).lower()).strip("_")
def sens(s):
 n=norm(s);return any(n==x or n.startswith(x+"_") or n.endswith("_"+x) for x in SENS)
def jval(v):
 if v is None or str(v)=="NULL":return None
 if isinstance(v,(str,int,float,bool)):return v
 if isinstance(v,(datetime.date,datetime.datetime,datetime.time)):return v.isoformat()
 try:return v.toString()
 except:return str(v)
def gtipo(c):
 t=QgsWkbTypes.geometryType(c.wkbType());return "Point" if t==QgsWkbTypes.PointGeometry else "LineString" if t==QgsWkbTypes.LineGeometry else "Polygon"
def vis(p,c):
 n=p.layerTreeRoot().findLayer(c.id());return n.itemVisibilityChecked() if n else True
def cams(e):
 p=QgsProject.instance();a=[c for c in p.mapLayers().values() if c.type()==QgsMapLayerType.VectorLayer and c.isSpatial()]
 if e=="SELECIONADAS":
  ids={c.id() for c in iface.layerTreeView().selectedLayers()};a=[c for c in a if c.id() in ids]
 elif e=="VISIVEIS":a=[c for c in a if vis(p,c)]
 return a
def cor(c,i):
 try:
  s=c.renderer().symbol();return s.color().name() if s else CORES[i%4]
 except:return CORES[i%4]
class Pub(QDialog):
 def __init__(self,p=None):
  super().__init__(p);self.setWindowTitle("Gerador de Mapa Interativo v0.0.4.1");self.resize(700,650);l=QVBoxLayout(self);g=QGroupBox("Identificacao");f=QFormLayout(g);self.t=QLineEdit("Mapa Interativo Ambiental e Fundiario");self.s=QLineEdit("Projeto QGIS");self.d=QTextEdit();self.d.setMaximumHeight(70);self.r=QLineEdit("Eloizio Henrique de Medeiros Dantas");self.fun=QLineEdit("Analista Licenciamento Ambiental Pl");self.ar=QLineEdit("Meio Ambiente");self.v=QLineEdit("v001");self.dt=QDateEdit(QDate.currentDate());self.dt.setCalendarPopup(True);self.dt.setDisplayFormat("dd/MM/yyyy")
  for a,b in [("Titulo",self.t),("Subtitulo",self.s),("Descricao",self.d),("Responsavel",self.r),("Funcao",self.fun),("Area",self.ar),("Versao",self.v),("Referencia",self.dt)]:f.addRow(a,b)
  l.addWidget(g);g2=QGroupBox("Conteudo");f2=QFormLayout(g2);self.rs=QRadioButton("Camadas selecionadas");self.rv=QRadioButton("Camadas visiveis");self.rt=QRadioButton("Todas vetoriais");self.rs.setChecked(True);f2.addRow(self.rs);f2.addRow(self.rv);f2.addRow(self.rt);self.sg=QComboBox();[self.sg.addItem(v[0],k) for k,v in SIG.items()];self.sg.setCurrentIndex(2);f2.addRow("Classificacao",self.sg);l.addWidget(g2);h=QHBoxLayout();self.out=QLineEdit(os.path.join(tempfile.gettempdir(),"mapa_interativo_qgis.html"));b=QPushButton("Selecionar");b.clicked.connect(self.pick);h.addWidget(self.out);h.addWidget(b);l.addLayout(h);bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);bb.button(QDialogButtonBox.Ok).setText("Revisar atributos");bb.accepted.connect(self.accept);bb.rejected.connect(self.reject);l.addWidget(bb)
 def esc(self):return "SELECIONADAS" if self.rs.isChecked() else "VISIVEIS" if self.rv.isChecked() else "TODAS"
 def pick(self):
  a,_=QFileDialog.getSaveFileName(self,"Salvar",self.out.text(),"HTML (*.html)");self.out.setText(a if not a or a.endswith(".html") else a+".html")
 def data(self):return {"titulo":self.t.text(),"subtitulo":self.s.text(),"descricao":self.d.toPlainText(),"responsavel":self.r.text(),"funcao":self.fun.text(),"area_responsavel":self.ar.text(),"versao_mapa":self.v.text(),"data_referencia":self.dt.date().toString("dd/MM/yyyy"),"classificacao":self.sg.currentData(),"escopo":self.esc(),"saida":os.path.abspath(self.out.text())}
class Attr(QDialog):
 def __init__(self,cs,p=None):
  super().__init__(p);self.cs=cs;self.cfg={};self.at=None;self.resize(820,620);self.setWindowTitle("Revisao de atributos");l=QVBoxLayout(self);self.cb=QComboBox()
  for c in cs:self.cb.addItem(c.name(),c.id());self.cfg[c.id()]=[{"nome":x.name(),"alias":x.alias() or x.name(),"incluir":not sens(x.name())} for x in c.fields()]
  l.addWidget(self.cb);self.tb=QTableWidget(0,3);self.tb.setHorizontalHeaderLabels(["Incluir","Campo","Rotulo"]);self.tb.setColumnWidth(2,340);l.addWidget(self.tb);bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);bb.accepted.connect(self.ok);bb.rejected.connect(self.reject);l.addWidget(bb);self.cb.currentIndexChanged.connect(self.load);self.load()
 def save(self):
  if not self.at:return
  for i,x in enumerate(self.cfg[self.at]):x["incluir"]=self.tb.cellWidget(i,0).isChecked();x["alias"]=self.tb.item(i,2).text().strip() or x["nome"]
 def load(self):
  self.save();self.at=self.cb.currentData();xs=self.cfg[self.at];self.tb.setRowCount(len(xs))
  for i,x in enumerate(xs):q=QCheckBox();q.setChecked(x["incluir"]);self.tb.setCellWidget(i,0,q);self.tb.setItem(i,1,QTableWidgetItem(x["nome"]));self.tb.setItem(i,2,QTableWidgetItem(x["alias"]))
 def ok(self):
  self.save();v=[c.name() for c in self.cs if not any(x["incluir"] for x in self.cfg[c.id()])]
  if v:QMessageBox.warning(self,"Sem campos","Selecione campos em:\n"+"\n".join(v));return
  self.accept()
def export(cfg,cs,ac):
 p=QgsProject.instance();w=QgsCoordinateReferenceSystem("EPSG:4326");ls=[]
 for i,c in enumerate(cs):
  fs=[x for x in ac[c.id()] if x["incluir"]];tr=QgsCoordinateTransform(c.crs(),w,p.transformContext());out=[]
  for f in c.getFeatures():
   g=f.geometry()
   if not g or g.isNull() or g.isEmpty():continue
   cp=QgsGeometry(g)
   try:
    if c.crs()!=w:cp.transform(tr)
    gj=json.loads(cp.asJson())
   except:continue
   out.append({"type":"Feature","geometry":gj,"properties":{x["alias"]:jval(f[x["nome"]]) for x in fs}})
  ls.append({"id":f"l{len(ls)}","name":c.name(),"color":cor(c,i),"geom_type":gtipo(c),"visible":vis(p,c),"feature_count":len(out),"field_count":len(fs),"data":{"type":"FeatureCollection","features":out}})
 rot,txt=SIG[cfg["classificacao"]];m={**cfg,"data_geracao":datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),"versao_gerador":VERSAO,"qgis":getattr(Qgis,"QGIS_VERSION",""),"quantidade_campos":sum(x["field_count"] for x in ls),"classificacao_rotulo":rot,"aviso_sigilo":txt,"mapas_base":"Esri World Imagery (padrao); Esri World Topographic Map"};d=json.dumps(ls,ensure_ascii=False).replace("</","<\\/");mj=json.dumps(m,ensure_ascii=False).replace("</","<\\/");h=HTML_TEMPLATE.replace("__TITLE__",html.escape(cfg["titulo"])).replace("__LOGO__",LOGO).replace("__DATA__",d).replace("__META__",mj);os.makedirs(os.path.dirname(cfg["saida"]),exist_ok=True);open(cfg["saida"],"w",encoding="utf-8").write(h);return m
HTML_TEMPLATE='<!doctype html><html lang=\'pt-BR\'><head><meta charset=\'utf-8\'><meta name=\'viewport\' content=\'width=device-width,initial-scale=1\'><title>__TITLE__</title><link rel=\'stylesheet\' href=\'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\'><script src=\'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\'></script><style>:root{--b:#0071AE;--n:#0D3862;--g:#D1D1D1;--c:#05A8FF}*{box-sizing:border-box}html,body{height:100%;margin:0;font-family:Arial,sans-serif}body{overflow:hidden}header{height:78px;display:flex;align-items:center;justify-content:space-between;padding:8px 20px;border-bottom:4px solid var(--b)}header img{width:170px;max-height:48px;object-fit:contain}.brand{display:flex;align-items:center;gap:16px}.head{border-left:1px solid var(--g);padding-left:16px}.head h1{margin:0;font-size:18px;color:var(--n)}.head p{margin:3px 0;color:#607585;font-size:12px}.badge{background:#e8f6fd;color:var(--b);padding:6px 10px;border-radius:99px;font-size:11px;font-weight:bold}.app{display:flex;height:calc(100vh - 78px)}aside{width:350px;background:var(--n);color:#fff;display:flex;flex-direction:column}.tabs{display:flex}.tab{flex:1;padding:13px 3px;border:0;background:transparent;color:var(--g);font-weight:bold}.tab.active{color:#fff;border-bottom:3px solid var(--c)}.panel{flex:1;overflow:auto;padding:15px}.hidden{display:none}.card{background:#ffffff14;border:1px solid #ffffff26;border-radius:8px;padding:11px;margin-bottom:9px}.row{display:flex;gap:8px}.sw{width:13px;height:13px;border-radius:50%;border:1px solid #fff}.ct{flex:1}.nm{font-size:13px;font-weight:bold}.meta{color:var(--g);font-size:10px}.op{display:flex;gap:7px;color:var(--g);font-size:10px;margin-top:8px}.op input{width:100%}main,#map{flex:1;height:100%}.attrs{width:100%;border-collapse:collapse;font-size:11px}.attrs td{padding:7px;border-bottom:1px solid #ffffff22}.attrs td:first-child{color:var(--g);font-weight:bold}.modal{position:fixed;inset:0;background:#0d3862e8;z-index:5000;display:flex;align-items:center;justify-content:center}.box{max-width:620px;background:#fff;border-radius:12px;overflow:hidden}.mhead{background:var(--n);color:#fff;padding:18px;border-bottom:4px solid var(--c)}.mbody{padding:22px}.actions{text-align:right;padding:0 22px 22px}.btn{padding:10px 14px;border:0;border-radius:7px;margin-left:8px}.primary{background:var(--b);color:#fff}</style></head><body><div id=\'modal\' class=\'modal\'><div class=\'box\'><div class=\'mhead\'>Aviso de confidencialidade</div><div class=\'mbody\'><span id=\'mclass\' class=\'badge\'></span><p id=\'mtext\'></p><strong>Ao continuar, o usuario declara estar ciente.</strong></div><div class=\'actions\'><button class=\'btn\' onclick=\'closeMap()\'>Fechar</button><button class=\'btn primary\' onclick=\'acceptNotice()\'>Estou ciente</button></div></div></div><header><div class=\'brand\'><img src=\'__LOGO__\'><div class=\'head\'><h1 id=\'title\'></h1><p id=\'subtitle\'></p></div></div><div><span id=\'class\' class=\'badge\'></span><div id=\'version\'></div></div></header><div class=\'app\'><aside><div class=\'tabs\'><button id=\'tab-layers\' class=\'tab active\' onclick="tab(\'layers\')">Camadas</button><button id=\'tab-details\' class=\'tab\' onclick="tab(\'details\')">Detalhes</button><button id=\'tab-about\' class=\'tab\' onclick="tab(\'about\')">Sobre</button></div><div id=\'content-layers\' class=\'panel\'><div id=\'layers\'></div></div><div id=\'content-details\' class=\'panel hidden\'><div id=\'info\'>Clique em uma feicao.</div></div><div id=\'content-about\' class=\'panel hidden\'></div></aside><main><div id=\'map\'></div></main></div><script>const data=__DATA__,meta=__META__;let map;const ll={};function init(){title.textContent=meta.titulo;subtitle.textContent=meta.subtitulo;document.getElementById(\'class\').textContent=meta.classificacao_rotulo;version.textContent=meta.versao_mapa+\' | \'+meta.data_referencia;mclass.textContent=meta.classificacao_rotulo;mtext.textContent=meta.aviso_sigilo;about();map=L.map(\'map\').setView([-14,-52],4);const sat=L.tileLayer(\'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}\',{attribution:\'Tiles &copy; Esri\',maxZoom:19,crossOrigin:true}).addTo(map);const topo=L.tileLayer(\'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}\',{attribution:\'Tiles &copy; Esri\',maxZoom:19,crossOrigin:true});L.control.layers({\'Imagem de satelite\':sat,\'Mapa topografico\':topo},null,{position:\'topright\',collapsed:true}).addTo(map);const bounds=L.featureGroup();data.forEach(d=>{const o=.38,l=L.geoJSON(d.data,{style:()=>style(d,o),pointToLayer:(f,p)=>L.circleMarker(p,style(d,o)),onEachFeature:(f,x)=>x.on(\'click\',()=>details(f.properties||{},d.name))});ll[d.id]={layer:l,data:d,opacity:o};if(d.visible)l.addTo(map);bounds.addLayer(l)});if(bounds.getLayers().length&&bounds.getBounds().isValid())map.fitBounds(bounds.getBounds(),{padding:[30,30]});controls()}function style(d,o){if(d.geom_type===\'Point\')return{radius:6,color:\'#fff\',weight:1.5,fillColor:d.color,fillOpacity:o};if(d.geom_type===\'LineString\')return{color:d.color,weight:3,opacity:Math.min(1,o+.35)};return{color:d.color,weight:2,opacity:Math.min(1,o+.35),fillColor:d.color,fillOpacity:o}}function controls(){const c=document.getElementById(\'layers\');data.forEach(d=>{const x=document.createElement(\'div\');x.className=\'card\';x.innerHTML=`<div class=\'row\'><input type=\'checkbox\' ${d.visible?\'checked\':\'\'} onchange="toggle(\'${d.id}\',this.checked)"><span class=\'sw\' style=\'background:${d.color}\'></span><div class=\'ct\'><div class=\'nm\'></div><div class=\'meta\'>${d.feature_count} feicao(oes) | ${d.field_count} campo(s)</div></div></div><div class=\'op\'>Opacidade<input type=\'range\' min=\'0\' max=\'1\' step=\'.05\' value=\'.38\' oninput="opacity(\'${d.id}\',this.value)"></div>`;x.querySelector(\'.nm\').textContent=d.name;c.appendChild(x)})}function toggle(id,v){v?ll[id].layer.addTo(map):map.removeLayer(ll[id].layer)}function opacity(id,v){const x=ll[id];x.opacity=Number(v);x.layer.eachLayer(s=>s.setStyle&&s.setStyle(style(x.data,x.opacity)))}function details(p,n){tab(\'details\');const c=document.getElementById(\'info\');c.innerHTML=\'\';const h=document.createElement(\'h3\');h.textContent=n;c.appendChild(h);const t=document.createElement(\'table\');t.className=\'attrs\';const b=document.createElement(\'tbody\');Object.entries(p).forEach(([k,v])=>{const r=document.createElement(\'tr\'),a=document.createElement(\'td\'),z=document.createElement(\'td\');a.textContent=k;z.textContent=v==null||v===\'\'?\'-\':String(v);r.append(a,z);b.appendChild(r)});t.appendChild(b);c.appendChild(t)}function about(){const c=document.getElementById(\'content-about\');const p=document.createElement(\'p\');p.textContent=meta.descricao||\'Mapa interativo gerado a partir do QGIS.\';c.appendChild(p);[[\'Responsavel\',meta.responsavel],[\'Cargo\',meta.funcao],[\'Area\',meta.area_responsavel],[\'Versao\',meta.versao_mapa],[\'Referencia\',meta.data_referencia],[\'Gerado em\',meta.data_geracao],[\'QGIS\',meta.qgis],[\'Gerador\',meta.versao_gerador],[\'Mapas-base\',meta.mapas_base],[\'Campos\',meta.quantidade_campos]].forEach(([k,v])=>{const q=document.createElement(\'p\');q.textContent=k+\': \'+(v||\'-\');c.appendChild(q)})}function tab(n){[\'layers\',\'details\',\'about\'].forEach(x=>{document.getElementById(\'content-\'+x).classList.toggle(\'hidden\',x!==n);document.getElementById(\'tab-\'+x).classList.toggle(\'active\',x===n)})}function acceptNotice(){modal.style.display=\'none\';setTimeout(()=>map.invalidateSize(),50)}function closeMap(){document.body.innerHTML=\'<h2 style="padding:40px">Visualizacao encerrada</h2>\'}window.onload=init;</script></body></html>'
try:
 j=Pub(iface.mainWindow())
 if j.exec_()!=QDialog.Accepted:raise InterruptedError("Cancelado.")
 cfg=j.data();cs=cams(cfg["escopo"])
 if not cs:raise Exception("Nenhuma camada no escopo.")
 a=Attr(cs,iface.mainWindow())
 if a.exec_()!=QDialog.Accepted:raise InterruptedError("Revisao cancelada.")
 export(cfg,cs,a.cfg);webbrowser.open_new_tab("file:///"+cfg["saida"].replace("\\","/"));print("VERSAO 0.0.4.1 EXECUTADA: "+cfg["saida"])
except InterruptedError as e:print(str(e))
except Exception as e:print("ERRO: "+str(e));QMessageBox.critical(iface.mainWindow(),"Erro",str(e))
