using System;
using EnergyCube.DMax;
class SimulationTests {
 static void Check(bool condition,string message){if(!condition)throw new Exception(message);}
 static void Main(){
  var a=new Simulation();var b=new Simulation();
  Check(a.Ports.Count==4,"four chargers");a.Advance(1);Check(a.Ports[0].Power==22,"distribution capped per charger");Check(a.Total<=60,"total limit");
  a.Other=55;a.Advance(1);Check(a.Ports[0].Power<=2.5&&a.Total<=60,"other loads reduce demo power");
  a.Other=10;a.Ports[0].Soc=99.99;a.Advance(100);Check(a.Ports[0].Soc==100&&a.Ports[0].Power==0,"SOC stops at 100");a.Advance(100);Check(a.Ports[0].Soc==100&&a.Ports[0].Power==0,"completed session stays stopped");
  a.Disconnect(0);a.Connect(0);Check(a.Ports[0].Soc==20,"new session resets battery");
  a.Ports[0].Paused=true;a.Advance(1);Check(a.Ports[0].Power==0,"pause simulation");Check(!b.Ports[0].Paused&&b.Ports[0].Soc==20,"separate sessions isolated");
  bool rejected=false;try{a.Advance(double.NaN);}catch(ArgumentOutOfRangeException){rejected=true;}Check(rejected,"invalid elapsed time rejected");
  System.Globalization.CultureInfo.CurrentCulture=new System.Globalization.CultureInfo("pt-BR");
  var row=new System.Collections.Generic.Dictionary<string,object>{{"at",1770000000.5},{"power",12.25m},{"string","22.5"}};
  Check(Values.Number(row,"at")==1770000000.5,"JSON epoch is culture invariant");Check(Values.Number(row,"power")==12.25,"decimal power is culture invariant");Check(Values.Number(row,"string")==22.5,"string number is invariant");
  var folder=System.IO.Path.Combine(System.IO.Path.GetTempPath(),"dmax-startup-test-"+Guid.NewGuid());
  StartupDiagnostics.Initialize(folder);StartupDiagnostics.Failure(new InvalidOperationException("fixture-sensitive-value"));
  var report=System.IO.File.ReadAllText(StartupDiagnostics.LogPath);Check(report.Contains("InvalidOperationException"),"startup failure type logged");Check(!report.Contains("fixture-sensitive-value"),"exception message not copied into diagnostics");System.IO.Directory.Delete(folder,true);
  var parsed=Json.Object("{\"ok\":true,\"user\":{\"role\":\"developer\"},\"clients\":[{\"updated_at\":1770000000.5}],\"none\":null}");
  Check(Values.Flag(parsed,"ok"),"JSON booleans are native booleans");Check(Values.Text(Values.Object(parsed,"user"),"role")=="developer","nested JSON object");Check(Values.Number(Values.Rows(parsed,"clients")[0],"updated_at")==1770000000.5,"JSON catalog arrays preserve numeric timestamps");
  var restored=Json.Object(Json.Serialize(new System.Collections.Generic.Dictionary<string,object>{{"name","João 🔋"},{"key","fixture"}}));Check(Values.Text(restored,"name")=="João 🔋","Unicode JSON round trip");
  TransportTests.Run();
  Console.WriteLine("24 native core/transport assertions passed, including standalone JSON and safe redirects.");
 }
}
