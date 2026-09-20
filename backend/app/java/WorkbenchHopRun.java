/** Private launcher: secret stays out of argv, metadata and public artifacts. */
class WorkbenchHopRun {
  public static void main(String[] args) throws Exception {
    String password = System.getenv("WORKBENCH_VERTICA_PASSWORD");
    if (password == null || password.isEmpty()) throw new IllegalStateException("HOP_CREDENTIAL_REQUIRED");
    System.setProperty("WORKBENCH_VERTICA_PASSWORD", password);
    try {
      org.apache.hop.run.HopRun.main(args);
    } finally {
      System.clearProperty("WORKBENCH_VERTICA_PASSWORD");
    }
  }
}
