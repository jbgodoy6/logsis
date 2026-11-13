using System;
using System.Collections.Generic;
namespace EnergyCube.DMax {
 internal sealed class ServiceError : Exception {
  public int Code { get; private set; }
  public ServiceError(string message, int code=503) : base(message) { Code=code; }
 }
 internal static class Values {
  public static string Text(IDictionary<string,object> row,string key) { object v; return row.TryGetValue(key,out v)&&v!=null?Convert.ToString(v):""; }
  public static bool Flag(IDictionary<string,object> row,string key) { object v; return row.TryGetValue(key,out v)&&v is bool&&(bool)v; }
  public static double Number(IDictionary<string,object> row,string key) {
   object value;double number;if(!row.TryGetValue(key,out value)||value==null)return 0;
   if(value is string){if(!double.TryParse((string)value,System.Globalization.NumberStyles.Float,System.Globalization.CultureInfo.InvariantCulture,out number))return 0;}
   else {try{number=Convert.ToDouble(value,System.Globalization.CultureInfo.InvariantCulture);}catch{return 0;}}
   return double.IsNaN(number)||double.IsInfinity(number)?0:number;
  }
  public static Dictionary<string,object> Object(IDictionary<string,object> row,string key) { object v;return row.TryGetValue(key,out v)?v as Dictionary<string,object>:null; }
  public static List<Dictionary<string,object>> Rows(IDictionary<string,object> row,string key) { object v;if(!row.TryGetValue(key,out v)||!(v is object[]))throw new ServiceError("Resposta da plataforma inválida.");var list=new List<Dictionary<string,object>>();foreach(var item in (object[])v){var data=item as Dictionary<string,object>;if(data==null)throw new ServiceError("Lista da plataforma inválida.");list.Add(data);}return list; }
 }
}
