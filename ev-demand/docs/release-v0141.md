# D-Max 0.14.1 — uma única aba para usuários da plataforma

A aba ativa de acessos passa a ser **Usuarios**, com `id | nome | login | perfil | situacao | valido_ate | verificador`.

Perfis aceitos: `tecnico`, `desenvolvedor`, `comercial`. Situações: `ativo`, `bloqueado`, `excluido`. Senhas continuam fora das células: use somente o verificador PBKDF2 gerado pela ferramenta. Administrador e operador locais permanecem no equipamento; root continua reservado à recuperação local após a transição.

## Aplicar no Google

1. Faça uma cópia da planilha antes da mudança. Substitua o Code.gs do mesmo projeto Apps Script pelo desta entrega; mantenha ID da planilha, propriedades e chaves existentes. Não crie outra implantação/URL.
2. Salve. No editor, selecione e execute **migrarUsuarios**; alternativamente, reabra a planilha e use **D-Max → Preparar/migrar usuários (aba única)**.
3. A migração valida os dados antes de criar a aba ativa. Copia Tecnicos e Contas para abas de backup; preserva e oculta as originais. Não apaga propriedades, IDs, logins, credenciais, Assinaturas ou diretório remoto. As cópias contêm verificadores: mantenha o acesso à planilha restrito. Não edite os arquivos de backup como cadastro ativo.
4. Registros das duas abas com **mesmo ID e mesmo login** tornam-se uma única conta. O perfil, metadados e verificador de Contas prevalecem nesse caso, preservando o ID. As credenciais anteriores ficam preservadas nas abas/propriedades antigas. Se o mesmo login tiver **IDs diferentes**, ou um ID tiver logins divergentes, a migração para com uma mensagem específica; não escolhe nem apaga uma identidade. Corrija a divergência preservando o ID histórico, com orientação do responsável, e repita.
5. Se a execução terminar com sucesso, confira Usuarios. Depois publique uma **nova versão da implantação existente** em Implantar → Gerenciar implantações → lápis → Nova versão. Preserve a mesma URL `/exec` e a autorização do equipamento.
6. No D-Max, use o root pelo endereço local e solicite sincronização em Técnicos globais. Cadastre e gerencie todos os três perfis somente em Usuarios. Não use mais as abas ocultas Tecnicos/Contas.

O migrador é repetível: se a aba única já estiver ativada, apenas valida o estado atual. Em caso de falha de escrita, não ativa uma tabela parcial. Não apague abas de preparação ou propriedades para tentar corrigir conflitos sem verificar a mensagem.

## Atualizar o Raspberry pelo terminal

Atualize para 0.14.1 antes de promover uma identidade técnica existente a desenvolvedor/comercial. O Apps Script mantém `technicians` e `accounts` separados na resposta para compatibilidade de protocolo com a 0.14.0 e versões antigas; os dois grupos vêm da mesma aba. A 0.14.1 valida e aplica o conjunto completo, permite mudança de perfil da mesma identidade global e revoga as sessões anteriores. Contas locais de operador/admin/root não podem ser assumidas por esse mecanismo.

Use o pacote **D-Max-Raspberry-0.14.1-SEM-ASSINATURA.zip** e seu `.sha256`. Essa é uma distribuição manual por SSH, sem assinatura original; a página Manutenção não aceita esse ZIP. O instalador existente verifica o manifesto SHA-256 e preserva a chave pública. Não troque a confiança instalada.

Encerre recargas e faça backup. Extraia fora de `/opt/d-max`, execute primeiro `sudo bash instalar-raspberry.sh --check` e, se passar, `sudo bash instalar-raspberry.sh`. O instalador faz a parada e o reinício do serviço; não desinstale e não é necessário reboot. Banco, histórico, configurações, root local, Grafana e ajustes de túnel são preservados.

O instalador agora também copia o gerador de verificadores para o local documentado:

```sh
/opt/d-max/.venv/bin/python /opt/d-max/tools/account_verifier.py
```

Escolha uma senha individual com 12 a 200 caracteres e cole somente o verificador completo na coluna `verificador`. Para mudar o perfil de uma conta, altere apenas `perfil`, preservando `id` e `login`. A mudança revoga sessões antigas; autentique novamente. Os prazos offline e o isolamento das demonstrações da 0.14.0 permanecem.

Não houve implantação nesta conta Google nem acesso ao Raspberry por este ambiente. Testes locais não substituem a confirmação no equipamento.
