import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.metadata.SerializableMetadataProvider;
import org.apache.hop.metadata.serializer.memory.MemoryMetadataProvider;
import org.apache.hop.pipeline.config.PipelineRunConfiguration;
import org.apache.hop.pipeline.engines.local.LocalPipelineRunConfiguration;

/** Native metadata round trip only. No engine or database connection. */
class VerifyMetadataExport {
  public static void main(String[] args) throws Exception {
    HopEnvironment.init();
    var provider = new MemoryMetadataProvider();
    var config = new PipelineRunConfiguration();
    config.setName("local");
    var engine = new LocalPipelineRunConfiguration();
    engine.setEnginePluginId("Local");
    engine.setEnginePluginName("Hop local pipeline engine");
    config.setEngineRunConfiguration(engine);
    provider.getSerializer(PipelineRunConfiguration.class).save(config);
    String json = args.length == 1 && args[0].equals("--candidate")
        ? java.nio.file.Files.readString(java.nio.file.Path.of("/candidate/metadata.json"))
        : new SerializableMetadataProvider(provider).toJson();
    var restored = new SerializableMetadataProvider(json);
    var loaded = restored.getSerializer(PipelineRunConfiguration.class).load("local");
    if (loaded == null || !(loaded.getEngineRunConfiguration() instanceof LocalPipelineRunConfiguration))
      throw new IllegalStateException("LOCAL_METADATA_ROUNDTRIP_FAILED");
    // Metadata may eventually contain credentials: never print the JSON.
    System.out.println("LOCAL_METADATA_ROUNDTRIP_PASSED execution=false database=false");
  }
}
