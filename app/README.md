# LogSis Android — área técnica 1.1.0

O desenvolvimento atual acrescenta conexão local ao equipamento, biblioteca de 17 controladores e geração **somente de BIN**, sem exportador Grafana. A área técnica exige ativação do serviço de autorização e permanece bloqueada até essa etapa.

[Funcionamento da versão 1.1](README_TECNICO.md) · [Ativar o serviço da planilha](backend/README.md)

## Histórico: base 1.0.0

As instruções e permissões abaixo descrevem a versão original 1.0, anterior à área técnica.

[Baixar APK de teste](../LOGSIS_ANDROID_1_0_TESTE.apk) · [Projeto-fonte](../LOGSIS_APP_ANDROID_FONTE_1_0.zip) · [Identidade visual aprovada](identidade/LOGSIS_PROPOSTA_VISUAL.png)

Aplicativo Android nativo do Logsis, com símbolo próprio, azul/amarelo e marca Grupo Sistel. A tela de abertura tem o botão **Acessar sistema**, que abre **https://logsis.com.br/** no próprio aplicativo. A autenticação pertence ao site existente: não há outro cadastro, senha embutida ou formulário nativo que imite o login.

## Instalar para testar

1. Em um celular com **Android 8.0 ou superior**, baixe `LOGSIS_ANDROID_1_0_TESTE.apk`.
2. Abra o arquivo. Se o Android solicitar, permita a instalação por esse navegador e toque em **Instalar**.
3. Abra **Logsis**, toque em **Acessar sistema** e entre com sua conta do site.

Este APK é assinado com certificado de avaliação para instalação direta. Não é uma publicação da Google Play nem usa a chave definitiva da empresa. A chave privada de avaliação fica fora do repositório e do ZIP; para atualizações estáveis/produção, o proprietário deverá configurar e guardar sua própria chave de assinatura.

## O que esta base entrega

- Tela de entrada, ícone adaptativo e identidade Logsis/Grupo Sistel.
- Navegação interna HTTPS no domínio Logsis e seus subdomínios; links HTTPS externos abrem no navegador do aparelho.
- Menu com atualizar, página inicial, abrir no navegador, sobre e limpar dados de acesso.
- Cookies e armazenamento do site administrados pelo WebView do Android, conforme as regras/expiração do servidor. O app não guarda a senha por conta própria.
- Erro de conexão com tentativa novamente, carregamento e botão voltar.
- Limpeza local da sessão, armazenamento e cache, recriando o WebView para descartar a página e o histórico anteriores. Não revoga sessões em outros aparelhos nem substitui um logout no servidor.
- Seleção de arquivos pelo seletor do Android, sem acesso geral aos arquivos do aparelho. Downloads são encaminhados ao navegador e podem exigir autenticação nele.
- Somente a permissão de Internet; sem câmera, contatos, localização, leitura de SMS ou biblioteca de rastreamento.

A interface do sistema após entrar é a do próprio site. Não foram criadas plantas, telas de login falsas ou leituras simuladas no aplicativo.

## Validação e limite atual

O ambiente de desenvolvimento teve o túnel de acesso a `logsis.com.br`/`www.logsis.com.br` negado pelo proxy da própria infraestrutura (**403 no CONNECT**). Portanto, não foi possível confirmar a disponibilidade do servidor, as rotas de login, um login real, SSO ou os dashboards de uma conta. Isso não prova que o site esteja fora do ar.

A compilação Android, o lint e os testes nativos em Robolectric são registrados em `VALIDACAO_ANDROID_1_0.json`. Robolectric usa Android simulado na JVM: não equivale a teste em aparelho físico. A política de URL tem 19 verificações próprias. O APK precisa de teste de acesso com sua conta em um celular com conexão ao site.

HTTPS é obrigatório. Certificados inválidos são recusados; o aplicativo não desativa TLS, não permite conteúdo HTTP misturado e não cria ponte JavaScript/nativa. Sessões não entram em backup e URLs de navegação/autenticação não são serializadas para restaurar uma tela após encerramento do processo.

Notificações de alarmes em segundo plano ainda não fazem parte desta base; precisam de integração com o sistema/servidor.

## Desenvolver

O projeto completo fica em `android/`. Use **JDK 17**, Android SDK **35**, Build Tools 35 e Android Studio compatível com AGP 8.7.3. Dependências de teste são JUnit/Robolectric; o aplicativo usa os componentes nativos do Android, sem framework web embarcado ou biblioteca de publicidade.

```sh
cd android
./gradlew assembleRelease lintRelease testReleaseUnitTest
./tools/check_navigation.sh
```

No Windows use `gradlew.bat`. Configure o SDK pelo Android Studio ou `local.properties`, sem versionar caminhos da sua máquina. `assembleRelease` gera um APK **sem assinatura**; assine com a chave apropriada antes de instalar/distribuir. O wrapper confere o SHA-256 do Gradle 8.9. Nenhuma configuração de proxy ou certificado do ambiente de desenvolvimento é incluída no app.

Pontos de entrada:

- `app/build.gradle`: versão, SDK e `SITE_URL`.
- `MainActivity.java`: abertura, WebView, menu, estados de conexão e sessão.
- `NavigationPolicy.java`: limites de navegação e esquemas permitidos.
- `drawable-nodpi/`: artes derivadas da identidade visual aprovada.
- `MainActivityTest.java`: fluxos de atividade em Android simulado.

O código não publica o app em loja, não altera o site ou o banco de dados e não requer credenciais de produção para compilar.
