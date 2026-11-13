using System;
using System.IO;
using System.Reflection;
using System.Text;
namespace EnergyCube.DMax {
 internal static class StartupDiagnostics {
  public static string LogPath { get; private set; }
  public static void Initialize(string targetFolder=null) {
   string folder=targetFolder??Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"EnergyCube","DMaxAcessoDesktop","Logs");
   try{Directory.CreateDirectory(folder);}catch{folder=Path.Combine(Path.GetTempPath(),"DMaxAcessoDesktop-Logs");Directory.CreateDirectory(folder);}
   LogPath=Path.Combine(folder,"abertura-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss-fffffff")+".txt");
   Write("D-Max Acesso Desktop "+Assembly.GetExecutingAssembly().GetName().Version+"; CLR "+Environment.Version+"; process "+(IntPtr.Size*8)+" bits");
  }
  public static void Write(string stage) {try{if(LogPath!=null)File.AppendAllText(LogPath,DateTime.UtcNow.ToString("o")+" "+stage+Environment.NewLine,new UTF8Encoding(false));}catch{}}
  public static void Failure(Exception error) {
   Write("Falha de abertura. Tipos e pilha somente; dados de formulários não são registrados.");
   for(int i=0;error!=null&&i<6;i++,error=error.InnerException){Write(error.GetType().FullName);Write(error.StackTrace??"(pilha indisponível)");}
  }
 }
}
