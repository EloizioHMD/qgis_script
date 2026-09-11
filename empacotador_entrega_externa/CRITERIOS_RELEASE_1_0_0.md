# Critérios de promoção para 1.0.0

## Gate A - Funcional
- [ ] Executa o fluxo completo em uma única operação.
- [ ] Gera pasta versionada sem sobrescrever pacote anterior.
- [ ] Gera GeoPackage, inventário, QML, QGZ, manifesto, hashes, LEIA-ME e marcador.
- [ ] Remove feições vazias somente da cópia.
- [ ] Preserva geometrias Z/M e CRS por camada.
- [ ] Trata `fid` como `fid_orig` e cria `gpkg_fid`.
- [ ] QGZ abre após mover a pasta.

## Gate B - Compatibilidade
- [ ] Testado em QGIS 3.34 LTR.
- [ ] Testado em pelo menos uma versão QGIS posterior suportada pela equipe.
- [ ] Testado com GeoJSON, Shapefile, GeoPackage e camada de memória.
- [ ] Testado com Point, MultiLineString, Polygon e MultiPolygonZ.
- [ ] Testado com nomes repetidos, acentos, caracteres especiais e nomes longos.

## Gate C - Falhas e recuperação
- [ ] CRS ausente bloqueia antes da gravação.
- [ ] Join ativo e edição aberta bloqueiam com mensagem clara.
- [ ] Cancelar qualquer diálogo não deixa pasta final incompleta.
- [ ] Falha de escrita remove somente `_EM_MONTAGEM`.
- [ ] Camada composta apenas por geometrias vazias bloqueia corretamente.
- [ ] Pacote existente gera versão seguinte.

## Gate D - Integridade
- [ ] Contagem origem - vazias = exportadas para todas as camadas.
- [ ] Todas as tabelas são reabertas e validadas.
- [ ] QGZ não contém caminho absoluto das fontes.
- [ ] Todos os hashes listados podem ser recalculados sem divergência.
- [ ] Log ativo está excluído e a exclusão consta no manifesto.

## Gate E - Segurança e governança
- [ ] Confirmado que a versão 1.0 não remove campos sensíveis automaticamente.
- [ ] LEIA-ME informa limitações e autorização de compartilhamento.
- [ ] Inventário registra origem, CRS, contagens, campos renomeados e ocorrências.
- [ ] Nenhum atributo é impresso no console ou manifesto.

## Gate F - Aceite
- [ ] Três projetos distintos passaram sem falha crítica.
- [ ] Um pacote foi validado em outro computador/perfil de usuário.
- [ ] Revisão de código concluída.
- [ ] README e changelog publicados.
- [ ] Tag Git `v1.0.0` criada somente após todos os gates obrigatórios.
