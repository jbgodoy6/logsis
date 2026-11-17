package com.energycube.dmax;
import org.json.*;

/** Single serialized session, kept only in memory, never returned to JavaScript. */
public final class Session {
 public interface Settings {String get();void put(String address);}
 public interface Transport {JSONObject call(String address,String action,JSONObject fields)throws Exception;}
 private final Transport platform;private final Settings settings;
 private String token="";private JSONObject actor;
 public Session(Transport platform,Settings settings){this.platform=platform;this.settings=settings;}
 public void clear(){token="";actor=null;}
 public JSONObject dispatch(String name,JSONArray args)throws Exception {
  if(name.equals("bootstrap"))return new JSONObject().put("ok",true).put("user",actor==null?JSONObject.NULL:actor);
  if(name.equals("portalLogin")){
   if(args.length()!=2)throw new Platform.Failure(422,"Dados inválidos.");
   String login=args.getString(0),password=args.getString(1);if(login.length()>40||password.length()>200)throw new Platform.Failure(422,"Dados inválidos.");
   JSONObject reply=call("desktop_login",new JSONObject().put("name",login).put("password",password));
   String next=reply.optString("token");if(!next.matches("[a-f0-9]{64}")||reply.optJSONObject("user")==null)throw new Platform.Failure(503,"Sessão não confirmada.");
   token=next;actor=reply.getJSONObject("user");reply.remove("token");return reply;
  }
  if(name.equals("portalLogout")){String previous=token;clear();if(!previous.isEmpty())try{call("desktop_logout",new JSONObject().put("token",previous));}catch(Exception ignored){}return ok();}
  if(token.isEmpty())throw new Platform.Failure(401,"Entre novamente.");
  if(name.equals("loadSettings")){developer();return ok().put("platform_url",settings.get());}
  if(name.equals("saveSettings")){
   developer();JSONObject f=args.getJSONObject(0);String url=f.getString("platform_url");if(!Policy.platform(url))throw new Platform.Failure(422,"Use a URL HTTPS /exec do Apps Script.");
   JSONObject proof=call("desktop_login",new JSONObject().put("name",actor.getString("name")).put("password",f.getString("password")));
   String proofToken=proof.optString("token");try{JSONObject who=proof.getJSONObject("user");if(!who.optString("id").equals(actor.optString("id"))||!who.optString("role").equals("developer")||who.optBoolean("must_change"))throw new Platform.Failure(403,"Autorização inválida.");}finally{if(!proofToken.isEmpty())try{call("desktop_logout",new JSONObject().put("token",proofToken));}catch(Exception ignored){}}
   try{call("desktop_logout",new JSONObject().put("token",token));}catch(Exception ignored){}settings.put(url);clear();return ok().put("message","Plataforma salva neste Android. Entre novamente.");
  }
  JSONObject fields=new JSONObject().put("token",token);String action;
  switch(name){
   case "portalState":action="desktop_state";break;
   case "portalClients":action="desktop_clients";break;
   case "portalMembers":action="desktop_members";break;
   case "portalDevices":action="desktop_devices";break;
   case "portalOpenClient":action="desktop_open_client";fields.put("controller_id",args.getString(0));break;
   case "portalSaveDevice":action="desktop_save_device";fields.put("fields",args.getJSONObject(0));break;
   case "portalSaveUser":action="desktop_save_user";fields.put("fields",args.getJSONObject(1));break;
   case "portalChangePassword":action="desktop_change_password";fields.put("fields",args.getJSONObject(0));break;
   default:throw new Platform.Failure(404,"Operação indisponível nesta versão do aplicativo.");
  }
  JSONObject reply=call(action,fields);
  if(name.equals("portalChangePassword")){
   String next=reply.optString("token");JSONObject user=reply.optJSONObject("user");
   if(!next.matches("[a-f0-9]{64}")||user==null||!user.optString("id").equals(actor.optString("id"))||user.optBoolean("must_change"))throw new Platform.Failure(503,"Troca não confirmada.");token=next;
  }
  reply.remove("token");if(reply.optJSONObject("user")!=null)actor=reply.getJSONObject("user");
  if(name.equals("portalOpenClient")&&!Policy.ticket(reply.optString("url")))throw new Platform.Failure(503,"Destino de acesso inválido.");
  return reply;
 }
 private void developer()throws Exception{JSONObject state=call("desktop_state",new JSONObject().put("token",token));actor=state.getJSONObject("user");if(!actor.optString("role").equals("developer")||actor.optBoolean("must_change"))throw new Platform.Failure(403,"Somente desenvolvedor pode configurar a plataforma.");}
 private JSONObject call(String action,JSONObject fields)throws Exception{try{return platform.call(settings.get(),action,fields);}catch(Platform.Failure e){if(e.code==401)clear();throw e;}}
 private JSONObject ok()throws JSONException{return new JSONObject().put("ok",true);}
}
