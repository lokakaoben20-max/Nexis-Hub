package com.nexishub.app.data

import java.time.Duration
import java.time.Instant
import java.time.LocalDate

/** Ce que les écrans lisent. Une seule source : le serveur Nexis.
 *
 * Aujourd'hui seule l'implémentation de démonstration existe (données
 * fictives, aucun appel réseau, aucun argent). La connexion au serveur
 * (/api/app/v1) la remplacera sans changer les écrans. */
interface NexisRepository {
    /** Canaux par lesquels le serveur envoie réellement un code. Un canal
     * absent n'est pas montré : jamais d'option qui fait semblant. */
    val codeChannels: List<CodeChannel>
    val communes: List<String>
    val signupTermsVersion: LocalDate

    /** Demande au serveur d'envoyer le code de connexion par ce canal. */
    suspend fun sendCode(phone: String, channel: CodeChannel)

    /** Démonstration : ouvre le compte du numéro s'il existe. */
    fun openAccount(phone: String): Boolean

    /** Crée le profil seulement si les conditions en vigueur sont acceptées. */
    fun registerClient(
        phone: String, firstName: String, lastName: String,
        commune: String, acceptedTermsVersion: LocalDate?,
    ): Boolean

    suspend fun profile(): Profile
    suspend fun wallet(): Wallet
    suspend fun missions(): List<Mission>
    suspend fun movements(): List<Movement>

    /** Le catalogue des services, dans l'ordre voulu par le serveur. */
    suspend fun serviceCatalog(): List<CatalogService>

    /** Crée une mission en attente de devis pour un service du catalogue. */
    suspend fun requestService(serviceId: String, commune: String, description: String)

    /** « Décrire mon besoin » : une demande libre transmise à l'équipe. */
    suspend fun sendFreeRequest(title: String, text: String)
}

/** Données FICTIVES de l'aperçu, reprises de l'app Flutter
 * (app_mobile/lib/data/demo_repository.dart). */
class DemoRepository(private val now: Instant = Instant.now()) : NexisRepository {
    private companion object {
        const val SAMPLE_PHONE = "+243812345412"
    }

    private var activePhone = SAMPLE_PHONE
    private val registered = mutableMapOf<String, Profile>()
    private val requested = mutableMapOf<String, MutableList<Mission>>()
    private var nextRequestId = 1000

    override val codeChannels = listOf(CodeChannel.WHATSAPP, CodeChannel.TELEGRAM, CodeChannel.SMS)

    /** Démonstration : aucun message ne part. L'envoi réel prend un moment ;
     * ce délai le reproduit pour que l'attente (pictogrammes qui se relaient)
     * se voie et se teste dans l'aperçu. */
    override suspend fun sendCode(phone: String, channel: CodeChannel) {
        require(DrcPhone.parse(phone).isValid && channel in codeChannels) { "Invalid code request" }
        kotlinx.coroutines.delay(1_500)
    }

    override val communes = listOf(
        "Bandalungwa", "Barumbu", "Bumbu", "Gombe", "Kalamu", "Kasa-Vubu",
        "Kimbanseke", "Kinshasa", "Kintambo", "Kisenso", "Lemba", "Limete",
        "Lingwala", "Makala", "Maluku", "Masina", "Matete", "Mont-Ngafula",
        "N'djili", "Ngaba", "Ngaliema", "Ngiri-Ngiri", "N'sele", "Selembao",
    )

    override val signupTermsVersion: LocalDate = LocalDate.of(2026, 11, 20)

    private val isSample get() = activePhone == SAMPLE_PHONE

    override fun openAccount(phone: String): Boolean {
        if (phone != SAMPLE_PHONE && phone !in registered) return false
        activePhone = phone
        return true
    }

    override fun registerClient(
        phone: String, firstName: String, lastName: String,
        commune: String, acceptedTermsVersion: LocalDate?,
    ): Boolean {
        val first = firstName.trim()
        val last = lastName.trim()
        if (phone == SAMPLE_PHONE || phone in registered || first.isEmpty() || last.isEmpty() ||
            commune !in communes || acceptedTermsVersion != signupTermsVersion
        ) return false
        registered[phone] = Profile(first, last, phone, commune, isProvider = false, termsVersion = acceptedTermsVersion)
        activePhone = phone
        return true
    }

    override suspend fun profile(): Profile = registered[activePhone]
        ?: Profile("Grâce", "Nsimba", SAMPLE_PHONE, "Limete", isProvider = true, termsVersion = signupTermsVersion)

    override suspend fun wallet(): Wallet = if (!isSample) Wallet.EMPTY else Wallet(
        available = mapOf(Currency.CDF to Money(45_000, Currency.CDF), Currency.USD to Money(1_250, Currency.USD)),
        secured = mapOf(Currency.CDF to Money(35_000, Currency.CDF), Currency.USD to Money(500, Currency.USD)),
    )

    private fun ago(minutes: Long = 0, hours: Long = 0, days: Long = 0): Instant =
        now.minus(Duration.ofMinutes(minutes).plusHours(hours).plusDays(days))

    private val sampleMissions by lazy {
        listOf(
            Mission(51, Service.PLOMBERIE, commune = "Gombe", status = MissionStatus.IN_PROGRESS,
                payment = PaymentState.SECURED, amount = Money(500, Currency.USD), providerName = "Jean M.", at = ago(hours = 1)),
            Mission(52, Service.NETTOYAGE, commune = "Limete", status = MissionStatus.QUOTED,
                payment = PaymentState.NONE, quotesCount = 3, at = ago(hours = 3), detail = "3 pièces"),
            Mission(49, Service.COIFFURE, commune = "Limete", status = MissionStatus.AWAITING_CONFIRMATION,
                payment = PaymentState.SECURED, amount = Money(15_000, Currency.CDF), providerName = "Nadia K.", at = ago(hours = 5)),
            Mission(47, Service.CLIMATISATION, commune = "Bandal", status = MissionStatus.DISPUTED,
                payment = PaymentState.BLOCKED, amount = Money(6_000, Currency.USD), providerName = "Rodrigue T.", at = ago(days = 1)),
            Mission(53, Service.ELECTRICITE, commune = "Ngaliema", status = MissionStatus.PENDING,
                payment = PaymentState.NONE, at = ago(minutes = 30)),
            Mission(41, Service.PLOMBERIE, commune = "Gombe", status = MissionStatus.COMPLETED,
                payment = PaymentState.RELEASED, amount = Money(4_500, Currency.USD), providerName = "Jean M.", at = ago(days = 2), rated = true),
            Mission(38, Service.NETTOYAGE, commune = "Limete", status = MissionStatus.COMPLETED,
                payment = PaymentState.RELEASED, amount = Money(25_000, Currency.CDF), providerName = "Prisca K.", at = ago(days = 6), rated = true),
            Mission(33, Service.ELECTRICITE, commune = "Limete", status = MissionStatus.COMPLETED,
                payment = PaymentState.RELEASED, amount = Money(18_000, Currency.CDF), providerName = "Alain L.", at = ago(days = 12)),
        )
    }

    override suspend fun missions(): List<Mission> =
        requested[activePhone].orEmpty() + if (isSample) sampleMissions else emptyList()

    override suspend fun movements(): List<Movement> = if (!isSample) emptyList() else listOf(
        Movement(MovementKind.PAYMENT, "Plomberie · Gombe", Money(-500, Currency.USD), ago(hours = 1), PaymentState.SECURED),
        Movement(MovementKind.REFUND, "Visite annulée", Money(10_000, Currency.CDF), ago(days = 1), PaymentState.REFUNDED),
        Movement(MovementKind.RELEASE, "Plomberie · Gombe", Money(-4_500, Currency.USD), ago(days = 2), PaymentState.RELEASED),
        Movement(MovementKind.RELEASE, "Nettoyage · Limete", Money(-25_000, Currency.CDF), ago(days = 6), PaymentState.RELEASED),
    )

    /** Fictif : « Peinture » et « Déménagement » montrent seulement comment
     * un service tout juste approuvé apparaît. */
    override suspend fun serviceCatalog(): List<CatalogService> = listOf(
        CatalogService("plomberie", "Plomberie", 0xFF0350E6, service = Service.PLOMBERIE,
            lastRequested = if (isSample) ago(days = 2) else null),
        CatalogService("nettoyage", "Nettoyage", 0xFF1E8A4C, service = Service.NETTOYAGE,
            lastRequested = if (isSample) ago(days = 6) else null),
        CatalogService("electricite", "Électricité", 0xFFC98200, service = Service.ELECTRICITE, recommended = true),
        CatalogService("climatisation", "Climatisation", 0xFF0A84D6, service = Service.CLIMATISATION),
        CatalogService("informatique", "Informatique", 0xFF021937, service = Service.INFORMATIQUE),
        CatalogService("peinture", "Peinture", 0xFFB4531A,
            translations = mapOf("en" to "Painting", "ln" to "Kopakola langi"), isNew = true),
        CatalogService("coiffure", "Coiffure", 0xFFC2416B, service = Service.COIFFURE),
        CatalogService("graphisme", "Graphisme", 0xFF494C95, service = Service.GRAPHISME),
        CatalogService("jardinage", "Jardinage", 0xFF4F8A10, service = Service.JARDINAGE),
        CatalogService("demenagement", "Déménagement", 0xFF2B6CB0,
            translations = mapOf("en" to "Moving", "ln" to "Kokende kofanda esika mosusu"), isNew = true),
    )

    override suspend fun requestService(serviceId: String, commune: String, description: String) {
        val detail = description.trim()
        val item = serviceCatalog().firstOrNull { it.id == serviceId }
        require(item != null && commune in communes && detail.length in 10..500) { "Invalid service request" }
        val mission = Mission(
            id = nextRequestId++, service = item.service ?: Service.AUTRE, catalogService = item,
            commune = commune, status = MissionStatus.PENDING, payment = PaymentState.NONE,
            at = Instant.now(), detail = detail,
        )
        requested.getOrPut(activePhone) { mutableListOf() }.add(0, mission)
    }

    /** Aperçu : la demande n'est envoyée nulle part. */
    override suspend fun sendFreeRequest(title: String, text: String) = Unit
}
