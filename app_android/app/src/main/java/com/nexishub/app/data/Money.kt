package com.nexishub.app.data

import kotlin.math.absoluteValue

/** Montants : la seule façon d'afficher de l'argent dans l'app.
 *
 * L'app ne calcule jamais d'argent : elle affiche les montants que le
 * serveur Nexis envoie, en unités mineures et sans virgule flottante,
 * avec les règles de la charte : « 25 000 FC » sans décimales et
 * « 12,50 USD » toujours avec deux décimales. */
enum class Currency { CDF, USD }

data class Money(
    /** Francs congolais : en francs. Dollars : en cents. */
    val minorUnits: Long,
    val currency: Currency,
) {
    val isZero: Boolean get() = minorUnits == 0L

    /** Même règle que l'app Flutter (`formatMoney`) : espace fine
     * insécable en français et en lingala, virgule en anglais. */
    fun formatted(language: String): String {
        val english = language == "en"
        val group = if (english) "," else " "
        val sign = if (minorUnits < 0) "−" else ""
        val absolute = minorUnits.absoluteValue

        fun grouped(value: Long): String {
            val digits = value.toString()
            val out = StringBuilder()
            digits.forEachIndexed { i, digit ->
                if (i > 0 && (digits.length - i) % 3 == 0) out.append(group)
                out.append(digit)
            }
            return out.toString()
        }

        return when (currency) {
            Currency.CDF -> "$sign${grouped(absolute)} FC"
            Currency.USD -> {
                val cents = (absolute % 100).toString().padStart(2, '0')
                "$sign${grouped(absolute / 100)}${if (english) "." else ","}$cents USD"
            }
        }
    }
}
