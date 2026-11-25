package com.nexishub.app.ui

import com.nexishub.app.R
import com.nexishub.app.data.CatalogService
import com.nexishub.app.data.Service

/** Pictogrammes de services : Phosphor Icons (duotone) et Tabler Icons,
 * licence MIT, dans res/drawable.
 *
 * Pour chaque service, la première icône est l'icône principale ; les
 * suivantes forment le tour animé de « Quel service ? ». Même liste que
 * outils/pictogrammes_apps_natives.py et l'app iOS (Pictogrammes.swift). */
object Pictogrammes {
    val byService: Map<String, List<Int>> = mapOf(
        "plomberie" to listOf(R.drawable.ph_wrench, R.drawable.ph_pipe, R.drawable.ph_shower, R.drawable.ph_toilet),
        "electricite" to listOf(R.drawable.ph_lightning, R.drawable.ph_plug, R.drawable.ph_lightbulb, R.drawable.ph_power),
        "climatisation" to listOf(R.drawable.ph_snowflake, R.drawable.ph_fan, R.drawable.ph_wind, R.drawable.ph_thermometer),
        "informatique" to listOf(R.drawable.ph_laptop, R.drawable.ph_monitor, R.drawable.ph_printer, R.drawable.ph_wifi_high),
        "graphisme" to listOf(R.drawable.ph_pen_nib, R.drawable.ph_palette, R.drawable.ph_paint_brush, R.drawable.ph_image),
        "coiffure" to listOf(R.drawable.ph_scissors, R.drawable.tb_razor_electric, R.drawable.ph_hair_dryer, R.drawable.ph_armchair),
        "nettoyage" to listOf(R.drawable.ph_broom, R.drawable.ph_spray_bottle, R.drawable.ph_washing_machine, R.drawable.ph_hand_soap),
        "jardinage" to listOf(R.drawable.ph_plant, R.drawable.ph_flower, R.drawable.ph_tree_palm, R.drawable.ph_shovel),
        "autre" to listOf(R.drawable.ph_squares_four),
        "peinture" to listOf(R.drawable.ph_paint_roller, R.drawable.ph_paint_bucket, R.drawable.ph_palette, R.drawable.ph_paint_brush_household),
        "demenagement" to listOf(R.drawable.ph_truck, R.drawable.ph_package, R.drawable.ph_key, R.drawable.ph_truck_trailer),
    )

    /** Icône d'un service que l'app ne connaît pas encore (publié par le serveur). */
    val fallback: List<Int> = listOf(R.drawable.ph_squares_four)

    fun icons(service: Service): List<Int> = byService[service.name.lowercase()] ?: fallback

    fun icons(item: CatalogService): List<Int> = byService[item.id] ?: item.service?.let(::icons) ?: fallback
}
