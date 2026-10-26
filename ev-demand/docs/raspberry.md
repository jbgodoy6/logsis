# D-Max no Raspberry Pi 4 — instalação e início automático

Recomendado: Raspberry Pi OS Lite **64 bits**, Python 3.12/3.13/3.14 (prefira uma versão fornecida pelo próprio sistema), SSD USB, Ethernet e alimentação estável. Um sistema antigo com Python 3.11 precisa ser atualizado para uma versão suportada; o instalador informa essa condição sem modificar o Python do sistema. A operação offline com horários requer relógio confiável/RTC.

Não copie a `.venv` do Windows. Envie apenas o projeto, sem ambientes virtuais. A arquitetura ARM64 requer suas próprias dependências.

## Preparar e instalar

Na pasta do projeto no Raspberry:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
python3 --version
bash instalar-raspberry.sh --check
sudo bash instalar-raspberry.sh
```

O instalador cria o usuário de serviço `dmax`, instala em `/opt/d-max`, usa banco em `/var/lib/d-max/controller.sqlite3` e configura `/etc/d-max/d-max.env`. É necessária internet na instalação das dependências. Depois, o controle local e o painel funcionam sem internet conforme a comunicação local dos equipamentos.

A unidade `d-max.service` é habilitada no boot, sem login ou janela de terminal. Se o processo sair, o systemd tenta reiniciar após cinco segundos. Para evitar ciclos ilimitados, dez falhas rápidas em um minuto interrompem as tentativas: confira os logs, corrija e execute `sudo systemctl reset-failed d-max; sudo systemctl start d-max`. Uma falha de lógica que mantenha o processo aberto não é equivalente a um encerramento do processo e exige diagnóstico.

## Verificar

```bash
sudo systemctl is-enabled d-max
sudo systemctl status d-max --no-pager
curl --fail http://127.0.0.1:8080/api/setup
sudo journalctl -u d-max -n 60 --no-pager
```

O `curl` deve retornar JSON, por exemplo `{"required":true}` em uma instalação nova. Serviço ativo sozinho não comprova controle físico. Para verificar o boot, reinicie o Raspberry e repita as verificações. Este reinício precisa ser testado no equipamento real.

## Primeiro acesso e rede

Por padrão, o serviço escuta apenas em `127.0.0.1:8080`. A partir do Windows, use um túnel SSH para fazer a primeira configuração local com o navegador:

```powershell
ssh -L 8080:127.0.0.1:8080 SEU_USUARIO@IP_DO_RASPBERRY
```

Abra `http://127.0.0.1:8080` no Windows. O túnel requer que o servidor SSH tenha sido habilitado no Raspberry e que a porta local 8080 esteja livre. Defina as senhas raiz e administrativa, então configure a instalação. Um banco novo inicia em **simulação**; não presume cadastros do Windows.

Para o painel e os carregadores acessarem diretamente a rede, configure host, porta, certificado confiável e chave em `/etc/d-max/d-max.env`, conforme o exemplo de `deploy/`. Arquivos TLS devem ser legíveis pelo grupo `dmax` (por exemplo root:dmax, 0640) dentro de `/etc/d-max`. Não desabilite a verificação de certificados. Reinicie com `sudo systemctl restart d-max` e valide a API no endereço HTTPS configurado antes de conectar carregadores.

## Multimedidor RS485

O serviço tem acesso pelo grupo `dialout`. Prefira um caminho estável `/dev/serial/by-id/...` para o adaptador, em vez de depender da ordem `/dev/ttyUSB0`. Configure porta, baud, paridade, stop bits, Unit ID e mapa manual na interface. Exige adaptador com direção automática e homologação física.

## Dados e atualizações

O instalador preserva o banco e as configurações existentes. Se o diretório `/opt/d-max` não foi criado por ele ou houver uma unidade systemd personalizada diferente, interrompe sem substituir esses arquivos. Em uma atualização gerenciada, interrompe o serviço e guarda o aplicativo anterior em `/var/backups/d-max` antes de copiar o código. A mudança de versão principal do Python do ambiente existente requer migração manual; a rotina não apaga `.venv` automaticamente.

Para migrar dados do Windows, encerre o aplicativo de origem e o serviço do Raspberry, faça backup consistente e copie o banco para o caminho do serviço, ajustando o proprietário para `dmax:dmax`. Preserve um backup de ambos os bancos. Não copie somente o SQLite principal enquanto houver gravações/WAL em andamento. Não importe automaticamente `.venv`, endereço COM ou configurações de rede do Windows: revise porta serial e endereços no Raspberry antes do modo físico.

## Limites da validação

Os testes do aplicativo foram executados em Linux x86-64. As dependências ARM64 são verificadas quanto à disponibilidade, mas o instalador, o boot, USB/RS485, desempenho e contingência precisam ser homologados em um Raspberry físico. A inicialização automática não fornece proteção elétrica independente. Valide os limites de contingência dos carregadores quando o controlador perder alimentação ou comunicação.
