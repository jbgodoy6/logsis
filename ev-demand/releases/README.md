# Distribuições atuais

- [Windows 1.3.0 — MSI com runtime](D-Max-Central-Rede-1.3.0-Completo.msi) · [SHA256](D-Max-Central-Rede-1.3.0-Completo.msi.sha256) · [Auditoria](D-Max-Central-Rede-1.3.0-Completo.audit.json).
- [Raspberry 0.15.0 — ZIP Linux ARM64](D-Max-Raspberry-0.15.0-SEM-ASSINATURA.zip) · [SHA256](D-Max-Raspberry-0.15.0-SEM-ASSINATURA.zip.sha256).
- [Android 1.0.0 — APK assinado, Android 10+](D-Max-Android-1.0.0.apk) · [SHA256](D-Max-Android-1.0.0.apk.sha256) · [Guia e limites](../android/README.md).
- [Apps Script — Code.gs](../google-apps-script/Code.gs), revisão `alphabetical-directory-1`.

[Instalação e novidades](../docs/release-v0150.md) · [Validação](../docs/versoes-validadas.md) · [Manifesto](versions.json).

Atualize os três componentes para usar acesso ao cliente sem repetir senha, equipamentos com situação na coluna E e troca obrigatória da senha inicial. O pacote Raspberry é para instalação manual, sem assinatura de atualização automática. O MSI inclui runtime; não exige .NET separado. Não houve instalação física ou validação pelo Defender pelo agente.

Somente as distribuições atuais são mantidas nesta pasta. As anteriores continuam no histórico e na branch estável anterior. Planilhas, propriedades e instalações existentes não foram alteradas.

Android conecta diretamente ao Google e ao Raspberry, sem servidor Windows. Primeira entrega com testes JVM/Chromium e verificação do APK; execução em aparelho/emulador ainda pendente. O arquivo D-Max-Android-1.0.0.audit.json registra a validação específica.
