package br.com.sistel.logsis;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebStorage;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/** Native branded shell. Authentication always belongs to the existing HTTPS site. */
public final class MainActivity extends Activity {
    private static final int BLUE = Color.rgb(0, 113, 199);
    private static final int INK = Color.rgb(15, 42, 70);
    private static final int MUTED = Color.rgb(102, 121, 140);
    private static final int PICK_FILE = 40;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private FrameLayout root;
    private View home;
    private LinearLayout browser;
    private FrameLayout pageContainer;
    private LinearLayout statePanel;
    private TextView stateTitle;
    private TextView stateMessage;
    private Button retry;
    private ProgressBar stateSpinner;
    private ProgressBar progress;
    private WebView webView;
    private boolean browsing;
    private boolean failed;
    private String lastTrustedUrl = BuildConfig.SITE_URL;
    private ValueCallback<Uri[]> fileCallback;
    private Runnable watchdog;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.WHITE);
        getWindow().setNavigationBarColor(Color.WHITE);
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);
        setContentView(root);
        if (Build.VERSION.SDK_INT >= 30) {
            getWindow().setDecorFitsSystemWindows(false);
            root.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets system = insets.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout());
                android.graphics.Insets keyboard = insets.getInsets(WindowInsets.Type.ime());
                view.setPadding(system.left, system.top, system.right,
                        Math.max(system.bottom, keyboard.bottom));
                return insets;
            });
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) controller.setSystemBarsAppearance(
                    WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                            | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
                    WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                            | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
        } else {
            root.setFitsSystemWindows(true);
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
                    | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        }
        buildHome();
        buildBrowser();
        if (state != null && state.getBoolean("browsing", false)) {
            browsing = true;
            home.setVisibility(View.GONE);
            browser.setVisibility(View.VISIBLE);
            String savedUrl = state.getString("trusted_url", BuildConfig.SITE_URL);
            load(NavigationPolicy.classify(savedUrl) == NavigationPolicy.Destination.INTERNAL
                    ? savedUrl : BuildConfig.SITE_URL);
        }
    }

    private void buildHome() {
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.WHITE);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER_HORIZONTAL);
        content.setPadding(dp(28), dp(24), dp(28), dp(18));
        scroll.addView(content, new ScrollView.LayoutParams(-1, -1));
        View topSpace = new View(this);
        content.addView(topSpace, new LinearLayout.LayoutParams(1, 0, 1));
        ImageView symbol = image(R.drawable.logsis_symbol, "Símbolo Logsis");
        content.addView(symbol, new LinearLayout.LayoutParams(dp(210), dp(190)));
        TextView name = text("Logsis", 46, BLUE);
        name.setTypeface(Typeface.create("sans-serif-condensed", Typeface.BOLD_ITALIC));
        name.setGravity(Gravity.CENTER);
        content.addView(name);
        TextView description = text("Monitoramento de energia", 16, MUTED);
        description.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sub = new LinearLayout.LayoutParams(-1, -2);
        sub.topMargin = dp(10);
        content.addView(description, sub);
        View accent = new View(this);
        accent.setBackground(shape(Color.rgb(255, 188, 25), 3));
        LinearLayout.LayoutParams line = new LinearLayout.LayoutParams(dp(32), dp(4));
        line.topMargin = dp(28); line.bottomMargin = dp(28);
        content.addView(accent, line);
        Button enter = primaryButton("Acessar sistema");
        LinearLayout.LayoutParams button = new LinearLayout.LayoutParams(-1, dp(56));
        button.setMargins(dp(12), 0, dp(12), 0);
        content.addView(enter, button);
        enter.setOnClickListener(view -> openSystem());
        TextView hint = text("Use seu acesso do sistema Logsis.", 13, MUTED);
        hint.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams hintParams = new LinearLayout.LayoutParams(-1, -2);
        hintParams.topMargin = dp(14);
        content.addView(hint, hintParams);
        Button technician = primaryButton("Área técnica");
        LinearLayout.LayoutParams technicianParams = new LinearLayout.LayoutParams(-1, dp(52));
        technicianParams.setMargins(dp(12), dp(18), dp(12), 0);
        content.addView(technician, technicianParams);
        technician.setOnClickListener(view -> startActivity(new Intent(this, TechnicianActivity.class)));
        content.addView(new View(this), new LinearLayout.LayoutParams(1, dp(35)));
        content.addView(new View(this), new LinearLayout.LayoutParams(1, 0, 1));
        content.addView(image(R.drawable.sistel_logo, "Grupo Sistel — energia confiável"),
                new LinearLayout.LayoutParams(dp(230), dp(92)));
        TextView version = text("Logsis · " + BuildConfig.VERSION_NAME, 10, MUTED);
        version.setGravity(Gravity.CENTER);
        content.addView(version);
        home = scroll;
        root.addView(home, new FrameLayout.LayoutParams(-1, -1));
    }

    private void buildBrowser() {
        browser = new LinearLayout(this);
        browser.setOrientation(LinearLayout.VERTICAL);
        browser.setBackgroundColor(Color.WHITE);
        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(5), 0, dp(5), 0);
        Button back = plainButton("‹", "Voltar");
        back.setTextSize(30);
        toolbar.addView(back, new LinearLayout.LayoutParams(dp(48), -1));
        back.setOnClickListener(view -> navigateBack());
        toolbar.addView(image(R.drawable.logsis_symbol, ""),
                new LinearLayout.LayoutParams(dp(40), dp(40)));
        TextView title = text("Logsis", 22, BLUE);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        title.setPadding(dp(6), 0, 0, 0);
        toolbar.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button menu = plainButton("⋮", "Opções");
        menu.setTextSize(28);
        toolbar.addView(menu, new LinearLayout.LayoutParams(dp(48), -1));
        menu.setOnClickListener(this::showMenu);
        browser.addView(toolbar, new LinearLayout.LayoutParams(-1, dp(58)));
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgressTintList(android.content.res.ColorStateList.valueOf(BLUE));
        browser.addView(progress, new LinearLayout.LayoutParams(-1, dp(3)));
        pageContainer = new FrameLayout(this);
        browser.addView(pageContainer, new LinearLayout.LayoutParams(-1, 0, 1));
        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        WebView.setWebContentsDebuggingEnabled(false);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setMediaPlaybackRequiresUserGesture(true);
        settings.setGeolocationEnabled(false);
        settings.setSafeBrowsingEnabled(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        // No JavaScript bridge, native password fields, TLS overrides or injected scripts.
        webView.setWebViewClient(new SiteClient());
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
            }
            @Override public boolean onShowFileChooser(WebView view,
                    ValueCallback<Uri[]> callback, FileChooserParams parameters) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try {
                    startActivityForResult(parameters.createIntent(), PICK_FILE);
                } catch (ActivityNotFoundException exception) {
                    fileCallback.onReceiveValue(null); fileCallback = null;
                    Toast.makeText(MainActivity.this, "Não foi possível abrir os arquivos.",
                            Toast.LENGTH_SHORT).show();
                }
                return true;
            }
        });
        // The system browser handles downloads; no storage permission is requested.
        webView.setDownloadListener((url, userAgent, disposition, mime, length) -> openExternal(url));
        pageContainer.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        buildStatePanel();
        browser.setVisibility(View.GONE);
        root.addView(browser, new FrameLayout.LayoutParams(-1, -1));
    }

    private void buildStatePanel() {
        statePanel = new LinearLayout(this);
        statePanel.setOrientation(LinearLayout.VERTICAL);
        statePanel.setGravity(Gravity.CENTER);
        statePanel.setPadding(dp(30), dp(24), dp(30), dp(24));
        statePanel.setBackgroundColor(Color.WHITE);
        stateSpinner = new ProgressBar(this);
        stateSpinner.setIndeterminateTintList(android.content.res.ColorStateList.valueOf(BLUE));
        statePanel.addView(stateSpinner, new LinearLayout.LayoutParams(dp(36), dp(36)));
        stateTitle = text("", 21, INK);
        stateTitle.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        stateTitle.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams titleParams = new LinearLayout.LayoutParams(-1, -2);
        titleParams.topMargin = dp(22);
        statePanel.addView(stateTitle, titleParams);
        stateMessage = text("", 15, MUTED);
        stateMessage.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams messageParams = new LinearLayout.LayoutParams(-1, -2);
        messageParams.topMargin = dp(12); messageParams.bottomMargin = dp(26);
        statePanel.addView(stateMessage, messageParams);
        retry = primaryButton("Tentar novamente");
        statePanel.addView(retry, new LinearLayout.LayoutParams(dp(240), dp(52)));
        retry.setOnClickListener(view -> load(lastTrustedUrl));
        pageContainer.addView(statePanel, new FrameLayout.LayoutParams(-1, -1));
    }

    private void openSystem() {
        browsing = true;
        home.setVisibility(View.GONE);
        browser.setVisibility(View.VISIBLE);
        if (webView.getUrl() == null || failed) load(lastTrustedUrl);
    }

    private void load(String url) {
        if (NavigationPolicy.classify(url) != NavigationPolicy.Destination.INTERNAL) return;
        lastTrustedUrl = url;
        webView.loadUrl(url);
    }

    private void showLoading() {
        failed = false;
        stateTitle.setText("Conectando ao Logsis");
        stateMessage.setText("Aguarde enquanto abrimos o sistema.");
        stateSpinner.setVisibility(View.VISIBLE);
        retry.setVisibility(View.GONE);
        statePanel.setVisibility(View.VISIBLE);
        progress.setVisibility(View.VISIBLE);
        cancelWatchdog();
        watchdog = () -> {
            failed = true;
            webView.stopLoading();
            showError("O sistema está demorando para responder",
                    "Verifique sua conexão e tente novamente.");
        };
        handler.postDelayed(watchdog, 35000);
    }

    private void showError(String title, String message) {
        failed = true;
        cancelWatchdog();
        progress.setVisibility(View.INVISIBLE);
        stateTitle.setText(title); stateMessage.setText(message);
        stateSpinner.setVisibility(View.GONE);
        retry.setVisibility(View.VISIBLE);
        statePanel.setVisibility(View.VISIBLE);
    }

    private void cancelWatchdog() {
        if (watchdog != null) handler.removeCallbacks(watchdog);
        watchdog = null;
    }

    private void showMenu(View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add(0, 1, 0, "Atualizar");
        menu.getMenu().add(0, 2, 1, "Página inicial do sistema");
        menu.getMenu().add(0, 3, 2, "Abrir no navegador");
        menu.getMenu().add(0, 4, 3, "Limpar dados de acesso");
        menu.getMenu().add(0, 5, 4, "Sobre o Logsis");
        menu.setOnMenuItemClickListener(item -> {
            switch (item.getItemId()) {
                case 1: load(lastTrustedUrl); break;
                case 2: load(BuildConfig.SITE_URL); break;
                case 3: openExternal(lastTrustedUrl); break;
                case 4: confirmClearSession(); break;
                case 5: new AlertDialog.Builder(this).setTitle("Logsis")
                        .setMessage("Grupo Sistel · Energia confiável\n\nVersão "
                                + BuildConfig.VERSION_NAME + "\nAcesso ao sistema logsis.com.br")
                        .setPositiveButton("Fechar", null).show(); break;
                default: return false;
            }
            return true;
        });
        menu.show();
    }

    private void confirmClearSession() {
        new AlertDialog.Builder(this).setTitle("Limpar dados de acesso?")
                .setMessage("Remove a sessão e os dados do site neste aparelho. Você precisará entrar novamente.")
                .setNegativeButton("Cancelar", null)
                .setPositiveButton("Limpar", (dialog, which) -> {
                    cancelWatchdog();
                    webView.stopLoading();
                    CookieManager.getInstance().removeAllCookies(removed -> {
                        CookieManager.getInstance().flush();
                        WebStorage.getInstance().deleteAllData();
                        webView.clearCache(true); webView.clearHistory(); webView.clearFormData();
                        lastTrustedUrl = BuildConfig.SITE_URL;
                        // Recreate the renderer as well as its history after local sign-out.
                        pageContainer.removeView(webView);
                        webView.destroy();
                        root.removeView(browser);
                        buildBrowser();
                        failed = false;
                        showHome();
                        Toast.makeText(this, "Dados de acesso removidos.", Toast.LENGTH_SHORT).show();
                    });
                }).show();
    }

    private void openExternal(String url) {
        if (NavigationPolicy.classify(url) == NavigationPolicy.Destination.BLOCKED) return;
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addCategory(Intent.CATEGORY_BROWSABLE);
            startActivity(intent);
        } catch (ActivityNotFoundException exception) {
            Toast.makeText(this, "Nenhum navegador disponível.", Toast.LENGTH_SHORT).show();
        }
    }

    private void showHome() {
        browsing = false;
        cancelWatchdog();
        browser.setVisibility(View.GONE);
        home.setVisibility(View.VISIBLE);
    }

    private void navigateBack() {
        if (!browsing) { super.onBackPressed(); return; }
        if (webView.canGoBack() && !failed) webView.goBack(); else showHome();
    }

    @Override public void onBackPressed() { navigateBack(); }
    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        }
    }
    @Override protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putBoolean("browsing", browsing);
        // Do not serialize form contents, passwords or arbitrary third-party URLs.
        outState.putString("trusted_url", BuildConfig.SITE_URL);
    }
    @Override protected void onPause() {
        CookieManager.getInstance().flush();
        if (webView != null) webView.onPause();
        super.onPause();
    }
    @Override protected void onResume() {
        super.onResume();
        if (webView != null) webView.onResume();
    }
    @Override protected void onDestroy() {
        cancelWatchdog();
        if (fileCallback != null) { fileCallback.onReceiveValue(null); fileCallback = null; }
        if (webView != null) { pageContainer.removeView(webView); webView.destroy(); }
        super.onDestroy();
    }

    private final class SiteClient extends WebViewClient {
        @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            // The per-domain HTTP exception belongs only to TechnicianActivity.
            // This also blocks POSTs, which do not call shouldOverrideUrlLoading.
            if ("http".equalsIgnoreCase(request.getUrl().getScheme())) {
                return new WebResourceResponse("text/plain", "utf-8", 403, "Forbidden",
                        java.util.Collections.emptyMap(), new java.io.ByteArrayInputStream(new byte[0]));
            }
            return null;
        }
        @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            if (!request.isForMainFrame()) return !"https".equalsIgnoreCase(request.getUrl().getScheme());
            String url = request.getUrl().toString();
            switch (NavigationPolicy.classify(url)) {
                case INTERNAL: return false;
                case EXTERNAL: openExternal(url); return true;
                default: return true;
            }
        }
        @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
            if ("about:blank".equals(url)) return;
            if (NavigationPolicy.classify(url) != NavigationPolicy.Destination.INTERNAL) {
                view.stopLoading(); return;
            }
            lastTrustedUrl = url;
            showLoading();
        }
        @Override public void onPageFinished(WebView view, String url) {
            if ("about:blank".equals(url)) return;
            cancelWatchdog();
            CookieManager.getInstance().flush();
            progress.setVisibility(View.INVISIBLE);
            if (!failed) statePanel.setVisibility(View.GONE);
        }
        @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) showError("Não foi possível abrir o sistema",
                    "Verifique sua conexão e toque em Tentar novamente.");
        }
        @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
            if (request.isForMainFrame() && response.getStatusCode() >= 500) {
                showError("Sistema temporariamente indisponível", "Tente novamente em alguns instantes.");
            }
        }
        @Override public void onReceivedSslError(WebView view, SslErrorHandler ssl, SslError error) {
            ssl.cancel();
            showError("Não foi possível verificar a conexão", "Tente novamente mais tarde ou entre em contato com o suporte.");
        }
    }

    private ImageView image(int resource, String description) {
        ImageView view = new ImageView(this);
        view.setImageResource(resource);
        view.setScaleType(ImageView.ScaleType.FIT_CENTER);
        if (!description.isEmpty()) view.setContentDescription(description);
        else view.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        return view;
    }
    private TextView text(String value, float size, int color) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(size); view.setTextColor(color);
        return view;
    }
    private Button primaryButton(String label) {
        Button button = new Button(this);
        button.setText(label); button.setTextColor(Color.WHITE); button.setTextSize(16);
        button.setAllCaps(false); button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setBackground(shape(BLUE, 15));
        return button;
    }
    private Button plainButton(String label, String description) {
        Button button = new Button(this);
        button.setText(label); button.setTextColor(BLUE); button.setAllCaps(false);
        button.setContentDescription(description); button.setMinWidth(0); button.setMinimumWidth(0);
        button.setPadding(0, 0, 0, 0); button.setBackgroundColor(Color.TRANSPARENT);
        return button;
    }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(color); drawable.setCornerRadius(dp(radius));
        return drawable;
    }
    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }
}
