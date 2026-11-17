package com.energycube.dmax;
import org.json.*;
import java.util.*;
public final class SessionTest {
 static void check(boolean v){if(!v)throw new AssertionError();}
 static final String TOKEN=String.join("",Collections.nCopies(64,"a")),NEXT=String.join("",Collections.nCopies(64,"b"));
 static JSONObject user(String role,boolean pending)throws Exception{return new JSONObject().put("id","USER1").put("name","fixture").put("role",role).put("must_change",pending);}
 static final class Mock implements Session.Transport {
  List<String> actions=new ArrayList<>();String role="developer",rotated=TOKEN;boolean pending=false;JSONObject last;
  public JSONObject call(String address,String action,JSONObject fields)throws Exception {
   check(Policy.platform(address));actions.add(action);last=fields;
   if(action.equals("desktop_login"))return new JSONObject().put("ok",true).put("token",TOKEN).put("user",user(role,pending));
   if(action.equals("desktop_change_password")){pending=false;rotated=NEXT;return new JSONObject().put("ok",true).put("token",NEXT).put("user",user(role,false));}
   check(fields.optString("token").equals(rotated)||action.equals("desktop_logout"));
   if(action.equals("desktop_open_client"))return new JSONObject().put("ok",true).put("url","https://fixture.trycloudflare.com/remote/sso#ticket="+TOKEN);
   return new JSONObject().put("ok",true).put("user",user(role,pending));
  }
 }
 public static void main(String[] args)throws Exception {
  check(Policy.platform(Policy.DEFAULT_PLATFORM));check(!Policy.platform("http://script.google.com/macros/s/abc/exec"));check(!Policy.platform(Policy.DEFAULT_PLATFORM+"?evil=1"));check(!Policy.platform("https://evil@script.google.com/macros/s/abc/exec"));
  check(Policy.googleResult("https://script.googleusercontent.com/macros/echo?key=fixture"));check(!Policy.googleResult("https://script.googleusercontent.com.evil/"));
  String url="https://fixture.trycloudflare.com/remote/sso#ticket="+TOKEN;check(Policy.ticket(url));check(!Policy.ticket(url.replace("/remote/sso","/login")));check(!Policy.ticket(url.replace("#ticket=","?ticket=")));check(!Policy.ticket(url.replace("fixture.trycloudflare.com","api.trycloudflare.com")));check(!Policy.sameClient("https://other.trycloudflare.com/",Policy.clientOrigin(url)));check(!Policy.sameClient("intent://fixture/",Policy.clientOrigin(url)));
  Mock mock=new Mock();String[] setting={Policy.DEFAULT_PLATFORM};Session s=new Session(mock,new Session.Settings(){public String get(){return setting[0];}public void put(String v){setting[0]=v;}});
  try{s.dispatch("portalClients",new JSONArray());throw new AssertionError();}catch(Platform.Failure e){check(e.code==401);}
  mock.pending=true;JSONObject login=s.dispatch("portalLogin",new JSONArray().put("fixture").put("12345678"));check(!login.has("token"));check(login.getJSONObject("user").getBoolean("must_change"));
  JSONObject changed=s.dispatch("portalChangePassword",new JSONArray().put(new JSONObject().put("password","fixture-new").put("confirmation","fixture-new")));check(!changed.has("token"));s.dispatch("portalClients",new JSONArray());check(mock.last.getString("token").equals(NEXT));
  check(Policy.ticket(s.dispatch("portalOpenClient",new JSONArray().put("CP-1")).getString("url")));check(mock.last.getString("controller_id").equals("CP-1"));
  s.dispatch("portalSaveUser",new JSONArray().put("ignored-local-session").put(new JSONObject().put("name","new")));check(mock.last.getJSONObject("fields").getString("name").equals("new"));
  mock.role="commercial";try{s.dispatch("loadSettings",new JSONArray());throw new AssertionError();}catch(Platform.Failure e){check(e.code==403);}
  s.dispatch("portalLogout",new JSONArray());check(s.dispatch("bootstrap",new JSONArray()).isNull("user"));
  mock.rotated=TOKEN;mock.role="developer";s.dispatch("portalLogin",new JSONArray().put("fixture").put("fixture-pass"));String target="https://script.google.com/macros/s/new-fixture/exec";s.dispatch("saveSettings",new JSONArray().put(new JSONObject().put("platform_url",target).put("password","fixture-pass")));check(setting[0].equals(target));check(s.dispatch("bootstrap",new JSONArray()).isNull("user"));
  System.out.println("Android session PASS: origin rules, memory-only tokens, forced-change response, token rotation, client handoff, user dispatch, developer settings and logout.");
 }
}
