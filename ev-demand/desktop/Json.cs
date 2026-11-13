using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
namespace EnergyCube.DMax {
 internal static class Json {
  public static string Serialize(object value){return JsonSerializer.Serialize(value);}
  public static Dictionary<string,object> Object(string text){
   using(var document=JsonDocument.Parse(text,new JsonDocumentOptions{MaxDepth=24})){
    return Plain(document.RootElement) as Dictionary<string,object>;
   }
  }
  private static object Plain(JsonElement value){
   switch(value.ValueKind){
    case JsonValueKind.Object:return value.EnumerateObject().ToDictionary(p=>p.Name,p=>Plain(p.Value));
    case JsonValueKind.Array:return value.EnumerateArray().Select(Plain).ToArray();
    case JsonValueKind.String:return value.GetString();
    case JsonValueKind.Number:long integer;return value.TryGetInt64(out integer)?(object)integer:value.GetDouble();
    case JsonValueKind.True:return true;
    case JsonValueKind.False:return false;
    default:return null;
   }
  }
 }
}
