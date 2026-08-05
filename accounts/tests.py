from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class RoleSystemTests(TestCase):
    def test_admin_role_sets_staff_permissions(self):
        user = User.objects.create_user(
            username="admin@example.com",
            email="admin@example.com",
            password="testpass123",
            full_name="Admin User",
            role=User.Role.SUPER_ADMIN,
            is_approved=True,
        )

        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff)

    def test_superuser_defaults_to_admin_role(self):
        user = User.objects.create_superuser(
            username="root@example.com",
            email="root@example.com",
            password="testpass123",
            full_name="Root User",
        )

        self.assertEqual(user.role, User.Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_approved)

    def test_login_redirects_to_role_dashboard(self):
        user = User.objects.create_user(
            username="citizen@example.com",
            email="citizen@example.com",
            password="testpass123",
            full_name="Citizen User",
            role=User.Role.CITIZEN,
            is_active=True,
            is_approved=True,
        )

        response = self.client.post(
            reverse("accounts:login", kwargs={"role": User.Role.CITIZEN}),
            {"email": user.email, "password": "testpass123"},
        )

        self.assertRedirects(response, reverse("dashboards:citizen_dashboard"))

    def test_admin_view_rejects_non_admin_user(self):
        user = User.objects.create_user(
            username="citizen2@example.com",
            email="citizen2@example.com",
            password="testpass123",
            full_name="Citizen User 2",
            role=User.Role.CITIZEN,
            is_active=True,
            is_approved=True,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("dashboards:admin_dashboard"))

        self.assertRedirects(response, reverse("dashboards:citizen_dashboard"))
