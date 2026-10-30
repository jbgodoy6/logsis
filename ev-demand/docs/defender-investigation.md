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

## Revisão da versão 0.6.1 — 30/10/2026

O usuário informou um novo bloqueio ao tentar instalar a 0.6.1 e solicitou revisão
sem fornecer o nome da detecção ou os recursos afetados. O alerta desta versão
permanece sem classificação identificada. Os nomes Ulthar/Wacatac acima são evidências
das versões antigas; não foram atribuídos automaticamente ao novo bloqueio.

### Integridade e origem

- ZIP analisado: `D-Max-v0.6.1-Windows.zip`, SHA-256
  `6a6e2b0a2e968aee6e0501bc58cef6e8dbc65f57311e324eb5e7a50092692c68`.
- Os 68 arquivos passaram pela verificação de integridade do ZIP e do manifesto;
  os arquivos de app/ correspondem byte a byte ao checkout publicado.
- Comparando com 0.6.0, não há entradas adicionadas ou removidas. Mudaram somente
  app/access.py, app/main.py, app/server_ui.py, LEIA-ME.txt e o manifesto SHA256SUMS.txt.
- As 44 wheels são idênticas às da 0.6.0. Os hashes de todas foram conferidos
  novamente com os metadados oficiais HTTPS do PyPI, em 32 pacotes/versões.
  Os manifests RECORD também foram conferidos: 2.332 entradas com hashes e tamanhos
  válidos. Isso verifica integridade/origem, sem certificar segurança dos fornecedores.
- Não há arquivos JavaScript, HTML, PowerShell, VBS ou executáveis EXE soltos no
  pacote. Wheels oficiais podem conter módulos nativos, necessários às dependências.

### Revisão do comportamento

Foram reexaminados o lançador Windows, o ponto de entrada, a descoberta mDNS,
o cadastro/autenticação, a migração de recuperação e os destinos de sincronização.
A pesquisa estática nos módulos distribuídos não encontrou eval/exec, subprocessos
ou comandos de sistema Python. O BAT cria o ambiente Python, instala dependências
com hashes e inicia run.py. Não altera o Defender, firewall, registro ou serviços.

A sincronização envia dados somente aos serviços configurados; a interface nativa
chama a API internamente por transporte ASGI. As mudanças 0.6.1 retiram o campo raiz
da instalação e adotam a senha fixa explicitamente solicitada. Esta credencial
comum permite acesso raiz a quem a conhece; o salt do hash local não elimina esse
risco. Não se atribui a ela a detecção do Defender sem evidência.

A nova execução do pip-audit sobre o lock não encontrou vulnerabilidades conhecidas.
O Bandit registrou oito alertas: cinco baixos (incluindo as duas senhas predefinidas)
e três médios relativos à escuta em 0.0.0.0 para o acesso LAN solicitado. Não houve
alertas altos. Esses resultados são análise de código, não análise antivírus.
Relatórios: [dependências](security/dependencies-v061.json),
[Bandit](security/bandit-v061.json), [origem das wheels](security/wheels-pypi-v061.json).

### Resultado e limite

Não foi encontrado comportamento malicioso nos trechos examinados nem alteração
concreta fundamentada para resolver a nova classificação. Nenhum arquivo de execução
foi alterado ou novo pacote publicado nesta revisão. Os 101 testes funcionais da
0.6.1 permanecem os da validação de lançamento; não foram apresentados como teste
antivírus. Não existe resultado de varredura Microsoft Defender neste ambiente Linux.

O bloqueio continua sem esclarecimento e não se declara falso positivo nem pacote
aprovado. Para uma classificação conclusiva, permanece indicado o portal oficial da
Microsoft citado acima. Nenhuma amostra do projeto foi enviada a terceiros; somente
nomes/versões de dependências foram consultados no PyPI para hashes e avisos públicos.

## Comparação com a última execução relatada — 30/10/2026

Na conversa, após receber a 0.6.0, o usuário relatou que o controlador mostrava seu
endereço automático dmax-….local:8080. Isso indica execução naquele momento e torna
a 0.6.0 uma referência de comparação mais próxima que a 0.5.0. Não demonstra que a
0.6.0 seria aceita hoje pelas definições atuais do Defender.

Foram comparados os conteúdos reais dos ZIPs 0.5.0, 0.6.0 e 0.6.1, incluindo CRC,
manifestos completos, nomes, tamanhos e hashes. Todos os arquivos estão cobertos
pelos manifestos; não há links simbólicos nem entradas extras fora dos manifestos.

| Item | 0.5.0 | 0.6.0 | 0.6.1 |
| --- | --- | --- | --- |
| Arquivos | 62 | 68 | 68 |
| Wheels | 40 | 44 | 44 |
| Interface de execução | Python sem JavaScript | Igual | Igual |
| Descoberta mDNS | Ausente | Introduzida | Idêntica à 0.6.0 |
| Recuperação root | Senha definida na instalação | Senha definida na instalação | Senha fixa compartilhada |

De 0.5.0 para 0.6.0 foram adicionados network.py, rede.ini, ifaddr e três wheels
Zeroconf para as versões de Python suportadas. O iniciador passou a encaminhar as
opções de linha de comando e o ponto de entrada passou a ler a configuração LAN.
Não foram reintroduzidos o JavaScript/HTML antigos no pacote de execução.

De 0.6.0 para 0.6.1 não foi adicionado nem removido arquivo. São byte a byte iguais:
iniciar-windows.bat, run.py, rede.ini, requirements.lock, todas as 44 wheels,
network.py, OCPP, Modbus, distribuição de demanda, sincronização Google, CSS e logos.
Mudaram três módulos Python (access.py, main.py, server_ui.py), o guia e o manifesto.
Os três módulos mudam a recuperação root, o formulário inicial e os números de versão.

### Achado de segurança independente da classificação antivírus

Foi reproduzida a inicialização de cada versão com um banco SQLite em memória e
contas root/admin previamente cadastradas. Na 0.6.0 a senha pessoal root permanece;
na 0.6.1 ela é substituída pela credencial fixa. Nas duas versões, o hash da conta
admin é preservado. Não foi necessário conectar à rede nem usar contas reais.

Essa mudança é uma regressão de segurança: uma credencial pública comum a todas as
instalações concede acesso raiz ao aplicativo, inclusive pela LAN quando habilitada.
A 0.6.1 também impede mudar essa credencial. Esse comportamento foi implementado por
pedido explícito, mas o pedido não elimina o risco. A remoção do campo raiz no primeiro
acesso não exige tecnicamente uma senha universal: uma alternativa seria gerar uma
credencial de recuperação exclusiva por equipamento e apresentá-la localmente uma vez,
mantendo apenas o cadastro da senha admin no formulário inicial.

Não há evidência para afirmar que esse comportamento causou o alerta do Defender.
Também não há evidência para culpar as bibliotecas de rede que já estavam na execução
0.6.0 relatada. Essa comparação localiza as mudanças entre artefatos, não substitui a
classificação do antivírus e não permite prometer que um novo pacote será aceito.

Não houve alteração de código de execução, troca de senha solicitada pelo usuário ou
publicação de outro ZIP durante esta comparação.
Evidências: [comparação dos ZIPs](security/artifact-regression-v050-v061.json) e
[teste isolado da recuperação](security/recovery-comparison-v060-v061.json).
