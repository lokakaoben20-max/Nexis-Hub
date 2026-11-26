import Foundation

/// Pictogrammes de services : Phosphor Icons (duotone) et Tabler Icons,
/// licence MIT, dans Resources/Pictogrammes.xcassets.
///
/// Pour chaque service, la première icône est l'icône principale ; les
/// suivantes forment le tour animé de « Quel service ? ». Même liste que
/// outils/pictogrammes_apps_natives.py et l'app Android (Pictogrammes.kt).
enum Pictogrammes {
    static let byService: [String: [String]] = [
        "plomberie": ["ph_wrench", "ph_pipe", "ph_shower", "ph_toilet"],
        "electricite": ["ph_lightning", "ph_plug", "ph_lightbulb", "ph_power"],
        "climatisation": ["ph_snowflake", "ph_fan", "ph_wind", "ph_thermometer"],
        "informatique": ["ph_laptop", "ph_monitor", "ph_printer", "ph_wifi_high"],
        "graphisme": ["ph_pen_nib", "ph_palette", "ph_paint_brush", "ph_image"],
        "coiffure": ["ph_scissors", "tb_razor_electric", "ph_hair_dryer", "ph_armchair"],
        "nettoyage": ["ph_broom", "ph_spray_bottle", "ph_washing_machine", "ph_hand_soap"],
        "jardinage": ["ph_plant", "ph_flower", "ph_tree_palm", "ph_shovel"],
        "autre": ["ph_squares_four"],
        "peinture": ["ph_paint_roller", "ph_paint_bucket", "ph_palette", "ph_paint_brush_household"],
        "demenagement": ["ph_truck", "ph_package", "ph_key", "ph_truck_trailer"],
    ]

    /// Icône d'un service que l'app ne connaît pas encore (publié par le serveur).
    static let fallback = ["ph_squares_four"]

    static func icons(for service: Service) -> [String] {
        byService[service.rawValue] ?? fallback
    }

    static func icons(forCatalogId id: String, service: Service?) -> [String] {
        byService[id] ?? service.map(icons(for:)) ?? fallback
    }
}
