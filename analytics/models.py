from django.db import models
from django.conf import settings


class Visit(models.Model):
    session_key = models.CharField(max_length=40, db_index=True, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, db_index=True)
    path = models.CharField(max_length=512)
    referrer = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)
    region = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=128, blank=True)
    response_status_code = models.IntegerField(null=True, blank=True)
    user_agent_details = models.JSONField(null=True, blank=True)
    is_suspected_bot = models.BooleanField(default=False, db_index=True)
    suspected_bot_pattern_version = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return self.path

    class Meta:
        indexes = [
            models.Index(fields=["path"]),
            models.Index(fields=["session_key", "started_at"]),
        ]


class UserAgentIgnore(models.Model):
    user_agent = models.TextField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user_agent


class UserAgentBotRule(models.Model):
    pattern = models.TextField(blank=True, default="")
    enabled = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User agent bot rule"
        verbose_name_plural = "User agent bot rule"

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                UserAgentBotRule.objects.filter(pk=self.pk)
                .values("pattern", "enabled", "version")
                .first()
            )
            if previous and (
                previous["pattern"] != self.pattern
                or previous["enabled"] != self.enabled
            ):
                self.version = previous["version"] + 1
        super().save(*args, **kwargs)

    @classmethod
    def get_current(cls):
        rule = cls.objects.order_by("id").first()
        if rule:
            return rule
        return cls.objects.create()


class UserAgentFalsePositive(models.Model):
    user_agent = models.TextField(unique=True)
    note = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("user_agent", "id")

    def __str__(self):
        return self.user_agent
