# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Empacotador de Dados para Entrega Externa
Versao: 0.5.1
Autor: Eloizio Dantas

Descricao:
    Fluxo consolidado para QGIS 3.34 LTR ou superior:
    1. Le camadas vetoriais espaciais selecionadas no painel Camadas;
    2. Diagnostica CRS, geometrias vazias/invalidas, joins e edicoes abertas;
    3. Cria pasta versionada de entrega de forma atomica;
    4. Consolida os vetores em um unico GeoPackage;
    5. Ignora feicoes sem geometria somente na copia;
    6. Renomeia o atributo reservado fid para fid_orig na copia;
    7. Salva estilos QML e inventario CSV;
    8. Cria QGZ portatil na raiz com caminhos relativos;
    9. Reabre e valida o QGZ e as tabelas;
    10. Gera manifesto JSON, LEIA-ME, hashes SHA-256 e marcador de validacao.

Limitacoes:
    - Nao processa rasters, tabelas sem geometria, joins ou relacoes.
    - Nao remove campos sensiveis nesta versao.
    - Nao corrige geometrias invalidas automaticamente.
    - O log ativo de fechamento nao integra a lista de hashes.
===============================================================================
"""

import csv
import hashlib
import json
import os
import platform
import re
import shutil
import tempfile
import unicodedata
import zipfile
from collections import Counter
from datetime import datetime

from qgis.core import (
    Qgis, QgsApplication, QgsFeature, QgsField, QgsLayerTreeGroup,
    QgsMapLayerType, QgsMessageLog, QgsProject, QgsVectorFileWriter,
    QgsVectorLayer, QgsWkbTypes
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QVBoxLayout
)
from qgis.utils import iface

VERSAO_SCRIPT = "0.5.1"
NOME_GPKG = "dados_entrega.gpkg"
NOME_INVENTARIO = "inventario_camadas.csv"
NOME_MANIFESTO = "manifesto_pacote.json"
NOME_HASHES = "verificacao_integridade.sha256"
NOME_LEIA_ME = "LEIA-ME.txt"
NOME_VALIDACAO = "PACOTE_VALIDADO.txt"
NOME_LOG = "empacotamento.log"
MAX_NOME_TABELA = 60

CAMPOS_INVENTARIO = [
    "ordem", "status", "nome_original", "nome_tabela_gpkg",
    "tipo_geometria", "possui_z", "possui_m", "crs", "crs_descricao",
    "provedor_origem", "fonte_origem", "quantidade_campos",
    "feicoes_origem", "feicoes_exportadas", "feicoes_vazias_ignoradas",
    "ids_vazios_origem", "geometrias_invalidas", "estilo_qml",
    "estilo_exportado", "acao_geometrias_vazias", "campos_renomeados",
    "chave_primaria_gpkg", "grupos", "visivel", "observacoes"
]


def agora_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(caminho, raiz):
    return os.path.relpath(caminho, raiz).replace("\\", "/")


def sem_acentos(texto):
    txt = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in txt if not unicodedata.combining(c))


def normalizar(nome, maiusculo=False, limite=60, remover_data=False):
    nome = sem_acentos(nome)
    if remover_data:
        nome = re.sub(r"^\s*\d{4}[-_]\d{2}[-_]\d{2}[-_\s]*", "", nome)
    nome = re.sub(r"[^A-Za-z0-9]+", "_", nome)
    nome = re.sub(r"_+", "_", nome).strip("_") or "camada"
    if nome[0].isdigit():
        nome = "camada_" + nome
    nome = nome.upper() if maiusculo else nome.lower()
    return nome[:limite].rstrip("_")


def nome_base_projeto():
    arq = QgsProject.instance().fileName()
    base = os.path.splitext(os.path.basename(arq))[0] if arq else "PROJETO_QGIS"
    return normalizar(base, True, 70)


def proxima_versao(destino, nome_base):
    data = datetime.now().strftime("%Y%m%d")
    n = 1
    while True:
        nome = f"ENTREGA_{nome_base}_{data}_v{n:03d}"
        final = os.path.join(destino, nome)
        montagem = final + "_EM_MONTAGEM"
        if not os.path.exists(final) and not os.path.exists(montagem):
            return nome, final, montagem
        n += 1


def registrar(log, mensagem):
    linha = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {mensagem}"
    print(linha)
    with open(log, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def caminho_grupos(no):
    grupos = []
    pai = no.parent() if no else None
    while pai is not None:
        if isinstance(pai, QgsLayerTreeGroup) and pai.name():
            grupos.append(pai.name())
        pai = pai.parent()
    return list(reversed(grupos))


def posicao_arvore(no):
    pos = []
    atual = no
    while atual and atual.parent() is not None:
        pai = atual.parent()
        try:
            pos.append(pai.children().index(atual))
        except ValueError:
            pos.append(0)
        atual = pai
    return tuple(reversed(pos))


def capturar_arvore(camadas):
    raiz = QgsProject.instance().layerTreeRoot()
    saida = []
    for camada in camadas:
        no = raiz.findLayer(camada.id())
        saida.append({
            "camada": camada,
            "grupos": caminho_grupos(no),
            "posicao": posicao_arvore(no) if no else (999999,),
            "visivel": no.itemVisibilityChecked() if no else True,
            "expandido": no.isExpanded() if no else True
        })
    return sorted(saida, key=lambda x: x["posicao"])


def diagnosticar_camada(camada):
    vazias = invalidas = 0
    ids_vazios = []
    for ft in camada.getFeatures():
        g = ft.geometry()
        if g is None or g.isNull() or g.isEmpty():
            vazias += 1
            ids_vazios.append(str(ft.id()))
            continue
        try:
            if not g.isGeosValid():
                invalidas += 1
        except Exception:
            pass
    try:
        joins = len(camada.vectorJoins())
    except Exception:
        joins = 0
    return {"vazias": vazias, "invalidas": invalidas,
            "ids_vazios": ids_vazios, "joins": joins}


def validar_camadas(camadas):
    bloqueios, avisos, diagnosticos = [], [], {}
    for c in camadas:
        if c.type() != QgsMapLayerType.VectorLayer:
            bloqueios.append(f"{c.name()}: nao e vetorial.")
            continue
        if not c.isSpatial():
            bloqueios.append(f"{c.name()}: tabela sem geometria.")
            continue
        if not c.isValid():
            bloqueios.append(f"{c.name()}: camada invalida.")
            continue
        if not c.crs().isValid():
            bloqueios.append(f"{c.name()}: CRS ausente ou invalido.")
        if c.isEditable():
            bloqueios.append(f"{c.name()}: possui edicao aberta.")
        d = diagnosticar_camada(c)
        diagnosticos[c.id()] = d
        if d["joins"]:
            bloqueios.append(f"{c.name()}: possui join ativo.")
        if d["vazias"]:
            avisos.append(f"{c.name()}: {d['vazias']} feicao(oes) sem geometria.")
        if d["invalidas"]:
            avisos.append(f"{c.name()}: {d['invalidas']} geometria(s) invalida(s).")
    return bloqueios, avisos, diagnosticos


class JanelaEmpacotador(QDialog):
    def __init__(self, camadas, parent=None):
        super().__init__(parent)
        self.camadas = camadas
        self.setWindowTitle("Empacotador de Dados para Entrega Externa")
        self.setMinimumWidth(720)
        self.setMinimumHeight(590)
        self.setWindowModality(Qt.ApplicationModal)
        lay = QVBoxLayout(self)
        texto = QLabel(
            "<b>Modalidade:</b> Entrega externa<br><br>"
            "As camadas selecionadas serao consolidadas em um GeoPackage, "
            "com projeto QGZ portatil, inventario, estilos, manifesto e hashes."
        )
        texto.setWordWrap(True); lay.addWidget(texto)
        grupo = QGroupBox("Camadas selecionadas"); gl = QVBoxLayout(grupo)
        lista = QListWidget()
        for c in camadas:
            crs = c.crs().authid() if c.crs().isValid() else "CRS invalido"
            item = QListWidgetItem(
                f"{c.name()} | {QgsWkbTypes.displayString(c.wkbType())} | "
                f"{crs} | {c.featureCount()} registro(s)"
            )
            item.setToolTip(c.source()); lista.addItem(item)
        gl.addWidget(lista); gl.addWidget(QLabel(f"<b>Total:</b> {len(camadas)} camada(s)"))
        lay.addWidget(grupo)
        ident = QGroupBox("Identificacao e destino"); il = QVBoxLayout(ident)
        il.addWidget(QLabel("Nome-base da entrega:"))
        self.nome = QLineEdit(nome_base_projeto()); il.addWidget(self.nome)
        il.addWidget(QLabel("Pasta de destino:"))
        linha = QHBoxLayout(); self.destino = QLineEdit(); self.destino.setReadOnly(True)
        botao = QPushButton("Selecionar..."); botao.clicked.connect(self.escolher)
        linha.addWidget(self.destino); linha.addWidget(botao); il.addLayout(linha); lay.addWidget(ident)
        regras = QLabel(
            "<b>Regras:</b><br>"
            "• as fontes originais nao serao alteradas;<br>"
            "• feicoes sem geometria serao ignoradas somente na copia;<br>"
            "• o campo fid sera preservado como fid_orig quando necessario;<br>"
            "• geometrias invalidas serao preservadas e registradas;<br>"
            "• caminhos relativos e validacao final sao obrigatorios."
        )
        regras.setWordWrap(True); lay.addWidget(regras)
        botoes = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Ok).setText("Criar pacote completo")
        botoes.accepted.connect(self.validar); botoes.rejected.connect(self.reject)
        lay.addWidget(botoes)

    def escolher(self):
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta de destino", os.path.expanduser("~"))
        if pasta: self.destino.setText(pasta)

    def validar(self):
        if not self.nome.text().strip():
            QMessageBox.warning(self, "Nome ausente", "Informe o nome-base da entrega."); return
        destino = self.destino.text().strip()
        if not destino or not os.path.isdir(destino) or not os.access(destino, os.W_OK):
            QMessageBox.warning(self, "Destino invalido", "Selecione uma pasta existente com permissao de gravacao."); return
        self.accept()

    def config(self):
        return {"nome_base": normalizar(self.nome.text(), True, 70),
                "destino": self.destino.text().strip()}


def nome_campo_unico(base, usados):
    candidato, n = base, 2
    while candidato.lower() in usados:
        candidato = f"{base}_{n}"; n += 1
    usados.add(candidato.lower())
    return candidato


def preparar_campos(camada):
    campos, alteracoes, usados = [], [], set()
    for original in camada.fields():
        nome = original.name()
        saida = nome_campo_unico("fid_orig" if nome.lower().strip() == "fid" else nome, usados)
        novo = QgsField(original); novo.setName(saida); campos.append(novo)
        if saida != nome: alteracoes.append(f"{nome} -> {saida}")
    return campos, alteracoes


def criar_camada_filtrada(camada, nome_tabela):
    uri = f"{QgsWkbTypes.displayString(camada.wkbType())}?crs={camada.crs().authid()}"
    out = QgsVectorLayer(uri, nome_tabela, "memory")
    if not out.isValid(): raise Exception(f"Falha ao criar memoria para {camada.name()}.")
    campos, renomeados = preparar_campos(camada)
    if campos and not out.dataProvider().addAttributes(campos):
        raise Exception(f"Falha ao copiar campos de {camada.name()}.")
    out.updateFields(); feats = []; vazios = []; invalidas = 0; total = 0
    for ft in camada.getFeatures():
        total += 1; g = ft.geometry()
        if g is None or g.isNull() or g.isEmpty():
            vazios.append(str(ft.id())); continue
        try:
            if not g.isGeosValid(): invalidas += 1
        except Exception: pass
        novo = QgsFeature(out.fields()); novo.setGeometry(g); novo.setAttributes(list(ft.attributes())); feats.append(novo)
    if not feats: raise Exception(f"{camada.name()} nao possui feicao espacial exportavel.")
    if not out.dataProvider().addFeatures(feats): raise Exception(f"Falha ao copiar feicoes de {camada.name()}.")
    out.updateExtents()
    return {"camada": out, "origem": total, "exportadas": len(feats),
            "vazias": len(vazios), "ids_vazios": vazios,
            "invalidas": invalidas, "renomeados": renomeados}


def nome_tabela_unico(nome, usados):
    base = normalizar(nome, False, MAX_NOME_TABELA, remover_data=True)
    candidato, n = base, 2
    while candidato.lower() in usados:
        sufixo = f"_{n:02d}"; candidato = base[:MAX_NOME_TABELA-len(sufixo)].rstrip("_") + sufixo; n += 1
    usados.add(candidato.lower()); return candidato


def gravar_gpkg(camada, caminho, tabela, primeira):
    op = QgsVectorFileWriter.SaveVectorOptions()
    op.driverName = "GPKG"; op.fileEncoding = "UTF-8"; op.layerName = tabela
    op.layerOptions = ["FID=gpkg_fid"]
    op.actionOnExistingFile = (QgsVectorFileWriter.CreateOrOverwriteFile if primeira
                               else QgsVectorFileWriter.CreateOrOverwriteLayer)
    res = QgsVectorFileWriter.writeAsVectorFormatV3(camada, caminho, QgsProject.instance().transformContext(), op)
    if res[0] != QgsVectorFileWriter.NoError:
        msg = str(res[1]) if len(res) > 1 else "Erro nao identificado"
        raise Exception(f"Falha ao gravar tabela {tabela}: {msg}")


def validar_tabela(gpkg, tabela, esperado, crs):
    c = QgsVectorLayer(f"{gpkg}|layername={tabela}", tabela, "ogr")
    if not c.isValid(): raise Exception(f"Tabela {tabela} nao pode ser reaberta.")
    if c.featureCount() != esperado: raise Exception(f"Contagem divergente em {tabela}.")
    if crs and c.crs().authid() and c.crs().authid() != crs: raise Exception(f"CRS divergente em {tabela}.")


def salvar_estilo(camada, pasta, tabela):
    caminho = os.path.join(pasta, tabela + ".qml")
    try:
        camada.saveNamedStyle(caminho)
        return rel(caminho, os.path.dirname(pasta)), os.path.isfile(caminho)
    except Exception:
        return "", False


def escrever_inventario(caminho, registros):
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_INVENTARIO, delimiter=";", extrasaction="ignore")
        w.writeheader(); w.writerows(registros)


def configurar_relativos(projeto):
    try:
        projeto.setFilePathStorage(Qgis.FilePathType.Relative); return
    except Exception: pass
    projeto.writeEntry("Paths", "/Absolute", False)


def obter_ou_criar_grupo(raiz, nomes, cache):
    atual, chave = raiz, []
    for nome in nomes:
        chave.append(nome); k = tuple(chave)
        if k not in cache: cache[k] = atual.addGroup(nome)
        atual = cache[k]
    return atual


def criar_qgz(registros, gpkg, pasta, caminho_qgz, log, crs_projeto):
    projeto = QgsProject(); projeto.setTitle(os.path.splitext(os.path.basename(caminho_qgz))[0])
    if crs_projeto.isValid(): projeto.setCrs(crs_projeto)
    projeto.setFileName(caminho_qgz); configurar_relativos(projeto)
    raiz = projeto.layerTreeRoot(); cache = {}; estilos = 0
    for i, r in enumerate(sorted(registros, key=lambda x: tuple(x["posicao"])), 1):
        c = QgsVectorLayer(f"{gpkg}|layername={r['nome_tabela_gpkg']}", r["nome_original"], "ogr")
        if not c.isValid(): raise Exception(f"Falha ao carregar {r['nome_original']} no projeto.")
        qml = os.path.join(pasta, r["estilo_qml"].replace("/", os.sep)) if r["estilo_qml"] else ""
        if qml and os.path.isfile(qml):
            try:
                retorno = c.loadNamedStyle(qml)
                sucesso = bool(retorno[1]) if isinstance(retorno, tuple) and len(retorno) > 1 else True
                if sucesso: estilos += 1
            except Exception: pass
        projeto.addMapLayer(c, False)
        no = obter_ou_criar_grupo(raiz, r["grupos_lista"], cache).addLayer(c)
        no.setItemVisibilityChecked(r["visivel_bool"]); no.setExpanded(r["expandido_bool"])
        registrar(log, f"Camada {i}/{len(registros)} adicionada ao QGZ: {r['nome_original']}")
    projeto.setCustomVariables({"modalidade_pacote": "ENTREGA_EXTERNA",
        "versao_empacotador": VERSAO_SCRIPT, "data_empacotamento": agora_iso(),
        "quantidade_camadas": len(registros), "geopackage_relativo": "dados/vetores/dados_entrega.gpkg"})
    if not projeto.write(caminho_qgz): raise Exception("Falha ao gravar QGZ.")
    projeto.clear()
    return estilos


def validar_qgz(caminho_qgz, pasta, esperado):
    if not zipfile.is_zipfile(caminho_qgz): raise Exception("QGZ sem estrutura ZIP valida.")
    p = QgsProject()
    if not p.read(caminho_qgz): raise Exception("QGZ nao pode ser reaberto.")
    camadas = list(p.mapLayers().values())
    if len(camadas) != esperado: raise Exception("Quantidade de camadas divergente no QGZ.")
    base = os.path.realpath(pasta)
    for c in camadas:
        if not c.isValid(): raise Exception(f"Camada invalida no QGZ: {c.name()}")
        fonte = os.path.realpath(c.source().split("|")[0])
        try: dentro = os.path.commonpath([base, fonte]) == base
        except ValueError: dentro = False
        if not dentro: raise Exception(f"Fonte fora do pacote: {c.name()}")
    p.clear()
    with zipfile.ZipFile(caminho_qgz, "r") as z:
        qgs = [n for n in z.namelist() if n.lower().endswith(".qgs")]
        if not qgs: raise Exception("QGZ sem QGS interno.")
        xml = z.read(qgs[0]).decode("utf-8", errors="replace")
    gpkg_abs = os.path.join(pasta, "dados", "vetores", NOME_GPKG)
    if gpkg_abs in xml or gpkg_abs.replace("\\", "/") in xml:
        raise Exception("Caminho absoluto encontrado no QGZ.")
    if "dados/vetores/dados_entrega.gpkg" not in xml and "dados\\vetores\\dados_entrega.gpkg" not in xml:
        raise Exception("Referencia relativa ao GeoPackage nao confirmada no QGZ.")


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""): h.update(bloco)
    return h.hexdigest()


def arquivos_para_hash(pasta):
    excluir = {NOME_MANIFESTO, NOME_HASHES, NOME_LEIA_ME, NOME_VALIDACAO, NOME_LOG}
    saida = []
    for raiz, dirs, nomes in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", ".qgis"} and not d.startswith("fechamento_")]
        for nome in nomes:
            if nome in excluir: continue
            caminho = os.path.join(raiz, nome)
            if os.path.isfile(caminho): saida.append(caminho)
    return sorted(saida, key=lambda x: rel(x, pasta).lower())


def versao_qgis():
    try: return Qgis.QGIS_VERSION
    except Exception:
        try: return QgsApplication.qgisVersion()
        except Exception: return "Nao identificada"


def fechar_pacote(pasta, qgz, gpkg, inventario, log, registros):
    arquivos = arquivos_para_hash(pasta); hashes = []
    for i, arq in enumerate(arquivos, 1):
        registrar(log, f"Hash {i}/{len(arquivos)}: {rel(arq, pasta)}")
        hashes.append({"arquivo": rel(arq, pasta), "sha256": sha256(arq), "tamanho_bytes": os.path.getsize(arq)})
    resumo = {
        "camadas": len(registros),
        "feicoes_origem": sum(int(r["feicoes_origem"]) for r in registros),
        "feicoes_exportadas": sum(int(r["feicoes_exportadas"]) for r in registros),
        "feicoes_vazias_ignoradas": sum(int(r["feicoes_vazias_ignoradas"]) for r in registros),
        "geometrias_invalidas": sum(int(r["geometrias_invalidas"]) for r in registros),
        "crs": sorted({r["crs"] for r in registros if r["crs"]})
    }
    manifesto = {
        "pacote": {"id": os.path.basename(pasta), "modalidade": "ENTREGA_EXTERNA", "status": "VALIDADO",
                   "validado_em": agora_iso(), "versao_empacotador": VERSAO_SCRIPT},
        "ambiente": {"qgis": versao_qgis(), "python": platform.python_version(), "sistema_operacional": platform.platform()},
        "projeto": {"arquivo": rel(qgz, pasta), "quantidade_camadas": len(registros),
                    "camadas_invalidas": 0, "fontes_fora_pacote": 0},
        "dados": {"geopackage": rel(gpkg, pasta), **resumo},
        "integridade": {"algoritmo": "SHA-256", "arquivo_hashes": NOME_HASHES,
            "arquivos_verificados": len(hashes), "arquivos_excluidos": [
                {"arquivo": f"logs/{NOME_LOG}", "motivo": "Log ativo durante o fechamento."},
                {"arquivo": NOME_MANIFESTO, "motivo": "Evitar dependencia circular."},
                {"arquivo": NOME_HASHES, "motivo": "O arquivo nao pode conter o proprio hash."},
                {"arquivo": NOME_LEIA_ME, "motivo": "Gerado no fechamento."},
                {"arquivo": NOME_VALIDACAO, "motivo": "Gerado apos a verificacao."}],
            "arquivos": hashes},
        "premissas": ["CRS declarados nas fontes foram considerados corretos.",
                      "Feicoes sem geometria foram ignoradas somente na copia.",
                      "Geometrias invalidas nao foram corrigidas automaticamente."]
    }
    temp = tempfile.mkdtemp(prefix="fechamento_", dir=pasta)
    try:
        man_t = os.path.join(temp, NOME_MANIFESTO); hash_t = os.path.join(temp, NOME_HASHES)
        leia_t = os.path.join(temp, NOME_LEIA_ME); val_t = os.path.join(temp, NOME_VALIDACAO)
        with open(man_t, "w", encoding="utf-8") as f: json.dump(manifesto, f, ensure_ascii=False, indent=2); f.write("\n")
        with open(hash_t, "w", encoding="utf-8", newline="\n") as f:
            for h in hashes: f.write(f"{h['sha256']}  {h['arquivo']}\n")
        leia = f"""PACOTE QGIS PARA ENTREGA EXTERNA
================================
Pacote: {os.path.basename(pasta)}
Status: VALIDADO
Projeto: {os.path.basename(qgz)}
GeoPackage: dados/vetores/{NOME_GPKG}
Camadas: {resumo['camadas']}
Feicoes de origem: {resumo['feicoes_origem']}
Feicoes exportadas: {resumo['feicoes_exportadas']}
Feicoes sem geometria ignoradas: {resumo['feicoes_vazias_ignoradas']}
CRS: {', '.join(resumo['crs'])}

COMO ABRIR
1. Mantenha toda a estrutura da pasta.
2. Abra o arquivo QGZ na raiz no QGIS.
3. Nao mova apenas o QGZ ou o GeoPackage isoladamente.

INTEGRIDADE
Os hashes SHA-256 estao em {NOME_HASHES}.
O log ativo logs/{NOME_LOG} nao integra a lista de hashes porque continua
recebendo registros durante o fechamento.

LIMITACOES
A validacao confirma estrutura e integridade digital. Nao comprova exatidao
posicional, titularidade, validade registral ou autorizacao de compartilhamento.
"""
        with open(leia_t, "w", encoding="utf-8", newline="\n") as f: f.write(leia)
        marcador = f"""PACOTE VALIDADO
===============
Pacote: {os.path.basename(pasta)}
Status: VALIDADO
Validado em: {agora_iso()}
Versao: {VERSAO_SCRIPT}
Projeto: {os.path.basename(qgz)}
Camadas: {resumo['camadas']}
Feicoes exportadas: {resumo['feicoes_exportadas']}
Feicoes vazias ignoradas: {resumo['feicoes_vazias_ignoradas']}
Arquivos com SHA-256: {len(hashes)}
Hash QGZ: {sha256(qgz)}
Hash GeoPackage: {sha256(gpkg)}
Hash manifesto: {sha256(man_t)}
"""
        with open(val_t, "w", encoding="utf-8", newline="\n") as f: f.write(marcador)
        for origem, destino in [(man_t, os.path.join(pasta, NOME_MANIFESTO)),
                                (hash_t, os.path.join(pasta, NOME_HASHES)),
                                (leia_t, os.path.join(pasta, NOME_LEIA_ME)),
                                (val_t, os.path.join(pasta, NOME_VALIDACAO))]:
            os.replace(origem, destino)
    finally:
        if os.path.isdir(temp): shutil.rmtree(temp)
    return resumo, len(hashes)


# =============================================================================
# PROCESSAMENTO PRINCIPAL
# =============================================================================

caminho_montagem = None
try:
    print("\n" + "=" * 80)
    print("EMPACOTADOR DE DADOS PARA ENTREGA EXTERNA - VERSAO 0.5.1")
    print("=" * 80)
    camadas = iface.layerTreeView().selectedLayers()
    if not camadas:
        raise Exception("Nenhuma camada selecionada no painel Camadas.")
    bloqueios, avisos, diagnosticos = validar_camadas(camadas)
    if bloqueios:
        raise Exception("Ocorrencias impeditivas:\n\n" + "\n".join(f"• {x}" for x in bloqueios))
    if avisos:
        resposta = QMessageBox.question(
            iface.mainWindow(), "Avisos do diagnostico",
            "Foram encontrados avisos:\n\n" + "\n".join(f"• {x}" for x in avisos[:15]) +
            "\n\nFeicoes sem geometria serao ignoradas somente na copia. "
            "Geometrias invalidas serao preservadas. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if resposta != QMessageBox.Yes: raise InterruptedError("Operacao cancelada.")
    janela = JanelaEmpacotador(camadas, iface.mainWindow())
    if janela.exec_() != QDialog.Accepted: raise InterruptedError("Operacao cancelada.")
    cfg = janela.config(); nome_pasta, caminho_final, caminho_montagem = proxima_versao(cfg["destino"], cfg["nome_base"])
    os.makedirs(os.path.join(caminho_montagem, "dados", "vetores"))
    os.makedirs(os.path.join(caminho_montagem, "estilos"))
    os.makedirs(os.path.join(caminho_montagem, "logs"))
    log = os.path.join(caminho_montagem, "logs", NOME_LOG)
    gpkg = os.path.join(caminho_montagem, "dados", "vetores", NOME_GPKG)
    inventario = os.path.join(caminho_montagem, NOME_INVENTARIO)
    qgz = os.path.join(caminho_montagem, f"{cfg['nome_base']}_ENTREGA.qgz")
    registrar(log, f"Inicio. Versao {VERSAO_SCRIPT}. Pacote {nome_pasta}.")
    arvore = capturar_arvore(camadas); usados = set(); registros = []; primeira = True
    for ordem, meta in enumerate(arvore, 1):
        c = meta["camada"]; tabela = nome_tabela_unico(c.name(), usados)
        registrar(log, f"Exportando {ordem}/{len(arvore)}: {c.name()} -> {tabela}")
        r = criar_camada_filtrada(c, tabela)
        gravar_gpkg(r["camada"], gpkg, tabela, primeira); primeira = False
        validar_tabela(gpkg, tabela, r["exportadas"], c.crs().authid())
        estilo_rel, estilo_ok = salvar_estilo(c, os.path.join(caminho_montagem, "estilos"), tabela)
        status = "SUCESSO_COM_AVISO" if (r["vazias"] or r["invalidas"] or r["renomeados"] or not estilo_ok) else "SUCESSO"
        obs = []
        if r["vazias"]: obs.append(f"{r['vazias']} feicao(oes) vazia(s) ignorada(s).")
        if r["invalidas"]: obs.append(f"{r['invalidas']} geometria(s) invalida(s) preservada(s).")
        if r["renomeados"]: obs.append("Campos renomeados: " + ", ".join(r["renomeados"]) + ".")
        registros.append({
            "ordem": ordem, "status": status, "nome_original": c.name(), "nome_tabela_gpkg": tabela,
            "tipo_geometria": QgsWkbTypes.displayString(c.wkbType()),
            "possui_z": "SIM" if QgsWkbTypes.hasZ(c.wkbType()) else "NAO",
            "possui_m": "SIM" if QgsWkbTypes.hasM(c.wkbType()) else "NAO",
            "crs": c.crs().authid(), "crs_descricao": c.crs().description(),
            "provedor_origem": c.providerType(), "fonte_origem": c.source(),
            "quantidade_campos": len(c.fields()), "feicoes_origem": r["origem"],
            "feicoes_exportadas": r["exportadas"], "feicoes_vazias_ignoradas": r["vazias"],
            "ids_vazios_origem": ",".join(r["ids_vazios"]), "geometrias_invalidas": r["invalidas"],
            "estilo_qml": estilo_rel, "estilo_exportado": "SIM" if estilo_ok else "NAO",
            "acao_geometrias_vazias": "IGNORADAS_NA_COPIA" if r["vazias"] else "NAO_APLICAVEL",
            "campos_renomeados": "; ".join(r["renomeados"]), "chave_primaria_gpkg": "gpkg_fid",
            "grupos": "/".join(meta["grupos"]), "grupos_lista": meta["grupos"],
            "visivel": "SIM" if meta["visivel"] else "NAO", "visivel_bool": meta["visivel"],
            "expandido_bool": meta["expandido"], "posicao": meta["posicao"], "observacoes": " ".join(obs)
        })
    escrever_inventario(inventario, registros)
    estilos = criar_qgz(registros, gpkg, caminho_montagem, qgz, log, QgsProject.instance().crs())
    validar_qgz(qgz, caminho_montagem, len(registros))
    resumo, qtd_hashes = fechar_pacote(caminho_montagem, qgz, gpkg, inventario, log, registros)
    registrar(log, f"Pacote validado. Camadas {len(registros)}; feicoes {resumo['feicoes_exportadas']}; hashes {qtd_hashes}.")
    os.rename(caminho_montagem, caminho_final); caminho_montagem = None
    print("\n" + "=" * 80)
    print("PACOTE CONCLUIDO E VALIDADO")
    print("=" * 80)
    print(f"Pasta: {caminho_final}")
    print(f"Projeto: {cfg['nome_base']}_ENTREGA.qgz")
    print(f"Camadas: {len(registros)}")
    print(f"Feicoes de origem: {resumo['feicoes_origem']}")
    print(f"Feicoes exportadas: {resumo['feicoes_exportadas']}")
    print(f"Feicoes vazias ignoradas: {resumo['feicoes_vazias_ignoradas']}")
    print(f"Estilos aplicados: {estilos}/{len(registros)}")
    print(f"Arquivos com SHA-256: {qtd_hashes}")
    print("=" * 80)
    QgsMessageLog.logMessage(f"Pacote externo validado: {caminho_final}", "Empacotador", Qgis.Success)
    QMessageBox.information(iface.mainWindow(), "Entrega criada",
        "Pacote criado e validado com sucesso.\n\n"
        f"Pasta:\n{caminho_final}\n\n"
        f"Camadas: {len(registros)}\nFeicoes exportadas: {resumo['feicoes_exportadas']}\n"
        f"Feicoes vazias ignoradas: {resumo['feicoes_vazias_ignoradas']}\n"
        f"Arquivos com SHA-256: {qtd_hashes}\n\n"
        "O projeto QGZ esta na raiz e as fontes originais nao foram alteradas.")
except InterruptedError as erro:
    print(str(erro))
except Exception as erro:
    print("\n" + "=" * 80 + "\nERRO NO EMPACOTADOR\n" + "=" * 80)
    print(str(erro)); print("=" * 80)
    if caminho_montagem and os.path.isdir(caminho_montagem):
        try: shutil.rmtree(caminho_montagem); print("Pasta temporaria removida.")
        except Exception as e: print(f"Falha ao remover pasta temporaria: {e}")
    QgsMessageLog.logMessage(str(erro), "Empacotador", Qgis.Critical)
    QMessageBox.critical(iface.mainWindow(), "Erro no empacotamento",
        f"Nao foi possivel concluir o pacote.\n\nDetalhes:\n{erro}\n\nAs fontes originais nao foram modificadas.")
