# D-Max 0.8.2 · Menu estável e cores na configuração local

Corrige o recarregamento completo das páginas Visão geral e Planta ao vivo que
reiniciava a rolagem do menu a cada dois segundos. O menu agora permanece estável;
somente o documento de dados, autenticado e somente para leitura, se atualiza.
As páginas com formulários continuam sem atualização automática. Não é necessário
habilitar JavaScript no navegador. O controle OCPP não foi alterado.

## Atualizar no Raspberry

Baixe D-Max-v0.8.2-RaspberryPi-ARM64.zip no próprio Raspberry e extraia fora de
/opt/d-max. Entre na pasta D-Max-Raspberry, abra um terminal nela e execute:

```
sudo bash instalar-raspberry.sh
```

Não desinstale nem apague banco ou arquivos de configuração. O instalador da
instalação gerenciada faz backup e preserva os dados. Depois abra
http://127.0.0.1:8080 (ou a porta já configurada) e use Ctrl+Shift+R uma vez.
Confirme a versão 0.8.2 no rodapé. Não precisa atualizar o kit Grafana por causa
desta correção: as alterações são no servidor e na página local do D-Max.

## Cores na página local

Entre como administrador, técnico ou raiz, abra **Configurações** e localize
**Cores da planta local**. Clique no seletor de cada estado:

- Carregando.
- Cabo conectado.
- Alarme.
- Cabo desconectado / estado não confirmado.
- Sem comunicação.

Clique em **Salvar cores** e abra **Planta ao vivo**. As escolhas ficam no banco
local e são preservadas após reiniciar o serviço. O formulário altera somente
as cores; não muda demanda, horários ou configuração do multimedidor. Operadores
podem visualizar a planta, mas não alterar a paleta.

Essas escolhas afetam a planta local. No Grafana a paleta continua disponível no
editor do cartão, em Thresholds/Limiares, conforme CORES-E-VISUAL.md.

## Validação e limites

Navegação e salvamento testados em Chromium com JavaScript desativado, em janela
curta de desktop e em largura de celular. O teste acompanha várias atualizações
dos dados, conserva rolagem vertical/horizontal do menu, abre uma opção no fim do
menu e confirma que texto digitado em formulário não desaparece. A cor escolhida
pela página é salva, permanece após recarregar e chega ao desenho.

Proteção de sessão permanece em cada atualização; somente os documentos dos dados
aceitam exibição por outra página da mesma origem. Login, configurações e API
mantêm bloqueio de incorporação. Scripts continuam proibidos pela política CSP.
Validação em Linux x86_64; teste físico no seu Raspberry ainda é necessário.
