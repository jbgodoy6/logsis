package com.energycube.dmax;
import org.json.JSONObject;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** HTTPS transport. Redirect GET never replays login, developer proof or session token. */
public final class Platform implements Session.Transport {
 public static final class Failure extends Exception {
  private static final long serialVersionUID=1L;
  public final int code;
  public Failure(int code,String message){super(message);this.code=code;}
 }
 public JSONObject call(String address,String action,JSONObject fields)throws Exception {
  if(!Policy.platform(address))throw new Failure(422,"URL da plataforma inválida.");
  JSONObject payload=new JSONObject(fields.toString());payload.put("action",action);
  HttpURLConnection first=null,result=null;
  try{
   first=open(address);first.setRequestMethod("POST");first.setDoOutput(true);first.setRequestProperty("Content-Type","application/json; charset=utf-8");
   byte[] bytes=payload.toString().getBytes(StandardCharsets.UTF_8);first.setFixedLengthStreamingMode(bytes.length);
   try(OutputStream out=first.getOutputStream()){out.write(bytes);}
   int status=first.getResponseCode();result=first;
   if(status==302||status==303){String url=first.getHeaderField("Location");if(!Policy.googleResult(url))throw new Failure(503,"Confira as permissões da implantação Google.");result=open(url);result.setRequestMethod("GET");status=result.getResponseCode();}
   if(status!=200)throw new Failure(503,"A plataforma retornou HTTP "+status+".");
   ByteArrayOutputStream data=new ByteArrayOutputStream();try(InputStream input=result.getInputStream()){byte[] buffer=new byte[8192];int n;while((n=input.read(buffer))!=-1){if(data.size()+n>5000000)throw new Failure(503,"Resposta muito grande.");data.write(buffer,0,n);}}
   JSONObject reply=new JSONObject(new String(data.toByteArray(),StandardCharsets.UTF_8));
   if(!reply.optBoolean("ok")){int code=reply.optInt("code",503);String message=code==401?"Login, senha ou sessão inválidos. Entre novamente.":code==403?"Seu perfil não permite esta operação, ou exige troca da senha inicial.":code==404?"Atualize a implantação do Apps Script: operação não reconhecida.":code==409?"Conflito de cadastro. Preserve o ID e o login existentes.":code==422?"A plataforma recusou os campos. Confira a versão do Apps Script e o cadastro.":code==429?"Muitas tentativas. Aguarde cinco minutos.":"Não foi possível concluir na plataforma Google.";throw new Failure(code,message+" ["+action+"; código "+code+"]");}
   return reply;
  }catch(Failure e){throw e;}catch(Exception e){throw new Failure(503,"Falha de conexão. Confira a internet e a implantação Google.");}
  finally{if(result!=null&&result!=first)result.disconnect();if(first!=null)first.disconnect();}
 }
 private HttpURLConnection open(String address)throws Exception {HttpURLConnection c=(HttpURLConnection)URI.create(address).toURL().openConnection();c.setInstanceFollowRedirects(false);c.setConnectTimeout(20000);c.setReadTimeout(120000);c.setUseCaches(false);c.setRequestProperty("Accept","application/json");return c;}
}
