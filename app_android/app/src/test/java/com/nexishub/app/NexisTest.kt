package com.nexishub.app

import com.nexishub.app.data.CardCheck
import com.nexishub.app.data.CardSide
import com.nexishub.app.data.CardVerdict
import com.nexishub.app.data.Currency
import com.nexishub.app.data.DemoRepository
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.FaceSample
import com.nexishub.app.data.HeadPose
import com.nexishub.app.data.HeadPosition
import com.nexishub.app.data.HeadTurn
import com.nexishub.app.data.IdentityCapture
import com.nexishub.app.data.IdentityDocument
import com.nexishub.app.data.ImageHash
import com.nexishub.app.data.MachineZone
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.Money
import com.nexishub.app.data.NexisRefusal
import com.nexishub.app.data.Portfolio
import com.nexishub.app.data.SelfieScript
import com.nexishub.app.data.Texts
import com.nexishub.app.data.ProofReview
import com.nexishub.app.data.ProviderStatus
import com.nexishub.app.data.WorkProof
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class MoneyTest {
    @Test
    fun francsWithoutDecimals() {
        assertEquals("25 000 FC", Money(25_000, Currency.CDF).formatted("fr"))
        assertEquals("25,000 FC", Money(25_000, Currency.CDF).formatted("en"))
    }

    @Test
    fun dollarsAlwaysTwoDecimals() {
        assertEquals("12,50 USD", Money(1_250, Currency.USD).formatted("fr"))
        assertEquals("12.50 USD", Money(1_250, Currency.USD).formatted("en"))
        assertEquals("0,05 USD", Money(5, Currency.USD).formatted("ln"))
        assertEquals("−45,00 USD", Money(-4_500, Currency.USD).formatted("fr"))
    }
}

class DrcPhoneTest {
    @Test
    fun stripsCountryCodeAndTrunkZero() {
        assertEquals("812345412", DrcPhone.parse("+243 812 345 412").digits)
        assertEquals("812345412", DrcPhone.parse("00243812345412").digits)
        assertEquals("812345412", DrcPhone.parse("0812345412").digits)
    }

    @Test
    fun validityAndFormat() {
        val phone = DrcPhone.parse("812345412")
        assertTrue(phone.isValid)
        assertEquals("81 234 5412", phone.formatted)
        assertEquals("+243812345412", phone.e164)
        assertFalse(DrcPhone.parse("11").prefixKnown)
    }
}

class TextsTest {
    private val texts = Texts(File("src/main/assets/textes.json").readText())

    @Test
    fun keysUsedByTheAppExistInThreeLanguages() {
        val keys = listOf(
            "slogan", "start", "haveAccount", "navHome", "navMissions", "navWallet", "navProfile",
            "requestService", "whichService", "helloHome", "eveningHome", "heldForMissions",
            "signupTitle", "signupAcceptTerms", "serviceRequestSaved",
        )
        for (key in keys) for (language in listOf("fr", "ln", "en")) {
            assertTrue("$key manque en $language", texts.has(key, language))
        }
    }

    @Test
    fun placeholdersAndPlurals() {
        assertEquals("Bonjour, Grâce", texts.text("helloHome", "fr", mapOf("name" to "Grâce")))
        assertEquals("1 appareil connecté", texts.plural("devicesCount", "fr", 1))
        assertEquals("3 appareils connectés", texts.plural("devicesCount", "fr", 3))
    }
}

class DemoRepositoryTest {
    @Test
    fun signupRequiresCurrentTerms() {
        val repo = DemoRepository()
        assertFalse(repo.registerClient("+243991112222", "Ana", "K", "Gombe", null))
        assertTrue(repo.registerClient("+243991112222", "Ana", "K", "Gombe", repo.signupTermsVersion))
    }

    @Test
    fun serviceRequestBecomesPendingMission() = runBlocking {
        val repo = DemoRepository()
        repo.requestService("jardinage", "Limete", "Tailler la haie du jardin")
        val first = repo.missions().first()
        assertEquals(MissionStatus.PENDING, first.status)
        assertEquals("jardinage", first.catalogService?.id)
    }

    @Test
    fun demoHasNoNotificationsYet() = runBlocking {
        assertTrue(DemoRepository().notifications().isEmpty())
    }

    @Test
    fun sendCodeAcceptsValidNumberOnOfferedChannel() = runBlocking {
        DemoRepository().sendCode("+243812345678", com.nexishub.app.data.CodeChannel.WHATSAPP)
    }

    @Test(expected = IllegalArgumentException::class)
    fun sendCodeRejectsIncompleteNumber() = runBlocking {
        DemoRepository().sendCode("+24381234", com.nexishub.app.data.CodeChannel.SMS)
    }

    @Test(expected = IllegalArgumentException::class)
    fun serviceRequestRejectsShortDescription() = runBlocking {
        DemoRepository().requestService("jardinage", "Limete", "court")
    }
}

class PictogrammesTest {
    @Test
    fun everyServiceHasAMainPictogram() {
        for (service in com.nexishub.app.data.Service.entries) {
            assertTrue("$service sans pictogramme", com.nexishub.app.ui.Pictogrammes.icons(service).isNotEmpty())
        }
    }

    @Test
    fun threeQuickTapsInTheVoidOpenTheRequestButton() {
        val detector = com.nexishub.app.screens.ConfusedTapDetector()
        assertFalse(detector.onTap(0))
        assertFalse(detector.onTap(1_000))
        assertTrue(detector.onTap(2_000))
        // La série repart de zéro après avoir ouvert le bouton.
        assertFalse(detector.onTap(2_500))
    }

    @Test
    fun slowTapsInTheVoidAreNotConfusion() {
        val detector = com.nexishub.app.screens.ConfusedTapDetector()
        assertFalse(detector.onTap(0))
        assertFalse(detector.onTap(3_000))
        assertFalse(detector.onTap(6_000))
        assertFalse(detector.onTap(9_500))
    }

    @Test
    fun loaderShowsTenDistinctServiceIcons() {
        assertEquals(10, com.nexishub.app.ui.LOADER_ICONS.distinct().size)
    }

    @Test
    fun otherServiceStaysStill() {
        assertEquals(1, com.nexishub.app.ui.Pictogrammes.icons(com.nexishub.app.data.Service.AUTRE).size)
    }
}

class FlowsTest {
    private fun refusal(block: suspend () -> Unit): String? = runBlocking {
        try { block(); null } catch (e: com.nexishub.app.data.NexisRefusal) { e.code }
    }

    @Test
    fun quotesComeBestRatedFirst() = runBlocking {
        val quotes = DemoRepository().quotes(52)
        assertEquals(listOf("Prisca K.", "Joël M.", "Aline L."), quotes.map { it.providerName })
    }

    @Test
    fun payingSecuresTheQuotedAmount() = runBlocking {
        val repo = DemoRepository()
        val paid = repo.pay(52, 522, com.nexishub.app.data.MobileOperator.MPESA)
        assertEquals(MissionStatus.CONFIRMED, paid.status)
        assertEquals(com.nexishub.app.data.PaymentState.SECURED, paid.payment)
        assertEquals(Money(22_000, Currency.CDF), paid.amount)
        assertEquals("Joël", paid.providerFirstName)
        assertEquals(MissionStatus.CONFIRMED, repo.mission(52).status)
    }

    @Test
    fun cannotPayWithoutARegisteredNumber() {
        val repo = DemoRepository()
        assertEquals("payment_refused", refusal { repo.pay(52, 521, com.nexishub.app.data.MobileOperator.AIRTEL) })
    }

    @Test
    fun confirmingReleasesTheMoney() = runBlocking {
        val repo = DemoRepository()
        val done = repo.confirmDone(49)
        assertEquals(MissionStatus.COMPLETED, done.status)
        assertEquals(com.nexishub.app.data.PaymentState.RELEASED, done.payment)
        assertEquals("mission_not_awaiting_confirmation", refusal { repo.confirmDone(51) })
    }

    @Test
    fun reportingBlocksSecuredMoneyOnly() = runBlocking {
        val repo = DemoRepository()
        val reason = com.nexishub.app.data.DisputeReason.NO_SHOW
        assertEquals("dispute_not_allowed", refusal { repo.reportProblem(52, reason, "Personne n'est venu.") })
        assertEquals("dispute_not_allowed", refusal { repo.reportProblem(51, reason, "   ") })
        repo.reportProblem(51, reason, "Personne n'est venu.")
        assertEquals(com.nexishub.app.data.PaymentState.BLOCKED, repo.mission(51).payment)
        assertTrue(repo.dispute(51) != null)
    }

    @Test
    fun decidedDisputeShowsServerAmounts() = runBlocking {
        val dispute = DemoRepository().dispute(44)!!
        assertTrue(dispute.decided)
        assertEquals(Money(30_000, Currency.CDF), dispute.clientAmount)
    }

    @Test
    fun quoteMustBePositiveAndSentOnce() = runBlocking {
        val repo = DemoRepository()
        val slot = repo.providerRequest(71).slotChoices.first()
        assertEquals("price_must_be_positive", refusal { repo.sendQuote(71, Money(0, Currency.CDF), slot) })
        repo.sendQuote(71, Money(25_000, Currency.CDF), slot)
        assertTrue(repo.providerRequest(71).quoted)
        assertEquals("quote_already_sent", refusal { repo.sendQuote(71, Money(25_000, Currency.CDF), slot) })
    }

    @Test
    fun presenceCodeLocksAfterFiveWrongTries() = runBlocking {
        val repo = DemoRepository()
        assertEquals("arrival_not_signaled", refusal { repo.enterPresenceCode(61, "0000") })
        repo.signalArrival(61)
        repeat(4) { assertEquals(com.nexishub.app.data.PresenceResult.WRONG_CODE, repo.enterPresenceCode(61, "0000")) }
        assertEquals(com.nexishub.app.data.PresenceResult.LOCKED, repo.enterPresenceCode(61, "0000"))
        assertEquals(com.nexishub.app.data.PresenceResult.LOCKED, repo.enterPresenceCode(61, repo.demoPresenceCode))
    }

    @Test
    fun rightCodeConfirmsArrivalThenJobCanFinish() = runBlocking {
        val repo = DemoRepository()
        assertEquals("arrival_not_confirmed", refusal { repo.finishJob(61) })
        repo.signalArrival(61)
        assertEquals(com.nexishub.app.data.PresenceResult.CONFIRMED, repo.enterPresenceCode(61, " 2580 "))
        val job = repo.finishJob(61)
        assertTrue(com.nexishub.app.data.ProviderStep.FINISHED in job.steps)
        assertEquals(Money(0, Currency.CDF), repo.providerHome().secured)
    }
}

class PriceInputTest {
    private val parse = com.nexishub.app.screens.PriceInput::parse
    private val typed = com.nexishub.app.screens.PriceInput::typed

    @Test
    fun francsAreWholeAndPositive() {
        assertEquals(Money(25_000, Currency.CDF), parse("25 000", Currency.CDF))
        assertEquals(null, parse("0", Currency.CDF))
        assertEquals(null, parse("12,5", Currency.CDF))
        assertEquals(null, parse("", Currency.CDF))
    }

    @Test
    fun dollarsKeepAtMostTwoDecimals() {
        assertEquals(Money(1_250, Currency.USD), parse("12,5", Currency.USD))
        assertEquals(Money(4_500, Currency.USD), parse("45", Currency.USD))
        assertEquals(Money(5, Currency.USD), parse("0.05", Currency.USD))
        assertEquals(null, parse("1.234", Currency.USD))
        assertEquals(null, parse("0,00", Currency.USD))
        assertEquals(null, parse("1.2.3", Currency.USD))
    }

    @Test
    fun francsAreGroupedWhileTyping() {
        assertEquals("25 000", typed("25000", Currency.CDF))
        assertEquals("1 234 567", typed("1 2345 67", Currency.CDF))
        assertEquals("12,5", typed("12a,5", Currency.USD))
    }
}

class DatesTest {
    private val zone = java.time.ZoneId.of("Africa/Kinshasa")
    private fun at(hour: Int, minute: Int) =
        java.time.LocalDate.of(2026, 11, 28).atTime(hour, minute).atZone(zone).toInstant()

    @Test
    fun clockReadsLikeKinshasa() {
        assertEquals("9 h", com.nexishub.app.ui.clockText(at(9, 0), "fr", zone))
        assertEquals("20 h 41", com.nexishub.app.ui.clockText(at(20, 41), "fr", zone))
        assertEquals("8:41 pm", com.nexishub.app.ui.clockText(at(20, 41), "en", zone))
    }

    @Test
    fun daysLeftCountsWholeDays() {
        val now = java.time.Instant.parse("2026-11-25T10:00:00Z")
        assertEquals(3, com.nexishub.app.ui.daysLeft(now.plusSeconds(70 * 3600L), now))
        assertEquals(0, com.nexishub.app.ui.daysLeft(now.minusSeconds(60), now))
    }
}

class AccountTest {
    private fun refusal(block: suspend () -> Unit): String? = runBlocking {
        try { block(); null } catch (e: com.nexishub.app.data.NexisRefusal) { e.code }
    }

    @Test
    fun profileUpdateKeepsPhoneAndChecksCommune() = runBlocking {
        val repo = DemoRepository()
        val before = repo.profile()
        val updated = repo.updateProfile(" Grâce ", "Mbuyi", "Gombe")
        assertEquals("Grâce", updated.firstName)
        assertEquals("Gombe", updated.commune)
        assertEquals(before.phone, updated.phone)
        assertEquals("profile_invalid", refusal { repo.updateProfile("Grâce", "Mbuyi", "Paris") })
    }

    @Test
    fun onlyOtherPhonesCanBeSignedOut() = runBlocking {
        val repo = DemoRepository()
        val devices = repo.devices()
        val current = devices.first { it.isCurrent }
        val other = devices.first { !it.isCurrent }
        assertTrue(other.moneyHoursLeft() > 0)
        assertEquals("use_sign_out", refusal { repo.signOutDevice(current.id) })
        repo.signOutDevice(other.id)
        assertEquals(listOf(current.id), repo.devices().map { it.id })
    }

    @Test
    fun providerApplicationNeedsEveryStep() = runBlocking {
        val repo = DemoRepository()
        assertTrue(repo.registerClient("+243810000001", "Esther", "M", "Limete", repo.signupTermsVersion))
        val identity = IdentityCapture(
            IdentityDocument.VOTER_CARD, byteArrayOf(1), byteArrayOf(2), byteArrayOf(3), 7, listOf(HeadTurn.RIGHT, HeadTurn.LEFT),
        )
        fun send(sent: IdentityCapture, terms: java.time.LocalDate?) = refusal {
            repo.applyAsProvider(listOf("nettoyage"), listOf("Limete"), sent, Portfolio(), terms)
        }
        assertEquals("provider_application_invalid", send(identity, null))
        val noVerso = IdentityCapture(identity.document, identity.recto, ByteArray(0), identity.video, 7, identity.headTurns)
        assertEquals("provider_application_invalid", send(noVerso, repo.providerTermsVersion))
        val noVideo = IdentityCapture(identity.document, identity.recto, identity.verso, ByteArray(0), 7, identity.headTurns)
        assertEquals("provider_application_invalid", send(noVideo, repo.providerTermsVersion))
        val oneTurn = IdentityCapture(identity.document, identity.recto, identity.verso, identity.video, 7, listOf(HeadTurn.LEFT, HeadTurn.LEFT))
        // Passeport : une seule page, jamais de verso.
        val passportWithVerso = IdentityCapture(IdentityDocument.PASSPORT, identity.recto, identity.verso, identity.video, 7, identity.headTurns)
        assertEquals("provider_application_invalid", send(passportWithVerso, repo.providerTermsVersion))
        assertTrue(IdentityCapture(IdentityDocument.PASSPORT, identity.recto, null, identity.video, 7, identity.headTurns).isComplete)
        assertFalse(IdentityCapture(IdentityDocument.DRIVING_LICENCE, identity.recto, null, identity.video, 7, identity.headTurns).isComplete)
        assertEquals("provider_application_invalid", send(oneTurn, repo.providerTermsVersion))
        assertEquals(null, send(identity, repo.providerTermsVersion))
        val profile = repo.profile()
        assertEquals(com.nexishub.app.data.ProviderStatus.PENDING, profile.providerStatus)
        assertTrue(!profile.isProvider)
        assertEquals(
            listOf(com.nexishub.app.data.LegalDocumentKey.CGU, com.nexishub.app.data.LegalDocumentKey.PROVIDER_TERMS),
            repo.legalDocuments().map { it.key },
        )
    }

    @Test
    fun captureCodesMatchTheScript() {
        assertEquals(com.nexishub.app.Capture.BECOME_IDENTITY, com.nexishub.app.Capture.from("become-identity"))
        assertEquals(com.nexishub.app.Capture.BECOME_WRONG_SIDE, com.nexishub.app.Capture.from("become-wrong-side"))
        assertEquals(com.nexishub.app.Capture.BECOME_VERSO, com.nexishub.app.Capture.from("become-verso"))
        assertEquals(com.nexishub.app.Capture.BECOME_SELFIE, com.nexishub.app.Capture.from("become-selfie"))
        assertEquals(com.nexishub.app.Capture.BECOME_REVIEW, com.nexishub.app.Capture.from("become-review"))
        assertEquals(com.nexishub.app.Capture.BECOME_PASSPORT, com.nexishub.app.Capture.from("become-passport"))
        assertEquals(com.nexishub.app.Capture.BECOME_WRONG_PAGE, com.nexishub.app.Capture.from("become-wrong-page"))
        assertEquals(com.nexishub.app.Capture.BECOME_PORTFOLIO, com.nexishub.app.Capture.from("become-portfolio"))
        assertEquals(com.nexishub.app.Capture.PORTFOLIO, com.nexishub.app.Capture.from("portfolio"))
        assertEquals(com.nexishub.app.Capture.PORTFOLIO_LOCKED, com.nexishub.app.Capture.from("portfolio-locked"))
        assertEquals(com.nexishub.app.Capture.SHOWCASE, com.nexishub.app.Capture.from("showcase"))
        assertEquals(com.nexishub.app.Capture.TRACKING, com.nexishub.app.Capture.from("tracking"))
    }
}

class IdentityGuideTest {
    @Test
    fun rectoNeedsAFace() {
        assertEquals(CardVerdict.ACCEPTED, CardCheck.verdict(CardSide.RECTO, true, listOf(1L), null))
        assertEquals(CardVerdict.SHOW_RECTO_FIRST, CardCheck.verdict(CardSide.RECTO, false, listOf(1L), null))
    }

    @Test
    fun versoMustDifferFromRecto() {
        val recto = 0x0F0F_0F0F_0F0F_0F0FL
        val same = recto xor 0b111L
        val other = recto.inv()
        assertEquals(CardVerdict.STILL_RECTO, CardCheck.verdict(CardSide.VERSO, false, listOf(same), recto))
        assertEquals(CardVerdict.ACCEPTED, CardCheck.verdict(CardSide.VERSO, false, listOf(other), recto))
        // Carte à l'envers : l'une des deux lectures ressemble au recto.
        assertEquals(CardVerdict.STILL_RECTO, CardCheck.verdict(CardSide.VERSO, false, listOf(other, same), recto))
        // Avec un visage visible, un écart moyen suffit à dire « encore le recto ».
        val medium = recto xor 0xFFFFL
        assertEquals(CardVerdict.STILL_RECTO, CardCheck.verdict(CardSide.VERSO, true, listOf(medium), recto))
        assertEquals(CardVerdict.ACCEPTED, CardCheck.verdict(CardSide.VERSO, false, listOf(medium), recto))
    }

    @Test
    fun passportNeedsFaceAndMachineZone() {
        assertEquals(listOf(CardSide.PASSPORT_PAGE), IdentityDocument.PASSPORT.sides)
        assertEquals(listOf(CardSide.RECTO, CardSide.VERSO), IdentityDocument.DRIVING_LICENCE.sides)
        assertEquals(CardVerdict.ACCEPTED, CardCheck.verdict(CardSide.PASSPORT_PAGE, true, emptyList(), null, machineZone = true))
        assertEquals(CardVerdict.SHOW_PHOTO_PAGE, CardCheck.verdict(CardSide.PASSPORT_PAGE, true, emptyList(), null, machineZone = false))
        assertEquals(CardVerdict.SHOW_PHOTO_PAGE, CardCheck.verdict(CardSide.PASSPORT_PAGE, false, emptyList(), null, machineZone = true))
    }

    @Test
    fun machineZoneIsRecognised() {
        val zone = listOf(
            "REPUBLIQUE DEMOCRATIQUE DU CONGO",
            "P<CODMUKENDI<<GRACE<<<<<<<<<<<<<<<<<<<<<<<<",
            "OP12345674COD9001014F3001019<<<<<<<<<<<<<<06",
        )
        assertTrue(MachineZone.found(zone))
        // Lu avec des espaces et des minuscules.
        assertTrue(MachineZone.found(listOf("p<cod mukendi<<grace<<<<<<<<<<<<<<<<<<<<", "OP1234567 4COD9001014F3001019<<<<<<<<<06")))
        // Une seule ligne, ou une page de visas : pas la page photo.
        assertFalse(MachineZone.found(listOf("P<CODMUKENDI<<GRACE<<<<<<<<<<<<<<<<<<<<<<<<")))
        assertFalse(MachineZone.found(listOf("VISAS", "Page 12", "ENTREE ARRIVAL 12/05/2025 KINSHASA NDJILI")))
    }

    @Test
    fun differenceHash() {
        val rising = IntArray(72) { (it % 9) * 20 }
        assertEquals(-1L, ImageHash.dHash(rising))
        assertEquals(0L, ImageHash.dHash(ImageHash.halfTurn(rising)))
        assertEquals(64, ImageHash.distance(0L, -1L))
    }

    @Test
    fun headPoseUsesTheNoseForTheDirection() {
        // Nez vers la droite de l'image (non inversée) : la personne tourne vers sa gauche.
        assertEquals(HeadPosition.Turned(HeadTurn.LEFT), HeadPose.position(FaceSample(1, turnDegrees = 28.0, noseOffset = 0.12)))
        assertEquals(HeadPosition.Turned(HeadTurn.RIGHT), HeadPose.position(FaceSample(1, turnDegrees = 28.0, noseOffset = -0.12)))
        assertEquals(HeadPosition.Ahead, HeadPose.position(FaceSample(1, turnDegrees = 4.0, noseOffset = 0.01)))
        assertEquals(HeadPosition.Between, HeadPose.position(FaceSample(1, turnDegrees = 15.0, noseOffset = 0.05)))
        assertEquals(HeadPosition.Turned(HeadTurn.RIGHT), HeadPose.position(FaceSample(1, noseOffset = -0.2)))
    }

    @Test
    fun selfieStepsComeInOrder() {
        val script = SelfieScript(listOf(HeadTurn.RIGHT, HeadTurn.LEFT), holdNeeded = 3)
        var time = 0.0
        fun run(sample: FaceSample, frames: Int) = (0 until frames).map { time += 0.1; script.feed(sample, time) }
        val framed = FaceSample(1, turnDegrees = 2.0)
        val left = FaceSample(1, turnDegrees = 30.0, noseOffset = 0.15)
        val right = FaceSample(1, turnDegrees = 30.0, noseOffset = -0.15)
        assertEquals(1, script.number)
        assertEquals(SelfieScript.Event.START_RECORDING, run(framed, 3).last())
        assertEquals(SelfieScript.Step.Turn(HeadTurn.RIGHT), script.step)
        // Tourner du mauvais côté ne fait pas avancer.
        assertFalse(SelfieScript.Event.ADVANCED in run(left, 5))
        assertEquals(SelfieScript.Event.ADVANCED, run(right, 3).last())
        assertEquals(SelfieScript.Event.ADVANCED, run(left, 3).last())
        assertEquals(SelfieScript.Step.LookAhead, script.step)
        assertEquals(4, script.number)
        assertEquals(SelfieScript.Event.FINISHED, run(framed, 3).last())
        assertEquals(SelfieScript.Step.Done, script.step)
        assertTrue(script.seconds > 0)
    }

    @Test
    fun selfieRestartsWhenTooSlowOrFaceLost() {
        val script = SelfieScript(listOf(HeadTurn.LEFT, HeadTurn.RIGHT), holdNeeded = 1, timeLimit = 5.0, lostLimit = 2)
        val framed = FaceSample(1, turnDegrees = 0.0)
        assertEquals(SelfieScript.Event.START_RECORDING, script.feed(framed, 0.0))
        assertEquals(SelfieScript.Event.RESTART, script.feed(framed, 6.0))
        assertEquals(SelfieScript.Step.FaceIn, script.step)
        assertEquals(SelfieScript.Event.START_RECORDING, script.feed(framed, 7.0))
        assertEquals(SelfieScript.Event.NONE, script.feed(FaceSample(0), 7.1))
        assertEquals(SelfieScript.Event.NONE, script.feed(FaceSample(0), 7.2))
        assertEquals(SelfieScript.Event.RESTART, script.feed(FaceSample(0), 7.3))
        // Deux visages : rien n'avance, et l'écran le dit.
        script.feed(FaceSample(2), 8.0)
        assertTrue(script.severalFaces)
        assertEquals(SelfieScript.Step.FaceIn, script.step)
    }

    @Test
    fun faceMustBeCenteredToStart() {
        assertTrue(HeadPose.isFramed(FaceSample(1, turnDegrees = 3.0)))
        assertFalse(HeadPose.isFramed(FaceSample(1, centerX = 0.8, turnDegrees = 3.0)))
        assertFalse(HeadPose.isFramed(FaceSample(1, width = 0.1, turnDegrees = 3.0)))
        assertFalse(HeadPose.isFramed(FaceSample(2, turnDegrees = 3.0)))
    }
}

class PortfolioTest {
    private fun work(service: String, photos: Int = 1, note: String = "") = WorkProof(service, List(photos) { byteArrayOf(1) }, note)

    @Test
    fun portfolioRules() {
        val services = setOf("plomberie", "electricite")
        assertTrue(Portfolio().isValid(services))
        assertTrue(Portfolio(listOf(work("plomberie", photos = 5)), listOf(byteArrayOf(2))).isValid(services))
        // Plus de 5 photos, un service non choisi, deux fois le même service.
        assertFalse(Portfolio(listOf(work("plomberie", photos = 6))).isValid(services))
        assertFalse(Portfolio(listOf(work("coiffure"))).isValid(services))
        assertFalse(Portfolio(listOf(work("plomberie"), work("plomberie"))).isValid(services))
        // Une phrase trop longue, 4 attestations, un fichier vide.
        assertFalse(Portfolio(listOf(work("plomberie", note = "a".repeat(201)))).isValid(services))
        assertFalse(Portfolio(certificates = List(4) { byteArrayOf(2) }).isValid(services))
        assertFalse(Portfolio(certificates = listOf(ByteArray(0))).isValid(services))
    }

    @Test
    fun cleanedDropsServicesWithoutPhotos() {
        val portfolio = Portfolio(listOf(work("plomberie", photos = 0, note = "Fuite"), work("electricite", note = "  Tableau  ")))
        assertEquals(listOf("electricite"), portfolio.cleaned.works.map { it.serviceId })
        assertEquals("Tableau", portfolio.cleaned.works.first().note)
        assertTrue(Portfolio(listOf(work("plomberie", photos = 0))).cleaned.isEmpty)
    }

    @Test
    fun portfolioIsSentWithTheApplicationAndLater() = runBlocking {
        val repo = DemoRepository()
        assertTrue(repo.registerClient("+243810000002", "Jean", "K", "Limete", repo.signupTermsVersion))
        // Un client seulement ne peut pas envoyer de preuves.
        assertEquals("portfolio_invalid", runCatching { repo.sendPortfolio(Portfolio(listOf(work("plomberie")))) }
            .exceptionOrNull()?.let { (it as NexisRefusal).code })
        val identity = IdentityCapture(IdentityDocument.PASSPORT, byteArrayOf(1), null, byteArrayOf(3), 7, listOf(HeadTurn.LEFT, HeadTurn.RIGHT))
        repo.applyAsProvider(listOf("plomberie"), listOf("Limete"), identity, Portfolio(listOf(work("plomberie", photos = 2))), repo.providerTermsVersion)
        assertEquals(2, repo.portfolio().works.first().photos.size)
        assertEquals(listOf("plomberie"), repo.providerServices())
        // L'équipe demande des preuves ; l'envoi y répond.
        repo.demoAskPortfolio(listOf("plomberie"))
        assertEquals(listOf("plomberie"), repo.portfolioRequest()?.services)
        repo.sendPortfolio(Portfolio(listOf(work("plomberie", photos = 3)), listOf(byteArrayOf(4))))
        assertEquals(null, repo.portfolioRequest())
        assertEquals(1, repo.portfolio().certificates.size)
        // Un service qui n'est pas dans la demande est refusé.
        assertEquals("portfolio_invalid", runCatching { repo.sendPortfolio(Portfolio(listOf(work("coiffure")))) }
            .exceptionOrNull()?.let { (it as NexisRefusal).code })
        // Pendant la vérification, sans demande de l'équipe : figé.
        assertEquals("portfolio_locked", runCatching { repo.sendPortfolio(Portfolio(listOf(work("plomberie")))) }
            .exceptionOrNull()?.let { (it as NexisRefusal).code })
        // Après l'accord de l'équipe : de nouveau modifiable.
        repo.demoVerifyProvider()
        repo.sendPortfolio(Portfolio(listOf(work("plomberie"))))
        assertEquals(1, repo.portfolio().works.first().photos.size)
    }

    @Test
    fun worksAreFrozenWhileTheTeamChecksTheProvider() {
        assertFalse(Portfolio.isEditable(null, false))
        assertFalse(Portfolio.isEditable(ProviderStatus.PENDING, false))
        assertTrue(Portfolio.isEditable(ProviderStatus.PENDING, true))
        assertTrue(Portfolio.isEditable(ProviderStatus.VERIFIED, false))
    }
    @Test
    fun clientsSeeOnlyApprovedWorksAndNeverCertificates() {
        val portfolio = Portfolio(
            listOf(work("plomberie", photos = 2, note = "Cuisine").withReview(ProofReview.APPROVED),
                work("electricite").withReview(ProofReview.REJECTED), work("coiffure")),
            listOf(byteArrayOf(9)), certificatesVerified = true,
        )
        val showcase = portfolio.showcase
        assertEquals(listOf("plomberie"), showcase?.works?.map { it.serviceId })
        assertEquals("Cuisine", showcase?.works?.first()?.note)
        assertEquals(true, showcase?.certificateVerified)
        // Rien d'approuvé : rien chez le client, même avec un diplôme vérifié.
        assertNull(Portfolio(listOf(work("plomberie")), listOf(byteArrayOf(9)), certificatesVerified = true).showcase)
    }

    @Test
    fun changedWorksGoBackToTheTeam() {
        val previous = Portfolio(
            listOf(work("plomberie", photos = 2, note = "Cuisine").withReview(ProofReview.APPROVED),
                work("electricite").withReview(ProofReview.REJECTED)),
            listOf(byteArrayOf(9)), certificatesVerified = true,
        )
        // Rien de changé : les décisions restent.
        val same = Portfolio(listOf(work("plomberie", photos = 2, note = "Cuisine"), work("electricite")), listOf(byteArrayOf(9)))
            .resubmitted(previous)
        assertEquals(listOf(ProofReview.APPROVED, ProofReview.REJECTED), same.works.map { it.review })
        assertTrue(same.certificatesVerified)
        // Une photo ajoutée, une phrase changée, un diplôme changé : tout repasse par l'équipe.
        val changed = Portfolio(listOf(work("plomberie", photos = 3, note = "Cuisine"), work("electricite", note = "Tableau")), listOf(byteArrayOf(8)))
            .resubmitted(previous)
        assertEquals(listOf(ProofReview.PENDING, ProofReview.PENDING), changed.works.map { it.review })
        assertFalse(changed.certificatesVerified)
        assertNull(changed.showcase)
    }

    @Test
    fun providerSeesTheTeamDecision() = runBlocking {
        val repo = DemoRepository()
        assertTrue(repo.registerClient("+243810000003", "Jean", "K", "Limete", repo.signupTermsVersion))
        val identity = IdentityCapture(IdentityDocument.PASSPORT, byteArrayOf(1), null, byteArrayOf(3), 7, listOf(HeadTurn.LEFT, HeadTurn.RIGHT))
        // L'app ne peut pas se donner l'accord de l'équipe.
        val forged = Portfolio(listOf(work("plomberie", photos = 2).withReview(ProofReview.APPROVED)), certificatesVerified = true)
        repo.applyAsProvider(listOf("plomberie"), listOf("Limete"), identity, forged, repo.providerTermsVersion)
        assertEquals(ProofReview.PENDING, repo.portfolio().works.first().review)
        assertFalse(repo.portfolio().certificatesVerified)
        repo.demoReview("plomberie", ProofReview.APPROVED)
        assertEquals(ProofReview.APPROVED, repo.portfolio().works.first().review)
        // Renvoyé sans changement, après l'accord du prestataire : toujours approuvé.
        repo.demoVerifyProvider()
        repo.sendPortfolio(Portfolio(listOf(work("plomberie", photos = 2))))
        assertEquals(ProofReview.APPROVED, repo.portfolio().works.first().review)
    }

    @Test
    fun quoteShowsOnlyTheApprovedShowcase() = runBlocking {
        val repo = DemoRepository()
        val prisca = repo.providerShowcase(521)
        assertEquals(listOf("nettoyage"), prisca?.works?.map { it.serviceId })
        assertEquals(true, prisca?.certificateVerified)
        // Joël attend encore l'équipe ; Aline n'a rien envoyé.
        assertNull(repo.providerShowcase(522))
        assertNull(repo.providerShowcase(523))
    }
}
