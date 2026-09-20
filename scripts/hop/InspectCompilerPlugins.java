import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.plugins.PluginRegistry;
import org.apache.hop.core.plugins.TransformPluginType;
import org.apache.hop.pipeline.transform.ITransformMeta;
/** Development-only inspection of a fixed allowlist; no user plugin IDs. */
class InspectCompilerPlugins {
  public static void main(String[] args) throws Exception {
    HopEnvironment.init();
    for (String id : new String[]{"CSVInput", "FilterRows", "SortRows", "GroupBy", "SelectValues", "TableOutput"}) {
      var meta = PluginRegistry.getInstance().loadClass(TransformPluginType.class, id, ITransformMeta.class);
      meta.setDefault();
      System.out.println("PLUGIN " + id + " " + meta.getClass().getName());
      System.out.println(meta.getXml());
      for (String suffix : new String[]{"SortRowsField", "GroupingField", "Aggregation", "AggregationType", "TableOutputField"}) {
        try {
          var type = meta.getClass().getClassLoader().loadClass(meta.getClass().getPackageName() + "." + suffix);
          System.out.println("RELATED " + type.getName());
          if (type.isEnum()) System.out.println(java.util.Arrays.toString(type.getEnumConstants()));
          for (var field : type.getDeclaredFields()) {
            if (java.lang.reflect.Modifier.isStatic(field.getModifiers()) && field.getType() == String[].class) {
              field.setAccessible(true);
              System.out.println("CODES " + field.getName() + "=" + java.util.Arrays.toString((String[])field.get(null)));
            }
            var property = field.getAnnotation(org.apache.hop.metadata.api.HopMetadataProperty.class);
            if (property != null) System.out.println("KEY " + field.getName() + "=" + property.key() + " type=" + field.getType());
          }
        } catch (ClassNotFoundException ignored) { }
      }
      for (var field : meta.getClass().getDeclaredFields()) {
        if (!java.lang.reflect.Modifier.isStatic(field.getModifiers()))
          System.out.println("FIELD " + field.getName() + " " + field.getGenericType());
      }
      for (var type : meta.getClass().getDeclaredClasses()) {
        System.out.println("NESTED " + type.getName());
        if (type.isEnum()) System.out.println(java.util.Arrays.toString(type.getEnumConstants()));
        for (var field : type.getDeclaredFields()) {
          var property = field.getAnnotation(org.apache.hop.metadata.api.HopMetadataProperty.class);
          if (property != null) System.out.println("KEY " + field.getName() + "=" + property.key());
        }
      }
      for (var field : meta.getClass().getFields()) {
        if (java.lang.reflect.Modifier.isStatic(field.getModifiers()) && field.getType() == String[].class)
          System.out.println(field.getName() + "=" + java.util.Arrays.toString((String[])field.get(null)));
      }
    }
  }
}
