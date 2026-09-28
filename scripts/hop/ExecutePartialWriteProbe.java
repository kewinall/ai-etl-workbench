import java.nio.file.Files;
import java.nio.file.Path;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.metadata.SerializableMetadataProvider;
import org.apache.hop.core.row.IRowMeta;
import org.apache.hop.core.variables.Variables;
import org.apache.hop.pipeline.PipelineMeta;
import org.apache.hop.pipeline.engines.local.LocalPipelineEngine;
import org.apache.hop.pipeline.transform.RowAdapter;

/** Opt-in native test only: pause after one batch, supervisor observes DB then cancels. */
class ExecutePartialWriteProbe {
  public static void main(String[] args) throws Exception {
    if ((args.length != 0 && args.length != 2) || !"dedicated-portability-database-v1".equals(System.getenv("WORKBENCH_PARTIAL_WRITE_PROBE")))
      throw new IllegalStateException("Explicit isolated probe required");
    Path directory = Path.of(args.length == 0 ? "/candidate" : args[0]);
    String source = args.length == 0 ? "/candidate/input.csv" : args[1];
    HopEnvironment.init();
    var factory = DocumentBuilderFactory.newInstance();
    factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
    factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
    factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
    var document = factory.newDocumentBuilder().parse(directory.resolve("candidate.hpl").toFile());
    var provider = new SerializableMetadataProvider(Files.readString(directory.resolve("metadata.json")));
    var meta = new PipelineMeta(document.getDocumentElement(), provider);
    var allowed = java.util.Set.of("CSVInput", "SortRows", "SelectValues", "TableOutput");
    for (var node : meta.getTransforms())
      if (!allowed.contains(node.getTransformPluginId())) throw new IllegalStateException("Unexpected plugin");
    if (!"TableOutput".equals(meta.findTransform("target").getTransformPluginId()))
      throw new IllegalStateException("Real database sink required");
    var variables = new Variables();
    variables.setVariable("SOURCE_CSV", source);
    variables.setVariable("WORKBENCH_VERTICA_PASSWORD", System.getenv("WORKBENCH_VERTICA_PASSWORD"));
    var engine = new LocalPipelineEngine(meta, variables, null);
    engine.setMetadataProvider(provider);
    engine.prepareExecution();
    engine.getTransform("target", 0).addRowListener(new RowAdapter() {
      private int read = 0;
      public void rowReadEvent(IRowMeta rowMeta, Object[] row) {
        if (++read == 1001) {
          try {
            Files.writeString(directory.resolve("partial-ready"), "1001 input events; not a commit claim");
            Thread.sleep(300_000);
          } catch (Exception error) { throw new IllegalStateException("Probe pause failed", error); }
        }
      }
    });
    engine.startThreads();
    engine.waitUntilFinished();
    throw new IllegalStateException("Probe was not interrupted in flight");
  }
}
