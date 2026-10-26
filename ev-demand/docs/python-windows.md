# Python no Windows — D-Max v0.2.1

O iniciador reconhece **Python 3.13 e 3.12**, nessa ordem, pelo Python Launcher. Não é necessário instalar 3.12 se já houver 3.13.

1. Extraia o ZIP em uma pasta gravável.
2. Execute `iniciar-windows.bat` dentro dessa pasta.
3. A primeira execução cria `.venv` e instala as dependências. A partir daí, o iniciador reutiliza esse ambiente.

Um `.venv` existente com versão diferente não é apagado ou substituído automaticamente. O iniciador informa a necessidade de preservar/renomear essa pasta antes de tentar novamente. Não copie `.venv` de outro sistema operacional.

## Diagnóstico do erro 1603 observado

O registro do Python 3.12 mostrou que `TARGETDIR` chegou corretamente na linha de comando do MSI, mas foi descartado pelo próprio Windows Installer:

```text
RestrictedUserControl = 1
Ignoring disallowed property TARGETDIR
The TARGETDIR variable must be provided when invoking this installer.
```

Também constaram `AlwaysInstallElevated=1` nas políticas de máquina e usuário e `EnableUserControl=0`. Esses dados explicam o descarte de propriedades nessa instalação. Não é ausência do argumento na chamada do D-Max ou erro de download. A revisão das políticas do Windows Installer, caso uma nova instalação ainda seja necessária, cabe à administração da máquina.

Para o D-Max, a solução adotada foi aproveitar o Python 3.13 já instalado, sem editar políticas, Registro ou proteções do Windows. O aviso de Launcher mais recente foi secundário: a falha fatal ocorreu no componente principal do Python.

## Validação

- Os 44 testes passaram em Linux com Python 3.13.16, além da validação anterior em 3.12.
- As dependências fixadas tiveram seus wheels CPython 3.13/Windows x64 baixados com sucesso para verificação de disponibilidade.
- O arquivo `.bat` e a execução nativa do aplicativo no Windows ainda precisam ser verificados no computador de destino; não foi feita afirmação de teste nativo em Windows.

Execução manual, em um terminal aberto **na pasta do D-Max**:

```powershell
py -3.13 -m venv .venv313
.\.venv313\Scripts\python.exe -m pip install -r requirements.lock
.\.venv313\Scripts\python.exe run.py
```

Essa alternativa mantém o ambiente `.venv` existente intacto e usa uma pasta separada. Execute as linhas na ordem e continue apenas se a anterior concluir sem erro.
