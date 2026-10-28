package br.com.sistel.logsis;

import android.content.Context;
import android.util.AtomicFile;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.UUID;

/** Stage every BIN and its digest before switching the private catalog pointer. */
public final class LibraryUpdate {
    public static int sync(Context context,TechnicianAuth auth) throws Exception {
        JSONArray entries=auth.authorized("library").getJSONArray("entries");
        if(entries.length()>64)throw new IllegalArgumentException("Biblioteca excede 64 modelos.");
        if(entries.length()==0)return 0;
        String version=UUID.randomUUID().toString();
        String previous="";
        android.util.AtomicFile current=new android.util.AtomicFile(new File(context.getFilesDir(),"library-current"));
        try(java.io.InputStream in=current.openRead()){previous=new String(BinLibrary.read(in),StandardCharsets.UTF_8).trim();}
        catch(java.io.FileNotFoundException ignored){}
        File folder=new File(new File(context.getFilesDir(),"libraries"),version);
        if(!folder.mkdirs())throw new java.io.IOException("Não foi possível criar a biblioteca.");
        boolean committed=false;
        try {
            StringBuilder catalog=new StringBuilder();HashSet<String> seen=new HashSet<>();
            for(int i=0;i<entries.length();i++){
                JSONObject entry=entries.getJSONObject(i);String model=entry.getString("model"),hash=entry.getString("sha256");
                if(!model.matches("[A-Z0-9_-]+")||!hash.matches("[a-f0-9]{64}")||!seen.add(model))throw new IllegalArgumentException("Catálogo inválido ou duplicado.");
                String encoded=auth.download(entry.getString("fileId")).getString("data");
                if(encoded.length()>2800000)throw new IllegalArgumentException("BIN excede 2 MB.");
                byte[] bytes=Base64.decode(encoded,Base64.DEFAULT);
                if(bytes.length>2097152||!BinLibrary.sha256(bytes).equals(hash))throw new IllegalArgumentException("Arquivo atualizado não confere com o catálogo.");
                BinDocument document=BinDocument.read(bytes);int active=0;
                for(java.util.Map.Entry<String,String> value:document.values().entrySet())
                    if(value.getKey().matches("MDBA_ID[0-9]{1,2}")&&!value.getValue().trim().equals("-1"))active++;
                if(active<1||active>100)throw new IllegalArgumentException("BIN sem mapa Modbus válido.");
                try(FileOutputStream out=new FileOutputStream(new File(folder,model+".bin"))){out.write(bytes);}
                catalog.append(model).append('\t').append(model).append('\t').append(active).append('\t').append(hash).append('\n');
            }
            if(!auth.verify())throw new IllegalStateException("Autorização não confirmada.");
            try(FileOutputStream out=new FileOutputStream(new File(folder,"catalog.tsv"))){out.write(catalog.toString().getBytes(StandardCharsets.UTF_8));}
            AtomicFile pointer=new AtomicFile(new File(context.getFilesDir(),"library-current"));FileOutputStream out=null;
            try{out=pointer.startWrite();out.write(version.getBytes(StandardCharsets.UTF_8));pointer.finishWrite(out);}
            catch(Exception e){if(out!=null)pointer.failWrite(out);throw e;}
            committed=true;
            File[] old=folder.getParentFile().listFiles();
            if(old!=null)for(File candidate:old){
                if(!candidate.isDirectory()||!candidate.getName().matches("[a-f0-9-]{36}")||candidate.getName().equals(version)||candidate.getName().equals(previous))continue;
                File[] children=candidate.listFiles();if(children!=null)for(File child:children)if(child.isFile())child.delete();candidate.delete();
            }
            return entries.length();
        }finally{
            if(!committed){File[] files=folder.listFiles();if(files!=null)for(File f:files)f.delete();folder.delete();}
        }
    }
}
