# Investigação do bloqueio pelo Microsoft Defender

Situação em 27/10/2026: **detecção ainda não esclarecida; manter o bloqueio**. Os ZIPs 0.3.0 e 0.3.1 não devem ser liberados por exceção de antivírus durante esta investigação.

## Evidência recebida

O histórico `Get-MpThreatDetection` fornecido pelo usuário identifica:

| Pacote | Detecção | Recurso indicado |
| --- | --- | --- |
| D-Max-v0.3.0.zip | Trojan:Script/Ulthar.A!ml — ID 2147751841 | `D-Max/app/static/app.js` e `D-Max/app/static/index.html`, dentro do ZIP |
| D-Max-v0.3.1.zip | Trojan:Script/Wacatac.B!ml — ID 2147735503 | ZIP baixado do repositório; o registro recebido não individualiza arquivos internos |

`ActionSuccess: True` indica sucesso da ação de proteção registrada. Esses dados, por si só, não demonstram execução do arquivo, infecção da máquina nem falso positivo. Caminhos pessoais e identificadores de processos do usuário foram omitidos deste relatório público.

## Comparação dos artefatos

Cada arquivo abaixo foi extraído do ZIP local e comparado byte a byte com o commit que publicou a versão. Todos correspondem ao repositório. O ZIP 0.3.1 publicado no GitHub também foi baixado e teve seu SHA-256 conferido na revisão anterior.

| Recurso | Versão | SHA-256 |
| --- | --- | --- |
| ZIP | 0.3.0 | `17565665fcf82b45220f7705085df55c30c8ad2987664a6896e481685917f894` |
| app.js | ambas | `adf594212ebdf37c229cf1f333ee953de6f15c578cbedfbf2bb3231bb7e8a9a8` |
| index.html | 0.3.0 | `01fbd8ba0af5abd798a8e19af00a54e6ef67821d7fee2fb153491b7364c0f8e4` |
| ZIP | 0.3.1 | `81d096140f0e7ab235c8c8afc1e78b86d313be3094a24aa645ffb4f9977a2f1d` |
| index.html | 0.3.1 | `115a17b68c9f74140155b0a9049d1a2a7f0154bc6857c34f3f6450d1e1dacf9c` |

O JavaScript é idêntico nas duas versões. As correções de dependências e autenticação da 0.3.1 foram necessárias, mas não alteraram esse arquivo e não resolveram a detecção. Não há evidência para atribuir a detecção ao lançador BAT ou às dependências Python.

## Revisão direcionada

Foi lido integralmente o JavaScript de 39.034 bytes e o HTML de 21.259 bytes, além da comparação dos artefatos e da verificação de sintaxe `node --check`.

- O HTML carrega apenas `/static/app.js`; não contém scripts inline, manipuladores inline, iframe, object ou embed. Os estilos e imagens do painel são locais.
- As chamadas `fetch` do JavaScript usam `/api` do próprio servidor. A conexão WebSocket usa o mesmo `location.host`, em `/ws/live`.
- Os formulários de senha usam a API local de instalação, login, troca ou recuperação. A configuração da chave do equipamento também é enviada para a API local. O link Google na tela é um link explícito para a planilha, não um destino dos formulários de senha.
- Não foram encontrados `eval`, `new Function`, execução de comandos do sistema, carregamento dinâmico de scripts externos ou persistência de senhas em localStorage/sessionStorage nesses arquivos. O código contém renderização de HTML e formulários administrativos próprios do painel, com escape de valores textuais.

Não foi identificado comportamento malicioso nessa leitura. Essa conclusão é limitada à análise do código e não equivale a uma varredura do Defender, análise dinâmica completa ou confirmação de falso positivo. As duas detecções devem continuar sendo tratadas como não resolvidas.

## Encaminhamento para análise do fabricante

O passo necessário para esclarecer a classificação é analisar as amostras exatas com a Microsoft, pelo [portal oficial de envio de arquivos](https://www.microsoft.com/en-us/wdsi/filesubmission). O envio pode exigir autenticação e upload da amostra em um ambiente autorizado para análise. Nenhum arquivo foi enviado automaticamente a terceiros nesta investigação.

Texto preparado para acompanhar a amostra:

> Please investigate Microsoft Defender detections on the attached D-Max source distribution. Version 0.3.0 was detected as Trojan:Script/Ulthar.A!ml (ThreatID 2147751841), naming D-Max/app/static/app.js and index.html inside the ZIP. Version 0.3.1 was detected as Trojan:Script/Wacatac.B!ml (ThreatID 2147735503), naming the downloaded ZIP. The JavaScript is identical in both versions (SHA-256 adf594212ebdf37c229cf1f333ee953de6f15c578cbedfbf2bb3231bb7e8a9a8). Manual review found same-origin application API calls and no external script loading or command execution; this is not a confirmed false positive. Please identify the triggering content and determine whether the detection is correct. The report includes SHA-256 hashes for the exact archives and HTML files. Source: https://github.com/jbgodoy6/logsis/tree/feat/ev-demand-v0.1/ev-demand . The original packages remain available in the same repository for comparison.

Após a resposta, deve-se corrigir qualquer conteúdo confirmado como malicioso ou, caso a Microsoft confirme falso positivo, atualizar as definições do Defender e repetir a análise da mesma amostra. Não renomear, cifrar, ofuscar, trocar a extensão ou criar exclusões para contornar a detecção.

## Revisão adicional de 29/10/2026

O usuário informou persistência do bloqueio após a entrega 0.4.0 e perguntou se o nome D-Max seria a causa. O histórico recebido identifica arquivos internos nas versões anteriores; não há evidência que permita atribuir a classificação apenas ao nome do ZIP. Ainda não foi recebido um registro que individualize os recursos detectados na 0.4.0.

Foi novamente conferido o ZIP original 0.4.0, de SHA-256 `c06b797679f7eb401078fd5caca95159259823005cb1b63524d0c069de7238bd`, incluindo integridade e ausência dos pontos de interpretação de HTML por texto removidos da interface. A leitura e a pesquisa do código atual não identificaram um novo comportamento malicioso que justificasse outra alteração. Isso não certifica ausência de ameaça.

Foi preparada uma instalação isolada em `/tmp` do ClamAV 1.4.6, obtido dos pacotes oficiais Debian (`deb.debian.org`). Não foi feita instalação no sistema nem enviado conteúdo do projeto a terceiros. A atualização pelo FreshClam falhou ao acessar `https://database.clamav.net/daily.cvd`; a consulta adicional ao servidor também encontrou falha de proxy. **Sem definições válidas, não foi executada uma varredura antivírus independente e não existe resultado de detecção a relatar.**

Nenhum arquivo de execução foi alterado nem novo ZIP foi publicado nessa etapa. Antes de comparar novas classificações no computador afetado, é pertinente atualizar o Defender pela função oficial `Update-MpSignature`, mantendo a proteção ativa e respeitando a política de TI. Se a mesma amostra continuar bloqueada, permanece necessária a análise da detecção pelo fabricante.
