# D-Max Android 1.0.0

Central Android independente do servidor Windows, para Android 10 ou superior (API 29), com Android System WebView atualizado. Conecta por HTTPS diretamente à implantação Google existente; os equipamentos remotos são Raspberry com acesso Cloudflare ativo. Não cria um servidor HTTP local.

## Instalar e usar

Instale `D-Max-Android-1.0.0.apk` no celular. Se o Android solicitar autorização para instalar por essa origem, autorize somente o navegador/gerenciador usado para este APK. Não desative Play Protect ou antivírus. A aplicação não está publicada na Play Store.

A URL /exec existente já vem configurada. Entre com sua conta da planilha. Novas contas/redefinições usam 12345678 e exigem troca da senha pessoal. A central oferece clientes, busca, simulação isolada e, para desenvolvedor, usuários, equipamentos e configurações da plataforma. A URL da plataforma pode ser alterada por desenvolvedor com confirmação de senha e é salva apenas neste Android. Nome/porta do servidor Windows não se aplicam.

Ao tocar em Acessar cliente, o aplicativo obtém um passe de 60 segundos e abre o D-Max dentro de uma WebView separada, sem passar senha ou token da central à página remota. O botão Voltar à central e o botão Voltar do Android fecham a tela do cliente e preservam a central. Fechar essa tela não é um comando para interromper recargas. O controle continua no Raspberry. Comercial permanece sujeito à demonstração/permissões existentes no controlador.

Requer Apps Script com `desktop_open_client`, `desktop_change_password`, `desktop_devices` e `desktop_save_device` (revisões central-sso-devices-2 ou alphabetical-directory-1) e Raspberry 0.15.0 para entrada automática. Equipamentos antigos precisam ser atualizados; não há fallback silencioso para controle ou autenticação diferente. A API Google continua validando os perfis; esconder botões não é o controle de autorização.

Downloads de relatórios do cliente são enviados para Downloads do Android com a sessão daquele cliente. Formulários de envio de arquivo usam o seletor do Android. Navegação para outros domínios/esquemas é bloqueada na tela do cliente; as funções D-Max do próprio cliente continuam internas. Links externos como Grafana/outros sites não são navegados por essa WebView.

A central exige internet para login/cadastros e acesso remoto; o computador Windows pode ficar desligado. Encerrar o app perde a sessão local e a simulação. Rotação de tela preserva as WebViews; se o Android encerrar o processo, será necessário novo login. O app tenta revogar o token ao encerrar normalmente; em encerramento forçado vale a expiração da plataforma. Cookies são limpos no início, troca de conta, saída e destruição normal da atividade. Nenhum token é salvo em preferências ou entregue ao JavaScript. A única preferência persistida é a URL pública /exec. A central não registra senhas/formulários nos logs.

## Compilar

Ferramentas: Java 21, Eclipse ECJ 3.39.0, Android SDK platform 35 e build-tools 35.0.0, Python 3. Sem Gradle ou dependências Android de terceiros. O SDK e ECJ ficam fora do repositório. `prepare_assets.py` adapta as telas existentes de `lan/assets` para o transporte Android, sem alterar os arquivos do Windows. Não edite os assets gerados em build.

Defina `ANDROID_HOME`, `ECJ_JAR`, `DMAX_ANDROID_KEYSTORE` e `DMAX_ANDROID_PASSWORD_FILE`, então execute:

```bash
python3 android/build.py
```

O keystore PKCS12 deve conter o alias `dmaxandroid`. A senha do arquivo protege o keystore e a chave. Mantenha ambos fora do repositório, com acesso restrito e backup seguro. A assinatura é específica desta distribuição e deve ser preservada para futuras atualizações do mesmo aplicativo; perder a chave exige outro pacote ou reinstalação. Não publique a chave/senha no Git. A compilação produz APK, SHA256 e verificação da assinatura. Nenhum certificado privado é incluído nos assets ou APK.

## Validar

`android/tests/SessionTest.java`: origens, sessão, troca inicial, rotação de token, dispatch e configurações por desenvolvedor, com transporte simulado. `TransportTest.java`: transporte HTTP interceptado em memória para verificar ausência de replay de credenciais, bloqueio de redirecionamentos externos e 307. Compile estes testes com ECJ e org.json 20240303 (somente teste JVM; o APK usa org.json do Android).

`android/tests/browser.cjs`: Chromium com ponte nativa fictícia para primeira troca, clientes, membros, equipamentos, configurações e simulação. Sirva android/build/assets na porta loopback 8795 e execute `node android/tests/browser.cjs`.

APK compilado e assinatura/manifesto/assets conferidos. Esses testes não substituem execução no Android real: não foi executado em celular ou emulador nesta entrega. Validar no aparelho: instalação, login real, SSO, botão nativo de retorno, rotação, downloads/uploads e reconexão. Nenhuma implantação Google, planilha ou instalação Raspberry foi alterada pelo agente.
