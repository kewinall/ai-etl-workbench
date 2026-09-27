import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Collections;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.row.IRowMeta;
import org.apache.hop.core.variables.Variables;
import org.apache.hop.metadata.serializer.memory.MemoryMetadataProvider;
import org.apache.hop.pipeline.PipelineMeta;
import org.apache.hop.pipeline.engines.local.LocalPipelineEngine;
import org.apache.hop.pipeline.transform.RowAdapter;

/** Synthetic ordered collector. Never sorts rows and never connects to a DB. */
class ExecuteSourceOrderProbe {
  public static void main(String[] args) throws Exception {
    if (args.length != 0) throw new IllegalArgumentException("No arguments accepted");
    HopEnvironment.init();
    var factory = DocumentBuilderFactory.newInstance();
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
    factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    var document = factory.newDocumentBuilder().parse(Path.of("/candidate/candidate.hpl").toFile());
    var provider = new MemoryMetadataProvider();
    var meta = new PipelineMeta(document.getDocumentElement(), provider);
    var allowed = java.util.Set.of("CSVInput", "SortRows", "SelectValues", "Dummy");
    for (var node : meta.getTransforms())
      if (!allowed.contains(node.getTransformPluginId())) throw new IllegalStateException("Unexpected plugin");
    if (!"Dummy".equals(meta.findTransform("target").getTransformPluginId()))
      throw new IllegalStateException("Collector required");
    var engine = new LocalPipelineEngine(meta, new Variables(), null);
    engine.setMetadataProvider(provider);
    engine.prepareExecution();
    var rows = Collections.synchronizedList(new ArrayList<String>());
    engine.getTransform("target", 0).addRowListener(new RowAdapter() {
      public void rowReadEvent(IRowMeta rowMeta, Object[] row) {
        String[] names = {"category", "amount", "source_position"};
        if (rowMeta.size() != names.length) throw new IllegalStateException("Output width changed");
        var values = new ArrayList<String>();
        for (int i = 0; i < names.length; i++) {
          if (!names[i].equals(rowMeta.getValueMeta(i).getName()) || row[i] == null)
            throw new IllegalStateException("Output contract changed");
          values.add(Base64.getEncoder().encodeToString(row[i].toString().getBytes(StandardCharsets.UTF_8)));
        }
        rows.add(String.join("|", values));
      }
    });
    engine.startThreads();
    long deadline = System.nanoTime() + 30_000_000_000L;
    while (!engine.isFinished() && System.nanoTime() < deadline) Thread.sleep(50);
    if (!engine.isFinished()) { engine.stopAll(); throw new IllegalStateException("Probe timeout"); }
    engine.waitUntilFinished();
    if (engine.getErrors() != 0) throw new IllegalStateException("Hop execution failed");
    for (var row : rows) System.out.println("SOURCE_ORDER_RESULT=" + row);
    System.out.println("SOURCE_ORDER_COLLECTED rows=" + rows.size() + " errors=0 database=false release=false");
  }
}
