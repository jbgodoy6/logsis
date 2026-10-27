# D-Max v0.3.0 — usuários, Google Planilhas e novo logo

Validação em 27/10/2026, Linux x86-64:

- 66 testes aprovados com Python 3.12 e 3.14. Mantidos os testes de alocação, 60 carregadores, OCPP e multimedidor.
- Hierarquia operador/administrador/técnico/raiz aplicada pelo servidor. Administrador ajusta demanda e horários, mas não multimedidor, teto técnico ou circuitos. Somente raiz gerencia técnicos.
- Senha inicial 12345678, ativação individual e troca obrigatória antes de acessar funções. Contas antigas preservam suas senhas.
- Bloqueio/exclusão preservam identidade e invalidam sessões. Validade de técnicos offline segue exatamente a última recebida, inclusive ausência de vencimento.
- Sincronização tem intervalo próprio, consulta no boot/login e configuração exclusiva do raiz.
- Cadastro offline pelo raiz, envio posterior, conflitos de versão, senha não restaurada por mudança de nome e revogação mesmo quando o envio de alterações locais falha.
- Código Apps Script executado em Node com serviços Google simulados: chave por equipamento, snapshot, credenciais fora das células, metadados, exclusão, idempotência e datas.
- Cliente Apps Script segue somente redirecionamento HTTPS para `script.googleusercontent.com`, sem encaminhar chave/cabeçalhos ao destino. Redirecionamento a outro host é rejeitado.
- Chave do equipamento e hashes não aparecem no estado público nem na auditoria. O código individual de ativação aparece somente na resposta de criação/renovação, para entrega ao usuário.
- Migração de banco antigo preserva senha e cria backup SQLite privado antes de alterar o esquema de usuários.
- Chromium: novo logo, criação, código de ativação, primeira troca de senha, operador com controles restritos, logout sem manter a tela privilegiada, formulário Google e chave não retornada. Desktop e celular sem erros de JavaScript no fluxo final.

Não executado: publicação/autorização real do Apps Script na conta Google do usuário, consulta autenticada da planilha real, ensaio de cotas Google, execução nativa desta versão no Windows ou Raspberry e homologação física. A URL e a chave mostradas nas capturas são de demonstração; a sincronização permanece desativada até configurar a implantação real.

O serviço Python em `platform_service/` é uma alternativa opcional testada em memória. A opção principal solicitada pelo usuário é **Google Planilhas + Apps Script**, sem VPS.
