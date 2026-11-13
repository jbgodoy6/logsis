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
