# D-Max 0.5.0 — instalação no Windows x64

Este pacote contém a interface gerada pelo Python, sem JavaScript no navegador.
As dependências Windows x64 para Python 3.12, 3.13 e 3.14 estão em wheels/.
A instalação dessas dependências funciona sem internet e confere seus hashes.
O Python deve estar previamente instalado e acessível pela conta do usuário.
O Python 3.14.0 já confirmado no computador do usuário é compatível.

## Começar

1. Extraia o ZIP inteiro, incluindo wheels/, em uma pasta nova e gravável, por
   exemplo C:\D-Max-0.5.0. Não execute dentro do ZIP nem misture os arquivos com
   uma versão antiga.
2. Execute iniciar-windows.bat. A primeira execução cria .venv e instala os
   pacotes locais. Não é necessário executar como administrador do Windows.
3. Mantenha o terminal aberto e acesse http://127.0.0.1:8080 no navegador.
4. Na primeira instalação, defina a senha raiz de recuperação e a senha do
   administrador. Depois entre com admin ou root e a senha que você definiu.
5. Para validar, abra Simulador e clique em Carregar demonstração. Volte a
   Visão geral para acompanhar a distribuição, atualizada a cada 2 segundos.
6. Ctrl+C no terminal encerra o programa. Para iniciar outra vez, execute o
   mesmo iniciar-windows.bat.

O usuário root é uma conta do D-Max, separada do administrador do Windows.
Nenhuma senha raiz ou administrativa vem predefinida no pacote. Operadores e
técnicos novos usam a senha inicial acordada 12345678, código individual e
troca obrigatória no primeiro acesso.

## Atualizar preservando os dados

Encerre a versão anterior e faça backup do banco antes de atualizar. Copie
somente a pasta data/ da instalação antiga para a nova pasta D-Max. Não copie
app/, arquivos HTML/JavaScript antigos, .venv ou configurações de teste.
As contas, carregadores, veículos e configurações existentes serão preservados
no banco; não crie uma instalação vazia se precisa desses dados. A migração
de usuários antigos, quando necessária, gera uma cópia privada de segurança.

## Páginas

- Visão geral: demanda, gráfico e estados; atualização automática a cada 2 s.
- Carregadores ao vivo: todos os conectores, também com atualização a cada 2 s.
- Simulador: outras cargas e demonstração, para validar sem hardware.
- Carregadores: cadastro, potência, pausa/retomada, veículo, emergência e teste.
- Veículos: nomes, identificadores e prioridade.
- Horários: bloqueios, dias e política durante o horário restrito.
- Multimedidor: TCP/IP ou RS485 e mapa manual, com teste antes de salvar.
- Configurações: demanda, circuitos e parâmetros conforme o perfil de acesso.
- Usuários: cadastro, bloqueio, exclusão e renovação da ativação.
- Técnicos globais: Google Planilhas/Apps Script, chave e intervalo, para root.
- Minha senha: alteração da própria senha, com novo login após trocar.

As páginas de configuração não atualizam automaticamente durante a digitação.
Nas outras páginas, use Atualizar quando desejar leituras mais recentes.

## Google Planilhas

A sincronização exige publicar o Apps Script na conta Google do proprietário.
Ela não é ativada automaticamente ao instalar o programa. O código e o guia
estão no repositório, fora deste pacote de execução:

https://github.com/jbgodoy6/logsis/blob/feat/ev-demand-v0.1/ev-demand/docs/google-planilhas.md

O cadastro de técnicos é global e mantém exatamente a validade da última
sincronização bem-sucedida quando estiver sem internet.

## Segurança e limites da validação

O pacote não contém a interface JavaScript antiga, testes de desenvolvimento,
relatórios com exemplos de vulnerabilidades, banco ou credenciais reais.
As wheels são artefatos oficiais do PyPI conferidos pelo requirements.lock.
Elas contêm bibliotecas nativas de terceiros necessárias ao Python; não são
um executável D-Max compilado ou um instalador assinado pela Microsoft.

Não foram executados Microsoft Defender nem esta versão nativamente no
Windows neste ambiente de desenvolvimento Linux. A classificação dos pacotes
anteriores não está esclarecida. Portanto, este pacote ainda precisa ser
validado pelo Defender: se houver alerta, mantenha o bloqueio. Não desative a
proteção, crie exclusões ou renomeie arquivos para contorná-lo.

O serviço é local por padrão, em 127.0.0.1. Não há serviço de inicialização
automática do Windows neste pacote. Para acesso pela rede, é necessário
configurar HTTPS/WSS e a proteção de rede da instalação.

O modo físico preserva o adaptador OCPP 1.6J e Modbus existentes, mas permanece
piloto: exige homologação do medidor, carregadores e proteções elétricas
independentes antes de operar uma instalação real.

O arquivo SHA256SUMS.txt permite conferir a integridade dos arquivos. Os hashes
não substituem análise antivírus ou assinatura de editor confiável.
