from django.db import models


class WidgetInstance(models.Model):
    widget_type = models.CharField(max_length=64)
    area = models.CharField(max_length=64)
    order = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["area", "order", "pk"]

    def __str__(self):
        return f"{self.widget_type} in {self.area} (order={self.order})"
