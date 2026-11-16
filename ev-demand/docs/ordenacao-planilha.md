# Ordenação alfabética da planilha

Revisão Apps Script: `alphabetical-directory-1`, compatível com Central Windows 1.3.0 e Raspberry 0.15.0.

Usuarios: nome completo na coluna B. DMax_Remoto: nome da instalação na coluna B. Empates usam o ID na coluna A. A ordenação usa o mecanismo nativo da planilha (conforme sua localidade), movimenta a linha completa até a última coluna usada e mantém o cabeçalho. Não muda o formato das abas nem migra colunas.

Depois de copiar Code.gs no projeto existente, salve e publique uma nova versão na mesma implantação /exec. Recarregue a planilha e execute D-Max → Ordenar usuários e clientes de A a Z para organizar os cadastros existentes. Não é necessário reinstalar Windows ou Raspberry para esta melhoria.

Novos salvamentos de usuário pelo Windows/Raspberry e de equipamento pela central, além dos informes remotos aceitos, ordenam a respectiva aba depois das confirmações de gravação. Edições manuais nas linhas de dados também ordenam pelo gatilho simples onEdit; escritas de outros scripts não disparam esse gatilho. Se o script estiver ocupado, a edição manual permanece salva e o menu permite repetir a ordenação.

A classificação movimenta linhas: um diálogo antigo de senha que ainda referencia uma linha deslocada será recusado pela proteção de identidade existente. Nesse caso feche o diálogo, selecione novamente o usuário e reabra.

Validação local: contrato de ordenação com nomes acentuados, desempate por ID, integridade das linhas/colunas extras, cabeçalhos, edição e lock; contratos de confirmação da gravação, trace e diagnóstico passaram. Nenhuma planilha ou implantação real foi modificada pelo agente. Os pacotes MSI/ZIP publicados continuam contendo a revisão original de sua entrega; este Code.gs é uma atualização separada.
