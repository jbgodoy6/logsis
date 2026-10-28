package br.com.sistel.logsis;

import android.net.Network;
import org.json.JSONObject;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** Password and short-lived bearer live in memory only, never preferences. */
public final class TechnicianAuth {
    private volatile String token="";
    private volatile long expires;
    private volatile Network internet;
    private volatile boolean localBound;
    public void internet(Network network){internet=network;}
    public void localBound(boolean value){localBound=value;}
    public void clear(){token="";expires=0;}
    public boolean hasSession(){return !token.isEmpty()&&System.currentTimeMillis()<expires;}
    public static boolean configured(){return validEndpoint(BuildConfig.TECH_AUTH_URL);}
    static boolean validEndpoint(String value){
        try { URL url=new URL(value);
            return "https".equals(url.getProtocol())&&"script.google.com".equals(url.getHost())
                    &&url.getUserInfo()==null&&url.getPort()==-1
                    &&url.getPath().matches("/macros/s/[A-Za-z0-9_-]+/exec")
                    &&url.getQuery()==null&&url.getRef()==null;
        }catch(Exception e){return false;}
    }
    public String login(String user,String password) throws Exception {
        clear();
        JSONObject result=post(new JSONObject().put("action","login").put("login",user).put("password",password));
        String received=result.getString("token");long end=result.getLong("expires");
        if(!received.matches("[a-f0-9]{64}")||end<=System.currentTimeMillis()||end>System.currentTimeMillis()+900000)
            throw new IllegalArgumentException("Autorização inválida.");
        token=received;expires=end;return result.optString("name",user);
    }
    public synchronized boolean verify(){
        if(!hasSession()){clear();return false;}
        try {authorized("verify");return true;}
        catch(Exception e){clear();return false;}
    }
    public JSONObject authorized(String action) throws Exception {
        if(!hasSession())throw new IllegalStateException("Entre novamente na área técnica.");
        return post(new JSONObject().put("action",action).put("token",token));
    }
    public JSONObject download(String id) throws Exception {
        if(!hasSession())throw new IllegalStateException("Entre novamente na área técnica.");
        return post(new JSONObject().put("action","bin").put("fileId",id).put("token",token));
    }
    private JSONObject post(JSONObject body) throws Exception {
        if(!configured())throw new IllegalStateException("O serviço de técnicos ainda precisa ser publicado pelo administrador.");
        Network data=internet;
        if(localBound&&data==null)throw new IllegalStateException("É necessária internet móvel para validar o técnico durante a conexão ao equipamento.");
        URL url=new URL(BuildConfig.TECH_AUTH_URL);boolean sendBody=true;
        for(int redirects=0;redirects<4;redirects++){
            HttpURLConnection connection=(HttpURLConnection)(data==null?url.openConnection():data.openConnection(url));
            connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(15000);connection.setReadTimeout(20000);
            connection.setUseCaches(false);
            try {
                if(sendBody){connection.setRequestMethod("POST");connection.setDoOutput(true);
                    connection.setRequestProperty("Content-Type","application/json; charset=utf-8");
                    byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);
                    connection.setFixedLengthStreamingMode(bytes.length);
                    try(java.io.OutputStream out=connection.getOutputStream()){out.write(bytes);}
                }
                int status=connection.getResponseCode();
                if(status==302||status==303){
                    URL next=new URL(url,connection.getHeaderField("Location"));
                    if(!"https".equals(next.getProtocol())||next.getUserInfo()!=null||next.getPort()!=-1
                            ||!(next.getHost().equals("script.google.com")||next.getHost().equals("script.googleusercontent.com")))
                        throw new IllegalStateException("Redirecionamento de autorização recusado.");
                    url=next;sendBody=false;continue;
                }
                if(status!=200)throw new IllegalStateException("Serviço de autorização indisponível.");
                byte[] response;
                try(InputStream input=connection.getInputStream()){
                    java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] b=new byte[8192];int n;
                    while((n=input.read(b))!=-1){if(out.size()+n>3*1024*1024)throw new IllegalStateException("Resposta inválida.");out.write(b,0,n);}response=out.toByteArray();
                }
                JSONObject result=new JSONObject(new String(response,StandardCharsets.UTF_8));
                if(!result.optBoolean("ok",false))throw new IllegalStateException(result.optString("message","Acesso não autorizado."));
                if(!BuildConfig.TECH_REGISTRY_ID.equals(result.optString("registryId")))throw new IllegalStateException("Cadastro técnico não corresponde a este aplicativo.");
                return result;
            }finally{connection.disconnect();}
        }
        throw new IllegalStateException("Resposta de autorização inválida.");
    }
}
