# Desktop 1.1.0 — Completo, com runtime incluído

O usuário não quer instalar .NET Framework separadamente. A aplicação foi migrada do .NET Framework 4.8 para .NET 10 Windows Forms e publicada explicitamente como `SelfContained=true`, `RuntimeIdentifier=win-x64`, `RuntimeFrameworkVersion=10.0.15`.

## Instalação

Execute D-Max-Acesso-Desktop-1.1.0-Completo.msi no Windows 10/11 x64, no mesmo usuário da instalação anterior. O UpgradeCode foi preservado para atualizar 1.0/1.0.1. Após a instalação, abra o atalho D-Max Acesso Desktop. O MSI apenas instala, sem abrir a aplicação automaticamente.

Não precisa instalar .NET Framework, .NET Desktop Runtime, SDK ou Python separadamente. O runtime é privado da pasta do aplicativo; não muda os runtimes globais do Windows. Não é uma versão “sem .NET”: ela leva consigo os componentes necessários.

A URL, o login e as APIs são os mesmos da versão Desktop anterior. Não é necessário atualizar novamente o Code.gs se já aplicou a versão Desktop. O arquivo de preferências com a URL pública é preservado. Senhas e tokens continuam somente em memória.

## Alterações técnicas

- Runtime Microsoft.NETCore.App 10.0.15 e Microsoft.WindowsDesktop.App 10.0.15 incluídos integralmente na publicação; o runtimeconfig contém `includedFrameworks` e não `framework`/`frameworks` externos.
- Removidas referências a System.Web.Extensions e a ReferenceAssemblies do .NET Framework. Serialização migrada para System.Text.Json com conversão explícita para os mesmos tipos de dados das APIs existentes. Testes cobrem arrays, booleanos, objetos, números em pt-BR e Unicode.
- Modelo de simulação, permissões, gestão e isolamento comercial preservados. Testes de transporte verificam POST de senha em HTTPS e GET do resultado Google sem reenviar credenciais.
- Instalador sem RegLocator/LaunchCondition de .NET Framework 4.8. Sem instalação separada de pré-requisitos, serviços, scripts/CustomAction, mudanças de ambiente ou início automático.
- Distribuição multifile padrão; sem single-file packing, trimming ou ofuscação. O instalador usa gabinete MSI padrão e instala 228 arquivos, incluindo notas de licença.
- Hashes SHA-512 dos três pacotes NuGet Microsoft de runtime/host foram verificados no cache de restauração e registrados em desktop/runtime-packages.json. Licenças Microsoft e notas de terceiros seguem na pasta Licencas.

## Evidência

Compilação/publicação Release para win-x64 concluída. Os testes portáveis do núcleo/JSON/transporte passaram; três testes de empacotamento rejeitam runtime externo, arquivos de host ausentes e perda de recursos em subdiretórios. O MSI foi auditado e extraído; cada um dos 228 arquivos extraídos coincide com o manifesto SHA-256 do payload publicado. Os arquivos de runtime e host necessários estão presentes.

A execução de .NET 10 Windows Forms/Windows Installer e o Defender não estão disponíveis nesta máquina Linux. O teste de interface Mono da versão 1.0.1 não é apresentado como execução do novo runtime Windows. Não houve teste em computador do cliente nem alteração de planilha/Raspberry. O MSI e o executável da aplicação não possuem certificado Authenticode de publicação da empresa; não há garantia de aprovação pelo Defender/SmartScreen. Não são recomendadas exclusões ou desativação de proteção.
