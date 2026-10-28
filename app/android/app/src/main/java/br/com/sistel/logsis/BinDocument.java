package br.com.sistel.logsis;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/** LogSis text BIN: keep encoding, BOM, original lines and unknown keys. */
public final class BinDocument {
    private final String text;
    private final Charset charset;
    private final boolean bom;
    private final String newline;
    private BinDocument(String text, Charset charset, boolean bom) {
        if (text.indexOf('\0') >= 0) throw new IllegalArgumentException("BIN não é configuração textual LogSis.");
        this.text = text; this.charset = charset; this.bom = bom;
        this.newline = text.contains("\r\n") ? "\r\n" : "\n";
    }
    public static BinDocument read(byte[] data) throws CharacterCodingException {
        boolean bom = data.length >= 3 && (data[0]&255)==239 && (data[1]&255)==187 && (data[2]&255)==191;
        ByteBuffer bytes = ByteBuffer.wrap(data, bom ? 3 : 0, data.length-(bom ? 3 : 0));
        Charset cs = StandardCharsets.UTF_8;
        String text;
        try { text = cs.newDecoder().onMalformedInput(CodingErrorAction.REPORT).decode(bytes).toString(); }
        catch (CharacterCodingException e) {
            if (bom) throw e;
            cs = Charset.forName("windows-1252");
            text = cs.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data)).toString();
        }
        return new BinDocument(text, cs, bom);
    }
    public Map<String,String> values() {
        Map<String,String> result = new LinkedHashMap<>();
        for (String line : text.split("\\r\\n|\\n|\\r", -1)) {
            int p = line.indexOf(';');
            if (p >= 0) result.put(line.substring(0,p).trim(), line.substring(p+1));
        }
        return result;
    }
    private static void safe(String key, String value) {
        if (key.isEmpty() || key.indexOf(';')>=0 || key.indexOf('\n')>=0 || key.indexOf('\r')>=0
                || key.indexOf('\0')>=0 || value.indexOf('\n')>=0 || value.indexOf('\r')>=0 || value.indexOf('\0')>=0)
            throw new IllegalArgumentException("Valor não pode conter quebra de linha ou NUL.");
    }
    public byte[] render(Map<String,String> changes) throws CharacterCodingException {
        changes.forEach(BinDocument::safe);
        Map<String,String> remaining = new LinkedHashMap<>(changes);
        StringBuilder out = new StringBuilder();
        for (String line : text.split("(?<=\\n)|(?<=\\r)(?!\\n)", -1)) {
            int end = line.length();
            while (end>0 && (line.charAt(end-1)=='\r' || line.charAt(end-1)=='\n')) end--;
            String body = line.substring(0,end), ending = line.substring(end);
            int sep = body.indexOf(';');
            String key = sep < 0 ? "" : body.substring(0,sep).trim();
            if (sep>=0 && changes.containsKey(key)) {
                String value=changes.get(key);
                out.append(body.substring(sep+1).equals(value) ? body : key+";"+value).append(ending);
                remaining.remove(key);
            } else out.append(line);
        }
        if (!remaining.isEmpty() && out.length()>0 && out.charAt(out.length()-1)!='\n' && out.charAt(out.length()-1)!='\r') out.append(newline);
        remaining.forEach((key,value)->out.append(key).append(';').append(value).append(newline));
        ByteBuffer encoded=charset.newEncoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).encode(CharBuffer.wrap(out));
        byte[] result=new byte[encoded.remaining()+(bom?3:0)];
        if (bom) { result[0]=(byte)239;result[1]=(byte)187;result[2]=(byte)191; }
        encoded.get(result,bom?3:0,encoded.remaining());
        return result;
    }
    public byte[] withSlave(int slave) throws CharacterCodingException {
        if (slave<1 || slave>247) throw new IllegalArgumentException("Slave ID deve estar entre 1 e 247.");
        Map<String,String> updates=new LinkedHashMap<>();
        values().forEach((k,v)-> { if (k.matches("MDBA_ID[0-9]{1,2}") && !v.trim().equals("-1")) updates.put(k,Integer.toString(slave)); });
        if (updates.isEmpty()) throw new IllegalArgumentException("BIN sem canais Modbus ativos.");
        return render(updates);
    }
}
