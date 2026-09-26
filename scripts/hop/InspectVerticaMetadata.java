import org.apache.hop.core.HopEnvironment;
import org.apache.hop.core.database.DatabaseMeta;
import org.apache.hop.core.metadata.SerializableMetadataProvider;
import org.apache.hop.metadata.serializer.memory.MemoryMetadataProvider;

/** Synthetic metadata only: no credentials, connection or engine execution. */
class InspectVerticaMetadata {
  public static void main(String[] args) throws Exception {
    HopEnvironment.init();
    var provider = new MemoryMetadataProvider();
    var db = new DatabaseMeta("etl_target", "VERTICA5", "Native", "synthetic.invalid", "synthetic", "5433", "synthetic", "${WORKBENCH_VERTICA_PASSWORD}");
    db.addExtraOption("VERTICA5", "TLSmode", "disable");
    provider.getSerializer(DatabaseMeta.class).save(db);
    var json = args.length > 0 ? java.nio.file.Files.readString(java.nio.file.Path.of("/candidate/metadata.json")) : new SerializableMetadataProvider(provider).toJson();
    var restored = new SerializableMetadataProvider(json).getSerializer(DatabaseMeta.class).load("etl_target");
    if (restored == null || !"synthetic.invalid".equals(restored.getHostname()))
      throw new IllegalStateException("VERTICA_METADATA_ROUNDTRIP_FAILED");
    if (!"${WORKBENCH_VERTICA_PASSWORD}".equals(restored.getPassword())) throw new IllegalStateException("PASSWORD_REFERENCE_CHANGED");
    if (!"disable".equals(restored.getExtraOptions().get("VERTICA5.TLSmode"))) throw new IllegalStateException("TLS_OPTION_CHANGED");
    if (!"com.vertica.jdbc.Driver".equals(restored.getDriverClass(new org.apache.hop.core.variables.Variables()))) throw new IllegalStateException("DRIVER_CLASS_MISMATCH");
    if (args.length == 0) System.out.println(json);
    System.out.println("VERTICA_METADATA_ROUNDTRIP_PASSED connection=false execution=false");
  }
}
