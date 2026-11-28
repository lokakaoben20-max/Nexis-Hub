package com.nexishub.app.data

import java.time.Duration
import java.time.Instant

// Espace entreprise : une entreprise est un compte à part, avec son propre
// portefeuille et son équipe (conception du 2026-11-27). L'app ne décide
// d'aucun droit ni d'aucun montant : les droits d'un rôle, l'état de la
// demande, les soldes et les délais viennent du serveur. Les règles
// ci-dessous servent seulement à AFFICHER ce que le serveur autorise ; le
// serveur refuse de toute façon ce qu'un rôle n'a pas le droit de faire.

/** Forme juridique choisie à la création. */
enum class OrgLegalForm { SARL, SARLU, SA, ESTABLISHMENT, OTHER }

/** Ce que l'entreprise fait sur NexisHub. */
enum class OrgActivity {
    ORDERS, PROVIDES, BOTH;

    val orders: Boolean get() = this != PROVIDES
    val provides: Boolean get() = this != ORDERS
}

/** Fonction du représentant dans l'entreprise (texte libre côté serveur). */
enum class OrgFunction { MANAGER, DIRECTOR, OWNER, ACCOUNTANT, OTHER }

/** Les rôles d'un espace entreprise. Un seul représentant actif. */
enum class OrgRole {
    REPRESENTATIVE, MANAGER, ACCOUNTANT, WORKER;

    /** Même tableau que celui du serveur ; l'app s'en sert pour cacher ce
     * qui est interdit, jamais pour l'autoriser. */
    fun can(right: OrgRight): Boolean = when (right) {
        OrgRight.SEE_MISSIONS, OrgRight.SEE_BALANCE, OrgRight.SEE_TEAM -> this != WORKER
        OrgRight.ASSIGN_MISSIONS -> this == REPRESENTATIVE || this == MANAGER
        OrgRight.MANAGE_MEMBERS, OrgRight.MANAGE_NUMBERS, OrgRight.WITHDRAW -> this == REPRESENTATIVE
    }

    /** Les droits proposés pour ce rôle ; le représentant peut les adapter
     * pour chaque personne. */
    val defaultRights: Set<OrgRight> get() = OrgRight.entries.filter { can(it) }.toSet()

    companion object {
        /** Rôles qu'on peut donner en invitant quelqu'un. */
        val invitable = listOf(MANAGER, ACCOUNTANT, WORKER)
    }
}

/** Ce qu'un rôle permet (tableau « Rôles et droits »). */
enum class OrgRight {
    SEE_MISSIONS, SEE_BALANCE, SEE_TEAM, ASSIGN_MISSIONS, MANAGE_MEMBERS, MANAGE_NUMBERS, WITHDRAW;

    /** Ce que le représentant peut adapter pour chaque personne. Les
     * retraits, les numéros et l'équipe restent à lui seul. */
    val isEditable: Boolean get() = this in editable

    companion object {
        val editable = listOf(SEE_MISSIONS, SEE_BALANCE, SEE_TEAM, ASSIGN_MISSIONS)
    }
}

/** Où en est la demande d'ouverture de l'espace. */
enum class OrgStatus {
    /** Envoyée, l'équipe NexisHub vérifie les documents. */
    REVIEWING,

    /** Un document est à refaire. */
    CORRECTION,

    /** Espace ouvert. */
    OPEN,
}

enum class OrgDocKind { RCCM, IDNAT, NIF }

enum class OrgDocState { RECEIVED, TO_ADD, TO_REDO }

data class OrgDocument(val kind: OrgDocKind, val state: OrgDocState)

/** Où en est la personne dans l'équipe. */
enum class OrgMemberStatus {
    /** Identité vérifiée : peut travailler. */
    VERIFIED,

    /** Identité envoyée ou pas encore faite : ne prend pas de mission. */
    TO_VERIFY,

    /** Invitation envoyée, pas encore acceptée. */
    INVITED,
}

data class OrgMember(
    val id: Int,
    val name: String,
    val initials: String,
    val color: Long,
    val role: OrgRole,
    val status: OrgMemberStatus,
    /** Le service d'un intervenant (« Électricité »), s'il en a un. */
    val service: Service? = null,
    /** La personne qui regarde l'écran. */
    val isMe: Boolean = false,
    /** Droits adaptés par le représentant ; sans choix, ceux du rôle. */
    val rights: Set<OrgRight>? = null,
) {
    val effectiveRights: Set<OrgRight> get() = rights ?: role.defaultRights
}

/** Un numéro Mobile Money marchand enregistré pour les retraits. Un numéro
 * ajouté attend 72 h (date donnée par le serveur) avant son premier retrait. */
data class WithdrawNumber(
    val id: Int,
    val operator: MobileOperator,
    /** Numéro national tel que le serveur le montre. */
    val number: String,
    val usableAt: Instant,
) {
    fun hoursLeft(now: Instant = Instant.now()): Int {
        val left = Duration.between(now, usableAt).seconds
        return if (left > 0) ((left + 3599) / 3600).toInt() else 0
    }

    fun isActive(now: Instant = Instant.now()): Boolean = hoursLeft(now) == 0
}

/** Une entreprise de la personne, vue par elle (son rôle compris). */
data class Organization(
    val id: Int,
    /** « Kasa Services SARLU ». */
    val name: String,
    /** « Kasa Services » : le nom court des écrans. */
    val shortName: String,
    val rccm: String,
    val activity: OrgActivity,
    val status: OrgStatus,
    /** Le rôle de la personne qui regarde. */
    val myRole: OrgRole,
    val sentAt: Instant,
    val documents: List<OrgDocument>,
    /** Message de l'équipe quand un document est à refaire. */
    val correctionNote: String? = null,
    val members: List<OrgMember> = emptyList(),
    val numbers: List<WithdrawNumber> = emptyList(),
    /** Solde de l'entreprise ; vide pour un rôle qui ne le voit pas. */
    val wallet: Wallet = Wallet.EMPTY,
    val representative: String = "",
    val email: String = "",
    /** Qui est affecté à chaque mission : numéro de mission → numéros de membres. */
    val assignments: Map<Int, List<Int>> = emptyMap(),
) {
    val isOpen: Boolean get() = status == OrgStatus.OPEN

    /** Ce que la personne qui regarde peut voir ou faire : ses droits
     * propres (adaptés par le représentant), sinon ceux de son rôle. */
    fun can(right: OrgRight): Boolean {
        val me = members.firstOrNull { it.isMe }
        return if (me != null) right in me.effectiveRights else myRole.can(right)
    }

    /** Les missions que la personne a le droit de voir : toutes, ou
     * seulement celles où elle est affectée. */
    fun visible(missions: List<Mission>): List<Mission> {
        if (can(OrgRight.SEE_MISSIONS)) return missions
        val me = members.firstOrNull { it.isMe } ?: return emptyList()
        return missions.filter { assignments[it.id]?.contains(me.id) == true }
    }

    companion object {
        /** « Kasa Services SARLU » devient « Kasa Services ». */
        fun shortName(name: String): String {
            val forms = setOf("SARL", "SARLU", "SA")
            val words = name.split(" ").filter { it.isNotEmpty() && it.uppercase() !in forms }
            return if (words.isEmpty()) name else words.joinToString(" ")
        }
    }
}

/** Ce que la personne saisit pour demander un espace entreprise. Le serveur
 * vérifie tout de nouveau ; ces règles servent à activer ou non « Suivant ». */
data class OrgDraft(
    val name: String = "",
    val rccm: String = "",
    val idnat: String = "",
    val nif: String = "",
    val commune: String? = null,
    val form: OrgLegalForm? = null,
    val activity: OrgActivity? = null,
    val representativeIsMe: Boolean = true,
    /** Téléphone du représentant quand ce n'est pas la personne. */
    val representativePhone: String = "",
    val function: OrgFunction = OrgFunction.MANAGER,
    /** Fonction écrite par la personne quand elle choisit « Autre ». */
    val functionOther: String = "",
    val email: String = "",
    val documents: Set<OrgDocKind> = emptySet(),
) {
    val step1Ready: Boolean
        get() = name.isNotBlank() && rccm.isNotBlank() && idnat.isNotBlank() && nif.isNotBlank() &&
            commune != null && form != null && activity != null && isEmail(email)

    fun step2Ready(identityVerified: Boolean, identityTaken: Boolean): Boolean {
        if (function == OrgFunction.OTHER && functionOther.isBlank()) return false
        if (representativeIsMe) return identityVerified || identityTaken
        return DrcPhone.parse(representativePhone).isValid
    }

    val step3Ready: Boolean get() = documents.size == OrgDocKind.entries.size

    companion object {
        fun isEmail(text: String): Boolean {
            val value = text.trim()
            if (value.contains(" ")) return false
            val at = value.indexOf('@')
            if (at <= 0) return false
            val domain = value.substring(at + 1)
            return domain.contains(".") && !domain.startsWith(".") && !domain.endsWith(".") && !domain.contains("@")
        }
    }
}

/** Écrans entreprise ouverts d'emblée pour les captures de la CI (version de
 * débogage seulement), avec des données dessinées. */
object OrgDemo {
    /** Écrans du parcours de création et de la demande, ouverts depuis le Profil. */
    val profileCaptures = setOf(
        "org-intro", "org-step1", "org-docs", "org-terms", "org-pending", "org-correction", "org-approved",
    )

    /** Un brouillon complet pour les captures (« Kasa Services SARLU »). */
    fun draft(documents: Boolean) = OrgDraft(
        name = "Kasa Services", rccm = "CD/KIN/RCCM/25-B-01234", idnat = "01-F4300-N12345K", nif = "A2512345B",
        commune = "Gombe", form = OrgLegalForm.SARLU, activity = OrgActivity.BOTH, email = "contact@kasaservices.cd",
        documents = if (documents) OrgDocKind.entries.toSet() else emptySet(),
    )

    /** Écrans de l'espace entreprise ouvert, pour le représentant. */
    val representativeCaptures = setOf(
        "org-switch", "org-home", "org-team", "org-invite", "org-roles", "org-numbers", "org-number-add",
        "org-withdraw", "org-member", "org-space-profile", "org-assign",
    )

    /** Vues d'un autre rôle. */
    val roleCaptures = setOf("org-accountant", "org-worker")

    /** Écrans de l'espace entreprise (onglets de l'espace). */
    val spaceCaptures: Set<String> get() = (representativeCaptures - "org-switch") + roleCaptures
}
