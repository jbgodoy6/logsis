package br.com.sistel.logsis;

import android.app.AlertDialog;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.TextView;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.Shadows;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.Config;
import org.robolectric.shadows.ShadowAlertDialog;
import org.robolectric.shadows.ShadowPopupMenu;
import org.robolectric.shadows.ShadowLooper;
import java.util.Map;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 28)
public class MainActivityTest {
    private ActivityController<MainActivity> controller;
    private MainActivity activity;

    @Before public void start() {
        controller = Robolectric.buildActivity(MainActivity.class).setup();
        activity = controller.get();
    }
    @After public void stop() { controller.pause().stop().destroy(); }

    private View byText(View view, String text) {
        if (view instanceof TextView && text.contentEquals(((TextView) view).getText())) return view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                View found = byText(group.getChildAt(i), text);
                if (found != null) return found;
            }
        }
        return null;
    }
    private View find(String text) { return byText(activity.getWindow().getDecorView(), text); }
    private WebView web(View view) {
        if (view instanceof WebView) return (WebView) view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                WebView found = web(group.getChildAt(i)); if (found != null) return found;
            }
        }
        return null;
    }
    private WebView web() { return web(activity.getWindow().getDecorView()); }

    @Test public void brandedHomeOpensConfiguredSite() {
        assertNotNull(find("Logsis"));
        find("Acessar sistema").performClick();
        assertEquals(BuildConfig.SITE_URL, Shadows.shadowOf(web()).getLastLoadedUrl());
    }
    @Test public void webConfigurationDoesNotExposeLocalFilesOrMixedContent() {
        WebSettings settings = web().getSettings();
        assertTrue(settings.getJavaScriptEnabled());
        assertTrue(settings.getDomStorageEnabled());
        assertFalse(settings.getAllowFileAccess());
        assertFalse(settings.getAllowContentAccess());
        assertEquals(WebSettings.MIXED_CONTENT_NEVER_ALLOW, settings.getMixedContentMode());
        assertFalse(settings.getJavaScriptCanOpenWindowsAutomatically());
    }
    private WebResourceRequest request(String url) {
        return new WebResourceRequest() {
            public android.net.Uri getUrl() { return android.net.Uri.parse(url); }
            public boolean isForMainFrame() { return true; }
            public boolean isRedirect() { return false; }
            public boolean hasGesture() { return true; }
            public String getMethod() { return "GET"; }
            public Map<String,String> getRequestHeaders() { return Map.of(); }
        };
    }
    @Test public void externalHttpsIsSentToBrowserAndUnsafeSchemesAreBlocked() {
        WebView view = web();
        assertFalse(view.getWebViewClient().shouldOverrideUrlLoading(view, request(BuildConfig.SITE_URL)));
        assertTrue(view.getWebViewClient().shouldOverrideUrlLoading(view, request("https://example.com/help")));
        assertEquals("https://example.com/help", Shadows.shadowOf(activity).getNextStartedActivity().getDataString());
        assertTrue(view.getWebViewClient().shouldOverrideUrlLoading(view, request("file:///private")));
        assertNull(Shadows.shadowOf(activity).getNextStartedActivity());
    }
    @Test public void mainFrameNetworkErrorHasWorkingRetry() {
        find("Acessar sistema").performClick();
        WebView view = web();
        view.getWebViewClient().onPageStarted(view, BuildConfig.SITE_URL, null);
        view.getWebViewClient().onReceivedError(view, request(BuildConfig.SITE_URL), null);
        assertNotNull(find("Não foi possível abrir o sistema"));
        find("Tentar novamente").performClick();
        assertEquals(BuildConfig.SITE_URL, Shadows.shadowOf(view).getLastLoadedUrl());
    }
    @Test public void clearingAccessRecreatesRendererAndDiscardsOldHistory() {
        find("Acessar sistema").performClick();
        WebView old = web();
        find("⋮").performClick();
        ShadowPopupMenu.getLatestPopupMenu().getMenu().performIdentifierAction(4, 0);
        ShadowAlertDialog.getLatestAlertDialog().getButton(AlertDialog.BUTTON_POSITIVE).performClick();
        ShadowLooper.idleMainLooper();
        assertNotSame(old, web());
        assertNull(Shadows.shadowOf(web()).getLastLoadedUrl());
        find("Acessar sistema").performClick();
        assertEquals(BuildConfig.SITE_URL, Shadows.shadowOf(web()).getLastLoadedUrl());
    }
    @Test @Config(sdk = 35) public void currentAndroidAlsoOpensTheBrandedHome() {
        assertNotNull(find("Acessar sistema"));
        find("Acessar sistema").performClick();
        assertEquals(BuildConfig.SITE_URL, Shadows.shadowOf(web()).getLastLoadedUrl());
    }
    @Test public void backFromFirstPageReturnsToWelcome() {
        find("Acessar sistema").performClick();
        activity.onBackPressed();
        assertEquals(View.VISIBLE, find("Acessar sistema").getVisibility());
    }
}
