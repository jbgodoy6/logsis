# EnergyCube D-Max 0.9.0 — Raspberry Pi OS ARM64

## Atualizar preservando os dados

1. Baixe o ZIP Raspberry 0.9.0 no Raspberry ou copie pela rede.
2. Extraia em uma pasta nova, fora de /opt/d-max. Abra um terminal dentro da pasta D-Max-Raspberry extraída.
3. Execute `sudo bash instalar-raspberry.sh` e aguarde a conclusão.
4. Abra novamente http://127.0.0.1:8080 no Raspberry ou o endereço de rede configurado. Confira **v0.9.0** no rodapé.

Não desinstale para atualizar. O instalador faz backup da versão anterior em
/var/backups/d-max e preserva banco, usuários, credencial raiz e /etc/d-max.
Continua iniciando no boot, com reinício automático e watchdog. O desinstalador
continua no pacote. Para uma atualização por SSH sujeita a queda, use uma sessão tmux.
Não feche o terminal durante a instalação.

## Novidades

- Multimedidor ampliado e leituras maiores/mais contrastadas na visão geral e
  planta ao vivo. Continua mostrando apenas as grandezas habilitadas, sem piscar.
- Histórico → **Relatório de recargas em PDF**: período, veículo e carregador;
  logos EnergyCube/D-Max, horários, duração, kWh e totais. Funciona offline.
- Veículos → **Excluir da frota**: confirmação obrigatória; recargas históricas e
  nome do veículo permanecem disponíveis. Veículo conectado/em sessão não pode
  ser excluído. Administrador, técnico e raiz podem excluir; operador não.
- Assinaturas por instalação na mesma planilha Google; veja ASSINATURAS-GOOGLE.md.
- Permissão limitada para porta 80 sem executar a aplicação como root.
- Serviço recebe os grupos dialout e, quando existente, plugdev para adaptadores
  USB/RS485. Isso não garante compatibilidade com qualquer adaptador/driver.

## Relatórios

O filtro seleciona pelo **início da sessão**, com início incluso e fim exclusivo,
no fuso da instalação. Um intervalo sem horário (pela API) começa à meia-noite.
A energia é a energia total da sessão selecionada, não um rateio artificial de
kWh no intervalo. Sessões em andamento são parciais e sessões simuladas são
identificadas. Contém todas as sessões encontradas no banco local, inclusive de
itens excluídos, não somente as últimas 100 da tabela da página. Acima de 20.000
sessões, solicite um período menor; não há truncamento silencioso. Não é relatório
fiscal nem cálculo tarifário. Grafana e banco externo não são consultados.

## Porta 80 (opcional)

Após instalar, edite `sudo nano /etc/d-max/rede.ini`, altere somente `porta = 80`,
salve e execute `sudo systemctl restart d-max`. Verifique antes se outro programa
usa a porta: `sudo ss -ltnp 'sport = :80'`. O padrão permanece 8080 para preservar
as instalações. A unidade concede apenas CAP_NET_BIND_SERVICE, sem rodar como root.
Acesse `http://<nome>.local` ou `http://<IP>`; resolução do nome depende do mDNS/DNS.
Se os carregadores usavam OCPP na porta 8080, **atualize também a URL OCPP deles**
para a nova porta; página web e OCPP compartilham a porta. Regras de firewall e
proxy podem precisar ser ajustadas. HTTP na porta 80 não habilita HTTPS.

## Validação

Testes automatizados cobrem PDF e filtros, histórico após exclusão, aviso assinado,
contagem offline/reinício/replay/retrocesso de relógio, regularização, comandos
OCPP sem perfil de potência no modo nativo e preservação de instalação. O teste
WebSocket usa carregadores simulados falando OCPP; não substitui homologação física.
Cada modelo real deve confirmar ClearChargingProfile, auto-início e término da
recarga antes de habilitar cobrança com transição automática. A confirmação OCPP
indica aceite do comando, não comprova a configuração elétrica interna.

Raspberry Pi físico, Windows nativo e adaptador RS485 físico não foram acessados
no ambiente de desenvolvimento. Validar primeiro em bancada, sem carga de cliente.
