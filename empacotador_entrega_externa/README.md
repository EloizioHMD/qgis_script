# Empacotador de Dados para Entrega Externa

Script PyQGIS para criar pacotes vetoriais portáteis, versionados, documentados e auditáveis a partir das camadas selecionadas em um projeto QGIS.

A versão atual consolida as camadas em um único GeoPackage, preserva a organização visual do projeto, cria um arquivo QGZ portátil na raiz da entrega e gera inventário, manifesto e verificações de integridade SHA-256.

## Versão atual

`1.0.0`

## Finalidade

O Empacotador de Dados para Entrega Externa foi desenvolvido para reduzir riscos comuns no compartilhamento de projetos QGIS, como:

- caminhos quebrados ao mover o projeto;
- arquivos de origem dispersos em várias pastas;
- perda de estilos e organização visual;
- inclusão acidental de registros sem geometria;
- conflito do campo `fid` com a chave interna do GeoPackage;
- ausência de inventário e rastreabilidade;
- sobrescrita de entregas anteriores;
- alteração acidental das fontes originais.

## Fluxo da ferramenta

```text
Camadas vetoriais selecionadas
              ↓
Diagnóstico técnico
              ↓
Confirmação de avisos
              ↓
Criação de pasta temporária versionada
              ↓
Conversão para um único GeoPackage
              ↓
Tratamento de feições vazias e do campo fid
              ↓
Exportação dos estilos QML
              ↓
Geração do inventário CSV
              ↓
Criação do projeto QGZ portátil
              ↓
Validação das fontes e dos caminhos relativos
              ↓
Manifesto, hashes, LEIA-ME e marcador de validação
              ↓
Publicação da pasta final
```

## Principais funcionalidades

### Diagnóstico prévio

Antes de criar o pacote, o script verifica:

- tipo da camada;
- presença de geometria;
- validade da camada;
- validade do CRS;
- edição aberta;
- joins ativos;
- feições sem geometria;
- geometrias inválidas.

### Consolidação vetorial

- reúne as camadas selecionadas em `dados/vetores/dados_entrega.gpkg`;
- mantém uma tabela por camada;
- preserva atributos, CRS e dimensões Z/M;
- normaliza nomes físicos das tabelas;
- mantém os nomes originais no painel Camadas;
- cria nomes únicos quando houver conflito.

### Tratamento de feições vazias

Feições nulas ou vazias:

- permanecem intactas na fonte original;
- não são incluídas no GeoPackage de entrega;
- são contabilizadas no inventário;
- têm seus identificadores de origem registrados para auditoria.

### Tratamento do campo `fid`

Quando a origem contém um campo chamado `fid`, ele é preservado na cópia como:

```text
fid_orig
```

O GeoPackage utiliza uma chave interna própria:

```text
gpkg_fid
```

Nenhum valor original é convertido para inteiro ou descartado silenciosamente.

### Projeto QGIS portátil

O script cria um arquivo QGZ na raiz do pacote e preserva, quando aplicável:

- nomes exibidos;
- grupos;
- ordem das camadas;
- visibilidade;
- expansão dos nós;
- CRS do projeto;
- estilos QML.

O QGZ aponta exclusivamente para o GeoPackage interno usando caminhos relativos.

### Versionamento e publicação atômica

O nome da pasta segue o padrão:

```text
ENTREGA_NOME_YYYYMMDD_v001
```

Se a versão já existir, o contador é incrementado automaticamente.

Durante a criação, o pacote recebe temporariamente o sufixo:

```text
_EM_MONTAGEM
```

A pasta final só é publicada depois que todas as validações forem concluídas. Em caso de erro, somente a pasta temporária é removida.

### Inventário e integridade

O pacote inclui:

- `inventario_camadas.csv`;
- `manifesto_pacote.json`;
- `verificacao_integridade.sha256`;
- `LEIA-ME.txt`;
- `PACOTE_VALIDADO.txt`;
- `logs/empacotamento.log`.

O log ativo não integra a lista de hashes porque continua recebendo registros durante o fechamento. Essa exclusão é registrada no manifesto.

## Estrutura da saída

```text
ENTREGA_NOME_YYYYMMDD_v001/
│
├── NOME_ENTREGA.qgz
├── inventario_camadas.csv
├── manifesto_pacote.json
├── verificacao_integridade.sha256
├── LEIA-ME.txt
├── PACOTE_VALIDADO.txt
│
├── dados/
│   └── vetores/
│       └── dados_entrega.gpkg
│
├── estilos/
│   └── arquivos.qml
│
└── logs/
    └── empacotamento.log
```

## Requisitos

- QGIS 3.34 LTR ou superior;
- Python 3 fornecido pelo QGIS;
- permissões de gravação na pasta de destino;
- camadas vetoriais espaciais com CRS válido.

Não é necessário instalar pacotes Python externos.

## Instalação

1. Baixe `empacotador_entrega_externa_v1_0_0.py`.
2. Abra o QGIS.
3. Acesse **Complementos > Console Python**.
4. Clique em **Mostrar Editor**.
5. Abra o arquivo do script no editor.

O script também pode ser salvo na pasta de scripts do perfil QGIS para reutilização.

## Como usar

1. No painel **Camadas**, selecione os vetores que devem compor a entrega. Use `Ctrl + clique` para selecionar várias camadas.
2. Execute `empacotador_entrega_externa_v1_0_0.py` no Editor Python do QGIS.
3. Revise os avisos, informe o nome-base e escolha a pasta de destino.
4. Abra o QGZ criado na raiz e faça uma conferência visual antes do envio.

## Bloqueios da execução

A versão 1.0.0 interrompe o fluxo quando encontra:

- camada não vetorial;
- tabela sem geometria;
- camada inválida;
- CRS ausente ou inválido;
- camada em modo de edição;
- join ativo;
- camada sem nenhuma feição espacial exportável;
- pasta de destino sem permissão de gravação.

## Avisos que permitem continuar

- feições sem geometria;
- geometrias inválidas.

Feições sem geometria são omitidas somente da cópia. Geometrias inválidas são preservadas e registradas, sem correção automática.

## Conteúdo do inventário

O inventário registra, por camada:

- ordem;
- status;
- nome original;
- nome da tabela no GeoPackage;
- tipo geométrico;
- presença de Z e M;
- CRS e descrição;
- provedor e fonte original;
- quantidade de campos;
- feições de origem e exportadas;
- feições vazias ignoradas;
- identificadores das feições vazias;
- geometrias inválidas;
- arquivo QML;
- campos renomeados;
- chave primária do GeoPackage;
- grupos e visibilidade;
- observações do processamento.

## Verificação de integridade

O arquivo `verificacao_integridade.sha256` contém uma linha por arquivo-base finalizado:

```text
HASH_SHA256  caminho/relativo/do/arquivo
```

Exemplo de verificação no PowerShell:

```powershell
Get-FileHash .\NOME_ENTREGA.qgz -Algorithm SHA256
```

Exemplo em Linux:

```bash
sha256sum NOME_ENTREGA.qgz
```

Compare o valor calculado com o valor registrado no arquivo de integridade.

## Governança e rastreabilidade

### Datum e CRS

- cada camada mantém o CRS declarado na origem;
- não há reprojeção automática;
- diferentes CRS podem coexistir no pacote;
- o CRS do projeto é preservado;
- o inventário registra o CRS de cada tabela.

### Escala e precisão

A conversão não aumenta a precisão dos dados. A qualidade do produto continua dependente de:

- escala da fonte;
- método de levantamento;
- precisão posicional;
- qualidade geométrica;
- CRS corretamente atribuído;
- data e procedência dos dados.

### Confidencialidade

A versão 1.0.0 não remove campos sensíveis automaticamente. O operador deve revisar se as camadas possuem dados pessoais, confidenciais, internos ou restritos antes da entrega.

A seleção de uma camada não significa que sua redistribuição esteja autorizada.

### Limites da validação

O status `VALIDADO` indica que o pacote passou por verificações estruturais e digitais. Ele não comprova:

- exatidão posicional;
- titularidade;
- domínio;
- validade registral;
- correspondência de campo;
- autorização jurídica de compartilhamento;
- conformidade regulatória.

## Limitações da versão 1.0.0

Ainda não são suportados:

- rasters;
- tabelas sem geometria;
- materialização de joins;
- relações entre tabelas;
- layouts de impressão;
- temas de mapa;
- formulários personalizados;
- recorte por máscara;
- remoção assistida de campos sensíveis;
- anexos;
- recursos SVG ou imagens externas;
- compactação ZIP;
- publicação em PostGIS ou GeoServer.

## Testes recomendados para contribuições

Antes de abrir um pull request, valide:

- GeoJSON, Shapefile e GeoPackage como fontes;
- Point, linha, Polygon e MultiPolygonZ;
- nomes com acentos, caracteres especiais e duplicidades;
- presença de feições vazias;
- presença de campo `fid` não inteiro;
- cancelamento pelo usuário;
- falha de gravação;
- movimentação da pasta e abertura do QGZ em outro diretório.

Critérios detalhados estão em `CRITERIOS_RELEASE_1_0_0.md`.

## Roadmap

Possíveis evoluções:

1. revisão e remoção assistida de campos sensíveis;
2. compactação ZIP e hash do arquivo distribuído;
3. suporte a recursos SVG externos;
4. suporte a rasters;
5. recorte por máscara;
6. cópia de layouts e temas de mapa;
7. suporte a relações e formulários;
8. modalidade de publicação em servidor de arquivos;
9. modalidade de backup completo.

## Contribuição

Contribuições são bem-vindas por meio de issues e pull requests.

Ao relatar um problema, inclua:

- versão do QGIS;
- sistema operacional;
- tipo e formato da camada;
- mensagem completa do console;
- etapa em que ocorreu a falha;
- exemplo mínimo sem dados confidenciais, quando possível.

## Autor

Eloízio Dantas

## Licença

Defina uma licença explícita no repositório antes de permitir redistribuição ampla. Se optar por uma licença aberta, adicione o arquivo `LICENSE` e atualize esta seção com o identificador correspondente.
