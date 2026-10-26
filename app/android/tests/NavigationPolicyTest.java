import br.com.sistel.logsis.NavigationPolicy;
import static br.com.sistel.logsis.NavigationPolicy.Destination.*;

public final class NavigationPolicyTest {
    private static int assertions;
    private static void check(String url, NavigationPolicy.Destination expected) {
        assertions++;
        if (NavigationPolicy.classify(url) != expected) throw new AssertionError(url);
    }
    public static void main(String[] args) {
        check("https://logsis.com.br/", INTERNAL);
        check("https://www.logsis.com.br/login?x=1#top", INTERNAL);
        check("https://sistema.logsis.com.br:443/", INTERNAL);
        check("HTTPS://LOGSIS.COM.BR/", INTERNAL);
        check("https://logsis.com.br.evil.example/", EXTERNAL);
        check("https://evil-logsis.com.br/", EXTERNAL);
        check("https://logsis.com.br:8443/", EXTERNAL);
        check("https://example.com/", EXTERNAL);
        check("https://logsis.com.br@evil.example/", BLOCKED);
        check("http://logsis.com.br/", BLOCKED);
        check("javascript:alert(1)", BLOCKED);
        check("file:///data/data/app/cookies", BLOCKED);
        check("content://private/doc", BLOCKED);
        check("intent://logsis.com.br/", BLOCKED);
        check("data:text/html,hello", BLOCKED);
        check("https:///logsis.com.br", BLOCKED);
        check("https://logsis.com.br/\nmalformed", BLOCKED);
        check("not a url", BLOCKED);
        check(null, BLOCKED);
        System.out.println(assertions + " navigation checks passed");
    }
}
