from django.contrib import admin

from .models import Answer, Evaluation, EvaluationCycle, PeerAssignment

admin.site.register(EvaluationCycle)
admin.site.register(PeerAssignment)
admin.site.register(Evaluation)
admin.site.register(Answer)
