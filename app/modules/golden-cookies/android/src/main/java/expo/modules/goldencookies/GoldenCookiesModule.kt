package expo.modules.goldencookies

import android.webkit.CookieManager
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

// Reads the app-wide WebView cookie jar for one URL (to hand an Abed-approved
// session to the twin) and flushes the jar to disk. Nothing is stored here.
class GoldenCookiesModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("GoldenCookies")

    AsyncFunction("getCookie") { url: String ->
      CookieManager.getInstance().getCookie(url)
    }

    AsyncFunction("flush") {
      CookieManager.getInstance().flush()
    }
  }
}
