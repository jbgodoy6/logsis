package br.com.sistel.logsis;

import java.net.URI;

/** The equipment browser accepts only the local LogSis origin. */
public final class DevicePolicy {
    public static final String HOME = "http://192.168.4.1/";
    public static final String SSID_PREFIX = "LOGSIS";
    public static final String WIFI_PASSWORD = "12345678910";
    public static final String DEVICE_USER = "admin";
    public static final String DEVICE_PASSWORD = "12345678910";
    private DevicePolicy() {}
    public static boolean local(String value) {
        try {
            URI u = new URI(value);
            return "http".equalsIgnoreCase(u.getScheme())
                    && "192.168.4.1".equals(u.getHost()) && u.getRawUserInfo() == null
                    && (u.getPort() == -1 || u.getPort() == 80);
        } catch (Exception e) { return false; }
    }
    public static boolean passiveAsset(String value,String method,boolean mainFrame){
        if(mainFrame||!"GET".equals(method)||!local(value))return false;
        try {
            URI uri=new URI(value);String path=uri.getRawPath();
            return uri.getRawQuery()==null&&path!=null&&path.indexOf('%')<0
                    &&path.toLowerCase(java.util.Locale.ROOT).matches(".*\\.(css|js|png|jpg|jpeg|svg|ico|gif|woff|woff2|ttf)$");
        }catch(Exception e){return false;}
    }
}
