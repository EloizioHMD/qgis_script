A versão 0.1.0 será o primeiro núcleo funcional do Consultor de Caracterização Ambiental, trabalhando exclusivamente com camadas vetoriais poligonais já carregadas no QGIS. O objetivo é enriquecer um polígono com informações de Geologia, Geomorfologia e Pedologia, mantendo os resultados completos em tabelas relacionadas e apenas um resumo na camada consultada.



Linha de desenvolvimento da versão 0.1.0



Etapa 1, entregue agora



Interface e validação:



listar camadas poligonais;

selecionar a área de consulta;

escolher uma feição ou dissolver todas;

ativar um, dois ou três temas;

selecionar o campo de classe;

informar fonte;

informar data-base;

informar escala;

verificar CRS;

verificar geometria;

verificar interseção de extensões;

apresentar o plano de consulta.



Nenhum arquivo é criado.



Etapa 2



Preparação da geometria:



copiar a área selecionada;

dissolver quando necessário;

validar área maior que zero;

escolher CRS de cálculo;

transformar cópias das geometrias;

gerar identificador de consulta.

Etapa 3



Motor temático:



recortar cada tema;

agrupar por classe;

dissolver por classe;

calcular área;

calcular percentual;

determinar predominância;

medir área sem cobertura;

detectar sobreposição.

Etapa 4



Produtos:



criar GeoPackage;

criar tabela relacionada;

adicionar campos-resumo;

gerar CSV;

gerar ficha HTML;

gerar parâmetros JSON;

gerar log.

Etapa 5



Consolidação:



reunir as etapas em um único script;

validar os resultados;

testar com as três bases;

preparar README;

promover para 0.1.0.

9\. O que o código da Etapa 1 já valida

Área de consulta

camada poligonal;

CRS válido;

exatamente uma feição quando o modo selecionado exigir;

ausência de geometria vazia;

ausência de geometria inválida.

Temas



Para cada tema ativado:



camada selecionada;

CRS válido;

campo de classe selecionado;

fonte informada;

escala informada ou advertência;

geometrias vazias;

geometrias inválidas;

possível ausência de interseção de extensões.

Segurança



O script:



não altera a camada;

não cria campos;

não grava arquivos;

não acessa a internet;

não corrige geometrias;

não atribui CRS;

não imprime valores de atributos.

10\. Como testar a Etapa 1

Carregue no QGIS uma camada poligonal de consulta e pelo menos uma camada temática poligonal.

Selecione exatamente uma feição na camada de consulta.

Execute o script da Etapa 1.

Configure pelo menos um tema e clique em Validar configuração.

Exemplo de teste

Área de consulta:

Área do imóvel



Escopo:

Uma feição selecionada



Geologia:

Camada: unidades\_geologicas

Campo: unidade

Fonte: SGB

Data-base: 01/01/2023

Escala: 1:1.000.000



Geomorfologia:

desativada



Pedologia:

Camada: pedologia\_bdia

Campo: classe\_solo

Fonte: IBGE/BDIA

Data-base: 01/01/2019

Escala: 1:250.000



Resultado esperado



O console mostrará:



PLANO DE CONSULTA VALIDADO



Área: Área do imóvel

CRS: EPSG:31983

Modo: FEICAO\_SELECIONADA



Temas:

Geologia

Pedologia





E o popup confirmará:



Nenhuma camada foi alterada

Nenhum arquivo foi criado



11\. Governança e rastreabilidade

Datum e CRS

CRS de entrada apenas identificado nesta etapa;

nenhuma transformação executada;

CRS de cálculo será visível e registrado nas próximas etapas;

fontes sem CRS serão bloqueadas.

Escala



A escala é informada pelo operador com base no metadado da fonte.



As bases citadas do IBGE/BDIA possuem caráter regional e produtos associados à escala 1:250.000. Essa informação precisa acompanhar cada resultado.



Fontes



Nesta versão:



apenas camadas já carregadas no projeto;

instituição informada pelo operador;

data-base informada pelo operador;

escala informada pelo operador;

nenhuma consulta automática a geosserviço.



A INDE disponibiliza catálogos de serviços WMS, WFS e WCS. A integração futura deverá priorizar WFS ou download para vetores e WCS ou download para coberturas, porque WMS é principalmente uma representação visual.



Premissas

o campo selecionado representa a classificação ambiental;

a fonte e sua data foram informadas corretamente;

o CRS declarado está corretamente atribuído;

a escala é adequada ao nível de caracterização esperado;

o polígono representa a área que se deseja consultar.

Limitações

predominância não significa homogeneidade;

ausência de cobertura não significa ausência da característica;

sobreposição pode produzir dupla contagem;

escala regional não substitui levantamento local;

o resultado não substitui vistoria;

o resultado não constitui conclusão jurídica ou regulatória.

Próximo passo técnico



O próximo módulo deve implementar somente a preparação da área de consulta e do CRS de cálculo. Isso nos permitirá validar o denominador da análise antes de construir o motor de interseção temática.

