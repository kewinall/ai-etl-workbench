/** Private launcher: secret stays out of argv, metadata and public artifacts. */
class WorkbenchHopRun {
  public static void main(String[] args) throws Exception {
    String password = System.getenv("WORKBENCH_VERTICA_PASSWORD");
    if (password == null || password.isEmpty()) throw new IllegalStateException("HOP_CREDENTIAL_REQUIRED");
    System.setProperty("WORKBENCH_VERTICA_PASSWORD", password);
    try {
      org.apache.hop.core.HopEnvironment.init();
      var registry = org.apache.hop.core.plugins.PluginRegistry.getInstance();
      var type = org.apache.hop.core.extension.ExtensionPointPluginType.class;
      var main = org.apache.hop.core.extension.IExtensionPoint.class;
      String id = "WorkbenchFinalMetricsV1";
      var plugin = new org.apache.hop.core.plugins.Plugin(new String[]{id}, type, main,
          "", "PipelineFinish", "Private final node counters", "", false, true,
          java.util.Map.of(), java.util.List.of(), "", new String[0], null, false);
      registry.registerPlugin(type, plugin);
      registry.addClassFactory(type, main, id, () ->
          (org.apache.hop.core.extension.IExtensionPoint) (log, variables, object) -> {
            if (!(object instanceof org.apache.hop.pipeline.Pipeline pipeline)) return;
            // One PrintStream write avoids interleaving the metric block.
            // Names/counters only: never row values, paths or credentials.
            StringBuilder lines = new StringBuilder();
            for (var node : pipeline.getTransforms()) {
              var t = node.transform;
              if (!node.transformName.matches("[A-Za-z_][A-Za-z0-9_]*") || node.copy != 0)
                throw new org.apache.hop.core.exception.HopException("WORKBENCH_METRICS_SCOPE_INVALID");
              lines.append("WORKBENCH_NODE_V1 ").append(node.transformName).append(" ")
                  .append(t.getLinesInput()).append(" ").append(t.getLinesOutput()).append(" ")
                  .append(t.getLinesRead()).append(" ").append(t.getLinesWritten()).append(" ")
                  .append(t.getLinesUpdated()).append(" ").append(t.getErrors()).append("\n");
            }
            lines.append("WORKBENCH_METRICS_END_V1 ").append(pipeline.getTransforms().size()).append("\n");
            System.out.print(lines.toString());
          });
      org.apache.hop.run.HopRun.main(args);
    } finally {
      System.clearProperty("WORKBENCH_VERTICA_PASSWORD");
    }
  }
}
