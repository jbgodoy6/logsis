package com.energycube.dmax;
import java.net.URI;

/** Shared origin rules: no credentials, custom ports, external schemes or query handoffs. */
public final class Policy {
 public static final String HOME="https://app.dmax.local/";
 public static final String DEFAULT_PLATFORM="https://script.google.com/macros/s/AKfycbwVIEPb4XCepVpb8si8tP3l-Z3H_PXBl5weM3kBcoop5njGpdeDDIar6xQc6E4gQ6JAvg/exec";
 private static URI secure(String value){try{URI u=new URI(value);return "https".equals(u.getScheme())&&u.getUserInfo()==null&&(u.getPort()==-1||u.getPort()==443)?u:null;}catch(Exception e){return null;}}
 public static boolean platform(String value){URI u=secure(value);return u!=null&&"script.google.com".equals(u.getHost())&&u.getPath().matches("/macros/s/[A-Za-z0-9_-]+/exec")&&u.getRawQuery()==null&&u.getRawFragment()==null;}
 public static boolean googleResult(String value){URI u=secure(value);return u!=null&&"script.googleusercontent.com".equals(u.getHost())&&u.getRawFragment()==null;}
 public static String clientOrigin(String value){URI u=secure(value);if(u==null||u.getHost()==null||!u.getHost().matches("[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.trycloudflare\\.com")||u.getHost().equals("api.trycloudflare.com")||u.getHost().equals("www.trycloudflare.com"))return null;return "https://"+u.getHost();}
 public static boolean ticket(String value){URI u=secure(value);return u!=null&&clientOrigin(value)!=null&&"/remote/sso".equals(u.getPath())&&u.getRawQuery()==null&&u.getRawFragment()!=null&&u.getRawFragment().matches("ticket=[a-f0-9]{64}");}
 public static boolean sameClient(String value,String origin){String actual=clientOrigin(value);return origin!=null&&origin.equals(actual);}
 private Policy(){}
}
