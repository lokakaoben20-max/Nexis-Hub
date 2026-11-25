package com.nexishub.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.Crossfade
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.nexishub.app.data.DemoRepository
import com.nexishub.app.data.Texts
import com.nexishub.app.screens.EntryFlow
import com.nexishub.app.screens.Shell
import com.nexishub.app.ui.NexisTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        val texts = Texts(assets.open("textes.json").bufferedReader().use { it.readText() })
        // Captures d'écran de la CI uniquement (version de débogage) :
        // ouvre directement l'écran demandé avec les données fictives.
        val capture = if (BuildConfig.DEBUG) Capture.from(intent.getStringExtra("capture")) else null
        val app = AppModel(DemoRepository(), texts, intent.getStringExtra("language") ?: AppModel.defaultLanguage())
        if (capture?.signedIn == true) app.signIn()
        setContent {
            NexisTheme {
                CompositionLocalProvider(LocalApp provides app) {
                    NexisRoot(app, capture)
                }
            }
        }
    }
}

@Composable
fun NexisRoot(app: AppModel, capture: Capture?) {
    val start = remember { capture }
    Crossfade(targetState = app.signedIn, label = "session") { signedIn ->
        if (signedIn) Shell(start) else EntryFlow(start)
    }
}

/** Écrans que la CI photographie (voir .github/workflows/apps-natives.yml). */
enum class Capture(val signedIn: Boolean, val tab: Int? = null, val entry: String? = null, val picker: Boolean = false) {
    WELCOME(false, entry = "welcome"),
    PHONE(false, entry = "phone"),
    SIGNUP(false, entry = "signup"),
    HOME(true, tab = 0),
    MISSIONS(true, tab = 1),
    WALLET(true, tab = 2),
    PROFILE(true, tab = 3),
    SERVICES(true, tab = 0, picker = true);

    companion object {
        fun from(value: String?): Capture? = entries.firstOrNull { it.name.equals(value, ignoreCase = true) }
    }
}
