# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Seletor Automático de UTM

Descrição:
    Script de automação para QGIS que identifica automaticamente o fuso UTM
    adequado para a camada vetorial ativa.

    O script utiliza o centro da extensão espacial da camada, transforma esse
    ponto para SIRGAS 2000 geográfico, EPSG:4674, calcula o fuso UTM com base
    na longitude e identifica o código EPSG correspondente ao sistema
    SIRGAS 2000 / UTM Sul.

    Ao final, o usuário pode definir o CRS identificado como o CRS do projeto.

Importante:
    - O script não reprojeta a camada.
    - O script não altera o CRS original da camada.
    - O script apenas identifica e, opcionalmente, configura o CRS do projeto.
    - A camada precisa possuir um CRS corretamente definido.

Autor: Eloízio Dantas
Data de Criação: 2026-08-27
Versão: 1.0.0

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x
    - Área de aplicação: território brasileiro
    - Datum de referência: SIRGAS 2000
===============================================================================
"""


# -------------------------------------------------------------------------
# 1. IMPORTAÇÕES
# -------------------------------------------------------------------------

import math

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMapLayerType,
    QgsMessageLog,
    QgsProject,
    Qgis
)

from qgis.PyQt.QtWidgets import QMessageBox
from qgis.utils import iface


# -------------------------------------------------------------------------
# 2. FUNÇÃO PARA CALCULAR O FUSO UTM
# -------------------------------------------------------------------------

def calcular_fuso_utm(longitude):
    """
    Calcula o número do fuso UTM a partir da longitude.

    Cada fuso UTM possui 6 graus de largura.

    Parâmetro:
        longitude: longitude em graus decimais.

    Retorno:
        Número inteiro correspondente ao fuso UTM.
    """

    fuso = math.floor((longitude + 180) / 6) + 1

    # Garante que o resultado permaneça entre os fusos 1 e 60
    fuso = max(1, min(fuso, 60))

    return fuso


# -------------------------------------------------------------------------
# 3. INÍCIO DO PROCESSAMENTO
# -------------------------------------------------------------------------

try:

    print("")
    print("=" * 70)
    print("SELETOR AUTOMÁTICO DE UTM")
    print("=" * 70)

    # ---------------------------------------------------------------------
    # 3.1. OBTER A CAMADA ATIVA
    # ---------------------------------------------------------------------

    camada_ativa = iface.activeLayer()

    # ---------------------------------------------------------------------
    # 3.2. VALIDAR SE EXISTE UMA CAMADA ATIVA
    # ---------------------------------------------------------------------

    if camada_ativa is None:
        raise Exception(
            "Nenhuma camada está ativa.\n\n"
            "Clique em uma camada vetorial no painel de Camadas "
            "e execute o script novamente."
        )

    # ---------------------------------------------------------------------
    # 3.3. VALIDAR SE A CAMADA É VETORIAL
    # ---------------------------------------------------------------------

    if camada_ativa.type() != QgsMapLayerType.VectorLayer:
        raise Exception(
            f"A camada ativa '{camada_ativa.name()}' não é vetorial.\n\n"
            "Selecione uma camada vetorial de pontos, linhas ou polígonos."
        )

    # ---------------------------------------------------------------------
    # 3.4. VALIDAR O CRS DA CAMADA
    # ---------------------------------------------------------------------

    crs_origem = camada_ativa.crs()

    if not crs_origem.isValid():
        raise Exception(
            f"A camada '{camada_ativa.name()}' não possui um CRS válido.\n\n"
            "Defina corretamente o CRS da camada antes de executar "
            "o seletor automático de UTM."
        )

    # ---------------------------------------------------------------------
    # 3.5. VALIDAR SE A CAMADA POSSUI FEIÇÕES
    # ---------------------------------------------------------------------

    if camada_ativa.featureCount() == 0:
        raise Exception(
            f"A camada '{camada_ativa.name()}' não possui feições."
        )

    # ---------------------------------------------------------------------
    # 3.6. OBTER A EXTENSÃO DA CAMADA
    # ---------------------------------------------------------------------

    extensao = camada_ativa.extent()

    if extensao.isEmpty():
        raise Exception(
            f"A camada '{camada_ativa.name()}' possui uma extensão vazia."
        )

    print(f"Camada analisada: {camada_ativa.name()}")
    print(f"CRS da camada: {crs_origem.authid()}")

    # ---------------------------------------------------------------------
    # 4. OBTER O CENTRO DA EXTENSÃO
    # ---------------------------------------------------------------------

    ponto_central = extensao.center()

    print("")
    print("Centro da extensão no CRS original:")
    print(f"X: {ponto_central.x():.3f}")
    print(f"Y: {ponto_central.y():.3f}")

    # ---------------------------------------------------------------------
    # 5. DEFINIR O CRS GEOGRÁFICO SIRGAS 2000
    # ---------------------------------------------------------------------

    crs_sirgas_geografico = QgsCoordinateReferenceSystem("EPSG:4674")

    if not crs_sirgas_geografico.isValid():
        raise Exception(
            "Não foi possível carregar o CRS SIRGAS 2000, EPSG:4674."
        )

    # ---------------------------------------------------------------------
    # 6. TRANSFORMAR O CENTRO PARA LONGITUDE E LATITUDE
    # ---------------------------------------------------------------------

    transformacao = QgsCoordinateTransform(
        crs_origem,
        crs_sirgas_geografico,
        QgsProject.instance().transformContext()
    )

    ponto_geografico = transformacao.transform(ponto_central)

    longitude = ponto_geografico.x()
    latitude = ponto_geografico.y()

    # ---------------------------------------------------------------------
    # 7. VALIDAR AS COORDENADAS OBTIDAS
    # ---------------------------------------------------------------------

    if longitude < -180 or longitude > 180:
        raise Exception(
            f"A longitude calculada é inválida: {longitude:.6f}°."
        )

    if latitude < -90 or latitude > 90:
        raise Exception(
            f"A latitude calculada é inválida: {latitude:.6f}°."
        )

    print("")
    print("Centro da extensão em SIRGAS 2000 geográfico:")
    print(f"Longitude: {longitude:.6f}°")
    print(f"Latitude: {latitude:.6f}°")

    # ---------------------------------------------------------------------
    # 8. VERIFICAR O HEMISFÉRIO
    # ---------------------------------------------------------------------

    if latitude >= 0:
        raise Exception(
            "A camada está localizada no hemisfério norte.\n\n"
            "Esta versão do script foi configurada especificamente para "
            "os códigos SIRGAS 2000 / UTM Sul utilizados no Brasil."
        )

    hemisferio = "S"

    # ---------------------------------------------------------------------
    # 9. CALCULAR O FUSO UTM
    # ---------------------------------------------------------------------

    fuso_utm = calcular_fuso_utm(longitude)

    print("")
    print(f"Fuso UTM calculado: {fuso_utm}{hemisferio}")

    # ---------------------------------------------------------------------
    # 10. VALIDAR SE O FUSO ESTÁ NO INTERVALO DO BRASIL
    # ---------------------------------------------------------------------
    #
    # O território brasileiro utiliza principalmente os fusos:
    #
    # 17S, 18S, 19S, 20S, 21S, 22S, 23S, 24S e 25S.
    # ---------------------------------------------------------------------

    if fuso_utm < 17 or fuso_utm > 25:
        raise Exception(
            f"O fuso calculado foi {fuso_utm}{hemisferio}.\n\n"
            "Esse fuso está fora do intervalo esperado para o território "
            "brasileiro, que vai do fuso 17S ao fuso 25S.\n\n"
            "Verifique se o CRS de origem da camada está corretamente definido."
        )

    # ---------------------------------------------------------------------
    # 11. IDENTIFICAR O EPSG SIRGAS 2000 / UTM SUL
    # ---------------------------------------------------------------------
    #
    # Correspondência:
    #
    # Fuso 17S = EPSG:31977
    # Fuso 18S = EPSG:31978
    # Fuso 19S = EPSG:31979
    # Fuso 20S = EPSG:31980
    # Fuso 21S = EPSG:31981
    # Fuso 22S = EPSG:31982
    # Fuso 23S = EPSG:31983
    # Fuso 24S = EPSG:31984
    # Fuso 25S = EPSG:31985
    #
    # Relação usada:
    #
    # Código EPSG = 31960 + número do fuso
    # ---------------------------------------------------------------------

    codigo_epsg = 31960 + fuso_utm
    identificacao_epsg = f"EPSG:{codigo_epsg}"

    crs_utm = QgsCoordinateReferenceSystem(identificacao_epsg)

    # ---------------------------------------------------------------------
    # 12. VALIDAR O CRS CALCULADO
    # ---------------------------------------------------------------------

    if not crs_utm.isValid():
        raise Exception(
            f"O CRS calculado, {identificacao_epsg}, "
            "não foi reconhecido pelo QGIS."
        )

    # ---------------------------------------------------------------------
    # 13. MOSTRAR O RESULTADO NO CONSOLE
    # ---------------------------------------------------------------------

    print("")
    print("-" * 70)
    print("RESULTADO")
    print("-" * 70)
    print(f"Camada: {camada_ativa.name()}")
    print(f"CRS original: {crs_origem.authid()}")
    print(f"Longitude central: {longitude:.6f}°")
    print(f"Latitude central: {latitude:.6f}°")
    print(f"Fuso UTM: {fuso_utm}{hemisferio}")
    print(f"CRS recomendado: {identificacao_epsg}")
    print(f"Descrição: {crs_utm.description()}")
    print("-" * 70)

    # ---------------------------------------------------------------------
    # 14. PREPARAR A MENSAGEM PARA O USUÁRIO
    # ---------------------------------------------------------------------

    mensagem_resultado = (
        "Sistema UTM identificado com sucesso.\n\n"
        f"Camada analisada:\n"
        f"{camada_ativa.name()}\n\n"
        f"CRS original:\n"
        f"{crs_origem.authid()} - {crs_origem.description()}\n\n"
        f"Coordenada central:\n"
        f"Longitude: {longitude:.6f}°\n"
        f"Latitude: {latitude:.6f}°\n\n"
        f"Fuso UTM recomendado:\n"
        f"{fuso_utm}{hemisferio}\n\n"
        f"CRS recomendado:\n"
        f"{identificacao_epsg} - {crs_utm.description()}\n\n"
        "Deseja definir esse CRS como o CRS do projeto?\n\n"
        "A camada original não será alterada."
    )

    # ---------------------------------------------------------------------
    # 15. PERGUNTAR SE O CRS DEVE SER APLICADO AO PROJETO
    # ---------------------------------------------------------------------

    resposta = QMessageBox.question(
        None,
        "Seletor Automático de UTM",
        mensagem_resultado,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.Yes
    )

    # ---------------------------------------------------------------------
    # 16. CONFIGURAR O CRS DO PROJETO
    # ---------------------------------------------------------------------

    if resposta == QMessageBox.Yes:

        QgsProject.instance().setCrs(crs_utm)

        print("")
        print(
            f"O CRS do projeto foi definido como "
            f"{identificacao_epsg}."
        )

        QMessageBox.information(
            None,
            "CRS do projeto atualizado",
            (
                "O CRS do projeto foi atualizado com sucesso.\n\n"
                f"Fuso: {fuso_utm}{hemisferio}\n"
                f"CRS: {identificacao_epsg}\n"
                f"Descrição: {crs_utm.description()}\n\n"
                "A camada original não foi reprojetada ou modificada."
            )
        )

        mensagem_log = (
            f"CRS do projeto definido automaticamente como "
            f"{identificacao_epsg}; "
            f"fuso {fuso_utm}{hemisferio}; "
            f"camada de referência: {camada_ativa.name()}; "
            f"longitude central: {longitude:.6f}; "
            f"latitude central: {latitude:.6f}."
        )

        QgsMessageLog.logMessage(
            mensagem_log,
            "Seletor Automático de UTM",
            Qgis.Info
        )

    else:

        print("")
        print(
            "O CRS foi identificado, mas o CRS do projeto "
            "não foi alterado."
        )

        QMessageBox.information(
            None,
            "CRS não alterado",
            (
                "O CRS recomendado foi identificado, mas não foi "
                "aplicado ao projeto.\n\n"
                f"CRS recomendado: {identificacao_epsg}\n"
                f"Fuso: {fuso_utm}{hemisferio}"
            )
        )


# -------------------------------------------------------------------------
# 17. TRATAMENTO DE ERROS
# -------------------------------------------------------------------------

except Exception as erro:

    mensagem_erro = (
        "Não foi possível identificar automaticamente o CRS UTM.\n\n"
        f"Detalhes:\n{str(erro)}"
    )

    print("")
    print("=" * 70)
    print("ERRO NO SELETOR AUTOMÁTICO DE UTM")
    print("=" * 70)
    print(str(erro))
    print("=" * 70)

    QgsMessageLog.logMessage(
        str(erro),
        "Seletor Automático de UTM",
        Qgis.Critical
    )

    QMessageBox.critical(
        None,
        "Erro no Seletor Automático de UTM",
        mensagem_erro
    )
