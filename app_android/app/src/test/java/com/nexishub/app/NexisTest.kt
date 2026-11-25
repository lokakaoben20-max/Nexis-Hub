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
    fun loaderShowsTenDistinctServiceIcons() {
        assertEquals(10, com.nexishub.app.ui.LOADER_ICONS.distinct().size)
    }

    @Test
    fun otherServiceStaysStill() {
        assertEquals(1, com.nexishub.app.ui.Pictogrammes.icons(com.nexishub.app.data.Service.AUTRE).size)
    }
}
