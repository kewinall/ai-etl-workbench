import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.plugins.PluginRegistry;
import org.apache.hop.core.plugins.TransformPluginType;
import org.apache.hop.pipeline.transform.ITransformMeta;

/** Inspect the installed native plugin only; never read data or run a pipeline. */
class InspectExcelPlugin {
  public static void main(String[] args) throws Exception {
    if (args.length != 0) throw new IllegalArgumentException("No arguments supported");
    HopEnvironment.init();
    var meta = PluginRegistry.getInstance().loadClass(TransformPluginType.class, "ExcelInput", ITransformMeta.class);
    meta.setDefault();
    System.out.println("EXCEL_PLUGIN=" + meta.getClass().getName());
    System.out.println(meta.getXml());
    for (var field : meta.getClass().getDeclaredFields()) {
      if (!java.lang.reflect.Modifier.isStatic(field.getModifiers()))
        System.out.println("FIELD " + field.getName() + " " + field.getGenericType() + " " + java.util.Arrays.toString(field.getAnnotations()));
    }
    for (var method : meta.getClass().getMethods())
      if (method.getName().startsWith("set")) System.out.println("SETTER " + method);
    var types = new java.util.ArrayList<Class<?>>();
    types.addAll(java.util.Arrays.asList(meta.getClass().getDeclaredClasses()));
    types.add(meta.getClass().getClassLoader().loadClass("org.apache.hop.pipeline.transforms.excelinput.ExcelInputField"));
    for (var type : types) {
      System.out.println("TYPE " + type.getName());
      for (var field : type.getDeclaredFields()) {
        var property = field.getAnnotation(org.apache.hop.metadata.api.HopMetadataProperty.class);
        if (property != null) System.out.println("KEY " + field.getName() + "=" + property.key() + " type=" + field.getType());
      }
    }
  }
}
