package br.com.sistel.logsis;

import android.content.Intent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.Shadows;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk={28,35})
public class TechnicianActivityTest {
 private View find(View v,String label){
  if(v instanceof TextView&&label.contentEquals(((TextView)v).getText()))return v;
  if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++){View found=find(g.getChildAt(i),label);if(found!=null)return found;}}
  return null;
 }
 @Test public void homeHasSeparateTechnicianEntry(){
  try(org.robolectric.android.controller.ActivityController<MainActivity> c=Robolectric.buildActivity(MainActivity.class).setup()){
   MainActivity activity=c.get();find(activity.getWindow().getDecorView(),"Área técnica").performClick();
   Intent intent=Shadows.shadowOf(activity).getNextStartedActivity();
   assertEquals(TechnicianActivity.class.getName(),intent.getComponent().getClassName());
  }
 }
 @Test public void missingServiceNeverGrantsProgrammingAccess(){
  try(org.robolectric.android.controller.ActivityController<TechnicianActivity> c=Robolectric.buildActivity(TechnicianActivity.class).setup()){
   Button enter=(Button)find(c.get().getWindow().getDecorView(),"Validar acesso");
   assertNotNull(enter);assertEquals(TechnicianAuth.configured(),enter.isEnabled());
   assertNull(find(c.get().getWindow().getDecorView(),"Conectar ao equipamento"));
  }
 }
 @Test public void packagedLibraryHasAllSeventeenStudioProfiles()throws Exception{
  android.content.Context context=org.robolectric.RuntimeEnvironment.getApplication();
  java.util.List<BinLibrary.Entry> entries=BinLibrary.entries(context);assertEquals(17,entries.size());
  for(BinLibrary.Entry entry:entries){
   java.util.Map<String,String> params=BinDocument.read(BinLibrary.preset(context,entry,247)).values();
   assertEquals("247",params.get("MDBA_ID0"));assertTrue(params.containsKey("MDBA_ADDR99"));
   if(entry.model.equals("DSE7420")){assertEquals("48653",params.get("MDBA_ADDR51"));assertEquals("48654",params.get("MDBA_ADDR52"));}
  }
 }
 @Test public void generatedBinProviderIsReadOnlyAndRejectsTraversal()throws Exception{
  android.content.Context context=org.robolectric.RuntimeEnvironment.getApplication();
  BinProvider provider=new BinProvider();android.content.pm.ProviderInfo info=new android.content.pm.ProviderInfo();
  info.authority=context.getPackageName()+".bins";provider.attachInfo(context,info);
  java.io.File folder=new java.io.File(context.getCacheDir(),"bins");folder.mkdirs();
  java.io.File file=new java.io.File(folder,"test.bin");
  try(java.io.FileOutputStream out=new java.io.FileOutputStream(file)){out.write(new byte[]{1,2,3});}
  android.net.Uri uri=android.net.Uri.parse("content://"+info.authority+"/test.bin");
  try(android.os.ParcelFileDescriptor descriptor=provider.openFile(uri,"r")){assertNotNull(descriptor);}
  assertThrows(java.io.FileNotFoundException.class,()->provider.openFile(uri,"w"));
  assertThrows(java.io.FileNotFoundException.class,()->provider.openFile(android.net.Uri.parse("content://"+info.authority+"/..%2Ftest.bin"),"r"));
 }
}
