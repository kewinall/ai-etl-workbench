import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.plugins.PluginRegistry;
import org.apache.hop.core.plugins.TransformPluginType;
import org.apache.hop.core.row.IRowMeta;
import org.apache.hop.core.variables.Variables;
import org.apache.hop.metadata.serializer.memory.MemoryMetadataProvider;
import org.apache.hop.pipeline.PipelineMeta;
import org.apache.hop.pipeline.engines.local.LocalPipelineEngine;
import org.apache.hop.pipeline.transform.ITransformMeta;
import org.apache.hop.pipeline.transform.RowAdapter;

/** Fixed synthetic row probe. NEVER tests TableOutput/Vertica or grants release rights. */
class ExecuteCompilerProbe {
  public static void main(String[] args) throws Exception {
    if (args.length != 0) throw new IllegalArgumentException("No user paths accepted");
    HopEnvironment.init();
    var factory = DocumentBuilderFactory.newInstance();
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
    factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    var document = factory.newDocumentBuilder().parse(Path.of("/candidate/candidate.hpl").toFile());
    var provider = new MemoryMetadataProvider();
    var meta = new PipelineMeta(document.getDocumentElement(), provider);
    if (meta.nrTransforms() != 7 || meta.nrPipelineHops() != 6) throw new IllegalStateException("Unexpected fixture");
    var allowed = java.util.Set.of("CSVInput", "FilterRows", "SortRows", "GroupBy", "SelectValues", "TableOutput", "Dummy");
    for (var node : meta.getTransforms())
      if (!allowed.contains(node.getTransformPluginId())) throw new IllegalStateException("Unexpected plugin");
    var target = meta.findTransform("target");
    if (!"TableOutput".equals(target.getTransformPluginId())) throw new IllegalStateException("Unexpected target");
    var dummy = PluginRegistry.getInstance().loadClass(TransformPluginType.class, "Dummy", ITransformMeta.class);
    dummy.setDefault();
    target.setTransform(dummy);
    target.setTransformPluginId("Dummy");
    for (var node : meta.getTransforms())
      if ("TableOutput".equals(node.getTransformPluginId())) throw new IllegalStateException("DB node remains");
    var variables = new Variables();
    variables.setVariable("SOURCE_CSV", "/validation/fixtures/compiler-input.csv");
    var engine = new LocalPipelineEngine(meta, variables, null);
    engine.setMetadataProvider(provider);
    engine.setVariable("SOURCE_CSV", "/validation/fixtures/compiler-input.csv");
    engine.prepareExecution();
    var rows = Collections.synchronizedList(new ArrayList<String>());
    var observedColumns = Collections.synchronizedSet(new java.util.HashSet<String>());
    engine.getTransform("target", 0).addRowListener(new RowAdapter() {
      public void rowReadEvent(IRowMeta rowMeta, Object[] row) {
        if (rowMeta.size() != 3 || row.length != 3) throw new IllegalStateException("Unexpected output width");
        observedColumns.add(rowMeta.getValueMeta(0).getName() + "|" + rowMeta.getValueMeta(1).getName() + "|" + rowMeta.getValueMeta(2).getName());
        var total = new java.math.BigDecimal(row[1].toString()).stripTrailingZeros().toPlainString();
        rows.add(row[0] + "|" + total + "|" + row[2]);
      }
    });
    engine.startThreads();
    long deadline = System.nanoTime() + 30_000_000_000L;
    while (!engine.isFinished() && System.nanoTime() < deadline) Thread.sleep(50);
    if (!engine.isFinished()) { engine.stopAll(); throw new IllegalStateException("Probe timeout"); }
    engine.waitUntilFinished();
    if (engine.getErrors() != 0) throw new IllegalStateException("Hop execution failed");
    Collections.sort(rows);
    if (!rows.equals(java.util.List.of("A|301.35|2", "B|300|1", "a|110|1")))
      throw new IllegalStateException("Golden result mismatch: " + rows);
    // Fixed synthetic fixture only; Python also validates these actual engine rows.
    if (observedColumns.size() != 1) throw new IllegalStateException("Inconsistent output metadata");
    System.out.println("SYNTHETIC_HOP_COLUMNS=" + observedColumns.iterator().next());
    for (var row : rows) System.out.println("SYNTHETIC_HOP_RESULT=" + row);
    System.out.println("HOP_ROW_PROBE_PASSED rows=3 errors=0 target=TEST_COLLECTOR vertica=false release=false");
  }
}
