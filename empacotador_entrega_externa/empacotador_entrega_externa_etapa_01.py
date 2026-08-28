# -*- coding: utf-8 -*-
"""
===============================================================================
Script: Empacotador de Dados para Entrega Externa
Etapa: 01 - Configuração e Validação Inicial

Descrição:
    Primeira etapa do desenvolvimento do Empacotador de Dados para Entrega
    Externa.

    O script:

    1. Obtém as camadas selecionadas no painel Camadas;
    2. Identifica o projeto QGIS atual;
    3. Abre uma janela de configuração do pacote;
    4. Permite definir o nome e a pasta de destino;
    5. Permite selecionar as opções iniciais do empacotamento;
    6. Verifica conflitos de nomenclatura e destino;
    7. Apresenta um resumo do plano de entrega.

    Nesta etapa, nenhum arquivo é criado, copiado ou modificado.

Autor: Eloízio Dantas
Data de Criação: 2026-08-27
Versão: 0.1.0

Requisitos / Compatibilidade:
    - QGIS: 3.34 LTR ou superior
    - Python: 3.x

Premissas e Limitações:
    - O usuário deve selecionar as camadas no painel Camadas.
    - Esta etapa não exporta dados.
    - Esta etapa não altera o projeto atual.
    - A seleção pode conter vetores, rasters ou tabelas.
===============================================================================
"""


# =============================================================================
# 1. IMPORTAÇÕES
# =============================================================================

import os
import re

from datetime import datetime

from qgis.core import (
    QgsMapLayerType,
    QgsProject,
    QgsVectorLayer,
    QgsRasterLayer
)

from qgis.PyQt.QtCore import Qt

from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout
)

from qgis.utils import iface


# =============================================================================
# 2. FUNÇÕES AUXILIARES
# =============================================================================

def normalizar_nome_pacote(nome):
    """
    Converte o nome informado em um nome seguro para pasta e arquivo.

    Exemplos:
        Projeto Mata Grande -> PROJETO_MATA_GRANDE
        Processo 19.591/2026 -> PROCESSO_19_591_2026
    """

    nome = nome.strip()

    # Remove acentos de forma simples para os caracteres mais comuns
    substituicoes = {
        "á": "a",
        "à": "a",
        "ã": "a",
        "â": "a",
        "ä": "a",
        "Á": "A",
        "À": "A",
        "Ã": "A",
        "Â": "A",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "É": "E",
        "Ê": "E",
        "í": "i",
        "Í": "I",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ö": "o",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "ú": "u",
        "ü": "u",
        "Ú": "U",
        "ç": "c",
        "Ç": "C"
    }

    for caractere, substituto in substituicoes.items():
        nome = nome.replace(
            caractere,
            substituto
        )

    # Substitui caracteres incompatíveis por sublinhado
    nome = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        nome
    )

    # Evita múltiplos sublinhados
    nome = re.sub(
        r"_+",
        "_",
        nome
    )

    nome = nome.strip(
        "_-"
    )

    if not nome:
        nome = "PROJETO_QGIS"

    return nome.upper()


def obter_nome_base_projeto():
    """
    Obtém um nome inicial baseado no arquivo do projeto atual.

    Se o projeto ainda não estiver salvo, utiliza PROJETO_QGIS.
    """

    projeto = QgsProject.instance()
    caminho_projeto = projeto.fileName()

    if caminho_projeto:

        nome_arquivo = os.path.basename(
            caminho_projeto
        )

        nome_sem_extensao = os.path.splitext(
            nome_arquivo
        )[0]

        return normalizar_nome_pacote(
            nome_sem_extensao
        )

    return "PROJETO_QGIS"


def classificar_camada(camada):
    """
    Classifica uma camada para apresentação no popup.
    """

    if camada.type() == QgsMapLayerType.VectorLayer:

        if camada.isSpatial():
            return "Vetor"

        return "Tabela"

    if camada.type() == QgsMapLayerType.RasterLayer:
        return "Raster"

    return "Outro"


def descrever_camada(camada):
    """
    Retorna uma descrição curta para exibição.
    """

    tipo = classificar_camada(
        camada
    )

    crs = camada.crs().authid()

    if not crs:
        crs = "CRS não identificado"

    if camada.type() == QgsMapLayerType.VectorLayer:

        quantidade = camada.featureCount()

        return (
            f"{camada.name()} | "
            f"{tipo} | "
            f"{crs} | "
            f"{quantidade} feição(ões)"
        )

    if camada.type() == QgsMapLayerType.RasterLayer:

        return (
            f"{camada.name()} | "
            f"{tipo} | "
            f"{crs}"
        )

    return (
        f"{camada.name()} | "
        f"{tipo}"
    )


def contar_tipos_camadas(camadas):
    """
    Conta vetores, rasters, tabelas e outros tipos.
    """

    contagens = {
        "Vetor": 0,
        "Raster": 0,
        "Tabela": 0,
        "Outro": 0
    }

    for camada in camadas:

        categoria = classificar_camada(
            camada
        )

        contagens[categoria] += 1

    return contagens


# =============================================================================
# 3. JANELA DE CONFIGURAÇÃO
# =============================================================================

class JanelaEntregaExterna(QDialog):
    """
    Janela inicial do Empacotador para Entrega Externa.
    """

    def __init__(
        self,
        camadas,
        parent=None
    ):

        super().__init__(parent)

        self.camadas = camadas

        self.configurar_janela()
        self.criar_interface()


    # -------------------------------------------------------------------------
    # 3.1. CONFIGURAÇÃO DA JANELA
    # -------------------------------------------------------------------------

    def configurar_janela(self):

        self.setWindowTitle(
            "Empacotador de Dados para Entrega Externa"
        )

        self.setMinimumWidth(670)
        self.setMinimumHeight(680)

        self.setWindowModality(
            Qt.ApplicationModal
        )


    # -------------------------------------------------------------------------
    # 3.2. CONSTRUÇÃO DA INTERFACE
    # -------------------------------------------------------------------------

    def criar_interface(self):

        layout_principal = QVBoxLayout()

        self.setLayout(
            layout_principal
        )

        # ---------------------------------------------------------------------
        # APRESENTAÇÃO
        # ---------------------------------------------------------------------

        projeto = QgsProject.instance()
        caminho_projeto = projeto.fileName()

        if caminho_projeto:
            projeto_apresentado = caminho_projeto
        else:
            projeto_apresentado = (
                "Projeto ainda não salvo"
            )

        apresentacao = QLabel(
            "<b>Modalidade:</b> Entrega externa<br>"
            f"<b>Projeto atual:</b> {projeto_apresentado}<br><br>"
            "As camadas abaixo foram selecionadas no painel Camadas."
        )

        apresentacao.setWordWrap(True)

        layout_principal.addWidget(
            apresentacao
        )

        # ---------------------------------------------------------------------
        # LISTA DE CAMADAS SELECIONADAS
        # ---------------------------------------------------------------------

        grupo_camadas = QGroupBox(
            "Camadas selecionadas para a entrega"
        )

        layout_camadas = QVBoxLayout()

        grupo_camadas.setLayout(
            layout_camadas
        )

        self.lista_camadas = QListWidget()

        for camada in self.camadas:

            item = QListWidgetItem(
                descrever_camada(camada)
            )

            item.setToolTip(
                camada.source()
            )

            self.lista_camadas.addItem(
                item
            )

        layout_camadas.addWidget(
            self.lista_camadas
        )

        contagens = contar_tipos_camadas(
            self.camadas
        )

        resumo_camadas = QLabel(
            f"<b>Total:</b> {len(self.camadas)} camada(s) | "
            f"Vetores: {contagens['Vetor']} | "
            f"Rasters: {contagens['Raster']} | "
            f"Tabelas: {contagens['Tabela']} | "
            f"Outros: {contagens['Outro']}"
        )

        resumo_camadas.setWordWrap(True)

        layout_camadas.addWidget(
            resumo_camadas
        )

        layout_principal.addWidget(
            grupo_camadas
        )

        # ---------------------------------------------------------------------
        # IDENTIFICAÇÃO DO PACOTE
        # ---------------------------------------------------------------------

        grupo_identificacao = QGroupBox(
            "Identificação da entrega"
        )

        layout_identificacao = QVBoxLayout()

        grupo_identificacao.setLayout(
            layout_identificacao
        )

        rotulo_nome = QLabel(
            "Nome do projeto ou pacote:"
        )

        self.campo_nome = QLineEdit()

        nome_inicial = obter_nome_base_projeto()

        self.campo_nome.setText(
            nome_inicial
        )

        self.campo_nome.setPlaceholderText(
            "Exemplo: MATA_GRANDE"
        )

        layout_identificacao.addWidget(
            rotulo_nome
        )

        layout_identificacao.addWidget(
            self.campo_nome
        )

        rotulo_destino = QLabel(
            "Pasta onde a entrega será criada:"
        )

        layout_destino = QHBoxLayout()

        self.campo_destino = QLineEdit()

        self.campo_destino.setReadOnly(
            True
        )

        self.campo_destino.setPlaceholderText(
            "Selecione a pasta de destino"
        )

        self.botao_destino = QPushButton(
            "Selecionar..."
        )

        self.botao_destino.clicked.connect(
            self.selecionar_pasta_destino
        )

        layout_destino.addWidget(
            self.campo_destino
        )

        layout_destino.addWidget(
            self.botao_destino
        )

        layout_identificacao.addWidget(
            rotulo_destino
        )

        layout_identificacao.addLayout(
            layout_destino
        )

        layout_principal.addWidget(
            grupo_identificacao
        )

        # ---------------------------------------------------------------------
        # OPÇÕES DO PACOTE
        # ---------------------------------------------------------------------

        grupo_opcoes = QGroupBox(
            "Conteúdo e segurança da entrega"
        )

        layout_opcoes = QVBoxLayout()

        grupo_opcoes.setLayout(
            layout_opcoes
        )

        self.check_converter_vetores = QCheckBox(
            "Converter camadas vetoriais para um único GeoPackage"
        )

        self.check_copiar_rasters = QCheckBox(
            "Copiar as camadas raster selecionadas"
        )

        self.check_copiar_estilos = QCheckBox(
            "Copiar estilos QML"
        )

        self.check_criar_qgz = QCheckBox(
            "Criar projeto QGZ na raiz da pasta"
        )

        self.check_caminhos_relativos = QCheckBox(
            "Usar caminhos relativos no projeto de entrega"
        )

        self.check_inventario = QCheckBox(
            "Gerar inventário das camadas em CSV"
        )

        self.check_manifesto = QCheckBox(
            "Gerar manifesto técnico em JSON"
        )

        self.check_hashes = QCheckBox(
            "Gerar hashes SHA-256 para verificação de integridade"
        )

        self.check_validar = QCheckBox(
            "Validar o projeto e as fontes após o empacotamento"
        )

        # Opções essenciais marcadas e bloqueadas
        self.check_converter_vetores.setChecked(True)
        self.check_criar_qgz.setChecked(True)
        self.check_caminhos_relativos.setChecked(True)
        self.check_inventario.setChecked(True)
        self.check_manifesto.setChecked(True)
        self.check_hashes.setChecked(True)
        self.check_validar.setChecked(True)

        self.check_converter_vetores.setEnabled(False)
        self.check_criar_qgz.setEnabled(False)
        self.check_caminhos_relativos.setEnabled(False)
        self.check_inventario.setEnabled(False)
        self.check_manifesto.setEnabled(False)
        self.check_validar.setEnabled(False)

        # Rasters e estilos permanecem configuráveis
        self.check_copiar_rasters.setChecked(True)
        self.check_copiar_estilos.setChecked(True)

        for componente in [
            self.check_converter_vetores,
            self.check_copiar_rasters,
            self.check_copiar_estilos,
            self.check_criar_qgz,
            self.check_caminhos_relativos,
            self.check_inventario,
            self.check_manifesto,
            self.check_hashes,
            self.check_validar
        ]:

            layout_opcoes.addWidget(
                componente
            )

        layout_principal.addWidget(
            grupo_opcoes
        )

        # ---------------------------------------------------------------------
        # AVISO DA ETAPA
        # ---------------------------------------------------------------------

        aviso = QLabel(
            "<i>Nesta primeira etapa, o script apenas valida e apresenta "
            "o plano de empacotamento. Nenhum arquivo será criado, copiado "
            "ou modificado.</i>"
        )

        aviso.setWordWrap(True)

        layout_principal.addWidget(
            aviso
        )

        # ---------------------------------------------------------------------
        # BOTÕES
        # ---------------------------------------------------------------------

        self.caixa_botoes = QDialogButtonBox(
            QDialogButtonBox.Ok |
            QDialogButtonBox.Cancel
        )

        botao_ok = self.caixa_botoes.button(
            QDialogButtonBox.Ok
        )

        botao_ok.setText(
            "Validar configuração"
        )

        self.caixa_botoes.accepted.connect(
            self.validar_e_aceitar
        )

        self.caixa_botoes.rejected.connect(
            self.reject
        )

        layout_principal.addWidget(
            self.caixa_botoes
        )


    # -------------------------------------------------------------------------
    # 3.3. SELEÇÃO DA PASTA
    # -------------------------------------------------------------------------

    def selecionar_pasta_destino(self):

        pasta = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta de destino da entrega",
            os.path.expanduser("~")
        )

        if pasta:

            self.campo_destino.setText(
                pasta
            )


    # -------------------------------------------------------------------------
    # 3.4. VALIDAÇÃO
    # -------------------------------------------------------------------------

    def validar_e_aceitar(self):

        nome_informado = self.campo_nome.text().strip()

        if not nome_informado:

            QMessageBox.warning(
                self,
                "Nome não informado",
                (
                    "Informe um nome para o projeto "
                    "ou pacote de entrega."
                )
            )

            return

        pasta_destino = self.campo_destino.text().strip()

        if not pasta_destino:

            QMessageBox.warning(
                self,
                "Destino não informado",
                "Selecione a pasta de destino da entrega."
            )

            return

        if not os.path.isdir(pasta_destino):

            QMessageBox.warning(
                self,
                "Destino inválido",
                (
                    "A pasta de destino selecionada "
                    "não existe ou não está acessível."
                )
            )

            return

        if not os.access(
            pasta_destino,
            os.W_OK
        ):

            QMessageBox.warning(
                self,
                "Destino sem permissão",
                (
                    "A pasta selecionada não permite gravação.\n\n"
                    "Escolha outra pasta ou verifique suas permissões."
                )
            )

            return

        nome_normalizado = normalizar_nome_pacote(
            nome_informado
        )

        data_execucao = datetime.now().strftime(
            "%Y%m%d"
        )

        nome_pasta = (
            f"ENTREGA_{nome_normalizado}_"
            f"{data_execucao}_v001"
        )

        caminho_pacote = os.path.join(
            pasta_destino,
            nome_pasta
        )

        if os.path.exists(caminho_pacote):

            QMessageBox.warning(
                self,
                "Pacote já existente",
                (
                    "Já existe uma pasta com o nome calculado:\n\n"
                    f"{caminho_pacote}\n\n"
                    "A ferramenta final utilizará versionamento "
                    "automático. Nesta etapa, informe outro nome."
                )
            )

            return

        self.accept()


    # -------------------------------------------------------------------------
    # 3.5. RETORNO DAS CONFIGURAÇÕES
    # -------------------------------------------------------------------------

    def obter_configuracao(self):

        nome_normalizado = normalizar_nome_pacote(
            self.campo_nome.text()
        )

        data_execucao = datetime.now().strftime(
            "%Y%m%d"
        )

        nome_pasta = (
            f"ENTREGA_{nome_normalizado}_"
            f"{data_execucao}_v001"
        )

        pasta_destino = self.campo_destino.text()

        caminho_pacote = os.path.join(
            pasta_destino,
            nome_pasta
        )

        nome_projeto_qgz = (
            f"{nome_normalizado}_ENTREGA.qgz"
        )

        return {
            "modalidade": "ENTREGA_EXTERNA",
            "nome_base": nome_normalizado,
            "nome_pasta": nome_pasta,
            "pasta_destino": pasta_destino,
            "caminho_pacote": caminho_pacote,
            "nome_projeto_qgz": nome_projeto_qgz,
            "converter_vetores":
                self.check_converter_vetores.isChecked(),
            "copiar_rasters":
                self.check_copiar_rasters.isChecked(),
            "copiar_estilos":
                self.check_copiar_estilos.isChecked(),
            "criar_qgz":
                self.check_criar_qgz.isChecked(),
            "caminhos_relativos":
                self.check_caminhos_relativos.isChecked(),
            "gerar_inventario":
                self.check_inventario.isChecked(),
            "gerar_manifesto":
                self.check_manifesto.isChecked(),
            "gerar_hashes":
                self.check_hashes.isChecked(),
            "validar_pacote":
                self.check_validar.isChecked()
        }


# =============================================================================
# 4. EXECUÇÃO
# =============================================================================

try:

    print("")
    print("=" * 76)
    print("EMPACOTADOR DE DADOS PARA ENTREGA EXTERNA")
    print("ETAPA 01 - CONFIGURAÇÃO E VALIDAÇÃO")
    print("=" * 76)

    projeto = QgsProject.instance()

    # -------------------------------------------------------------------------
    # 4.1. OBTER CAMADAS SELECIONADAS
    # -------------------------------------------------------------------------

    camadas_selecionadas = (
        iface.layerTreeView().selectedLayers()
    )

    if not camadas_selecionadas:

        raise Exception(
            "Nenhuma camada foi selecionada.\n\n"
            "Selecione no painel Camadas os dados que devem "
            "compor a entrega e execute o script novamente.\n\n"
            "Use Ctrl + clique para selecionar várias camadas."
        )

    # -------------------------------------------------------------------------
    # 4.2. VERIFICAR DUPLICIDADE DE NOMES
    # -------------------------------------------------------------------------

    nomes = [
        camada.name()
        for camada in camadas_selecionadas
    ]

    nomes_duplicados = sorted({
        nome
        for nome in nomes
        if nomes.count(nome) > 1
    })

    if nomes_duplicados:

        resposta = QMessageBox.question(
            iface.mainWindow(),
            "Nomes de camadas duplicados",
            (
                "Existem camadas selecionadas com o mesmo nome:\n\n"
                + "\n".join(
                    f"• {nome}"
                    for nome in nomes_duplicados
                )
                + "\n\nA versão final padronizará os nomes "
                  "para evitar conflitos no GeoPackage.\n\n"
                  "Deseja continuar a configuração?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if resposta != QMessageBox.Yes:

            raise InterruptedError(
                "Configuração cancelada devido a nomes duplicados."
            )

    # -------------------------------------------------------------------------
    # 4.3. ABRIR A JANELA
    # -------------------------------------------------------------------------

    janela = JanelaEntregaExterna(
        camadas=camadas_selecionadas,
        parent=iface.mainWindow()
    )

    resultado = janela.exec_()

    if resultado != QDialog.Accepted:

        raise InterruptedError(
            "Configuração cancelada pelo usuário."
        )

    configuracao = janela.obter_configuracao()

    # -------------------------------------------------------------------------
    # 4.4. CONTAR OS TIPOS
    # -------------------------------------------------------------------------

    contagens = contar_tipos_camadas(
        camadas_selecionadas
    )

    # -------------------------------------------------------------------------
    # 4.5. MOSTRAR CONFIGURAÇÃO NO CONSOLE
    # -------------------------------------------------------------------------

    print("")
    print("-" * 76)
    print("PLANO DE EMPACOTAMENTO")
    print("-" * 76)

    print(
        f"Modalidade: "
        f"{configuracao['modalidade']}"
    )

    print(
        f"Nome-base: "
        f"{configuracao['nome_base']}"
    )

    print(
        f"Pasta do pacote: "
        f"{configuracao['caminho_pacote']}"
    )

    print(
        f"Projeto QGZ: "
        f"{configuracao['nome_projeto_qgz']}"
    )

    print(
        f"Camadas selecionadas: "
        f"{len(camadas_selecionadas)}"
    )

    print(
        f"Vetores: {contagens['Vetor']}"
    )

    print(
        f"Rasters: {contagens['Raster']}"
    )

    print(
        f"Tabelas: {contagens['Tabela']}"
    )

    print("")
    print("Opções:")

    print(
        "  Converter vetores: "
        f"{configuracao['converter_vetores']}"
    )

    print(
        "  Copiar rasters: "
        f"{configuracao['copiar_rasters']}"
    )

    print(
        "  Copiar estilos: "
        f"{configuracao['copiar_estilos']}"
    )

    print(
        "  Criar QGZ na raiz: "
        f"{configuracao['criar_qgz']}"
    )

    print(
        "  Caminhos relativos: "
        f"{configuracao['caminhos_relativos']}"
    )

    print(
        "  Gerar inventário: "
        f"{configuracao['gerar_inventario']}"
    )

    print(
        "  Gerar manifesto: "
        f"{configuracao['gerar_manifesto']}"
    )

    print(
        "  Gerar hashes: "
        f"{configuracao['gerar_hashes']}"
    )

    print(
        "  Validar pacote: "
        f"{configuracao['validar_pacote']}"
    )

    print("")
    print("Camadas:")

    for indice, camada in enumerate(
        camadas_selecionadas,
        start=1
    ):

        print(
            f"  {indice}. "
            f"{descrever_camada(camada)}"
        )

    print("-" * 76)

    # -------------------------------------------------------------------------
    # 4.6. RESUMO NO POPUP
    # -------------------------------------------------------------------------

    texto_camadas = "\n".join(
        f"• {camada.name()}"
        for camada in camadas_selecionadas
    )

    mensagem = (
        "Configuração validada com sucesso.\n\n"
        f"Modalidade:\n"
        "Entrega externa\n\n"
        f"Pasta planejada:\n"
        f"{configuracao['caminho_pacote']}\n\n"
        f"Projeto na raiz:\n"
        f"{configuracao['nome_projeto_qgz']}\n\n"
        f"Camadas selecionadas: "
        f"{len(camadas_selecionadas)}\n"
        f"Vetores: {contagens['Vetor']}\n"
        f"Rasters: {contagens['Raster']}\n"
        f"Tabelas: {contagens['Tabela']}\n\n"
        f"Camadas:\n{texto_camadas}\n\n"
        "Nesta etapa, nenhum arquivo foi criado ou alterado."
    )

    QMessageBox.information(
        iface.mainWindow(),
        "Plano de entrega validado",
        mensagem
    )


# =============================================================================
# 5. CANCELAMENTO
# =============================================================================

except InterruptedError as erro_cancelamento:

    print("")
    print(str(erro_cancelamento))


# =============================================================================
# 6. ERROS
# =============================================================================

except Exception as erro:

    print("")
    print("=" * 76)
    print("ERRO NO EMPACOTADOR DE DADOS")
    print("=" * 76)
    print(str(erro))
    print("=" * 76)

    QMessageBox.critical(
        iface.mainWindow(),
        "Erro no Empacotador",
        (
            "Não foi possível validar a configuração "
            "da entrega externa.\n\n"
            f"Detalhes:\n{str(erro)}"
        )
    )