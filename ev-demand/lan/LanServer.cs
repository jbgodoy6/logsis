using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using EnergyCube.DMax;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace EnergyCube.DMax.Lan {
 public sealed class ServerSettings {
  public string Name {get;set;}="d-max";
  public int Port {get;set;}=80;
  public string PlatformUrl {get;set;}="";
  public string Url {get{return "http://"+Name+".local:"+Port;}}
  public void Validate(){if(!Regex.IsMatch(Name??"",@"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"))throw new InvalidOperationException("Nome inválido. Use letras minúsculas, números e hífen, sem .local.");if(Port<1||Port>65535)throw new InvalidOperationException("A porta deve ficar entre 1 e 65535.");using(var test=new Platform(PlatformUrl)){} }
 }
 public sealed class LanServer : IAsyncDisposable {
  private sealed class Session { public string Central;public Dictionary<string,object> Actor;public DateTime Until; }
  private readonly ConcurrentDictionary<string,Session> sessions=new ConcurrentDictionary<string,Session>();
  private readonly ConcurrentDictionary<string,List<DateTime>> attempts=new ConcurrentDictionary<string,List<DateTime>>();
  private readonly SemaphoreSlim lifecycle=new SemaphoreSlim(1,1);
  private readonly string configPath,assetPath;
  private readonly Func<string,Platform> platformFactory;
  private bool testMode;
  private WebApplication app;
  private Platform platform;
  private MdnsAnnouncer discovery;
  public ServerSettings Settings {get;private set;}
  public bool Running {get{return app!=null;}}
  public string DiscoveryStatus {get{return discovery==null?"Não anunciado":discovery.Status;}}
  public event Action Changed;
  public LanServer(string configPath,string assetPath):this(configPath,assetPath,null){}
  internal LanServer(string configPath,string assetPath,Func<string,Platform> factory){this.configPath=configPath;this.assetPath=assetPath;platformFactory=factory??(url=>new Platform(url));Settings=Load();}
  public static IPAddress[] Addresses(){return NetworkInterface.GetAllNetworkInterfaces().Where(n=>n.OperationalStatus==OperationalStatus.Up&&(n.NetworkInterfaceType==NetworkInterfaceType.Ethernet||n.NetworkInterfaceType==NetworkInterfaceType.Wireless80211)).SelectMany(n=>{try{return n.GetIPProperties().UnicastAddresses.Select(a=>a.Address).ToArray();}catch{return new IPAddress[0];}}).Where(a=>a.AddressFamily==System.Net.Sockets.AddressFamily.InterNetwork&&!IPAddress.IsLoopback(a)&&Private(a)).Distinct().ToArray();}
  public static bool Private(IPAddress ip){if(ip==null)return false;if(ip.IsIPv4MappedToIPv6)ip=ip.MapToIPv4();if(IPAddress.IsLoopback(ip))return true;var b=ip.GetAddressBytes();if(b.Length==4)return b[0]==10||b[0]==192&&b[1]==168||b[0]==172&&b[1]>=16&&b[1]<=31||b[0]==169&&b[1]==254;return ip.IsIPv6LinkLocal||(b[0]&0xfe)==0xfc;}
  private ServerSettings Load(){try{if(File.Exists(configPath)){var row=Json.Object(File.ReadAllText(configPath));var s=new ServerSettings{Name=Values.Text(row,"name"),Port=(int)Values.Number(row,"port"),PlatformUrl=Values.Text(row,"platform_url")};s.Validate();return s;}}catch{}return new ServerSettings();}
  public async Task StartAsync(ServerSettings settings,bool loopbackTest=false){
   settings.Validate();testMode=loopbackTest;await lifecycle.WaitAsync();try{if(app!=null)throw new InvalidOperationException("O servidor já está ativo.");
    var builder=WebApplication.CreateBuilder(new WebApplicationOptions{ContentRootPath=assetPath,Args=Array.Empty<string>()});builder.Logging.ClearProviders();
    builder.WebHost.UseUrls("http://"+(loopbackTest?"127.0.0.1":"0.0.0.0")+":"+settings.Port);
    builder.WebHost.ConfigureKestrel(o=>{o.Limits.MaxConcurrentConnections=128;o.Limits.MaxRequestBodySize=24000;o.Limits.RequestHeadersTimeout=TimeSpan.FromSeconds(15);});
    var keyDirectory=Path.Combine(Path.GetDirectoryName(configPath),"Keys");Directory.CreateDirectory(keyDirectory);var keys=builder.Services.AddDataProtection().PersistKeysToFileSystem(new DirectoryInfo(keyDirectory));if(OperatingSystem.IsWindows())keys.ProtectKeysWithDpapi();
    builder.Services.AddAntiforgery(o=>{o.HeaderName="X-D-Max-CSRF";o.Cookie.Name="DMaxLanCsrf";o.Cookie.HttpOnly=true;o.Cookie.SameSite=SameSiteMode.Strict;});
    var next=builder.Build();var client=platformFactory(settings.PlatformUrl);
    Settings=settings;platform=client;sessions.Clear();
    next.Use(async(context,proceed)=>{
     var host=context.Request.Host.Host.ToLowerInvariant();IPAddress ip;
     bool valid=host==settings.Name+".local"||host=="localhost"||host==Environment.MachineName.ToLowerInvariant()||IPAddress.TryParse(host,out ip)&&(IPAddress.IsLoopback(ip)||Addresses().Contains(ip));
     if(!valid||!Private(context.Connection.RemoteIpAddress)){context.Response.StatusCode=403;return;}
     context.Response.Headers["Cache-Control"]="no-store";context.Response.Headers["X-Content-Type-Options"]="nosniff";context.Response.Headers["X-Frame-Options"]="DENY";context.Response.Headers["Referrer-Policy"]="same-origin";context.Response.Headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'; object-src 'none'";
     if(HttpMethods.IsPost(context.Request.Method)){try{await context.RequestServices.GetRequiredService<IAntiforgery>().ValidateRequestAsync(context);}catch(AntiforgeryValidationException){await Reply(context,new{ok=false,code=403,message="Formulário expirou. Atualize a página."});return;}}
     await proceed();
    });
    next.MapGet("/",context=>Asset(context,"index.html","text/html; charset=utf-8"));
    next.MapGet("/assets/app.js",context=>Asset(context,"app.js","application/javascript"));next.MapGet("/assets/style.css",context=>Asset(context,"style.css","text/css"));next.MapGet("/assets/d-max-logo.png",context=>Asset(context,"d-max-logo.png","image/png"));
    next.MapGet("/api/bootstrap",async context=>{var tokens=context.RequestServices.GetRequiredService<IAntiforgery>().GetAndStoreTokens(context);var session=Find(context);Dictionary<string,object> actor=null;if(session!=null){try{var result=await platform.Call("desktop_state",new Dictionary<string,object>{{"token",session.Central}});actor=Values.Object(result,"user");session.Actor=actor;}catch{Remove(context);}}await Reply(context,new{ok=true,csrf=tokens.RequestToken,user=actor,server=new{name=Settings.Name,port=Settings.Port,url=Settings.Url,discovery=DiscoveryStatus}});});
    next.MapPost("/api/portal",Portal);
    next.MapGet("/api/settings",async context=>{try{var session=await Developer(context);await Reply(context,new{ok=true,name=Settings.Name,port=Settings.Port,platform_url=Settings.PlatformUrl,url=Settings.Url,discovery=DiscoveryStatus});}catch(ServiceError e){await Error(context,e);}});
    next.MapPost("/api/settings",SaveSettings);
    try{await next.StartAsync();app=next;if(!loopbackTest){discovery=new MdnsAnnouncer(settings.Name,settings.Port,Addresses);await discovery.StartAsync();}Persist(settings);Changed?.Invoke();}catch{if(discovery!=null){await discovery.DisposeAsync();discovery=null;}app=null;await next.DisposeAsync();client.Dispose();platform=null;throw;}
   }finally{lifecycle.Release();}
  }
  private async Task Asset(HttpContext context,string name,string type){var file=Path.Combine(assetPath,name);context.Response.ContentType=type;await context.Response.SendFileAsync(file);}
  private static async Task Reply(HttpContext context,object value){context.Response.ContentType="application/json; charset=utf-8";await context.Response.WriteAsync(Json.Serialize(value));}
  private static Task Error(HttpContext context,ServiceError error){return Reply(context,new{ok=false,code=error.Code,message=error.Message});}
  private Session Find(HttpContext context){string sid;Session s;foreach(var item in sessions.Where(p=>p.Value.Until<DateTime.UtcNow).ToArray())sessions.TryRemove(item.Key,out _);if(!context.Request.Cookies.TryGetValue("DMaxLanSession",out sid)||!Regex.IsMatch(sid,@"^[0-9a-f]{64}$")||!sessions.TryGetValue(sid,out s)||s.Until<DateTime.UtcNow)return null;s.Until=DateTime.UtcNow.AddMinutes(Values.Text(s.Actor,"role")=="commercial"?15:60);return s;}
  private void Remove(HttpContext context){string sid;if(context.Request.Cookies.TryGetValue("DMaxLanSession",out sid))sessions.TryRemove(sid,out _);context.Response.Cookies.Delete("DMaxLanSession");}
  private async Task<Session> Developer(HttpContext context){var session=Find(context);if(session==null)throw new ServiceError("Entre novamente.",401);var result=await platform.Call("desktop_state",new Dictionary<string,object>{{"token",session.Central}});session.Actor=Values.Object(result,"user");if(session.Actor==null||Values.Text(session.Actor,"role")!="developer")throw new ServiceError("Somente desenvolvedor pode alterar a configuração.",403);return session;}
  private async Task Portal(HttpContext context){
   try{var body=Json.Object(await new StreamReader(context.Request.Body).ReadToEndAsync());var name=Values.Text(body,"name");object raw;var args=body.TryGetValue("args",out raw)?raw as object[]:null;args=args??Array.Empty<object>();
    if(name=="portalLogin"){
     string ip=context.Connection.RemoteIpAddress.ToString();foreach(var old in attempts.ToArray()){lock(old.Value){old.Value.RemoveAll(t=>t<DateTime.UtcNow.AddMinutes(-5));if(old.Value.Count==0)attempts.TryRemove(old.Key,out _);}}if(attempts.Count>=1024&&!attempts.ContainsKey(ip))throw new ServiceError("Muitas tentativas. Aguarde cinco minutos.",429);var times=attempts.GetOrAdd(ip,_=>new List<DateTime>());lock(times){times.RemoveAll(t=>t<DateTime.UtcNow.AddMinutes(-5));if(times.Count>=8)throw new ServiceError("Muitas tentativas. Aguarde cinco minutos.",429);times.Add(DateTime.UtcNow);}
     if(args.Length!=2||!(args[0] is string)||!(args[1] is string)||((string)args[0]).Length>40||((string)args[1]).Length>200)throw new ServiceError("Dados inválidos.",422);
     var result=await platform.Call("desktop_login",new Dictionary<string,object>{{"name",args[0]},{"password",args[1]}});var actor=Values.Object(result,"user");var central=Values.Text(result,"token");if(actor==null||central.Length!=64)throw new ServiceError("Sessão inválida.");
     if(sessions.Count>=64)throw new ServiceError("Limite de sessões atingido.");Remove(context);var sid=Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();sessions[sid]=new Session{Actor=actor,Central=central,Until=DateTime.UtcNow.AddMinutes(Values.Text(actor,"role")=="commercial"?15:60)};context.Response.Cookies.Append("DMaxLanSession",sid,new CookieOptions{HttpOnly=true,SameSite=SameSiteMode.Strict,IsEssential=true,Path="/"});await Reply(context,new{ok=true,user=actor});return;
    }
    var session=Find(context);if(session==null)throw new ServiceError("Sessão encerrada. Entre novamente.",401);
    if(name=="portalLogout"){Remove(context);try{await platform.Call("desktop_logout",new Dictionary<string,object>{{"token",session.Central}});}catch{}await Reply(context,new{ok=true});return;}
    var request=new Dictionary<string,object>{{"token",session.Central}};string action;
    switch(name){case "portalState":action="desktop_state";break;case "portalClients":action="desktop_clients";break;case "portalMembers":action="desktop_members";break;case "portalSaveUser":action="desktop_save_user";if(args.Length!=2||!(args[1] is Dictionary<string,object>))throw new ServiceError("Formulário inválido.",422);request["fields"]=args[1];break;default:throw new ServiceError("Operação indisponível.",404);}
    var reply=await platform.Call(action,request);var current=Values.Object(reply,"user");if(current!=null)session.Actor=current;await Reply(context,reply);
   }catch(ServiceError error){if(error.Code==401)Remove(context);await Error(context,error);}catch{await Reply(context,new{ok=false,code=503,message="Não foi possível concluir a consulta. Confira a plataforma."});}
  }
  private async Task SaveSettings(HttpContext context){try{var session=await Developer(context);var body=Json.Object(await new StreamReader(context.Request.Body).ReadToEndAsync());var proof=await platform.Call("desktop_login",new Dictionary<string,object>{{"name",Values.Text(session.Actor,"name")},{"password",Values.Text(body,"password")}});var actor=Values.Object(proof,"user");if(actor==null||Values.Text(actor,"id")!=Values.Text(session.Actor,"id")||Values.Text(actor,"role")!="developer")throw new ServiceError("Autorização inválida.",403);try{await platform.Call("desktop_logout",new Dictionary<string,object>{{"token",Values.Text(proof,"token")}});}catch{}
    var settings=new ServerSettings{Name=Values.Text(body,"name").Trim().ToLowerInvariant(),Port=(int)Values.Number(body,"port"),PlatformUrl=Values.Text(body,"platform_url").Trim()};settings.Validate();await Reply(context,new{ok=true,url=settings.Url,message="Configuração salva. O servidor vai reiniciar neste novo endereço."});var previous=Settings;var previousTestMode=testMode;_=Task.Run(async()=>{await Task.Delay(1800);try{await StopAsync();await StartAsync(settings,previousTestMode);}catch{try{await StopAsync();await StartAsync(previous,previousTestMode);}catch{}Changed?.Invoke();}});
   }catch(ServiceError e){await Error(context,e);}catch{await Reply(context,new{ok=false,code=422,message="Confira o nome, porta e endereço da plataforma."});}}
  private void Persist(ServerSettings s){Directory.CreateDirectory(Path.GetDirectoryName(configPath));File.WriteAllText(configPath,Json.Serialize(new{name=s.Name,port=s.Port,platform_url=s.PlatformUrl}),new UTF8Encoding(false));}
  public async Task StopAsync(){await lifecycle.WaitAsync();try{if(discovery!=null){await discovery.DisposeAsync();discovery=null;}if(app!=null){var old=app;app=null;await old.StopAsync();await old.DisposeAsync();}platform?.Dispose();platform=null;sessions.Clear();Changed?.Invoke();}finally{lifecycle.Release();}}
  public async ValueTask DisposeAsync(){await StopAsync();}
 }
}
