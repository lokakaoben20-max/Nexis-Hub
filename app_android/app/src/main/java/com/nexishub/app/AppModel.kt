package com.nexishub.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import com.nexishub.app.data.AppSecurity
import com.nexishub.app.data.CodeRules
import com.nexishub.app.data.Currency
import com.nexishub.app.data.Money
import com.nexishub.app.data.NexisRepository
import com.nexishub.app.data.Texts
import java.time.Instant
import java.util.Locale
import kotlinx.coroutines.CompletableDeferred

/** État partagé de l'app : langue, session, réglages d'affichage du
 * portefeuille, et accès aux données. */
class AppModel(
    val repository: NexisRepository,
    private val texts: Texts,
    /** Code NexisHub et empreinte de ce téléphone. */
    val security: AppSecurity,
    language: String = defaultLanguage(),
) {
    /** « fr », « ln » ou « en ». Le français est la langue par défaut. */
    var language by mutableStateOf(language)
    var signedIn by mutableStateOf(false)
        private set
    var walletCurrency by mutableStateOf(Currency.CDF)
    var amountsHidden by mutableStateOf(false)

    /** Espace prestataire ouvert (seulement pour un compte prestataire). */
    var providerSpace by mutableStateOf(false)

    /** Onglet demandé par un écran (« Voir mon portefeuille ») ; le cadre
     * l'ouvre puis l'efface. */
    var requestedTab by mutableStateOf<Int?>(null)

    /** L'app demande le code (ou l'empreinte) avant de montrer quoi que ce soit. */
    var locked by mutableStateOf(false)

    /** Cache posé quand l'app passe en arrière-plan. */
    var covered by mutableStateOf(false)
        private set

    /** Sortie d'argent en attente de confirmation par le code ou l'empreinte. */
    var gate by mutableStateOf<MoneyGate?>(null)
        private set

    /** Écran de protection encore ouvert après la création du code
     * (empreinte, puis « Votre compte est protégé »). */
    var finishingProtection by mutableStateOf(false)

    private var leftAt: Instant? = null

    init {
        // Le code part avec la session : l'app s'ouvre sans session, donc un
        // code resté d'une session précédente ne sert plus.
        security.erase()
    }

    /** Écran ouvert d'emblée pour les captures de la CI (version de débogage). */
    var capture: String? = null

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

    /** Le compte est ouvert mais ce téléphone n'a pas encore de code. */
    val needsProtection: Boolean get() = signedIn && !security.hasCode

    /** L'app passe en arrière-plan. */
    fun left(at: Instant = Instant.now()) {
        if (!signedIn) return
        leftAt = at
        covered = true
    }

    /** L'app revient : verrou si elle est restée fermée au moins une minute. */
    fun cameBack(at: Instant = Instant.now()) {
        covered = false
        if (signedIn && security.hasCode && CodeRules.shouldLock(leftAt, at)) {
            locked = true
            finishGate(false)
        }
        leftAt = null
    }

    /** Demande le code ou l'empreinte avant une sortie d'argent. Faux si la
     * personne annule : rien ne part. */
    suspend fun confirmMoneyOut(reason: String): Boolean {
        if (!security.hasCode) return false
        finishGate(false)
        val pending = MoneyGate(reason)
        gate = pending
        return pending.answer.await()
    }

    /** Termine la demande en cours, une seule fois. */
    fun finishGate(confirmed: Boolean) {
        val pending = gate ?: return
        gate = null
        pending.answer.complete(confirmed)
    }

    fun signOut() {
        finishGate(false)
        security.erase()
        locked = false
        covered = false
        finishingProtection = false
        leftAt = null
        signedIn = false
        amountsHidden = false
        walletCurrency = Currency.CDF
        providerSpace = false
        requestedTab = null
    }

    companion object {
        val languages = listOf("fr", "ln", "en")

        fun defaultLanguage(): String =
            Locale.getDefault().language.takeIf { it in languages } ?: "fr"
    }
}

/** Une sortie d'argent qui attend le code ou l'empreinte. */
class MoneyGate(val reason: String) {
    val answer = CompletableDeferred<Boolean>()
}

val LocalApp = staticCompositionLocalOf<AppModel> { error("AppModel absent") }
