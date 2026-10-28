# LogSis Android 1.1 — área técnica

Aplicativo nativo com identidade LogSis/Grupo Sistel, acesso normal ao site e área técnica separada. **Gera apenas BIN; não exporta dashboards ou JSON do Grafana.**

## Estado da entrega

O código e a compilação de avaliação estão preparados. **Falta publicar o serviço na conta Google do administrador e incluir sua URL fixa no APK.** Sem essa ativação, a área técnica informa a pendência e bloqueia a programação. Não existe senha de teste, autorização offline ou configuração de URL pelo usuário.

Veja o [guia de ativação](backend/README.md). A prévia não substitui uma instalação anterior assinada com outra chave, porque usa o identificador separado `br.com.sistel.logsis.avaliacao`.

## Operação

1. O técnico informa login e senha padrão. A senha é verificada no servidor, sem ser embutida no APK.
2. No Android 10+, o seletor do sistema apresenta redes começando com `LOGSIS`, incluindo `LOGSIS_numero_de_serie`, e solicita confirmação. Android 8/9 usa a seleção manual nas configurações, com conferência do prefixo ao retornar.
3. O app direciona seu navegador local ao Wi-Fi escolhido e abre `http://192.168.4.1/`, mesmo com o 4G ligado. As consultas de autorização usam uma rede de internet separada. Sem internet para validar o técnico, a programação é bloqueada.
4. O técnico navega pelas telas do próprio equipamento. Autenticação HTTP Basic usa as credenciais fornecidas pelo proprietário. Formulários HTML são preenchidos pelo técnico; o botão **Acesso** mostra as credenciais. Não há automação baseada em campos ou endereços internos desconhecidos.
5. No campo de envio de arquivo, escolhe **Biblioteca LogSis** ou **Arquivos do celular**. A segunda opção envia o `.bin` escolhido sem reescrevê-lo.
6. A página do equipamento realiza o envio. O app não inventa endpoints de upload nem envia comandos de partida ou disjuntores. Use o BIN no campo de **configuração**, não no de atualização de firmware.

## Biblioteca e BIN

Os 17 BINs-base são os mesmos do Studio: DSE7420, DSE8610, DSE4520 MkII, DSE6120 MkII, DSE6320, DSE7320 MkII, DSE8620, DSE8660, DSE8680, AGC150 GEN, GEN/BUS, MAINS, ATS e ENG, SGC420 MkII, CGC412 e CGC413. SGC120, SGC410, GEN-H e BTB permanecem excluídos do escopo.

Nos perfis locais, o técnico escolhe Slave ID e valores nominais de tensão L–L, frequência, bateria e rotação. O app recalcula somente os limites indicados pelos metadados do Studio, com o mesmo arredondamento. Os padrões são 380 V, 60 Hz, 24 V, 1800 rpm e Slave ID 10; confira os valores da instalação, especialmente média tensão.

Para Wi-Fi da instalação, o BIN recebe SSID e senha escolhidos. O AP do equipamento mantém a senha padrão informada pelo proprietário. Para 4G, configure operadora/APN nas telas do equipamento após carregar o BIN. Não foram inventados campos de firmware ou APNs que ainda não recebemos.

Atualizações da pasta privada do Drive passam pelo serviço autorizado e são verificadas por SHA-256 antes de ativar o catálogo novo. A pasta ainda depende de configuração administrativa. Sem atualização, os perfis locais permanecem; o acesso técnico continua exigindo validação online. Perfis externos preservam os limites definidos pelo administrador.

O BIN textual mantém UTF-8/BOM ou Windows-1252, quebras de linha, parâmetros desconhecidos e valores com ponto e vírgula. Os BINs preparados são entregues ao WebView por um provedor privado, somente de leitura, ou salvos pelo seletor do Android. Não há permissão geral de armazenamento.

## Acesso e rede

Somente `ATIVO` autoriza; inativo, excluído, cadastro apagado ou duplicado não autorizam. A sessão fica em memória e é revalidada periodicamente e antes de enviar arquivos e solicitações de escrita. As limitações da senha compartilhada estão no guia do serviço.

O navegador normal continua limitado a HTTPS. O navegador técnico aceita somente `192.168.4.1`, porta 80, única exceção de HTTP. Não há ponte JavaScript/nativa, liberação de certificados inválidos ou navegação para arquivos locais. A conexão local é liberada ao sair da área técnica.

Além de internet e estado da rede, a conexão solicita permissões Wi-Fi. Até Android 12, o sistema exige as permissões de localização para essa seleção; a partir do Android 13, usa dispositivos Wi-Fi próximos. O app não coleta histórico de localização, contatos ou SMS.

## Compilar e verificar

JDK 17 ou 21, Android SDK 35, Build Tools 35.0.0 e Gradle 8.9, cujo SHA-256 é conferido pelo wrapper.

```sh
cd app/android
./gradlew assembleDebug testDebugUnitTest lintDebug
./gradlew assembleRelease -PtechnicianAuthUrl=https://script.google.com/macros/s/ID_DA_IMPLANTACAO/exec
```

Use a URL real e assine o release com a chave do proprietário. Para testes do serviço sem acessar dados reais: `node app/backend/test_backend.cjs`.

Robolectric simula Android; não substitui teste físico de Wi-Fi/4G simultâneos, das páginas reais ou da programação do equipamento. A implantação Google e uma conta técnica real ainda precisam ser testadas após ativação. Esta entrega não publica o app em loja nem altera a planilha.
