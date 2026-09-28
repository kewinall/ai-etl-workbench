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

/** Network-disabled synthetic XLSX collector; no database or release authority. */
class ExecuteExcelProbe {
  public static void main(String[] args) throws Exception {
    if (args.length != 0) throw new IllegalArgumentException("Unexpected arguments");
    HopEnvironment.init();
    var factory = DocumentBuilderFactory.newInstance();
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
    factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    var document = factory.newDocumentBuilder().parse(Path.of("/candidate/candidate.hpl").toFile());
    var provider = new MemoryMetadataProvider();
    var meta = new PipelineMeta(document.getDocumentElement(), provider);
    var allowed = java.util.Set.of("ExcelInput", "FilterRows", "SortRows", "GroupBy", "SelectValues", "Dummy");
    for (var node : meta.getTransforms())
      if (!allowed.contains(node.getTransformPluginId())) throw new IllegalStateException("Unexpected plugin");
    if (meta.getTransforms().size() > 20
        || !"ExcelInput".equals(meta.findTransform("source").getTransformPluginId())
        || !"Dummy".equals(meta.findTransform("target").getTransformPluginId()))
      throw new IllegalStateException("XLSX source and collector required");
    var engine = new LocalPipelineEngine(meta, new Variables(), null);
    engine.setMetadataProvider(provider);
    engine.prepareExecution();
    var rows = Collections.synchronizedList(new ArrayList<String>());
    engine.getTransform("target", 0).addRowListener(new RowAdapter() {
      public void rowReadEvent(IRowMeta rowMeta, Object[] row) {
        if (rowMeta.size() < 1 || rowMeta.size() > 200) throw new IllegalStateException("Unexpected output width");
        var values = new ArrayList<String>();
        for (int i = 0; i < rowMeta.size(); i++)
          values.add(row[i] == null ? "NULL" : Base64.getEncoder().encodeToString(
              (row[i] instanceof java.util.Date ? ((java.util.Date) row[i]).toInstant().toString()
                  : row[i].toString()).getBytes(StandardCharsets.UTF_8)));
        rows.add(String.join("|", values));
      }
    });
    engine.startThreads();
    long deadline = System.nanoTime() + 30_000_000_000L;
    while (!engine.isFinished() && System.nanoTime() < deadline) Thread.sleep(50);
    if (!engine.isFinished()) { engine.stopAll(); throw new IllegalStateException("Probe timeout"); }
    engine.waitUntilFinished();
    if (engine.getErrors() != 0) throw new IllegalStateException("Hop execution failed");
    for (var row : rows) System.out.println("EXCEL_RESULT=" + row);
    System.out.println("EXCEL_COLLECTED rows=" + rows.size() + " errors=0 database=false release=false");
  }
}
