package com.nexishub.app

import androidx.fragment.app.FragmentActivity
import com.nexishub.app.data.AppSecurity
import com.nexishub.app.data.BiometricResult
import com.nexishub.app.data.Biometrics
import com.nexishub.app.data.CodeRules
import com.nexishub.app.data.DemoRepository
import com.nexishub.app.data.MemoryCodeVault
import com.nexishub.app.data.Texts
import java.io.File
import java.time.Instant
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pas d'empreinte dans les tests : le téléphone répondrait « non ». */
private class NoBiometrics : Biometrics {
    var forgotten = 0
    override val available = false
    override fun prepare() = Unit
    override suspend fun authenticate(activity: FragmentActivity, title: String, negative: String) = BiometricResult.FAILED
    override fun forget() {
        forgotten++
    }
}

class CodeRulesTest {
    @Test
    fun weakCodesAreRefused() {
        for (code in listOf("000000", "111111", "121212", "123456", "654321", "123123", "12345", "12a456", "1234567")) {
            assertTrue(code, CodeRules.isWeak(code))
        }
        for (code in listOf("482916", "190573", "112233", "250489")) {
            assertFalse(code, CodeRules.isWeak(code))
        }
    }

    @Test
    fun locksAfterOneMinuteAway() {
        val left = Instant.ofEpochSecond(1_000)
        assertFalse(CodeRules.shouldLock(null, left))
        assertFalse(CodeRules.shouldLock(left, left.plusSeconds(59)))
        assertTrue(CodeRules.shouldLock(left, left.plusSeconds(60)))
    }
}

class AppSecurityTest {
    @Test
    fun codeIsStoredOnlyAsSaltedDigest() {
        val vault = MemoryCodeVault()
        val security = AppSecurity(vault, NoBiometrics())
        security.setCode("482916")
        val record = vault.load()!!
        assertEquals(16, record.salt.size)
        assertFalse(String(record.digest, Charsets.ISO_8859_1).contains("482916"))
        assertEquals(AppSecurity.Check.Ok, security.check("482916"))
    }

    @Test
    fun fiveWrongCodesBlockEvenAfterRestart() {
        val vault = MemoryCodeVault()
        val security = AppSecurity(vault, NoBiometrics())
        security.setCode("482916")
        assertEquals(AppSecurity.Check.Wrong(4), security.check("111222"))
        assertEquals(AppSecurity.Check.Ok, security.check("482916"))
        for (left in listOf(4, 3, 2, 1)) assertEquals(AppSecurity.Check.Wrong(left), security.check("111222"))
        // Une nouvelle ouverture de l'app relit le compteur.
        val reopened = AppSecurity(vault, NoBiometrics())
        assertEquals(AppSecurity.Check.Blocked, reopened.check("111222"))
        assertEquals(AppSecurity.Check.Blocked, reopened.check("482916"))
    }

    @Test
    fun eraseForgetsTheFingerprintKey() {
        val biometrics = NoBiometrics()
        val security = AppSecurity(MemoryCodeVault(), biometrics)
        security.setCode("482916")
        security.erase()
        assertFalse(security.hasCode)
        assertTrue(biometrics.forgotten > 0)
    }
}

class MoneyGateTest {
    private fun app(): AppModel {
        val texts = Texts(File("src/main/assets/textes.json").readText())
        return AppModel(DemoRepository(), texts, AppSecurity(MemoryCodeVault(), NoBiometrics()), "fr")
    }

    @Test
    fun signOutErasesCodeAndCancelsPendingPayment() = runBlocking {
        val app = app()
        app.signIn()
        assertTrue(app.needsProtection)
        app.security.setCode("482916")
        assertFalse(app.needsProtection)
        val confirmed = async { app.confirmMoneyOut("Payer 25 000 FC à Prisca") }
        while (app.gate == null) yield()
        app.signOut()
        assertFalse(confirmed.await())
        assertFalse(app.security.hasCode)
        assertNull(app.gate)
    }

    @Test
    fun moneyOutWaitsForConfirmation() = runBlocking {
        val app = app()
        app.signIn()
        app.security.setCode("482916")
        val confirmed = async { app.confirmMoneyOut("Verser l'argent à Nadia") }
        while (app.gate == null) yield()
        assertNotNull(app.gate)
        app.finishGate(true)
        assertTrue(confirmed.await())
    }

    @Test
    fun noMoneyOutWithoutCode() = runBlocking {
        val app = app()
        app.signIn()
        assertFalse(app.confirmMoneyOut("Payer"))
    }

    @Test
    fun locksOnlyAfterAMinuteInBackground() {
        val app = app()
        app.signIn()
        app.security.setCode("482916")
        val start = Instant.ofEpochSecond(5_000)
        app.left(start)
        assertTrue(app.covered)
        app.cameBack(start.plusSeconds(20))
        assertFalse(app.covered)
        assertFalse(app.locked)
        app.left(start)
        app.cameBack(start.plusSeconds(90))
        assertTrue(app.locked)
    }

    @Test
    fun securityCapturesExist() {
        assertEquals(Capture.PROTECT_BIO, Capture.from("protect-bio"))
        assertEquals(Capture.SECURITY, Capture.from("security"))
    }
}
