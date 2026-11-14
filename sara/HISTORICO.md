# Histórico do piloto SARA

O piloto usa 20 casos de treino (10 pares). O teste oficial tem 100 casos binários. Os números abaixo são do piloto. A referência para o novo EDIT é pilot-29c3ee5ad655.

## Fluxo implementado

1. prepare.py extrai narrativa, hipótese e legislação, remove rótulos e nomes reveladores e atribui IDs opacos. Os materiais formais ficam em data/evaluator.
2. DIRECT pede ao LLM uma decisão e uma substituição factual. No braço VERDICT, COMPILE recebe legislação e hipótese e produz a fórmula e suas variáveis. EXTRACT lê o relato e atribui valores com citações ou registra desconhecido.
3. O núcleo SMT/MaxSMT vendorizado testa a fórmula e sua negação sob os fatos. Quando só uma delas é compatível, o adaptador emite a decisão. Quando ambas são compatíveis, abstém-se. Erros de formato ou evidência também contam no total.
4. Para uma decisão determinada com condições pivotais, EDIT propõe uma substituição. O piloto aplica substituições de um trecho único e reavalia o texto nos dois braços. O VERDICT reaproveita a compilação e extrai novamente os fatos.
5. evaluate.py mede acertos, cobertura e inversões. Na auditoria independente, um revisor traduz a edição em fatos formais. O Prolog consulta a hipótese original e a editada. Essa etapa determina se a edição realmente muda a resposta SARA.

## Rodadas e alterações

| Etapa | Mudança e evidência |
|---|---|
| Adaptação inicial | Diretório SARA próprio, comparação pareada, cache por requisição, solver vendorizado e avaliação independente. |
| Depuração | Aceitação de identificadores descritivos e inteiros, tratamento do tipo ambíguo quando o valor o resolve. Pedido explícito de JSON em EDIT, mensagens da API e nova tentativa em timeout de leitura. O snapshot Mini foi alinhado ao WebShop. |
| Mini, pilot-620cc164d6e5 | Direto 19/20, VERDICT 8/20. A auditoria dos positivos revelou requisitos fora do inciso. |
| Nano, pilot-4b5f10b3af55 | Direto 19/20, VERDICT 9/20. Prolog confirmou 5/6 propostas do direto e 8/9 do VERDICT. |
| Nano com COMPILE focado no inciso, pilot-29c3ee5ad655 | O compilador passou a explicitar dispositivo e proposição, restringir condições externas e admitir status declarado. VERDICT 14/20, com 9/12 propostas confirmadas. Direto 19/20. |
| Novo EDIT, pilot-f475e96fd63a | Recebe a fórmula compilada. Pede uma mudança suficiente, mantendo os outros fatos e verificando a fórmula inteira, com valores antes/depois. Admite edição conjunta em um trecho ou abstenção. Os valores propostos são registrados como changes. Auditoria concluída: 9/11 propostas inverteram o Prolog, com cobertura de 9/20 e 14/20 decisões originais corretas. Em 6 das 9 intervenções válidas, o VERDICT reproduziu a inversão. Uma das 7 inversões do modelo ocorreu sem inversão do oráculo. |

## Comparação prevista

Executar o mesmo snapshot Nano, endpoint e split pilot. Usar a pasta informada pelo runner para evaluate.py. Comparar com a rodada de escopo por ID. Auditar as novas propostas no Prolog e registrar edições confirmadas/propostas e confirmadas/20. A referência é 9 confirmadas, 3 inválidas e 14 decisões corretas. O cache recupera chamadas idênticas. Novas propostas e reavaliações de textos inéditos podem consumir API.

## Diagnóstico final antes do teste oficial

Reprocessamos pelo cache as quatro falhas técnicas originais de pilot-f475e96fd63a, sem novas inferências. As quatro rejeições foram reproduzidas.

| Caso | Saída rejeitada | Motivo |
|---|---|---|
| §3306(b)(7), positivo e negativo | A compilação compartilhada declara apenas v1, mas a fórmula usa payment_medium, service_not_in_employer_trade e recipient_is_employee, além do literal textual cash. | Referências sem declaração e literal fora da linguagem. A única variável declarada também representa a própria conclusão. |
| §63(a), positivo | A extração de v5 cita a definição legal do valor por isenção. | A definição não é evidência narrativa do valor por pessoa. O relato fornece o total permitido sob §151. |
| §63(c)(7)(ii), positivo | A variável v3 pede que o extrator confirme o valor definido na lei e ele cita o inciso. | É uma regra jurídica modelada como fato do caso. A fonte não atende ao contrato de EXTRACT. |

Decisão de congelamento: manter o compilador, o extrator, o EDIT e a validação da execução pilot-f475e96fd63a para o teste oficial. Os incidentes não demonstraram rejeição indevida de entrada válida. Para uma futura variante, explicitar no COMPILE que toda folha simbólica precisa ser uma variável declarada e que constantes legais pertencem à fórmula. Submeter essa variante a avaliação própria.

## Teste oficial congelado e auditoria contrafactual

Execução test-dd4ec1fe5cf1, 100 casos. Acurácia original: direto 85/100, VERDICT 45/100. Ambos propuseram 37 edições. Revisão textual/formal das 74 propostas; em 65 foi possível executar a consulta original e a contrafactual. As 65 consultas de referência reproduziram seus rótulos. Resultado direto: 20 inversões, 10 manutenções, 7 propostas sem resultado formal validado (2 inválidas). Resultado VERDICT: 22 inversões, 13 manutenções e 2 propostas ambíguas/não verificáveis. Nove casos tiveram edição confirmada nos dois braços; 11 apenas no direto e 13 apenas no VERDICT. Das propostas confirmadas, decisão correta tanto antes como depois: direto 16/20, VERDICT 13/22. Os números dependem da tradução documentada e da representação dos autores; as edições são específicas de cada braço. Artefatos em results/test-dd4ec1fe5cf1/audit-edits.json e oracle-edits.txt; entradas formais em data/evaluator/runtime/inputs-test.json. O caso de cunhada do direto inclui um teste adicional das duas relações familiares usuais.
