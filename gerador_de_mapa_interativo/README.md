# Gerador de Mapa Interativo QGIS

Ferramenta em **PyQGIS** para transformar camadas vetoriais de um projeto QGIS em um mapa interativo responsivo, distribuído como um único arquivo HTML.

O produto foi concebido para facilitar o compartilhamento de análises territoriais com gestores e equipes não especialistas em geoprocessamento. O mesmo mapa pode ser consultado em computador, tablet ou celular, sem necessidade de instalação de software GIS no equipamento do destinatário.

> **Versão atual do ciclo:** 0.0.7.2  
> **Status:** desenvolvimento e validação funcional  
> **Aplicação de referência:** QGIS 3.40 LTR com Python 3.12

---

## Objetivo

O Gerador de Mapa Interativo QGIS permite que um técnico:

1. prepare e revise as camadas no QGIS;
2. escolha quais camadas e atributos serão publicados;
3. configure título, descrição, responsável, classificação e rótulos;
4. gere um arquivo HTML responsivo;
5. compartilhe o mapa por meio corporativo;
6. permita que o destinatário consulte camadas, atributos e medições pelo navegador.

O HTML gerado é uma **publicação de consulta**. O arquivo não substitui o projeto QGIS, os dados-fonte, levantamentos de campo, memoriais descritivos ou análises periciais.

---

## Funcionalidades

### Publicação das camadas

- exportação de camadas vetoriais selecionadas, visíveis ou existentes no projeto;
- transformação das geometrias para WGS 84;
- suporte a pontos, linhas e polígonos;
- seleção dos atributos publicados;
- edição do nome exibido de cada atributo;
- preservação das escolhas ao alternar entre camadas;
- botões **Marcar todos** e **Desmarcar todos**;
- barra de progresso e cancelamento da exportação;
- geração de um único arquivo HTML.

### Rótulos

- escolha do campo de rótulo por camada;
- ativação inicial opcional;
- definição de zoom mínimo;
- posicionamento calculado no QGIS;
- controle individual no HTML;
- caixa compacta com transparência;
- funcionamento responsivo em desktop e celular.

### Mapas-base

- Esri World Imagery como mapa-base padrão;
- Esri World Topographic Map como alternativa;
- troca de mapa-base sem alterar as camadas publicadas.

### Consulta de atributos

- clique ou toque em pontos, linhas e polígonos;
- exibição dos atributos selecionados;
- painel lateral no desktop;
- painel móvel junto às abas em telas menores;
- quebra de linha para textos e vínculos extensos.

### Medições

- distância geodésica aproximada;
- área esférica aproximada;
- cálculo de perímetro;
- unidades automáticas em metros, quilômetros, metros quadrados, hectares e quilômetros quadrados;
- controles **Desfazer**, **Concluir**, **Cancelar** e **Limpar**;
- barra compacta e contextual;
- comportamento equivalente em desktop e celular.

### Responsividade

- interface automática para desktop, tablet e celular;
- painel de camadas em formato de gaveta no celular;
- cabeçalho compacto;
- título em até duas linhas;
- controles adaptados ao toque;
- preservação de zoom, camadas e medições após rotação do dispositivo;
- ausência de rolagem horizontal na página.

### Classificação e confidencialidade

Classificações disponíveis:

- Uso público;
- Uso interno;
- Confidencial;
- Restrito.

O mapa apresenta um aviso inicial de uso. A classificação também é registrada no cabeçalho e na aba **Sobre**.

### Dados temporários KML/KMZ

Durante a sessão, o usuário pode carregar arquivos `.kml` ou `.kmz` para apoio a reuniões e discussões territoriais.

Recursos disponíveis:

- abertura local de KML e KMZ;
- suporte a pontos, linhas, polígonos e `MultiGeometry`;
- leitura de nome, descrição e `ExtendedData`;
- identificação visual com selo **TEMPORÁRIO**;
- estilo laranja diferenciado;
- aproximação automática da extensão;
- checkbox de visibilidade;
- controle individual de opacidade;
- consulta de atributos;
- remoção individual ou coletiva.

Os dados temporários:

- permanecem somente na memória do navegador;
- não são incorporados ao HTML original;
- não alteram o projeto QGIS;
- não alteram os metadados da publicação;
- desaparecem ao atualizar ou fechar a página.

---

## Requisitos

### Ambiente de geração

- QGIS 3.x;
- Python fornecido pelo QGIS;
- projeto com pelo menos uma camada vetorial espacial válida;
- CRS corretamente atribuído às camadas;
- permissão de gravação no local escolhido para o HTML.

### Navegadores-alvo

- Microsoft Edge em Windows e Android;
- Google Chrome em Windows e Android.

A abertura direta de anexos HTML dentro de aplicativos de e-mail depende das políticas de segurança do ambiente corporativo. O fluxo recomendado é baixar o arquivo e abri-lo no navegador.

### Conectividade

A versão atual utiliza recursos externos para:

- Leaflet;
- mapas-base Esri;
- logotipo;
- JSZip, usado para abrir KMZ.

Sem internet, esses recursos podem não ser carregados. A leitura de KML utiliza recursos nativos do navegador, mas a leitura de KMZ depende do carregamento do JSZip nesta versão.

---

## Instalação

O projeto é distribuído como script PyQGIS e não exige instalação como plugin.

1. Baixe o script da versão desejada.
2. Abra o projeto no QGIS.
3. Abra o Editor Python ou o Editor de Scripts de Processamento.
4. Carregue o arquivo `.py`.
5. Execute o script.

Exemplo de arquivo:

```text
gerador_mapa_interativo_0.0.7.2.py
```

> Mantenha versões anteriores arquivadas. Não substitua uma versão estável enquanto a nova versão estiver em validação.

---

## Uso

### 1. Preparar o projeto

- confira os CRS;
- revise nomes e atributos;
- organize a visibilidade das camadas;
- selecione as camadas que serão publicadas.

### 2. Configurar a publicação

Preencha:

- título;
- subtítulo;
- descrição;
- responsável;
- função;
- área responsável;
- versão da publicação;
- data de referência;
- classificação;
- caminho do arquivo HTML.

### 3. Revisar atributos e rótulos

Para cada camada:

- marque os campos que entrarão no HTML;
- revise os nomes exibidos;
- escolha o campo de rótulo;
- defina a exibição inicial;
- defina o zoom mínimo.

### 4. Gerar o mapa

Clique em **Confirmar atributos** e acompanhe a barra de progresso. Ao final, o HTML será gravado e aberto no navegador.

---

## Uso do HTML pelo destinatário

### Computador

1. Abra o HTML no navegador.
2. Leia e aceite o aviso de uso.
3. Utilize as abas **Camadas**, **Detalhes** e **Sobre**.
4. Clique nas feições para consultar os atributos.

### Celular

1. Baixe o arquivo recebido por e-mail.
2. Abra o HTML no Microsoft Edge ou Google Chrome.
3. Toque no menu para abrir as camadas.
4. Toque nas feições para consultar os detalhes.

### Abrir KML ou KMZ temporariamente

1. Abra a aba **Camadas**.
2. Localize **Dados temporários**.
3. Selecione **Abrir KML ou KMZ**.
4. Escolha o arquivo local.
5. Ajuste a visibilidade e a opacidade conforme necessário.
6. Use **Remover** ao encerrar a análise.

---

## Estrutura conceitual

```text
Projeto QGIS
    │
    ├── Camadas vetoriais
    ├── Atributos selecionados
    ├── Configuração de rótulos
    └── Metadados da publicação
            │
            ▼
Gerador PyQGIS
            │
            ▼
HTML responsivo único
    ├── Camadas publicadas
    ├── Mapas-base
    ├── Consulta de atributos
    ├── Medições
    ├── Confidencialidade
    └── KML/KMZ temporário em memória
```

---

## Governança cartográfica

### Sistemas de referência

- vetores incorporados ao HTML: **WGS 84, EPSG:4326**;
- KML/KMZ: coordenadas geográficas em WGS 84;
- mapas-base: **Web Mercator, EPSG:3857**.

### Fontes

- camadas publicadas: projeto QGIS utilizado na geração;
- dados temporários: arquivo selecionado pelo usuário durante a sessão;
- mapas-base: serviços Esri.

### Escala e precisão

A escala e a precisão são determinadas pelas fontes originais. A aproximação visual, a transparência, o zoom ou a sobreposição no navegador não aumentam a precisão posicional dos dados.

### Medições

As medições são aproximadas e destinadas à exploração visual. Não substituem:

- levantamento topográfico;
- memorial descritivo;
- certificação fundiária;
- cálculo pericial;
- validação registral;
- conferência de campo.

### Dados temporários

A sobreposição de um KML ou KMZ temporário não comprova conflito territorial, ambiental, fundiário ou registral. Antes de qualquer conclusão, valide:

- origem do arquivo;
- autoria;
- data de referência;
- método de levantamento;
- CRS;
- escala;
- precisão;
- integridade geométrica.

Decisões com efeito jurídico, regulatório ou pericial exigem validação por profissional competente e, quando aplicável, análise jurídica ou conferência de campo.

---

## Limitações conhecidas

- dependência de internet para recursos externos;
- anexos HTML podem ser bloqueados por políticas corporativas;
- KMZ depende do JSZip externo;
- estilos KML complexos podem ser ignorados;
- não há suporte a `GroundOverlay`, modelos 3D, tours ou `NetworkLink`;
- imagens internas de KMZ não são renderizadas;
- dados temporários não são persistidos;
- geometrias muito grandes podem consumir memória significativa;
- rótulos podem se sobrepor em áreas densas;
- o arquivo HTML contém os atributos publicados e estes podem ser tecnicamente extraídos.

---

## Limites operacionais atuais

| Item | Limite |
|---|---:|
| Arquivo KML/KMZ | 25 MB |
| Feições temporárias | 10.000 |
| Persistência temporária | Somente sessão |
| Profundidade de edição | Somente visualização |

---

## Segurança e privacidade

- publique somente atributos necessários;
- não incorpore dados pessoais ou confidenciais sem base e autorização apropriadas;
- não inclua credenciais, tokens ou senhas no HTML;
- trate o HTML conforme a classificação escolhida;
- compartilhe arquivos confidenciais somente pelos canais corporativos autorizados;
- lembre que dados embutidos no HTML podem ser extraídos por usuários com conhecimento técnico.

---

## Organização das versões

O versionamento segue o padrão de desenvolvimento incremental:

```text
0.0.5.x  Consolidação da interface e dos rótulos
0.0.6.x  Responsividade e medição móvel
0.0.7.x  Camadas temporárias KML/KMZ
```

### Histórico resumido

| Versão | Entrega principal |
|---|---|
| 0.0.4.2 | Referência visual da interface QGIS |
| 0.0.5.5 | Interface consolidada e seleção de atributos |
| 0.0.6.3 | Responsividade e barra de medição contextual |
| 0.0.7 | Importação temporária de KML/KMZ |
| 0.0.7.1 | Opacidade das camadas temporárias |
| 0.0.7.2 | Visibilidade das camadas temporárias e ajuste do painel Detalhes |

---

## Estrutura sugerida do repositório

```text
.
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/
│   └── gerador_mapa_interativo_0.0.7.2.py
├── docs/
│   ├── especificacao_tecnica_mapa_interativo_0.0.6.md
│   └── especificacao_tecnica_mapa_interativo_0.0.7.md
├── examples/
│   └── README.md
└── tests/
    └── plano_de_testes.md
```

---

## Desenvolvimento

Ao implementar uma nova funcionalidade:

1. preserve a versão anterior;
2. incremente a versão do gerador;
3. atualize o título das interfaces;
4. valide a sintaxe Python com `compile()` ou `py_compile`;
5. gere um novo HTML;
6. teste desktop e celular;
7. registre CRS, fontes, premissas e limitações;
8. atualize o `CHANGELOG.md`.

### Verificação de sintaxe

```bash
python -m py_compile src/gerador_mapa_interativo_0.0.7.2.py
```

A verificação de sintaxe não substitui o teste dentro do QGIS e do navegador.

---

## Contribuições

Contribuições devem:

- preservar a simplicidade para usuários não especialistas;
- evitar regressões na interface desktop e móvel;
- incluir tratamento de erros;
- preservar a rastreabilidade da publicação;
- manter dados temporários separados dos dados oficiais;
- documentar dependências externas;
- informar CRS, fonte, escala e limitações;
- incluir instruções de validação.

Sugestão de fluxo:

```text
feature/nome-da-funcionalidade
fix/descricao-do-erro
docs/descricao-da-documentacao
```

---

## Licença

Defina a licença do repositório antes da publicação. Caso o código seja de uso exclusivamente corporativo, substitua esta seção por uma declaração explícita de uso interno e restrições de redistribuição.

Exemplo para projeto aberto:

```text
Este projeto é disponibilizado sob a licença definida no arquivo LICENSE.
```

---

## Aviso técnico

Esta ferramenta apoia visualização e comunicação territorial. O mapa interativo, as medições e as sobreposições temporárias não constituem laudo, certificação, parecer jurídico ou validação pericial.
