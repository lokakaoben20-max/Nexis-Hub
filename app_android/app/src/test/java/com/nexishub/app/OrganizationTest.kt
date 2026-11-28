package com.nexishub.app

import com.nexishub.app.data.DemoRepository
import com.nexishub.app.data.NexisRefusal
import com.nexishub.app.data.OrgDemo
import com.nexishub.app.data.OrgDocKind
import com.nexishub.app.data.OrgDocState
import com.nexishub.app.data.OrgDraft
import com.nexishub.app.data.OrgFunction
import com.nexishub.app.data.OrgStatus
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class OrgDraftTest {
    @Test
    fun emailNeedsAnAtAndADomain() {
        assertTrue(OrgDraft.isEmail("contact@kasaservices.cd"))
        assertFalse(OrgDraft.isEmail("contact"))
        assertFalse(OrgDraft.isEmail("@kasa.cd"))
        assertFalse(OrgDraft.isEmail("contact@kasa"))
        assertFalse(OrgDraft.isEmail("con tact@kasa.cd"))
        assertFalse(OrgDraft.isEmail("a@b@kasa.cd"))
    }

    @Test
    fun firstStepNeedsEveryField() {
        val full = OrgDemo.draft(documents = false)
        assertTrue(full.step1Ready)
        assertFalse(full.copy(name = " ").step1Ready)
        assertFalse(full.copy(nif = "").step1Ready)
        assertFalse(full.copy(commune = null).step1Ready)
        assertFalse(full.copy(email = "contact").step1Ready)
    }

    @Test
    fun verifiedPersonIsNeverAskedForIdentityAgain() {
        val draft = OrgDemo.draft(documents = false)
        assertTrue(draft.step2Ready(identityVerified = true, identityTaken = false))
        assertFalse(draft.step2Ready(identityVerified = false, identityTaken = false))
        assertTrue(draft.step2Ready(identityVerified = false, identityTaken = true))
    }

    @Test
    fun otherRepresentativeNeedsAValidPhoneNotAnIdentity() {
        val draft = OrgDemo.draft(documents = false).copy(representativeIsMe = false)
        assertFalse(draft.step2Ready(identityVerified = false, identityTaken = false))
        assertTrue(draft.copy(representativePhone = "812345678").step2Ready(false, false))
    }

    @Test
    fun otherFunctionNeedsAText() {
        val draft = OrgDemo.draft(documents = false).copy(function = OrgFunction.OTHER)
        assertFalse(draft.step2Ready(identityVerified = true, identityTaken = false))
        assertTrue(draft.copy(functionOther = "Gérante").step2Ready(true, false))
    }

    @Test
    fun documentsStepNeedsAllThree() {
        val draft = OrgDemo.draft(documents = false)
        assertFalse(draft.step3Ready)
        assertFalse(draft.copy(documents = setOf(OrgDocKind.RCCM, OrgDocKind.NIF)).step3Ready)
        assertTrue(OrgDemo.draft(documents = true).step3Ready)
    }
}

class OrganizationRequestTest {
    private fun refusal(block: suspend () -> Unit): String? = runBlocking {
        try { block(); null } catch (e: NexisRefusal) { e.code }
    }

    @Test
    fun requestWithoutAcceptedTermsIsRefused() {
        val repo = DemoRepository()
        assertEquals("organization_invalid", refusal {
            repo.createOrganization(OrgDemo.draft(documents = true), null, null)
        })
    }

    @Test
    fun incompleteDocumentsAreRefused() {
        val repo = DemoRepository()
        assertEquals("organization_invalid", refusal {
            repo.createOrganization(OrgDemo.draft(documents = false), repo.orgTermsVersion, null)
        })
    }

    @Test
    fun verifiedPersonSendsNoIdentity() = runBlocking {
        val repo = DemoRepository()
        val before = repo.organizations().size
        val org = repo.createOrganization(OrgDemo.draft(documents = true), repo.orgTermsVersion, null)
        assertEquals(OrgStatus.REVIEWING, org.status)
        assertEquals("Kasa Services SARLU", org.name)
        assertEquals("Kasa Services", org.shortName)
        assertEquals(before + 1, repo.organizations().size)
        assertNotNull(repo.organization(org.id))
    }

    @Test
    fun replacingADocumentOnlyWorksWhenTheTeamAskedForIt() {
        val repo = DemoRepository()
        val code = refusal {
            val org = repo.createOrganization(OrgDemo.draft(documents = true), repo.orgTermsVersion, null)
            repo.replaceDocument(org.id, OrgDocKind.NIF)
        }
        assertEquals("document_not_requested", code)
    }

    @Test
    fun correctionReturnsToReviewOnceTheDocumentIsReplaced() = runBlocking {
        val repo = DemoRepository()
        repo.demoPreset("org-correction")
        val org = repo.organizations().single()
        assertEquals(OrgStatus.CORRECTION, org.status)
        assertEquals(OrgDocState.TO_REDO, org.documents.first { it.kind == OrgDocKind.NIF }.state)
        repo.replaceDocument(org.id, OrgDocKind.NIF)
        val after = repo.organization(org.id)
        assertEquals(OrgStatus.REVIEWING, after.status)
        assertTrue(after.documents.all { it.state == OrgDocState.RECEIVED })
    }
}
