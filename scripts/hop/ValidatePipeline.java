import java.nio.file.Files;
import java.nio.file.Path;
import java.io.ByteArrayInputStream;
import java.util.HashSet;
import javax.xml.parsers.DocumentBuilderFactory;
import org.apache.hop.core.HopEnvironment;
import org.apache.hop.metadata.serializer.memory.MemoryMetadataProvider;
import org.apache.hop.pipeline.PipelineMeta;

/** Offline metadata check only. Never creates an execution engine or DB connection. */
class ValidatePipeline {
  public static void main(String[] args) {
    try {
      if (args.length != 1 && !(args.length == 2 && "--compiler-probe".equals(args[1]))) throw new IllegalArgumentException();
      Path path = Path.of(args[0]);
      if (Files.size(path) > 4 * 1024 * 1024) throw new IllegalArgumentException();
      byte[] bytes = Files.readAllBytes(path);
      var factory = DocumentBuilderFactory.newInstance();
      factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
      factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
      factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
      factory.setXIncludeAware(false);
      factory.setExpandEntityReferences(false);
      var builder = factory.newDocumentBuilder();
      builder.setErrorHandler(new org.xml.sax.helpers.DefaultHandler() {
        public void error(org.xml.sax.SAXParseException e) throws org.xml.sax.SAXException { throw e; }
        public void fatalError(org.xml.sax.SAXParseException e) throws org.xml.sax.SAXException { throw e; }
      });
      var root = builder.parse(new ByteArrayInputStream(bytes)).getDocumentElement();
      if (!"pipeline".equals(root.getTagName())) throw new IllegalArgumentException();
      HopEnvironment.init();
      var pipeline = new PipelineMeta(root, new MemoryMetadataProvider());
      if (pipeline.getTransforms().isEmpty()) throw new IllegalArgumentException();
      var names = new HashSet<String>();
      for (var transform : pipeline.getTransforms()) {
        if (transform.isMissing() || transform.getTransform() == null
            || transform.getName() == null || transform.getName().isBlank()
            || !names.add(transform.getName())) throw new IllegalArgumentException();
      }
      for (var hop : pipeline.getPipelineHops()) {
        if (hop.getFromTransform() == null || hop.getToTransform() == null)
          throw new IllegalArgumentException();
      }
      if (args.length == 2) {
        // Fixed synthetic compiler probe only; does not inspect or connect target DB.
        var row = pipeline.getTransformFields(new org.apache.hop.core.variables.Variables(), "projection");
        if (!java.util.Arrays.equals(row.getFieldNames(), new String[]{"category", "total_amount", "row_count"}))
          throw new IllegalArgumentException();
        String[] expectedTypes = {"String", "BigNumber", "Integer"};
        for (int i = 0; i < row.size(); i++)
          if (!expectedTypes[i].equals(row.getValueMeta(i).getTypeDesc())) throw new IllegalArgumentException();
        String aggregate = pipeline.findTransform("aggregate").getTransform().getXml();
        String filter = pipeline.findTransform("filter").getTransform().getXml();
        for (String token : new String[]{"<type>SUM</type>", "<type>COUNT_ANY</type>", "<name>category</name>", "<subject>amount</subject>"})
          if (!aggregate.contains(token)) throw new IllegalArgumentException();
        for (String token : new String[]{"<function>IS NOT NULL</function>", "<function>&gt;</function>", "<text>100.00</text>", "<send_true_to>sort</send_true_to>", "<send_false_to>discard</send_false_to>"})
          if (!filter.contains(token)) throw new IllegalArgumentException();
        System.out.println("HOP_COMPILER_PROBE_PASSED fields=3 execution=false");
      }
      System.out.println("HOP_METADATA_LOADED transforms=" + names.size()
          + " hops=" + pipeline.getPipelineHops().size() + " execution=false");
    } catch (Exception e) {
      // Do not echo paths, XML, connection details, or arbitrary exception messages.
      System.err.println("HOP_METADATA_REJECTED category=" + e.getClass().getSimpleName());
      Throwable cause = e.getCause();
      for (int depth = 0; cause != null && depth < 8; depth++, cause = cause.getCause())
        System.err.println("cause_category=" + cause.getClass().getSimpleName());
      System.exit(2);
    }
  }
}
