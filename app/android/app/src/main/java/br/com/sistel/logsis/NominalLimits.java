package br.com.sistel.logsis;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.LinkedHashMap;
import java.util.Map;

/** Only generated metadata from Studio selects which threshold fields to edit. */
public final class NominalLimits {
    public static byte[] apply(byte[] bin,String metadata,double voltage,double frequency,double battery,double rpm)throws Exception{
        for(double value:new double[]{voltage,frequency,battery,rpm})
            if(!Double.isFinite(value)||value<=0)throw new IllegalArgumentException("Valores nominais devem ser positivos.");
        Map<String,String> changes=new LinkedHashMap<>();
        for(String line:metadata.split("\n")){
            if(line.trim().isEmpty())continue;
            String[] f=line.split("\t");if(f.length!=3)throw new IllegalArgumentException("Metadados de limites inválidos.");
            int index=Integer.parseInt(f[0]),divisor=Integer.parseInt(f[2]);
            if(index<0||index>=100||divisor<=0)throw new IllegalArgumentException("Metadados de limites inválidos.");
            double base,low=.9,high=1.1;
            switch(f[1]){
                case "LN":base=voltage/Math.sqrt(3);break;
                case "LL":base=voltage;break;
                case "FREQ":base=frequency;break;
                case "BATTERY":base=battery;low=.8;high=1.2;break;
                case "RPM":base=rpm;divisor=1;break;
                default:throw new IllegalArgumentException("Tipo de limite inválido.");
            }
            int lower=BigDecimal.valueOf(base*low*divisor).setScale(0,RoundingMode.HALF_UP).intValueExact();
            int upper=BigDecimal.valueOf(base*high*divisor).setScale(0,RoundingMode.HALF_UP).intValueExact();
            changes.put("MDBA_TL"+index,Integer.toString(lower));changes.put("MDBA_TH"+index,Integer.toString(upper));
        }
        return BinDocument.read(bin).render(changes);
    }
}
