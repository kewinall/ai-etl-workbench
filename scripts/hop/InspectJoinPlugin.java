import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.plugins.PluginRegistry;
import org.apache.hop.core.plugins.TransformPluginType;
import org.apache.hop.pipeline.transform.ITransformMeta;

/** Native metadata inspection only; no data, network or execution. */
class InspectJoinPlugin {
  public static void main(String[] args) throws Exception {
    HopEnvironment.init();
    var meta = PluginRegistry.getInstance().loadClass(TransformPluginType.class, "MergeJoin", ITransformMeta.class);
    meta.setDefault();
    meta.getClass().getMethod("setJoinType", String.class).invoke(meta, "LEFT OUTER");
    meta.getClass().getMethod("setLeftTransformName", String.class).invoke(meta, "left_sort");
    meta.getClass().getMethod("setRightTransformName", String.class).invoke(meta, "right_sort");
    meta.getClass().getMethod("setKeyFields1", java.util.List.class).invoke(meta, java.util.List.of("left_key"));
    meta.getClass().getMethod("setKeyFields2", java.util.List.class).invoke(meta, java.util.List.of("right_key"));
    System.out.println(meta.getXml());
    for (var method : meta.getClass().getMethods())
      if (method.getName().startsWith("set") || method.getName().startsWith("get"))
        System.out.println(method.toGenericString());
  }
}
