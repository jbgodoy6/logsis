# Diagnóstico do código 422 na central

A resposta antiga ocultava a causa em dois pontos: `portalReply_` no Apps Script e `Platform.Call` no Windows. O texto sobre Usuarios não comprovava problema nos dados nem identificava qual consulta falhou.

Esta correção acrescenta códigos fixos de diagnóstico, sem retornar exceções brutas ou credenciais:

| Diagnóstico | Etapa identificada |
| --- | --- |
| `directory_not_prepared` | A implantação não tem `directory.unified=1`; a existência da aba não substitui essa propriedade. |
| `users_headers` | Cabeçalhos ausentes ou incompatíveis em Usuarios. |
| `users_record` | Validação completa do cadastro, incluindo identidade/perfil, situação/verificador, datas e limites. |
| `remote_headers` | Cabeçalhos do diretório remoto. |
| `remote_record` | Registros/limites do diretório remoto. |
| `validation` | Outra recusa de validação; não permite atribuir a causa a Usuarios. |

O Windows mostra a operação e o código, por exemplo `[desktop_clients; código 422]`. Respostas antigas sem diagnóstico continuam aceitas, com texto que informa a falta de evidência específica. Mensagens arbitrárias do servidor não são exibidas. Conflitos históricos continuam como 409; falha de credencial/sessão continua como 401.

GET na implantação passa a anunciar `desktop_protocol`, `desktop_actions` e `diagnostics_version`, sem acessar planilhas ou propriedades. O banner antigo com `version: 1.0` não comprova suporte às operações desktop.

## Validação local

Na pasta `ev-demand`:

```sh
node tests/desktop_diagnostics_contract.cjs
node tests/apps_script_contract.cjs google-apps-script/Code.gs
dotnet run --project desktop/tests/SimulationTests.csproj -c Release
dotnet run --project lan/tests/DMaxLan.Tests.csproj -c Release
```

Os testes usam somente serviços fictícios. A nova suíte cobre preparação ausente, cabeçalhos, classificação de registros, compatibilidade com respostas antigas, identificação da operação e proteção contra exposição de detalhes.

## Situação da implantação informada

Em 16/11/2026, a consulta GET à URL informada foi impedida pelo proxy do ambiente (`CONNECT 403`, antes de alcançar o Google), inclusive na tentativa autorizada fora do sandbox. Não houve inspeção da planilha ou confirmação da versão publicada. Nenhum login real foi tentado: essa operação grava contadores/sessões.

Esta alteração não migra cadastros, não define `directory.unified`, não apaga identidades e não muda o protocolo Raspberry. A causa concreta do erro da instalação existente ainda precisa de resposta da implantação por operação. Não definir a propriedade manualmente para contornar o diagnóstico: a preparação deve preservar e validar as identidades existentes.

Aplicar esta correção em produção exige atualizar explicitamente o Apps Script e a central Windows; os arquivos locais não atualizam a implantação ou o MSI instalado. Avisar o responsável antes dessas atualizações, preservar a URL /exec, propriedades e planilha. Não houve publicação ou alteração da instalação nesta tarefa.
