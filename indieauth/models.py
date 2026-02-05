from django.conf import settings
from django.db import models


class IndieAuthClient(models.Model):
    client_id = models.URLField(max_length=2000, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    logo_url = models.URLField(max_length=2000, blank=True, default="")
    redirect_uris = models.JSONField(default=list, blank=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    fetch_error = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name or self.client_id


class IndieAuthAuthorizationCode(models.Model):
    code_hash = models.CharField(max_length=64, unique=True)
    code_challenge = models.CharField(max_length=255)
    code_challenge_method = models.CharField(max_length=32, default="S256")
    client_id = models.URLField(max_length=2000)
    redirect_uri = models.URLField(max_length=2000)
    me = models.URLField(max_length=2000)
    scope = models.TextField(blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.client_id} -> {self.me}"


class IndieAuthAccessToken(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    client_id = models.URLField(max_length=2000)
    me = models.URLField(max_length=2000)
    scope = models.TextField(blank=True, default="")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.client_id} -> {self.me}"


class IndieAuthConsent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_id = models.URLField(max_length=2000)
    scope = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["user", "client_id", "scope"]

    def __str__(self):
        return f"{self.user_id} {self.client_id}"


class IndieAuthRequestLog(models.Model):
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    status_code = models.PositiveSmallIntegerField()
    error = models.TextField(blank=True)
    request_headers = models.JSONField(default=dict)
    request_query = models.JSONField(default=dict)
    request_body = models.TextField(blank=True)
    response_body = models.TextField(blank=True)
    remote_addr = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.path} -> {self.status_code}"
