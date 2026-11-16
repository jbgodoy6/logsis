# Distribuições atuais

- [Central Windows 1.2.1 — MSI com runtime](D-Max-Central-Rede-1.2.1-Diagnostico.msi) · [SHA256](D-Max-Central-Rede-1.2.1-Diagnostico.msi.sha256) · [Auditoria](D-Max-Central-Rede-1.2.1-Diagnostico.audit.json).
- [Raspberry 0.14.2 — ZIP Linux ARM64](D-Max-Raspberry-0.14.2-SEM-ASSINATURA.zip) · [SHA256](D-Max-Raspberry-0.14.2-SEM-ASSINATURA.zip.sha256).
- [Apps Script atual — Code.gs](../google-apps-script/Code.gs), revisão `sheet-user-write-1`.

[Relatório de validação](../docs/versoes-validadas.md) · [Manifesto das versões e hashes](versions.json).

O ZIP Raspberry foi atualizado apenas para incluir o Apps Script atual e seu manifesto de integridade. O controlador continua na versão 0.14.2; seus arquivos de aplicação não mudaram. O pacote continua sem assinatura para atualização automática: use o procedimento de instalação manual documentado. O nome “Diagnostico” do MSI foi preservado para manter o mesmo arquivo 1.2.1 já distribuído.

A limpeza removeu 32 arquivos de versões anteriores desta pasta. Não houve reescrita do histórico, exclusão de branches/tags, alteração de instalações, banco de dados, planilhas ou implantação Google. Notas de versões anteriores permanecem porque fazem parte da documentação e dos scripts de construção.
