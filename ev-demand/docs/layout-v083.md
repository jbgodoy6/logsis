# D-Max 0.8.3 · Planta ao vivo em largura completa

Corrige a apresentação pequena da área de dados quando o navegador conserva uma
folha de estilo anterior à introdução da navegação estável. O problema foi
reproduzido em Chromium: o quadro assumia o tamanho padrão de cerca de 300 × 150 px.

Agora todas as folhas de estilo usam a versão do aplicativo na URL, para que uma
atualização solicite os arquivos novos. O quadro também declara largura completa
e altura utilizável no próprio HTML como alternativa se o estilo não carregar.
Não altera o controle OCPP, usuários, históricos, rede ou cores salvas.

## Atualizar

Baixe D-Max-v0.8.3-RaspberryPi-ARM64.zip e extraia fora da pasta de instalação.
Na pasta D-Max-Raspberry, abra um terminal e execute:

```
sudo bash instalar-raspberry.sh
```

Não desinstale nem apague os dados. Depois feche a aba antiga do D-Max e abra
http://127.0.0.1:8080 novamente (ou a porta configurada). Também pode usar
Ctrl+Shift+R uma vez. Confirme a versão 0.8.3 no rodapé e abra Planta ao vivo.
Não é necessário atualizar o kit Grafana para esta correção local.

## Verificação

Chromium sem JavaScript: a área ocupou toda a largura interna do conteúdo em
1440×900, 1280×720, 800×480 e 390×780. Em 1280×720 a largura foi 978 px,
correspondente à área restante após o menu e os espaçamentos. Forçando o estilo
antigo, a alternativa HTML também manteve 978 px de largura e 720 px de altura.
Somente o documento de dados se atualiza; o menu permanece fora dele.
Testes de sessão, formulários e cores continuam passando. Validação em Linux
x86_64; confirmar a aparência no Raspberry físico após a atualização.
