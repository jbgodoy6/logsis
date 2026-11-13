using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;

namespace EnergyCube.DMax {
 internal sealed class Platform : IDisposable {
  private readonly HttpClient http;
  private readonly JavaScriptSerializer json=new JavaScriptSerializer { MaxJsonLength=5000000,RecursionLimit=24 };
  public string Address { get; private set; }
  public Platform(string address) {
   Uri uri;
   if(!Uri.TryCreate(address,UriKind.Absolute,out uri)||uri.Scheme!="https"||uri.Host!="script.google.com"||uri.Port!=443||uri.UserInfo.Length>0||uri.Query.Length>0||uri.Fragment.Length>0||!Regex.IsMatch(uri.AbsolutePath,@"^/macros/s/[A-Za-z0-9_-]+/exec$"))throw new ServiceError("Informe a URL da implantação Google Apps Script terminada em /exec.",422);
   Address=uri.AbsoluteUri;
   http=new HttpClient(new HttpClientHandler { AllowAutoRedirect=false,UseCookies=false }) { Timeout=TimeSpan.FromSeconds(120) };
  }
  public async Task<Dictionary<string,object>> Call(string action,Dictionary<string,object> fields) {
   fields=new Dictionary<string,object>(fields);fields["action"]=action;
   using(var cancellation=new CancellationTokenSource(TimeSpan.FromSeconds(120))) {
    try {
     using(var request=new HttpRequestMessage(HttpMethod.Post,Address)) {
      request.Content=new StringContent(json.Serialize(fields),Encoding.UTF8,"application/json");
      using(var initial=await http.SendAsync(request,HttpCompletionOption.ResponseHeadersRead,cancellation.Token)) {
       HttpResponseMessage result=initial,redirected=null;
       try {
        if(initial.StatusCode==HttpStatusCode.Found||initial.StatusCode==HttpStatusCode.SeeOther) {
         Uri target=initial.Headers.Location;
         if(target==null||!target.IsAbsoluteUri||target.Scheme!="https"||target.Host!="script.googleusercontent.com"||target.Port!=443||target.UserInfo.Length>0)throw new ServiceError("O Google pediu autenticação externa. Confira as permissões da implantação.");
         // The result GET carries no password, session token or custom headers.
         redirected=await http.SendAsync(new HttpRequestMessage(HttpMethod.Get,target),HttpCompletionOption.ResponseHeadersRead,cancellation.Token);result=redirected;
        }
        if(!result.IsSuccessStatusCode)throw new ServiceError("A plataforma retornou HTTP "+(int)result.StatusCode+".");
        using(var input=await result.Content.ReadAsStreamAsync())using(var output=new MemoryStream()) {
         var buffer=new byte[8192];int read;
         while((read=await input.ReadAsync(buffer,0,buffer.Length,cancellation.Token))>0){if(output.Length+read>5000000)throw new ServiceError("Resposta da plataforma excedeu o limite.");output.Write(buffer,0,read);}
         var data=json.DeserializeObject(Encoding.UTF8.GetString(output.ToArray())) as Dictionary<string,object>;
         if(data==null)throw new ServiceError("A implantação não retornou dados válidos.");
         if(!Values.Flag(data,"ok")) {
          int code=(int)Values.Number(data,"code");
          var message=code==401?"Login, senha ou sessão inválidos. Entre novamente.":code==403?"Seu perfil não permite esta operação.":code==409?"Conflito de ID/login. Preserve a identidade existente ou crie uma nova conta com outro login.":code==422?"Confira os dados e a aba Usuarios da planilha.":code==429?"Muitas tentativas. Aguarde cinco minutos.":"Não foi possível concluir. Confira a implantação do Apps Script.";
          throw new ServiceError(message,code);
         }
         return data;
        }
       } finally { if(redirected!=null)redirected.Dispose(); }
      }
     }
    } catch(ServiceError){throw;}catch(TaskCanceledException){throw new ServiceError("A consulta demorou demais. Confira a conexão e tente novamente.");}catch(Exception e)when(e is HttpRequestException||e is IOException||e is ArgumentException||e is InvalidOperationException){throw new ServiceError("Falha na conexão ou resposta Google inválida. Confira a implantação.");}
   }
  }
  public static bool IsClientAddress(string address) {
   Uri uri;return Uri.TryCreate(address,UriKind.Absolute,out uri)&&uri.Scheme=="https"&&uri.Port==443&&uri.UserInfo.Length==0&&uri.Query.Length==0&&uri.Fragment.Length==0&&(uri.AbsolutePath=="/"||uri.AbsolutePath=="")&&Regex.IsMatch(uri.Host,@"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com$")&&uri.Host!="api.trycloudflare.com"&&uri.Host!="www.trycloudflare.com";
  }
  public void Dispose(){http.Dispose();}
 }
 internal static class Settings {
  private static string DirectoryPath {get{return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"EnergyCube","DMaxAcessoDesktop");}}
  public static string Load() {try {var path=Path.Combine(DirectoryPath,"settings.json");if(!File.Exists(path))return "";var data=new JavaScriptSerializer().DeserializeObject(File.ReadAllText(path)) as Dictionary<string,object>;return data==null?"":Values.Text(data,"platform_url");}catch{return "";}}
  public static void Save(string url){Directory.CreateDirectory(DirectoryPath);File.WriteAllText(Path.Combine(DirectoryPath,"settings.json"),new JavaScriptSerializer().Serialize(new{platform_url=url}),new UTF8Encoding(false));}
 }
}
