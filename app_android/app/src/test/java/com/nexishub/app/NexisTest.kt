package com.nexishub.app

import com.nexishub.app.data.Currency
import com.nexishub.app.data.DemoRepository
import com.nexishub.app.data.DrcPhone
import com.nexishub.app.data.MissionStatus
import com.nexishub.app.data.Money
import com.nexishub.app.data.Texts
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
        val photo = byteArrayOf(1, 2, 3)
        assertEquals("provider_application_invalid", refusal {
            repo.applyAsProvider(listOf("nettoyage"), listOf("Limete"), photo, photo, null)
        })
        assertEquals("provider_application_invalid", refusal {
            repo.applyAsProvider(listOf("nettoyage"), listOf("Limete"), ByteArray(0), photo, repo.providerTermsVersion)
        })
        repo.applyAsProvider(listOf("nettoyage"), listOf("Limete"), photo, photo, repo.providerTermsVersion)
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
        assertEquals(com.nexishub.app.Capture.TRACKING, com.nexishub.app.Capture.from("tracking"))
    }
}
