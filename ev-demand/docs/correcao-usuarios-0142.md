# Correção do histórico de usuários no Apps Script

Atualize somente Code.gs. Não é necessário reinstalar o Raspberry.

O cadastro unificado identity.* prevalece sobre caches antigos user.* e account.* do mesmo ID antes da validação de logins. Isso inclui exclusões. Antes, um cache obsoleto podia causar 409 mesmo com um registro unificado autoritativo. Propriedades e chaves são preservadas; conflitos reais entre identidades continuam recusados.

Testes: regressão reproduzida antes da correção; exclusão de técnico, desenvolvedor e comercial; revogações persistentes; sincronizações repetidas; caches antigos; proteção contra reutilização de login e diagnóstico sem escrita.

Substitua Code.gs completo, salve e atualize a implantação existente com Nova versão, mantendo a URL. No D-Max, execute Configurações → Sincronizar agora.

A causa específica na planilha do usuário ainda precisa ser confirmada após aplicar. Se persistir 409, execute diagnosticarUsuarios no editor e consulte o registro. Essa função apenas lê cadastros e propriedades, sem registrar chaves ou verificadores. Não apague propriedades para contornar conflitos.
