package com.energycube.dmax;
import android.app.*;
import android.os.*;
import android.content.*;
import android.graphics.Color;
import android.net.Uri;
import android.webkit.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.concurrent.*;
import org.json.*;

public final class MainActivity extends Activity {
 private WebView central,remote;private LinearLayout layout,bar;private String clientOrigin;
 private final ExecutorService worker=Executors.newSingleThreadExecutor();private Session session;private boolean destroyed;
 private ValueCallback<Uri[]> fileCallback;
 @Override public void onCreate(Bundle state){super.onCreate(state);WebView.setWebContentsDebuggingEnabled(false);
  android.content.SharedPreferences prefs=getSharedPreferences("platform",MODE_PRIVATE);
  session=new Session(new Platform(),new Session.Settings(){public String get(){return prefs.getString("url",Policy.DEFAULT_PLATFORM);}public void put(String value){prefs.edit().putString("url",value).commit();}});
  CookieManager.getInstance().removeAllCookies(null);
  layout=new LinearLayout(this);layout.setOrientation(LinearLayout.VERTICAL);layout.setBackgroundColor(Color.WHITE);layout.setFitsSystemWindows(true);setContentView(layout);
  central=new WebView(this);configure(central);central.addJavascriptInterface(new Bridge(),"DMaxNative");central.setWebViewClient(new WebViewClient(){
   @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){return local(request.getUrl().toString());}
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !request.getUrl().toString().equals(Policy.HOME);}
   @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())toast("Não foi possível abrir a central local.");}
  });layout.addView(central,new LinearLayout.LayoutParams(-1,0,1));central.loadUrl(Policy.HOME);
 }
 @SuppressWarnings("deprecation") private void configure(WebView view){WebSettings s=view.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(false);s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setAllowFileAccessFromFileURLs(false);s.setAllowUniversalAccessFromFileURLs(false);s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setJavaScriptCanOpenWindowsAutomatically(false);s.setSupportMultipleWindows(false);s.setSaveFormData(false);s.setGeolocationEnabled(false);s.setCacheMode(WebSettings.LOAD_NO_CACHE);CookieManager.getInstance().setAcceptThirdPartyCookies(view,false);}
 private WebResourceResponse local(String address){
  try{Uri u=Uri.parse(address);if(!"https".equals(u.getScheme())||!"app.dmax.local".equals(u.getHost())||u.getPort()!=-1)return blocked();String path=u.getPath();String file=path.equals("/")?"index.html":path.equals("/assets/app.js")?"app.js":path.equals("/assets/style.css")?"style.css":path.equals("/assets/d-max-logo.png")?"d-max-logo.png":null;if(file==null)return blocked();String mime=file.endsWith(".js")?"application/javascript":file.endsWith(".css")?"text/css":file.endsWith(".png")?"image/png":"text/html";
   java.util.Map<String,String> headers=new java.util.HashMap<>();headers.put("Cache-Control","no-store");headers.put("Content-Security-Policy","default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'none'; frame-src 'none'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'; object-src 'none'");headers.put("X-Content-Type-Options","nosniff");return new WebResourceResponse(mime,"UTF-8",200,"OK",headers,getAssets().open(file));
  }catch(Exception e){return blocked();}
 }
 private WebResourceResponse blocked(){return new WebResourceResponse("text/plain","UTF-8",403,"Forbidden",java.util.Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));}
 private final class Bridge {
  @JavascriptInterface public void request(String id,String name,String args){
   if(id==null||!id.matches("[0-9]{1,10}")||name==null||name.length()>40||args==null||args.length()>24000)return;
   worker.execute(()->{JSONObject reply;String destination=null;try{
    reply=session.dispatch(name,new JSONArray(args));if(name.equals("portalOpenClient")){destination=reply.getString("url");reply.remove("url");}
   }catch(Platform.Failure e){reply=failure(e.code,e.getMessage());}catch(Exception e){reply=failure(422,"Dados inválidos para esta operação.");}
   final String result=reply.toString(),url=destination;
   runOnUiThread(()->{if(destroyed)return;Runnable respond=()->{if(destroyed)return;central.evaluateJavascript("window.dmaxReply("+JSONObject.quote(id)+","+result+")",null);if(url!=null)openClient(url);};if(name.equals("portalLogin")||name.equals("portalLogout")||name.equals("saveSettings"))CookieManager.getInstance().removeAllCookies(ignored->respond.run());else respond.run();});
   });
  }
 }
 private JSONObject failure(int code,String message){JSONObject result=new JSONObject();try{result.put("ok",false).put("code",code).put("message",message);}catch(JSONException ignored){}return result;}
 private void openClient(String address){if(!Policy.ticket(address)){toast("Passe de acesso inválido.");return;}closeClient();clientOrigin=Policy.clientOrigin(address);central.setVisibility(View.GONE);
  bar=new LinearLayout(this);bar.setPadding(12,8,12,8);bar.setBackgroundColor(Color.WHITE);bar.setElevation(8);Button back=new Button(this);back.setText("‹ Voltar à central");styleButton(back,true);back.setOnClickListener(v->closeClient());bar.addView(back);Button reload=new Button(this);reload.setText("Recarregar");styleButton(reload,false);reload.setOnClickListener(v->{if(remote!=null)remote.reload();});bar.addView(reload);layout.addView(bar,0);
  remote=new WebView(this);configure(remote);remote.getSettings().setDomStorageEnabled(true);remote.getSettings().setAllowContentAccess(true);remote.setWebViewClient(new WebViewClient(){
   @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){if(Policy.sameClient(request.getUrl().toString(),clientOrigin))return false;toast("Este link não pertence ao cliente aberto.");return true;}
   @Override public WebResourceResponse shouldInterceptRequest(WebView view,WebResourceRequest request){return Policy.sameClient(request.getUrl().toString(),clientOrigin)?null:blocked();}
   @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame())showClientError();}
   @Override public void onReceivedHttpError(WebView view,WebResourceRequest request,WebResourceResponse response){if(request.isForMainFrame()&&response.getStatusCode()>=400)showClientError();}
  });
  remote.setWebChromeClient(new WebChromeClient(){@Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){if(fileCallback!=null)fileCallback.onReceiveValue(null);fileCallback=callback;Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT);pick.addCategory(Intent.CATEGORY_OPENABLE);pick.setType("*/*");try{startActivityForResult(pick,27);return true;}catch(Exception e){fileCallback=null;return false;}}});
  remote.setDownloadListener((url,agent,disposition,mime,length)->download(url,agent,disposition,mime));layout.addView(remote,new LinearLayout.LayoutParams(-1,0,1));remote.loadUrl(address);
 }
 private void styleButton(Button button,boolean primary){button.setAllCaps(false);button.setTextSize(13);button.setTextColor(primary?Color.WHITE:Color.rgb(18,61,103));android.graphics.drawable.GradientDrawable shape=new android.graphics.drawable.GradientDrawable();shape.setColor(primary?Color.rgb(8,127,227):Color.rgb(234,242,250));shape.setCornerRadius(12*getResources().getDisplayMetrics().density);button.setBackground(shape);button.setPadding(22,12,22,12);LinearLayout.LayoutParams size=new LinearLayout.LayoutParams(-2,-2);size.setMargins(0,0,12,0);button.setLayoutParams(size);}
 private void download(String url,String agent,String disposition,String mime){if(!Policy.sameClient(url,clientOrigin)){toast("Download externo recusado.");return;}try{DownloadManager.Request request=new DownloadManager.Request(Uri.parse(url));String cookies=CookieManager.getInstance().getCookie(url);if(cookies!=null)request.addRequestHeader("Cookie",cookies);request.addRequestHeader("User-Agent",agent);request.setMimeType(mime);request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,URLUtil.guessFileName(url,disposition,mime));((DownloadManager)getSystemService(DOWNLOAD_SERVICE)).enqueue(request);toast("Arquivo enviado para Downloads.");}catch(Exception e){toast("Não foi possível baixar o arquivo.");}}
 private void showClientError(){toast("Cliente indisponível. Volte à central e tente acessar novamente.");}
 private void closeClient(){if(fileCallback!=null){fileCallback.onReceiveValue(null);fileCallback=null;}if(remote!=null){remote.stopLoading();layout.removeView(remote);remote.destroy();remote=null;}if(bar!=null){layout.removeView(bar);bar=null;}clientOrigin=null;if(central!=null)central.setVisibility(View.VISIBLE);}
 private void toast(String text){runOnUiThread(()->{if(!destroyed)Toast.makeText(this,text,Toast.LENGTH_LONG).show();});}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==27&&fileCallback!=null){fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));fileCallback=null;}}
 @Override public void onBackPressed(){if(remote!=null){closeClient();return;}new AlertDialog.Builder(this).setMessage("Sair do D-Max e encerrar a sessão neste aplicativo?").setNegativeButton("Continuar",null).setPositiveButton("Sair",(d,w)->{central.evaluateJavascript("document.getElementById('logout').click()",null);finish();}).show();}
 @Override protected void onDestroy(){destroyed=true;closeClient();if(central!=null){central.removeJavascriptInterface("DMaxNative");central.destroy();}worker.execute(()->{try{session.dispatch("portalLogout",new JSONArray());}catch(Exception ignored){}session.clear();});worker.shutdown();CookieManager.getInstance().removeAllCookies(null);super.onDestroy();}
}
