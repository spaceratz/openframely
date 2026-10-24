package au.openframely.kiosk;

import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;

/**
 * Runs shell commands on this device as the adb "shell" user by speaking the
 * adb wire protocol to the board's own adbd on 127.0.0.1:5555.
 *
 * The kiosk is a standard APK (the board uses a vendor platform key rather than
 * AOSP's), while the shell user can change Wi-Fi, timezone, brightness and
 * screen power. With ro.adb.secure=0 and TCP 5555 started by our init rc, the
 * APK applies device settings locally on the board.
 */
final class LocalShell {
    private static final int A_CNXN = 0x4e584e43, A_OPEN = 0x4e45504f, A_OKAY = 0x59414b4f,
        A_WRTE = 0x45545257, A_CLSE = 0x45534c43, A_AUTH = 0x48545541;
    private static final int VERSION = 0x01000000, MAX_DATA = 256 * 1024;

    private LocalShell() {}

    /** Run one command, return combined stdout/stderr. Blocking, call off the UI thread. */
    static synchronized String run(String command) throws IOException {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress("127.0.0.1", 5555), 3000);
            s.setSoTimeout(30000);
            OutputStream out = s.getOutputStream();
            DataInputStream in = new DataInputStream(s.getInputStream());
            send(out, A_CNXN, VERSION, MAX_DATA, "host::kiosk\0".getBytes(StandardCharsets.UTF_8));
            Msg m = read(in);
            if (m.cmd == A_AUTH) throw new IOException("adbd wants auth (ro.adb.secure is on)");
            if (m.cmd != A_CNXN) throw new IOException("unexpected adb reply " + Integer.toHexString(m.cmd));
            int local = 1;
            send(out, A_OPEN, local, 0, ("shell:" + command + "\0").getBytes(StandardCharsets.UTF_8));
            ByteArrayOutputStream result = new ByteArrayOutputStream();
            int remote = 0;
            while (true) {
                m = read(in);
                if (m.cmd == A_OKAY) { remote = m.arg0; continue; }
                if (m.cmd == A_WRTE) { result.write(m.data); send(out, A_OKAY, local, m.arg0, new byte[0]); continue; }
                if (m.cmd == A_CLSE) { if (remote != 0) send(out, A_CLSE, local, remote, new byte[0]); break; }
            }
            return result.toString("UTF-8");
        }
    }

    private static final class Msg { int cmd, arg0, arg1; byte[] data; }

    private static void send(OutputStream out, int cmd, int arg0, int arg1, byte[] data) throws IOException {
        int sum = 0;
        for (byte b : data) sum += b & 0xff;
        ByteBuffer h = ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN);
        h.putInt(cmd).putInt(arg0).putInt(arg1).putInt(data.length).putInt(sum).putInt(~cmd);
        out.write(h.array());
        out.write(data);
        out.flush();
    }

    private static Msg read(DataInputStream in) throws IOException {
        byte[] hb = new byte[24];
        in.readFully(hb);
        ByteBuffer h = ByteBuffer.wrap(hb).order(ByteOrder.LITTLE_ENDIAN);
        Msg m = new Msg();
        m.cmd = h.getInt(); m.arg0 = h.getInt(); m.arg1 = h.getInt();
        int len = h.getInt();
        m.data = new byte[len];
        in.readFully(m.data);
        return m;
    }

    /** Single-quote for sh. */
    static String q(String s) { return "'" + s.replace("'", "'\\''") + "'"; }
}
