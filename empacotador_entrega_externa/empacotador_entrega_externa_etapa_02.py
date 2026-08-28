# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Empacotador de Dados para Entrega Externa
Etapa: 02 - Diagnóstico Técnico das Camadas

Descrição:
    Segunda etapa do desenvolvimento do Empacotador de Dados para Entrega
    Externa.

    O script analisa as camadas selecionadas no painel Camadas e verifica:

    - tipo da camada;
    - provedor e fonte;
    - CRS;
    - tipo de geometria;
    - quantidade de feições;
    - geometrias vazias;
    - geometrias inválidas;
    - geometrias duplicadas;
    - joins;
    - filtros ativos;
    - alterações não salvas;
    - campos potencialmente sensíveis;
    - natureza local, remota ou temporária da fonte;
    - ação recomendada para o empacotamento.

    Nesta etapa, nenhum arquivo é criado, copiado, removido ou modificado.

Autor: Eloízio Dantas
Data de Criação: 2026-08-27
Versão: 0.2.0

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x

Premissas e Limitações:
    - As camadas devem estar selecionadas no painel Camadas.
    - Geometrias inválidas são apenas identificadas.
    - Campos sensíveis são apenas candidatos para revisão humana.
    - A presença de um nome de campo na lista de padrões não comprova
      que o conteúdo seja efetivamente pessoal, confidencial ou restrito.
===============================================================================
"""


# =============================================================================
# 1. IMPORTAÇÕES
# =============================================================================

import os
import re
import time
import hashlib

from collections import Counter

from qgis.core import (
    QgsMapLayerType,
    QgsMessageLog,
    QgsProject,
    QgsWkbTypes,
    Qgis
)

from qgis.PyQt.QtWidgets import (
    QMessageBox
)

from qgis.utils import iface


# =============================================================================
# 2. CONFIGURAÇÕES
# =============================================================================

# Termos utilizados apenas para localizar campos que merecem revisão
# antes de uma entrega externa.
#
# Nenhum campo será removido automaticamente nesta etapa.

PADROES_CAMPOS_SENSIVEIS = [
    "cpf",
    "cnpj",
    "email",
    "e_mail",
    "telefone",
    "tel",
    "celular",
    "fone",
    "proprietario",
    "proprietário",
    "responsavel",
    "responsável",
    "interessado",
    "requerente",
    "contato",
    "endereco",
    "endereço",
    "observacao_interna",
    "observação_interna",
    "anotacao_interna",
    "anotação_interna",
    "usuario",
    "usuário",
    "login",
    "senha",
    "password",
    "token",
    "secret",
    "segredo",
    "matricula_funcional"
]


# Provedores normalmente relacionados a serviços ou bancos remotos.

PROVEDORES_REMOTOS = {
    "postgres",
    "mssql",
    "oracle",
    "wfs",
    "arcgisfeatureserver",
    "vectortile",
    "xyz",
    "wms",
    "wcs",
    "arcgismapserver"
}


# =============================================================================
# 3. FUNÇÕES DE TEXTO
# =============================================================================

def remover_acentos_simples(texto):
    """
    Remove os acentos mais comuns para facilitar comparações de nomes.
    """

    substituicoes = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "ä": "a",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ö": "o",
        "ú": "u",
        "ü": "u",
        "ç": "c"
    }

    resultado = texto.lower()

    for original, substituto in substituicoes.items():
        resultado = resultado.replace(
            original,
            substituto
        )

    return resultado


def normalizar_nome_para_comparacao(texto):
    """
    Normaliza um nome para comparação com padrões sensíveis.
    """

    texto = remover_acentos_simples(
        str(texto)
    )

    texto = re.sub(
        r"[^a-z0-9]+",
        "_",
        texto
    )

    return texto.strip("_")


def abreviar_texto(texto, limite=110):
    """
    Abrevia textos longos para exibição segura no console.
    """

    texto = str(texto)

    if len(texto) <= limite:
        return texto

    return texto[:limite - 3] + "..."


# =============================================================================
# 4. CLASSIFICAÇÃO DA CAMADA E DA FONTE
# =============================================================================

def classificar_tipo_camada(camada):
    """
    Classifica a camada como Vetor, Tabela, Raster ou Outro.
    """

    if camada.type() == QgsMapLayerType.VectorLayer:

        if camada.isSpatial():
            return "Vetor"

        return "Tabela"

    if camada.type() == QgsMapLayerType.RasterLayer:
        return "Raster"

    return "Outro"


def classificar_fonte(camada):
    """
    Classifica a fonte como temporária, remota, local ou desconhecida.

    Retorno:
        Dicionário com tipo, persistência e observação.
    """

    provedor = camada.providerType().lower()
    fonte = camada.source()
    fonte_normalizada = fonte.lower()

    # ---------------------------------------------------------------------
    # FONTES TEMPORÁRIAS
    # ---------------------------------------------------------------------

    if provedor == "memory":

        return {
            "tipo": "TEMPORARIA",
            "persistente": False,
            "observacao": (
                "Camada em memória. Precisa ser materializada "
                "no GeoPackage da entrega."
            )
        }

    if fonte_normalizada.startswith("memory:"):

        return {
            "tipo": "TEMPORARIA",
            "persistente": False,
            "observacao": (
                "Fonte temporária. Precisa ser exportada "
                "antes do fechamento do projeto."
            )
        }

    # ---------------------------------------------------------------------
    # FONTES REMOTAS
    # ---------------------------------------------------------------------

    if provedor in PROVEDORES_REMOTOS:

        return {
            "tipo": "REMOTA",
            "persistente": True,
            "observacao": (
                "Fonte remota. Deve ser materializada para que "
                "o pacote funcione sem conexão ou credenciais."
            )
        }

    marcadores_remotos = [
        "http://",
        "https://",
        "service=",
        "url=",
        "host=",
        "dbname=",
        "authcfg="
    ]

    if any(
        marcador in fonte_normalizada
        for marcador in marcadores_remotos
    ):

        return {
            "tipo": "REMOTA",
            "persistente": True,
            "observacao": (
                "A URI indica uma fonte remota ou autenticada. "
                "A entrega não deve preservar credenciais."
            )
        }

    # ---------------------------------------------------------------------
    # FONTES LOCAIS
    # ---------------------------------------------------------------------

    caminho_base = fonte.split("|")[0]

    if os.path.exists(caminho_base):

        return {
            "tipo": "LOCAL",
            "persistente": True,
            "observacao": "Fonte local localizada no sistema de arquivos."
        }

    # Algumas fontes OGR usam URIs que não são caminhos simples.

    if provedor == "ogr":

        return {
            "tipo": "LOCAL_OU_URI_OGR",
            "persistente": True,
            "observacao": (
                "Fonte OGR. O caminho será validado novamente "
                "durante a exportação."
            )
        }

    return {
        "tipo": "DESCONHECIDA",
        "persistente": False,
        "observacao": (
            "Não foi possível determinar com segurança "
            "a natureza da fonte."
        )
    }


# =============================================================================
# 5. CAMPOS POTENCIALMENTE SENSÍVEIS
# =============================================================================

def localizar_campos_potencialmente_sensiveis(camada):
    """
    Localiza campos cujos nomes coincidem com padrões de revisão.

    A função avalia apenas os nomes dos campos.
    Nenhum valor das feições é exibido ou registrado.
    """

    campos_localizados = []

    padroes_normalizados = [
        normalizar_nome_para_comparacao(padrao)
        for padrao in PADROES_CAMPOS_SENSIVEIS
    ]

    for campo in camada.fields():

        nome_original = campo.name()

        nome_normalizado = normalizar_nome_para_comparacao(
            nome_original
        )

        padroes_encontrados = [
            padrao
            for padrao in padroes_normalizados
            if (
                nome_normalizado == padrao
                or nome_normalizado.startswith(padrao + "_")
                or nome_normalizado.endswith("_" + padrao)
                or ("_" + padrao + "_") in ("_" + nome_normalizado + "_")
            )
        ]

        if padroes_encontrados:

            campos_localizados.append({
                "campo": nome_original,
                "tipo": campo.typeName(),
                "padroes": sorted(set(padroes_encontrados))
            })

    return campos_localizados


# =============================================================================
# 6. DIAGNÓSTICO DE GEOMETRIAS
# =============================================================================

def diagnosticar_geometrias(camada):
    """
    Analisa as geometrias de uma camada vetorial espacial.

    Verifica:
        - geometrias nulas ou vazias;
        - geometrias inválidas;
        - geometrias duplicadas exatas.

    Observação:
        A duplicidade é calculada pelo hash WKB da geometria.
        Isso identifica cópias binariamente iguais, mas não todas as
        equivalências topológicas possíveis.
    """

    resultado = {
        "total": camada.featureCount(),
        "vazias": 0,
        "invalidas": 0,
        "duplicadas": 0,
        "ids_vazias": [],
        "ids_invalidas": [],
        "grupos_duplicados": []
    }

    hashes_geometrias = {}

    for feicao in camada.getFeatures():

        geometria = feicao.geometry()

        # -----------------------------------------------------------------
        # GEOMETRIA VAZIA OU AUSENTE
        # -----------------------------------------------------------------

        if (
            geometria is None
            or geometria.isNull()
            or geometria.isEmpty()
        ):

            resultado["vazias"] += 1
            resultado["ids_vazias"].append(
                feicao.id()
            )

            continue

        # -----------------------------------------------------------------
        # GEOMETRIA INVÁLIDA
        # -----------------------------------------------------------------

        try:

            if not geometria.isGeosValid():

                resultado["invalidas"] += 1
                resultado["ids_invalidas"].append(
                    feicao.id()
                )

        except Exception:

            # Alguns tipos especiais podem não ser verificáveis pelo GEOS.
            pass

        # -----------------------------------------------------------------
        # DUPLICIDADE EXATA
        # -----------------------------------------------------------------

        try:

            wkb = bytes(
                geometria.asWkb()
            )

            hash_geometria = hashlib.sha256(
                wkb
            ).hexdigest()

            if hash_geometria not in hashes_geometrias:

                hashes_geometrias[
                    hash_geometria
                ] = []

            hashes_geometrias[
                hash_geometria
            ].append(
                feicao.id()
            )

        except Exception:

            pass

    # Registra cada ocorrência além da primeira como duplicada.

    for ids in hashes_geometrias.values():

        if len(ids) > 1:

            resultado["duplicadas"] += (
                len(ids) - 1
            )

            resultado["grupos_duplicados"].append(
                ids
            )

    return resultado


# =============================================================================
# 7. OUTRAS DEPENDÊNCIAS DA CAMADA
# =============================================================================

def contar_joins(camada):
    """
    Conta os joins associados à camada.
    """

    try:

        return len(
            camada.vectorJoins()
        )

    except Exception:

        return 0


def obter_filtro_ativo(camada):
    """
    Obtém a expressão de subconjunto ou filtro do provedor.
    """

    try:

        filtro = camada.subsetString()

        if filtro:
            return filtro

    except Exception:

        pass

    return ""


def descrever_geometria(camada):
    """
    Retorna uma descrição legível do tipo geométrico.
    """

    if camada.type() != QgsMapLayerType.VectorLayer:
        return "Não aplicável"

    if not camada.isSpatial():
        return "Sem geometria"

    try:

        return QgsWkbTypes.displayString(
            camada.wkbType()
        )

    except Exception:

        return "Geometria não identificada"


# =============================================================================
# 8. CLASSIFICAÇÃO DE STATUS
# =============================================================================

def calcular_status_diagnostico(diagnostico):
    """
    Define o status geral da camada.

    Status:
        OK
        AVISO
        BLOQUEIO
    """

    bloqueios = []
    avisos = []

    # ---------------------------------------------------------------------
    # BLOQUEIOS
    # ---------------------------------------------------------------------

    if not diagnostico["camada_valida"]:

        bloqueios.append(
            "Camada inválida"
        )

    if not diagnostico["crs_valido"] and diagnostico["espacial"]:

        bloqueios.append(
            "CRS ausente ou inválido"
        )

    if diagnostico["tipo_fonte"] == "DESCONHECIDA":

        bloqueios.append(
            "Fonte não identificada"
        )

    # ---------------------------------------------------------------------
    # AVISOS
    # ---------------------------------------------------------------------

    if diagnostico["tipo_fonte"] == "TEMPORARIA":

        avisos.append(
            "Camada temporária"
        )

    if diagnostico["tipo_fonte"] == "REMOTA":

        avisos.append(
            "Fonte remota"
        )

    if diagnostico["geometrias_vazias"] > 0:

        avisos.append(
            "Geometrias vazias"
        )

    if diagnostico["geometrias_invalidas"] > 0:

        avisos.append(
            "Geometrias inválidas"
        )

    if diagnostico["geometrias_duplicadas"] > 0:

        avisos.append(
            "Geometrias duplicadas"
        )

    if diagnostico["campos_sensiveis"]:

        avisos.append(
            "Campos para revisão"
        )

    if diagnostico["joins"] > 0:

        avisos.append(
            "Joins dependentes"
        )

    if diagnostico["filtro_ativo"]:

        avisos.append(
            "Filtro ativo"
        )

    if diagnostico["em_edicao"]:

        avisos.append(
            "Alterações não confirmadas"
        )

    if bloqueios:

        return {
            "status": "BLOQUEIO",
            "bloqueios": bloqueios,
            "avisos": avisos
        }

    if avisos:

        return {
            "status": "AVISO",
            "bloqueios": [],
            "avisos": avisos
        }

    return {
        "status": "OK",
        "bloqueios": [],
        "avisos": []
    }


def recomendar_acao(diagnostico):
    """
    Define a ação recomendada para o empacotamento.
    """

    if diagnostico["status"] == "BLOQUEIO":

        return (
            "Corrigir os bloqueios antes do empacotamento."
        )

    if diagnostico["tipo"] in ["Vetor", "Tabela"]:

        if diagnostico["tipo_fonte"] == "REMOTA":

            return (
                "Materializar no GeoPackage e remover a URI remota "
                "do projeto de entrega."
            )

        if diagnostico["tipo_fonte"] == "TEMPORARIA":

            return (
                "Exportar obrigatoriamente para o GeoPackage "
                "antes de fechar o projeto."
            )

        if diagnostico["joins"] > 0:

            return (
                "Materializar os atributos dos joins na cópia de entrega."
            )

        return (
            "Converter para o GeoPackage de entrega."
        )

    if diagnostico["tipo"] == "Raster":

        if diagnostico["tipo_fonte"] == "REMOTA":

            return (
                "Revisar licença e disponibilidade para materialização."
            )

        return (
            "Copiar o raster e seus arquivos auxiliares para dados/rasters."
        )

    return (
        "Revisar manualmente antes da inclusão."
    )


# =============================================================================
# 9. DIAGNÓSTICO COMPLETO DE UMA CAMADA
# =============================================================================

def diagnosticar_camada(camada):
    """
    Executa o diagnóstico completo de uma camada.
    """

    tipo = classificar_tipo_camada(
        camada
    )

    fonte = classificar_fonte(
        camada
    )

    espacial = False

    if camada.type() == QgsMapLayerType.VectorLayer:

        espacial = camada.isSpatial()

    elif camada.type() == QgsMapLayerType.RasterLayer:

        espacial = True

    crs_authid = ""

    try:

        crs_authid = camada.crs().authid()

    except Exception:

        crs_authid = ""

    crs_valido = False

    try:

        crs_valido = camada.crs().isValid()

    except Exception:

        crs_valido = False

    diagnostico = {
        "id": camada.id(),
        "nome": camada.name(),
        "tipo": tipo,
        "provedor": camada.providerType(),
        "fonte": camada.source(),
        "tipo_fonte": fonte["tipo"],
        "fonte_persistente": fonte["persistente"],
        "observacao_fonte": fonte["observacao"],
        "camada_valida": camada.isValid(),
        "espacial": espacial,
        "crs": crs_authid or "Não identificado",
        "crs_valido": crs_valido,
        "geometria": descrever_geometria(camada),
        "feicoes": None,
        "geometrias_vazias": 0,
        "geometrias_invalidas": 0,
        "geometrias_duplicadas": 0,
        "grupos_duplicados": [],
        "campos": 0,
        "campos_sensiveis": [],
        "joins": 0,
        "filtro_ativo": "",
        "em_edicao": False,
        "status": "",
        "bloqueios": [],
        "avisos": [],
        "acao_recomendada": ""
    }

    # ---------------------------------------------------------------------
    # CAMADAS VETORIAIS E TABELAS
    # ---------------------------------------------------------------------

    if camada.type() == QgsMapLayerType.VectorLayer:

        diagnostico["feicoes"] = camada.featureCount()
        diagnostico["campos"] = len(camada.fields())

        diagnostico["campos_sensiveis"] = (
            localizar_campos_potencialmente_sensiveis(
                camada
            )
        )

        diagnostico["joins"] = contar_joins(
            camada
        )

        diagnostico["filtro_ativo"] = obter_filtro_ativo(
            camada
        )

        diagnostico["em_edicao"] = camada.isEditable()

        if camada.isSpatial():

            resultado_geometrias = diagnosticar_geometrias(
                camada
            )

            diagnostico["geometrias_vazias"] = (
                resultado_geometrias["vazias"]
            )

            diagnostico["geometrias_invalidas"] = (
                resultado_geometrias["invalidas"]
            )

            diagnostico["geometrias_duplicadas"] = (
                resultado_geometrias["duplicadas"]
            )

            diagnostico["grupos_duplicados"] = (
                resultado_geometrias["grupos_duplicados"]
            )

    # ---------------------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------------------

    avaliacao = calcular_status_diagnostico(
        diagnostico
    )

    diagnostico["status"] = avaliacao["status"]
    diagnostico["bloqueios"] = avaliacao["bloqueios"]
    diagnostico["avisos"] = avaliacao["avisos"]

    diagnostico["acao_recomendada"] = recomendar_acao(
        diagnostico
    )

    return diagnostico


# =============================================================================
# 10. APRESENTAÇÃO DO RESULTADO
# =============================================================================

def imprimir_diagnostico(diagnostico, numero):
    """
    Imprime o diagnóstico de uma camada no Console Python.
    """

    print("")
    print("-" * 78)

    print(
        f"{numero}. {diagnostico['nome']}"
    )

    print("-" * 78)

    print(
        f"Status: {diagnostico['status']}"
    )

    print(
        f"Tipo: {diagnostico['tipo']}"
    )

    print(
        f"Geometria: {diagnostico['geometria']}"
    )

    print(
        f"Provedor: {diagnostico['provedor']}"
    )

    print(
        f"Tipo da fonte: {diagnostico['tipo_fonte']}"
    )

    print(
        f"CRS: {diagnostico['crs']}"
    )

    print(
        f"CRS válido: {diagnostico['crs_valido']}"
    )

    print(
        f"Fonte: {abreviar_texto(diagnostico['fonte'])}"
    )

    print(
        f"Observação da fonte: "
        f"{diagnostico['observacao_fonte']}"
    )

    if diagnostico["feicoes"] is not None:

        print(
            f"Feições: {diagnostico['feicoes']}"
        )

        print(
            f"Campos: {diagnostico['campos']}"
        )

        print(
            f"Geometrias vazias: "
            f"{diagnostico['geometrias_vazias']}"
        )

        print(
            f"Geometrias inválidas: "
            f"{diagnostico['geometrias_invalidas']}"
        )

        print(
            f"Geometrias duplicadas: "
            f"{diagnostico['geometrias_duplicadas']}"
        )

        print(
            f"Joins: {diagnostico['joins']}"
        )

        print(
            f"Filtro ativo: "
            f"{bool(diagnostico['filtro_ativo'])}"
        )

        print(
            f"Camada em edição: "
            f"{diagnostico['em_edicao']}"
        )

    if diagnostico["campos_sensiveis"]:

        print("Campos para revisão:")

        for campo in diagnostico["campos_sensiveis"]:

            print(
                f"  - {campo['campo']} "
                f"({campo['tipo']})"
            )

    else:

        print(
            "Campos para revisão: nenhum localizado pelo nome"
        )

    if diagnostico["bloqueios"]:

        print("Bloqueios:")

        for bloqueio in diagnostico["bloqueios"]:

            print(
                f"  - {bloqueio}"
            )

    if diagnostico["avisos"]:

        print("Avisos:")

        for aviso in diagnostico["avisos"]:

            print(
                f"  - {aviso}"
            )

    print(
        f"Ação recomendada: "
        f"{diagnostico['acao_recomendada']}"
    )


# =============================================================================
# 11. EXECUÇÃO
# =============================================================================

try:

    print("")
    print("=" * 78)
    print("EMPACOTADOR DE DADOS PARA ENTREGA EXTERNA")
    print("ETAPA 02 - DIAGNÓSTICO TÉCNICO DAS CAMADAS")
    print("=" * 78)

    # -------------------------------------------------------------------------
    # 11.1. OBTER CAMADAS SELECIONADAS
    # -------------------------------------------------------------------------

    camadas_selecionadas = (
        iface.layerTreeView().selectedLayers()
    )

    if not camadas_selecionadas:

        raise Exception(
            "Nenhuma camada foi selecionada.\n\n"
            "Selecione no painel Camadas os dados que devem "
            "compor a entrega e execute novamente."
        )

    inicio = time.time()

    diagnosticos = []

    # -------------------------------------------------------------------------
    # 11.2. DIAGNOSTICAR AS CAMADAS
    # -------------------------------------------------------------------------

    for numero, camada in enumerate(
        camadas_selecionadas,
        start=1
    ):

        print("")
        print(
            f"Analisando camada {numero} de "
            f"{len(camadas_selecionadas)}: {camada.name()}"
        )

        diagnostico = diagnosticar_camada(
            camada
        )

        diagnosticos.append(
            diagnostico
        )

        imprimir_diagnostico(
            diagnostico,
            numero
        )

    duracao = time.time() - inicio

    # -------------------------------------------------------------------------
    # 11.3. CONSOLIDAR RESULTADOS
    # -------------------------------------------------------------------------

    contagem_status = Counter(
        diagnostico["status"]
        for diagnostico in diagnosticos
    )

    total_ok = contagem_status.get(
        "OK",
        0
    )

    total_aviso = contagem_status.get(
        "AVISO",
        0
    )

    total_bloqueio = contagem_status.get(
        "BLOQUEIO",
        0
    )

    total_vazias = sum(
        diagnostico["geometrias_vazias"]
        for diagnostico in diagnosticos
    )

    total_invalidas = sum(
        diagnostico["geometrias_invalidas"]
        for diagnostico in diagnosticos
    )

    total_duplicadas = sum(
        diagnostico["geometrias_duplicadas"]
        for diagnostico in diagnosticos
    )

    camadas_com_campos_sensiveis = [
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico["campos_sensiveis"]
    ]

    camadas_temporarias = [
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico["tipo_fonte"] == "TEMPORARIA"
    ]

    camadas_remotas = [
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico["tipo_fonte"] == "REMOTA"
    ]

    camadas_com_joins = [
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico["joins"] > 0
    ]

    camadas_em_edicao = [
        diagnostico
        for diagnostico in diagnosticos
        if diagnostico["em_edicao"]
    ]

    # -------------------------------------------------------------------------
    # 11.4. RESUMO NO CONSOLE
    # -------------------------------------------------------------------------

    print("")
    print("=" * 78)
    print("RESUMO DO DIAGNÓSTICO")
    print("=" * 78)

    print(
        f"Camadas analisadas: {len(diagnosticos)}"
    )

    print(
        f"Camadas sem ocorrências: {total_ok}"
    )

    print(
        f"Camadas com avisos: {total_aviso}"
    )

    print(
        f"Camadas com bloqueios: {total_bloqueio}"
    )

    print(
        f"Geometrias vazias: {total_vazias}"
    )

    print(
        f"Geometrias inválidas: {total_invalidas}"
    )

    print(
        f"Geometrias duplicadas: {total_duplicadas}"
    )

    print(
        "Camadas com campos para revisão: "
        f"{len(camadas_com_campos_sensiveis)}"
    )

    print(
        f"Camadas temporárias: {len(camadas_temporarias)}"
    )

    print(
        f"Camadas remotas: {len(camadas_remotas)}"
    )

    print(
        f"Camadas com joins: {len(camadas_com_joins)}"
    )

    print(
        f"Camadas em edição: {len(camadas_em_edicao)}"
    )

    print(
        f"Duração do diagnóstico: {duracao:.2f} segundo(s)"
    )

    print("=" * 78)

    # -------------------------------------------------------------------------
    # 11.5. LISTA RESUMIDA PARA O POPUP
    # -------------------------------------------------------------------------

    linhas_atencao = []

    for diagnostico in diagnosticos:

        if diagnostico["status"] != "OK":

            ocorrencias = (
                diagnostico["bloqueios"]
                + diagnostico["avisos"]
            )

            linhas_atencao.append(
                f"• {diagnostico['nome']}: "
                + ", ".join(ocorrencias)
            )

    if linhas_atencao:

        texto_atencao = "\n".join(
            linhas_atencao[:12]
        )

        if len(linhas_atencao) > 12:

            texto_atencao += (
                "\n"
                f"• ... e mais "
                f"{len(linhas_atencao) - 12} camada(s)."
            )

    else:

        texto_atencao = (
            "Nenhuma ocorrência foi localizada."
        )

    # -------------------------------------------------------------------------
    # 11.6. DEFINIR PRONTIDÃO
    # -------------------------------------------------------------------------

    if total_bloqueio > 0:

        situacao_pacote = (
            "NÃO APTO PARA EMPACOTAMENTO"
        )

        orientacao = (
            "Corrija as ocorrências classificadas como bloqueio "
            "antes de iniciar a exportação."
        )

        nivel_log = Qgis.Critical

    elif total_aviso > 0:

        situacao_pacote = (
            "APTO COM REVISÕES"
        )

        orientacao = (
            "O empacotamento poderá continuar, mas os avisos "
            "devem ser revisados antes da entrega externa."
        )

        nivel_log = Qgis.Warning

    else:

        situacao_pacote = (
            "APTO PARA EMPACOTAMENTO"
        )

        orientacao = (
            "As camadas podem seguir para a etapa de conversão."
        )

        nivel_log = Qgis.Success

    # -------------------------------------------------------------------------
    # 11.7. REGISTRAR NO LOG DO QGIS
    # -------------------------------------------------------------------------

    mensagem_log = (
        f"Diagnóstico concluído; "
        f"camadas: {len(diagnosticos)}; "
        f"OK: {total_ok}; "
        f"avisos: {total_aviso}; "
        f"bloqueios: {total_bloqueio}; "
        f"geometrias vazias: {total_vazias}; "
        f"geometrias inválidas: {total_invalidas}; "
        f"geometrias duplicadas: {total_duplicadas}; "
        f"fontes temporárias: {len(camadas_temporarias)}; "
        f"fontes remotas: {len(camadas_remotas)}; "
        f"campos para revisão: "
        f"{len(camadas_com_campos_sensiveis)}."
    )

    QgsMessageLog.logMessage(
        mensagem_log,
        "Empacotador de Entrega Externa",
        nivel_log
    )

    # -------------------------------------------------------------------------
    # 11.8. MOSTRAR POPUP
    # -------------------------------------------------------------------------

    mensagem_final = (
        "Diagnóstico técnico concluído.\n\n"
        f"Situação:\n{situacao_pacote}\n\n"
        f"Camadas analisadas: {len(diagnosticos)}\n"
        f"Sem ocorrências: {total_ok}\n"
        f"Com avisos: {total_aviso}\n"
        f"Com bloqueios: {total_bloqueio}\n\n"
        f"Geometrias vazias: {total_vazias}\n"
        f"Geometrias inválidas: {total_invalidas}\n"
        f"Geometrias duplicadas: {total_duplicadas}\n\n"
        "Dependências e segurança:\n"
        f"Camadas temporárias: {len(camadas_temporarias)}\n"
        f"Camadas remotas: {len(camadas_remotas)}\n"
        f"Camadas com joins: {len(camadas_com_joins)}\n"
        f"Camadas em edição: {len(camadas_em_edicao)}\n"
        "Camadas com campos para revisão: "
        f"{len(camadas_com_campos_sensiveis)}\n\n"
        "Ocorrências principais:\n"
        f"{texto_atencao}\n\n"
        f"{orientacao}\n\n"
        "Consulte o Console Python para o diagnóstico detalhado.\n"
        "Nenhum arquivo foi criado ou modificado."
    )

    if total_bloqueio > 0:

        QMessageBox.critical(
            iface.mainWindow(),
            "Diagnóstico da entrega",
            mensagem_final
        )

    elif total_aviso > 0:

        QMessageBox.warning(
            iface.mainWindow(),
            "Diagnóstico da entrega",
            mensagem_final
        )

    else:

        QMessageBox.information(
            iface.mainWindow(),
            "Diagnóstico da entrega",
            mensagem_final
        )


# =============================================================================
# 12. TRATAMENTO DE ERROS
# =============================================================================

except Exception as erro:

    print("")
    print("=" * 78)
    print("ERRO NO DIAGNÓSTICO DO EMPACOTADOR")
    print("=" * 78)
    print(str(erro))
    print("=" * 78)

    QgsMessageLog.logMessage(
        str(erro),
        "Empacotador de Entrega Externa",
        Qgis.Critical
    )

    QMessageBox.critical(
        iface.mainWindow(),
        "Erro no diagnóstico",
        (
            "Não foi possível concluir o diagnóstico "
            "das camadas selecionadas.\n\n"
            f"Detalhes:\n{str(erro)}"
        )
    )