using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;
using EnergyCube.DMax.Lan;
namespace EnergyCube.DMax {
 internal sealed class ServerWindow : Form {
  private readonly LanServer server;
  private readonly TextBox name=new TextBox{Text="d-max",Width=420};
  private readonly NumericUpDown port=new NumericUpDown{Minimum=1,Maximum=65535,Value=80,Width=150};
  private readonly TextBox url=new TextBox{Width=620,MaxLength=1000};
  private readonly Label status=new Label{AutoSize=true,MaximumSize=new Size(650,0)};
  private readonly Label address=new Label{AutoSize=true,Font=new Font("Segoe UI",16,FontStyle.Bold)};
  private readonly NotifyIcon tray=new NotifyIcon{Icon=SystemIcons.Application,Text="Servidor D-Max",Visible=true};
  private bool exiting,busy;
  public ServerWindow(bool selfTest=false){
   Text="D-Max — Servidor da rede 1.2";Width=800;Height=660;MinimumSize=new Size(720,600);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Segoe UI",10);BackColor=Color.FromArgb(243,246,251);
   var path=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"EnergyCube","DMaxAcessoLan","server.json");server=new LanServer(path,Path.Combine(AppContext.BaseDirectory,"assets"));
   var form=new FlowLayoutPanel{Dock=DockStyle.Fill,FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoScroll=true,Padding=new Padding(30)};Controls.Add(form);
   form.Controls.Add(new Label{Text="D-Max · Central na rede",AutoSize=true,Font=new Font("Segoe UI",24,FontStyle.Bold),ForeColor=Color.FromArgb(9,44,80)});
   form.Controls.Add(new Label{Text="Instalado neste computador. A página fica disponível aos demais pela rede privada.",AutoSize=true,MaximumSize=new Size(650,0)});
   Add(form,"Nome local (sem .local)",name);Add(form,"Porta",port);Add(form,"URL da plataforma Google Apps Script (/exec)",url);
   name.Text=server.Settings.Name;port.Value=server.Settings.Port;url.Text=server.Settings.PlatformUrl;
   if(url.Text.Length==0)url.Text=Settings.Load();
   var actions=new FlowLayoutPanel{AutoSize=true,Width=650};actions.Controls.Add(Btn("Salvar e iniciar/reiniciar",async()=>{await Run(async()=>{var settings=new ServerSettings{Name=name.Text.Trim().ToLowerInvariant(),Port=(int)port.Value,PlatformUrl=url.Text.Trim()};settings.Validate();await server.StopAsync();await server.StartAsync(settings);ShowStatus();});}));actions.Controls.Add(Btn("Abrir página",()=>{Open();return Task.CompletedTask;}));actions.Controls.Add(Btn("Parar servidor",async()=>await Run(async()=>{await server.StopAsync();ShowStatus();})));form.Controls.Add(actions);form.Controls.Add(address);form.Controls.Add(status);
   form.Controls.Add(new Label{AutoSize=true,MaximumSize=new Size(650,0),Text="Se o Windows pedir acesso à rede, permita somente redes privadas. O servidor usa TCP da porta escolhida e mDNS UDP 5353. Não desative o firewall ou o antivírus."});
   form.Controls.Add(new Label{AutoSize=true,MaximumSize=new Size(650,0),Text="Fechar esta janela mantém o servidor na bandeja. Para encerrar, use o ícone do D-Max perto do relógio. O computador deve permanecer ligado."});
   var menu=new ContextMenuStrip();menu.Items.Add("Abrir página",null,(s,e)=>Open());menu.Items.Add("Configurar servidor",null,(s,e)=>{Show();WindowState=FormWindowState.Normal;Activate();});menu.Items.Add("Encerrar servidor",null,async(s,e)=>{exiting=true;await server.StopAsync();tray.Visible=false;Close();});tray.ContextMenuStrip=menu;tray.DoubleClick+=(s,e)=>Open();
   server.Changed+=()=>{if(!IsDisposed)try{BeginInvoke(new Action(ShowStatus));}catch{}};
   FormClosing+=(s,e)=>{if(!exiting&&!selfTest){e.Cancel=true;Hide();tray.ShowBalloonTip(2500,"D-Max ativo","O servidor continua acessível na rede.",ToolTipIcon.Info);}};
   Shown+=async(s,e)=>{if(!selfTest&&url.Text.Length>0)await Run(async()=>{var settings=new ServerSettings{Name=name.Text,Port=(int)port.Value,PlatformUrl=url.Text};await server.StartAsync(settings);ShowStatus();Open();});};
   FormClosed+=(s,e)=>tray.Dispose();ShowStatus();
  }
  private static void Add(FlowLayoutPanel form,string label,Control input){form.Controls.Add(new Label{Text=label,AutoSize=true,Margin=new Padding(0,18,0,5)});form.Controls.Add(input);}
  private Button Btn(string text,Func<Task> action){var button=new Button{Text=text,AutoSize=true,Padding=new Padding(8),Margin=new Padding(0,18,8,15)};button.Click+=async(s,e)=>await action();return button;}
  private async Task Run(Func<Task> operation){if(busy)return;busy=true;status.Text="Aguarde...";try{await operation();}catch(Exception e){StartupDiagnostics.Failure(e);MessageBox.Show(this,"Não foi possível iniciar o servidor. Confira a URL e se a porta está livre.\n\n"+e.GetType().Name+"\nDiagnóstico: "+StartupDiagnostics.LogPath,"D-Max",MessageBoxButtons.OK,MessageBoxIcon.Information);status.Text="Servidor não iniciado. Ajuste os campos e tente novamente.";}finally{busy=false;}}
  private void ShowStatus(){address.Text=server.Settings.Url;status.Text=server.Running?"Servidor ativo. "+server.DiscoveryStatus+"\nIPs: "+string.Join(" · ",LanServer.Addresses().Select(ip=>"http://"+ip+":"+server.Settings.Port)):"Servidor parado. Configure a plataforma e clique em Salvar e iniciar.";if(server.Running){name.Text=server.Settings.Name;port.Value=server.Settings.Port;url.Text=server.Settings.PlatformUrl;}}
  private void Open(){if(server.Running)try{Process.Start(new ProcessStartInfo("http://localhost:"+server.Settings.Port){UseShellExecute=true});}catch{MessageBox.Show(this,"Abra no navegador: http://localhost:"+server.Settings.Port);}}
 }
}
