from django.db import models


class Channel(models.Model):
    uid = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="subscriptions")
    url = models.URLField(max_length=2000)
    name = models.CharField(max_length=255, blank=True)
    photo = models.URLField(max_length=2000, blank=True)
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    fetch_error = models.TextField(blank=True)
    websub_hub = models.URLField(max_length=2000, blank=True)
    websub_secret = models.CharField(max_length=255, blank=True)
    websub_subscribed_at = models.DateTimeField(null=True, blank=True)
    websub_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["channel", "url"]]

    def __str__(self):
        return f"{self.url} in {self.channel}"


class Entry(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="entries")
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    uid = models.TextField()
    data = models.JSONField()
    published = models.DateTimeField()
    is_read = models.BooleanField(default=False, db_index=True)
    is_removed = models.BooleanField(default=False, db_index=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["channel", "uid"]]
        ordering = ["-published"]

    def __str__(self):
        return f"Entry {str(self.uid)[:50]}"


class MutedUser(models.Model):
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="muted_users",
    )
    url = models.URLField(max_length=2000)

    class Meta:
        unique_together = [["channel", "url"]]

    def __str__(self):
        return f"Muted {self.url}"


class BlockedUser(models.Model):
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="blocked_users",
    )
    url = models.URLField(max_length=2000)

    class Meta:
        unique_together = [["channel", "url"]]

    def __str__(self):
        return f"Blocked {self.url}"
