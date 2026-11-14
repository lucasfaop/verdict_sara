# SARA · LLM direto, VERDICT e VERDICT com política fornecida

Comparação nos 100 casos do teste oficial SARA v1 com GPT-5 nano (snapshot de 7 de agosto de 2025). As narrativas e hipóteses originais são as mesmas nos três métodos.

| Método | Como decide | Acertos | Decisões erradas | Sem decisão |
|---|---|---:|---:|---:|
| LLM direto | O modelo recebe estatutos, narrativa e hipótese | 85 | 15 | 0 |
| VERDICT | A LLM compila a regra e extrai fatos. O SMT testa a regra e sua negação | 45 | 13 | 42 |
| VERDICT + política | Uma fórmula fornecida substitui a compilação. A LLM extrai fatos e o SMT decide | 75 | 1 | 24 |

A política fornecida foi construída retrospectivamente para os dispositivos conhecidos do SARA. As edições contrafactuais são avaliadas separadamente da acurácia original.

## Consultar o estudo

Abra [o relatório bilíngue](sara/relatorio.html) localmente no navegador. [Resultados congelados](sara/frozen/) contém os manifestos, decisões por caso, métricas e auditorias. As novas execuções escrevem em `sara/results/`. O diretório congelado permite verificar a execução histórica mesmo quando o modelo já não estiver disponível.

## Preparar o ambiente e os dados

Na raiz deste repositório, em PowerShell com Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
New-Item -ItemType Directory -Force sara/data/evaluator | Out-Null
Invoke-WebRequest 'https://nlp.jhu.edu/law/sara/sara.tar.gz' -OutFile sara/data/evaluator/sara-v1.tar.gz
.\.venv\Scripts\python.exe sara/code/prepare.py
```

O preparador verifica o SHA-256 da distribuição antes de extrair os dados. Ele separa a entrada pública do gabarito usado pelo avaliador. Fontes: [SARA](https://nlp.jhu.edu/law/) e [artigo do dataset](https://arxiv.org/abs/2005.05257).

## Verificar offline

```powershell
.\.venv\Scripts\python.exe sara/code/smoke.py
.\.venv\Scripts\python.exe sara/code/supplied_policy.py --check
.\.venv\Scripts\python.exe sara/code/evaluate.py sara/frozen/test-dd4ec1fe5cf1
.\.venv\Scripts\python.exe sara/code/evaluate.py sara/frozen/politica-fornecida-bb7055fdc7ff
```

O avaliador recalcula as métricas dos registros e grava metrics.json na pasta avaliada. O smoke test usa exemplos artificiais para verificar o software.

## Rodar com API

Configure `OPENAI_API_KEY` no ambiente do terminal. Os comandos abaixo usam o modelo histórico. Um modelo alternativo compatível com Chat Completions e saída JSON caracteriza uma nova configuração. Para outro endpoint, configure `PILOT_API_BASE`.

```powershell
$model = 'gpt-5-nano-2025-08-07'
.\.venv\Scripts\python.exe sara/code/run.py --model $model --split test
.\.venv\Scripts\python.exe sara/code/supplied_policy.py --model $model
```

O primeiro comando executa direto e VERDICT sobre originais e edições. O segundo executa a política fornecida sobre originais. Use as pastas impressas pelos respectivos comandos:

```powershell
.\.venv\Scripts\python.exe sara/code/evaluate.py <pasta-do-primeiro-comando>
.\.venv\Scripts\python.exe sara/code/supplied_edits.py <pasta-do-segundo-comando>
```

Substitua os campos entre sinais de menor e maior pelos caminhos reais. Os scripts retomam resultados locais existentes. A comparação pareada automática do avaliador procura a execução histórica test-dd4ec1fe5cf1 ao lado da execução com política. A tabela do relatório descreve as rodadas congeladas.

## Créditos

A adaptação para SARA usa o módulo MaxSMT do [VERDICT](https://github.com/zikai-zhou/clinical-trial-matching). A [licença](vendor/verdict/LICENSE), os [avisos](vendor/verdict/NOTICE) e a [citação](vendor/verdict/CITATION.cff) acompanham esse componente. O dataset e o programa Prolog de referência são de Holzenberger, Blair-Stanek e Van Durme. As traduções formais das intervenções são parte desta análise.
