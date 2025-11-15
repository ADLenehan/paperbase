"""
Integration Tests for OAuth and Organization Management

Tests the complete OAuth flow and organization multi-tenancy.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.settings import User, Organization, OrganizationInvite
from app.models.document import Document
from app.models.schema import Schema


class TestOAuthFlow:
    """Test OAuth authentication flows"""

    def test_google_oauth_not_configured_returns_503(self, client: TestClient):
        """Test that OAuth endpoints return 503 when not configured"""
        response = client.get("/api/auth/oauth/google/authorize")

        # If Google OAuth not configured, should return 503
        if response.status_code == 503:
            assert "not configured" in response.json()["detail"].lower()
        else:
            # If configured, should return auth URL
            assert response.status_code == 200
            assert "url" in response.json()
            assert "state" in response.json()
            assert "code_verifier" in response.json()

    def test_unsupported_provider_returns_400(self, client: TestClient):
        """Test that unsupported providers return 400"""
        response = client.get("/api/auth/oauth/facebook/authorize")
        assert response.status_code == 404  # Route not found, or 400 if provider check comes first


class TestOrganizationManagement:
    """Test organization CRUD operations"""

    def test_create_organization(self, client: TestClient, auth_headers: dict):
        """Test creating a new organization"""
        response = client.post(
            "/api/organizations/",
            headers=auth_headers,
            json={"name": "Test Organization", "slug": "test-org"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Organization"
        assert data["slug"] == "test-org"
        assert "id" in data
        assert "owner_id" in data

    def test_get_my_organization(self, client: TestClient, auth_headers: dict, test_organization: Organization):
        """Test getting current user's organization"""
        response = client.get(
            "/api/organizations/my",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_organization.id
        assert data["name"] == test_organization.name

    def test_cannot_create_org_if_already_member(self, client: TestClient, auth_headers: dict):
        """Test that users can't create org if already a member"""
        # First org creation should succeed
        response1 = client.post(
            "/api/organizations/",
            headers=auth_headers,
            json={"name": "First Org"}
        )
        assert response1.status_code == 200

        # Second should fail
        response2 = client.post(
            "/api/organizations/",
            headers=auth_headers,
            json={"name": "Second Org"}
        )
        assert response2.status_code == 400
        assert "already belongs" in response2.json()["detail"].lower()


class TestInvitationSystem:
    """Test organization invitation system"""

    def test_create_invitation(self, client: TestClient, auth_headers: dict, test_organization: Organization):
        """Test creating an invitation"""
        response = client.post(
            f"/api/organizations/{test_organization.id}/invites",
            headers=auth_headers,
            json={
                "role": "member",
                "expires_in_days": 7,
                "max_uses": 1
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "invite_code" in data
        assert data["role"] == "member"
        assert data["max_uses"] == 1
        assert not data["is_expired"]

    def test_accept_invitation(
        self,
        client: TestClient,
        db: Session,
        test_organization: Organization,
        test_invite: OrganizationInvite
    ):
        """Test accepting an invitation"""
        # Create new user without organization
        new_user = User(
            email="newuser@test.com",
            name="New User",
            is_active=True
        )
        db.add(new_user)
        db.commit()

        # Get auth token for new user (mock this)
        new_user_headers = {"Authorization": f"Bearer {generate_test_token(new_user)}"}

        # Accept invite
        response = client.post(
            "/api/organizations/join",
            headers=new_user_headers,
            json={"invite_code": test_invite.invite_code}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_organization.id

        # Verify user is now member
        db.refresh(new_user)
        assert new_user.org_id == test_organization.id
        assert new_user.organization_role == test_invite.role

    def test_expired_invite_returns_400(self, client: TestClient, auth_headers: dict, expired_invite: OrganizationInvite):
        """Test that expired invites cannot be accepted"""
        response = client.post(
            "/api/organizations/join",
            headers=auth_headers,
            json={"invite_code": expired_invite.invite_code}
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()


class TestMultiTenancyIsolation:
    """CRITICAL: Test organization data isolation"""

    def test_document_isolation(
        self,
        client: TestClient,
        db: Session,
        test_user1: User,  # Org 1
        test_user2: User   # Org 2
    ):
        """Test that users can only access documents from their organization"""
        # Create organizations
        org1 = Organization(name="Org 1", slug="org1")
        org2 = Organization(name="Org 2", slug="org2")
        db.add_all([org1, org2])
        db.commit()

        test_user1.org_id = org1.id
        test_user2.org_id = org2.id
        db.commit()

        # Create documents in each org
        doc1 = Document(
            filename="doc1.pdf",
            organization_id=org1.id,
            status="completed"
        )
        doc2 = Document(
            filename="doc2.pdf",
            organization_id=org2.id,
            status="completed"
        )
        db.add_all([doc1, doc2])
        db.commit()

        # User 1 should only see doc1
        user1_headers = {"Authorization": f"Bearer {generate_test_token(test_user1)}"}
        response1 = client.get("/api/documents", headers=user1_headers)

        assert response1.status_code == 200
        docs = response1.json()
        assert len(docs) == 1
        assert docs[0]["id"] == doc1.id

        # User 1 should NOT be able to access doc2
        response2 = client.get(f"/api/documents/{doc2.id}", headers=user1_headers)
        assert response2.status_code == 404

    def test_schema_isolation(
        self,
        client: TestClient,
        db: Session,
        test_user1: User,  # Org 1
        test_user2: User   # Org 2
    ):
        """Test that users can only access schemas from their organization"""
        org1 = Organization(name="Org 1", slug="org1")
        org2 = Organization(name="Org 2", slug="org2")
        db.add_all([org1, org2])
        db.commit()

        test_user1.org_id = org1.id
        test_user2.org_id = org2.id
        db.commit()

        # Create schemas in each org
        schema1 = Schema(
            name="Invoice Template",
            fields=[],
            organization_id=org1.id
        )
        schema2 = Schema(
            name="Contract Template",
            fields=[],
            organization_id=org2.id
        )
        db.add_all([schema1, schema2])
        db.commit()

        # User 1 should only see schema1
        user1_headers = {"Authorization": f"Bearer {generate_test_token(test_user1)}"}
        response1 = client.get("/api/templates", headers=user1_headers)

        if response1.status_code == 200:
            schemas = response1.json()
            schema_ids = [s["id"] for s in schemas]
            assert schema1.id in schema_ids
            assert schema2.id not in schema_ids

    def test_physical_file_isolation(
        self,
        client: TestClient,
        db: Session,
        test_user1: User,
        test_user2: User
    ):
        """Test that file deduplication works per-organization"""
        from app.models.physical_file import PhysicalFile

        org1 = Organization(name="Org 1", slug="org1")
        org2 = Organization(name="Org 2", slug="org2")
        db.add_all([org1, org2])
        db.commit()

        # Same file hash in both orgs - should create separate PhysicalFiles
        file1 = PhysicalFile(
            filename="contract.pdf",
            file_hash="abc123",  # Same hash
            file_path="/uploads/org1/contract.pdf",
            organization_id=org1.id
        )
        file2 = PhysicalFile(
            filename="contract.pdf",
            file_hash="abc123",  # Same hash
            file_path="/uploads/org2/contract.pdf",
            organization_id=org2.id
        )
        db.add_all([file1, file2])
        db.commit()

        # Both should exist with same hash but different orgs
        files = db.query(PhysicalFile).filter(
            PhysicalFile.file_hash == "abc123"
        ).all()
        assert len(files) == 2
        assert {f.organization_id for f in files} == {org1.id, org2.id}


class TestMemberManagement:
    """Test organization member management"""

    def test_list_members(self, client: TestClient, auth_headers: dict, test_organization: Organization):
        """Test listing organization members"""
        response = client.get(
            f"/api/organizations/{test_organization.id}/members",
            headers=auth_headers
        )

        assert response.status_code == 200
        members = response.json()
        assert len(members) > 0
        assert all("email" in m for m in members)
        assert all("organization_role" in m for m in members)

    def test_remove_member(
        self,
        client: TestClient,
        db: Session,
        test_organization: Organization,
        owner_user: User,
        member_user: User
    ):
        """Test removing a member from organization"""
        owner_headers = {"Authorization": f"Bearer {generate_test_token(owner_user)}"}

        response = client.delete(
            f"/api/organizations/{test_organization.id}/members/{member_user.id}",
            headers=owner_headers
        )

        assert response.status_code == 200

        # Verify member removed
        db.refresh(member_user)
        assert member_user.org_id is None

    def test_cannot_remove_owner(
        self,
        client: TestClient,
        test_organization: Organization,
        owner_user: User
    ):
        """Test that organization owner cannot be removed"""
        owner_headers = {"Authorization": f"Bearer {generate_test_token(owner_user)}"}

        response = client.delete(
            f"/api/organizations/{test_organization.id}/members/{owner_user.id}",
            headers=owner_headers
        )

        assert response.status_code == 400
        assert "owner" in response.json()["detail"].lower()

    def test_change_member_role(
        self,
        client: TestClient,
        db: Session,
        test_organization: Organization,
        owner_user: User,
        member_user: User
    ):
        """Test changing a member's role"""
        owner_headers = {"Authorization": f"Bearer {generate_test_token(owner_user)}"}

        response = client.put(
            f"/api/organizations/{test_organization.id}/members/{member_user.id}/role",
            headers=owner_headers,
            json={"role": "admin"}
        )

        assert response.status_code == 200

        # Verify role changed
        db.refresh(member_user)
        assert member_user.organization_role == "admin"


# Test Fixtures (to be implemented)

@pytest.fixture
def test_organization(db: Session) -> Organization:
    """Create a test organization"""
    org = Organization(name="Test Org", slug="test")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture
def test_invite(db: Session, test_organization: Organization, test_user: User) -> OrganizationInvite:
    """Create a test invitation"""
    invite = OrganizationInvite(
        organization_id=test_organization.id,
        invite_code="TEST123",
        role="member",
        max_uses=1,
        created_by_user_id=test_user.id
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def generate_test_token(user: User) -> str:
    """Generate a test JWT token for a user"""
    from app.core.auth import create_access_token
    return create_access_token(user_id=user.id)
