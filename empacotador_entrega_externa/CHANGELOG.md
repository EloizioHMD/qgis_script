# Changelog

Todas as alterações relevantes deste projeto serão documentadas neste arquivo.

O formato segue os princípios de [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Planejado

- revisão assistida de campos sensíveis;
- geração opcional de ZIP;
- suporte a recursos SVG externos;
- suporte a rasters;
- recorte por máscara.

## [1.0.0] - 2026-09-11

### Adicionado

- fluxo consolidado em uma única execução;
- diagnóstico de camadas vetoriais selecionadas;
- validação de CRS, joins e edições abertas;
- consolidação das camadas em um único GeoPackage;
- preservação de CRS e dimensões Z/M;
- normalização e desambiguação de nomes de tabelas;
- exclusão de feições sem geometria somente da cópia;
- registro dos IDs das feições vazias no inventário;
- preservação de geometrias inválidas sem correção automática;
- tratamento do atributo `fid` como `fid_orig`;
- chave interna do GeoPackage configurada como `gpkg_fid`;
- exportação de estilos QML;
- inventário CSV em UTF-8;
- reconstrução de grupos, ordem, visibilidade e expansão dos nós;
- criação de projeto QGZ portátil na raiz;
- configuração e verificação de caminhos relativos;
- reabertura e validação do QGZ;
- validação das tabelas e contagens do GeoPackage;
- manifesto técnico JSON;
- hashes SHA-256 dos arquivos-base finalizados;
- arquivo LEIA-ME para o destinatário;
- marcador `PACOTE_VALIDADO.txt`;
- versionamento automático das pastas;
- montagem e publicação atômica com `_EM_MONTAGEM`;
- limpeza da pasta temporária em caso de falha;
- log consolidado de execução.

### Segurança

- fontes originais não são modificadas;
- entregas existentes não são sobrescritas;
- pacotes incompletos não são publicados como finais;
- join ativo e edição aberta bloqueiam o processo;
- geometrias inválidas não são corrigidas silenciosamente;
- o log ativo é excluído do conjunto de hashes;
- exclusões dos hashes são registradas no manifesto;
- valores de atributos não são incluídos no manifesto.

### Validado

- criação de pacote com 19 camadas vetoriais;
- conversão de 22 registros de origem em 20 feições espaciais exportadas;
- exclusão documentada de duas feições sem geometria;
- preservação de MultiPolygon e MultiPolygonZ;
- coexistência de EPSG:31983 e EPSG:4674;
- exportação de 19 estilos QML;
- tratamento de campos `fid` do tipo incompatível com a chave do GeoPackage;
- movimentação da pasta e abertura bem-sucedida do QGZ em outro diretório;
- ausência de fontes externas no projeto final.

### Limitações conhecidas

- somente camadas vetoriais espaciais;
- sem suporte a rasters;
- sem tabelas sem geometria;
- sem materialização de joins;
- sem relações entre tabelas;
- sem layouts e temas de mapa;
- sem formulários personalizados;
- sem remoção automática de campos sensíveis;
- sem recorte por máscara;
- sem anexos e recursos externos;
- sem compactação ZIP.

## [0.5.1] - 2026-08-28

### Corrigido

- exclusão do log ativo da Etapa 5 do cálculo de SHA-256;
- documentação da exclusão no manifesto e no LEIA-ME;
- prevenção de hash imediatamente desatualizado após novo registro no log.

## [0.5.0] - 2026-08-28

### Adicionado

- manifesto técnico JSON;
- hashes SHA-256;
- LEIA-ME;
- marcador de validação;
- validação final da estrutura do pacote.

## [0.4.0] - 2026-08-28

### Adicionado

- projeto QGZ portátil na raiz;
- reconstrução da árvore de camadas;
- preservação de grupos, ordem e visibilidade;
- aplicação dos estilos QML;
- caminhos relativos;
- reabertura e validação do projeto.

## [0.3.1] - 2026-08-28

### Corrigido

- conflito entre campo `fid` do tipo Double e chave primária do GeoPackage;
- renomeação controlada de `fid` para `fid_orig`;
- criação explícita da chave `gpkg_fid`;
- registro das renomeações no inventário.

## [0.3.0] - 2026-08-28

### Adicionado

- criação da estrutura versionada do pacote;
- conversão das camadas para um único GeoPackage;
- filtragem de feições vazias somente na cópia;
- validação posterior de tabelas e contagens;
- exportação de estilos QML;
- inventário CSV;
- publicação atômica da pasta.

## [0.2.0] - 2026-08-27

### Adicionado

- diagnóstico técnico das camadas;
- verificação de CRS e fontes;
- contagem de geometrias vazias, inválidas e duplicadas;
- detecção de joins, filtros e edição aberta;
- identificação preliminar de campos para revisão.

## [0.1.0] - 2026-08-27

### Adicionado

- interface inicial da Modalidade A, Entrega Externa;
- seleção de camadas no painel do QGIS;
- definição de nome e pasta de destino;
- plano preliminar de empacotamento;
- validação inicial sem criação de arquivos.
