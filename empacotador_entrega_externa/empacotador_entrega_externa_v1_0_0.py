# -*- coding: utf-8 -*-
"""Empacotador de Dados para Entrega Externa - v1.0.0
Autor: Eloizio Dantas
QGIS 3.34 LTR+

Consolida vetores selecionados em GeoPackage, ignora feicoes vazias somente
na copia, preserva CRS e Z/M, trata fid, exporta QML, cria inventario e QGZ
portatil, valida caminhos relativos e gera manifesto, hashes e documentacao.
Nao altera as fontes originais. Nao inclui raster, joins ou tabelas sem geometria.
"""
import csv, hashlib, json, os, platform, re, shutil, tempfile, unicodedata, zipfile
from datetime import datetime
from qgis.core import (Qgis, QgsApplication, QgsFeature, QgsField,
    QgsLayerTreeGroup, QgsMapLayerType, QgsMessageLog, QgsProject,
    QgsVectorFileWriter, QgsVectorLayer, QgsWkbTypes)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout)
from qgis.utils import iface

VERSAO_SCRIPT = "1.0.0"
GPKG = "dados_entrega.gpkg"
INVENTARIO = "inventario_camadas.csv"
MANIFESTO = "manifesto_pacote.json"
HASHES = "verificacao_integridade.sha256"
LEIAME = "LEIA-ME.txt"
VALIDADO = "PACOTE_VALIDADO.txt"
LOG = "empacotamento.log"
MAX_TABELA = 60
CAMPOS_INV = ["ordem","status","nome_original","nome_tabela_gpkg",
 "tipo_geometria","possui_z","possui_m","crs","crs_descricao",
 "provedor_origem","fonte_origem","quantidade_campos","feicoes_origem",
 "feicoes_exportadas","feicoes_vazias_ignoradas","ids_vazios_origem",
 "geometrias_invalidas","estilo_qml","estilo_exportado",
 "acao_geometrias_vazias","campos_renomeados","chave_primaria_gpkg",
 "grupos","visivel","observacoes"]

def agora(): return datetime.now().astimezone().isoformat(timespec="seconds")
def relativo(p, raiz): return os.path.relpath(p, raiz).replace("\\", "/")
def sem_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))
def normalizar(s, upper=False, limite=60, tirar_data=False):
    s = sem_acentos(s)
    if tirar_data: s = re.sub(r"^\s*\d{4}[-_]\d{2}[-_]\d{2}[-_\s]*", "", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_") or "camada"
    if s[0].isdigit(): s = "camada_" + s
    s = s.upper() if upper else s.lower()
    return s[:limite].rstrip("_")
def nome_projeto():
    p = QgsProject.instance().fileName()
    return normalizar(os.path.splitext(os.path.basename(p))[0] if p else "PROJETO_QGIS", True, 70)
def proxima_pasta(destino, base):
    data = datetime.now().strftime("%Y%m%d"); n = 1
    while True:
        nome = f"ENTREGA_{base}_{data}_v{n:03d}"
        final = os.path.join(destino, nome); temp = final + "_EM_MONTAGEM"
        if not os.path.exists(final) and not os.path.exists(temp): return nome, final, temp
        n += 1
def logar(arq, msg):
    linha = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(linha)
    with open(arq,"a",encoding="utf-8") as f: f.write(linha+"\n")

def grupos_no(no):
    r=[]; p=no.parent() if no else None
    while p:
        if isinstance(p,QgsLayerTreeGroup) and p.name(): r.append(p.name())
        p=p.parent()
    return list(reversed(r))
def pos_no(no):
    r=[]; a=no
    while a and a.parent():
        p=a.parent()
        try: r.append(p.children().index(a))
        except ValueError: r.append(0)
        a=p
    return tuple(reversed(r))
def metadados_arvore(camadas):
    raiz=QgsProject.instance().layerTreeRoot(); r=[]
    for c in camadas:
        no=raiz.findLayer(c.id())
        r.append({"camada":c,"grupos":grupos_no(no),"posicao":pos_no(no) if no else (999999,),
                  "visivel":no.itemVisibilityChecked() if no else True,
                  "expandido":no.isExpanded() if no else True})
    return sorted(r,key=lambda x:x["posicao"])

def diagnostico(c):
    vazias=invalidas=0; ids=[]
    for f in c.getFeatures():
        g=f.geometry()
        if g is None or g.isNull() or g.isEmpty(): vazias+=1; ids.append(str(f.id())); continue
        try:
            if not g.isGeosValid(): invalidas+=1
        except Exception: pass
    try: joins=len(c.vectorJoins())
    except Exception: joins=0
    return {"vazias":vazias,"invalidas":invalidas,"ids":ids,"joins":joins}
def validar_selecao(camadas):
    bloqueios=[]; avisos=[]; ds={}
    for c in camadas:
        if c.type()!=QgsMapLayerType.VectorLayer: bloqueios.append(f"{c.name()}: nao e vetor."); continue
        if not c.isSpatial(): bloqueios.append(f"{c.name()}: tabela sem geometria."); continue
        if not c.isValid(): bloqueios.append(f"{c.name()}: camada invalida."); continue
        if not c.crs().isValid(): bloqueios.append(f"{c.name()}: CRS invalido.")
        if c.isEditable(): bloqueios.append(f"{c.name()}: edicao aberta.")
        d=diagnostico(c); ds[c.id()]=d
        if d["joins"]: bloqueios.append(f"{c.name()}: join ativo.")
        if d["vazias"]: avisos.append(f"{c.name()}: {d['vazias']} feicao(oes) vazia(s).")
        if d["invalidas"]: avisos.append(f"{c.name()}: {d['invalidas']} geometria(s) invalida(s).")
    return bloqueios,avisos,ds

class Janela(QDialog):
    def __init__(self, camadas, parent=None):
        super().__init__(parent); self.setWindowTitle("Empacotador de Entrega Externa v1.0.0")
        self.setMinimumWidth(720); self.setMinimumHeight(560); self.setWindowModality(Qt.ApplicationModal)
        l=QVBoxLayout(self); t=QLabel("<b>Entrega externa:</b> gera GeoPackage, QGZ portatil, inventario, estilos, manifesto e hashes.")
        t.setWordWrap(True); l.addWidget(t)
        g=QGroupBox("Camadas selecionadas"); gl=QVBoxLayout(g); lista=QListWidget()
        for c in camadas:
            crs=c.crs().authid() if c.crs().isValid() else "CRS invalido"
            i=QListWidgetItem(f"{c.name()} | {QgsWkbTypes.displayString(c.wkbType())} | {crs} | {c.featureCount()} registro(s)")
            i.setToolTip(c.source()); lista.addItem(i)
        gl.addWidget(lista); gl.addWidget(QLabel(f"<b>Total:</b> {len(camadas)}")); l.addWidget(g)
        gi=QGroupBox("Identificacao e destino"); il=QVBoxLayout(gi); il.addWidget(QLabel("Nome-base:"))
        self.nome=QLineEdit(nome_projeto()); il.addWidget(self.nome); il.addWidget(QLabel("Pasta de destino:"))
        h=QHBoxLayout(); self.dest=QLineEdit(); self.dest.setReadOnly(True); b=QPushButton("Selecionar...")
        b.clicked.connect(self.escolher); h.addWidget(self.dest); h.addWidget(b); il.addLayout(h); l.addWidget(gi)
        a=QLabel("<i>Fontes originais nao serao alteradas. Feicoes vazias saem apenas da copia. Joins, rasters e tabelas sem geometria nao sao aceitos.</i>")
        a.setWordWrap(True); l.addWidget(a)
        bb=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); bb.button(QDialogButtonBox.Ok).setText("Criar pacote completo")
        bb.accepted.connect(self.checar); bb.rejected.connect(self.reject); l.addWidget(bb)
    def escolher(self):
        p=QFileDialog.getExistingDirectory(self,"Selecionar destino",os.path.expanduser("~"))
        if p:self.dest.setText(p)
    def checar(self):
        d=self.dest.text().strip()
        if not self.nome.text().strip(): QMessageBox.warning(self,"Nome","Informe o nome-base."); return
        if not d or not os.path.isdir(d) or not os.access(d,os.W_OK): QMessageBox.warning(self,"Destino","Selecione pasta gravavel."); return
        self.accept()
    def config(self): return normalizar(self.nome.text(),True,70),self.dest.text().strip()

def campo_unico(base, usados):
    c=base;n=2
    while c.lower() in usados: c=f"{base}_{n}";n+=1
    usados.add(c.lower());return c
def preparar_campos(c):
    campos=[];mud=[];usados=set()
    for f in c.fields():
        nome=f.name();novo=campo_unico("fid_orig" if nome.lower().strip()=="fid" else nome,usados)
        nf=QgsField(f);nf.setName(novo);campos.append(nf)
        if novo!=nome:mud.append(f"{nome} -> {novo}")
    return campos,mud
def camada_filtrada(c,tabela):
    out=QgsVectorLayer(f"{QgsWkbTypes.displayString(c.wkbType())}?crs={c.crs().authid()}",tabela,"memory")
    if not out.isValid():raise Exception(f"Falha ao criar memoria para {c.name()}.")
    campos,mud=preparar_campos(c)
    if campos and not out.dataProvider().addAttributes(campos):raise Exception(f"Falha ao copiar campos de {c.name()}.")
    out.updateFields();feats=[];ids=[];inv=0;total=0
    for ft in c.getFeatures():
        total+=1;g=ft.geometry()
        if g is None or g.isNull() or g.isEmpty():ids.append(str(ft.id()));continue
        try:
            if not g.isGeosValid():inv+=1
        except Exception:pass
        n=QgsFeature(out.fields());n.setGeometry(g);n.setAttributes(list(ft.attributes()));feats.append(n)
    if not feats:raise Exception(f"{c.name()} nao possui feicao espacial exportavel.")
    if not out.dataProvider().addFeatures(feats):raise Exception(f"Falha ao copiar feicoes de {c.name()}.")
    out.updateExtents();return out,total,len(feats),ids,inv,mud
def tabela_unica(nome, usados):
    base=normalizar(nome,False,MAX_TABELA,True);c=base;n=2
    while c.lower() in usados:
        s=f"_{n:02d}";c=base[:MAX_TABELA-len(s)].rstrip("_")+s;n+=1
    usados.add(c.lower());return c
def gravar(c,gpkg,tabela,primeira):
    o=QgsVectorFileWriter.SaveVectorOptions();o.driverName="GPKG";o.fileEncoding="UTF-8";o.layerName=tabela;o.layerOptions=["FID=gpkg_fid"]
    o.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteFile if primeira else QgsVectorFileWriter.CreateOrOverwriteLayer
    r=QgsVectorFileWriter.writeAsVectorFormatV3(c,gpkg,QgsProject.instance().transformContext(),o)
    if r[0]!=QgsVectorFileWriter.NoError:raise Exception(f"Falha em {tabela}: {r[1] if len(r)>1 else 'erro OGR'}")
def validar_tabela(gpkg,tabela,n,crs):
    c=QgsVectorLayer(f"{gpkg}|layername={tabela}",tabela,"ogr")
    if not c.isValid() or c.featureCount()!=n:raise Exception(f"Validacao falhou em {tabela}.")
    if crs and c.crs().authid() and c.crs().authid()!=crs:raise Exception(f"CRS divergente em {tabela}.")
def salvar_qml(c,pasta,tabela,raiz):
    arq=os.path.join(pasta,tabela+".qml")
    try:c.saveNamedStyle(arq);return relativo(arq,raiz),os.path.isfile(arq)
    except Exception:return "",False
def inventariar(arq,regs):
    with open(arq,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=CAMPOS_INV,delimiter=";",extrasaction="ignore");w.writeheader();w.writerows(regs)
def caminhos_relativos(p):
    try:p.setFilePathStorage(Qgis.FilePathType.Relative)
    except Exception:p.writeEntry("Paths","/Absolute",False)
def grupo(raiz,nomes,cache):
    a=raiz;k=[]
    for nome in nomes:
        k.append(nome);t=tuple(k)
        if t not in cache:cache[t]=a.addGroup(nome)
        a=cache[t]
    return a
def criar_qgz(regs,gpkg,raiz_pacote,qgz,log,crs):
    p=QgsProject();p.setTitle(os.path.splitext(os.path.basename(qgz))[0]);p.setFileName(qgz);caminhos_relativos(p)
    if crs.isValid():p.setCrs(crs)
    root=p.layerTreeRoot();cache={};estilos=0
    for i,r in enumerate(regs,1):
        c=QgsVectorLayer(f"{gpkg}|layername={r['_tabela']}",r["nome_original"],"ogr")
        if not c.isValid():raise Exception(f"Falha ao carregar {r['nome_original']} no QGZ.")
        qml=os.path.join(raiz_pacote,r["estilo_qml"].replace("/",os.sep)) if r["estilo_qml"] else ""
        if qml and os.path.isfile(qml):
            try:
                ret=c.loadNamedStyle(qml);ok=bool(ret[1]) if isinstance(ret,tuple) and len(ret)>1 else True
                if ok:estilos+=1
            except Exception:pass
        p.addMapLayer(c,False);no=grupo(root,r["_grupos"],cache).addLayer(c);no.setItemVisibilityChecked(r["_visivel"]);no.setExpanded(r["_expandido"])
        logar(log,f"QGZ {i}/{len(regs)}: {r['nome_original']}")
    p.setCustomVariables({"modalidade":"ENTREGA_EXTERNA","versao_empacotador":VERSAO_SCRIPT,"data":agora(),"quantidade_camadas":len(regs)})
    if not p.write(qgz):raise Exception("Falha ao gravar QGZ.")
    p.clear();return estilos
def validar_qgz(qgz,pasta,n):
    if not zipfile.is_zipfile(qgz):raise Exception("QGZ invalido.")
    p=QgsProject()
    if not p.read(qgz):raise Exception("QGZ nao pode ser reaberto.")
    cs=list(p.mapLayers().values())
    if len(cs)!=n:raise Exception("Quantidade divergente no QGZ.")
    base=os.path.realpath(pasta)
    for c in cs:
        if not c.isValid():raise Exception(f"Camada invalida: {c.name()}")
        fonte=os.path.realpath(c.source().split("|")[0])
        try:dentro=os.path.commonpath([base,fonte])==base
        except ValueError:dentro=False
        if not dentro:raise Exception(f"Fonte externa: {c.name()}")
    p.clear()
    with zipfile.ZipFile(qgz) as z:
        nomes=[x for x in z.namelist() if x.lower().endswith(".qgs")]
        if not nomes:raise Exception("QGS interno ausente.")
        xml=z.read(nomes[0]).decode("utf-8",errors="replace")
    abs_gpkg=os.path.join(pasta,"dados","vetores",GPKG)
    if abs_gpkg in xml or abs_gpkg.replace("\\","/") in xml:raise Exception("QGZ contem caminho absoluto.")
    if "dados/vetores/dados_entrega.gpkg" not in xml and "dados\\vetores\\dados_entrega.gpkg" not in xml:raise Exception("Caminho relativo nao confirmado.")
def sha(arq):
    h=hashlib.sha256()
    with open(arq,"rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()
def arquivos_hash(pasta):
    excluir={MANIFESTO,HASHES,LEIAME,VALIDADO,LOG};r=[]
    for base,dirs,files in os.walk(pasta):
        dirs[:]=[d for d in dirs if d not in {"__pycache__",".git",".qgis"} and not d.startswith("fechamento_")]
        for n in files:
            if n not in excluir:r.append(os.path.join(base,n))
    return sorted(r,key=lambda x:relativo(x,pasta).lower())
def qgis_ver():
    try:return Qgis.QGIS_VERSION
    except Exception:
        try:return QgsApplication.qgisVersion()
        except Exception:return "Nao identificada"
def fechar(pasta,qgz,gpkg,regs,log):
    arqs=arquivos_hash(pasta);hs=[]
    for i,a in enumerate(arqs,1):logar(log,f"Hash {i}/{len(arqs)}: {relativo(a,pasta)}");hs.append({"arquivo":relativo(a,pasta),"sha256":sha(a),"tamanho_bytes":os.path.getsize(a)})
    resumo={"camadas":len(regs),"feicoes_origem":sum(int(r["feicoes_origem"]) for r in regs),"feicoes_exportadas":sum(int(r["feicoes_exportadas"]) for r in regs),"feicoes_vazias_ignoradas":sum(int(r["feicoes_vazias_ignoradas"]) for r in regs),"geometrias_invalidas":sum(int(r["geometrias_invalidas"]) for r in regs),"crs":sorted({r["crs"] for r in regs if r["crs"]})}
    man={"pacote":{"id":os.path.basename(pasta),"modalidade":"ENTREGA_EXTERNA","status":"VALIDADO","validado_em":agora(),"versao_empacotador":VERSAO_SCRIPT},"ambiente":{"qgis":qgis_ver(),"python":platform.python_version(),"sistema":platform.platform()},"projeto":{"arquivo":relativo(qgz,pasta),"camadas":len(regs),"fontes_externas":0},"dados":{"geopackage":relativo(gpkg,pasta),**resumo},"integridade":{"algoritmo":"SHA-256","arquivos_verificados":len(hs),"exclusoes":[{"arquivo":f"logs/{LOG}","motivo":"log ativo"},{"arquivo":MANIFESTO,"motivo":"evitar ciclo"},{"arquivo":HASHES,"motivo":"auto-hash impossivel"},{"arquivo":LEIAME,"motivo":"gerado no fechamento"},{"arquivo":VALIDADO,"motivo":"gerado no fechamento"}],"arquivos":hs},"limitacoes":["Sem rasters, joins ou tabelas sem geometria.","Validacao estrutural nao comprova exatidao posicional ou autorizacao de compartilhamento."]}
    tmp=tempfile.mkdtemp(prefix="fechamento_",dir=pasta)
    try:
        mp=os.path.join(tmp,MANIFESTO);hp=os.path.join(tmp,HASHES);lp=os.path.join(tmp,LEIAME);vp=os.path.join(tmp,VALIDADO)
        with open(mp,"w",encoding="utf-8") as f:json.dump(man,f,ensure_ascii=False,indent=2);f.write("\n")
        with open(hp,"w",encoding="utf-8",newline="\n") as f:
            for h in hs:f.write(f"{h['sha256']}  {h['arquivo']}\n")
        texto=f"""PACOTE QGIS PARA ENTREGA EXTERNA
================================
Pacote: {os.path.basename(pasta)}
Status: VALIDADO
Projeto: {os.path.basename(qgz)}
GeoPackage: dados/vetores/{GPKG}
Camadas: {resumo['camadas']}
Feicoes exportadas: {resumo['feicoes_exportadas']}
Feicoes vazias ignoradas: {resumo['feicoes_vazias_ignoradas']}
CRS: {', '.join(resumo['crs'])}

COMO ABRIR
1. Mantenha toda a pasta.
2. Abra o QGZ da raiz no QGIS.
3. Nao mova isoladamente o QGZ ou o GeoPackage.

INTEGRIDADE
Hashes em {HASHES}. O log ativo logs/{LOG} nao integra os hashes.

LIMITACOES
A validacao confirma estrutura e integridade digital. Nao comprova exatidao
posicional, titularidade, validade registral ou autorizacao de compartilhamento.
"""
        with open(lp,"w",encoding="utf-8",newline="\n") as f:f.write(texto)
        marcador=f"PACOTE VALIDADO\n===============\nPacote: {os.path.basename(pasta)}\nValidado em: {agora()}\nVersao: {VERSAO_SCRIPT}\nCamadas: {len(regs)}\nFeicoes exportadas: {resumo['feicoes_exportadas']}\nArquivos com SHA-256: {len(hs)}\nHash QGZ: {sha(qgz)}\nHash GeoPackage: {sha(gpkg)}\nHash manifesto: {sha(mp)}\n"
        with open(vp,"w",encoding="utf-8",newline="\n") as f:f.write(marcador)
        for a,n in [(mp,MANIFESTO),(hp,HASHES),(lp,LEIAME),(vp,VALIDADO)]:os.replace(a,os.path.join(pasta,n))
    finally:
        if os.path.isdir(tmp):shutil.rmtree(tmp)
    return resumo,len(hs)

montagem=None
try:
    print("\n"+"="*80);print("EMPACOTADOR DE DADOS PARA ENTREGA EXTERNA - VERSAO 1.0.0");print("="*80)
    camadas=iface.layerTreeView().selectedLayers()
    if not camadas:raise Exception("Nenhuma camada selecionada.")
    bloqueios,avisos,_=validar_selecao(camadas)
    if bloqueios:raise Exception("Ocorrencias impeditivas:\n\n"+"\n".join("• "+x for x in bloqueios))
    if avisos:
        r=QMessageBox.question(iface.mainWindow(),"Avisos","\n".join("• "+x for x in avisos[:15])+"\n\nFeicoes vazias serao omitidas somente da copia. Continuar?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if r!=QMessageBox.Yes:raise InterruptedError("Operacao cancelada.")
    j=Janela(camadas,iface.mainWindow())
    if j.exec_()!=QDialog.Accepted:raise InterruptedError("Operacao cancelada.")
    base,dest=j.config();nome,final,montagem=proxima_pasta(dest,base)
    os.makedirs(os.path.join(montagem,"dados","vetores"));os.makedirs(os.path.join(montagem,"estilos"));os.makedirs(os.path.join(montagem,"logs"))
    log=os.path.join(montagem,"logs",LOG);gpkg=os.path.join(montagem,"dados","vetores",GPKG);inv=os.path.join(montagem,INVENTARIO);qgz=os.path.join(montagem,f"{base}_ENTREGA.qgz")
    logar(log,f"Inicio v{VERSAO_SCRIPT}. Pacote {nome}.")
    metas=metadados_arvore(camadas);usados=set();regs=[];primeira=True
    for ordem,m in enumerate(metas,1):
        c=m["camada"];tab=tabela_unica(c.name(),usados);logar(log,f"Exportando {ordem}/{len(metas)}: {c.name()} -> {tab}")
        mem,total,n,ids,invalidas,mud=camada_filtrada(c,tab);gravar(mem,gpkg,tab,primeira);primeira=False;validar_tabela(gpkg,tab,n,c.crs().authid())
        qml,ok=salvar_qml(c,os.path.join(montagem,"estilos"),tab,montagem);obs=[]
        if ids:obs.append(f"{len(ids)} feicao(oes) vazia(s) ignorada(s).")
        if invalidas:obs.append(f"{invalidas} geometria(s) invalida(s) preservada(s).")
        if mud:obs.append("Campos renomeados: "+", ".join(mud)+".")
        regs.append({"ordem":ordem,"status":"SUCESSO_COM_AVISO" if(ids or invalidas or mud or not ok) else "SUCESSO","nome_original":c.name(),"nome_tabela_gpkg":tab,"tipo_geometria":QgsWkbTypes.displayString(c.wkbType()),"possui_z":"SIM" if QgsWkbTypes.hasZ(c.wkbType()) else "NAO","possui_m":"SIM" if QgsWkbTypes.hasM(c.wkbType()) else "NAO","crs":c.crs().authid(),"crs_descricao":c.crs().description(),"provedor_origem":c.providerType(),"fonte_origem":c.source(),"quantidade_campos":len(c.fields()),"feicoes_origem":total,"feicoes_exportadas":n,"feicoes_vazias_ignoradas":len(ids),"ids_vazios_origem":",".join(ids),"geometrias_invalidas":invalidas,"estilo_qml":qml,"estilo_exportado":"SIM" if ok else "NAO","acao_geometrias_vazias":"IGNORADAS_NA_COPIA" if ids else "NAO_APLICAVEL","campos_renomeados":"; ".join(mud),"chave_primaria_gpkg":"gpkg_fid","grupos":"/".join(m["grupos"]),"visivel":"SIM" if m["visivel"] else "NAO","observacoes":" ".join(obs),"_tabela":tab,"_grupos":m["grupos"],"_visivel":m["visivel"],"_expandido":m["expandido"]})
    inventariar(inv,regs);estilos=criar_qgz(regs,gpkg,montagem,qgz,log,QgsProject.instance().crs());validar_qgz(qgz,montagem,len(regs));resumo,qtd=fechar(montagem,qgz,gpkg,regs,log)
    logar(log,f"Pacote validado: {len(regs)} camadas, {resumo['feicoes_exportadas']} feicoes, {qtd} hashes.")
    os.rename(montagem,final);montagem=None
    print("\n"+"="*80);print("PACOTE CONCLUIDO E VALIDADO");print("="*80);print(final);print(f"Camadas: {len(regs)} | Feicoes: {resumo['feicoes_exportadas']} | Vazias: {resumo['feicoes_vazias_ignoradas']} | Estilos: {estilos}/{len(regs)} | Hashes: {qtd}")
    QgsMessageLog.logMessage(f"Pacote validado: {final}","Empacotador",Qgis.Success)
    QMessageBox.information(iface.mainWindow(),"Entrega criada",f"Pacote criado e validado.\n\n{final}\n\nCamadas: {len(regs)}\nFeicoes exportadas: {resumo['feicoes_exportadas']}\nFeicoes vazias ignoradas: {resumo['feicoes_vazias_ignoradas']}\nHashes: {qtd}\n\nO QGZ esta na raiz e as fontes originais nao foram alteradas.")
except InterruptedError as e:print(str(e))
except Exception as e:
    print("\n"+"="*80+"\nERRO NO EMPACOTADOR\n"+"="*80);print(str(e));print("="*80)
    if montagem and os.path.isdir(montagem):
        try:shutil.rmtree(montagem);print("Pasta temporaria removida.")
        except Exception as le:print(f"Falha na limpeza: {le}")
    QgsMessageLog.logMessage(str(e),"Empacotador",Qgis.Critical)
    QMessageBox.critical(iface.mainWindow(),"Erro",f"Nao foi possivel concluir.\n\n{e}\n\nAs fontes originais nao foram modificadas.")
