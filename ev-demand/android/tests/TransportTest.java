package com.energycube.dmax;
import java.net.*;
import java.io.*;
import java.util.*;
import org.json.*;
public final class TransportTest {
 static class Connection extends HttpURLConnection {
  ByteArrayOutputStream sent=new ByteArrayOutputStream();int status;String destination,body;boolean inputRead;
  Connection(URL u,int status,String destination,String body){super(u);this.status=status;this.destination=destination;this.body=body;}
  public void connect(){}public void disconnect(){}public boolean usingProxy(){return false;}public OutputStream getOutputStream(){return sent;}public int getResponseCode(){return status;}public String getHeaderField(String key){return key.equals("Location")?destination:null;}public InputStream getInputStream(){inputRead=true;return new ByteArrayInputStream(body.getBytes(java.nio.charset.StandardCharsets.UTF_8));}
 }
 static List<Connection> calls=new ArrayList<>();static int mode=0;
 static void check(boolean v){if(!v)throw new AssertionError();}
 public static void main(String[] ignored)throws Exception {
  URL.setURLStreamHandlerFactory(protocol->protocol.equals("https")?new URLStreamHandler(){protected URLConnection openConnection(URL url){Connection c;if(url.getHost().equals("script.google.com"))c=new Connection(url,mode==2?307:302,mode==1?"https://evil.example/result":"https://script.googleusercontent.com/macros/echo?fixture=1","");else c=new Connection(url,200,null,"{\"ok\":true,\"users\":[]}");calls.add(c);return c;}}:null);
  Platform p=new Platform();JSONObject fields=new JSONObject().put("name","fixture").put("password","fixture-only-password").put("token","fixture-only-token");
  p.call(Policy.DEFAULT_PLATFORM,"desktop_login",fields);check(calls.size()==2);check(calls.get(0).getRequestMethod().equals("POST"));check(calls.get(0).sent.toString().contains("fixture-only-password"));check(calls.get(1).getRequestMethod().equals("GET"));check(calls.get(1).sent.size()==0);check(!calls.get(1).getURL().toString().contains("fixture-only-password"));check(!fields.has("action"));check(!calls.get(0).getInstanceFollowRedirects());
  calls.clear();mode=1;try{p.call(Policy.DEFAULT_PLATFORM,"desktop_login",fields);throw new AssertionError();}catch(Platform.Failure e){check(e.code==503);check(calls.size()==1);}
  calls.clear();mode=2;try{p.call(Policy.DEFAULT_PLATFORM,"desktop_login",fields);throw new AssertionError();}catch(Platform.Failure e){check(calls.size()==1);}
  System.out.println("Android transport PASS: POST to Google only, result GET without credentials, external redirects and 307 rejected, input unchanged.");
 }
}
