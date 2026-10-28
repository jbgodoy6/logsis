import br.com.sistel.logsis.BinDocument;
import br.com.sistel.logsis.NominalLimits;
import java.nio.file.*;
import java.util.*;
public final class BinInteroperabilityTest {
 public static void main(String[] args)throws Exception {
  int count=0;
  try(DirectoryStream<Path> files=Files.newDirectoryStream(Path.of(args[0]),"*.bin")){
   for(Path file:files){
    byte[] actual=BinDocument.read(Files.readAllBytes(file)).withSlave(247);
    byte[] expected=Files.readAllBytes(Path.of(args[1]).resolve(file.getFileName()));
    if(!Arrays.equals(actual,expected))throw new AssertionError(file.getFileName());
    String metadata=Files.readString(file.resolveSibling(file.getFileName().toString().replace(".bin",".limits.tsv")));
    byte[] changed=NominalLimits.apply(actual,metadata,13800,50,12,1500);
    byte[] nominal=Files.readAllBytes(Path.of(args[2]).resolve(file.getFileName()));
    if(!Arrays.equals(changed,nominal))throw new AssertionError("Nominal limits differ: "+file.getFileName());
    count++;
   }
  }
  if(count!=17)throw new AssertionError("Expected 17 models");
  System.out.println("17 Android BINs match Studio byte-for-byte for Slave ID and 13.8 kV/50 Hz nominal limits");
 }
}
