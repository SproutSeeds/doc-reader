using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class DocReaderLauncher {
    [STAThread]
    static void Main(string[] args) {
        try {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            var start = new ProcessStartInfo(Path.Combine(root, "runtime", "pythonw.exe"),
                "-m doc_reader.windows_app " + (args.Length == 1 && args[0] == "--stop" ? "stop" : "open"));
            start.WorkingDirectory = root;
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
            start.EnvironmentVariables["DOC_READER_TTS_DEVICE"] = "cpu";
            using (var child = Process.Start(start)) {
                child.WaitForExit();
                if (child.ExitCode != 0) throw new Exception("The local workspace could not start. See the logs in " +
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".doc-reader-managed", "logs"));
            }
        } catch (Exception error) {
            MessageBox.Show(error.Message, "Read Docs", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
