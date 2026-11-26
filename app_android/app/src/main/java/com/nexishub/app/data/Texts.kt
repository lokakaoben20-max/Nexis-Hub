package com.nexishub.app.data

import org.json.JSONObject

/** Les textes de Nexis en français, lingala et anglais.
 *
 * Source unique : app_mobile/lib/l10n/ *.arb, copiés dans
 * assets/textes.json par outils/textes_apps_natives.py. Rien n'est
 * traduit ici. */
class Texts(json: String) {
    private sealed interface Entry {
        data class Text(val value: String) : Entry
        data class Plural(val forms: Map<String, String>) : Entry
    }

    private val table: Map<String, Map<String, Entry>>

    init {
        val root = JSONObject(json)
        val out = mutableMapOf<String, Map<String, Entry>>()
        for (key in root.keys()) {
            val languages = root.getJSONObject(key)
            val entries = mutableMapOf<String, Entry>()
            for (language in languages.keys()) {
                val value = languages.get(language)
                entries[language] = if (value is JSONObject) {
                    Entry.Plural(value.keys().asSequence().associateWith { value.getString(it) })
                } else {
                    Entry.Text(value.toString())
                }
            }
            out[key] = entries
        }
        table = out
    }

    fun has(key: String, language: String): Boolean = table[key]?.containsKey(language) == true

    /** Texte simple. Les variables {nom} sont remplacées par `args`. */
    fun text(key: String, language: String, args: Map<String, String> = emptyMap()): String =
        when (val entry = entry(key, language)) {
            null -> key
            is Entry.Text -> fill(entry.value, args)
            is Entry.Plural -> fill(entry.forms["other"] ?: key, args)
        }

    /** Texte au pluriel ICU : « =0 », « =1 », sinon « other ». */
    fun plural(key: String, language: String, count: Int, args: Map<String, String> = emptyMap()): String {
        val values = args + ("count" to count.toString())
        return when (val entry = entry(key, language)) {
            null -> key
            is Entry.Text -> fill(entry.value, values)
            is Entry.Plural -> fill(entry.forms["=$count"] ?: entry.forms["other"] ?: key, values)
        }
    }

    private fun entry(key: String, language: String): Entry? = table[key]?.let { it[language] ?: it["fr"] }

    private fun fill(text: String, args: Map<String, String>): String =
        args.entries.fold(text) { acc, (name, value) -> acc.replace("{$name}", value) }
}
