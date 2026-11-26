package com.nexishub.app.data

import java.time.DayOfWeek
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

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

    /** Version en vigueur des conditions des prestataires. */
    val providerTermsVersion: LocalDate

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

    /** Les notifications de la personne, les plus récentes d'abord. */
    suspend fun notifications(): List<AppNotification>

    /** Le catalogue des services, dans l'ordre voulu par le serveur. */
    suspend fun serviceCatalog(): List<CatalogService>

    /** Crée une mission en attente de devis pour un service du catalogue. */
    suspend fun requestService(serviceId: String, commune: String, description: String)

    /** « Décrire mon besoin » : une demande libre transmise à l'équipe. */
    suspend fun sendFreeRequest(title: String, text: String)

    // --- Profil et compte ---

    /** Prénom, nom et commune. Le numéro ne change pas ici : il sert à se
     * connecter. */
    suspend fun updateProfile(firstName: String, lastName: String, commune: String): Profile

    /** Les téléphones reliés au compte, celui-ci d'abord. */
    suspend fun devices(): List<AppDevice>

    /** Coupe un autre téléphone, pour toujours : il devra se reconnecter par
     * code. Ce téléphone-ci se déconnecte par « Se déconnecter ». */
    suspend fun signOutDevice(id: Int)

    /** Les documents en vigueur pour les rôles de la personne. */
    suspend fun legalDocuments(): List<LegalDocument>
    suspend fun legalText(key: LegalDocumentKey): LegalText

    /** Demande à devenir prestataire. Le profil reste en vérification jusqu'à
     * la décision de l'équipe NexisHub. Le recto, le verso et la vidéo ne
     * servent qu'à cette vérification. */
    suspend fun applyAsProvider(
        services: List<String>, communes: List<String>, identity: IdentityCapture,
        acceptedTermsVersion: LocalDate?,
    )

    // --- Client : devis, paiement, suivi, litige ---

    suspend fun mission(id: Int): Mission

    /** Les devis reçus pour une mission, le mieux noté en premier. */
    suspend fun quotes(missionId: Int): List<Quote>
    suspend fun payAccounts(): List<PayAccount>

    /** Demande le paiement du devis choisi à l'opérateur. Le montant est celui
     * du devis enregistré sur le serveur, jamais un calcul de l'app. */
    suspend fun pay(missionId: Int, quoteId: Int, operator: MobileOperator): Mission

    /** Le client confirme que le travail est fait : le serveur verse l'argent
     * sécurisé au prestataire. */
    suspend fun confirmDone(missionId: Int): Mission

    /** Le litige de la mission, s'il y en a un. */
    suspend fun dispute(missionId: Int): Dispute?

    /** Le client signale un problème : le serveur ouvre le litige et bloque
     * l'argent sécurisé jusqu'à la décision. Refusé sans argent sécurisé. */
    suspend fun reportProblem(missionId: Int, reason: DisputeReason, text: String): Dispute

    // --- Espace prestataire ---

    suspend fun providerHome(): ProviderHome

    /** « En service » : reçoit ou non les nouvelles demandes. */
    suspend fun setInService(value: Boolean)
    suspend fun providerRequest(missionId: Int): ProviderRequest

    /** Envoie un devis. Le serveur refuse un prix nul ou négatif, ou une
     * mission qui n'est plus ouverte. */
    suspend fun sendQuote(missionId: Int, price: Money, slot: Instant)
    suspend fun providerJob(missionId: Int): ProviderJob
    suspend fun setSharing(missionId: Int, value: Boolean): ProviderJob

    /** « Je suis parti ». */
    suspend fun leaveForJob(missionId: Int): ProviderJob

    /** « Je suis arrivé » : prévient le client, ne confirme rien seul. */
    suspend fun signalArrival(missionId: Int): ProviderJob

    /** Le code de présence du client, tapé par le prestataire. Cinq essais au
     * plus ; ensuite seul l'appui du client confirme. */
    suspend fun enterPresenceCode(missionId: Int, code: String): PresenceResult

    /** « J'ai terminé » : le client a 48 h pour confirmer ou signaler. */
    suspend fun finishJob(missionId: Int): ProviderJob
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
        registered[phone] = Profile(first, last, phone, commune, termsVersion = acceptedTermsVersion)
        activePhone = phone
        return true
    }

    private var sampleProfile = Profile(
        "Grâce", "Nsimba", SAMPLE_PHONE, "Limete", providerStatus = ProviderStatus.VERIFIED, termsVersion = signupTermsVersion,
    )

    override suspend fun profile(): Profile = registered[activePhone] ?: sampleProfile

    private fun store(profile: Profile) {
        if (isSample) sampleProfile = profile else registered[activePhone] = profile
    }

    override suspend fun wallet(): Wallet = if (!isSample) Wallet.EMPTY else Wallet(
        available = mapOf(Currency.CDF to Money(45_000, Currency.CDF), Currency.USD to Money(1_250, Currency.USD)),
        secured = mapOf(Currency.CDF to Money(35_000, Currency.CDF), Currency.USD to Money(500, Currency.USD)),
    )

    private fun ago(minutes: Long = 0, hours: Long = 0, days: Long = 0): Instant =
        now.minus(Duration.ofMinutes(minutes).plusHours(hours).plusDays(days))

    private fun quote(id: Int, name: String, initials: String, color: Long,
                      rating: Double, reviews: Int, price: Money, slot: Instant) =
        Quote(id, name, initials, color, rating, reviews, price, slot)

    /** Le prochain jour de la semaine à cette heure (jamais aujourd'hui). */
    private fun next(day: DayOfWeek, hour: Int): Instant {
        val zone = ZoneId.systemDefault()
        var date = now.atZone(zone).toLocalDate().plusDays(1)
        while (date.dayOfWeek != day) date = date.plusDays(1)
        return date.atTime(hour, 0).atZone(zone).toInstant()
    }

    private val sampleMissions: MutableList<Mission> by lazy {
        mutableListOf(
            Mission(51, Service.PLOMBERIE, commune = "Gombe", status = MissionStatus.IN_PROGRESS,
                payment = PaymentState.SECURED, amount = Money(500, Currency.USD), providerName = "Jean M.", at = ago(hours = 1),
                chosen = quote(511, "Jean M.", "JM", 0xFF1E7A5C, 4.8, 92, Money(500, Currency.USD), now.plus(Duration.ofMinutes(40))),
                distanceKm = 2.4,
                steps = mapOf(TrackStep.PAID to ago(minutes = 30), TrackStep.ON_THE_WAY to ago(minutes = 19))),
            Mission(52, Service.NETTOYAGE, commune = "Limete", status = MissionStatus.QUOTED,
                payment = PaymentState.NONE, quotesCount = 3, at = ago(hours = 3), detail = "3 pièces", wanted = "Samedi matin"),
            Mission(49, Service.COIFFURE, commune = "Limete", status = MissionStatus.AWAITING_CONFIRMATION,
                payment = PaymentState.SECURED, amount = Money(15_000, Currency.CDF), providerName = "Nadia K.", at = ago(hours = 5),
                chosen = quote(491, "Nadia K.", "NK", 0xFFC2416B, 4.9, 57, Money(15_000, Currency.CDF), ago(hours = 3)),
                steps = mapOf(TrackStep.PAID to ago(hours = 5), TrackStep.ON_THE_WAY to ago(minutes = 210),
                    TrackStep.ON_SITE to ago(hours = 3), TrackStep.WORK_DONE to ago(minutes = 20))),
            Mission(47, Service.CLIMATISATION, commune = "Bandal", status = MissionStatus.DISPUTED,
                payment = PaymentState.BLOCKED, amount = Money(6_000, Currency.USD), providerName = "Rodrigue T.", at = ago(days = 1)),
            Mission(44, Service.JARDINAGE, commune = "Ngaliema", status = MissionStatus.DISPUTED,
                payment = PaymentState.BLOCKED, amount = Money(30_000, Currency.CDF), providerName = "Patrick B.", at = ago(days = 4)),
            Mission(53, Service.ELECTRICITE, commune = "Ngaliema", status = MissionStatus.PENDING,
                payment = PaymentState.NONE, at = ago(minutes = 30)),
            Mission(41, Service.PLOMBERIE, commune = "Gombe", status = MissionStatus.COMPLETED,
                payment = PaymentState.RELEASED, amount = Money(4_500, Currency.USD), providerName = "Jean M.", at = ago(days = 2),
                rated = true, providerRating = 4.8, providerReviews = 92),
            Mission(38, Service.NETTOYAGE, commune = "Limete", status = MissionStatus.COMPLETED,
                payment = PaymentState.RELEASED, amount = Money(25_000, Currency.CDF), providerName = "Prisca K.", at = ago(days = 6),
                rated = true, providerRating = 4.9, providerReviews = 212),
            Mission(33, Service.ELECTRICITE, commune = "Limete", status = MissionStatus.COMPLETED,
                payment = PaymentState.RELEASED, amount = Money(18_000, Currency.CDF), providerName = "Alain L.", at = ago(days = 12),
                providerRating = 4.6, providerReviews = 58),
        )
    }

    private val sampleMovements: MutableList<Movement> by lazy {
        mutableListOf(
            Movement(MovementKind.PAYMENT, "Plomberie · Gombe", Money(-500, Currency.USD), ago(hours = 1), PaymentState.SECURED),
            Movement(MovementKind.REFUND, "Visite annulée", Money(10_000, Currency.CDF), ago(days = 1), PaymentState.REFUNDED),
            Movement(MovementKind.RELEASE, "Plomberie · Gombe", Money(-4_500, Currency.USD), ago(days = 2), PaymentState.RELEASED),
            Movement(MovementKind.RELEASE, "Nettoyage · Limete", Money(-25_000, Currency.CDF), ago(days = 6), PaymentState.RELEASED),
        )
    }

    private val disputes: MutableMap<Int, Dispute> by lazy {
        mutableMapOf(
            47 to Dispute(47, DisputeReason.BAD_WORK, "Le climatiseur coule encore dans la chambre.", photos = 2,
                openedAt = ago(hours = 20), providerReply = "Je peux repasser demain matin.", providerRepliedAt = ago(hours = 17)),
            44 to Dispute(44, DisputeReason.NOT_FINISHED, "La haie du fond n'a pas été taillée.", photos = 1,
                openedAt = ago(days = 3), outcome = DisputeOutcome.REFUND, decidedAt = ago(hours = 2),
                clientAmount = Money(30_000, Currency.CDF), providerAmount = Money(0, Currency.CDF),
                contestUntil = ago(hours = 2).plus(Duration.ofDays(3))),
        )
    }

    private val quotesByMission: Map<Int, List<Quote>> by lazy {
        mapOf(
            52 to listOf(
                quote(521, "Prisca K.", "PK", 0xFF494C95, 4.9, 128, Money(25_000, Currency.CDF), next(DayOfWeek.SATURDAY, 9)),
                quote(522, "Joël M.", "JM", 0xFF1E7A5C, 4.7, 64, Money(22_000, Currency.CDF), next(DayOfWeek.SATURDAY, 10)),
                quote(523, "Aline L.", "AL", 0xFFC98200, 4.6, 31, Money(28_000, Currency.CDF), next(DayOfWeek.SATURDAY, 8)),
            ),
        )
    }

    override suspend fun missions(): List<Mission> =
        requested[activePhone].orEmpty() + if (isSample) sampleMissions.toList() else emptyList()

    /** Démonstration : aucune notification. La liste se remplira quand
     * l'app sera branchée au serveur. */
    override suspend fun notifications(): List<AppNotification> = emptyList()

    override suspend fun movements(): List<Movement> = if (!isSample) emptyList() else sampleMovements.toList()

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

    // --- Profil et compte ---

    override val providerTermsVersion: LocalDate = LocalDate.of(2026, 11, 20)

    override suspend fun updateProfile(firstName: String, lastName: String, commune: String): Profile {
        val first = firstName.trim()
        val last = lastName.trim()
        if (first.isEmpty() || first.length > 60 || last.isEmpty() || last.length > 60 || commune !in communes) {
            throw NexisRefusal("profile_invalid")
        }
        val updated = profile().copy(firstName = first, lastName = last, commune = commune)
        store(updated)
        return updated
    }

    private val sampleDevices: MutableList<AppDevice> by lazy {
        mutableListOf(
            AppDevice(1, "Samsung Galaxy A14", DevicePlatform.ANDROID, ago(days = 58), now, ago(days = 58), isCurrent = true),
            AppDevice(
                2, "iPhone 11", DevicePlatform.IOS, ago(hours = 20), ago(hours = 3),
                ago(hours = 20).plus(Duration.ofHours(72)), isCurrent = false,
            ),
        )
    }

    override suspend fun devices(): List<AppDevice> =
        if (isSample) sampleDevices.toList()
        else listOf(AppDevice(1, "Android", DevicePlatform.ANDROID, now, now, now, isCurrent = true))

    override suspend fun signOutDevice(id: Int) {
        val device = devices().firstOrNull { it.id == id } ?: throw NexisRefusal("device_not_found")
        if (device.isCurrent) throw NexisRefusal("use_sign_out")
        sampleDevices.removeAll { it.id == id }
    }

    private var providerTermsAcceptedAt: LocalDate? = null

    override suspend fun legalDocuments(): List<LegalDocument> {
        val me = profile()
        return buildList {
            add(LegalDocument(LegalDocumentKey.CGU, signupTermsVersion, me.termsVersion?.let { signupTermsVersion }))
            if (me.providerStatus != null) {
                add(LegalDocument(LegalDocumentKey.PROVIDER_TERMS, providerTermsVersion, providerTermsAcceptedAt ?: providerTermsVersion))
            }
        }
    }

    /** Aperçu : aucune version n'est publiée, donc pas de texte. */
    override suspend fun legalText(key: LegalDocumentKey): LegalText =
        LegalText(key, if (key == LegalDocumentKey.CGU) signupTermsVersion else providerTermsVersion, null)

    override suspend fun applyAsProvider(
        services: List<String>, communes: List<String>, identity: IdentityCapture,
        acceptedTermsVersion: LocalDate?,
    ) {
        val me = profile()
        val catalog = serviceCatalog().map { it.id }.toSet()
        val valid = me.providerStatus == null &&
            services.isNotEmpty() && services.size <= 50 && catalog.containsAll(services) &&
            communes.isNotEmpty() && communes.size <= 50 && this.communes.containsAll(communes) &&
            identity.isComplete && acceptedTermsVersion == providerTermsVersion
        if (!valid) throw NexisRefusal("provider_application_invalid")
        // Aperçu : le recto, le verso et la vidéo ne sont gardés nulle part.
        kotlinx.coroutines.delay(1_000)
        providerTermsAcceptedAt = LocalDate.now()
        store(me.copy(providerStatus = ProviderStatus.PENDING))
    }

    // --- Client : devis, paiement, suivi, litige ---

    override suspend fun mission(id: Int): Mission =
        missions().firstOrNull { it.id == id } ?: throw NexisRefusal("mission_not_found")

    override suspend fun quotes(missionId: Int): List<Quote> =
        quotesByMission[missionId].orEmpty().sortedByDescending { it.rating }

    override suspend fun payAccounts(): List<PayAccount> = listOf(
        PayAccount(MobileOperator.MPESA, "+243 81 •• •• 412"),
        PayAccount(MobileOperator.ORANGE, "+243 89 •• •• 207"),
        PayAccount(MobileOperator.AIRTEL, null),
    )

    private fun replace(mission: Mission): Mission {
        val index = sampleMissions.indexOfFirst { it.id == mission.id }
        if (index >= 0) sampleMissions[index] = mission
        return mission
    }

    override suspend fun pay(missionId: Int, quoteId: Int, operator: MobileOperator): Mission {
        val mission = mission(missionId)
        val quote = quotesByMission[missionId]?.firstOrNull { it.id == quoteId }
        val account = payAccounts().firstOrNull { it.operator == operator && it.maskedNumber != null }
        if (mission.status != MissionStatus.QUOTED || quote == null || account == null) throw NexisRefusal("payment_refused")
        // Démonstration : l'opérateur accepte après quelques secondes.
        kotlinx.coroutines.delay(3_000)
        sampleMovements.add(0, Movement(MovementKind.PAYMENT, "${mission.service.label("fr")} · ${mission.commune}",
            Money(-quote.price.minorUnits, quote.price.currency), Instant.now(), PaymentState.SECURED))
        return replace(mission.copy(
            status = MissionStatus.CONFIRMED, payment = PaymentState.SECURED, amount = quote.price,
            providerName = quote.providerName, chosen = quote, steps = mapOf(TrackStep.PAID to Instant.now()),
        ))
    }

    override suspend fun confirmDone(missionId: Int): Mission {
        val mission = mission(missionId)
        if (mission.status != MissionStatus.AWAITING_CONFIRMATION || mission.payment != PaymentState.SECURED) {
            throw NexisRefusal("mission_not_awaiting_confirmation")
        }
        return replace(mission.copy(status = MissionStatus.COMPLETED, payment = PaymentState.RELEASED,
            steps = mission.steps + (TrackStep.CONFIRMED to Instant.now())))
    }

    override suspend fun dispute(missionId: Int): Dispute? = disputes[missionId]

    override suspend fun reportProblem(missionId: Int, reason: DisputeReason, text: String): Dispute {
        val mission = mission(missionId)
        val words = text.trim()
        val open = setOf(MissionStatus.CONFIRMED, MissionStatus.IN_PROGRESS, MissionStatus.AWAITING_CONFIRMATION)
        if (mission.status !in open || mission.payment != PaymentState.SECURED || words.isEmpty() || words.length > 500) {
            throw NexisRefusal("dispute_not_allowed")
        }
        val dispute = Dispute(missionId, reason, words, photos = 0, openedAt = Instant.now())
        disputes[missionId] = dispute
        replace(mission.copy(status = MissionStatus.DISPUTED, payment = PaymentState.BLOCKED))
        return dispute
    }

    // --- Espace prestataire (fictif) ---

    private var inService = true

    /** Code de présence de la cliente dans l'aperçu. Sur le vrai serveur, il
     * n'est donné qu'au client et n'est jamais enregistré. */
    val demoPresenceCode = "2580"

    private val requests: MutableList<ProviderRequest> by lazy {
        mutableListOf(
            ProviderRequest(71, Service.NETTOYAGE, "Limete", "Samedi matin · 3 pièces",
                "Appartement de 3 pièces, cuisine et salle de bain comprises. Produits à apporter.",
                wanted = "Samedi matin", photos = 3, receivedAt = ago(minutes = 3),
                slotChoices = listOf(next(DayOfWeek.SATURDAY, 8), next(DayOfWeek.SATURDAY, 9), next(DayOfWeek.SATURDAY, 10))),
            ProviderRequest(72, Service.JARDINAGE, "Ngaliema", "Dimanche · petit jardin",
                "Petit jardin devant la maison : tondre et tailler la haie.",
                wanted = "Dimanche", photos = 1, receivedAt = ago(minutes = 12),
                slotChoices = listOf(next(DayOfWeek.SUNDAY, 9), next(DayOfWeek.SUNDAY, 14))),
        )
    }

    private val jobs: MutableList<ProviderJob> by lazy {
        mutableListOf(
            ProviderJob(61, Service.NETTOYAGE, "Limete", "Esther M.", "EM", 0xFFC2416B,
                "Limete, 7e rue · près de l'école", Money(25_000, Currency.CDF),
                steps = mapOf(ProviderStep.CLIENT_PAID to ago(minutes = 40), ProviderStep.LEFT_HOME to ago(minutes = 12)),
                sharing = true),
        )
    }

    override suspend fun providerHome(): ProviderHome {
        val securedFrancs = jobs.filter { ProviderStep.FINISHED !in it.steps && it.amount.currency == Currency.CDF }
            .sumOf { it.amount.minorUnits }
        return ProviderHome(inService, listOf("Limete", "Gombe"), Money(120_000, Currency.CDF),
            Money(securedFrancs, Currency.CDF), requests.toList(), jobs.toList())
    }

    override suspend fun setInService(value: Boolean) { inService = value }

    override suspend fun providerRequest(missionId: Int): ProviderRequest =
        requests.firstOrNull { it.missionId == missionId } ?: throw NexisRefusal("mission_not_open")

    override suspend fun sendQuote(missionId: Int, price: Money, slot: Instant) {
        val index = requests.indexOfFirst { it.missionId == missionId }
        if (index < 0) throw NexisRefusal("mission_not_open")
        if (requests[index].quoted) throw NexisRefusal("quote_already_sent")
        if (price.minorUnits <= 0) throw NexisRefusal("price_must_be_positive")
        if (!slot.isAfter(Instant.now())) throw NexisRefusal("slot_in_the_past")
        requests[index] = requests[index].copy(quoted = true)
    }

    override suspend fun providerJob(missionId: Int): ProviderJob =
        jobs.firstOrNull { it.missionId == missionId } ?: throw NexisRefusal("mission_not_found")

    private fun save(job: ProviderJob): ProviderJob {
        val index = jobs.indexOfFirst { it.missionId == job.missionId }
        if (index >= 0) jobs[index] = job
        return job
    }

    override suspend fun setSharing(missionId: Int, value: Boolean): ProviderJob =
        save(providerJob(missionId).copy(sharing = value))

    override suspend fun leaveForJob(missionId: Int): ProviderJob {
        val job = providerJob(missionId)
        if (ProviderStep.LEFT_HOME in job.steps) return job
        return save(job.copy(steps = job.steps + (ProviderStep.LEFT_HOME to Instant.now())))
    }

    override suspend fun signalArrival(missionId: Int): ProviderJob {
        val job = providerJob(missionId)
        if (ProviderStep.LEFT_HOME !in job.steps) throw NexisRefusal("not_on_the_way")
        return save(job.copy(arrivalSignaled = true))
    }

    override suspend fun enterPresenceCode(missionId: Int, code: String): PresenceResult {
        val job = providerJob(missionId)
        if (ProviderStep.ARRIVED in job.steps) return PresenceResult.CONFIRMED
        if (!job.arrivalSignaled) throw NexisRefusal("arrival_not_signaled")
        if (job.codeAttemptsLeft <= 0) return PresenceResult.LOCKED
        if (code.trim() != demoPresenceCode) {
            val left = job.codeAttemptsLeft - 1
            save(job.copy(codeAttemptsLeft = left))
            return if (left == 0) PresenceResult.LOCKED else PresenceResult.WRONG_CODE
        }
        save(job.copy(steps = job.steps + (ProviderStep.ARRIVED to Instant.now())))
        return PresenceResult.CONFIRMED
    }

    override suspend fun finishJob(missionId: Int): ProviderJob {
        val job = providerJob(missionId)
        if (ProviderStep.ARRIVED !in job.steps) throw NexisRefusal("arrival_not_confirmed")
        if (ProviderStep.FINISHED in job.steps) return job
        return save(job.copy(steps = job.steps + (ProviderStep.FINISHED to Instant.now())))
    }
}
