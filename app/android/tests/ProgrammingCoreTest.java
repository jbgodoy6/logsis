import br.com.sistel.logsis.BinDocument;
import br.com.sistel.logsis.DevicePolicy;
import java.nio.charset.StandardCharsets;
import java.nio.charset.Charset;
import java.util.*;

public class ProgrammingCoreTest {
 private static int checks;
 private static void check(boolean b,String label){checks++;if(!b)throw new AssertionError(label);}
 private static void rejects(Runnable r){checks++;try{r.run();throw new AssertionError("Expected rejection");}catch(IllegalArgumentException expected){}}
 public static void main(String[] args)throws Exception {
  for(String url:new String[]{"http://192.168.4.1/","http://192.168.4.1:80/misc.html?x=1","http://192.168.4.1/upload"})check(DevicePolicy.local(url),url);
  for(String url:new String[]{"https://192.168.4.1/","http://192.168.4.1.evil.test/","http://192.168.4.1@evil.test/","http://admin@192.168.4.1/","http://192.168.4.1:8080/","file:///etc/passwd","javascript:alert(1)","http://192.168.4.2/"})check(!DevicePolicy.local(url),url);
  check(DevicePolicy.passiveAsset("http://192.168.4.1/style.css","GET",false),"passive stylesheet");
  check(!DevicePolicy.passiveAsset("http://192.168.4.1/style.css?set=1","GET",false),"query always needs live authorization");
  check(!DevicePolicy.passiveAsset("http://192.168.4.1/save","GET",false),"dynamic GET needs live authorization");
  check(!DevicePolicy.passiveAsset("http://192.168.4.1/style.css","POST",false),"POST always needs live authorization");
  check(!DevicePolicy.passiveAsset("http://192.168.4.1/style.css","GET",true),"navigation always needs live authorization");
  String text="# preserve\r\nWIFI_STA_PWD;abc;def\r\nMDBA_ID0;10\r\nMDBA_ID1;-1\r\nUNKNOWN;ação\r\n";
  for(Charset cs:new Charset[]{StandardCharsets.UTF_8,Charset.forName("windows-1252")}){
   byte[] input=text.getBytes(cs);BinDocument bin=BinDocument.read(input);
   check(Arrays.equals(input,bin.render(Collections.emptyMap())),"identity encoding/newlines");
   check(bin.values().get("WIFI_STA_PWD").equals("abc;def"),"first semicolon");
   String changed=new String(bin.withSlave(247),cs);
   check(changed.contains("MDBA_ID0;247\r\n"),"active slave updated");
   check(changed.contains("MDBA_ID1;-1\r\n"),"reserved slot stays inactive");
   check(changed.contains("UNKNOWN;ação\r\n"),"unknown keys preserved");
  }
  byte[] raw=text.getBytes(StandardCharsets.UTF_8),bom=new byte[raw.length+3];bom[0]=(byte)239;bom[1]=(byte)187;bom[2]=(byte)191;System.arraycopy(raw,0,bom,3,raw.length);
  check(Arrays.equals(bom,BinDocument.read(bom).render(Collections.emptyMap())),"BOM preserved");
  rejects(()->{try{BinDocument.read(raw).withSlave(0);}catch(java.nio.charset.CharacterCodingException e){throw new RuntimeException(e);}});
  rejects(()->{try{BinDocument.read(raw).withSlave(248);}catch(java.nio.charset.CharacterCodingException e){throw new RuntimeException(e);}});
  rejects(()->{try{BinDocument.read(raw).render(Collections.singletonMap("WIFI_STA_PWD","ok\nINJECT;1"));}catch(java.nio.charset.CharacterCodingException e){throw new RuntimeException(e);}});
  check(new String(BinDocument.read("A;1".getBytes(StandardCharsets.UTF_8)).render(Collections.singletonMap("B","2")),StandardCharsets.UTF_8).equals("A;1\nB;2\n"),"append complete line");
  System.out.println(checks+" BIN/local-device policy checks passed");
 }
}
