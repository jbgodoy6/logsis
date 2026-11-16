# Versões mantidas — validação de 16/11/2026

Conjunto atual: **Windows 1.2.1**, **Raspberry 0.14.2** e **Apps Script `sheet-user-write-1`**. Arquivos e hashes completos em [versions.json](../releases/versions.json).

## Evidência executada nesta revisão

| Componente | Resultado |
| --- | --- |
| MSI Windows | SHA256 externo confirmado; 372 arquivos extraídos conferidos contra o manifesto. Core, WindowsDesktop e ASP.NET 10.0.15 incluídos; sem exigência de runtime externo, CustomAction ou serviço. Assemblies iguais à publicação Windows anteriormente compilada. |
| Núcleo Windows/LAN | Testes existentes passaram: transporte, redirecionamentos sem replay de credenciais, simulação, mDNS, endereço padrão, Host/CSRF, cookies, perfis, revogação e persistência. |
| Navegador da central | Chromium passou com transporte fictício: logo, login/recarga, clientes, perfis, verificador, sessões isoladas, simulação sem comandos, parada em 100%, layout e rolagem. |
| Raspberry/Python | **55 testes passaram, 0 falhas, 0 ignorados**, em Python 3.12/Linux x86-64, com dependências instaladas pelo lock e hashes. Módulos: access, v0140, requested_changes, pi_deploy, pi_scripts, remote_registry, remote_clients e desktop_runtime_package. |
| Instalação Raspberry | Instalação, importação, desinstalação preservando dados, reinstalação e limpeza confirmada passaram em estrutura temporária. UID, systemctl e pip foram simulados pelo teste; SQL e operações de arquivo executaram de fato. |
| Navegador do controlador | Fixture da UI Python passou no Chromium: atualização da curva, pico em CSV/PDF, login/logout comercial, isolamento entre usuários, recusa de rotas de hardware e ausência de requisições externas/erros JavaScript. |
| Apps Script | Contratos executaram o Code.gs completo com serviços Google fictícios. Passaram autenticação, snapshot/update, gerenciamento, revogações, identidades, API desktop, criação com ID automático e D/E/G preenchidas, credenciais pendentes, validações de listas e confirmação de persistência. |
| Senha pela planilha | Testes de servidor e diálogo Chromium passaram: escrita só em G, preservação dos demais campos, contexto do editor, linha alterada durante a edição, confirmação da gravação, PBKDF2 verificado independentemente e ausência de senha no envio à função de gravação. O canal Google do diálogo foi simulado. |
| Pacote Raspberry | ZIP e manifesto interno íntegros, 147 arquivos; wheels conferidos contra requirements.lock pelo empacotador; binário cloudflared ARM64 conferido contra o hash registrado. |

O usuário também confirmou funcionamento da instalação e da planilha durante esta conversa. Isso é um relato de operação, separado dos testes executados pelo agente. Não identifica com certeza qual MSI estava instalado no computador no momento desse relato.

## Sincronização das distribuições

O ZIP Raspberry anteriormente incluía uma revisão antiga de Code.gs. Ele foi reconstruído com o empacotador existente, reaproveitando apenas os wheels e o cloudflared previamente conferidos. A comparação entre os ZIPs demonstrou mudanças exclusivamente em `google-apps-script/Code.gs` e `SHA256SUMS.txt`. Não houve alteração no código de controle, requisitos, chaves ou dados do Raspberry. O hash externo do ZIP foi regenerado.

O MSI 1.2.1 permaneceu byte a byte igual ao distribuído anteriormente. O Apps Script atual foi mantido sem alterações de lógica nesta revisão. A cópia dele dentro do ZIP Raspberry tem o mesmo SHA256 do arquivo fonte.

## Limites

Não houve execução do MSI em Windows real, teste Defender, assinatura Authenticode, boot em Raspberry físico ou teste com carregadores/medidores reais. O ZIP Raspberry é de instalação manual e não contém assinatura exigida pelo atualizador automático. SHA256 confirma integridade; não substitui essa assinatura. A implantação Google e os dados reais não foram alterados ou consultados pelo agente nesta validação.

## Limpeza autorizada

Foram removidos **32 artefatos antigos** da árvore atual de `ev-demand/releases`, conservando MSI/ZIP atuais, seus hashes, auditoria e manifesto de arquivos do MSI. A lista exata removida está em versions.json. O histórico Git e as branches/tags permanecem disponíveis para recuperação. Código, testes e documentos necessários à reprodução foram preservados; nenhuma instalação ou planilha foi apagada.
