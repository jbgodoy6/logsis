package br.com.sistel.logsis;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;

/** Navigation rules independent from Android, also exercised by the desktop test. */
public final class NavigationPolicy {
    public enum Destination { INTERNAL, EXTERNAL, BLOCKED }
    private NavigationPolicy() {}

    public static Destination classify(String value) {
        if (value == null || value.length() > 16384) return Destination.BLOCKED;
        try {
            URI uri = new URI(value);
            String host = uri.getHost();
            if (!"https".equalsIgnoreCase(uri.getScheme()) || host == null
                    || uri.getRawUserInfo() != null) return Destination.BLOCKED;
            host = host.toLowerCase(Locale.ROOT);
            boolean ownHost = host.equals("logsis.com.br") || host.endsWith(".logsis.com.br");
            if (ownHost && (uri.getPort() == -1 || uri.getPort() == 443)) {
                return Destination.INTERNAL;
            }
            return Destination.EXTERNAL;
        } catch (URISyntaxException | IllegalArgumentException exception) {
            return Destination.BLOCKED;
        }
    }
}
