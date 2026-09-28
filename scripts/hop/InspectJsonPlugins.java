import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.plugins.PluginRegistry;
import org.apache.hop.core.plugins.TransformPluginType;
import org.apache.hop.pipeline.transform.ITransformMeta;

/** Read installed fixed plugin metadata; never execute or read operator data. */
class InspectJsonPlugins {
  public static void main(String[] args) throws Exception {
    if (args.length != 0) throw new IllegalArgumentException("No arguments");
    HopEnvironment.init();
    for (String id : new String[]{"RowGenerator", "JsonInput"}) {
      var meta = PluginRegistry.getInstance().loadClass(TransformPluginType.class, id, ITransformMeta.class);
      meta.setDefault();
      System.out.println("PLUGIN=" + id);
      System.out.println(meta.getXml());
      for (var field : meta.getClass().getDeclaredFields()) {
        var property = field.getAnnotation(org.apache.hop.metadata.api.HopMetadataProperty.class);
        if (property != null) System.out.println("FIELD=" + field.getName() + " key=" + property.key() + " type=" + field.getGenericType());
      }
      if (id.equals("RowGenerator")) {
        var type = meta.getClass().getClassLoader().loadClass("org.apache.hop.pipeline.transforms.rowgenerator.GeneratorField");
        for (var field : type.getDeclaredFields()) {
          var property = field.getAnnotation(org.apache.hop.metadata.api.HopMetadataProperty.class);
          if (property != null) System.out.println("KEY=" + field.getName() + "=" + property.key());
        }
      }
    }
  }
}
