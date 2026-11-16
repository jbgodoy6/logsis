# Validação de 16/11/2026

Conjunto: **Windows 1.3.0**, **Raspberry 0.15.0** e **Apps Script `central-sso-devices-2`**. [Hashes e limites](../releases/versions.json) · [Instalação e operação](release-v0150.md).

| Verificação | Resultado |
| --- | --- |
| Python/controlador | 119 testes passaram, zero falhas/ignorados, Python 3.12/Linux x86-64. Autenticação, sessões, SSO, senha inicial/troca, APIs, isolamento comercial, OCPP, aprendizagem AC/DC e persistência, controle de demanda, proxy, cadastro remoto, instalação/importação/desinstalação e empacotamento. |
| LAN/.NET | Compilação e testes passaram: endereço padrão, mDNS, Host/CSRF, cookies, perfis, revogação, configurações e persistência. |
| Central/Chromium | Passou com plataforma fictícia: troca obrigatória no primeiro acesso, clientes/SSO, equipamentos, usuários sem senha personalizada, permissões, sessões isoladas, simulação até SOC 100%, layout e rolagem. |
| Raspberry/Chromium | SSO passou com Google fictício: sem segundo formulário de senha, fragmento removido, cookie HttpOnly e repetição do passe recusada. |
| Apps Script | Contrato completo com serviços Google simulados passou: cadastro com D/E/G, senha inicial, reset/troca e rotação de sessão, permissões, confirmação de gravação, passe de uso único vinculado ao equipamento, expiração/logout, migração com backup e preservação dos prazos pendentes. Contratos adicionais de diagnóstico, confirmação/trace e diálogo de senha também passaram. |
| MSI | 372 arquivos extraídos conferidos por SHA256; assets iguais ao código. Core/WindowsDesktop/ASP.NET 10.0.15 incluídos, win-x64, sem runtime externo, CustomAction ou serviço. |
| ZIP Raspberry | ZIP íntegro e 151 entradas do manifesto conferidas (152 arquivos contando o manifesto). Code.gs, aprendizagem e módulos SSO/senha iguais ao código. Wheels e cloudflared ARM64 conferidos pelo empacotador. |
| Ciclo de instalação | Arquivos temporários e SQL reais; UID, systemctl e pip simulados. Dados preservados nos caminhos de importação/desinstalação previstos. |

## Limites

Não houve execução do MSI em Windows real, teste pelo Defender, assinatura Authenticode ou execução física ARM64. A aprendizagem foi validada com telemetria e transportes simulados; mínimos elétricos exigem comissionamento e homologação no carregador real. O ZIP não contém assinatura para atualização automática: siga a instalação manual. Não há garantia de aceitação pelo antivírus.

Não foi alterada a implantação Google, planilha, propriedades nem instalação do usuário. A atualização do Code.gs deve ser publicada na mesma implantação /exec para ativar as novas operações. A migração da coluna E cria backup; não preencha E com situação antes de executá-la. O relato anterior do usuário de funcionamento refere-se ao conjunto anterior, não constitui validação física desta entrega.

As distribuições substituídas foram retiradas desta pasta, preservando histórico Git e branch anterior. O manifesto registra a origem do código e hashes dos arquivos finais.
