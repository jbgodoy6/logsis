package br.com.sistel.logsis;

import android.content.Context;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

public final class BinLibrary {
    public static final class Entry {
        public final String model,label,hash;
        public final int count;
        public java.io.File updatedFile;
        Entry(String[] fields) {model=fields[0];label=fields[1];count=Integer.parseInt(fields[2]);hash=fields[3];}
        @Override public String toString() { return label+" · "+count+" canais"; }
    }
    public static String sha256(byte[] data) throws Exception {
        StringBuilder s=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(data)) s.append(String.format(Locale.ROOT,"%02x",b&255));
        return s.toString();
    }
    public static List<Entry> entries(Context context) throws Exception {
        byte[] data;
        try(InputStream in=context.getAssets().open("library/catalog.tsv")){data=read(in);}
        java.util.LinkedHashMap<String,Entry> result=new java.util.LinkedHashMap<>();
        for(String line:new String(data,StandardCharsets.UTF_8).split("\n")) {
            if(line.startsWith("model\t")||line.trim().isEmpty())continue;
            String[] fields=line.split("\t",-1);
            if(fields.length!=4||!fields[0].matches("[A-Z0-9_]+"))throw new IllegalArgumentException("Catálogo inválido.");
            Entry entry=new Entry(fields);result.put(entry.model,entry);
        }
        java.io.File pointer=new java.io.File(context.getFilesDir(),"library-current");
        if(pointer.isFile()){
            String version;
            try(InputStream in=new android.util.AtomicFile(pointer).openRead()){version=new String(read(in),StandardCharsets.UTF_8).trim();}
            if(!version.matches("[a-f0-9-]{36}"))throw new IllegalArgumentException("Biblioteca inválida.");
            java.io.File folder=new java.io.File(new java.io.File(context.getFilesDir(),"libraries"),version);
            byte[] catalog;
            try(InputStream in=new java.io.FileInputStream(new java.io.File(folder,"catalog.tsv"))){catalog=read(in);}
            for(String line:new String(catalog,StandardCharsets.UTF_8).split("\n")){
                if(line.trim().isEmpty())continue;
                String[] fields=line.split("\t",-1);
                if(fields.length!=4||!fields[0].matches("[A-Z0-9_-]+")||!fields[3].matches("[a-f0-9]{64}"))throw new IllegalArgumentException("Biblioteca inválida.");
                Entry entry=new Entry(fields);entry.updatedFile=new java.io.File(folder,entry.model+".bin");result.put(entry.model,entry);
            }
        }
        return new ArrayList<>(result.values());
    }
    public static byte[] preset(Context context,Entry entry,int slave) throws Exception {
        byte[] bytes;
        try(InputStream in=entry.updatedFile==null?context.getAssets().open("library/"+entry.model+".bin"):new java.io.FileInputStream(entry.updatedFile)){bytes=read(in);}
        if(!sha256(bytes).equals(entry.hash))throw new IllegalArgumentException("BIN da biblioteca está corrompido.");
        return BinDocument.read(bytes).withSlave(slave);
    }
    public static byte[] preset(Context context,Entry entry,int slave,double[] nominal) throws Exception {
        byte[] data=preset(context,entry,slave);
        if(entry.updatedFile!=null)return data; // External library owns its thresholds.
        String metadata;
        try(InputStream in=context.getAssets().open("library/"+entry.model+".limits.tsv")){
            metadata=new String(read(in),StandardCharsets.UTF_8);
        }
        return NominalLimits.apply(data,metadata,nominal[0],nominal[1],nominal[2],nominal[3]);
    }
    public static byte[] read(InputStream in) throws Exception {
        java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream();byte[] buffer=new byte[8192];int n;
        while((n=in.read(buffer))!=-1){if(out.size()+n>2*1024*1024)throw new IllegalArgumentException("BIN excede 2 MB.");out.write(buffer,0,n);}
        return out.toByteArray();
    }
}
