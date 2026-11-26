package com.nexishub.app.data

/** Opérateurs mobiles de la RDC, d'après les deux chiffres qui suivent
 * +243. Contrôle de confort à la saisie seulement : le serveur reste seul
 * juge du numéro (backend/app/app_auth.py). Même règle que
 * app_mobile/lib/ui/phone.dart. */
enum class DrcOperator(val prefixes: Set<String>) {
    VODACOM(setOf("81", "82", "83")),
    AIRTEL(setOf("97", "98", "99")),
    ORANGE(setOf("80", "84", "85", "89")),
    AFRICELL(setOf("90", "91")),
}

/** Le numéro national saisi : 9 chiffres, sans le 0 d'appel ni le +243. */
data class DrcPhone(val digits: String) {
    companion object {
        const val LENGTH = 9

        /** Garde les chiffres, retire un +243 / 00243 / 243 ou un 0 d'appel
         * collé en tête, et coupe à 9 chiffres. */
        fun parse(raw: String): DrcPhone {
            var d = raw.filter { it in '0'..'9' }
            d = when {
                d.startsWith("00243") -> d.drop(5)
                d.startsWith("243") && d.length > LENGTH -> d.drop(3)
                d.startsWith("0") -> d.drop(1)
                else -> d
            }
            return DrcPhone(d.take(LENGTH))
        }
    }

    val isComplete: Boolean get() = digits.length == LENGTH

    val operator: DrcOperator?
        get() = if (digits.length < 2) null else DrcOperator.entries.firstOrNull { digits.take(2) in it.prefixes }

    /** Faux dès que les deux premiers chiffres ne sont ceux d'aucun opérateur. */
    val prefixKnown: Boolean get() = digits.length < 2 || operator != null

    val isValid: Boolean get() = isComplete && operator != null

    /** `81 234 5678` (maquette de connexion). */
    val formatted: String
        get() {
            val parts = mutableListOf<String>()
            var rest = digits
            for (size in listOf(2, 3, 4)) {
                if (rest.isEmpty()) break
                parts += rest.take(size)
                rest = rest.drop(size)
            }
            return parts.joinToString(" ")
        }

    /** Format international attendu par le serveur : `+243812345454`. */
    val e164: String get() = "+243$digits"
}
