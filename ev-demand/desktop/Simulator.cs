using System;
using System.Collections.Generic;
using System.Linq;
namespace EnergyCube.DMax {
 internal sealed class SimulatedPort {
  public int Id;
  public double Soc,Power,Energy;
  public bool Connected,Paused;
 }
 internal sealed class Simulation {
  public readonly List<SimulatedPort> Ports=new List<SimulatedPort>();
  public double Other=10;
  public double Total { get {return Other+Ports.Sum(p=>p.Power);} }
  public Simulation(){for(int i=0;i<4;i++)Ports.Add(new SimulatedPort{Id=i,Soc=20+i*10,Connected=i<2});}
  public void Advance(double seconds) {
   if(double.IsNaN(seconds)||double.IsInfinity(seconds)||seconds<0)throw new ArgumentOutOfRangeException("seconds");
   var active=Ports.Where(p=>p.Connected&&!p.Paused&&p.Soc<100).ToList();
   var power=Math.Min(22,Math.Max(0,60-Other)/Math.Max(1,active.Count));
   foreach(var p in Ports){p.Power=active.Contains(p)?power:0;var energy=Math.Min((100-p.Soc)*60/100,p.Power*seconds*60/3600);p.Energy+=energy;p.Soc=Math.Min(100,p.Soc+energy/60*100);if(p.Soc>=100)p.Power=0;}
  }
  public void Connect(int id){var p=Ports[id];if(p.Connected)throw new InvalidOperationException("Conector ocupado");p.Connected=true;p.Paused=false;p.Soc=20;p.Energy=0;p.Power=0;}
  public void Disconnect(int id){var p=Ports[id];p.Connected=false;p.Paused=false;p.Power=0;}
 }
}
