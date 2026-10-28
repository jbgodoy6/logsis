package br.com.sistel.logsis;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.view.Gravity;
import android.view.View;
import android.webkit.HttpAuthHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Restricted programming workspace. No Grafana exporter or write endpoint guesses. */
public final class TechnicianActivity extends Activity {
    private static final int PICK_BIN=71,SAVE_BIN=72,WIFI_PERMISSION=73;
    private final TechnicianAuth auth=new TechnicianAuth();
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private DeviceConnection connection;
    private LinearLayout screen;
    private WebView web;
    private TextView status;
    private ValueCallback<Uri[]> upload;
    private byte[] generated;
    private boolean closed;
    private long revision;
    private final Runnable periodic=new Runnable(){public void run(){
        if(closed||!auth.hasSession()){if(!closed)lock("Entre novamente para continuar.");return;}
        long expected=revision;
        worker.execute(()->{boolean ok=auth.verify();runOnUiThread(()->{
            if(closed||expected!=revision)return;
            if(!ok)lock("Não foi possível confirmar a autorização do técnico.");
            else handler.postDelayed(periodic,30000);
        });});
    }};

    @Override public void onCreate(Bundle state){super.onCreate(state);showLogin("");}
    private void setRoot(View root){
        getWindow().setStatusBarColor(Color.WHITE);getWindow().setNavigationBarColor(Color.WHITE);
        setContentView(root);
        if(android.os.Build.VERSION.SDK_INT>=30){
            getWindow().setDecorFitsSystemWindows(false);
            root.setOnApplyWindowInsetsListener((v,insets)->{
                android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout());
                android.graphics.Insets ime=insets.getInsets(android.view.WindowInsets.Type.ime());
                v.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));return insets;
            });
            android.view.WindowInsetsController c=getWindow().getInsetsController();
            if(c!=null)c.setSystemBarsAppearance(android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
                    android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS|android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        }else root.setFitsSystemWindows(true);
    }
    private int dp(int n){return Math.round(getResources().getDisplayMetrics().density*n);}
    private TextView text(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(Color.rgb(20,45,70));t.setPadding(0,dp(8),0,dp(8));return t;}
    private void page(String title){
        screen=new LinearLayout(this);screen.setOrientation(LinearLayout.VERTICAL);screen.setPadding(dp(22),dp(30),dp(22),dp(22));screen.setBackgroundColor(Color.WHITE);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(screen);setRoot(scroll);
        TextView brand=text("LOGSIS / SISTEL",14);brand.setTextColor(Color.rgb(0,113,199));screen.addView(brand);
        TextView heading=text(title,28);heading.setTypeface(Typeface.DEFAULT,Typeface.BOLD);screen.addView(heading);
    }
    private Button button(String label,Runnable action){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextColor(Color.WHITE);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(0,113,199)));screen.addView(b,new LinearLayout.LayoutParams(-1,dp(54)));b.setOnClickListener(v->action.run());return b;}
    private EditText input(String hint,int type){EditText edit=new EditText(this);edit.setHint(hint);edit.setInputType(type);edit.setSingleLine(true);screen.addView(edit,new LinearLayout.LayoutParams(-1,dp(58)));return edit;}
    private void showLogin(String message){
        page("Área técnica");screen.addView(text("Entre para programar o equipamento.",15));
        EditText login=input("Login do técnico",android.text.InputType.TYPE_CLASS_TEXT);
        EditText password=input("Senha",android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        status=text(message,14);screen.addView(status);
        Button enter=button("Validar acesso",()->{
            String user=login.getText().toString().trim(),secret=password.getText().toString();password.setText("");
            if(user.isEmpty()||secret.isEmpty()){status.setText("Informe login e senha.");return;}
            status.setText("Validando técnico…");
            worker.execute(()->{try{String name=auth.login(user,secret);runOnUiThread(()->{if(!closed){showWorkspace(name);handler.postDelayed(periodic,30000);}});}
                catch(Exception e){runOnUiThread(()->{if(!closed)status.setText(e.getMessage());});}});
        });
        if(!TechnicianAuth.configured()){
            enter.setEnabled(false);login.setEnabled(false);password.setEnabled(false);
            status.setText("A área técnica aguarda a ativação do serviço de cadastro pelo administrador. O acesso ao sistema LogSis continua disponível na tela inicial.");
        }
        button("Voltar",this::finish);
    }
    private void showWorkspace(String name){
        if(connection==null)connection=new DeviceConnection(this,auth);
        connection.prepareInternet();
        page("Programar LogSis");screen.addView(text("Técnico: "+name,15));
        screen.addView(text("Conecte à rede LOGSIS do equipamento. O Android apresentará as redes disponíveis para sua escolha.",15));
        status=text("A configuração será enviada pelas telas do próprio equipamento.",14);screen.addView(status);
        button("Conectar ao equipamento",this::connect);
        button("Gerar BIN da biblioteca",()->pickLibrary(false));
        button("Atualizar biblioteca",this::syncLibrary);
        button("Encerrar acesso técnico",()->lock("Sessão encerrada."));
    }
    private void connect(){
        if(connection==null)connection=new DeviceConnection(this,auth);
        if(!connection.permissionGranted()){requestPermissions(DeviceConnection.permissions(),WIFI_PERMISSION);return;}
        status.setText("Confirme a rede LOGSIS na solicitação do Android.");
        connection.connect(new DeviceConnection.Listener(){
            public void connected(){if(!closed)showEquipment();}
            public void failed(String message){if(!closed){if(web!=null){web.stopLoading();web.destroy();web=null;showWorkspace("Sessão autorizada");}status.setText(message);}}
        });
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);
        if(code==WIFI_PERMISSION&&results.length>0){if(results[0]==PackageManager.PERMISSION_GRANTED)connect();else status.setText("É necessário permitir a conexão Wi-Fi para acessar o equipamento.");}
    }
    private void showEquipment(){
        if(web!=null){web.destroy();web=null;}
        LinearLayout layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setBackgroundColor(Color.WHITE);
        LinearLayout bar=new LinearLayout(this);bar.setGravity(Gravity.CENTER_VERTICAL);
        Button back=new Button(this);back.setText("Voltar");bar.addView(back);back.setOnClickListener(v->lock("Conexão encerrada."));
        TextView title=text("LogSis · equipamento",16);bar.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        Button info=new Button(this);info.setText("Acesso");bar.addView(info);info.setOnClickListener(v->new AlertDialog.Builder(this).setTitle("Acesso ao equipamento")
                .setMessage("Usuário: "+DevicePolicy.DEVICE_USER+"\nSenha: "+DevicePolicy.DEVICE_PASSWORD+"\n\nNavegue até o envio da configuração e toque no campo de arquivo para escolher o BIN.")
                .setPositiveButton("Entendi",null).show());
        layout.addView(bar);web=new WebView(this);layout.addView(web,new LinearLayout.LayoutParams(-1,0,1));setRoot(layout);
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);settings.setSupportMultipleWindows(false);settings.setGeolocationEnabled(false);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);settings.setUseWideViewPort(true);settings.setLoadWithOverviewMode(true);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !DevicePolicy.local(request.getUrl().toString());}
            @Override public boolean shouldOverrideUrlLoading(WebView view,String url){return !DevicePolicy.local(url);}
            @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){
                if(!DevicePolicy.local(request.getUrl().toString()))return denied();
                // Recheck every page navigation and state-changing request, on the
                // interception worker thread, using the Internet Network (not AP).
                if(!auth.hasSession()||(!DevicePolicy.passiveAsset(request.getUrl().toString(),request.getMethod(),request.isForMainFrame())&&!auth.verify())){
                    runOnUiThread(()->{if(!closed)lock("Autorização não confirmada. A operação foi bloqueada.");});return denied();
                }
                return null;
            }
            @Override public void onReceivedHttpAuthRequest(WebView view,HttpAuthHandler handler,String host,String realm){
                if("192.168.4.1".equals(host)&&auth.hasSession())handler.proceed(DevicePolicy.DEVICE_USER,DevicePolicy.DEVICE_PASSWORD);else handler.cancel();
            }
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                cancelUpload();upload=callback;
                if(!DevicePolicy.local(view.getUrl())||!auth.hasSession()){cancelUpload();return true;}
                new AlertDialog.Builder(TechnicianActivity.this).setTitle("Selecionar configuração BIN")
                        .setItems(new String[]{"Biblioteca LogSis","Arquivos do celular"},(d,n)->{if(n==0)pickLibrary(true);else chooseFile();})
                        .setOnCancelListener(d->cancelUpload()).show();return true;
            }
        });
        web.loadUrl(DevicePolicy.HOME);
    }
    private WebResourceResponse denied(){
        return new WebResourceResponse("text/plain","utf-8",403,"Forbidden",java.util.Collections.emptyMap(),
                new ByteArrayInputStream("Operação não autorizada. Retorne ao aplicativo.".getBytes(StandardCharsets.UTF_8)));
    }
    private void chooseFile(){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
        try{startActivityForResult(intent,PICK_BIN);}catch(android.content.ActivityNotFoundException e){cancelUpload();toast("Seletor de arquivos indisponível.");}
    }
    private void pickLibrary(boolean forUpload){
        try{
            List<BinLibrary.Entry> entries=BinLibrary.entries(this);String[] labels=new String[entries.size()];
            for(int i=0;i<labels.length;i++)labels[i]=entries.get(i).toString();
            new AlertDialog.Builder(this).setTitle("Modelo do controlador").setItems(labels,(d,index)->{
                BinLibrary.Entry entry=entries.get(index);
                LinearLayout form=new LinearLayout(this);form.setOrientation(LinearLayout.VERTICAL);form.setPadding(dp(20),0,dp(20),0);
                EditText id=configField(form,"Slave ID · 1 a 247","10",false);
                EditText[] nominal=new EditText[4];
                if(entry.updatedFile==null){
                    String[] labelsNominal={"Tensão L–L · V","Frequência · Hz","Bateria · V","Rotação · rpm"};
                    String[] initial={"380","60","24","1800"};
                    for(int i=0;i<4;i++)nominal[i]=configField(form,labelsNominal[i],initial[i],false);
                }else form.addView(text("Perfil atualizado: os limites definidos na biblioteca serão preservados.",13));
                android.widget.Spinner mode=new android.widget.Spinner(this);
                mode.setAdapter(new android.widget.ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,
                        new String[]{"Manter ajustes de conexão do BIN","Wi-Fi","4G · configurar no equipamento"}));
                form.addView(mode);EditText ssid=configField(form,"Wi-Fi · nome da rede","",true);
                EditText wifiPassword=configField(form,"Wi-Fi · senha","",true);wifiPassword.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
                ssid.setVisibility(View.GONE);wifiPassword.setVisibility(View.GONE);
                TextView apn=text("Configure a operadora e o APN nas telas do equipamento após carregar o BIN.",13);apn.setVisibility(View.GONE);form.addView(apn);
                mode.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){
                    public void onItemSelected(android.widget.AdapterView<?> p,View v,int n,long item){ssid.setVisibility(n==1?View.VISIBLE:View.GONE);wifiPassword.setVisibility(n==1?View.VISIBLE:View.GONE);apn.setVisibility(n==2?View.VISIBLE:View.GONE);}
                    public void onNothingSelected(android.widget.AdapterView<?> p){}
                });
                ScrollView scroll=new ScrollView(this);scroll.addView(form);
                new AlertDialog.Builder(this).setTitle("Configuração · "+entry.label)
                        .setView(scroll).setNegativeButton("Cancelar",(x,n)->{if(forUpload)cancelUpload();})
                        .setPositiveButton("Preparar BIN",(x,n)->{
                            try{
                                int slave=Integer.parseInt(id.getText().toString());double[] values={380,60,24,1800};
                                if(entry.updatedFile==null)for(int i=0;i<4;i++)values[i]=Double.parseDouble(nominal[i].getText().toString().replace(',','.'));
                                generated=BinLibrary.preset(this,entry,slave,values);
                                generated=BinDocument.read(generated).render(java.util.Collections.singletonMap("WIFI_AP_PWD",DevicePolicy.WIFI_PASSWORD));
                                if(mode.getSelectedItemPosition()==1){
                                    String network=ssid.getText().toString(),secret=wifiPassword.getText().toString();
                                    int length=network.getBytes(StandardCharsets.UTF_8).length;
                                    if(length<1||length>32)throw new IllegalArgumentException("SSID inválido.");
                                    java.util.Map<String,String> changes=new java.util.LinkedHashMap<>();
                                    changes.put("SYS_USE_WIFI","1");changes.put("SYS_USE_GSM","0");changes.put("SYS_USE_PPPOS","0");
                                    changes.put("WIFI_STA_SSID",network);changes.put("WIFI_STA_PWD",secret);
                                    generated=BinDocument.read(generated).render(changes);
                                    wifiPassword.setText("");
                                }
                                if(forUpload){File file=store(generated,entries.get(index).model);deliver(Uri.parse("content://"+getPackageName()+".bins/"+file.getName()));generated=null;}
                                else startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                                        .setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE,"LOGSIS_"+entries.get(index).model+".bin"),SAVE_BIN);
                            }catch(Exception e){generated=null;if(forUpload)cancelUpload();toast("Não foi possível preparar o BIN. Confira o Slave ID e a biblioteca.");}
                        }).setOnCancelListener(x->{if(forUpload)cancelUpload();}).show();
            }).setOnCancelListener(d->{if(forUpload)cancelUpload();}).show();
        }catch(Exception e){if(forUpload)cancelUpload();toast("Não foi possível abrir a biblioteca.");}
    }
    private EditText configField(LinearLayout form,String caption,String initial,boolean word){
        EditText edit=new EditText(this);edit.setHint(caption);edit.setSingleLine(true);edit.setText(initial);
        edit.setInputType(word?android.text.InputType.TYPE_CLASS_TEXT:android.text.InputType.TYPE_CLASS_NUMBER|android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL);
        form.addView(text(caption,12));form.addView(edit,new LinearLayout.LayoutParams(-1,dp(52)));return edit;
    }
    private File store(byte[] bytes,String model) throws Exception {
        File folder=new File(getCacheDir(),"bins");if(!folder.isDirectory()&&!folder.mkdirs())throw new java.io.IOException();
        File file=new File(folder,"LOGSIS_"+model+"_"+UUID.randomUUID().toString()+".bin");
        try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}return file;
    }
    private void deliver(Uri uri){
        ValueCallback<Uri[]> pending=upload;upload=null;
        if(pending==null)return;
        long expected=revision;
        worker.execute(()->{boolean allowed=auth.verify();runOnUiThread(()->{
            boolean current=!closed&&expected==revision&&auth.hasSession()&&web!=null;
            pending.onReceiveValue(current&&allowed?new Uri[]{uri}:null);
            if(!closed&&expected==revision&&!allowed)lock("Não foi possível confirmar sua autorização para enviar o BIN.");
        });});
    }
    @Override protected void onActivityResult(int code,int result,Intent data){
        super.onActivityResult(code,result,data);
        if(code==PICK_BIN){
            if(result!=RESULT_OK||data==null||data.getData()==null){cancelUpload();return;}
            Uri uri=data.getData();
            if(!"content".equals(uri.getScheme())){cancelUpload();toast("Arquivo inválido.");return;}
            String name="";
            try(android.database.Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);
            }catch(Exception ignored){}
            if(name==null||!name.toLowerCase(java.util.Locale.ROOT).endsWith(".bin")){cancelUpload();toast("Escolha um arquivo .bin.");return;}
            deliver(uri);
        }else if(code==SAVE_BIN){
            byte[] bytes=generated;generated=null;
            if(bytes!=null&&result==RESULT_OK&&data!=null&&data.getData()!=null&&"content".equals(data.getData().getScheme())){
                worker.execute(()->{
                    if(!auth.verify()){runOnUiThread(()->lock("Autorização não confirmada."));return;}
                    try(java.io.OutputStream out=getContentResolver().openOutputStream(data.getData())){if(out==null)throw new java.io.IOException();out.write(bytes);runOnUiThread(()->toast("BIN salvo."));}
                    catch(Exception e){runOnUiThread(()->toast("Não foi possível salvar o BIN."));}
                });
            }
        }
    }
    private void syncLibrary(){
        status.setText("Consultando biblioteca…");
        worker.execute(()->{try{int count=LibraryUpdate.sync(this,auth);runOnUiThread(()->{if(!closed)status.setText(count+" modelos atualizados. A biblioteca do Studio permanece disponível.");});}
            catch(Exception e){runOnUiThread(()->{if(!closed)status.setText(e.getMessage());});}});
    }
    private void cancelUpload(){if(upload!=null){upload.onReceiveValue(null);upload=null;}}
    private void toast(String message){if(!closed)Toast.makeText(this,message,Toast.LENGTH_LONG).show();}
    private void lock(String message){
        revision++;
        handler.removeCallbacks(periodic);auth.clear();cancelUpload();generated=null;
        if(web!=null){web.stopLoading();web.destroy();web=null;}
        if(connection!=null){connection.close();connection=null;}
        if(!closed)showLogin(message);
    }
    @Override public void onBackPressed(){
        if(web!=null&&web.canGoBack()){web.goBack();return;}
        lock("Sessão encerrada.");finish();
    }
    @Override protected void onDestroy(){closed=true;lock("");worker.shutdown();super.onDestroy();}
}
