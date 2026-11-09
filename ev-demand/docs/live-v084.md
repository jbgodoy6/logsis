# D-Max 0.8.4 · Atualização sem piscar e versão sempre visível

Visão geral e Planta ao vivo não recarregam mais documentos. Um arquivo JavaScript
local consulta dados autenticados a cada dois segundos e modifica somente textos,
atributos dos desenhos e pontos da curva que mudaram. Elementos existentes são
preservados, inclusive cartões e o SVG da curva. Não usa iframe, meta refresh,
innerHTML, eval, código remoto, bibliotecas externas ou conversão de HTML no navegador.

O rodapé fixo mostra **Versão instalada: v0.8.4**, inclusive ao rolar a página.
Nas telas ao vivo, o número vem também do servidor em cada consulta. O login mostra
a versão no rodapé. Se a comunicação falhar, os últimos dados permanecem e aparece
aviso de desatualização; a consulta é retomada automaticamente. Sessão encerrada
interrompe a consulta e solicita novo acesso. Formulários não recebem atualizações
em segundo plano.

## Atualizar

Baixe D-Max-v0.8.4-RaspberryPi-ARM64.zip e extraia fora de /opt/d-max. Na pasta
D-Max-Raspberry, abra um terminal e execute:

```
sudo bash instalar-raspberry.sh
```

Não desinstale nem apague dados. Feche a aba antiga, abra http://127.0.0.1:8080
(ou a porta configurada) e confirme a versão no rodapé. Pode usar Ctrl+Shift+R
uma vez. O navegador precisa permitir JavaScript para a atualização em segundo
plano; se estiver desativado, a página mostra um aviso e continua acessível pelo
botão Atualizar. Este pacote corrige o D-Max local; o kit Grafana não precisa mudar.

## Segurança e validação

Somente páginas ao vivo autenticadas carregam o pequeno script local. Login,
configuração e formulários continuam sem scripts. A política CSP permite scripts
da própria origem nessas duas páginas, proíbe scripts inline e avaliação dinâmica,
e mantém Trusted Types e bloqueio de incorporação. O servidor envia uma descrição
restrita da interface em JSON, baseada nos templates já escapados, sem formulários.
O navegador aceita apenas elementos e atributos da lista de leitura; textos externos
continuam textos, sem serem interpretados como marcação.

Teste Chromium: mudança real da carga simulada altera valor e curva, mantendo as
mesmas referências de DOM do número, SVG e cartão, sem navegação de documento e
sem perda da rolagem do menu. Desconexão/reconexão, encerramento da sessão e rodapé
fixo em desktop/celular também foram verificados. Testes em Linux x86_64; homologar
no Raspberry e nos equipamentos físicos permanece necessário.
