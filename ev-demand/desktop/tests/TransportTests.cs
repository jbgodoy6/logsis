using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using EnergyCube.DMax;
internal static class TransportTests {
 static void Check(bool value,string message){if(!value)throw new Exception(message);}
 internal static void Run(){
  var handler=new Fake();using(var client=new Platform("https://script.google.com/macros/s/fixture/exec",handler)){
   var response=client.Call("desktop_login",new Dictionary<string,object>{{"name","joao"},{"password","Senha áç 🔋"}}).GetAwaiter().GetResult();
   Check(Values.Flag(response,"ok"),"native response accepted");Check(handler.Requests==2,"single approved redirect");
  }
  Check(Platform.IsClientAddress("https://client.trycloudflare.com"),"approved client");
  Check(!Platform.IsClientAddress("https://client.trycloudflare.com.attacker.test"),"lookalike hostname denied");
  foreach(var diagnostic in new[]{"directory_not_prepared","users_headers","users_record","remote_headers","remote_record","unknown-sensitive-value",""}){
   using(var client=new Platform("https://script.google.com/macros/s/fixture/exec",new Rejected(diagnostic))){
    try{client.Call("desktop_clients",new Dictionary<string,object>()).GetAwaiter().GetResult();throw new Exception("422 accepted");}
    catch(ServiceError e){Check(e.Code==422&&e.Message.Contains("desktop_clients"),"422 preserves operation and code");Check(!e.Message.Contains("fixture-secret")&&!e.Message.Contains("unknown-sensitive-value"),"untrusted details never displayed");if(diagnostic=="directory_not_prepared")Check(e.Message.Contains("directory.unified"),"preparation distinguished from user data");if(diagnostic=="")Check(e.Message.Contains("não identifica erro na planilha"),"legacy response does not blame sheet");}
   }
  }
 }
 private sealed class Rejected : HttpMessageHandler {
  readonly string diagnostic;internal Rejected(string value){diagnostic=value;}
  protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,CancellationToken ct)=>Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK){Content=new StringContent(Json.Serialize(new{ok=false,code=422,diagnostic,message="fixture-secret"}))});
 }
 private sealed class Fake : HttpMessageHandler {
  internal int Requests;
  protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,CancellationToken cancellationToken){
   Requests++;
   if(Requests==1){
    var body=Json.Object(await request.Content.ReadAsStringAsync());Check(Values.Text(body,"password")=="Senha áç 🔋"&&Values.Text(body,"action")=="desktop_login","Unicode request preserved");
    var result=new HttpResponseMessage(HttpStatusCode.Found);result.Headers.Location=new Uri("https://script.googleusercontent.com/macros/echo?fixture=1");return result;
   }
   Check(request.Method==HttpMethod.Get&&request.Content==null&&!request.Headers.Contains("Authorization"),"credentials not replayed on result GET");
   return new HttpResponseMessage(HttpStatusCode.OK){Content=new StringContent("{\"ok\":true,\"user\":{\"role\":\"developer\"}}")};
  }
 }
}
