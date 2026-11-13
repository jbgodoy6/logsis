using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using EnergyCube.DMax;
using EnergyCube.DMax.Lan;

internal sealed class Fixture : HttpMessageHandler {
 internal readonly Dictionary<string,string> Tokens=new();
 internal bool Revoke;
 internal static object Actor(string role)=>new{id=role=="developer"?"DV001":"CM001",name=role=="developer"?"dev":"comercial",full_name=role=="developer"?"Desenvolvedor Teste":"Comercial Teste",role};
 protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,CancellationToken ct){
  var data=Json.Object(await request.Content.ReadAsStringAsync(ct));var action=Values.Text(data,"action");string role="";object reply;
  if(action=="desktop_login"){
   if(Values.Text(data,"password")!="Teste1234")reply=new{ok=false,code=401};
   else {role=Values.Text(data,"name")=="dev"?"developer":"commercial";var token=Convert.ToHexString(System.Security.Cryptography.RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();Tokens[token]=role;reply=new{ok=true,token,user=Actor(role)};}
  }else if(Revoke||!Tokens.TryGetValue(Values.Text(data,"token"),out role))reply=new{ok=false,code=401};
  else switch(action){
   case "desktop_state":reply=new{ok=true,user=Actor(role)};break;
   case "desktop_logout":Tokens.Remove(Values.Text(data,"token"));reply=new{ok=true};break;
   case "desktop_clients":reply=new{ok=true,clients=new[]{new{site_name="Caratinga",controller_id="D-MAX-001",url="https://caratinga-fixture.trycloudflare.com/",connected=true,updated_at=DateTimeOffset.UtcNow.ToUnixTimeSeconds()},new{site_name="Cliente Belo Horizonte",controller_id="D-MAX-002",url="https://bh-fixture.trycloudflare.com/",connected=false,updated_at=DateTimeOffset.UtcNow.ToUnixTimeSeconds()-3000}}};break;
   case "desktop_members":reply=role!="developer"?(object)new{ok=false,code=403}:new{ok=true,users=new[]{new{id="CM001",name="comercial",full_name="Comercial Teste",role="commercial",active=true,deleted=false,expires_at=0}}};break;
   case "desktop_save_user":var fields=Values.Object(data,"fields");reply=role!="developer"?(object)new{ok=false,code=403}:Values.Text(fields,"actor_password")!="Teste1234"?new{ok=false,code=401}:new{ok=true,verifier="pbkdf2_sha256$fixture-verifier"};break;
   default:throw new Exception("Ação inesperada: "+action);
  }
  return new HttpResponseMessage(HttpStatusCode.OK){Content=new StringContent(Json.Serialize(reply),Encoding.UTF8,"application/json")};
 }
 protected override void Dispose(bool disposing){} // Shared in-memory fixture, never production transport.
}
internal static class Program {
 static void Check(bool value,string message){if(!value)throw new Exception(message);}
 static async Task Main(string[] args){
  const string google="https://script.google.com/macros/s/fixture/exec";
  var assets=Path.GetFullPath(args.Length>1?args[1]:"lan/assets");
  var config=Path.Combine(Path.GetTempPath(),"dmax-lan-tests-"+Guid.NewGuid(),"server.json");var fixture=new Fixture();
  await using var server=new LanServer(config,assets,url=>new Platform(url,fixture));
  var defaults=new ServerSettings();Check(defaults.Url=="http://d-max.local:80","Default exato");Check(LanServer.Private(IPAddress.Parse("192.168.1.1"))&&!LanServer.Private(IPAddress.Parse("8.8.8.8")),"Somente rede privada");
  foreach(var invalid in new[]{"d-max.local","a/b","-bad","UPPER"}){try{new ServerSettings{Name=invalid,PlatformUrl=google}.Validate();throw new Exception("Nome deveria falhar");}catch(InvalidOperationException){}}
  // Bounded DNS parser, address/service records and goodbye packets.
  var wire=MdnsWire.Response("d-max.local","d-max._http._tcp.local",80,new[]{IPAddress.Parse("192.168.10.20")});var records=MdnsWire.Answers(wire);Check(records.Count==5&&records.Any(r=>r.Type==1&&r.Name=="d-max.local"&&r.Data.SequenceEqual(new byte[]{192,168,10,20})),"mDNS A");var srv=records.Single(r=>r.Type==33);Check(srv.Data[4]==0&&srv.Data[5]==80,"mDNS porta 80");var off=6;Check(MdnsWire.Name(srv.Data,ref off)=="d-max.local","mDNS SRV target");Check(MdnsWire.Answers(MdnsWire.Response("outro.local","outro._http._tcp.local",8080,new[]{IPAddress.Loopback},0)).All(r=>r.Ttl==0),"mDNS goodbye");bool unicast;Check(MdnsWire.Relevant(MdnsWire.Probe("d-max.local"),"d-max.local","d-max._http._tcp.local",out unicast),"mDNS consulta");try{var n=0;MdnsWire.Name(new byte[]{0xc0,0},ref n);throw new Exception("Ciclo DNS aceito");}catch(InvalidDataException){}
  if(args.Contains("--announce")){await using var mdns=new MdnsAnnouncer("dmax-lan-fixture",8080,LanServer.Addresses);await mdns.StartAsync();Console.WriteLine(mdns.Status);await Task.Delay(20000);return;}
  var listener=new System.Net.Sockets.TcpListener(IPAddress.Loopback,0);listener.Start();int port=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();if(args.Contains("--serve"))port=8780;
  await server.StartAsync(new ServerSettings{PlatformUrl=google,Port=port},true);
  if(args.Contains("--serve")){Console.WriteLine("FIXTURE_READY http://127.0.0.1:"+port);await Task.Delay(Timeout.Infinite);return;}
  var cookies=new CookieContainer();var http=new HttpClient(new HttpClientHandler{CookieContainer=cookies}){BaseAddress=new Uri("http://127.0.0.1:"+port)};
  async Task<Dictionary<string,object>> Get(string path)=>Json.Object(await http.GetStringAsync(path));
  var boot=await Get("/api/bootstrap");var csrf=Values.Text(boot,"csrf");Check(csrf.Length>20&&Values.Object(boot,"user")==null,"Bootstrap anônimo");
  async Task<Dictionary<string,object>> Post(string path,object body,bool withCsrf=true){using var req=new HttpRequestMessage(HttpMethod.Post,path){Content=new StringContent(Json.Serialize(body),Encoding.UTF8,"application/json")};if(withCsrf)req.Headers.Add("X-D-Max-CSRF",csrf);using var res=await http.SendAsync(req);return Json.Object(await res.Content.ReadAsStringAsync());}
  async Task<Dictionary<string,object>> Rpc(string name,params object[] a)=>await Post("/api/portal",new{name,args=a});
  Check((int)Values.Number(await Rpc("portalClients","bogus"),"code")==401,"Dados exigem login");
  Check((int)Values.Number(await Post("/api/portal",new{name="portalLogin",args=new[]{"dev","Teste1234"}},false),"code")==403,"CSRF obrigatório");
  using(var bad=new HttpRequestMessage(HttpMethod.Get,"/")){bad.Headers.Host="evil.example";Check((await http.SendAsync(bad)).StatusCode==HttpStatusCode.Forbidden,"Host externo recusado");}
  var login=await Rpc("portalLogin","dev","Teste1234");Check(Values.Flag(login,"ok")&&!login.ContainsKey("token"),"Token central não sai para navegador");Check(cookies.GetCookies(http.BaseAddress)["DMaxLanSession"].HttpOnly,"Cookie HttpOnly");
  Check(Values.Text(Values.Object(await Get("/api/bootstrap"),"user"),"role")=="developer","Sessão recarrega");
  Check(Values.Rows(await Rpc("portalClients","ignored"),"clients").Count==2,"Clientes Google");Check(Values.Rows(await Rpc("portalMembers","ignored"),"users").Count==1,"Membros desenvolvedor");
  var settings=await Get("/api/settings");Check(Values.Text(settings,"name")=="d-max"&&Values.Text(settings,"platform_url")==google,"Config desenvolvedor");
  Check((int)Values.Number(await Post("/api/settings",new{name="outro",port=8080,platform_url=google,password="incorreta"}),"code")==401,"Config exige senha atual");Check(server.Settings.Name=="d-max","Config não muda sem prova");
  await Rpc("portalLogout","ignored");Check((int)Values.Number(await Rpc("portalClients","ignored"),"code")==401,"Logout revoga sessão local");
  await Rpc("portalLogin","comercial","Teste1234");Check((int)Values.Number(await Get("/api/settings"),"code")==403,"Comercial sem configuração");Check((int)Values.Number(await Rpc("portalMembers","ignored"),"code")==403,"Comercial sem membros");
  fixture.Revoke=true;Check((int)Values.Number(await Rpc("portalClients","ignored"),"code")==401,"Revogação online aplicada");fixture.Revoke=false;
  await Rpc("portalLogin","dev","Teste1234");
  listener=new System.Net.Sockets.TcpListener(IPAddress.Loopback,0);listener.Start();int changedPort=((IPEndPoint)listener.LocalEndpoint).Port;listener.Stop();
  var changed=await Post("/api/settings",new{name="central-teste",port=changedPort,platform_url=google,password="Teste1234"});Check(Values.Flag(changed,"ok")&&Values.Text(changed,"url")=="http://central-teste.local:"+changedPort,"Mudança de nome aceita");
  for(int i=0;i<60&&server.Settings.Name!="central-teste";i++)await Task.Delay(100);
  Check(server.Settings.Name=="central-teste"&&server.Settings.Port==changedPort&&server.Running,"Reinício após alteração");http.Dispose();http=new HttpClient(new HttpClientHandler{CookieContainer=cookies}){BaseAddress=new Uri("http://127.0.0.1:"+changedPort)};Check((int)Values.Number(await Rpc("portalClients","ignored"),"code")==401,"Reinício descarta sessões");
  var saved=File.ReadAllText(config);Check(!saved.Contains("Teste1234")&&!saved.Contains("token"),"Config sem senha/token");
  http.Dispose();await server.StopAsync();Directory.Delete(Path.GetDirectoryName(config),true);Console.WriteLine("LAN PASS: defaults, mDNS, CSRF, host, cookies, roles, revocation, persistence");
 }
}
