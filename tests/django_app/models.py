from django.db import models


class Bar(models.Model):
    right = models.CharField(max_length=10, null=True)
    wrong = models.CharField(max_length=10, null=True)
