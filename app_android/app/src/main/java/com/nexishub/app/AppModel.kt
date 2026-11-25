package com.nexishub.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import com.nexishub.app.data.Currency
import com.nexishub.app.data.Money
import com.nexishub.app.data.NexisRepository
import com.nexishub.app.data.Texts
import java.util.Locale

/** État partagé de l'app : langue, session, réglages d'affichage du
 * portefeuille, et accès aux données. */
class AppModel(
    val repository: NexisRepository,
    private val texts: Texts,
    language: String = defaultLanguage(),
) {
    /** « fr », « ln » ou « en ». Le français est la langue par défaut. */
    var language by mutableStateOf(language)
    var signedIn by mutableStateOf(false)
        private set
    var walletCurrency by mutableStateOf(Currency.CDF)
    var amountsHidden by mutableStateOf(false)

    /** Change quand des données changent : les écrans relisent alors le dépôt. */
    var revision by mutableIntStateOf(0)
        private set

    /** Locale des dates et des nombres (le lingala emprunte le français). */
    val locale: Locale get() = Locale.forLanguageTag(if (language == "ln") "fr" else language)

    fun t(key: String, vararg args: Pair<String, String>): String = texts.text(key, language, args.toMap())

    fun plural(key: String, count: Int, vararg args: Pair<String, String>): String =
        texts.plural(key, language, count, args.toMap())

    fun money(value: Money): String = value.formatted(language)

    fun dataChanged() {
        revision++
    }

    fun signIn() {
        signedIn = true
    }

    fun signOut() {
        signedIn = false
        amountsHidden = false
        walletCurrency = Currency.CDF
    }

    companion object {
        val languages = listOf("fr", "ln", "en")

        fun defaultLanguage(): String =
            Locale.getDefault().language.takeIf { it in languages } ?: "fr"
    }
}

val LocalApp = staticCompositionLocalOf<AppModel> { error("AppModel absent") }
