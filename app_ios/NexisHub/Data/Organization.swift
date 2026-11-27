import Foundation

// Espace entreprise : une entreprise est un compte à part, avec son propre
// portefeuille et son équipe (conception du 2026-11-27). L'app ne décide
// d'aucun droit ni d'aucun montant : les droits d'un rôle, l'état de la
// demande, les soldes et les délais viennent du serveur. Les règles
// ci-dessous servent seulement à AFFICHER ce que le serveur autorise ; le
// serveur refuse de toute façon ce qu'un rôle n'a pas le droit de faire.

/// Forme juridique choisie à la création.
enum OrgLegalForm: String, CaseIterable, Hashable {
    case sarl, sarlu, sa, establishment, other
}

/// Ce que l'entreprise fait sur NexisHub.
enum OrgActivity: String, CaseIterable, Hashable {
    case orders, provides, both

    var orders: Bool { self != .provides }
    var provides: Bool { self != .orders }
}

/// Fonction du représentant dans l'entreprise (texte libre côté serveur).
enum OrgFunction: String, CaseIterable, Hashable {
    case manager, director, owner, accountant, other
}

/// Les rôles d'un espace entreprise. Un seul représentant actif.
enum OrgRole: String, CaseIterable, Hashable {
    case representative, manager, accountant, worker

    /// Rôles qu'on peut donner en invitant quelqu'un.
    static let invitable: [OrgRole] = [.manager, .accountant, .worker]
}

/// Ce qu'un rôle permet (tableau « Rôles et droits »).
enum OrgRight: CaseIterable, Hashable {
    case seeMissions, seeBalance, seeTeam, assignMissions, manageMembers, manageNumbers, withdraw

    /// Ce que le représentant peut adapter pour chaque personne. Les
    /// retraits, les numéros et l'équipe restent à lui seul.
    static let editable: [OrgRight] = [.seeMissions, .seeBalance, .seeTeam, .assignMissions]

    var isEditable: Bool { Self.editable.contains(self) }
}

extension OrgRole {
    /// Même tableau que celui du serveur ; l'app s'en sert pour cacher ce
    /// qui est interdit, jamais pour l'autoriser.
    func can(_ right: OrgRight) -> Bool {
        switch right {
        case .seeMissions, .seeBalance, .seeTeam: return self != .worker
        case .assignMissions: return self == .representative || self == .manager
        case .manageMembers, .manageNumbers, .withdraw: return self == .representative
        }
    }

    /// Les droits proposés pour ce rôle ; le représentant peut les adapter
    /// pour chaque personne.
    var defaultRights: Set<OrgRight> { Set(OrgRight.allCases.filter { can($0) }) }
}

/// Où en est la demande d'ouverture de l'espace.
enum OrgStatus: String, Hashable {
    /// Envoyée, l'équipe NexisHub vérifie les documents.
    case reviewing
    /// Un document est à refaire.
    case correction
    /// Espace ouvert.
    case open
}

enum OrgDocKind: String, CaseIterable, Hashable {
    case rccm, idnat, nif
}

enum OrgDocState: Hashable {
    case received, toAdd, toRedo
}

struct OrgDocument: Identifiable, Hashable {
    let kind: OrgDocKind
    var state: OrgDocState
    var id: String { kind.rawValue }
}

/// Où en est la personne dans l'équipe.
enum OrgMemberStatus: Hashable {
    /// Identité vérifiée : peut travailler.
    case verified
    /// Identité envoyée ou pas encore faite : ne prend pas de mission.
    case toVerify
    /// Invitation envoyée, pas encore acceptée.
    case invited
}

struct OrgMember: Identifiable, Hashable {
    let id: Int
    let name: String
    let initials: String
    let color: UInt32
    let role: OrgRole
    var status: OrgMemberStatus
    /// Le service d'un intervenant (« Électricité »), s'il en a un.
    var service: Service? = nil
    /// La personne qui regarde l'écran.
    var isMe: Bool = false
    /// Droits adaptés par le représentant ; sans choix, ceux du rôle.
    var rights: Set<OrgRight>? = nil

    var effectiveRights: Set<OrgRight> { rights ?? role.defaultRights }
}

/// Un numéro Mobile Money marchand enregistré pour les retraits. Un numéro
/// ajouté attend 72 h (date donnée par le serveur) avant son premier retrait.
struct WithdrawNumber: Identifiable, Hashable {
    let id: Int
    let mobileOperator: MobileOperator
    /// Numéro national tel que le serveur le montre.
    let number: String
    let usableAt: Date

    func hoursLeft(now: Date = .now) -> Int {
        let left = usableAt.timeIntervalSince(now)
        return left > 0 ? Int((left / 3600).rounded(.up)) : 0
    }

    func isActive(now: Date = .now) -> Bool { hoursLeft(now: now) == 0 }
}

/// Une entreprise de la personne, vue par elle (son rôle compris).
struct Organization: Identifiable, Hashable {
    let id: Int
    /// « Kasa Services SARLU ».
    let name: String
    /// « Kasa Services » : le nom court des écrans.
    let shortName: String
    let rccm: String
    var activity: OrgActivity
    var status: OrgStatus
    /// Le rôle de la personne qui regarde.
    var myRole: OrgRole
    var sentAt: Date
    var documents: [OrgDocument]
    /// Message de l'équipe quand un document est à refaire.
    var correctionNote: String? = nil
    var members: [OrgMember] = []
    var numbers: [WithdrawNumber] = []
    /// Solde de l'entreprise ; vide pour un rôle qui ne le voit pas.
    var wallet: Wallet = .empty
    var representative: String = ""
    var email: String = ""
    /// Qui est affecté à chaque mission : numéro de mission → numéros de membres.
    var assignments: [Int: [Int]] = [:]

    var isOpen: Bool { status == .open }

    /// Ce que la personne qui regarde peut voir ou faire : ses droits
    /// propres (adaptés par le représentant), sinon ceux de son rôle.
    func can(_ right: OrgRight) -> Bool {
        if let me = members.first(where: \.isMe) { return me.effectiveRights.contains(right) }
        return myRole.can(right)
    }

    /// Les missions que la personne a le droit de voir : toutes, ou
    /// seulement celles où elle est affectée.
    func visible(_ missions: [Mission]) -> [Mission] {
        if can(.seeMissions) { return missions }
        guard let me = members.first(where: \.isMe) else { return [] }
        return missions.filter { assignments[$0.id]?.contains(me.id) == true }
    }

    /// « Kasa Services SARLU » devient « Kasa Services ».
    static func shortName(of name: String) -> String {
        let forms: Set<String> = ["SARL", "SARLU", "SA"]
        let words = name.split(separator: " ").filter { !forms.contains($0.uppercased()) }
        return words.isEmpty ? name : words.joined(separator: " ")
    }
}

/// Une invitation reçue à rejoindre une équipe.
struct OrgInvitation: Identifiable, Hashable {
    let id: Int
    let orgName: String
    let inviterName: String
    let role: OrgRole
}

/// Ce que la personne remplit pour demander l'espace (étapes 1 à 4).
struct OrgDraft: Equatable {
    var name = ""
    var rccm = ""
    var idnat = ""
    var nif = ""
    var commune: String?
    var form: OrgLegalForm?
    var activity: OrgActivity?
    var representativeIsMe = true
    /// Téléphone du représentant quand ce n'est pas la personne.
    var representativePhone = ""
    var function: OrgFunction = .manager
    /// Fonction écrite par la personne quand elle choisit « Autre ».
    var functionOther = ""
    var email = ""
    var documents: Set<OrgDocKind> = []

    static func isEmail(_ text: String) -> Bool {
        let value = text.trimmingCharacters(in: .whitespaces)
        guard !value.contains(" "), let at = value.firstIndex(of: "@"), at != value.startIndex else { return false }
        let domain = value[value.index(after: at)...]
        return domain.contains(".") && !domain.hasPrefix(".") && !domain.hasSuffix(".") && !domain.contains("@")
    }

    var step1Ready: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
            && !rccm.trimmingCharacters(in: .whitespaces).isEmpty
            && !idnat.trimmingCharacters(in: .whitespaces).isEmpty
            && !nif.trimmingCharacters(in: .whitespaces).isEmpty
            && commune != nil && form != nil && activity != nil
            && Self.isEmail(email)
    }

    func step2Ready(identityVerified: Bool, identityTaken: Bool) -> Bool {
        if function == .other && functionOther.trimmingCharacters(in: .whitespaces).isEmpty { return false }
        if representativeIsMe { return identityVerified || identityTaken }
        return DrcPhone.parse(representativePhone).isValid
    }

    var step3Ready: Bool { documents.count == OrgDocKind.allCases.count }
}

/// Écrans entreprise ouverts d'emblée pour les captures de la CI (versions de
/// débogage seulement), avec des données dessinées.
enum OrgDemo {
    /// Écrans du parcours de création, de l'invitation et de la demande :
    /// ouverts depuis l'onglet Profil.
    static let profileCaptures: Set<String> = [
        "org-profile", "org-intro", "org-step1", "org-rep-verified", "org-rep-unverified", "org-docs", "org-terms",
        "org-pending", "org-correction", "org-approved", "org-invited-verified", "org-invited-unverified",
    ]
    /// Écrans de l'espace entreprise ouvert, pour le représentant.
    static let representativeCaptures: Set<String> = [
        "org-switch", "org-home", "org-team", "org-invite", "org-roles", "org-numbers", "org-number-add",
        "org-withdraw", "org-member", "org-photo", "org-space-profile", "org-assign",
    ]
    /// Vues d'un autre rôle.
    static let roleCaptures: Set<String> = ["org-accountant", "org-worker"]
    /// Écrans de l'espace entreprise (onglets de l'espace).
    static var spaceCaptures: Set<String> {
        representativeCaptures.subtracting(["org-switch"]).union(roleCaptures)
    }
    /// Un brouillon complet pour les captures (« Kasa Services SARLU »).
    static func draft(documents: Bool) -> OrgDraft {
        var draft = OrgDraft()
        draft.name = "Kasa Services"
        draft.rccm = "CD/KIN/RCCM/25-B-01234"
        draft.idnat = "01-F4300-N12345K"
        draft.nif = "A2512345B"
        draft.commune = "Gombe"
        draft.form = .sarlu
        draft.activity = .both
        draft.email = "contact@kasaservices.cd"
        if documents { draft.documents = Set(OrgDocKind.allCases) }
        return draft
    }

    static var all: Set<String> { profileCaptures.union(representativeCaptures).union(roleCaptures) }
}
