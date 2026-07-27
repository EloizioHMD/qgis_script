# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Gerador de Máscara de Área de Interesse
Descrição:
    Script de automação para QGIS que realiza a união (merge) de camadas
    vetoriais selecionadas pela interface, reprojeta o resultado para um
    sistema de coordenadas métrico (SIRGAS 2000 / UTM), aplica um buffer
    de 5.000 metros e dissolve a geometria final.
    
    O objetivo é gerar uma camada vetorial de máscara única para ser utilizada
    no recorte/limitação de bases de dados espaciais maiores.

Autor: Eloízio Dantas
Data de Criação: 2026-07-27
Versão: 1.0.0
Requisitos / Compatibilidade:
    - QGIS Versão: 3.34 LTR (ou superior)
    - Python: 3.x
===============================================================================
"""

import processing
from qgis.core import QgsProject, QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
from qgis.utils import iface

# -------------------------------------------------------------------------
# 1. SELEÇÃO DINÂMICA DAS CAMADAS DA TELA
# -------------------------------------------------------------------------
# Pega todas as camadas atualmente selecionadas pelo usuário no painel "Camadas"
camadas_selecionadas = iface.layerTreeView().selectedLayers()

# Filtra para garantir que apenas camadas VETORIAIS foram selecionadas
camadas_entrada = [layer for layer in camadas_selecionadas if layer.type() == layer.VectorLayer]

# Validação: verifica se o usuário selecionou pelo menos 2 camadas
if len(camadas_entrada) < 2:
    QMessageBox.warning(
        None, 
        "Atenção", 
        "Por favor, selecione pelo menos DUAS camadas vetoriais no painel de Camadas antes de executar o script."
    )
else:
    # -------------------------------------------------------------------------
    # 2. CAIXA PARA SALVAR O ARQUIVO RESULTANTE
    # -------------------------------------------------------------------------
    caminho_mascara_final, _ = QFileDialog.getSaveFileName(
        None,
        "Salvar Máscara Resultante",
        "",
        "GeoPackage (*.gpkg);;Shapefile (*.shp)"
    )

    if caminho_mascara_final:
        
        # -------------------------------------------------------------------------
        # 3. UNIR AS CAMADAS (MERGE)
        # -------------------------------------------------------------------------
        print("Unindo as camadas selecionadas...")
        res_merge = processing.run("native:mergevectorlayers", {
            'LAYERS': camadas_entrada,
            'CRS': None, # Mantém o CRS original da primeira camada
            'OUTPUT': 'memory:'
        })

        # -------------------------------------------------------------------------
        # 4. REPROJETAR PARA UM SISTEMA MÉTRICO (SIRGAS 2000 UTM)
        # -------------------------------------------------------------------------
        # Defina aqui o EPSG métrico adequado para sua área de estudo.
        # Exemplo: EPSG:31985 -> SIRGAS 2000 / UTM zone 25S
        # Exemplo: EPSG:31984 -> SIRGAS 2000 / UTM zone 24S
        # Exemplo: EPSG:31983 -> SIRGAS 2000 / UTM zone 23S
        epsg_metrico = "EPSG:31985" 

        print(f"Reprojetando para o sistema métrico ({epsg_metrico})...")
        res_reproj = processing.run("native:reprojectlayer", {
            'INPUT': res_merge['OUTPUT'],
            'TARGET_CRS': QgsCoordinateReferenceSystem(epsg_metrico),
            'OUTPUT': 'memory:'
        })

        # -------------------------------------------------------------------------
        # 5. GERAR BUFFER DE 5.000 METROS
        # -------------------------------------------------------------------------
        print("Gerando buffer de 5.000m...")
        res_buffer = processing.run("native:buffer", {
            'INPUT': res_reproj['OUTPUT'], # Usa a camada já em UTM/Metros
            'DISTANCE': 5000,              # Em metros.
            'SEGMENTS': 10,
            'END_CAP_STYLE': 0,
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'DISSOLVE': False,
            'OUTPUT': 'memory:'
        })

        # -------------------------------------------------------------------------
        # 6. DISSOLVER E SALVAR NO DISCO
        # -------------------------------------------------------------------------
        print("Dissolvendo geometrias e salvando arquivo...")
        processing.run("native:dissolve", {
            'INPUT': res_buffer['OUTPUT'],
            'FIELD': [],
            'OUTPUT': caminho_mascara_final
        })

        # Carrega o resultado de volta na tela do QGIS
        iface.addVectorLayer(caminho_mascara_final, "Mascara_Area_Interesse", "ogr")
        print("Processo concluído com sucesso!")

    else:
        print("Operação cancelada pelo usuário na caixa de diálogo de salvamento.")