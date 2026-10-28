package br.com.sistel.logsis;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.wifi.WifiManager;
import android.net.wifi.WifiNetworkSpecifier;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.PatternMatcher;
import android.provider.Settings;

/** Only the equipment WebView uses the process Wi-Fi route. Authorization
 * requests always use an explicitly retained Internet/mobile Network. */
public final class DeviceConnection {
    public interface Listener {void connected();void failed(String message);}
    private final Activity activity;
    private final TechnicianAuth auth;
    private final ConnectivityManager manager;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private ConnectivityManager.NetworkCallback wifiCallback,cellCallback;
    private Network previous,local,mobile;
    private boolean closed;
    public DeviceConnection(Activity activity,TechnicianAuth auth){
        this.activity=activity;this.auth=auth;manager=(ConnectivityManager)activity.getSystemService(Context.CONNECTIVITY_SERVICE);
    }
    public static String permission(){return Build.VERSION.SDK_INT>=33?Manifest.permission.NEARBY_WIFI_DEVICES:Manifest.permission.ACCESS_FINE_LOCATION;}
    public static String[] permissions(){return Build.VERSION.SDK_INT>=33?new String[]{Manifest.permission.NEARBY_WIFI_DEVICES}:
            new String[]{Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION};}
    public boolean permissionGranted(){return activity.checkSelfPermission(permission())==PackageManager.PERMISSION_GRANTED;}
    public void prepareInternet(){if(!closed){auth.internet(mobile!=null?mobile:manager.getActiveNetwork());requestMobile();}}
    public void connect(Listener listener){
        if(closed||!auth.hasSession()){listener.failed("Entre novamente na área técnica.");return;}
        if(!permissionGranted()){listener.failed("Autorize a conexão Wi-Fi para continuar.");return;}
        disconnectWifi();previous=manager.getBoundNetworkForProcess();prepareInternet();
        if(Build.VERSION.SDK_INT<29){
            Network network=manager.getActiveNetwork();
            WifiManager wifi=(WifiManager)activity.getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            String ssid=wifi.getConnectionInfo().getSSID().replace("\"","");
            NetworkCapabilities caps=network==null?null:manager.getNetworkCapabilities(network);
            if(ssid.startsWith(DevicePolicy.SSID_PREFIX)&&caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))bind(network,listener);
            else {activity.startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));listener.failed("Selecione uma rede LOGSIS nas configurações, volte e toque em Conectar.");}
            return;
        }
        WifiNetworkSpecifier specifier=new WifiNetworkSpecifier.Builder()
                .setSsidPattern(new PatternMatcher(DevicePolicy.SSID_PREFIX,PatternMatcher.PATTERN_PREFIX))
                .setWpa2Passphrase(DevicePolicy.WIFI_PASSWORD).build();
        NetworkRequest request=new NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).setNetworkSpecifier(specifier).build();
        wifiCallback=new ConnectivityManager.NetworkCallback(){
            @Override public void onAvailable(Network network){if(!closed)bind(network,listener);}
            @Override public void onUnavailable(){if(!closed)listener.failed("Conexão cancelada ou nenhuma rede LOGSIS disponível.");}
            @Override public void onLost(Network network){if(network.equals(local)){disconnectWifi();if(!closed)listener.failed("Conexão com o equipamento perdida.");}}
        };
        try{manager.requestNetwork(request,wifiCallback,handler,45000);}
        catch(SecurityException|IllegalArgumentException e){disconnectWifi();listener.failed("Não foi possível solicitar o Wi-Fi. Confira as permissões e o Wi-Fi do celular.");}
    }
    private void requestMobile(){
        if(cellCallback!=null)return;
        cellCallback=new ConnectivityManager.NetworkCallback(){
            @Override public void onAvailable(Network network){if(!closed){mobile=network;auth.internet(network);}}
            @Override public void onLost(Network network){if(!closed&&network.equals(mobile)){mobile=null;auth.internet(null);}}
        };
        try{manager.requestNetwork(new NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR)
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(),cellCallback,handler);}
        catch(SecurityException e){cellCallback=null;}
    }
    private void bind(Network network,Listener listener){
        if(closed)return;
        if(!manager.bindProcessToNetwork(network)){listener.failed("Não foi possível direcionar a conexão ao equipamento.");return;}
        local=network;auth.localBound(true);listener.connected();
    }
    private void disconnectWifi(){
        if(local!=null){manager.bindProcessToNetwork(previous);local=null;auth.localBound(false);}
        if(wifiCallback!=null){try{manager.unregisterNetworkCallback(wifiCallback);}catch(IllegalArgumentException ignored){}wifiCallback=null;}
    }
    public void close(){
        closed=true;disconnectWifi();
        if(cellCallback!=null){try{manager.unregisterNetworkCallback(cellCallback);}catch(IllegalArgumentException ignored){}cellCallback=null;}
        auth.internet(null);
    }
}
