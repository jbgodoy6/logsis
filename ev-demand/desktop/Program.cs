using System;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Windows.Forms;
namespace EnergyCube.DMax {
 internal static class Program {
  [STAThread] static int Main(string[] args) {
   bool selfTest=args.Contains("--self-test-ui");
   try {
    StartupDiagnostics.Initialize();
    return RunApplication(selfTest);
   } catch(Exception error) {
    StartupDiagnostics.Failure(error);
    if(!selfTest)ShowStartupFailure(error);
    return 1;
   }
  }
  [MethodImpl(MethodImplOptions.NoInlining)]
  static int RunApplication(bool selfTest) {
   Exception threadFailure=null;
   Application.SetUnhandledExceptionMode(UnhandledExceptionMode.CatchException);
   Application.ThreadException+=(sender,eventArgs)=>{threadFailure=eventArgs.Exception;Application.Exit();};
   AppDomain.CurrentDomain.UnhandledException+=(sender,eventArgs)=>{var error=eventArgs.ExceptionObject as Exception;if(error!=null)StartupDiagnostics.Failure(error);};
   StartupDiagnostics.Write("Preparando interface gráfica");
   Application.EnableVisualStyles();
   Application.SetCompatibleTextRenderingDefault(false);
   using(var window=new MainWindow()) {
    StartupDiagnostics.Write("Janela criada");
    bool shown=false;
    window.Shown+=(sender,eventArgs)=>{shown=true;StartupDiagnostics.Write("Janela de login exibida");if(selfTest){if(CountInputs(window)<3||window.ClientSize.Width<700||window.ClientSize.Height<450)throw new InvalidOperationException("Janela de login incompleta");var timer=new Timer{Interval=500};timer.Tick+=(s,e)=>{timer.Stop();timer.Dispose();window.Close();};timer.Start();}};
    Application.Run(window);
    if(threadFailure!=null)throw new InvalidOperationException("Falha na interface gráfica",threadFailure);
    if(selfTest&&!shown)throw new InvalidOperationException("Janela não exibida no teste de abertura.");
    StartupDiagnostics.Write(selfTest?"UI STARTUP TEST PASSED":"Aplicação encerrada normalmente");
   }
   return 0;
  }
  static int CountInputs(Control root){int count=root is TextBox?1:0;foreach(Control child in root.Controls)count+=CountInputs(child);return count;}
  [MethodImpl(MethodImplOptions.NoInlining)]
  static void ShowStartupFailure(Exception error) {
   try{MessageBox.Show("O D-Max não conseguiu abrir a janela.\n\nErro: "+error.GetType().Name+"\n\nDiagnóstico local:\n"+(StartupDiagnostics.LogPath??"Não foi possível gravar o relatório.")+"\n\nEsta versão inclui o runtime necessário. Não exige instalar .NET Framework.","D-Max — falha de abertura",MessageBoxButtons.OK,MessageBoxIcon.Error);}catch{}
  }
 }
}
