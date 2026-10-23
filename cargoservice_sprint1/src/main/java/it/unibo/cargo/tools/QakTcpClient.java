package it.unibo.cargo.tools;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;
import org.json.JSONObject;

/** Client TCP line-oriented del protocollo QAK, usato da simulatore e test. */
public final class QakTcpClient implements AutoCloseable {
    private static final AtomicInteger SEQUENCE = new AtomicInteger();
    private final Socket socket;
    private final BufferedReader reader;
    private final BufferedWriter writer;
    private final String sender;
    private final String receiver;
    public QakTcpClient(int port, String receiver) throws IOException {
        this.sender = "client" + SEQUENCE.incrementAndGet();
        this.receiver = receiver;
        socket = new Socket();
        socket.connect(new InetSocketAddress("127.0.0.1", port), 2000);
        socket.setSoTimeout(15000);
        reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
        writer = new BufferedWriter(new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8));
    }
    public void send(String id, String kind, String args) throws IOException {
        writer.write("msg(" + id + "," + kind + "," + sender + "," + receiver + "," + id + "(" + args + ")," + SEQUENCE.incrementAndGet() + ")\n");
        writer.flush();
    }
    public String request(String id, String args) throws IOException {
        send(id, "request", args);
        String response = reader.readLine();
        if (response == null) throw new EOFException("No reply for " + id);
        return response;
    }
    public JSONObject json(String id) throws IOException {
        String response = request(id, "none");
        int start = response.indexOf('{');
        int end = response.lastIndexOf('}');
        if (start < 0 || end < start) throw new IOException("Expected JSON reply: " + response);
        return new JSONObject(response.substring(start, end + 1));
    }
    public void close() throws IOException { socket.close(); }
}
