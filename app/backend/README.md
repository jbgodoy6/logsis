# Ativar a autorização técnica do LogSis

O serviço lê a planilha fixa `17HCp2CX3eUZXqQsTkTNDZvrLkGqzZQrJkCfeHo-toPQ`, aba `Tecnicos`. O celular não precisa de acesso direto à planilha. Não publique a planilha na web para fazer a autenticação funcionar.

O código está preparado, mas o serviço ainda **não foi implantado** em uma conta Google. O APK de avaliação mantém a área técnica bloqueada enquanto sua URL não estiver definida na compilação. O acesso normal ao site continua separado.

## Publicar uma vez, como administrador

1. Entre em [Google Apps Script](https://script.google.com/) com uma conta que tenha acesso à planilha. Crie um **novo projeto independente**, por exemplo `LogSis — autorização técnica`. Não substitua o script ou o menu D-Max que já existir na planilha.
2. Copie [Code.gs](Code.gs) para o arquivo `Code.gs` do projeto novo. Nas configurações do editor, habilite a exibição do manifesto e copie [appsscript.json](appsscript.json) para o manifesto. Ele solicita leitura de planilhas e Drive, não escrita nos cadastros.
3. Em **Configurações do projeto → Propriedades do script**, crie `AUTH_PASSWORD_SETUP`, com a senha padrão escolhida. Essa propriedade é administrativa e não pertence à planilha ou ao aplicativo.
4. Execute **`configurarSenhaTecnica`** pelo editor e autorize o projeto. A função cria o HMAC da senha com uma chave aleatória privada, remove `AUTH_PASSWORD_SETUP` e revoga sessões anteriores. A senha não é colocada no código ou no APK.
5. Confirme que há cadastro real na aba `Tecnicos`: `id` único, `nome`, `login` único e `situacao` igual a `ATIVO`. `INATIVO`, `EXCLUIDO`, `EXCLUÍDO`, cadastro apagado ou duplicado não autorizam. `valido_ate` vazio não acrescenta vencimento; se preenchido, use `DD/MM/AAAA` ou `AAAA-MM-DD`, válido até o fim do dia em Brasília.
6. Selecione **Implantar → Nova implantação → Aplicativo da Web**. Execute como o proprietário e permita acesso **a qualquer pessoa**, conforme as opções da conta. Isso publica o serviço; a planilha continua privada. A senha e o cadastro ativo são validados pelo serviço.
7. Copie a URL terminada em **`/exec`**, não `/dev`. Envie **somente essa URL**, sem a senha, para concluir a compilação do aplicativo. Ela ficará fixa no APK, sem configuração pelo usuário.

Se a organização não permitir publicar aplicativos web para qualquer pessoa, o administrador precisará providenciar um backend HTTPS equivalente. Não altere a política da organização para contornar um bloqueio.

## Atualizar a biblioteca pelo Drive

Opcionalmente, crie uma pasta privada no Drive, acessível à conta que executa o serviço, contendo os BINs-base dos controladores, com nomes como `DSE7420.bin`, `DSE8610.bin` e `AGC150_GEN.bin`.

Configure a propriedade administrativa `LIBRARY_FOLDER_ID` com o ID dessa pasta. Sem ela, os 17 perfis locais permanecem disponíveis; o app informa que a atualização ainda não está configurada. Não inclua senhas de clientes ou redes de instalações nos BINs-base.

O serviço permite até 64 BINs de até 2 MB e informa seu SHA-256. O app verifica os arquivos antes de publicar o catálogo privado atualizado. Uma atualização incompleta não substitui a anterior. Perfis externos preservam os limites definidos na biblioteca; o app altera o Slave ID e as opções de conexão escolhidas pelo técnico.

## Bloqueio e limites

- O servidor lê novamente o cadastro a cada validação. Não existe cópia permanente de `ATIVO` no aparelho.
- O app revalida periodicamente, antes das páginas, da entrega do BIN e de solicitações de escrita. Sem internet para confirmar a autorização, a programação é bloqueada. Ao usar o AP do LogSis, a validação usa outra rede, normalmente o 4G.
- A senha é compartilhada por decisão do projeto. Quem souber a senha e o login de outro técnico ativo poderá se identificar como ele. O modelo bloqueia o **login informado**, sem comprovar identidade individual. Senhas individuais ou um provedor de identidade são a evolução recomendada.
- Esse controle vale para o aplicativo; não altera a autenticação do firmware nem impede acesso por outros programas que conheçam as credenciais do equipamento.
- As sessões duram até 10 minutos, ficam em memória no celular e são revalidadas online. Trocar a senha pelo procedimento acima revoga as sessões antigas.
- Os testes usam serviços Google simulados. A planilha real, a implantação e o equipamento físico ainda precisam de validação após a ativação.

## Compilar com endereço fixo

```sh
./gradlew assembleRelease -PtechnicianAuthUrl=https://script.google.com/macros/s/ID_DA_IMPLANTACAO/exec
```

Assine o APK com a chave de produção do proprietário. A prévia usa o identificador separado `br.com.sistel.logsis.avaliacao` e certificado de avaliação. Chaves privadas, senhas e configurações do ambiente de compilação não fazem parte do projeto-fonte distribuído.
