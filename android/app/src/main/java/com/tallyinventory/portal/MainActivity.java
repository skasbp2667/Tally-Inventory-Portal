package com.tallyinventory.portal;

import android.app.Activity;
import android.os.Bundle;
import android.content.SharedPreferences;
import android.text.InputType;
import android.view.ViewGroup;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final String BASE = "https://tally-api-prod-production.up.railway.app";
    private ExecutorService ex = Executors.newSingleThreadExecutor();
    private SharedPreferences sp;
    private LinearLayout root;
    private EditText user, pass;
    private TextView status;
    private String token = "";

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        sp = getSharedPreferences("cache", MODE_PRIVATE);
        token = sp.getString("token", "");
        if (token.isEmpty()) showLogin(); else showHome();
    }

    private TextView tv(String s) {
        TextView t = new TextView(this);
        t.setText(s); t.setTextSize(16); t.setPadding(20, 16, 20, 16);
        return t;
    }

    private void base() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(20, 20, 20, 20);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);
    }

    private Button button(String s) {
        Button b = new Button(this); b.setText(s);
        b.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return b;
    }

    private void showLogin() {
        base();
        root.addView(tv("TALLY INVENTORY PORTAL"));
        root.addView(tv("Secure sign-in"));
        user = new EditText(this); user.setHint("Username"); root.addView(user);
        pass = new EditText(this); pass.setHint("Password"); pass.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD); root.addView(pass);
        Button x = button("LOGIN"); root.addView(x);
        status = tv(""); root.addView(status);
        x.setOnClickListener(v -> login());
    }

    private void login() {
        status.setText("Signing in...");
        String u = user.getText().toString().trim(), p = pass.getText().toString();
        ex.submit(() -> {
            try {
                JSONObject j = post("/auth/login", new JSONObject().put("username", u).put("password", p));
                token = j.getString("access_token");
                sp.edit().putString("token", token).apply();
                runOnUiThread(this::showHome);
            } catch (Exception e) { runOnUiThread(() -> status.setText("Login failed: " + e.getMessage())); }
        });
    }

    private void showHome() {
        base();
        root.addView(tv("TALLY INVENTORY PORTAL"));
        Button s = button("STOCK / INVENTORY");
        Button l = button("LEDGERS");
        Button r = button("REFRESH DATA");
        Button logout = button("LOG OUT");
        root.addView(s); root.addView(l); root.addView(r); root.addView(logout);
        status = tv("Ready"); root.addView(status);
        s.setOnClickListener(v -> load("/api/stock", "stock"));
        l.setOnClickListener(v -> load("/api/ledgers", "ledgers"));
        r.setOnClickListener(v -> { load("/api/stock", "stock"); load("/api/ledgers", "ledgers"); });
        logout.setOnClickListener(v -> { sp.edit().remove("token").apply(); token=""; showLogin(); });
    }

    private void load(String path, String key) {
        status.setText("Loading...");
        ex.submit(() -> {
            try {
                JSONObject j = get(path);
                sp.edit().putString(key, j.toString()).apply();
                runOnUiThread(() -> showData(key, j));
            } catch (Exception e) {
                try {
                    JSONObject j = new JSONObject(sp.getString(key, "{\"status\":\"OFFLINE\",\"items\":[]}"));
                    runOnUiThread(() -> showData(key, j));
                } catch (Exception z) { runOnUiThread(() -> status.setText("No connection and no cached data")); }
            }
        });
    }

    private void showData(String key, JSONObject j) {
        base();
        root.addView(tv(key.toUpperCase()));
        root.addView(tv("Status: " + j.optString("status", "CACHED")));
        root.addView(tv(formatItems(j)));
        Button back = button("BACK"); root.addView(back);
        back.setOnClickListener(v -> showHome());
    }

    private String formatItems(JSONObject j) {
        StringBuilder b = new StringBuilder();
        JSONArray a = j.optJSONArray("items");
        if (a == null || a.length() == 0) return "No data available.\n\nThe app will use the last cached data when the server is unavailable.";
        for (int i=0; i<a.length(); i++) {
            JSONObject o = a.optJSONObject(i);
            if (o != null) {
                b.append("Name: ").append(o.optString("name","")).append("\n");
                b.append("Code: ").append(o.optString("code","")).append("\n");
                b.append("Quantity: ").append(o.optString("quantity",o.optString("closing",""))).append("\n");
                b.append("Unit/Parent: ").append(o.optString("unit",o.optString("parent",""))).append("\n\n");
            } else b.append(a.optString(i)).append("\n\n");
        }
        return b.toString();
    }

    private JSONObject get(String path) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(BASE+path).openConnection();
        c.setRequestMethod("GET"); c.setConnectTimeout(15000); c.setReadTimeout(30000);
        c.setRequestProperty("Authorization","Bearer "+token); return read(c);
    }

    private JSONObject post(String path, JSONObject body) throws Exception {
        HttpURLConnection c=(HttpURLConnection)new URL(BASE+path).openConnection();
        c.setRequestMethod("POST"); c.setDoOutput(true); c.setConnectTimeout(15000); c.setReadTimeout(30000);
        c.setRequestProperty("Content-Type","application/json");
        try(OutputStream o=c.getOutputStream()){o.write(body.toString().getBytes("UTF-8"));}
        return read(c);
    }

    private JSONObject read(HttpURLConnection c) throws Exception {
        int code=c.getResponseCode();
        InputStream in=code<400?c.getInputStream():c.getErrorStream();
        BufferedReader br=new BufferedReader(new InputStreamReader(in));
        StringBuilder b=new StringBuilder(); String q;
        while((q=br.readLine())!=null)b.append(q);
        if(code>=400)throw new Exception(b.toString());
        return new JSONObject(b.toString());
    }

    @Override protected void onDestroy(){ ex.shutdownNow(); super.onDestroy(); }
}
