using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace EnergyCube.DMax {
 internal sealed class MainWindow : Form {
  private readonly Color navy=Color.FromArgb(9,44,80),blue=Color.FromArgb(8,123,200),background=Color.FromArgb(243,246,251);
  private readonly Panel sidebar=new Panel{Dock=DockStyle.Left,Width=220};
  private readonly Panel body=new Panel{Dock=DockStyle.Fill,AutoScroll=true,Padding=new Padding(25)};
  private readonly FlowLayoutPanel menu=new FlowLayoutPanel{Dock=DockStyle.Top,FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoSize=true,Padding=new Padding(10)};
  private readonly Label identity=new Label{Dock=DockStyle.Bottom,Height=95,Padding=new Padding(15),ForeColor=Color.White};
  private readonly ToolStripStatusLabel status=new ToolStripStatusLabel{Spring=true,TextAlign=ContentAlignment.MiddleLeft};
  private readonly Timer timer=new Timer{Interval=1000};
  private Platform platform;
  private string token="",view="",address="";
  private Dictionary<string,object> actor;
  private List<Dictionary<string,object>> clients=new List<Dictionary<string,object>>(),members=new List<Dictionary<string,object>>();
  private Simulation simulation;
  private long lastTick=Stopwatch.GetTimestamp(),lastInput=Stopwatch.GetTimestamp(),lastPing=Stopwatch.GetTimestamp();
  private bool busy;
  private FlowLayoutPanel clientCards,simCards;
  private Label simTotal;
  private TextBox search;
  private readonly List<Label[]> simLabels=new List<Label[]>();
  private readonly List<Button[]> simButtons=new List<Button[]>();
  public MainWindow() {
   Text="D-Max Acesso Desktop 1.0";Width=1250;Height=850;MinimumSize=new Size(900,640);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Segoe UI",10);BackColor=background;
   sidebar.BackColor=navy;
   var brand=new Label{Dock=DockStyle.Top,Height=110,Text="D-Max\nACESSO DESKTOP",Font=new Font("Segoe UI",22,FontStyle.Bold),ForeColor=Color.White,TextAlign=ContentAlignment.MiddleCenter};
   var menuHost=new Panel{Dock=DockStyle.Fill};menuHost.Controls.Add(menu);
   sidebar.Controls.Add(menuHost);sidebar.Controls.Add(identity);sidebar.Controls.Add(brand);
   Controls.Add(body);Controls.Add(sidebar);
   var bar=new StatusStrip();bar.Items.Add(status);Controls.Add(bar);bar.BringToFront();
   address=Settings.Load();
   timer.Tick+=async(s,e)=>await Tick();timer.Start();
   FormClosed+=(s,e)=>{timer.Stop();token="";actor=null;simulation=null;if(platform!=null)platform.Dispose();};
   KeyPreview=true;KeyDown+=(s,e)=>lastInput=Stopwatch.GetTimestamp();MouseDown+=(s,e)=>lastInput=Stopwatch.GetTimestamp();
   ShowLogin();
  }
  private Button Button(string text,Action click,bool secondary=false) {
   var b=new Button{Text=text,AutoSize=true,MinimumSize=new Size(125,38),Padding=new Padding(12,5,12,5),FlatStyle=FlatStyle.Flat,BackColor=secondary?Color.FromArgb(229,239,249):blue,ForeColor=secondary?navy:Color.White,Margin=new Padding(4,8,8,8),Cursor=Cursors.Hand};b.FlatAppearance.BorderSize=0;b.Click+=(s,e)=>{lastInput=Stopwatch.GetTimestamp();click();};return b;
  }
  private Label Label(string text,int size=10,bool bold=false) {return new Label{Text=text,AutoSize=true,MaximumSize=new Size(900,0),Font=new Font("Segoe UI",size,bold?FontStyle.Bold:FontStyle.Regular),ForeColor=navy,Margin=new Padding(4,7,4,7)};}
  private FlowLayoutPanel Stack() {return new FlowLayoutPanel{FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoSize=true,AutoSizeMode=AutoSizeMode.GrowAndShrink,Padding=new Padding(18),Margin=new Padding(0,0,0,18),BackColor=Color.White};}
  private FlowLayoutPanel Page(string title) {
   view=title;AcceptButton=null;foreach(Control old in body.Controls.Cast<Control>().ToArray())old.Dispose();body.Controls.Clear();simCards=null;clientCards=null;simLabels.Clear();simButtons.Clear();
   var page=new FlowLayoutPanel{Dock=DockStyle.Top,FlowDirection=FlowDirection.TopDown,WrapContents=false,AutoSize=true};body.Controls.Add(page);
   page.Controls.Add(Label(title,24,true));
   Action resize=()=>{foreach(Control c in page.Controls)if(c is FlowLayoutPanel||c is DataGridView)c.Width=Math.Max(500,body.ClientSize.Width-65);};
   EventHandler resized=(s,e)=>{if(!page.IsDisposed)resize();};body.ClientSizeChanged+=resized;page.Disposed+=(s,e)=>body.ClientSizeChanged-=resized;page.ControlAdded+=(s,e)=>resize();return page;
  }
  private TextBox Input(bool password=false) {var input=new TextBox{Width=480,MaxLength=200,UseSystemPasswordChar=password,Margin=new Padding(4,2,4,10)};input.TextChanged+=(s,e)=>lastInput=Stopwatch.GetTimestamp();return input;}
  private void Field(FlowLayoutPanel panel,string label,Control value){panel.Controls.Add(Label(label));panel.Controls.Add(value);}
  private async Task Run(Func<Task> operation) {
   if(busy)return;busy=true;body.Enabled=false;menu.Enabled=false;status.Text="Aguarde a confirmação da plataforma...";
   try{await operation();if(actor!=null)status.Text="Conectado como "+Values.Text(actor,"full_name")+" · "+Role(Values.Text(actor,"role"));}
   catch(ServiceError e){status.Text=e.Message;if(e.Code==401&&actor!=null){ClearSession();ShowLogin();}MessageBox.Show(this,e.Message,"D-Max Acesso",MessageBoxButtons.OK,MessageBoxIcon.Information);}
   catch{status.Text="Não foi possível concluir a operação.";MessageBox.Show(this,"Não foi possível concluir. Confira a conexão, a implantação e os dados informados.","D-Max Acesso",MessageBoxButtons.OK,MessageBoxIcon.Information);}
   finally{busy=false;if(!IsDisposed){body.Enabled=true;menu.Enabled=true;}}
  }
  private string Role(string role){return role=="developer"?"Desenvolvedor":role=="commercial"?"Comercial":role=="technician"?"Técnico":"Perfil inválido";}
  private bool IsDeveloper {get{return actor!=null&&Values.Text(actor,"role")=="developer";}}
  private Dictionary<string,object> SessionFields(){return new Dictionary<string,object>{{"token",token}};}
  private void ClearSession(){token="";actor=null;simulation=null;clients.Clear();members.Clear();identity.Text="";menu.Controls.Clear();sidebar.Visible=false;}
  private void BuildMenu() {
   sidebar.Visible=true;menu.Controls.Clear();
   menu.Controls.Add(Button("Visão geral",()=>{var ignored=Run(ShowClients);}));
   menu.Controls.Add(Button("Simulação",ShowSimulation));
   if(IsDeveloper){menu.Controls.Add(Button("Usuários",()=>{var ignored=Run(ShowMembers);}));menu.Controls.Add(Button("Configurações",ShowSettings));}
   menu.Controls.Add(Button("Sair",()=>{var ignored=Run(SignOut);}));
   identity.Text=Values.Text(actor,"full_name")+"\n"+Role(Values.Text(actor,"role"))+"\nDesktop 1.0";
  }
  private void ShowLogin() {
   sidebar.Visible=false;var page=Page("D-Max Acesso Desktop");var section=Stack();page.Controls.Add(section);
   section.Controls.Add(Label("Entre com seu usuário da planilha",18,true));section.Controls.Add(Label("Aplicativo nativo. Sem navegador local, Python ou controlador de demanda."));
   var url=Input();url.Width=650;url.MaxLength=1000;url.Text=address;
   var name=Input();name.MaxLength=40;var password=Input(true);
   Field(section,"URL publicada da plataforma Google Apps Script (/exec)",url);Field(section,"Login",name);Field(section,"Senha",password);
   var enter=Button("Entrar",()=>{var ignored=Run(async()=>{
    if(platform!=null)platform.Dispose();platform=new Platform(url.Text.Trim());
    var response=await platform.Call("desktop_login",new Dictionary<string,object>{{"name",name.Text.Trim().ToLowerInvariant()},{"password",password.Text}});
    password.Clear();token=Values.Text(response,"token");actor=Values.Object(response,"user");
    if(token.Length!=64||actor==null||!new[]{"developer","commercial","technician"}.Contains(Values.Text(actor,"role")))throw new ServiceError("A plataforma retornou uma sessão inválida.");
    address=platform.Address;Settings.Save(address);simulation=new Simulation();lastTick=Stopwatch.GetTimestamp();lastInput=Stopwatch.GetTimestamp();lastPing=Stopwatch.GetTimestamp();BuildMenu();await ShowClients();
   });});section.Controls.Add(enter);AcceptButton=enter;
   section.Controls.Add(Label("A URL é salva neste computador. Senhas e sessões não são gravadas em disco."));
  }
  private async Task SignOut() {
   var previous=token;ClearSession();ShowLogin();status.Text="Sessão encerrada e simulação descartada.";
   if(platform!=null&&previous.Length>0){try{await platform.Call("desktop_logout",new Dictionary<string,object>{{"token",previous}});}catch{}}
  }
  private async Task ShowClients() {
   var result=await platform.Call("desktop_clients",SessionFields());clients=Values.Rows(result,"clients");
   var page=Page("Visão geral");var tools=Stack();page.Controls.Add(tools);
   search=Input();search.Width=600;Field(tools,"Buscar cliente",search);search.TextChanged+=(s,e)=>RenderClients();
   tools.Controls.Add(Button("Atualizar clientes",()=>{var ignored=Run(ShowClients);}));
   clientCards=new FlowLayoutPanel{FlowDirection=FlowDirection.LeftToRight,WrapContents=true,AutoSize=true,Margin=new Padding(0)};page.Controls.Add(clientCards);RenderClients();
   page.Controls.Add(Label("Acessar cliente abre o D-Max remoto no seu navegador. Entre nele com seu login. Nenhuma senha é enviada pelo botão."));
   if(Values.Text(actor,"role")=="commercial")page.Controls.Add(Label("Comercial: use a simulação local para demonstrar. O login comercial no Raspberry continua isolado dos carregamentos reais."));
  }
  private void RenderClients() {
   if(clientCards==null||clientCards.IsDisposed)return;clientCards.Controls.Clear();var query=(search==null?"":search.Text).Trim();int count=0;
   foreach(var r in clients.OrderBy(r=>Values.Text(r,"site_name"))) {
    string name=Values.Text(r,"site_name"),id=Values.Text(r,"controller_id"),url=Values.Text(r,"url");
    if(query.Length>0&&(name+" "+id).IndexOf(query,StringComparison.OrdinalIgnoreCase)<0)continue;
    if(!Platform.IsClientAddress(url))continue;
    var card=Stack();card.Width=350;card.Margin=new Padding(0,0,18,18);var online=Values.Flag(r,"connected")&&DateTimeOffset.UtcNow.ToUnixTimeSeconds()-Values.Number(r,"updated_at")<=900;
    card.Controls.Add(Label(online?"Conectado · último informe":"Sem conexão recente confirmada"));card.Controls.Add(Label(name,17,true));
    var stamp=Values.Number(r,"updated_at");if(stamp>0&&stamp<253402300799)card.Controls.Add(Label("Último informe: "+DateTimeOffset.FromUnixTimeSeconds((long)stamp).LocalDateTime.ToString("dd/MM/yyyy HH:mm")));
    card.Controls.Add(Button("Acessar cliente",()=>{try{if(!Platform.IsClientAddress(url))throw new InvalidOperationException();Process.Start(new ProcessStartInfo(url){UseShellExecute=true});}catch{MessageBox.Show(this,"Não foi possível abrir o navegador padrão.","D-Max Acesso");}}));
    clientCards.Controls.Add(card);count++;
   }
   if(count==0)clientCards.Controls.Add(Label("Nenhum cliente encontrado."));
  }
  private void ShowSimulation() {
   if(actor==null||simulation==null)return;var page=Page("Simulação");var info=Stack();page.Controls.Add(info);
   info.Controls.Add(Label("Demonstração fictícia e isolada desta sessão",17,true));info.Controls.Add(Label("Baterias de 60 kWh · tempo acelerado 60× · encerra em 100%. Não existe conexão com carregadores reais."));simTotal=Label("",19,true);info.Controls.Add(simTotal);
   var load=new NumericUpDown{Minimum=0,Maximum=1000,DecimalPlaces=1,Increment=1,Width=180,Value=(decimal)simulation.Other};Field(info,"Outras cargas · kW",load);info.Controls.Add(Button("Aplicar carga",()=>{simulation.Other=(double)load.Value;UpdateSimulation();}));
   simCards=new FlowLayoutPanel{WrapContents=true,AutoSize=true};page.Controls.Add(simCards);
   foreach(var port in simulation.Ports) {
    int id=port.Id;var card=Stack();card.Width=350;card.Margin=new Padding(0,0,18,18);card.Controls.Add(Label("Carregador "+(id+1),17,true));Label state=Label(""),soc=Label("",28,true),power=Label("");card.Controls.Add(state);card.Controls.Add(soc);card.Controls.Add(power);
    var connect=Button("",()=>{if(port.Connected)simulation.Disconnect(id);else simulation.Connect(id);UpdateSimulation();});
    var pause=Button("",()=>{port.Paused=!port.Paused;UpdateSimulation();},true);card.Controls.Add(connect);card.Controls.Add(pause);simLabels.Add(new[]{state,soc,power});simButtons.Add(new[]{connect,pause});simCards.Controls.Add(card);
   }
   UpdateSimulation();
  }
  private void UpdateSimulation() {
   if(simulation==null||simCards==null||simCards.IsDisposed)return;simTotal.Text=simulation.Total.ToString("0.0")+" kW · limite fictício 60 kW";
   for(int i=0;i<simulation.Ports.Count&&i<simLabels.Count;i++){var p=simulation.Ports[i];simLabels[i][0].Text=!p.Connected?"Sem veículo":p.Soc>=100?"Carga completa":p.Paused?"Pausado":p.Power>0?"Carregando":"Aguardando potência";simLabels[i][1].Text=p.Soc.ToString("0.0")+"%";simLabels[i][2].Text=p.Power.ToString("0.0")+" kW";simButtons[i][0].Text=p.Connected?"Desconectar":"Conectar veículo";simButtons[i][1].Text=p.Paused?"Retomar":"Pausar";simButtons[i][1].Visible=p.Connected;}
  }
  private async Task ShowMembers() {
   if(!IsDeveloper)return;var result=await platform.Call("desktop_members",SessionFields());members=Values.Rows(result,"users");
   var page=Page("Usuários");var top=Stack();page.Controls.Add(top);top.Controls.Add(Label("Gestão completa pelo desenvolvedor",17,true));top.Controls.Add(Label("Crie, edite, bloqueie, exclua ou reative membros. Cada alteração exige novamente sua senha."));
   top.Controls.Add(Button("Criar novo membro",()=>EditMember(null)));top.Controls.Add(Button("Atualizar membros",()=>{var ignored=Run(ShowMembers);},true));
   var grid=new DataGridView{Height=360,ReadOnly=true,AllowUserToAddRows=false,AllowUserToDeleteRows=false,AutoSizeColumnsMode=DataGridViewAutoSizeColumnsMode.Fill,SelectionMode=DataGridViewSelectionMode.FullRowSelect,MultiSelect=false,RowHeadersVisible=false,BackgroundColor=Color.White,BorderStyle=BorderStyle.None};
   grid.Columns.Add("id","ID");grid.Columns.Add("name","Nome");grid.Columns.Add("login","Login");grid.Columns.Add("role","Perfil");grid.Columns.Add("status","Situação");
   foreach(var r in members){int index=grid.Rows.Add(Values.Text(r,"id"),Values.Text(r,"full_name"),Values.Text(r,"name"),Role(Values.Text(r,"role")),Values.Flag(r,"deleted")?"Excluído":Values.Flag(r,"active")?"Ativo":"Bloqueado");grid.Rows[index].Tag=r;}
   page.Controls.Add(grid);var edit=Button("Editar membro selecionado",()=>{if(grid.CurrentRow!=null)EditMember(grid.CurrentRow.Tag as Dictionary<string,object>);});page.Controls.Add(edit);grid.CellDoubleClick+=(s,e)=>{if(e.RowIndex>=0)EditMember(grid.Rows[e.RowIndex].Tag as Dictionary<string,object>);};
  }
  private void EditMember(Dictionary<string,object> old) {
   if(!IsDeveloper)return;
   using(var dialog=new Form{Text=old==null?"Novo membro":"Editar membro",Width=700,Height=800,MinimumSize=new Size(620,650),StartPosition=FormStartPosition.CenterParent,Font=Font,BackColor=background}) {
    var scroll=new Panel{Dock=DockStyle.Fill,AutoScroll=true,Padding=new Padding(15)};var form=Stack();form.Dock=DockStyle.Top;scroll.Controls.Add(form);dialog.Controls.Add(scroll);
    var id=Input();id.ReadOnly=true;id.Text=old==null?"":Values.Text(old,"id");var full=Input();full.MaxLength=100;full.Text=old==null?"":Values.Text(old,"full_name");var name=Input();name.MaxLength=40;name.Text=old==null?"":Values.Text(old,"name");name.ReadOnly=old!=null;
    var role=new ComboBox{Width=480,DropDownStyle=ComboBoxStyle.DropDownList};role.Items.AddRange(new object[]{"Desenvolvedor","Comercial","Técnico"});role.SelectedIndex=old==null?1:Values.Text(old,"role")=="developer"?0:Values.Text(old,"role")=="commercial"?1:2;
    var situation=new ComboBox{Width=480,DropDownStyle=ComboBoxStyle.DropDownList};situation.Items.AddRange(new object[]{"Ativo","Bloqueado","Excluído"});situation.SelectedIndex=old==null?0:Values.Flag(old,"deleted")?2:Values.Flag(old,"active")?0:1;
    var expires=new DateTimePicker{Format=DateTimePickerFormat.Short,ShowCheckBox=true,Checked=false,Width=250};if(old!=null&&Values.Number(old,"expires_at")>0){expires.Value=DateTimeOffset.FromUnixTimeSeconds((long)Values.Number(old,"expires_at")).LocalDateTime;expires.Checked=true;}
    var password=Input(true);var confirmation=Input(true);var current=Input(true);
    Field(form,"ID · automático para novo membro",id);Field(form,"Nome completo",full);Field(form,"Login",name);Field(form,"Perfil",role);Field(form,"Situação",situation);Field(form,"Validade · desmarcado não expira",expires);Field(form,"Nova senha · 8 a 200 caracteres; vazio mantém",password);Field(form,"Confirme a nova senha",confirmation);Field(form,"Sua senha de desenvolvedor · autorizar alteração",current);
    var save=Button("Salvar na planilha e gerar verificador",()=>{});save.Click+=async(s,e)=>{
     if(password.Text!=confirmation.Text){MessageBox.Show(dialog,"As novas senhas não coincidem.");return;}
     if((old==null||password.Text.Length>0)&&(password.Text.Length<8||password.Text.Length>200)){MessageBox.Show(dialog,"A nova senha deve ter de 8 a 200 caracteres.");return;}
     if(current.Text.Length==0){MessageBox.Show(dialog,"Informe sua senha de desenvolvedor.");return;}
     save.Enabled=false;status.Text="Confirmando alteração na planilha...";
     try {
      var fields=new Dictionary<string,object>{{"id",id.Text},{"full_name",full.Text.Trim()},{"name",name.Text.Trim().ToLowerInvariant()},{"role",new[]{"developer","commercial","technician"}[role.SelectedIndex]},{"status",new[]{"ativo","bloqueado","excluido"}[situation.SelectedIndex]},{"expires",expires.Checked?expires.Value.ToString("yyyy-MM-dd"):""},{"password",password.Text},{"confirmation",confirmation.Text},{"actor_password",current.Text}};
      var response=await platform.Call("desktop_save_user",new Dictionary<string,object>{{"token",token},{"fields",fields}});current.Clear();password.Clear();confirmation.Clear();
      using(var result=new Form{Text="Alteração confirmada na planilha",Width=650,Height=250,StartPosition=FormStartPosition.CenterParent}){var area=new TextBox{Dock=DockStyle.Fill,Multiline=true,ReadOnly=true,Text=Values.Text(response,"verifier"),Font=new Font("Consolas",10),ScrollBars=ScrollBars.Vertical};result.Controls.Add(area);result.ShowDialog(dialog);}
      dialog.DialogResult=DialogResult.OK;dialog.Close();
     }catch(ServiceError error){MessageBox.Show(dialog,error.Message,"Não foi possível salvar");if(error.Code==401){ClearSession();dialog.Close();ShowLogin();}}
     catch{MessageBox.Show(dialog,"Não foi possível salvar. Confira a conexão e tente novamente.");}
     finally{current.Clear();if(!save.IsDisposed)save.Enabled=true;}
    };form.Controls.Add(save);form.Controls.Add(Label("Para mudar o login, crie outra conta e exclua a anterior. Reativar mantém o mesmo ID e login."));
    if(dialog.ShowDialog(this)==DialogResult.OK&&actor!=null){var ignored=Run(ShowMembers);}
   }
  }
  private void ShowSettings() {
   if(!IsDeveloper)return;var page=Page("Configurações");var box=Stack();page.Controls.Add(box);box.Controls.Add(Label("Plataforma desta instalação",17,true));var input=Input();input.Width=700;input.MaxLength=1000;input.Text=address;Field(box,"URL Google Apps Script (/exec)",input);
   box.Controls.Add(Button("Salvar URL e sair",()=>{var ignored=Run(async()=>{using(var test=new Platform(input.Text.Trim())){Settings.Save(test.Address);address=test.Address;}await SignOut();});}));box.Controls.Add(Label("Somente o endereço público é salvo neste computador. Senhas, verificadores e sessões não são persistidos."));
  }
  private async Task Tick() {
   if(actor==null||simulation==null)return;long now=Stopwatch.GetTimestamp();var seconds=Math.Max(0,(now-lastTick)/(double)Stopwatch.Frequency);lastTick=now;simulation.Advance(seconds);UpdateSimulation();
   if(Values.Text(actor,"role")=="commercial"&&(now-lastInput)/(double)Stopwatch.Frequency>=900&&!busy){await Run(SignOut);return;}
   if((now-lastPing)/(double)Stopwatch.Frequency>=60&&!busy){lastPing=now;await Run(async()=>{var result=await platform.Call("desktop_state",SessionFields());actor=Values.Object(result,"user");if(actor==null)throw new ServiceError("Sessão inválida.",401);});}
  }
 }
}
